"""Normal-path graph and in-memory RAG HTTP contract tests; no provider calls."""
import sys
from pathlib import Path
import unittest

import httpx
from fastapi import FastAPI
from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.graph.state import (RAGRequest, ScopeDecision, EvidenceDecision, ComparisonResult,
                             PolicyMatch, AnswerDraft)
from app.graph.workflow import PolicyRagService
from app.graph.nodes import LLMReasoner
from app.tools.local_rag import LocalRAGRetriever
from unittest.mock import Mock, patch
from app.tools.youth_policy_api import ApiLookupResult

DOC = Document(page_content='청년 월세 지원의 대상과 신청 방법',
               metadata={'source':'https://www.youthcenter.go.kr/', 'title':'테스트 정책'})


class Retriever:
    def __init__(self, documents): self.documents = documents; self.calls = 0
    async def search(self, *args): self.calls += 1; return self.documents


class Agent:
    configured = True
    def __init__(self): self.calls = 0
    async def lookup(self, query, missing_information, **kwargs):
        self.calls += 1
        return ApiLookupResult(documents=[DOC], status='used')


class Reasoner:
    async def scope(self, question): return ScopeDecision(in_scope=True, reason='청년정책')
    async def review(self, payload):
        return EvidenceDecision(sufficient=True,
            usable_ids=[d['evidence_id'] for d in payload['documents']],
            missing_information=[], reason='조건 비교 근거 있음')
    async def compare(self, payload):
        ids = [d['evidence_id'] for d in payload['documents']]
        return ComparisonResult(policies=[PolicyMatch(policy_name='테스트 정책', status='needs_review',
            reason='소득 추가 확인', missing_fields=['소득 증빙'], evidence_ids=ids)], follow_up_question='')
    async def generate(self, payload):
        identifier = payload['documents'][0]['evidence_id']
        return AnswerDraft(answer=f'정책 조건을 확인하세요. [{identifier}]', cited_ids=[identifier])


def request(**changes):
    data = dict(question='주거 정책을 검색해줘', profile=dict(age=25, region='서울', statuses=['unemployed'], interests=['housing'], details=['월세·주거비']), source='web')
    data.update(changes)
    return RAGRequest(**data)


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_review_cannot_silently_drop_rag_candidate(self):
        class ChangingReasoner(Reasoner):
            async def review(self, payload):
                after_api = any(doc['origin'] == 'policy_api' for doc in payload['documents'])
                return EvidenceDecision(sufficient=True, usable_ids=['A1'] if after_api else ['V1', 'V2'],
                                        missing_information=['모집 여부'], reason='정책 개요')
            async def compare(self, payload):
                after_api = any(doc['origin'] == 'policy_api' for doc in payload['documents'])
                policies = [PolicyMatch(policy_name='인턴', status='candidate', reason='연령 부합',
                                        missing_fields=[], evidence_ids=['V1'])]
                if not after_api:
                    policies.append(PolicyMatch(policy_name='청년수당', status='candidate', reason='미취업 조건 부합',
                                                missing_fields=[], evidence_ids=['V2']))
                return ComparisonResult(policies=policies, follow_up_question='')
        docs = [DOC, Document(page_content='청년수당 지원 내용', metadata=DOC.metadata)]
        agent = Agent()
        result = await PolicyRagService(Retriever(docs), ChangingReasoner(), agent).answer_question(request())
        self.assertEqual({p.policy_name for p in result.policies}, {'인턴', '청년수당'})
        self.assertEqual(agent.calls, 1)
        self.assertEqual(next(p for p in result.policies if p.policy_name == '청년수당').status, 'needs_review')

    async def test_failed_supplement_preserves_rag_answer_and_policy_query(self):
        class FailedAgent:
            calls = 0
            async def lookup(self, query, missing_information, **kwargs):
                self.calls += 1
                self.query = query
                return ApiLookupResult(status='failed')
        agent = FailedAgent()
        doc = Document(page_content=DOC.page_content, metadata={
            **DOC.metadata, 'record_type': 'policy_evidence', 'title': '서울 청년수당'})
        result = await PolicyRagService(Retriever([doc]), Reasoner(), agent).answer_question(request())
        self.assertEqual(agent.calls, 1)
        self.assertEqual(agent.query, '서울 청년수당')
        self.assertEqual(result.status, 'answered')
        self.assertEqual(result.api_status, 'failed')
        self.assertTrue(result.citations)

    async def test_policy_details_survive_graph_response(self):
        class DetailReasoner(Reasoner):
            async def compare(self, payload):
                return ComparisonResult(policies=[PolicyMatch(
                    policy_name='청년 월세 지원', status='needs_review', reason='현재 모집 확인 필요',
                    missing_fields=[], evidence_ids=['V1'], benefit='월 최대 20만원 지원',
                    application_period={'display': '2026. 3. 1. ~ 2026. 3. 31.'})], follow_up_question='')
        document = Document(page_content='월 최대 20만원 지원. 신청 기간: 2026. 3. 1. ~ 2026. 3. 31.',
                            metadata=DOC.metadata)
        result = await PolicyRagService(Retriever([document]), DetailReasoner(), Agent()).answer_question(request())
        policy = result.model_dump()['policies'][0]
        self.assertEqual(policy['benefit'], '월 최대 20만원 지원')
        self.assertEqual(policy['application_period']['display'], '2026. 3. 1. ~ 2026. 3. 31.')
        self.assertEqual(policy['status'], 'needs_review')
        self.assertTrue(result.needs_review)

    async def test_unknown_policy_details_are_null(self):
        result = await PolicyRagService(Retriever([DOC]), Reasoner(), Agent()).answer_question(request())
        policy = result.model_dump()['policies'][0]
        self.assertIsNone(policy['benefit'])
        self.assertIsNone(policy['application_period'])

    async def test_compare_requests_grounded_details_with_nullable_schema(self):
        captured = {}
        class RecordingReasoner(LLMReasoner):
            async def _ask(self, schema, instruction, payload):
                captured.update(schema=schema, instruction=instruction, payload=payload)
                return ComparisonResult(policies=[], follow_up_question='')
        await RecordingReasoner().compare({'documents': []})
        self.assertIs(captured['schema'], ComparisonResult)
        self.assertIn('benefit', captured['instruction'])
        self.assertIn('application_period.display', captured['instruction'])
        self.assertIn('지급 기간', captured['instruction'])
        self.assertIn('null', captured['instruction'])
        schema = ComparisonResult.model_json_schema()
        properties = schema['$defs']['PolicyMatch']['properties']
        self.assertIn('benefit', properties)
        self.assertIn('application_period', properties)

    async def test_sufficient_rag_with_unknown_recruitment_uses_agent_once(self):
        agent = Agent()
        result = await PolicyRagService(Retriever([DOC]), Reasoner(), agent).answer_question(request())
        self.assertEqual(result.status, 'answered')
        self.assertEqual(agent.calls, 1)
        self.assertEqual(result.api_status, 'used')
        self.assertTrue(result.citations)
        self.assertTrue(result.needs_review)

    async def test_insufficient_rag_uses_agent_once_then_reassesses(self):
        agent = Agent()
        result = await PolicyRagService(Retriever([]), Reasoner(), agent).answer_question(request())
        self.assertEqual(agent.calls, 1)
        self.assertEqual(result.api_status, 'used')
        self.assertEqual(result.node_path.count('assess_information'), 2)
        self.assertEqual(result.citations[0].origin, 'policy_api')

    async def test_survey_without_income_reaches_recommendation(self):
        req = request()
        self.assertIsNone(req.profile.income)
        result = await PolicyRagService(Retriever([DOC]), Reasoner(), Agent()).answer_question(req)
        self.assertEqual(result.status, 'answered')
        self.assertTrue(result.needs_review)

    async def test_internal_rag_to_graph(self):
        store = Mock()
        store.similarity_search_with_score.return_value = [(DOC, 0.2)]
        with patch('app.tools.local_rag.load_vectorstore', return_value=store):
            result = await PolicyRagService(LocalRAGRetriever(), Reasoner(), Agent()).answer_question(request())
        self.assertEqual(result.status, 'answered')
        self.assertEqual(result.citations[0].origin, 'vector_db')


    async def test_policy_facts_answered_with_citations_and_unverified_recruitment_notice(self):
        class PartialReasoner(Reasoner):
            async def review(self, payload):
                return EvidenceDecision(sufficient=True, application_status_verified=False,
                    usable_ids=['V1'], missing_information=['현재 모집 공고'], reason='정책 개요는 확인 가능')
            async def compare(self, payload):
                self.asserted_review = payload['evidence_review']
                return ComparisonResult(policies=[PolicyMatch(policy_name='테스트 정책',
                    status='candidate', reason='문서상 정책 내용 확인', missing_fields=[], evidence_ids=['V1'])],
                    follow_up_question='')
            async def generate(self, payload):
                assert not payload['evidence_review']['application_status_verified']
                return AnswerDraft(answer='2026년 시행계획 103쪽에 청년 월세 지원 내용이 있습니다. [V1]', cited_ids=['V1'])
        reasoner, agent = PartialReasoner(), Agent()
        result = await PolicyRagService(Retriever([DOC]), reasoner, agent).answer_question(request())
        self.assertEqual(result.status, 'answered')
        self.assertIn('2026년 시행계획', result.answer)
        self.assertIn('현재 모집 여부·신청 가능 여부: 최신 공식 공고 확인이 필요합니다.', result.answer)
        self.assertTrue(result.citations)
        self.assertTrue(result.needs_review)
        self.assertEqual(result.policies[0].status, 'needs_review')
        self.assertEqual(agent.calls, 1)

    async def test_planning_document_cannot_verify_current_recruitment(self):
        class OptimisticReasoner(Reasoner):
            async def review(self, payload):
                return EvidenceDecision(sufficient=True, application_status_verified=True,
                    usable_ids=['V1'], missing_information=[], reason='공식 계획')
        plan = Document(page_content=DOC.page_content,
            metadata={**DOC.metadata, 'authority':'planning_document', 'application_status':'unverified'})
        result = await PolicyRagService(Retriever([plan]), OptimisticReasoner(), Agent()).answer_question(request())
        self.assertIn('최신 공식 공고 확인', result.answer)
        self.assertTrue(result.needs_review)

    async def test_no_evidence_still_refuses_and_has_no_citations(self):
        class EmptyAgent:
            async def lookup(self, *args, **kwargs): return ApiLookupResult(documents=[], status='no_results')
        result = await PolicyRagService(Retriever([]), Reasoner(), EmptyAgent()).answer_question(request())
        self.assertEqual(result.status, 'insufficient')
        self.assertFalse(result.citations)
        self.assertNotIn('generate', result.node_path)

    async def test_unrelated_evidence_is_not_promoted_to_supported_answer(self):
        class IrrelevantReasoner(Reasoner):
            async def review(self, payload):
                return EvidenceDecision(sufficient=False, usable_ids=[], missing_information=['관련 본문'], reason='무관')
        class EmptyAgent:
            async def lookup(self, *args, **kwargs): return ApiLookupResult(documents=[], status='no_results')
        result = await PolicyRagService(Retriever([DOC]), IrrelevantReasoner(), EmptyAgent()).answer_question(request())
        self.assertEqual(result.status, 'insufficient')
        self.assertFalse(result.citations)

    async def test_verified_recruitment_has_no_blanket_unverified_notice(self):
        class VerifiedReasoner(Reasoner):
            async def review(self, payload):
                return EvidenceDecision(sufficient=True, application_status_verified=True,
                    usable_ids=['V1'], missing_information=[], reason='현재 공식 공고 확인')
        result = await PolicyRagService(Retriever([DOC]), VerifiedReasoner(), Agent()).answer_question(request())
        self.assertNotIn('현재 모집 여부·신청 가능 여부:', result.answer)

    async def test_invalid_generated_citation_still_rejected(self):
        class InvalidReasoner(Reasoner):
            async def generate(self, payload):
                return AnswerDraft(answer='근거 없는 내용 [V999]', cited_ids=['V999'])
        with self.assertRaises(ValueError):
            await PolicyRagService(Retriever([DOC]), InvalidReasoner(), Agent()).answer_question(request())

    async def test_partial_answer_review_contract(self):
        captured = {}
        class RecordingReasoner(LLMReasoner):
            async def _ask(self, schema, instruction, payload):
                captured['instruction'] = instruction
                return EvidenceDecision(sufficient=True, usable_ids=['V1'], missing_information=['모집 공고'], reason='개요 있음')
        await RecordingReasoner().review({})
        self.assertIn('현재 모집 여부·최신 공고·신청 절차가 없다는 이유만으로 정책 개요 안내까지 거절하지 마라', captured['instruction'])
        self.assertIn('안내할 모든 정책의 공식 공고', captured['instruction'])


if __name__ == '__main__': unittest.main()

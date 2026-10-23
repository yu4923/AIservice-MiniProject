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
    async def lookup(self, query, missing_information):
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
    data = dict(question='주거 정책을 추천해줘', profile=dict(age=25, region='서울', statuses=['unemployed'], interests=['housing'], details=['월세·주거비']), source='web')
    data.update(changes)
    return RAGRequest(**data)


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_sufficient_rag_skips_agent(self):
        agent = Agent()
        result = await PolicyRagService(Retriever([DOC]), Reasoner(), agent).answer_question(request())
        self.assertEqual(result.status, 'answered')
        self.assertEqual(agent.calls, 0)
        self.assertEqual(result.api_status, 'not_used')
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


if __name__ == '__main__': unittest.main()

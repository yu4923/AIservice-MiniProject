"""Python 3.11: 가짜 검색·모델·Agent로 요청부터 Graph 응답까지 검사합니다."""

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from pydantic import ValidationError

from app.agents.policy_agent import GraphPolicyAgent
from app.graph.nodes import LLMReasoner, to_evidence
from app.graph.state import (
    POLICY_CORPUS, AnswerDraft, ComparisonResult, EvidenceDecision,
    PolicyMatch, RAGRequest as GraphRequest, ScopeDecision,
)
from app.graph.workflow import PolicyRagService
from app.input_validation import DEFAULT_QUESTION, RAGRequest
from app.tools.youth_policy_api import ApiLookupResult


def request_body(**updates):
    """실제 개인정보 대신 고정된 예시 설문을 매번 새 객체로 만듭니다."""
    body = {"profile": {
        "age": 25, "region": "울산", "statuses": ["unemployed"],
        "interests": ["employment", "housing"], "details": ["면접 지원", "월세·주거비"],
        "income": "월 소득 0원", "employment_status": "미취업", "household_size": 1,
    }}
    body.update(updates)
    return body


def document(index=1, **metadata):
    return Document(page_content=f"정책 {index}의 지원 조건과 내용",
                    metadata={"source": f"https://example.invalid/{index}", **metadata})


class FakeRetriever:
    def __init__(self, documents=()):
        self.documents = list(documents)
        self.calls = []

    async def search(self, query, source, top_k):
        self.calls.append((query, source, top_k))
        return self.documents[:top_k]


class FakeReasoner:
    """모델의 정확도를 평가하지 않고, 구조화된 결과를 받은 뒤의 코드 흐름만 검사합니다."""

    def __init__(self, *, keywords=("창업",), sufficient=True, in_scope=True):
        self.keywords = list(keywords)
        self.sufficient = sufficient
        self.in_scope = in_scope
        self.calls = []

    async def scope(self, question):
        self.calls.append(("scope", question))
        return ScopeDecision(in_scope=self.in_scope, reason="테스트", search_keywords=self.keywords)

    async def review(self, payload):
        self.calls.append(("review", payload))
        return EvidenceDecision(sufficient=self.sufficient,
            usable_ids=[doc["evidence_id"] for doc in payload["documents"]],
            missing_information=[] if self.sufficient else ["모집 기간"], reason="테스트")

    async def compare(self, payload):
        self.calls.append(("compare", payload))
        return ComparisonResult(policies=[PolicyMatch(policy_name="테스트 정책", status="candidate",
            reason="테스트 조건 비교", missing_fields=[],
            evidence_ids=[doc["evidence_id"] for doc in payload["documents"]])], follow_up_question="")

    async def generate(self, payload):
        self.calls.append(("generate", payload))
        evidence_id = payload["documents"][0]["evidence_id"]
        return AnswerDraft(answer=f"확인된 근거에 따른 안내 [{evidence_id}]", cited_ids=[evidence_id])


class FakeAgent:
    def __init__(self, *, status="used", fail_on_call=None):
        self.status = status
        self.fail_on_call = fail_on_call
        self.calls = []

    async def lookup(self, query, missing_information):
        self.calls.append((query, missing_information))
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("테스트 API 오류")
        if self.status == "timeout":
            raise TimeoutError
        return ApiLookupResult(status=self.status,
            documents=[document(len(self.calls))] if self.status == "used" else [])


class InputTests(unittest.TestCase):
    def test_missing_null_and_blank_questions_get_default(self):
        bodies = [request_body()] + [request_body(question=value) for value in (None, "", " \t\n ")]
        for body in bodies:
            with self.subTest(body_has_question="question" in body):
                request = RAGRequest.model_validate(body)
                self.assertEqual(request.question, DEFAULT_QUESTION)
                self.assertTrue(request.question_is_generated)
                self.assertTrue(RAGRequest.model_validate(request).question_is_generated)

    def test_supplied_question_is_preserved_even_if_equal_to_default(self):
        for text in ("창업 자금을 알려줘", DEFAULT_QUESTION):
            request = RAGRequest.model_validate(request_body(question=f"  {text}  "))
            self.assertEqual(request.question, text)
            self.assertFalse(request.question_is_generated)

    def test_prompt_alias_still_works(self):
        request = RAGRequest.model_validate(request_body(prompt="면접비 정책을 알려줘"))
        self.assertEqual(request.question, "면접비 정책을 알려줘")
        self.assertFalse(request.question_is_generated)
        self.assertTrue(RAGRequest.model_validate(request_body(prompt=" ")).question_is_generated)

    def test_invalid_nonempty_questions_are_rejected(self):
        for value in (123, True, [], "가", "가" * 1001):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValidationError):
                    RAGRequest.model_validate(request_body(question=value))

    def test_source_and_top_k_contract(self):
        request = RAGRequest.model_validate(request_body())
        self.assertEqual((request.source, request.top_k), ("pdf", 5))
        for source in ("all", "pdf", "web"):
            for top_k in (1, 5, 10, 20):
                with self.subTest(source=source, top_k=top_k):
                    request = RAGRequest.model_validate(request_body(source=source, top_k=top_k))
                    self.assertEqual((request.source, request.top_k), (source, top_k))
        for value in (0, 21, "5", True, 5.0, None):
            with self.subTest(top_k=value):
                with self.assertRaises(ValidationError):
                    RAGRequest.model_validate(request_body(top_k=value))
        for source in ("", None, "internet"):
            with self.assertRaises(ValidationError):
                RAGRequest.model_validate(request_body(source=source))

    def test_optional_text_is_trimmed_without_inventing_values(self):
        for value in (None, "", "   ", "\t\n"):
            body = request_body()
            body["profile"].update(income=value, employment_status=value)
            request = RAGRequest.model_validate(body)
            self.assertIsNone(request.profile.income)
            self.assertIsNone(request.profile.employment_status)
        body = request_body()
        body["profile"]["income"] = "  월 소득 0원  "
        self.assertEqual(RAGRequest.model_validate(body).profile.income, "월 소득 0원")
        body["profile"]["income"] = 0
        with self.assertRaises(ValidationError):
            RAGRequest.model_validate(body)

    def test_question_origin_is_not_an_external_field(self):
        request = RAGRequest.model_validate(request_body())
        self.assertIs(GraphRequest, RAGRequest)
        self.assertNotIn("question_is_generated", request.model_dump())
        self.assertNotIn("question_is_generated", RAGRequest.model_json_schema()["properties"])
        for field in ("question_is_generated", "_question_is_generated"):
            with self.assertRaises(ValidationError):
                RAGRequest.model_validate(request_body(**{field: False}))

    def test_existing_68_input_cases_with_new_question_rules(self):
        # app 밖의 팀원 평가셋은 수정하지 않습니다. 변경된 네 사례의 기대값만 여기서 명시합니다.
        path = Path(__file__).resolve().parents[2] / "checks/request_validation_cases.json"
        fixtures = json.loads(path.read_text())
        changed = {"INPUT-014", "INPUT-054", "INPUT-055", "INPUT-058"}
        for case in fixtures["cases"]:
            body = copy.deepcopy(fixtures["fixture"])
            for name, value in case.get("set", {}).items():
                parts = name.split(".")
                target = body
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
            for name in case.get("remove", []):
                parts = name.split(".")
                target = body
                for part in parts[:-1]:
                    target = target[part]
                del target[parts[-1]]
            expected = case["expected_status"] == 200 or case["id"] in changed
            with self.subTest(case=case["id"]):
                try:
                    RAGRequest.model_validate(body)
                    accepted = True
                except ValidationError:
                    accepted = False
                self.assertEqual(accepted, expected)

    def test_evidence_conversion_keeps_twenty_unique_nonempty_documents(self):
        docs = [document(index) for index in range(25)]
        docs.insert(0, Document(page_content="   "))
        docs.insert(2, document(0))
        result = to_evidence(docs, "vector_db", "V", limit=20)
        self.assertEqual(len(result), 20)
        self.assertEqual([item.evidence_id for item in result], [f"V{index}" for index in range(1, 21)])


class GraphTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # 이 테스트가 실수로 네트워크를 사용하면 즉시 실패하도록 막습니다.
        self.network_guard = patch("httpx.AsyncClient.send", side_effect=AssertionError("live HTTP forbidden"))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)

    async def test_default_question_searches_profile_and_details(self):
        retriever, reasoner, agent = FakeRetriever([document()]), FakeReasoner(), FakeAgent()
        service = PolicyRagService(retriever, reasoner, agent)
        result = await service.answer_question(RAGRequest.model_validate(request_body()))
        query, source, top_k = retriever.calls[0]
        for value in ("2026", "울산", "25세", "미취업", "취업", "주거", "면접 지원", "월세·주거비"):
            self.assertIn(value, query)
        self.assertNotIn("employment", query)
        self.assertEqual((source, top_k), ("pdf", 5))
        self.assertEqual(result.status, "answered")
        self.assertFalse(agent.calls)
        comparison = next(payload for name, payload in reasoner.calls if name == "compare")
        self.assertEqual(comparison["search_mode"], "profile")
        self.assertEqual(comparison["profile"]["details"], ["면접 지원", "월세·주거비"])

    async def test_explicit_question_controls_retrieval_and_api(self):
        retriever, reasoner, agent = FakeRetriever(), FakeReasoner(keywords=["창업"]), FakeAgent()
        service = PolicyRagService(retriever, reasoner, agent)
        result = await service.answer_question(RAGRequest.model_validate(
            request_body(question="창업 자금 지원을 알려줘")))
        self.assertEqual(retriever.calls[0][0], "창업 자금 지원을 알려줘")
        self.assertEqual(agent.calls[0][0], "창업")
        self.assertEqual(result.status, "answered")
        comparison = next(payload for name, payload in reasoner.calls if name == "compare")
        self.assertEqual(comparison["search_mode"], "question")
        self.assertEqual(comparison["profile"]["age"], 25)
        self.assertEqual(comparison["profile"]["income"], "월 소득 0원")

    async def test_top_k_is_not_silently_capped_at_ten(self):
        for top_k in (1, 5, 10, 20):
            with self.subTest(top_k=top_k):
                retriever = FakeRetriever([document(index) for index in range(20)])
                reasoner = FakeReasoner()
                service = PolicyRagService(retriever, reasoner, FakeAgent())
                await service.answer_question(RAGRequest.model_validate(request_body(top_k=top_k, source="pdf")))
                reviewed = next(payload for name, payload in reasoner.calls if name == "review")
                self.assertEqual(len(reviewed["documents"]), top_k)
                self.assertEqual(retriever.calls[0][1:], ("pdf", top_k))

    async def test_blank_profile_stops_before_search_or_model(self):
        body = request_body()
        body["profile"].update(income=" \n ", employment_status=" \t ")
        retriever, reasoner, agent = FakeRetriever(), FakeReasoner(), FakeAgent()
        result = await PolicyRagService(retriever, reasoner, agent).answer_question(RAGRequest.model_validate(body))
        self.assertEqual(result.status, "needs_profile")
        self.assertEqual(set(result.missing_fields), {"income", "employment_status"})
        self.assertFalse(retriever.calls or reasoner.calls or agent.calls)

    async def test_statuses_do_not_guess_missing_income_or_employment(self):
        body = request_body()
        del body["profile"]["income"]
        del body["profile"]["employment_status"]
        result = await PolicyRagService(FakeRetriever(), FakeReasoner(), FakeAgent()).answer_question(
            RAGRequest.model_validate(body))
        self.assertEqual(result.status, "needs_profile")
        self.assertIn("employment_status", result.missing_fields)

    async def test_unknown_and_none_are_not_search_keywords(self):
        body = request_body()
        body["profile"].update(statuses=["none"], interests=["unknown"], details=[])
        retriever, agent = FakeRetriever(), FakeAgent()
        await PolicyRagService(retriever, FakeReasoner(), agent).answer_question(RAGRequest.model_validate(body))
        self.assertNotIn("none", retriever.calls[0][0])
        self.assertNotIn("unknown", retriever.calls[0][0])
        self.assertEqual(agent.calls[0][0], "청년")

    async def test_all_four_interests_reach_unchanged_graph_agent(self):
        class OfficialAPIStub:
            def __init__(self):
                self.keywords = []

            async def lookup(self, keyword):
                self.keywords.append(keyword)
                return {"policies": [{"plcyNo": keyword, "plcyNm": keyword + " 지원",
                    "refUrl1": "https://example.invalid/policy"}]}

        underlying = OfficialAPIStub()
        adapter = GraphPolicyAgent(agent=underlying)
        body = request_body()
        body["profile"].update(interests=["employment", "housing", "education", "startup"], details=[])
        result = await PolicyRagService(FakeRetriever(), FakeReasoner(), adapter).answer_question(
            RAGRequest.model_validate(body))
        self.assertEqual(underlying.keywords, ["취업", "주거", "교육", "창업"])
        self.assertEqual(result.node_path.count("supplement"), 1)
        self.assertEqual(result.status, "answered")

    async def test_still_insufficient_after_one_supplement_finishes(self):
        agent = FakeAgent()
        result = await PolicyRagService(FakeRetriever(), FakeReasoner(sufficient=False), agent).answer_question(
            RAGRequest.model_validate(request_body()))
        self.assertEqual(result.status, "insufficient")
        self.assertEqual(result.node_path.count("supplement"), 1)
        self.assertEqual(result.node_path[-1], "finish")

    async def test_explicit_question_without_keywords_does_not_use_old_interests(self):
        agent = FakeAgent()
        result = await PolicyRagService(FakeRetriever(), FakeReasoner(keywords=[]), agent).answer_question(
            RAGRequest.model_validate(request_body(question="특정 정책을 알려줘")))
        self.assertFalse(agent.calls)
        self.assertEqual(result.api_status, "no_results")

    async def test_successful_batch_is_preserved_when_later_batch_fails(self):
        body = request_body()
        body["profile"].update(interests=["employment", "housing", "education", "startup"], details=[])
        agent = FakeAgent(fail_on_call=2)
        result = await PolicyRagService(FakeRetriever(), FakeReasoner(), agent).answer_question(
            RAGRequest.model_validate(body))
        self.assertEqual(len(agent.calls), 2)
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.api_status, "used")

    async def test_failed_supplement_statuses_finish_safely(self):
        for status in ("timeout", "not_configured", "no_results", "failed"):
            with self.subTest(status=status):
                result = await PolicyRagService(FakeRetriever(), FakeReasoner(), FakeAgent(status=status)).answer_question(
                    RAGRequest.model_validate(request_body()))
                self.assertEqual(result.status, "insufficient")
                self.assertEqual(result.api_status, status)

    async def test_out_of_scope_never_searches(self):
        retriever, agent = FakeRetriever(), FakeAgent()
        result = await PolicyRagService(retriever, FakeReasoner(in_scope=False), agent).answer_question(
            RAGRequest.model_validate(request_body(question="날씨를 알려줘")))
        self.assertEqual(result.status, "out_of_scope")
        self.assertFalse(retriever.calls or agent.calls)

    async def test_explicit_age_mismatch_overrides_fake_model(self):
        reasoner = FakeReasoner()
        result = await PolicyRagService(FakeRetriever([document(age_max=20)]), reasoner, FakeAgent()).answer_question(
            RAGRequest.model_validate(request_body()))
        self.assertEqual(result.policies[0].status, "not_eligible")
        self.assertFalse(any(name == "generate" for name, _ in reasoner.calls))

    async def test_corpus_and_prompt_contracts_without_calling_llm(self):
        self.assertEqual(len(POLICY_CORPUS["regions"]), 17)
        self.assertEqual(len(POLICY_CORPUS["central_task_categories"]), 5)
        model = LLMReasoner()
        model._ask = AsyncMock(return_value=ScopeDecision(in_scope=True, reason="test"))
        await model.scope("창업 지원")
        _, instruction, payload = model._ask.call_args.args
        self.assertIn("search_keywords", instruction)
        self.assertEqual(payload["policy_corpus"]["year"], 2026)
        self.assertIsNone(model._model)
        await model.review({})
        self.assertIn("시행계획", model._ask.call_args.args[1])
        await model.compare({})
        self.assertIn("시군구", model._ask.call_args.args[1])
        await model.generate({})
        self.assertIn("모집 공고", model._ask.call_args.args[1])


class HTTPTests(unittest.TestCase):
    def test_fastapi_input_boundary_calls_real_graph_service(self):
        # 실제 진입점과 같은 DTO·Service 호출을 검사합니다. main/auth를 import하지 않으므로
        # JWT_SECRET·사용자 .env가 필요 없고 프로젝트의 jwt_log에도 파일을 만들지 않습니다.
        reasoner = FakeReasoner()
        retriever = FakeRetriever([document()])
        service = PolicyRagService(retriever, reasoner, FakeAgent())
        application = FastAPI()

        @application.post("/recommend")
        async def recommend(request: RAGRequest):
            return await service.answer_question(request)

        with TestClient(application) as client:
            response = client.post("/recommend", json=request_body())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["question"], DEFAULT_QUESTION)
            self.assertEqual(retriever.calls[0][1:], ("pdf", 5))
            response = client.post("/recommend", json=request_body(question="창업 지원을 알려줘"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["question"], "창업 지원을 알려줘")
            before = len(reasoner.calls)
            self.assertEqual(client.post("/recommend", json=request_body(top_k="5")).status_code, 422)
            self.assertEqual(len(reasoner.calls), before)


if __name__ == "__main__":
    unittest.main()

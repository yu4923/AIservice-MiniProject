"""Search detail schema and structured LLM boundary, without provider calls."""
import unittest
from unittest.mock import AsyncMock, Mock

from app.graph.nodes import LLMReasoner
from app.graph.state import AnswerResponse, ComparisonResult, PolicyMatch


class SearchContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_extracts_details_through_structured_schema(self):
        expected = ComparisonResult(policies=[PolicyMatch(
            policy_name='청년 월세 지원', status='needs_review', reason='현재 공고 확인 필요',
            missing_fields=[], evidence_ids=['V1'], benefit='월 최대 20만원 지원',
            application_period={'display': '2026. 3. 1. ~ 2026. 3. 31.'})], follow_up_question='')
        runnable = Mock()
        runnable.ainvoke = AsyncMock(return_value=expected)
        reasoner = LLMReasoner()
        reasoner._model = Mock()
        reasoner._model.with_structured_output.return_value = runnable
        payload = {'documents': [{'evidence_id': 'V1', 'content':
            '월 최대 20만원 지원. 신청 기간: 2026. 3. 1. ~ 2026. 3. 31.'}]}
        result = await reasoner.compare(payload)
        reasoner._model.with_structured_output.assert_called_once_with(ComparisonResult, method='json_schema')
        messages = runnable.ainvoke.call_args.args[0]
        for text in ['benefit', 'application_period.display', '지급 기간', 'null', '연도를 보존']:
            self.assertIn(text, messages[0].content)
        response = AnswerResponse(question='월세 정책 검색', prompt='월세 정책 검색',
            answer='검색 결과', response='검색 결과', status='answered', policies=result.policies)
        policy = response.model_dump(mode='json')['policies'][0]
        self.assertEqual(policy['benefit'], '월 최대 20만원 지원')
        self.assertEqual(policy['application_period'], {'display': '2026. 3. 1. ~ 2026. 3. 31.'})

    async def test_unknown_details_remain_null_and_schema_is_nullable(self):
        policy = PolicyMatch(policy_name='정책', status='needs_review', reason='정보 확인 필요',
                             missing_fields=[], evidence_ids=['V1'])
        self.assertIsNone(policy.model_dump()['benefit'])
        self.assertIsNone(policy.model_dump()['application_period'])
        schema = ComparisonResult.model_json_schema()['$defs']['PolicyMatch']['properties']
        for field in ['benefit', 'application_period']:
            self.assertIn({'type': 'null'}, schema[field]['anyOf'])


if __name__ == '__main__':
    unittest.main()

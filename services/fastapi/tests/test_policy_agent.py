import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agents.policy_agent import PolicyAgent
from app.tools import youth_policy_api as api


class PolicyAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_env_file_and_request(self):
        with tempfile.TemporaryDirectory() as folder:
            env_file = Path(folder) / '.env'
            env_file.write_text('YOUTH_POLICY_API_KEY=test-only-secret\n')
            def handler(request):
                self.assertEqual(request.url.params['apiKeyNm'], 'test-only-secret')
                self.assertEqual(request.url.params['plcyNm'], '월세')
                self.assertEqual(request.url.params['zipCd'], '11000')
                return httpx.Response(200, json={'result': {'youthPolicyList': [{'plcyNo': 'p1'}], 'pagging': {'totCount': 1}}})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch.dict(os.environ, {}, clear=True), patch.object(api, 'ENV_FILE', env_file):
                    result = await PolicyAgent(api.YouthPolicyAPI(client=client)).lookup('월세', region_code='11000')
            self.assertEqual(result['policies'][0]['plcyNo'], 'p1')
            self.assertNotIn('test-only-secret', str(result))

    async def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(api, 'load_dotenv'):
            with self.assertRaisesRegex(ValueError, 'YOUTH_POLICY_API_KEY'):
                PolicyAgent()

    async def test_detail_and_empty_result(self):
        def handler(request):
            self.assertEqual(request.url.params['pageType'], '2')
            self.assertEqual(request.url.params['plcyNo'], 'p1')
            return httpx.Response(200, json={'result': {'youthPolicyList': []}})
        with patch.dict(os.environ, {'YOUTH_POLICY_API_KEY': 'test-only-secret'}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await PolicyAgent(api.YouthPolicyAPI(client=client)).get_detail('p1')
                self.assertEqual(result['policies'], [])

    async def test_errors_are_sanitized(self):
        for status, body in [(401, {}), (200, {'resultCode': 'ERROR'})]:
            with patch.dict(os.environ, {'YOUTH_POLICY_API_KEY': 'test-only-secret'}):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
                    with self.assertRaises(api.PolicyAPIError) as caught:
                        await PolicyAgent(api.YouthPolicyAPI(client=client)).lookup('월세')
                    self.assertNotIn('test-only-secret', str(caught.exception))
                    self.assertNotIn('apiKeyNm', str(caught.exception))

    async def test_timeout_and_validation(self):
        def handler(request):
            raise httpx.ReadTimeout('test-only-secret', request=request)
        with patch.dict(os.environ, {'YOUTH_POLICY_API_KEY': 'test-only-secret'}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                agent = PolicyAgent(api.YouthPolicyAPI(client=client))
                with self.assertRaisesRegex(api.PolicyAPIError, '초과'):
                    await agent.lookup('월세')
                with self.assertRaises(ValueError):
                    await agent.lookup('월세', region_code='서울')
                with self.assertRaises(ValueError):
                    await agent.lookup('월세', page_size=0)


if __name__ == '__main__':
    unittest.main()

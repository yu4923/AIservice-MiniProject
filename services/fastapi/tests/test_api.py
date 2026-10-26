import os
import unittest
from unittest.mock import patch

# Avoid reading or printing real credentials during test module import.
with patch.dict(os.environ, {'JWT_SECRET':'ci-fixture-only-not-a-real-key', 'OPENAI_API_KEY':'', 'YOUTH_POLICY_API_KEY':''}):
    from app.main import create_app
    from app.auth import get_current_user

from fastapi import Response
from fastapi.testclient import TestClient
from test_graph import Reasoner, Agent, Retriever, DOC, request
from app.graph.workflow import PolicyRagService


class APITests(unittest.TestCase):
    def test_one_business_route_and_internal_graph(self):
        service = PolicyRagService(Retriever([DOC]), Reasoner(), Agent())
        app = create_app(service, initialize_indexes=False)
        async def authenticated(response: Response):
            response.headers['X-Request-Id'] = 'ci-request'
            return object()
        app.dependency_overrides[get_current_user] = authenticated
        with TestClient(app) as client:
            response = client.post('/search', json=request().model_dump())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'answered')
            self.assertIsNone(response.json()['policies'][0]['benefit'])
            self.assertIsNone(response.json()['policies'][0]['application_period'])
            self.assertEqual(client.post('/recommend', json={}).status_code, 404)
            self.assertEqual(client.post('/rag-query', json={}).status_code, 404)
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(client.get('/health').json()['service'], 'search')
            paths = client.get('/openapi.json').json()['paths']
            self.assertEqual(set(paths), {'/search', '/health'})

    def test_startup_prepares_indexes_once(self):
        service = PolicyRagService(Retriever([DOC]), Reasoner(), Agent())
        with patch('app.main.prepare_indexes') as prepare:
            app = create_app(service)
            with TestClient(app) as client:
                self.assertEqual(client.get('/health').status_code, 200)
            prepare.assert_called_once_with()

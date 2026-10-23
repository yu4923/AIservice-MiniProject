"""Retrieval HTTP regression checks without OpenAI, DB or network requests."""
import importlib
import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

with patch.dict(os.environ, {}, clear=True), patch('dotenv.load_dotenv'):
    main = importlib.import_module('app.main')


class MainTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.document = Document(page_content='청년 지원 대상과 신청방법입니다.', metadata={
            'source': 'housing.pdf', 'page': 3, 'pages': [3, 4], 'title': '청년 주거 지원',
            'document_year': 2026, 'context_year': 2026, 'section_role': 'plan',
            'authority': 'planning_document', 'eligibility_status': 'conflict',
            'quality_flags': ['image_text_not_verified']})
        self.store = Mock()
        self.store.similarity_search_with_score.return_value = [(self.document, .2)]

    def tearDown(self):
        self.client.close()

    def request(self, source='pdf', **changes):
        body = {'prompt': '청년 주거 지원 알려줘', 'source': source, 'top_k': 1}
        body.update(changes)
        return self.client.post('/rag-query', json=body)

    def test_pdf_returns_evidence_with_metadata_and_distance(self):
        with patch.object(main, 'load_vectorstore', return_value=self.store) as loader:
            response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(set(result), {'prompt', 'source', 'documents', 'context', 'index_available'})
        self.assertEqual(result['source'], 'pdf')
        self.assertTrue(result['index_available'])
        self.assertEqual(result['documents'], [{
            'content': self.document.page_content, 'metadata': self.document.metadata, 'distance': .2}])
        self.assertIn(self.document.page_content, result['context'])
        loader.assert_called_once_with('pdf')
        self.store.similarity_search_with_score.assert_called_once_with('청년 주거 지원 알려줘', k=1)

    def test_web_uses_web_index_and_returns_source_metadata(self):
        self.document.metadata = {'source': 'https://www.seoul.go.kr/view?id=1',
                                  'published_at': '2026-03-03', 'collected_at': '2026-10-23',
                                  'application_status': 'unverified'}
        with patch.object(main, 'load_vectorstore', return_value=self.store) as loader:
            response = self.request('web')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['documents'][0]['metadata'], self.document.metadata)
        loader.assert_called_once_with('web')
        self.store.similarity_search_with_score.assert_called_once_with('청년 주거 지원 알려줘', k=1)

    def test_missing_index_returns_retrieval_schema(self):
        with patch.object(main, 'load_vectorstore', return_value=None):
            response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result['index_available'])
        self.assertEqual(result['documents'], [])
        self.assertEqual(result['context'], '')

    def test_invalid_source_is_rejected_before_loading(self):
        with patch.object(main, 'load_vectorstore') as loader:
            response = self.request('invalid')
        self.assertEqual(response.status_code, 422)
        loader.assert_not_called()

    def test_invalid_prompt_and_top_k_are_rejected_before_loading(self):
        with patch.object(main, 'load_vectorstore') as loader:
            for changes in ({'top_k': 0}, {'top_k': 51}, {'prompt': ''}):
                with self.subTest(changes=changes):
                    self.assertEqual(self.request(**changes).status_code, 422)
        loader.assert_not_called()

    def test_index_error_returns_503_without_internal_details(self):
        with patch.object(main, 'load_vectorstore', side_effect=RuntimeError('private internal path')):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private internal path', response.text)

    def test_empty_search_keeps_index_available(self):
        self.store.similarity_search_with_score.return_value = []
        with patch.object(main, 'load_vectorstore', return_value=self.store):
            response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['index_available'])
        self.assertEqual(response.json()['documents'], [])
        self.assertEqual(response.json()['context'], '')

    def test_search_error_returns_500_without_internal_details(self):
        self.store.similarity_search_with_score.side_effect = RuntimeError('private service details')
        with patch.object(main, 'load_vectorstore', return_value=self.store):
            response = self.request()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private service details', response.text)

    def test_duplicate_and_blank_documents_are_filtered(self):
        self.store.similarity_search_with_score.return_value = [
            (self.document, .2), (self.document, .3), (Document(page_content='  '), .4)]
        with patch.object(main, 'load_vectorstore', return_value=self.store):
            response = self.request(top_k=3)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['documents']), 1)
        self.assertEqual(response.json()['documents'][0]['distance'], .2)

    def test_reload_on_next_request_after_ingestion(self):
        updated = Mock()
        updated.similarity_search_with_score.return_value = [(Document(page_content='갱신된 근거'), .1)]
        with patch.object(main, 'load_vectorstore', side_effect=[None, self.store, updated]) as loader:
            first, second, third = self.request(), self.request(), self.request()
        self.assertEqual([r.status_code for r in (first, second, third)], [200, 200, 200])
        self.assertFalse(first.json()['index_available'])
        self.assertEqual(second.json()['documents'][0]['content'], self.document.page_content)
        self.assertEqual(third.json()['documents'][0]['content'], '갱신된 근거')
        self.assertEqual(loader.call_count, 3)


if __name__ == '__main__':
    unittest.main()

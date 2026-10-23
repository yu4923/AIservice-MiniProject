"""HTTP compatibility checks with local mocks: no DB, OpenAI or search requests."""
import importlib
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

# Keep import-time configuration validation, but do not open any external service.
with patch.dict(os.environ, {'OPENAI_API_KEY':'test-not-a-real-key', 'ASYNC_DB_URL':'sqlite+aiosqlite://'}), \
     patch('dotenv.load_dotenv'), \
     patch('sqlalchemy.ext.asyncio.create_async_engine', return_value=Mock()), \
     patch('app.retrieval.faiss_store.load_vectorstore', return_value=None):
    main = importlib.import_module('app.main')


class MainTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.document = Document(page_content='청년 지원 대상과 신청방법입니다.', metadata={
            'source':'housing.pdf','page':3,'pages':[3,4],'title':'청년 주거 지원',
            'document_year':2026,'context_year':2026,'section_role':'plan',
            'authority':'planning_document','eligibility_status':'conflict',
            'quality_flags':['image_text_not_verified']})
        self.store = Mock()
        self.store.similarity_search_with_score.return_value = [(self.document, .2)]
        self.store.similarity_search.return_value = [self.document]
        self.llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='근거에 따른 답변')))
    def tearDown(self):
        self.client.close()
    def request(self, source='pdf', **changes):
        body = {'prompt':'청년 주거 지원 알려줘','source':source,'top_k':1}
        body.update(changes)
        return self.client.post('/rag-query',json=body)
    def test_pdf_fills_todos_and_preserves_response_schema(self):
        with patch.object(main,'load_vectorstore',return_value=self.store) as loader, \
             patch.object(main,'ChatOpenAI',return_value=self.llm):
            response = self.request()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(set(response.json()),{'prompt','response'})
        self.assertEqual(response.json()['response'],'근거에 따른 답변')
        loader.assert_called_once_with('pdf')
        self.store.similarity_search_with_score.assert_called_once_with('청년 주거 지원 알려줘',k=1)
        prompt = self.llm.ainvoke.await_args.args[0][0].content
        self.assertIn('housing.pdf',prompt)
        self.assertIn('PDF 쪽: 3, 4',prompt)
        self.assertIn('적용범위 충돌',prompt)
        self.assertIn('image_text_not_verified',prompt)
        self.assertIn('현재 모집',prompt)
    def test_web_async_reply_and_source_url(self):
        self.document.metadata = {'source':'https://www.seoul.go.kr/view?id=1',
                                  'published_at':'2026-03-03','collected_at':'2026-10-23',
                                  'application_status':'unverified'}
        self.llm.ainvoke.return_value.content = '### ANSWER_START\n웹 답변\n### ANSWER_END'
        with patch.object(main,'load_vectorstore',return_value=self.store), \
             patch.object(main,'ChatOpenAI',return_value=self.llm):
            response = self.request('web')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['response'],'웹 답변')
        self.store.similarity_search.assert_called_once()
        prompt = self.llm.ainvoke.await_args.args[0][0].content
        self.assertIn('https://www.seoul.go.kr/view?id=1',prompt)
        self.assertIn('수집시각: 2026-10-23',prompt)
    def test_missing_index_retains_400(self):
        with patch.object(main,'load_vectorstore',return_value=None), patch.object(main,'ChatOpenAI') as llm:
            response = self.request()
        self.assertEqual(response.status_code,400)
        self.assertIn('ingest_papers.py',response.json()['detail'])
        llm.assert_not_called()
    def test_invalid_source_retains_400(self):
        with patch.object(main,'load_vectorstore') as loader:
            response = self.request('invalid')
        self.assertEqual(response.status_code,400)
        loader.assert_not_called()
    def test_invalid_top_k_is_validated(self):
        self.assertEqual(self.request(top_k=0).status_code,422)
    def test_index_error_returns_503_without_internal_details(self):
        with patch.object(main,'load_vectorstore',side_effect=RuntimeError('private internal path')):
            response = self.request()
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private internal path',response.text)
    def test_empty_search_does_not_invoke_llm(self):
        self.store.similarity_search_with_score.return_value=[]
        with patch.object(main,'load_vectorstore',return_value=self.store), \
             patch.object(main,'ChatOpenAI',return_value=self.llm):
            response = self.request()
        self.assertEqual(response.status_code,200)
        self.llm.ainvoke.assert_not_awaited()
    def test_long_web_chunk_retains_context_with_truncation_notice(self):
        doc = Document(page_content='내용'*5000,metadata={'source':'https://www.seoul.go.kr/view?id=1'})
        context = main.build_context([doc],source='web',limit_chars=4000)
        self.assertTrue(context)
        self.assertLessEqual(len(context),4000)
        self.assertIn('내용 일부 생략',context)
        self.assertIn('https://www.seoul.go.kr/view?id=1',context)
    def test_legacy_metadata_and_response_blocks(self):
        doc = Document(page_content='기존 청크',metadata={'source':'old.pdf','page':7})
        context = main.build_context([doc],source='pdf',limit_chars=1000)
        self.assertIn('PDF 쪽: 7',context)
        self.assertEqual(main.response_text([{'type':'text','text':'블록 응답'}]),'블록 응답')
    def test_reload_on_next_request(self):
        with patch.object(main,'load_vectorstore',side_effect=[None,self.store]) as loader, \
             patch.object(main,'ChatOpenAI',return_value=self.llm):
            first, second = self.request(), self.request()
        self.assertEqual(first.status_code,400)
        self.assertEqual(second.status_code,200)
        self.assertEqual(loader.call_count,2)


if __name__ == '__main__':
    unittest.main()

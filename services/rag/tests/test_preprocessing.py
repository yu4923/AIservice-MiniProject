"""Offline regression checks: no paid embeddings, search or LLM API calls."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.policy_preprocessing import (Settings, TASK, build_records, normalize,
                                           source_context, _section, _facts, table_text, money_mentions)
from app.utils.web_preprocessing import official_url, canonical_url, parse_html, web_chunks, _fetch
from app.retrieval import faiss_store
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


def page(number, lines):
    return {"page": number, "printed_page": str(number - 1), "raw_text": "\n".join(lines),
            "width": 600, "height": 840, "quality_flags": [],
            "blocks": [{"text": line, "kind": "text", "bbox": [40, 50 + i*20, 550, 65 + i*20]}
                       for i, line in enumerate(lines)]}


class PolicyTests(unittest.TestCase):
    def test_korean_nfc_and_task_number_survive(self):
        self.assertEqual(normalize("청년\u200b  Ⅲ-1-1-(1)"), "청년 Ⅲ-1-1-(1)")
        self.assertTrue(TASK.match("1-1-서울-3 서울영커리언스 인턴십"))
        self.assertTrue(TASK.match("Ⅲ-1-1-(1) 청년층 대상 공공분양"))

    def test_age_conflict_and_page_evidence(self):
        pages = [page(2, ["Ⅲ-1-1-(1) 청년층 대상 공공분양", "정책대상 연령무관"]),
                 page(3, ["1. 사업 개요", "ㅇ (사업 대상) 청년", "- (연령 기준) 19~39세(청년특공 기준)",
                          "* 공급유형별 상세 소득기준은 상이함"])]
        context = source_context("3. (주거) 2026 과제카드.pdf")
        policies, chunks, reviews = build_records(pages, "cards.pdf", "id", context)
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0]["eligibility_status"], "conflict")
        self.assertEqual(reviews[0]["reason"], "age_scope_conflict")
        self.assertEqual({f['page'] for f in policies[0]['eligibility_candidates']}, {2, 3})
        self.assertIn("청년특공 기준", str(policies[0]['eligibility_candidates']))
        self.assertTrue(all('evidence' in c['metadata'] for c in chunks))

    def test_years_and_budget_do_not_become_eligibility(self):
        section = _section("2. ’25년도 추진실적", {"role": "plan", "year": 2026, "name": ""}, 2026)
        self.assertEqual((section['role'], section['year']), ('past_performance', 2025))
        b = {"text": "19~39세 미취업자", "kind": "text", "page": 1, "bbox": [0,0,10,10],
             "section": "예산", "section_role": "budget", "context_year": 2026}
        self.assertEqual(_facts([b]), [])
        history = _section("ㅇ (추진 경과)", section, 2026)
        self.assertEqual(history['role'], 'historical_context')
        self.assertEqual(_section("ㅇ (사업 대상) 청년", history, 2026)['role'], 'plan')

    def test_policy_boundaries_are_not_merged(self):
        a = page(2, ["Ⅰ-1-1-(1) 첫 정책", "대학생 지원 내용 " * 20])
        b = page(3, ["Ⅰ-1-1-(2) 둘째 정책", "미취업자 지원 내용 " * 20])
        policies, chunks, _ = build_records([a,b], "2026 과제카드.pdf", "id", source_context("2026 과제카드.pdf"))
        self.assertEqual(len(policies), 2)
        for c in chunks:
            self.assertEqual(len(c['metadata']['pages']), 1)

    def test_region_is_publisher_only_and_unknown_age_not_unrestricted(self):
        ctx = source_context("01. (서울) 2026년 청년정책.pdf")
        policies, _, _ = build_records([page(1, ["1-1-서울-3 청년 사업", "학생을 위한 지원 내용 "*20])], "x", "id", ctx)
        self.assertEqual(ctx['publisher_region'], '서울특별시')
        self.assertEqual(policies[0]['eligibility_status'], 'unverified')
        self.assertNotIn('residence_region', policies[0])
        self.assertEqual(policies[0]['eligibility_candidates'], [])

    def test_table_units_and_empty_cells_survive(self):
        rows = [['연도', '예산(백만원)', None], ['2026', '427,000', '※ 지원액 아님']]
        text = table_text(rows)
        self.assertIn('예산(백만원)', text)
        self.assertIn('427,000', text)
        self.assertIn('※ 지원액 아님', text)

    def test_money_units_preserved_without_benefit_inference(self):
        values = money_mentions('사업비 427,000백만원, 월 500천원, 최대 1억2,000만원')
        self.assertEqual([v['value_krw'] for v in values], [427000000000,500000,120000000])
        self.assertTrue(all(v['benefit_status']=='unverified' for v in values))

    def test_income_basis_and_footnote_stay_with_age_candidate(self):
        context = source_context('2026 과제카드.pdf')
        _, _, _ = build_records([], 'a', 'b', context)
        blocks = [dict(page=3,bbox=[0,0,100,10],section='대상',section_role='plan',context_year=2026,
                       kind='text',text='만 19~39세(청년특공 기준), 도시근로자 월평균소득 140% 이하'),
                  dict(page=3,bbox=[0,10,100,20],section='대상',section_role='plan',context_year=2026,
                       kind='text',text='* 공급유형별 상세 소득기준은 상이함')]
        facts = _facts(blocks)
        age = next(f for f in facts if f['field']=='age')
        self.assertEqual(age['scope'], ['청년특공 기준'])
        self.assertEqual(len(age['qualifiers']),1)
        income = next(f for f in facts if f['field']=='income')
        self.assertIn('월평균소득',income['basis'])
        self.assertEqual(income['percent'],140)

    def test_partial_ingestion_blocked_before_embedding(self):
        from app.utils.ingestion import ingest_paper
        from app.utils.policy_preprocessing import Result
        result = Result({'document_id':'a','run_id':'b','partial':True})
        with tempfile.TemporaryDirectory() as d, patch('app.utils.ingestion.preprocess_pdf', return_value=result):
            with self.assertRaisesRegex(ValueError, '일부 페이지'):
                ingest_paper('test.pdf', output_dir=d)

    def test_invalid_settings(self):
        with self.assertRaises(ValueError):
            Settings(max_pages=0)


class WebTests(unittest.TestCase):
    def test_official_boundary_and_redirect_targets(self):
        self.assertTrue(official_url('https://www.seoul.go.kr/a'))
        for url in ['https://seoul.go.kr.attacker.test/', 'https://localhost/',
                    'http://www.seoul.go.kr/', 'https://user:secret@www.seoul.go.kr/',
                    'https://www.seoul.go.kr:8080/']:
            self.assertFalse(official_url(url), url)

    def test_query_identifiers_are_preserved(self):
        self.assertNotEqual(canonical_url('https://a.go.kr/view?id=1'), canonical_url('https://a.go.kr/view?id=2'))

    def test_html_body_not_search_snippet(self):
        html = '''<html><title>공식 공고</title><body><nav>메뉴</nav><main>
        <h1>청년 지원 공고</h1><p>만 19~34세 청년 대상</p><script>evil()</script>
        <table><tr><th>연도</th><th>지원</th></tr><tr><td>2026</td><td>50만원</td></tr></table>
        <a href="/download?id=1">공고.pdf</a></main></body></html>'''
        record = parse_html(html, 'https://www.seoul.go.kr/view?id=2')
        self.assertIn('만 19~34세', record['text'])
        self.assertNotIn('evil()', record['text'])
        self.assertNotIn('메뉴', record['text'])
        self.assertEqual(record['tables'][0][1], ['2026', '50만원'])
        self.assertEqual(record['attachments'][0]['status'], 'not_fetched')
        docs = web_chunks(record, 'https://www.seoul.go.kr/view?id=2', '청년', '2026-10-23')
        self.assertIn('출처:', docs[0]['page_content'])
        self.assertEqual(docs[0]['metadata']['application_status'], 'unverified')

    def test_web_table_not_split_by_character_limit(self):
        table = '연도 | 단위\n' + '2026 | 50만원\n'*100
        record = {'title':'공고','text':table,'published_at':None,
                  'blocks':[{'kind':'table','text':table}]}
        chunks = web_chunks(record,'https://a.go.kr/','test','today',max_chars=50)
        self.assertEqual(len(chunks),1)
        self.assertIn(table,chunks[0]['page_content'])

    def test_unapproved_redirect_never_fetched(self):
        class Response:
            status = 302
            headers = {'Location': 'https://attacker.test/'}
            async def __aenter__(self): return self
            async def __aexit__(self,*a): return False
        class Session:
            calls = 0
            def get(self,*a,**kw): self.calls += 1; return Response()
        session = Session()
        with self.assertRaises(ValueError):
            asyncio.run(_fetch(session, 'https://seoul.go.kr/', None))
        self.assertEqual(session.calls, 1)


class OfflineEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]
    def embed_query(self, text):
        return [float(sum(text.encode()) % 97), float(len(text) % 17), 1.0]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = faiss_store.FAISS_DIR
        faiss_store.FAISS_DIR = Path(self.tmp.name)
        faiss_store._CACHE.clear()
        self.embeddings = OfflineEmbeddings()
    def tearDown(self):
        faiss_store.FAISS_DIR = self.old_root
        faiss_store._CACHE.clear()
        self.tmp.cleanup()
    def docs(self, key, text):
        return [Document(page_content=text, metadata={'source_key':key, 'source':key+'.pdf', 'page':1})]
    def replace(self, key, text, embeddings=None):
        return faiss_store.replace_documents(self.docs(key,text), 'pdf', sources={key},
                                              embeddings=embeddings or self.embeddings)
    def test_replace_preserves_other_sources_and_is_idempotent(self):
        self.replace('a','old evidence')
        self.replace('b','other source')
        store, added = self.replace('a','new evidence')
        self.assertEqual(added,1)
        contents = [store.docstore.search(i).page_content for i in store.index_to_docstore_id.values()]
        self.assertEqual(set(contents), {'new evidence','other source'})
        pointer = (Path(self.tmp.name)/'pdf/current.json').read_text()
        self.assertEqual(self.replace('a','new evidence')[1], 0)
        self.assertEqual(pointer, (Path(self.tmp.name)/'pdf/current.json').read_text())
    def test_failed_embedding_keeps_published_generation(self):
        self.replace('a','old evidence')
        pointer = (Path(self.tmp.name)/'pdf/current.json').read_text()
        class Broken(OfflineEmbeddings):
            def embed_documents(self, texts): raise RuntimeError('embedding failed')
        with self.assertRaises(RuntimeError): self.replace('a','new evidence',Broken())
        self.assertEqual(pointer, (Path(self.tmp.name)/'pdf/current.json').read_text())
        store = faiss_store.load_vectorstore('pdf',embeddings=self.embeddings)
        self.assertEqual(store.index.ntotal,1)
        self.assertEqual(store.docstore.search(next(iter(store.index_to_docstore_id.values()))).page_content,'old evidence')
    def test_empty_collection_never_deletes_source(self):
        self.replace('a','old evidence')
        with self.assertRaises(ValueError):
            faiss_store.replace_documents([], 'pdf',sources={'a'},embeddings=self.embeddings)
        self.assertEqual(faiss_store.load_vectorstore('pdf',embeddings=self.embeddings).index.ntotal,1)

    def test_model_change_refused_before_embedding(self):
        self.replace('a','old evidence')
        with patch.dict(os.environ, {'RAG_EMBEDDING_MODEL':'different-model'}), patch.object(faiss_store,'_embeddings') as call:
            with self.assertRaisesRegex(ValueError,'Embedding model changed'):
                faiss_store.replace_documents(self.docs('a','new'), 'pdf', sources={'a'})
            call.assert_not_called()

    def test_cached_server_reader_sees_next_generation(self):
        self.replace('a','old evidence')
        with patch.object(faiss_store,'_embeddings',return_value=self.embeddings):
            old = faiss_store.load_vectorstore('pdf')
            self.replace('a','updated evidence')
            new = faiss_store.load_vectorstore('pdf')
        def contents(store):
            return [store.docstore.search(i).page_content for i in store.index_to_docstore_id.values()]
        self.assertEqual(contents(old), ['old evidence'])
        self.assertEqual(contents(new), ['updated evidence'])


if __name__ == '__main__':
    unittest.main()

"""Offline regression checks: no paid embeddings, search or LLM API calls."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.utils.policy_preprocessing import (
    Settings, TASK, build_records, normalize,
    source_context, _heading, _section, _facts,
    table_text, money_mentions,
    _partition_pages, _supplement_records, _condition_conflicts,
    _link_summary_evidence,
)
from rag.utils.web_preprocessing import (
    official_url, canonical_url, parse_html, web_chunks, _fetch,
)
from rag.retrieval import faiss_store
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


def page(number, lines):
    return {"page": number, "printed_page": str(number - 1), "raw_text": "\n".join(lines),
            "width": 600, "height": 840, "quality_flags": [],
            "blocks": [{"text": line, "kind": "text", "bbox": [40, 50 + i*20, 550, 65 + i*20]}
                       for i, line in enumerate(lines)]}


class PolicyTests(unittest.TestCase):
    def facts(self, text, **changes):
        block = dict(kind='text', text=text, page=1, bbox=[0, 0, 100, 20],
                     section='사업 대상', section_role='plan', context_year=2026,
                     quality_flags=[])
        block.update(changes)
        return _facts([block])

    def test_age_range_keeps_both_bounds_without_duplicate_single_bound(self):
        for text in ('19세 이상~34세 이하', '19~34세 이하', '만 19세 이상 ~ 만 34세 이하'):
            with self.subTest(text=text):
                ages = [f for f in self.facts(text) if f['field'] == 'age']
                self.assertEqual(len(ages), 1)
                self.assertEqual((ages[0]['min'], ages[0]['max']), (19, 34))
                self.assertTrue(ages[0]['lower_inclusive'])
                self.assertTrue(ages[0]['upper_inclusive'])
        age = next(f for f in self.facts('19세 초과~34세 미만') if f['field'] == 'age')
        self.assertFalse(age['lower_inclusive'])
        self.assertFalse(age['upper_inclusive'])

    def test_explicit_subject_and_military_exception_survive(self):
        facts = self.facts('일반청년 19~34세 이하, 단, 군필자는 39세 이하')
        ages = [f for f in facts if f['field'] == 'age']
        self.assertEqual(len(ages), 2)
        self.assertEqual([f['subject'] for f in ages], ['일반청년', '군필자'])
        self.assertTrue(ages[0]['exceptions'])
        self.assertEqual(ages[1]['max'], 39)
        self.assertEqual(_condition_conflicts(facts), [])

    def test_table_cohorts_keep_age_and_income_on_the_same_row(self):
        rows = [['지원대상', '연령기준', '소득기준'],
                ['차상위이하', '만 15세 ~ 만 39세', '중위소득 50% 이하'],
                ['차상위초과', '만 19세 ~ 만 34세', '중위소득\n50% 초과 ~ 100% 이하']]
        facts = self.facts(table_text(rows), kind='table', rows=rows)
        ages = [f for f in facts if f['field'] == 'age']
        self.assertEqual([(f['subject'], f['min'], f['max']) for f in ages],
                         [('차상위이하', 15, 39), ('차상위초과', 19, 34)])
        income = next(f for f in facts if f['field'] == 'income' and f['subject'] == '차상위초과')
        self.assertEqual((income['percent_min'], income['percent_max']), (50, 100))
        self.assertFalse(income['lower_inclusive'])
        self.assertEqual(income['condition_group'], ages[1]['condition_group'])
        self.assertEqual(_condition_conflicts(facts), [])

    def test_ocr_age_and_income_require_evidence_review(self):
        facts = self.facts('19세 이상~34세 이하, 중위소득 100% 이하',
                           quality_flags=['ocr_requires_review'], extraction_method='native+ocr')
        numeric = [f for f in facts if f['field'] in {'age', 'income'}]
        self.assertEqual(len(numeric), 2)
        self.assertTrue(all(f['verification_status'] == 'requires_review' for f in numeric))
        self.assertTrue(all(f['extraction_method'] == 'native+ocr' for f in numeric))

    def test_future_plan_conditions_are_not_current_eligibility(self):
        section = _section('□ 연도별 추진계획 (‘27년 이후)', {'role':'plan','year':2026,'name':''}, 2026)
        self.assertEqual((section['role'], section['year']), ('future_plan', 2027))
        self.assertEqual(self.facts('19~39세 청년 지원', section_role=section['role'], context_year=section['year']), [])

    def test_priority_selection_and_following_exceptions_remain_in_evidence(self):
        blocks = [dict(kind='text',text=text,page=55,bbox=[0,i*20,100,i*20+15],section='대상',
                       section_role='plan',context_year=2026,quality_flags=[])
                  for i,text in enumerate(['- (연령 기준) 19~39세', '- (기타 조건) 우선선발 및 차순위선발',
                                           '▶ 우선선발: 장애인, 다자녀 가구', 'ㅇ (사업 내용) 행정지원'])]
        facts = _facts(blocks)
        age = next(f for f in facts if f['field']=='age')
        self.assertTrue(any('다자녀' in q['text'] for q in age['qualifiers']))
        self.assertTrue(any(f['field']=='selection_text' and '장애인' in f['evidence'] for f in facts))

    def test_trailing_labels_and_regional_number_formats_start_policies(self):
        cases = [('청년내일저축계좌 지원사업 공통', '공통', '청년내일저축계좌 지원사업'),
                 ('공동캠퍼스 조성 공통', '공통', '공동캠퍼스 조성'),
                 ('기타 공동캠퍼스 조성 공통', '기타', '공동캠퍼스 조성'),
                 ('1-4 전북 청년 직무인턴 운영 자체', '1-4', '전북 청년 직무인턴 운영'),
                 ('1-3-제주-1-① 제주시 대학생 아르바이트 자체', '1-3-제주-1-①', '제주시 대학생 아르바이트'),
                 ('1-3-제주-1-② 서귀포시 대학생 아르바이트 자체', '1-3-제주-1-②', '서귀포시 대학생 아르바이트')]
        for text, task, title in cases:
            with self.subTest(text=text):
                self.assertEqual(_heading(page(1, [text, '1. 사업 개요'])), (task, title))
        self.assertIsNone(_heading(page(1, ['1-4 예산 항목', '일반 목록'])))

    def test_summary_annex_does_not_inherit_last_policy(self):
        pages = [page(1, ['1-1-울산-1 마지막 정책 자체', '1. 사업 개요', '청년 지원 내용 '*20]),
                 page(2, ['Ⅲ. 기초 지방자치단체 자체사업 총괄', '다른 사업 50~70세 대상 '*10]),
                 page(3, ['기초 지자체명 분야 사업명 주요내용', '다른 사업 표 내용 '*20])]
        policies, chunks, _ = build_records(pages, 'ulsan.pdf', 'id', source_context('(울산) 2026.pdf'))
        self.assertEqual(policies[0]['page_end'], 1)
        self.assertEqual(policies[0]['pages'], [1])
        self.assertNotIn('다른 사업', policies[0]['raw_text'])
        self.assertTrue(all(c['metadata']['pages'] == [1] for c in chunks))
        supplements = _supplement_records(_partition_pages(pages), 'ulsan.pdf', source_context('(울산) 2026.pdf'))
        self.assertEqual([s['page'] for s in supplements], [2, 3])
        self.assertTrue(all(s['policy_link_status'] == 'unverified' for s in supplements))

    def test_centred_appendix_divider_and_later_policy_are_separate(self):
        divider = page(2, ['붙 임'])
        divider['blocks'][0]['bbox'] = [100, 400, 500, 440]
        pages = [page(1, ['1-1-울산-1 첫 정책', '1. 사업 개요']), divider,
                 page(3, ['1-1-울산-2 둘째 정책', '1. 사업 개요'])]
        tagged = _partition_pages(pages)
        self.assertEqual([p['document_role'] for p in tagged], ['policy', 'appendix', 'policy'])

    def test_contents_and_policy_specific_attachment_are_not_global_annexes(self):
        contents = page(1, ['목 차', 'Ⅲ. 기초지방자치단체 자체사업 총괄 403'])
        reference = page(2, ['붙임 단위과제 주요 내용', '이 사업의 과제 내용 '*20])
        before = page(3, ['참고 5대 분야 주요사업 추진 실적', '2025년 평가 내용 '*20])
        self.assertEqual([p['document_role'] for p in _partition_pages([contents, reference, before])],
                         ['policy', 'policy', 'policy'])

    def test_same_subject_summary_body_disagreement_keeps_both(self):
        pages = [page(1, ['1-1-울산-1 청년 사업 자체', '1. 사업 개요', '19~34세 지원 내용 '*10])]
        context = source_context('(울산) 2026.pdf')
        policies, chunks, reviews = build_records(pages, 'ulsan.pdf', 'id', context)
        supplements = [{**context, 'entries': [{'policy_name': '청년 사업', 'issuer_raw': '울산광역시',
                        'conditions_raw': '19~39세', 'page': 2, 'bbox': [0,0,100,50],
                        'quality_flags': [], 'link_status': 'requires_review'}]}]
        _link_summary_evidence(supplements, policies, chunks, reviews)
        self.assertEqual(reviews[-1]['reason'], 'summary_body_condition_difference')
        self.assertEqual(policies[0]['eligibility_status'], 'requires_review')
        self.assertTrue(all(c['metadata']['eligibility_status'] == 'requires_review' for c in chunks))
        self.assertEqual(next(f for f in policies[0]['eligibility_candidates'] if f['field']=='age')['max'], 34)
        self.assertEqual(next(f for f in supplements[0]['entries'][0]['condition_candidates'] if f['field']=='age')['max'], 39)
        self.assertEqual(supplements[0]['entries'][0]['link_status'], 'requires_review')

    def test_same_policy_name_in_other_municipality_is_not_linked(self):
        context = source_context('(울산) 2026.pdf')
        policies, chunks, reviews = build_records([page(1, ['1-1-울산-1 청년 사업 자체', '1. 사업 개요',
                                                           '19~34세 지원 '*20])], 'ulsan.pdf', 'id', context)
        supplements = [{**context, 'entries': [{'policy_name': '청년 사업', 'issuer_raw': '울산광역시 남구',
                        'conditions_raw': '19~39세', 'page': 2, 'bbox': [0,0,100,50],
                        'quality_flags': [], 'link_status': 'requires_review'}]}]
        _link_summary_evidence(supplements, policies, chunks, reviews)
        self.assertEqual(policies[0]['review_flags'], [])
        self.assertEqual(supplements[0]['entries'][0]['name_candidates'], [policies[0]['policy_id']])
        self.assertEqual(supplements[0]['entries'][0]['link_status'], 'requires_review')

    def test_summary_rows_preserve_issuer_years_and_unverified_link(self):
        pg = page(2, ['Ⅲ. 자체사업 총괄'])
        rows = [['기초 지자체명', '분야', '사업명', '주요내용', '’25예산', '’26예산'],
                ['울산광역시 남구', '주거', '청년 주거 지원', '19세 이상~34세 이하', '10', '20']]
        pg['blocks'].append(dict(kind='table', rows=rows, text=table_text(rows), bbox=[30, 100, 550, 700]))
        entry = _supplement_records(_partition_pages([pg]), 'ulsan.pdf', source_context('(울산) 2026.pdf'))[0]['entries'][0]
        self.assertEqual(entry['issuer_raw'], '울산광역시 남구')
        self.assertEqual(entry['year_values_raw'], {'2025': '10', '2026': '20'})
        self.assertEqual(entry['link_status'], 'requires_review')
        self.assertEqual(entry['residence_status'], 'unverified')
        rows[0][-1] = '2‘6예산'
        uncertain = _supplement_records(_partition_pages([pg]), 'ulsan.pdf', source_context('(울산) 2026.pdf'))[0]['entries'][0]
        self.assertEqual(uncertain['year_mapping_status'], 'requires_review')
        self.assertNotIn('2026', uncertain['year_values_raw'])
        self.assertIn('2‘6예산', uncertain['year_headers_raw'])

    def test_ocr_money_and_plan_year_mismatch_reach_chunks(self):
        pg = page(1, ['1-1-울산-1 청년 사업 자체', '1. 사업 개요', '3. ’25년도 추진계획', '사업비 100만원 '*10])
        pg['quality_flags'] = ['ocr_requires_review']
        pg['extraction_method'] = 'native+ocr'
        policies, chunks, reviews = build_records([pg], 'ulsan.pdf', 'id', source_context('(울산) 2026.pdf'))
        reasons = {r['reason'] for r in reviews}
        self.assertTrue({'numeric_evidence_requires_review', 'plan_year_mismatch'} <= reasons)
        self.assertEqual(policies[0]['money_mentions'][0]['verification_status'], 'requires_review')
        self.assertEqual(policies[0]['money_mentions'][0]['context_year'], 2025)
        self.assertTrue(all(c['metadata']['eligibility_status'] == 'requires_review' for c in chunks))

    def test_unparsed_age_condition_is_visible_for_review(self):
        pg = page(1, ['1-1-울산-1 청년 사업 자체', '1. 사업 개요', '- (연령 기준) 19 이상 34 이하', '지원 내용 '*20])
        policies, chunks, reviews = build_records([pg], 'ulsan.pdf', 'id', source_context('(울산) 2026.pdf'))
        self.assertIn('unparsed_age_condition', policies[0]['review_flags'])
        self.assertTrue(any(r['reason'] == 'unparsed_age_condition' for r in reviews))
        self.assertTrue(all(c['metadata']['verification_status'] == 'requires_review' for c in chunks))

    def test_rag_evidence_keeps_policy_name_conditions_and_source(self):
        from app.retrieval.policy_search import RAGRequest, search_policies
        from unittest.mock import Mock
        pg = page(180, ['청년내일저축계좌 지원사업 공통', '1. 사업 개요', '일반청년 만19세 이상~만34세 이하', '지원 내용 '*20])
        _, chunks, _ = build_records([pg], 'ulsan.pdf', 'id', source_context('(울산) 2026.pdf'))
        chunk = next(c for c in chunks if c['metadata']['eligibility_candidates'])
        store = Mock()
        store.similarity_search_with_score.return_value = [(Document(page_content=chunk['page_content'], metadata=chunk['metadata']), .1)]
        response = search_policies(RAGRequest(prompt='청년내일저축계좌', source='pdf'), store)
        metadata = response.documents[0].metadata
        self.assertEqual(metadata['title'], '청년내일저축계좌 지원사업')
        self.assertEqual(metadata['source'], 'ulsan.pdf')
        self.assertEqual(metadata['pages'], [180])
        self.assertEqual(metadata['publisher_region'], '울산광역시')
        age = next(f for f in metadata['eligibility_candidates'] if f['field'] == 'age')
        self.assertEqual((age['min'], age['max']), (19, 34))

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

    def test_dates_and_onestop_word_are_not_money(self):
        for text in ('23.08.07.원', '- ‘23.08.07. 원스톱전세피해지원센터 이전 개소',
                     '2026.01.01.원', '100 원스톱 서비스', '10,00만원', '5..2원'):
            with self.subTest(text=text):
                self.assertEqual(money_mentions(text), [])
        values = money_mentions('23.08.07.원 이후 사업비 145백만원 (시비 100%)')
        self.assertEqual([v['value_krw'] for v in values], [145000000])

    def test_money_decimals_particles_and_compound_units(self):
        values = money_mentions('1.5억원, 30만원은 지원, 500천원씩 지급, 1억2,000만원까지 지원')
        self.assertEqual([v['value_krw'] for v in values], [150000000, 300000, 500000, 120000000])
        self.assertEqual(money_mentions('최대100만원')[0]['value_krw'], 1000000)

    def test_incheon_pua_task_with_title_before_and_after_number(self):
        pg = page(37, ['구직활동 청년 지원을 위한', '1-\uf000-인천-1 자체',
                       '‘드림체크카드’', '1. 사업 개요', '청년 지원 내용 '*20])
        self.assertEqual(_heading(pg), ('1-\uf000-인천-1', '구직활동 청년 지원을 위한 ‘드림체크카드’'))
        context = source_context('04. (인천) 2026년 청년정책.pdf')
        policies, chunks, reviews = build_records([pg], 'incheon.pdf', 'id', context)
        self.assertTrue(chunks)
        self.assertEqual(policies[0]['task_id'], '1-\uf000-인천-1')
        self.assertEqual(reviews[0]['reason'], 'task_number_unverified')

    def test_chungnam_local_number_title_and_bracketed_reference(self):
        pg = page(17, ['Ⅰ. 일자리 분야 (41개)', '1-1-1', '청년인턴 사업 자체',
                       '[1-3-충남-15]', '1. 사업 개요', '청년 인턴 지원 내용 '*20])
        self.assertEqual(_heading(pg), ('1-1-1', '청년인턴 사업'))
        context = source_context('12. (충남) 2026년 청년정책.pdf')
        policies, chunks, _ = build_records([pg], 'chungnam.pdf', 'id', context)
        self.assertEqual(len(policies), 1)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]['metadata']['publisher_region'], '충청남도')

    def test_multiline_title_and_numeric_reference_are_kept_separate(self):
        pg = page(34, ['1-1-8 충청남도 친화형 PILOT 프로그램', '자체',
                       '[1-3-충남-15] (프로젝트 인턴십)', '1. 사업 개요'])
        self.assertEqual(_heading(pg), ('1-1-8', '충청남도 친화형 PILOT 프로그램 (프로젝트 인턴십)'))
        pg = page(21, ['1-1-3', '지방공기업 체험형 청년인턴 제도 운영 공통',
                       '[1-3-15]', '1. 사업 개요'])
        self.assertEqual(_heading(pg), ('1-1-3', '지방공기업 체험형 청년인턴 제도 운영'))

    def test_common_and_pua_only_headers_require_business_overview(self):
        for prefix in ('공통', '\uf000'):
            with self.subTest(prefix=prefix):
                pg = page(40, [prefix+' 청년도전지원사업 공통', '1. 사업 개요'])
                self.assertEqual(_heading(pg), (prefix, '청년도전지원사업'))
                self.assertIsNone(_heading(page(1, [prefix+' 청년도전지원사업 공통', '2026 예산 목록'])))

    def test_repeated_regional_ids_and_common_policies_do_not_merge(self):
        pages = [page(27, ['1-\uf000-인천-1 첫 정책 자체', '1. 사업 개요', '첫 정책 지원 '*20]),
                 page(31, ['1-\uf000-인천-1 둘째 정책 자체', '1. 사업 개요', '둘째 정책 지원 '*20]),
                 page(40, ['공통 셋째 정책 공통', '1. 사업 개요', '셋째 정책 지원 '*20]),
                 page(44, ['공통 넷째 정책 공통', '1. 사업 개요', '넷째 정책 지원 '*20])]
        policies, chunks, _ = build_records(pages, 'incheon.pdf', 'id', source_context('(인천) 2026.pdf'))
        self.assertEqual(len(policies), 4)
        self.assertEqual(len({p['policy_id'] for p in policies}), 4)
        self.assertEqual({p['policy_name'] for p in policies}, {'첫 정책', '둘째 정책', '셋째 정책', '넷째 정책'})
        for chunk in chunks:
            self.assertEqual(len(chunk['metadata']['pages']), 1)

    def test_heading_survives_table_extraction_using_original_lines(self):
        original = page(17, ['1-1-1', '청년인턴 사업 자체', '[1-3-충남-15]', '1. 사업 개요'])
        pg = {**original, 'heading_blocks': original['blocks'],
              'blocks': [{'kind': 'table', 'text': '청년인턴 사업 | 자체',
                          'bbox': [40, 50, 550, 100]}, original['blocks'][-1]]}
        self.assertEqual(_heading(pg), ('1-1-1', '청년인턴 사업'))

    def test_summary_table_rows_do_not_start_policies(self):
        original = page(16, ['1-\uf000-인천-1 인공지능융합 인재양성 100 200'])
        pg = {**original, 'heading_blocks': original['blocks'],
              'blocks': [{'kind': 'table', 'text': '과제번호 | 과제명 | 예산',
                          'bbox': [40, 50, 550, 700]}]}
        self.assertIsNone(_heading(pg))

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
        from rag.utils.ingestion import ingest_paper
        from rag.utils.policy_preprocessing import Result
        result = Result({'document_id':'a','run_id':'b','partial':True})
        with tempfile.TemporaryDirectory() as d, patch('rag.utils.ingestion.preprocess_pdf', return_value=result):
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

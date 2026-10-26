from app.graph.state import PolicyMatch
from app.graph.workflow import suggested_questions


def policy(name, **updates):
    fields = dict(policy_name=name, status="needs_review", reason="확인된 연령 조건 부합",
                  missing_fields=[], evidence_ids=["V1"])
    fields.update(updates)
    return PolicyMatch(**fields)


def test_suggestions_use_known_benefits_and_comparison_without_unknown_procedures():
    policies = [policy("인턴", benefit="직무교육·인턴십"),
                policy("수당", benefit="구직활동비", checks=["소득 확인 필요"])]
    questions = suggested_questions(policies, "처음 추천", "answered")
    assert len(questions) == 3
    assert "지원 내용을 비교" in questions[0]
    assert "우선순위" in questions[1]
    assert any("먼저 확인할 항목" in q for q in questions)
    assert not any("서류" in q or "신청 절차" in q or "신청 기간" in q for q in questions)


def test_no_questions_for_failure_or_unsubstantiated_policy():
    assert suggested_questions([policy("수당")], "질문", "insufficient") == []
    assert suggested_questions([policy("수당", evidence_ids=[])], "질문", "answered") == []
    assert suggested_questions([policy("수당", status="not_eligible")], "질문", "answered") == []


def test_single_policy_deepens_known_benefit_and_avoids_identical_question():
    policies = [policy("인턴", benefit="직무교육")]
    questions = suggested_questions(policies, "처음 추천", "answered")
    assert len(questions) == 1
    assert "구체적으로 설명" in questions[0]
    assert suggested_questions(policies, questions[0], "answered") == []

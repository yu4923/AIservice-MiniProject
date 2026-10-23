"""백업의 요청·응답 DTO와 Graph 공유 상태를 현재 프로젝트 구조로 복원했습니다."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

# 기존 Graph의 import 경로를 유지하면서 외부 입력 검사는 별도 모듈에 둔다.
from app.input_validation import RAGRequest, UserProfile


POLICY_SCOPES = (
    "중앙정부 청년 지원사업", "지자체 청년 지원정책", "청년정책 신청 자격 지원 내용",
    "청년 지원사업 모집 공고", "청년정책 종합 안내",
)


# [LLM의 판단 결과 DTO]
# 자유로운 문장 대신 정해진 항목으로 결과를 받아 Graph가 분기할 수 있게 합니다.
# sufficient는 '신청 자격이 된다'가 아니라 '조건을 비교할 문서 정보가 있다'는 뜻입니다.
class ScopeDecision(BaseModel):
    in_scope: bool
    reason: str


class EvidenceDecision(BaseModel):
    sufficient: bool
    # Policy facts can be answerable even when current recruitment is unverified.
    application_status_verified: bool = False
    usable_ids: list[str]
    missing_information: list[str]
    reason: str


class PolicyMatch(BaseModel):
    policy_name: str
    status: Literal["candidate", "not_eligible", "needs_review"]
    reason: str
    missing_fields: list[str]
    evidence_ids: list[str]


class ComparisonResult(BaseModel):
    policies: list[PolicyMatch]
    follow_up_question: str


class AnswerDraft(BaseModel):
    answer: str
    cited_ids: list[str]


class Citation(BaseModel):
    evidence_id: str
    source: str
    title: str
    page: int | None = None
    origin: Literal["vector_db", "policy_api"]


class AnswerResponse(BaseModel):
    question: str
    answer: str
    # 기존 클라이언트가 prompt·response를 읽어도 동작하도록 같은 값을 함께 제공합니다.
    prompt: str
    response: str
    status: Literal["answered", "needs_profile", "out_of_scope", "insufficient"]
    sources: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    policies: list[PolicyMatch] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_question: str = ""
    needs_review: bool = True
    handoff: bool = False
    api_status: str = "not_used"
    node_path: list[str] = Field(default_factory=list)
    latency_ms: int = 0


class Evidence(BaseModel):
    evidence_id: str
    content: str
    metadata: dict[str, Any]
    origin: Literal["vector_db", "policy_api"]


# [Graph의 작업 노트]
# 각 노드는 같은 state에서 필요한 값을 읽고 새 결과만 반환합니다.
# question/profile은 사용자 입력, documents/context는 검색 자료로 계속 분리합니다.
class PolicyState(TypedDict, total=False):
    request: RAGRequest
    reference_date: str
    missing_fields: list[str]
    search_query: str
    scope: ScopeDecision
    documents: list[Evidence]
    review: EvidenceDecision
    comparison: ComparisonResult
    answer: str
    cited_ids: list[str]
    api_status: str
    api_added: bool
    status: str
    follow_up_question: str
    node_path: list[str]

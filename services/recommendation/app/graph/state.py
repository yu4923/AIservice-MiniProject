"""백업의 요청·응답 DTO와 Graph 공유 상태를 현재 프로젝트 구조로 복원했습니다."""

from typing import Any, Literal, TypedDict

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


POLICY_SCOPES = (
    "중앙정부 청년 지원사업", "지자체 청년 지원정책", "청년정책 신청 자격 지원 내용",
    "청년 지원사업 모집 공고", "청년정책 종합 안내",
)


# [사용자 입력 DTO: Spring의 Request DTO에 해당]
# 사용자 상황은 profile, 질문은 question입니다. 검색 자료 context는 서버가 만듭니다.
# 소득은 '월 200만원'과 '기준중위소득 100%'가 다른 정보이므로 단위가 있는 문자열로 받습니다.
class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    age: int | None = Field(default=None, ge=0, le=120)
    region: str | None = Field(default=None, max_length=100)
    income: str | None = Field(default=None, max_length=200)
    employment_status: str | None = Field(default=None, max_length=100)
    interests: list[str] = Field(default_factory=list, max_length=10)
    # 기본 다섯 항목을 받은 뒤 소득 조건 비교에 더 필요한 경우 추가로 받을 수 있습니다.
    household_size: int | None = Field(default=None, ge=1, le=30)

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("관심 분야는 빈 값 없이 항목당 100자 이내로 입력하세요.")
        return [value.strip() for value in values]


class RAGRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # 기존 콘솔의 prompt도 받습니다. API 담당자는 새 이름 question을 사용하면 됩니다.
    question: str = Field(min_length=2, max_length=2000,
                          validation_alias=AliasChoices("question", "prompt"))
    profile: UserProfile = Field(default_factory=UserProfile)
    source: Literal["pdf", "web", "all"] = "all"
    top_k: int = Field(default=5, ge=1, le=20)


# [LLM의 판단 결과 DTO]
# 자유로운 문장 대신 정해진 항목으로 결과를 받아 Graph가 분기할 수 있게 합니다.
# sufficient는 '신청 자격이 된다'가 아니라 '조건을 비교할 문서 정보가 있다'는 뜻입니다.
class ScopeDecision(BaseModel):
    in_scope: bool
    reason: str


class EvidenceDecision(BaseModel):
    sufficient: bool
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

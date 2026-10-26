"""검색 요청의 자료형과 설문 선택 규칙을 추천 로직 실행 전에 검사한다."""

from typing import Literal

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, field_validator,
)

RECOMMEND_PROMPT = "설문에서 선택한 조건과 관심 분야에 맞는 청년 정책을 검색해 주세요."

REGIONS = frozenset({
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
})
STATUSES = frozenset({
    "student", "employed", "unemployed", "self_employed", "freelance", "none",
})
DETAILS_BY_INTEREST = {
    "employment": frozenset({"취업 준비 비용", "면접 지원", "일 경험·인턴", "직무 교육"}),
    "housing": frozenset({"월세·주거비", "임대주택", "주거 상담"}),
    "education": frozenset({"시험 응시료", "직무교육", "학습비"}),
    "startup": frozenset({"사업화 자금", "교육·멘토링", "창업 공간"}),
    "unknown": frozenset(),
}


def check_selection(values: list[str], allowed, *, exclusive: str | None = None) -> list[str]:
    """중복·배타 선택을 임의로 보정하지 않고 잘못된 입력으로 거절한다."""
    if len(values) != len(set(values)):
        raise ValueError("중복된 선택값은 허용하지 않습니다.")
    if any(value not in allowed for value in values):
        raise ValueError("허용된 항목만 선택해 주세요.")
    if exclusive is not None and exclusive in values and len(values) != 1:
        raise ValueError("해당 항목은 다른 항목과 함께 선택할 수 없습니다.")
    return values


class UserProfile(BaseModel):
    """클라이언트의 설문을 검증하며 사용자 식별자는 받지 않는다."""

    # 문자열 나이와 boolean을 정수로 보정하지 않고 JSON 타입 그대로 검사한다.
    model_config = ConfigDict(extra="forbid", strict=True)
    age: int = Field(ge=12, le=49)
    region: str
    statuses: list[str] = Field(min_length=1, max_length=5)
    interests: list[str] = Field(min_length=1, max_length=4)
    details: list[str] = Field(default_factory=list, max_length=13)

    # 기존 Graph가 참조하는 값은 보존하되 statuses로 소득·고용 형태를 추정하지 않는다.
    income: str | None = Field(default=None, max_length=200)
    employment_status: str | None = Field(default=None, max_length=100)
    household_size: int | None = Field(default=None, ge=1, le=30)

    @field_validator("region")
    @classmethod
    def check_region(cls, value: str) -> str:
        """상세 주소나 임의 지역 문자열을 지정된 17개 지역과 혼용하지 않는다."""
        if value not in REGIONS:
            raise ValueError("거주지역은 지정된 17개 지역 중 하나를 선택해 주세요.")
        return value

    @field_validator("statuses")
    @classmethod
    def check_statuses(cls, values: list[str]) -> list[str]:
        """현재 상황은 복수 선택을 허용하며 none만 단독 선택으로 제한한다."""
        return check_selection(values, STATUSES, exclusive="none")

    @field_validator("interests")
    @classmethod
    def check_interests(cls, values: list[str]) -> list[str]:
        """unknown을 특정 분야와 함께 전달해 의미가 충돌하는 것을 막는다."""
        return check_selection(values, DETAILS_BY_INTEREST, exclusive="unknown")

    @field_validator("details")
    @classmethod
    def check_details(cls, values: list[str], info: ValidationInfo) -> list[str]:
        """선택한 상위 관심 분야의 상세 항목만 허용하며 한국어 표기를 그대로 구분한다."""
        interests = info.data.get("interests")
        if interests is None:
            return values  # 상위 항목 오류가 이미 있어 추가 오류를 중복 생성하지 않는다.
        allowed = set().union(*(DETAILS_BY_INTEREST[interest] for interest in interests))
        return check_selection(values, allowed)

    def __repr__(self) -> str:
        """기본 객체 출력에 나이·지역 등 설문 원문이 섞이는 것을 막는다."""
        return "UserProfile[redacted]"

    def __str__(self) -> str:
        """문자열 로그에서도 설문 원문을 숨긴다."""
        return "UserProfile[redacted]"


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=4000)


class RAGRequest(BaseModel):
    """질문과 검증된 설문을 검색 API에 전달한다."""

    model_config = ConfigDict(extra="forbid", strict=True)

    prompt: str | None = Field(default=None, min_length=2, max_length=1000,
                               validation_alias=AliasChoices("prompt", "question"))
    profile: UserProfile

    @property
    def question(self) -> str:
        return self.prompt if self.prompt is not None else RECOMMEND_PROMPT

    @property
    def is_chat(self) -> bool:
        return self.prompt is not None

    policy_context: list[str] = Field(default_factory=list, max_length=5)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=4)

    @field_validator("policy_context")
    @classmethod
    def check_policy_context(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("정책명은 1~200자로 입력해 주세요.")
        return list(dict.fromkeys(value.strip() for value in values))

    # all과 기본값은 기존 추천 서버 계약을 유지한다.
    source: Literal["pdf", "web", "all"] = "all"
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("prompt", mode="before")
    @classmethod
    def prepare_question(cls, value):
        """질문만 앞뒤 공백을 제거하며 본문·대소문자·줄바꿈은 보존한다."""
        return value.strip() if isinstance(value, str) else value

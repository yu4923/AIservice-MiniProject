"""추천 요청의 자료형과 설문 선택 규칙을 추천 로직 실행 전에 검사한다."""

from typing import Literal

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo,
    field_validator, model_validator,
)

# [질문을 입력하지 않은 추천 요청]
# 답변을 고정하는 것이 아니라, 별도로 받은 profile로 추천하라는 작업 지시만 채웁니다.
DEFAULT_QUESTION = "입력한 사용자 정보와 관심 분야에 맞는 청년 지원정책을 추천해줘."

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
    age: int = Field(ge=0, le=120)
    region: str
    statuses: list[str] = Field(min_length=1, max_length=5)
    interests: list[str] = Field(min_length=1, max_length=4)
    details: list[str] = Field(default_factory=list, max_length=13)

    # 기존 Graph가 참조하는 값은 보존하되 statuses로 소득·고용 형태를 추정하지 않는다.
    income: str | None = Field(default=None, max_length=200)
    employment_status: str | None = Field(default=None, max_length=100)
    household_size: int | None = Field(default=None, ge=1, le=30)

    # [공백만 있는 소득·취업 상태도 미입력]
    # "   "는 실제 정보가 아닙니다. 문자열의 공백을 제거하고 비면 None으로 통일합니다.
    # 숫자나 boolean을 문자열로 바꾸지는 않으므로 기존 엄격한 자료형 검증은 유지됩니다.
    @field_validator("income", "employment_status", mode="before")
    @classmethod
    def prepare_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

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


class RAGRequest(BaseModel):
    """질문과 검증된 설문을 추천 API에 전달한다."""

    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(default=DEFAULT_QUESTION, min_length=2, max_length=1000,
                          validation_alias=AliasChoices("question", "prompt"))
    profile: UserProfile
    # [프론트는 profile만 전달]
    # source가 없으면 서버가 PDF 검색을 선택합니다. 부족하면 기존 Graph가 정책 API로 보완합니다.
    source: Literal["pdf", "web", "all"] = "pdf"
    top_k: int = Field(default=5, ge=1, le=20)

    # [클라이언트가 조작할 수 없는 내부 표시]
    # 같은 질문 문장이 들어와도 '직접 입력'과 '서버 자동 생성'을 문자열 비교로 구분하지 않습니다.
    # PrivateAttr는 요청·응답 JSON에 포함되지 않으며 프론트가 보낼 필드도 아닙니다.
    _question_is_generated: bool = PrivateAttr(default=False)

    @property
    def question_is_generated(self) -> bool:
        return self._question_is_generated

    @model_validator(mode="wrap")
    @classmethod
    def remember_question_origin(cls, value, handler):
        request = handler(value)
        if isinstance(value, dict):
            raw = value.get("question", value.get("prompt"))
            request._question_is_generated = raw is None or (
                isinstance(raw, str) and not raw.strip())
        return request

    @field_validator("question", mode="before")
    @classmethod
    def prepare_question(cls, value):
        """질문이 null·빈 문자열·공백이면 기본 질문을 쓰고, 유효한 질문은 보존한다."""
        if value is None:
            return DEFAULT_QUESTION
        if isinstance(value, str):
            return value.strip() or DEFAULT_QUESTION
        return value

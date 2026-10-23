"""Read-only client for the official Ontong Youth policy API."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
import os

import httpx
from langchain_core.documents import Document
from dotenv import load_dotenv

API_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class PolicyAPIError(RuntimeError):
    """Sanitized error: never include an authenticated request URL or body."""


class YouthPolicyAPI:
    def __init__(self, *, client: httpx.AsyncClient | None = None):
        load_dotenv(ENV_FILE)
        self._key = (os.getenv("YOUTH_POLICY_API_KEY") or "").strip()
        if not self._key:
            raise ValueError("services/recommendation/.env에 YOUTH_POLICY_API_KEY를 설정하세요.")
        self._client = client

    async def _get(self, params: dict) -> dict:
        params = {**params, "apiKeyNm": self._key, "rtnType": "json"}
        try:
            if self._client is not None:
                response = await self._client.get(API_URL, params=params, timeout=20)
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    response = await client.get(API_URL, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException:
            raise PolicyAPIError("온통청년 API 응답 시간이 초과되었습니다.") from None
        except httpx.HTTPStatusError as error:
            raise PolicyAPIError(f"온통청년 API HTTP 오류: {error.response.status_code}") from None
        except (httpx.RequestError, ValueError):
            raise PolicyAPIError("온통청년 API 호출 또는 JSON 응답 해석에 실패했습니다.") from None
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict) or not isinstance(result.get("youthPolicyList"), list):
            raise PolicyAPIError("온통청년 API 오류 응답입니다. 인증키 승인 상태와 API 명세를 확인하세요.")
        policies = result["youthPolicyList"]
        if not all(isinstance(policy, dict) for policy in policies):
            raise PolicyAPIError("온통청년 API 정책 목록 형식이 올바르지 않습니다.")
        return {"policies": policies, "pagination": result.get("pagging", {}), "source": API_URL}

    async def search(self, keyword: str, *, region_code: str | None = None,
                     page: int = 1, page_size: int = 10) -> dict:
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError("정책 검색어가 필요합니다.")
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page는 1 이상, page_size는 1~100 정수여야 합니다.")
        params = {"plcyNm": keyword.strip(), "pageNum": page, "pageSize": page_size, "pageType": "1"}
        if region_code:
            if not isinstance(region_code, str) or not all(len(c) == 5 and c.isdigit() for c in region_code.split(",")):
                raise ValueError("region_code는 5자리 지역코드 또는 쉼표로 구분한 지역코드여야 합니다.")
            params["zipCd"] = region_code
        return await self._get(params)

    async def detail(self, policy_no: str) -> dict:
        if not isinstance(policy_no, str) or not policy_no.strip():
            raise ValueError("정책번호가 필요합니다.")
        return await self._get({"plcyNo": policy_no.strip(), "pageType": "2", "pageNum": 1, "pageSize": 1})


# [stash 복구: 기존 Graph의 연결 규격을 최신 API 구현과 함께 유지]
# 위 YouthPolicyAPI는 원격에서 받은 실제 API 클라이언트이며 그대로 유지합니다.
# 아래 규격은 Graph가 요구하는 Document 목록용입니다. API의 원본 dict와는 다릅니다.
# 기존 PolicyAgent도 lookup(keyword, *, region_code=...) 형태이므로,
# Graph의 lookup(query, missing_information)과 연결하려면 별도 어댑터가 필요합니다.
# 이번에는 복구만 수행하고 agents 폴더나 실제 Agent 연결 방식은 바꾸지 않습니다.
# Spring의 Repository 인터페이스처럼 '무엇을 받을지'만 정합니다.
class PolicyApiClient(Protocol):
    configured: bool

    async def search(self, query: str) -> list[Document]: ...


# [Graph가 Agent에게서 받아야 하는 결과]
# Agent의 설명 문장이 아니라 실제 정책 본문과 출처가 있는 Document만 근거로 사용합니다.
@dataclass
class ApiLookupResult:
    documents: list[Document] = field(default_factory=list)
    status: Literal["not_configured", "used", "no_results", "failed", "timeout"] = "not_configured"


# [Agent 담당자와의 연결 약속]
# 검색어와 부족한 정책 정보를 받고, 보완한 문서와 처리 상태를 돌려주세요.
class PolicySupplementer(Protocol):
    async def lookup(self, query: str, missing_information: list[str]) -> ApiLookupResult: ...


# [미연결 상태를 명시하는 대체 객체: 실제 Agent가 아님]
# agents 폴더를 수정할 수 없으므로 기본 서버는 '아직 연결되지 않음'을 반환합니다.
# Agent 담당자가 준비되면 create_app(api_agent=담당자객체)로 이 객체를 교체합니다.
class UnconfiguredPolicyAgent:
    configured = False

    async def lookup(self, query: str, missing_information: list[str]) -> ApiLookupResult:
        return ApiLookupResult()

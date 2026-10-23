"""Read-only client for the official Ontong Youth policy API."""
from pathlib import Path
import os

import httpx
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

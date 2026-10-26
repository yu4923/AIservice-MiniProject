"""External lookup entry point for the future recommendation graph.

This module queries official policy data; LLM tool selection is not implemented yet.
"""
from app.tools.youth_policy_api import YouthPolicyAPI


REGION_PREFIXES = {
    "서울": {"11"}, "부산": {"26"}, "대구": {"27"}, "인천": {"28"},
    "광주": {"29"}, "대전": {"30"}, "울산": {"31"}, "세종": {"36"},
    "경기": {"41"}, "강원": {"42", "51"}, "충북": {"43"}, "충남": {"44"},
    "전북": {"45", "52"}, "전남": {"46"}, "경북": {"47"}, "경남": {"48"}, "제주": {"50"},
}


def matches_region(policy: dict, region: str | None) -> bool:
    # 등록기관 주소가 아닌 API의 대상 지역코드를 사용한다. 미기재는 검토 근거로 남긴다.
    codes = [code.strip() for code in str(policy.get("zipCd") or "").split(",") if code.strip()]
    prefixes = REGION_PREFIXES.get(region)
    if not prefixes or not codes or "00000" in codes:
        return True
    if any(len(code) != 5 or not code.isdigit() for code in codes):
        return True
    return any(code[:2] in prefixes for code in codes)


class PolicyAgent:
    def __init__(self, api: YouthPolicyAPI | None = None):
        self.api = api if api is not None else YouthPolicyAPI()

    async def lookup(self, keyword: str, *, region_code: str | None = None,
                     page: int = 1, page_size: int = 10) -> dict:
        """Search by policy name; return official data without judging eligibility."""
        return await self.api.search(keyword, region_code=region_code, page=page, page_size=page_size)

    async def get_detail(self, policy_no: str) -> dict:
        return await self.api.detail(policy_no)


class GraphPolicyAgent:
    """Adapt official API records to the graph's single supplement contract."""
    def __init__(self, agent=None):
        import os
        from dotenv import load_dotenv
        from app.tools.youth_policy_api import ENV_FILE
        load_dotenv(ENV_FILE, override=False)
        self.configured = agent is not None or bool((os.getenv("YOUTH_POLICY_API_KEY") or "").strip())
        self.agent = agent

    async def lookup(self, query: str, missing_information: list[str], *,
                     region: str | None = None, fallback_keywords: list[str] | None = None):
        import json
        import asyncio
        from urllib.parse import urlsplit
        from langchain_core.documents import Document
        from app.tools.youth_policy_api import ApiLookupResult, API_URL
        if not self.configured:
            return ApiLookupResult(status="not_configured")
        if self.agent is None:
            self.agent = PolicyAgent()
        documents, seen = [], set()
        try:
            # Graph sends up to three interest keywords, not the full private profile.
            keywords = list(dict.fromkeys(k.strip() for k in query.split(",") if k.strip()))[:3]
            async def search(keyword):
                # 지역 필터 없는 목록도 조회해 전국 정책을 누락하지 않는다.
                result = await self.agent.lookup(keyword, page_size=100)
                return [policy for policy in result["policies"] if matches_region(policy, region)]

            candidates = []
            for keyword in keywords:
                candidates.extend(await search(keyword))
            if not candidates:
                for keyword in list(dict.fromkeys(fallback_keywords or []))[:3]:
                    if not keyword.strip():
                        continue
                    # 지역명+키워드를 우선 조회하고 전국 대상도 찾을 수 있도록 핵심어로 보완한다.
                    local = await search(f"{region} {keyword}" if region else keyword)
                    candidates.extend(local)
                    if not local and keyword not in keywords:
                        candidates.extend(await search(keyword))
            for policy in candidates:
                    identifier = str(policy.get("plcyNo") or json.dumps(policy, sort_keys=True, ensure_ascii=False))
                    if identifier in seen:
                        continue
                    seen.add(identifier)
                    if policy.get("plcyNo") and len(documents) < 3:
                        try:
                            detail = await self.agent.get_detail(str(policy["plcyNo"]))
                            matching = [item for item in detail["policies"]
                                        if str(item.get("plcyNo")) == str(policy["plcyNo"])]
                            if matching:
                                policy = {**policy, **{key: value for key, value in matching[0].items()
                                                      if value is not None and value != ""}}
                        except Exception:
                            pass  # 상세 조회 실패 시 성공한 목록 응답은 유지한다.
                    source = API_URL
                    for field in ("refUrlAddr1", "refUrlAddr2", "aplyUrlAddr"):
                        url = policy.get(field)
                        if isinstance(url, str) and urlsplit(url).scheme in {"http", "https"} and urlsplit(url).netloc:
                            source = url
                            break
                    documents.append(Document(page_content=json.dumps(policy, ensure_ascii=False),
                        metadata={"source": source, "url": source,
                                  "title": str(policy.get("plcyNm") or "청년정책"),
                                  "policy_name": str(policy.get("plcyNm") or ""),
                                  "policy_id": str(policy.get("plcyNo") or ""),
                                  "target_region_codes": str(policy.get("zipCd") or ""),
                                  "application_period": str(policy.get("aplyYmd") or ""),
                                  "last_modified": str(policy.get("lastMdfcnDt") or "")}))
                    if len(documents) >= 10:
                        return ApiLookupResult(documents=documents, status="used")
        except asyncio.TimeoutError:
            return ApiLookupResult(status="timeout")
        except Exception:
            return ApiLookupResult(status="failed")
        return ApiLookupResult(documents=documents, status="used" if documents else "no_results")

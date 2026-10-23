"""External lookup entry point for the future recommendation graph.

This module queries official policy data; LLM tool selection is not implemented yet.
"""
from app.tools.youth_policy_api import YouthPolicyAPI


class PolicyAgent:
    def __init__(self, api: YouthPolicyAPI | None = None):
        self.api = api if api is not None else YouthPolicyAPI()

    async def lookup(self, keyword: str, *, region_code: str | None = None,
                     page: int = 1, page_size: int = 10) -> dict:
        """Search by policy name; return official data without judging eligibility."""
        return await self.api.search(keyword, region_code=region_code, page=page, page_size=page_size)

    async def get_detail(self, policy_no: str) -> dict:
        return await self.api.detail(policy_no)

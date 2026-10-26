"""백업의 조건 분기 Graph와 Service 진입 함수를 복원합니다."""

import asyncio
import re
import time
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import PolicyNodes, Reasoner, Retriever
from app.graph.state import AnswerResponse, Citation, PolicyState, RAGRequest
from app.agents.policy_agent import GraphPolicyAgent


def display_references(text: str, citations: list[Citation]) -> str:
    """사용자용 문장의 내부 근거 ID를 읽을 수 있는 출처명으로 바꾼다."""
    labels = {citation.evidence_id: citation.display or citation.title for citation in citations}
    return re.sub(
        r"\[([VA]\d+)\]|(?<![A-Za-z0-9_])([VA]\d+)(?![A-Za-z0-9_])",
        lambda match: labels.get(match.group(1) or match.group(2), "참고 자료"), text,
    )


# [이전 policy_graph.py를 현재 폴더 구조에 맞게 나눈 Service]
# main.py가 answer_question()을 부르면 각 노드는 workflow에 정의한 경로로 움직입니다.
class PolicyRagService(PolicyNodes):
    def __init__(self, retriever: Retriever, reasoner: Reasoner, api_agent=None):
        # Explicit injection remains available for tests and alternative API agents.
        super().__init__(retriever, reasoner,
                         api_agent if api_agent is not None else GraphPolicyAgent())
        self.graph = self._build_graph()

    # [Graph의 지도]
    # add_edge는 항상 이동하는 길, add_conditional_edges는 조건별로 갈라지는 길입니다.
    # 보완 Agent는 한 번만 진입하므로 자료가 없어도 무한 검색하지 않습니다.
    def _build_graph(self):
        graph = StateGraph(PolicyState)
        for name in ("collect_profile", "build_search", "retrieve", "assess_information",
                     "supplement", "compare_conditions", "generate", "finish"):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "collect_profile")
        graph.add_conditional_edges("collect_profile",
            lambda s: "finish" if s["missing_fields"] else "build_search",
            {"finish": "finish", "build_search": "build_search"})
        graph.add_conditional_edges("build_search",
            lambda s: "retrieve" if s["scope"].in_scope else "finish",
            {"retrieve": "retrieve", "finish": "finish"})
        graph.add_edge("retrieve", "assess_information")

        def route_information(state):
            review = state["review"]
            if (state.get("api_status", "not_used") == "not_used"
                    and (not review.sufficient or not review.application_status_verified
                         or review.missing_information)):
                return "supplement"
            if state["review"].sufficient:
                return "compare_conditions"
            return "supplement" if state.get("api_status", "not_used") == "not_used" else "finish"

        graph.add_conditional_edges("assess_information", route_information,
            {name: name for name in ("compare_conditions", "supplement", "finish")})
        # API가 미설정이거나 새 자료가 없으면 같은 자료로 모델을 다시 부르지 않고 종료합니다.
        graph.add_conditional_edges("supplement",
            lambda s: ("assess_information" if s["api_added"] else
                       "compare_conditions" if s["review"].sufficient else "finish"),
            {name: name for name in ("assess_information", "compare_conditions", "finish")})
        graph.add_edge("compare_conditions", "generate")
        graph.add_edge("generate", END)
        graph.add_edge("finish", END)
        return graph.compile()

    async def answer_question(self, request: RAGRequest) -> AnswerResponse:
        started = time.perf_counter()
        state = await asyncio.wait_for(self.graph.ainvoke({
            "request": request, "reference_date": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
            "api_status": "not_used", "node_path": [],
        }, config={"recursion_limit": 16}), timeout=150)
        cited = set(state.get("cited_ids", []))
        citations = []
        for doc in state.get("documents", []):
            if doc.evidence_id not in cited:
                continue
            meta = doc.metadata
            page = meta.get("page")
            source = str(meta.get("url") or meta.get("source") or "출처 미상")
            raw_title = str(meta.get("title") or meta.get("source") or "정책 자료")
            # 로컬 자료의 디렉터리 경로는 표시명에서 제외하고 원본 source는 보존한다.
            title = (raw_title if urlsplit(raw_title).scheme in {"http", "https"}
                     else PurePosixPath(raw_title.replace("\\", "/")).name)
            page = page if isinstance(page, int) and not isinstance(page, bool) else None
            citations.append(Citation(evidence_id=doc.evidence_id,
                source=source, title=title, page=page,
                display=f"{title} · {page}쪽" if page is not None else title,
                origin=doc.origin))
        comparison = state.get("comparison")
        policies = [policy.model_copy(deep=True) for policy in comparison.policies] if comparison else []
        for policy in policies:
            policy.reason = display_references(policy.reason, citations)
            policy.checks = [display_references(check, citations) for check in policy.checks]
            if policy.benefit is not None:
                policy.benefit = display_references(policy.benefit, citations)
        answer = display_references(state["answer"], citations)
        return AnswerResponse(question=request.question, prompt=request.question,
            answer=answer, response=answer, status=state["status"],
            # 기존 화면은 sources의 문자열을 표시하므로 PDF는 읽기 쉬운 이름을 제공한다.
            # 웹 출처는 클릭할 수 있도록 원래 URL을 유지한다.
            sources=list(dict.fromkeys(
                c.source if urlsplit(c.source).scheme in {"http", "https"} else c.display
                for c in citations)), citations=citations,
            policies=policies, missing_fields=list(dict.fromkeys(
                state.get("missing_fields", []) + [field for policy in policies for field in policy.missing_fields])),
            follow_up_question=display_references(state.get("follow_up_question", ""), citations),
            needs_review=(state["status"] != "answered"
                          or not state.get("review", None)
                          or not state["review"].application_status_verified
                          or any(p.status == "needs_review" for p in policies)),
            handoff=state["status"] == "insufficient", api_status=state["api_status"],
            node_path=state["node_path"], latency_ms=round((time.perf_counter() - started) * 1000))

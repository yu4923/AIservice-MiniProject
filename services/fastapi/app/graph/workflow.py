"""백업의 조건 분기 Graph와 Service 진입 함수를 복원합니다."""

import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import PolicyNodes, Reasoner, Retriever
from app.graph.state import AnswerResponse, Citation, PolicyState, RAGRequest
from app.agents.policy_agent import GraphPolicyAgent


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
            if state["review"].sufficient:
                return "compare_conditions"
            return "supplement" if state.get("api_status", "not_used") == "not_used" else "finish"

        graph.add_conditional_edges("assess_information", route_information,
            {name: name for name in ("compare_conditions", "supplement", "finish")})
        # API가 미설정이거나 새 자료가 없으면 같은 자료로 모델을 다시 부르지 않고 종료합니다.
        graph.add_conditional_edges("supplement",
            lambda s: "assess_information" if s["api_added"] else "finish",
            {"assess_information": "assess_information", "finish": "finish"})
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
            citations.append(Citation(evidence_id=doc.evidence_id,
                source=str(meta.get("url") or meta.get("source") or "출처 미상"),
                title=str(meta.get("title") or meta.get("source") or "정책 자료"),
                page=page if isinstance(page, int) and not isinstance(page, bool) else None,
                origin=doc.origin))
        comparison = state.get("comparison")
        policies = comparison.policies if comparison else []
        return AnswerResponse(question=request.question, prompt=request.question,
            answer=state["answer"], response=state["answer"], status=state["status"],
            sources=list(dict.fromkeys(c.source for c in citations)), citations=citations,
            policies=policies, missing_fields=list(dict.fromkeys(
                state.get("missing_fields", []) + [field for policy in policies for field in policy.missing_fields])),
            follow_up_question=state.get("follow_up_question", ""),
            needs_review=(state["status"] != "answered"
                          or not state.get("review", None)
                          or not state["review"].application_status_verified
                          or any(p.status == "needs_review" for p in policies)),
            handoff=state["status"] == "insufficient", api_status=state["api_status"],
            node_path=state["node_path"], latency_ms=round((time.perf_counter() - started) * 1000))

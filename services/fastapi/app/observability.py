"""LangSmith 추적 설정과 HTTP 요청 ID 연결."""
from contextvars import ContextVar
import os
from uuid import uuid4

# 질문·설문과 생성 응답은 기본적으로 외부 추적 서비스에 저장하지 않는다.
os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")

request_id_context: ContextVar[str | None] = ContextVar("search_request_id", default=None)


def graph_trace_config(is_chat: bool) -> dict:
    return {
        "recursion_limit": 16,
        "run_name": "youth_compass_chat" if is_chat else "youth_compass_recommend",
        "tags": ["youth-compass", "chat" if is_chat else "recommend"],
        "metadata": {
            "request_id": request_id_context.get() or str(uuid4()),
            "service": "fastapi",
        },
    }

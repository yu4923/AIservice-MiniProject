"""추천 서비스의 FastAPI 진입점입니다. 백업의 Graph 호출 부분을 복원했습니다."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.graph.nodes import LLMReasoner
from app.graph.state import AnswerResponse, RAGRequest
from app.graph.workflow import PolicyRagService
from app.tools.rag_api import RAGApiRetriever


# [설정 범위] 작업 가능한 app 안의 .env만 명시적으로 읽습니다.
# 기존 share 폴더나 다른 서비스의 .env를 복사하거나 읽지 않습니다.
# 터미널·컨테이너에서 이미 전달한 환경변수가 .env보다 우선합니다.
APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env", override=False)


# [객체 연결: Spring의 의존성 주입과 같은 역할]
# API는 요청과 응답만 담당하고, 실제 처리는 PolicyRagService에 맡깁니다.
# agents 폴더는 그대로 두고, 담당자의 객체가 준비되면 api_agent로 주입합니다.
def create_app(service: PolicyRagService | None = None, *, api_agent=None) -> FastAPI:
    application = FastAPI(title="청년정책 추천 Graph API", version="1.0.0")
    application.state.policy_service = service if service is not None else PolicyRagService(
        retriever=RAGApiRetriever(), reasoner=LLMReasoner(), api_agent=api_agent,
    )

    # [추천 API] 사용자 질문과 profile을 받습니다. context는 받지 않습니다.
    # 예전 /rag-query 경로도 추천 서버 내부 별칭으로만 유지합니다.
    # 별도 RAG 검색 서버의 /rag-query는 이 API와 역할·포트가 다릅니다.
    @application.post("/recommend", response_model=AnswerResponse, tags=["추천"])
    @application.post("/rag-query", response_model=AnswerResponse, include_in_schema=False)
    async def recommend(request: RAGRequest):
        try:
            return await application.state.policy_service.answer_question(request)
        except Exception:
            # API 키·질문·소득·외부 서비스 오류 원문을 사용자 응답에 노출하지 않습니다.
            raise HTTPException(
                status_code=503,
                detail="정책 검색 또는 모델 처리에 실패했습니다. 설정과 서비스 상태를 확인해 주세요.",
            ) from None

    @application.get("/health", tags=["상태"])
    def health():
        # 프로세스와 설정 존재 여부만 확인합니다. 외부 API 연결 성공을 보장하지 않습니다.
        # 이 경로는 LLM·RAG·외부 정책 API를 실제 호출하지 않습니다.
        return {
            "status": "ok",
            "service": "recommendation",
            "llm_configured": bool(os.getenv("OPENAI_API_KEY")),
            "policy_agent_configured": bool(
                getattr(application.state.policy_service.api_agent, "configured", False)),
            "general_web_search": False,
        }

    return application


# LLM 객체는 첫 실제 요청 때 생성되므로 키가 없어도 /health와 입력 검증은 가능합니다.
app = create_app()


# services/recommendation에서 실행:
# python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload

"""추천 서비스의 FastAPI 진입점입니다. 백업의 Graph 호출 부분을 복원했습니다."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response  #JWT_code: 인증 결과와 요청 ID를 응답에 연결한다.
from fastapi.middleware.cors import CORSMiddleware                      #JWT_code: 브라우저의 인증 쿠키 요청을 허용한다.

SERVICE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SERVICE_DIR / ".env", override=False)

from app.auth import FRONTEND_ORIGIN, get_current_user                  #JWT_code: 요청별 JWT 검증과 보관 기능을 사용한다.

from app.graph.nodes import LLMReasoner
from app.graph.state import AnswerResponse
from app.input_validation import RAGRequest
from app.graph.workflow import PolicyRagService
from app.tools.local_rag import LocalRAGRetriever
from contextlib import asynccontextmanager
import asyncio
from rag.bootstrap import prepare_indexes


# [설정 경로 통합] LLM과 정책 API가 같은 recommendation/.env를 읽게 합니다.
# .env.example은 설정 견본이고, 실행할 때 읽는 파일은 실제 .env입니다.
# 기존 share 폴더나 다른 서비스의 .env를 복사하거나 읽지 않습니다.
# 터미널·컨테이너에서 이미 전달한 환경변수가 .env보다 우선합니다.


# [객체 연결: Spring의 의존성 주입과 같은 역할]
# API는 요청과 응답만 담당하고, 실제 처리는 PolicyRagService에 맡깁니다.
# Default GraphPolicyAgent uses the policy API; tests can inject another agent.
def create_app(service: PolicyRagService | None = None, *, api_agent=None, initialize_indexes: bool = True) -> FastAPI:
    """#JWT_code: 프론트 입력을 받는 추천 API에 쿠키 인증과 CORS를 연결한다."""
    @asynccontextmanager
    async def lifespan(application):
        if initialize_indexes:
            await asyncio.to_thread(prepare_indexes)
        yield

    application = FastAPI(title="청년정책 추천 API", version="1.0.0", lifespan=lifespan)
    #JWT_code: 인증 쿠키 요청의 응답을 읽을 수 있는 프론트 Origin을 명시한다.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],                                 #JWT_code: 프론트가 인증 로그의 요청 ID를 확인하게 한다.
    )
    application.state.policy_service = service if service is not None else PolicyRagService(
        retriever=LocalRAGRetriever(), reasoner=LLMReasoner(), api_agent=api_agent,
    )

    # [추천 API] 사용자 질문과 profile을 받습니다. context는 받지 않습니다.
    @application.post("/recommend", response_model=AnswerResponse, tags=["추천"])
    async def recommend(
        request: RAGRequest, response: Response, _user=Depends(get_current_user),
    ):
        """#JWT_code: JWT를 검증한 요청의 질문과 profile만 기존 처리부에 전달한다."""
        try:
            return await application.state.policy_service.answer_question(request)
        except HTTPException:
            raise                                                       #JWT_code: 인증 모듈이 정한 상태와 추적 헤더를 보존한다.
        except Exception:
            # API 키·질문·소득·외부 서비스 오류 원문을 사용자 응답에 노출하지 않습니다.
            raise HTTPException(
                status_code=503,
                headers={"X-Request-Id": response.headers.get("X-Request-Id", "unavailable")},  #JWT_code: 실패 응답도 인증 로그와 대조할 수 있게 한다.
                detail="정책 검색 또는 모델 처리에 실패했습니다. 설정과 서비스 상태를 확인해 주세요.",
            ) from None

    @application.get("/health", tags=["상태"])
    def health():
        """서비스 상태만 확인하며 사용자 입력이나 인증 정보는 반환하지 않는다."""
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


# services/fastapi에서 실행:
# python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload

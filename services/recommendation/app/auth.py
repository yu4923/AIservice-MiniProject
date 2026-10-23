"""#JWT_code: Spring JWT 검증과 요청별 전달, 비밀값 없는 인증 로그를 담당한다."""
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import threading
import time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Cookie, HTTPException, Request, Response
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

#JWT_code: 서비스 자신의 설정만 읽으며 이미 주입된 환경변수를 덮어쓰지 않는다.
SERVICE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SERVICE_DIR / ".env", override=False)
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = "simple-auth-server"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")
JWT_LOG_DIR = SERVICE_DIR / "jwt_log"

if not JWT_SECRET.strip():
    raise RuntimeError("JWT_SECRET is required")

#JWT_code: 공유 Service와 Graph 상태에 JWT를 넣지 않아 동시 사용자의 토큰을 분리한다.
_request_token: ContextVar[str | None] = ContextVar("jwt_request_token", default=None)
_request_context: ContextVar[dict | None] = ContextVar("jwt_request_context", default=None)
_logger_lock = threading.RLock()


class _AuditFileHandler(RotatingFileHandler):
    """#JWT_code: 비공개 회전 로그를 디스크에 반영하고 기록 실패를 숨기지 않는다."""

    def _open(self):
        """#JWT_code: 새 로그를 소유자만 읽고 쓸 수 있는 권한으로 만든다."""
        descriptor = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        return os.fdopen(descriptor, "a", encoding="utf-8")

    def handleError(self, record):
        """#JWT_code: logging의 기본 오류 무시 동작 대신 호출자에게 실패를 알린다."""
        raise OSError("JWT audit log write failed") from None

    def emit(self, record):
        """#JWT_code: 인증 결과를 파일 버퍼뿐 아니라 디스크에도 반영한다."""
        super().emit(record)
        if self.stream is not None:
            os.fsync(self.stream.fileno())


def _audit_logger() -> logging.Logger:
    """#JWT_code: 프로세스별 파일을 사용해 다중 worker의 로그 회전 충돌을 막는다."""
    pid = os.getpid()
    logger = logging.getLogger(f"jwt_audit.{SERVICE_DIR}.{pid}")
    with _logger_lock:
        if not logger.handlers:
            JWT_LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            handler = _AuditFileHandler(
                JWT_LOG_DIR / f"jwt-{pid}.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
    return logger


def _audit(result: str, reason: str, status: int, *, event: str = "jwt_auth") -> str:
    """#JWT_code: 고정된 진단 항목만 JSON으로 기록해 토큰·본문·개인정보를 제외한다."""
    context = _request_context.get() or {
        "request_id": str(uuid4()), "method": "-", "path": "-",
    }
    record = {
        "timestamp": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="milliseconds"),
        "service": SERVICE_DIR.name,
        "pid": os.getpid(),
        "event": event,
        "result": result,
        "reason": reason,
        "auth_status": status,
        **context,
    }
    try:
        _audit_logger().info(json.dumps(record, ensure_ascii=False))
    except (OSError, ValueError):
        #JWT_code: 기록 없이 인증이 통과하는 것을 막고 내부 파일 경로는 노출하지 않는다.
        raise HTTPException(
            status_code=503,
            detail="Authentication audit logging is unavailable",
            headers={"X-Request-Id": context["request_id"]},
        ) from None
    return context["request_id"]


def _reject(reason: str, status: int = 401):
    """#JWT_code: 실패 사유는 로그로 구분하고 클라이언트에는 일반 오류만 반환한다."""
    request_id = _audit("rejected", reason, status)
    raise HTTPException(
        status_code=status,
        detail="Origin is not allowed" if status == 403 else "Authentication is required",
        headers={"X-Request-Id": request_id},
    )


@dataclass(frozen=True)
class CurrentUser:
    """#JWT_code: JWT 원문 없이 검증된 내부 번호와 로그인 아이디만 전달한다."""
    no: str
    id: str


def verify_access_token(token: str) -> CurrentUser:
    """#JWT_code: Spring과 같은 HS256 서명·issuer·exp·sub·id 계약을 검증한다."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
    except ExpiredSignatureError:
        _reject("expired")
    except JWTClaimsError:
        _reject("invalid_claims")
    except (JWTError, TypeError, ValueError):
        _reject("invalid_token")

    if payload.get("iss") != JWT_ISSUER:
        _reject("invalid_issuer")
    if "exp" not in payload:
        _reject("missing_exp")
    if type(payload["exp"]) is not int:
        _reject("invalid_exp")
    if payload["exp"] <= int(time.time()):
        _reject("expired")
    no = payload.get("sub")
    if not isinstance(no, str) or re.fullmatch(r"[1-9][0-9]{0,18}", no) is None:
        _reject("invalid_sub")
    if int(no) > 2**63 - 1:
        _reject("invalid_sub")
    login_id = payload.get("id")
    if not isinstance(login_id, str) or not login_id.strip():
        _reject("invalid_id")
    _audit("accepted", "valid", 200)
    return CurrentUser(no=no, id=login_id)


async def get_current_user(
    request: Request,
    response: Response,
    access_token: str | None = Cookie(default=None, alias="ACCESS_TOKEN"),
) -> AsyncIterator[CurrentUser]:
    """#JWT_code: 쿠키를 검증하고 요청별 JWT·추적 정보를 종료 시 반드시 정리한다."""
    try:
        request_id = str(UUID(request.headers.get("X-Request-Id", "")))
    except (ValueError, AttributeError):
        request_id = str(uuid4())
    route = request.scope.get("route")
    #JWT_code: query와 실제 URL 대신 라우트 템플릿을 기록해 비밀번호·토큰 유출을 막는다.
    context = _request_context.set({
        "request_id": request_id,
        "method": request.method,
        "path": getattr(route, "path", "-"),
    })
    token_context = None
    try:
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin is not None:
            own_origin = str(request.base_url).rstrip("/")
            if origin not in {FRONTEND_ORIGIN, own_origin}:
                _reject("origin_not_allowed", 403)
        if not access_token:
            _reject("missing_cookie")
        user = verify_access_token(access_token)
        token_context = _request_token.set(access_token)
        response.headers["X-Request-Id"] = request_id
        yield user
    finally:
        if token_context is not None:
            _request_token.reset(token_context)
        _request_context.reset(context)


def forwarded_cookies() -> dict[str, str]:
    """#JWT_code: 현재 요청의 JWT만 RAG 호출에 사용하고 전달 시도를 기록한다."""
    token = _request_token.get()
    if token is None:
        _reject("missing_request_context")
    _audit("forwarding", "rag_request", 200, event="jwt_forward")
    return {"ACCESS_TOKEN": token}


def forwarded_headers() -> dict[str, str]:
    """#JWT_code: 추천과 RAG 로그를 같은 요청 ID로 연결한다."""
    context = _request_context.get()
    if context is None:
        _reject("missing_request_context")
    return {"X-Request-Id": context["request_id"]}


_audit("ready", "logger_ready", 200, event="jwt_logger")

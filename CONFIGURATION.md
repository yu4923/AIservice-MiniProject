# 환경설정・실행 안내

## 인증 서버

Spring 인증 서버의 실행은 [services/auth/README.md](services/auth/README.md)를 참고하세요.
DB 접속 정보와 JWT 키는 `services/auth/.env`로 관리합니다.

## 통합 FastAPI

[services/fastapi/README.md](services/fastapi/README.md)에 설치・설정・초기 적재・실행 방법을 정리했습니다.
RAG와 검색은 하나의 FastAPI 프로세스에서 실행합니다.
`services/fastapi/.env`에 JWT・OpenAI・온통청년・KURE・자료 수집 설정을 넣습니다.
JWT_SECRET은 Spring과 동일하게 설정하세요. RAG_API_URL은 더 이상 사용하지 않습니다.

## 기타 서비스

음성 서비스는 `services/voice`에 유지하며 이번 통합에서는 변경하지 않았습니다.
실제 `.env`, 인덱스, PDF, 인증 로그는 Git에서 제외합니다.

## LangSmith 실행 추적

Compose 실행은 루트 `.env`, 개별 FastAPI 실행은 `services/fastapi/.env`에 설정합니다.

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=발급받은_키
LANGSMITH_PROJECT=youth-compass
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_HIDE_INPUTS=true
LANGSMITH_HIDE_OUTPUTS=true
```

LangSmith 프로젝트에서 추천·채팅 실행, Graph 노드, LLM 호출의 처리 시간과 오류를 확인합니다. Trace 메타데이터의 `request_id`는 HTTP 응답의 `X-Request-Id` 및 인증 로그와 연결됩니다. 인증 실패는 기존 인증 로그에서 확인합니다.

입출력 숨김이 기본값입니다. 개발용 데이터로 질문·근거·응답까지 확인하려면 `LANGSMITH_HIDE_INPUTS`와 `LANGSMITH_HIDE_OUTPUTS`를 `false`로 설정합니다. 계정 리전에 맞게 endpoint를 지정합니다. 비활성화는 `LANGSMITH_TRACING=false`로 설정합니다.

```bash
docker compose up -d --build fastapi
```

- [LangGraph 추적 공식 문서](https://docs.langchain.com/langsmith/trace-with-langgraph)
- [입출력 숨김 공식 문서](https://docs.langchain.com/langsmith/mask-inputs-outputs)

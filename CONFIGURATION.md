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

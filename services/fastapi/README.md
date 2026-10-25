# FastAPI 실행

`app/`은 JWT 인증・설문 검증・LangGraph・검색 답변 생성을 담당하고,
`rag/`는 자료 적재・KURE 임베딩・FAISS 내부 검색을 담당합니다.
하나의 Python 프로세스에서 동작하며 RAG HTTP 서버는 실행하지 않습니다.

## 설치

저장소 루트에서:

```bash
cd services/fastapi
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

`.env`의 다음 값을 입력합니다. 실제 키는 Git에 올리지 않습니다.

- `JWT_SECRET`: Spring 인증 서버와 동일한 값. 없으면 서버가 시작되지 않습니다.
- `OPENAI_API_KEY`: 검색 답변 생성용.
- `YOUTH_POLICY_API_KEY`: 온통청년 정책 조회용. 없으면 외부 보완은 not_configured.
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 최초 웹 검색 적재에 필요.
- `RAG_REQUIRED_INDEXES`: 기본 web. PDF도 필수면 web,pdf로 설정하고 `rag/documents/`에 PDF를 넣습니다.

기존 추천 `.env`는 폴더 이동에 따라 `services/fastapi/.env`에 유지됩니다.
기존 RAG `.env`는 `rag/.env`에 보관되지만 자동으로 읽지 않습니다.
필요한 KURE・수집 설정은 통합 `.env`로 옮기세요. 프로세스 환경변수가 우선합니다.
설정은 실행 전에 넣고, 실행 중 설정을 바꾸었다면 프로세스를 다시 시작하세요.

## 서버 실행

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --workers 1
```

시작 순서: 설정 확인 → 필수 인덱스 확인 → 없으면 수집・전처리・임베딩・저장 → 로딩 검증 → 요청 수신.
최초에는 KURE 모델 다운로드와 자료 처리로 시간이 걸릴 수 있습니다.
기존 인덱스가 있으면 재구축하지 않습니다. 모델이 다른 인덱스는 자동 덮어쓰기하지 않고 시작을 실패시킵니다.
적재 실패나 필수 인덱스 생성 실패 시 요청을 받지 않습니다. OCR이 필요한 PDF는 Tesseract와 kor/eng 언어팩이 필요합니다.
부트스트랩 잠금으로 여러 시작 작업의 중복 적재를 막지만, 초기 운영은 단일 worker를 사용하세요.

`RAG_BUILD_ON_START=false`는 자동 적재를 생략합니다. 인덱스가 없으면 Graph가 빈 검색 결과를 받고 외부 API 보완을 시도합니다.
전체 초기화를 비동기 스레드에서 수행하되 서버는 완료를 기다립니다.

- `POST /search`: JWT 인증이 필요한 유일한 업무 API.
- `GET /health`: 서버・설정 상태 확인. 외부 서비스 성공 보장 아님.
- `GET /docs`: Swagger 문서.
- `/rag-query`는 제거했습니다.

Spring에서 먼저 로그인한 브라우저가 ACCESS_TOKEN 쿠키를 보내야 합니다.
서버를 테스트한다고 인증을 끄거나 임의 토큰을 허용하지 않습니다.

요청 본문 예시:

```json
{
  "question": "내 조건에 맞는 주거 정책을 검색해줘",
  "profile": {
    "age": 25,
    "region": "서울",
    "statuses": ["unemployed"],
    "interests": ["housing"],
    "details": ["월세·주거비"]
  },
  "source": "all",
  "top_k": 5
}
```

소득은 필수 입력이 아닙니다. 미입력 소득을 추정하지 않고 조건 비교 결과에 확인 필요 항목으로 남깁니다.
`node_path`, `api_status`, `citations`, `policies`로 검색・외부 보완 결과를 확인할 수 있습니다.

각 `policies` 항목은 `policy_name`, `reason`, `status`, `missing_fields`, `evidence_ids`와
`benefit`, `application_period`를 반환합니다. LLM은 해당 근거에서 확인된 지원 내용을
`benefit`에, 신청·접수 기간을 `application_period: {"display": "공고에 명시된 기간"}`에 추출합니다.
근거가 없는 항목은 `null`입니다. 시행·지급 기간을 신청 기간으로 추정하지 않으며,
과거 공고는 원래 연도를 유지합니다. 기간이 있어도 현재 신청 가능 여부를 보장하지 않습니다.

업무 API는 `POST /search`이며 이전 `/recommend`는 제공하지 않습니다.
프론트 설정은 `VITE_SEARCH_API_URL`, 루트 Compose 포트 설정은 `SEARCH_PORT`를 사용합니다.

## 수동 적재와 테스트

```bash
python rag/scripts/ingest_topics.py
python rag/scripts/ingest_papers.py
python -m pytest tests rag/tests -q
```

테스트용 의존성은 저장소 루트에서 `python -m pip install -r infra/ci/requirements.txt`로 설치할 수 있습니다.
테스트는 실제 키・모델을 호출하지 않고 Graph・내부 검색・시작 초기화를 검증합니다.
모델과 실제 정책 API 검증은 GitHub Actions의 수동 integration 작업으로 분리합니다.

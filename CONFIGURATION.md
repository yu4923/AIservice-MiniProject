# 서비스별 환경변수 설정

각 서비스는 자신의 폴더에 있는 `.env`만 사용합니다. 루트 `.env`와
`services/voice/app/.env`는 자동으로 읽지 않습니다. 이미 주입된 프로세스 환경변수는
Python의 `.env`보다 우선하므로 이전에 export한 값이 있다면 확인하세요.
Java는 `.env`를 자동으로 읽지 않으며 실행 전에 환경변수로 내보내야 합니다.

| 서비스 | 설정 파일 | 필요한 값 |
|---|---|---|
| Java 인증 | `services/auth/.env` | DB_URL, DB_USER, DB_PASSWORD, JWT_SECRET |
| 음성 FastAPI | `services/voice/.env` | OPENAI_API_KEY, JWT_SECRET |
| RAG FastAPI | `services/rag/.env` | OPENAI_API_KEY, ASYNC_DB_URL, Naver 검색 인증정보 |

## 준비

프로젝트 루트에서 다음을 실행합니다. 기존 `.env`가 있으면 덮어쓰지 않습니다.
각 파일은 로컬에서 값을 입력하고 Git에는 `.env.example`만 게시하세요.

```bash
cp -n services/auth/.env.example services/auth/.env
cp -n services/voice/.env.example services/voice/.env
cp -n services/rag/.env.example services/rag/.env
chmod 600 services/auth/.env services/voice/.env services/rag/.env
```

`JWT_SECRET`은 `openssl rand -hex 32`로 한 번 생성한 값을 Java와 음성 서버 양쪽에
동일하게 설정합니다. 서버마다 새로 생성하지 마세요. 키 변경 후에는 기존 쿠키를 삭제하고
다시 로그인해야 합니다. RAG의 `ASYNC_DB_URL`은 사용자명과 비밀번호를 URL 인코딩한
MySQL 연결 문자열입니다. 기존 `.env`에 없던 필수 항목은 예시 파일을 보고 추가하세요.

## Java 실행

프로젝트 루트에서 시작합니다. `.env`는 셸 명령으로 해석되므로 본인이 작성하고
신뢰하는 파일만 source 하세요.

```bash
cd services/auth
set -a
source ./.env
set +a
./gradlew :app:run --no-configuration-cache
```

## 음성 서버 실행

프로젝트 루트에서 시작합니다. 이동 전 생성한 가상환경은 경로가 달라지므로 새 경로에서 다시 생성하세요.

```bash
cd services/voice
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8008 --reload
```

Docker Compose도 음성 서비스의 `.env`만 전달합니다. 프로젝트 루트에서:

```bash
docker compose --env-file services/voice/.env -f infra/compose.yaml up -d --build
```

## 프런트엔드 실행

```bash
cd frontend
npm ci
npm run dev
```

브라우저에서 `http://localhost:5174`를 엽니다. `npm run build` 결과는 `frontend/dist`에 생성됩니다.
프런트엔드 `.env.example`에는 공개 API 주소만 들어 있습니다. API 키는 넣지 마세요.
운영 웹 서버는 `/external`, `/internal` 요청을 `index.html`로 연결해야 합니다.

## RAG 서버

```bash
cd services/rag
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```


`services/rag/.env`를 자동으로 읽습니다. 다른 서비스의 `.env`는 읽지 않습니다.

## Git 게시 전

`.gitignore`는 모든 서비스의 `.env`, 가상환경, 빌드 결과, 업로드 음성, 로컬 DB,
벡터 인덱스를 제외합니다. 각 서비스의 `.env.example`은 게시 대상입니다.
Docker 이미지에도 `.env`와 업로드 파일을 포함하지 않습니다.
기존 로컬 `.env`는 삭제하거나 덮어쓰지 않았습니다.

이미 추적 중인 파일에는 ignore 규칙이 소급 적용되지 않습니다. `git status`와
`git ls-files`로 실제 게시 대상을 확인하세요. 과거 커밋에 비밀값을 올렸다면
키·비밀번호를 교체하고 Git 이력도 별도로 정리해야 합니다.

## RAG・추천 서비스의 컨테이너 연결

```bash
docker compose --env-file services/recommendation/.env -f infra/compose.backend.yaml up -d --build
```

Compose는 추천 서버에 OpenAI 키·온통청년 키·모델·RAG 주소만 주입하고,
RAG 검색 서버에는 로컬 임베딩 설정만 주입합니다. `.env`는 이미지에 복사되지 않습니다.
RAG 모델을 바꾸려면 같은 명령에 `--env-file services/rag/.env`를 추가할 수 있습니다.
로컬 실행에서는 각 서비스 폴더의 `.env`를 읽고, 컨테이너 환경변수가 우선합니다.

컨테이너에서는 `RAG_API_URL=http://rag:8001`, 호스트에서 개별 실행할 때는
`http://127.0.0.1:8001`을 사용합니다. URL에 `/rag-query`를 붙이지 마세요.
외부 API 키가 없으면 Graph는 `not_configured`로 처리합니다. 키가 있으면 기본 Agent가 연결됩니다.

이 Compose에는 음성・인증 DB・FAISS 볼륨 구성을 추가하지 않았습니다.
보류한 FAISS 데이터 연결을 구성하기 전에는 컨테이너의 RAG 검색 결과가 비어 있을 수 있습니다.
PDF OCR은 별도의 Tesseract・한국어 언어팩 구성이 필요하며 이번 이미지에는 추가하지 않았습니다.

# Youth Compass · 청년정책 나침반

Youth Compass는 청년 지원기관과 기업이 도입해 이용자에게 맞춤형 정책 정보를 제공하는 **연간 구독 기반 B2B 서비스**를 지향합니다. 공공기관 대상 공급은 B2G 모델로 확장합니다. 사용자의 나이, 거주 지역, 취업 상태와 관심 분야를 바탕으로 청년정책을 찾고, 지원 내용과 확인할 조건을 안내합니다.

중앙정부·광역지자체 정책 자료를 RAG로 검색하고, 온통청년 API에서 추가 정보를 조회해 답변을 보완합니다. 정책별 지원 내용과 추천 이유를 안내합니다.

## Pain Point

청년정책을 찾는 이용자와 이를 안내하는 기관은 다음과 같은 어려움을 겪습니다.

| Pain Point | 겪는 어려움 |
|---|---|
| 흩어진 정책 정보 | 중앙정부·지자체·기관별 자료를 각각 찾아봐야 합니다. |
| 복잡한 지원 조건 | 나이·거주지·취업 상태·소득 등 여러 조건을 비교해야 합니다. |
| 달라지는 공고와 일정 | 연도별 시행계획과 실제 모집 공고를 구분하고 변경 내용을 확인해야 합니다. |
| 반복되는 상담 업무 | 상담사가 비슷한 질문마다 자료를 찾고 근거를 정리해야 합니다. |
| 출처 확인의 어려움 | 추천 결과가 어떤 원본 자료를 근거로 하는지 확인하기 어렵습니다. |

Youth Compass는 사용자 조건에 맞는 정책 후보와 확인할 사항을 함께 제시하고, 원본 문서·페이지 또는 참고 링크를 제공해 정책 탐색과 상담을 돕습니다.

## 주요 기능

- 회원가입 및 로그인
- 사용자 설문 기반 맞춤형 청년정책 검색·추천
- 정책 관련 추가 질의응답
- 정부·지자체 정책 자료 기반 RAG 검색
- 온통청년 API를 활용한 정책 정보 보완

## 예상 고객

청년 대상 상담·교육·정책 안내 서비스를 운영하는 기관과 기업을 주요 고객으로 설정합니다.

| 예상 고객 | 도입 검토 부서·주체 | 활용 방식 |
|---|---|---|
| 지역 청년센터·위탁운영 법인 | 센터 운영팀·청년지원 매니저 | 상담 전 정책 후보 탐색, 출처 확인, 이용자 맞춤 정책 안내 |
| 대학·대학일자리플러스센터 | 취업지원처·학생지원처·센터 운영팀 | 재학생·졸업생에게 취업·주거·생활지원 정책 안내 |
| 지방자치단체 | 청년정책·일자리·정보화 담당 부서 | 지역 정책과 중앙정부 정책 통합 안내, 반복 문의 대응 |
| 청년 지원 재단·일자리 관련 공공기관 | 사업 운영팀·상담 부서 | 지원사업 참여자에게 관련 정책 연결, 상담 자료 탐색 지원 |
| 민간 취업지원·직업교육 운영기업 | 취업상담팀·교육사업팀 | 구직자·교육생 대상 취업 및 생활지원 정책 연계 |
| 채용·대학생·청년 생활 플랫폼 기업 | 서비스 기획팀·제휴팀 | 기존 서비스에 맞춤 정책 안내 기능 연동 |
| 금융·임직원 복지 플랫폼 기업 | 고객 서비스·복지 서비스 담당 부서 | 청년 고객·임직원을 위한 정책 혜택 탐색 기능 제공 |

초기에는 청년센터 운영기관과 대학일자리플러스센터를 중심으로 상담 업무 보조 효과를 검증합니다.

## 수익 모델

**기관·기업 단위의 연간 구독료를 주요 수익 모델로 설정합니다.** 고객은 1년 단위로 서비스를 구독하고, 상담사와 이용자에게 맞춤형 청년정책 검색·안내 기능을 제공합니다.

청년·복지 정책은 연도별 예산과 사업계획에 따라 지원 내용·대상·규모가 개편되는 경우가 많습니다. 따라서 정책 자료를 일회성으로 제공하기보다 매년 새로운 정책을 반영하고, 연중 변경되는 모집 공고와 신청 일정을 보완하는 지속적인 운영이 필요합니다. 이러한 정책 운영 주기에 맞춰 **1년 단위로 이용하고 갱신하는 구독 방식**을 채택합니다.

| 구분 | 내용 |
|---|---|
| 계약 단위 | 기관 또는 기업별 1년 구독 |
| 제공 가치 | 맞춤 정책 탐색, 상담 지원, 원본 출처 제공 |
| 운영 범위 | 계약에 합의한 정책 자료 갱신, 서비스 운영·유지보수 및 기본 사용량 |
| 갱신 | 다음 연도 정책과 고객의 이용 범위를 고려해 연간 계약 갱신 |

구체적인 구독료와 제공 범위는 도입 규모·이용량·운영 비용을 검증한 뒤 결정합니다.

## 서비스 구성

```text
Vue 화면
├── Spring Boot 인증 서버 ── MariaDB
└── FastAPI 정책 검색 서버
    ├── LangGraph: 검색·검토·API 보완·조건 비교·답변 생성
    ├── 내부 RAG: KURE 임베딩 + FAISS
    ├── 온통청년 API: 정책 정보 보완
    └── OpenAI API: 근거 검토·정책 비교·답변 생성
```

RAG와 추천 흐름은 하나의 FastAPI 컨테이너에서 실행합니다. LangGraph로 실행 흐름을 제어하고 FAISS로 정책 자료를 검색합니다.

| 구성 | 사용 기술 |
|---|---|
| 화면 | Vue 3, Vue Router, Vite, Nginx |
| 인증 | Java 21, Spring Boot, JWT, BCrypt |
| 정책 검색·추천 | Python 3.11, FastAPI, LangGraph, LangChain |
| 임베딩·검색 | KURE-v1, FAISS |
| 사용자 정보 저장 | MariaDB |
| 실행·검증 | Docker Compose, GitHub Actions |

## 디렉터리 구조

```text
frontend/                  Vue 화면·인증 및 검색 API 연동
services/auth/             Spring Boot 인증·MariaDB 연결
services/fastapi/
├── app/                   API·JWT 검증·Graph·정책 API 보완
└── rag/                   전처리·자료 적재·KURE·FAISS 검색
services/voice/             별도 음성 기능
compose.yaml               로컬 통합 실행 구성
data/                      인덱스·전처리 결과·모델 캐시
.github/workflows/         CI 및 수동 통합 검증
infra/                     추가 실행 구성·검증 도구
docs/                      상세 안내 문서
```

## 실행 방법

Docker와 Docker Compose가 설치되어 있어야 합니다. 모든 명령은 저장소 루트에서 실행합니다.

### 1. 환경변수 설정

기존 `.env`가 없다면 예제 파일을 복사합니다.

```bash
cp -n .env.example .env
```

`.env`에 다음 값을 입력합니다.

| 환경변수 | 용도 |
|---|---|
| `DB_USER` | MariaDB 서비스용 계정. 기본 예제는 `appuser` |
| `DB_PASSWORD` | 서비스용 DB 계정 비밀번호 |
| `MARIADB_ROOT_PASSWORD` | MariaDB 관리자 비밀번호 |
| `JWT_SECRET` | Spring과 FastAPI가 공유할 JWT 서명 비밀키 |
| `OPENAI_API_KEY` | 실제 정책 검토·답변 생성에 필요한 키 |
| `YOUTH_POLICY_API_KEY` | 온통청년 API 보완을 사용할 때 필요한 키 |
| `LLM_MODEL` | 답변 모델. 기본값 `gpt-4o` |

JWT 비밀키는 다음과 같이 생성할 수 있습니다.

```bash
openssl rand -hex 32
```

Compose는 루트 `.env`의 값을 각 서비스에 전달합니다. 이 방식으로 실행할 때 서비스별 `.env`를 추가로 만들 필요는 없습니다. 키워드 기반 웹 자료 수집에는 선택적으로 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`을 설정합니다.

### 2. 정책 자료 준비

중앙정부·광역지자체 정책 PDF 또는 PDF가 들어 있는 ZIP을 아래 폴더에 넣습니다. 원본 자료는 별도로 준비해야 합니다.

```text
services/fastapi/rag/documents/
```

데이터 저장 폴더를 준비하고 Compose 설정을 검사합니다.

```bash
mkdir -p services/fastapi/rag/documents data/faiss-kure-v1 data/preprocessed data/hf-cache
docker compose config --quiet
```

### 3. FAISS 인덱스 생성

```bash
docker compose --profile tools run --rm --no-deps --build ingest
```

PDF 전처리와 KURE 임베딩을 수행해 `data/faiss-kure-v1/`에 인덱스를 저장합니다. 완료 결과에서 `successful_documents`와 `failed_documents`를 확인합니다.

동일 자료·모델로 만든 정상 인덱스가 있으면 이 단계는 생략할 수 있습니다.

현재 루트 Compose는 서버 시작 시 자동 적재하지 않습니다. 적재 컨테이너가 인덱스를 만들고 FastAPI는 해당 경로를 읽기 전용으로 사용합니다.

### 4. 전체 서비스 실행

```bash
docker compose up -d --build
docker compose ps
```

| 서비스 | 기본 주소 |
|---|---|
| 웹 화면 | http://localhost:5174 |
| 인증 서버 상태 | http://localhost:8080/health |
| FastAPI 상태 | http://localhost:8002/health |
| FastAPI Swagger | http://localhost:8002/docs |

MariaDB는 Compose 내부의 `db:3306`으로 연결하며 호스트에 DB 포트를 공개하지 않습니다.

화면에서 **회원가입 → 로그인 → 설문 입력 → 정책 검색 → 추가 질문** 순서로 확인합니다.

브라우저 접속에는 `localhost`를 일관되게 사용합니다. 기본 구성은 로컬 PC 실행용이며, 프런트 포트를 변경하면 `FRONTEND_ORIGIN`, `LOGIN_SUCCESS_URL`도 실제 주소에 맞춰야 합니다.

### 실행 관리

로그 확인:

```bash
docker compose logs --tail=100 auth fastapi
```

FastAPI 코드 변경 반영:

```bash
docker compose up -d --build fastapi
```

정지 및 재실행:

```bash
docker compose down
docker compose up -d
```

### 추가 문서

- [환경변수 설정](CONFIGURATION.md)
- [Compose 상세 실행 안내](docs/COMPOSE_DRAFT_GUIDE.md)
- [CI·통합 검증 안내](docs/CI.md)

## 팀원

| 이름 | 역할 |
|---|---|
| 강서현 | 프런트엔드 |
| 김가은 | 배포·CI·운영 환경 |
| 김태완 | PM |
| 심지웅 | LLM 서빙·RAG·정책 API 보완 |
| 엄진용 | 데이터 파이프라인·전처리·적재 |
| 유선일 | 백엔드 API·인증 |
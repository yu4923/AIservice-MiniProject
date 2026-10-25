# aimini

## 디렉터리 구조

```text
aimini/
├── frontend/                    # 화면 담당 영역
├── services/
│   ├── auth/                    # Spring Boot 인증・MariaDB 연동
│   ├── fastapi/                 # 검색・RAG 통합 실행
│   │   ├── app/
│   │   │   ├── main.py          # 검색 API・시작 초기화
│   │   │   ├── auth.py          # JWT 검증
│   │   │   ├── graph/           # 검색 흐름・조건 비교・생성
│   │   │   ├── agents/          # 외부 정책 보완
│   │   │   └── tools/           # 내부 RAG・정책 API 연결
│   │   ├── rag/
│   │   │   ├── bootstrap.py     # 시작 시 인덱스 준비
│   │   │   ├── retrieval/       # KURE・FAISS 검색과 저장
│   │   │   ├── utils/           # 전처리・적재
│   │   │   ├── scripts/         # 수동 적재
│   │   │   ├── config/          # 검색어・공식 도메인
│   │   │   └── documents/       # PDF 원본 (Git 제외)
│   │   └── tests/               # 통합 로직 테스트
│   └── voice/                   # 기존 음성 기능
├── infra/                       # 실행 설정・CI 도구
├── data/                        # FAISS 등 영속 데이터 (Git 제외)
└── docs/                        # 참고 자료
```

## 담당 작업 영역

| 담당 파트 | 담당자 | 작업 폴더·파일 | 작업 내용·산출물 |
|---|---|---|---|
| 백엔드 API | 유선일 | `services/fastapi/app/main.py`, `services/auth/app/src/main/java/workplace/SimpleAuthServer.java`, `services/voice/app/main.py`, `services/voice/app/routers/` | 엔드포인트, 요청·응답 스키마, 인증, 로그, 미들웨어, API 명세·Swagger |
| 데이터 파이프라인 | 엄진용 | `services/fastapi/app/main.py`의 수집·적재 부분, `data/faiss/` | 데이터 수집·정제·청킹·임베딩, FAISS 적재·인덱스 관리, 적재 스크립트·데이터 출처표 |
| LLM 서빙 / RAG | 심지웅 | `services/fastapi/app/main.py`의 검색·생성 부분, `services/voice/app/services/processor_service.py` | Open Weight 모델 서빙 또는 Closed API 연동, 검색·프롬프트·응답 생성, 출처·확인 필요 여부 처리, RAG 체인·평가 결과 |
| 프런트엔드 | 강서현 | `frontend/src/`, `services/auth/app/src/main/resources/web/`, `services/voice/app/static/` | Vue 화면·API 연동, 답변·출처·확인 필요 여부 표시, 기존 인증·음성 화면 관리 |
| 배포 | 김가은 | `infra/compose.yaml`, `services/voice/Dockerfile`, `frontend/vite.config.js`, 각 서비스의 `.env.example`, `CONFIGURATION.md`, `README.md` | 서비스 실행·컨테이너 구성, 배포 설정·환경변수 항목 관리, 배포 URL·Compose 파일·문서 |

### RAG 공통 파일의 작업 구분

현재 RAG 기능은 `services/fastapi/app/main.py`에 함께 있으므로, 같은 파일 안에서도 다음 영역을 기준으로 나누어 작업합니다.

| 담당 | 파일 안의 작업 영역 |
|---|---|
| 백엔드 API | `FastAPI()` 설정, CORS·미들웨어, 라우트 선언, `input_validation.RAGRequest`·`AnswerResponse`, 입력 검증·HTTP 응답·로그 |
| 데이터 파이프라인 | `load_paper()`, `upload_topic()`·`upload_pdf()` 내부의 수집·텍스트 추출·청킹·임베딩·저장, FAISS 인덱스 로딩 |
| LLM 서빙 / RAG | `services/fastapi/app/graph/nodes.py`의 검색 조건·근거 평가·조건 비교·검색 답변 생성, `services/fastapi/app/agents/`의 외부 정보 보완 |

`AnswerResponse`와 프런트엔드의 응답 처리는 백엔드 API·LLM 서빙 / RAG·프런트엔드 담당자가 함께 맞추는 영역입니다.

### 프런트엔드 파일별 작업 구분

| 파일 | 작업 영역 |
|---|---|
| `frontend/src/views/HomeView.vue` | 홈 화면·콘솔 진입 |
| `frontend/src/views/ExternalRagView.vue` | 웹·PDF 업로드, 외부 RAG 질의·응답 화면 |
| `frontend/src/views/InternalRagView.vue` | 내부 데이터 인덱싱·검색·질의 화면 |
| `frontend/src/components/JsonOutput.vue` | 공통 결과 출력 |
| `frontend/src/api/http.js` | 공통 HTTP 요청·오류 처리 |
| `frontend/src/api/config.js` | API 서버 주소 |
| `frontend/src/router/index.js` | 페이지 경로·이동 |
| `frontend/src/assets/main.css` | 공통 스타일 |

### 음성 서버 파일별 작업 구분

| 파일·폴더 | 작업 영역 |
|---|---|
| `services/voice/app/main.py`, `services/voice/app/config.py` | 백엔드 API: 서버 초기화·JWT·설정 |
| `services/voice/app/routers/stt_router.py`, `services/voice/app/routers/tts_router.py`, `services/voice/app/routers/stt_tts_router.py` | 백엔드 API: 음성 요청·응답·인증 |
| `services/voice/app/services/stt_service.py`, `services/voice/app/services/tts_service.py` | 백엔드 API: 음성 인식·합성 서비스 연결 |
| `services/voice/app/services/processor_service.py` | LLM 서빙 / RAG: 음성 통번역 모델 호출·프롬프트 |
| `services/voice/app/static/` | 프런트엔드: 기존 음성 화면 |
| `services/voice/Dockerfile`, `infra/compose.yaml` | 배포: 음성 서버 컨테이너 구성 |

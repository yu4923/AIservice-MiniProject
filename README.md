# aimini

## 디렉터리 구조

```text
aimini/
├── frontend/                              # Vue 3 프런트엔드
│   ├── src/
│   │   ├── views/                         # 홈·외부 RAG·내부 RAG 페이지
│   │   ├── components/                    # 공통 화면 컴포넌트
│   │   ├── api/                           # API 주소·HTTP 요청 처리
│   │   ├── router/                        # 페이지 라우팅
│   │   ├── assets/                        # 공통 스타일
│   │   ├── App.vue                        # 최상위 화면
│   │   └── main.js                        # Vue 앱 진입점
│   ├── vite.config.js                     # 프런트엔드 개발·빌드 설정
│   └── .env.example                       # 공개 API 주소 예시
├── services/
│   ├── auth/                              # Java 인증 서버
│   │   ├── app/src/main/java/workplace/
│   │   │   ├── SimpleAuthServer.java      # 인증 API·회원 저장소·JWT 처리
│   │   │   ├── Environment.java           # 환경변수 검증
│   │   │   └── DbExample.java             # DB 접속 확인 예제
│   │   ├── app/src/main/resources/web/     # Java 서버의 로그인·회원가입 화면
│   │   ├── app/build.gradle               # Java 의존성·실행 설정
│   │   └── .env.example                   # DB·JWT 설정 예시
│   ├── rag/                               # FastAPI RAG 서버
│   │   ├── app/main.py                    # API·수집·임베딩·FAISS·LLM 처리
│   │   ├── requirements.txt               # RAG 서버 의존성
│   │   └── .env.example                   # LLM·DB·검색 API 설정 예시
│   └── voice/                             # FastAPI 음성 서버
│       ├── app/
│       │   ├── main.py                    # 라우터 등록·JWT 검증·정적 파일 제공
│       │   ├── config.py                  # 환경변수·업로드 경로 설정
│       │   ├── routers/                   # STT·TTS·음성 통번역 API
│       │   ├── services/                  # 음성 인식·LLM 번역·음성 합성
│       │   ├── static/                    # 기존 음성 기능 화면
│       │   └── utils/                     # 음성 관련 공통 유틸리티
│       ├── Dockerfile                     # 음성 서버 이미지 구성
│       ├── requirements.txt               # 음성 서버 의존성
│       └── .env.example                   # OpenAI·JWT 설정 예시
├── infra/
│   └── compose.yaml                       # 현재 음성 서버 컨테이너 구성
├── data/                                  # 로컬 데이터 저장 영역
│   ├── faiss/                             # 웹·PDF FAISS 인덱스
│   └── voice/uploads/                     # 업로드 음성·합성 음성
├── docs/                                  # 참고 자료
├── CONFIGURATION.md                       # 환경설정·실행 안내
└── README.md                              # 디렉터리·담당 작업 영역
```

## 담당 작업 영역

| 담당 파트 | 담당자 | 작업 폴더·파일 | 작업 내용·산출물 |
|---|---|---|---|
| 백엔드 API | 유선일 | `services/rag/app/main.py`, `services/auth/app/src/main/java/workplace/SimpleAuthServer.java`, `services/voice/app/main.py`, `services/voice/app/routers/` | 엔드포인트, 요청·응답 스키마, 인증, 로그, 미들웨어, API 명세·Swagger |
| 데이터 파이프라인 | 엄진용 | `services/rag/app/main.py`의 수집·적재 부분, `data/faiss/` | 데이터 수집·정제·청킹·임베딩, FAISS 적재·인덱스 관리, 적재 스크립트·데이터 출처표 |
| LLM 서빙 / RAG | 심지웅 | `services/rag/app/main.py`의 검색·생성 부분, `services/voice/app/services/processor_service.py` | Open Weight 모델 서빙 또는 Closed API 연동, 검색·프롬프트·응답 생성, 출처·확인 필요 여부 처리, RAG 체인·평가 결과 |
| 프런트엔드 | 강서현 | `frontend/src/`, `services/auth/app/src/main/resources/web/`, `services/voice/app/static/` | Vue 화면·API 연동, 답변·출처·확인 필요 여부 표시, 기존 인증·음성 화면 관리 |
| 배포 | 김가은 | `infra/compose.yaml`, `services/voice/Dockerfile`, `frontend/vite.config.js`, 각 서비스의 `.env.example`, `CONFIGURATION.md`, `README.md` | 서비스 실행·컨테이너 구성, 배포 설정·환경변수 항목 관리, 배포 URL·Compose 파일·문서 |

### RAG 공통 파일의 작업 구분

현재 RAG 기능은 `services/rag/app/main.py`에 함께 있으므로, 같은 파일 안에서도 다음 영역을 기준으로 나누어 작업합니다.

| 담당 | 파일 안의 작업 영역 |
|---|---|
| 백엔드 API | `FastAPI()` 설정, CORS·미들웨어, 라우트 선언, `RAGRequest`·`AnswerResponse`, 입력 검증·HTTP 응답·로그 |
| 데이터 파이프라인 | `load_paper()`, `upload_topic()`·`upload_pdf()` 내부의 수집·텍스트 추출·청킹·임베딩·저장, FAISS 인덱스 로딩 |
| LLM 서빙 / RAG | `rag_query()` 내부의 검색·LLM 선택·프롬프트·답변 생성, `extract_by_marker()`, `fallback_extract_from_context()`, 출처·확인 필요 여부 판단 |

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

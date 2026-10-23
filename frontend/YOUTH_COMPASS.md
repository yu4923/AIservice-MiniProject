# Youth Compass 프론트엔드

SKALA_mini Figma 원본 기반 Vue 3 + Vite 구현입니다. Figma에서 받은 로고·배경·일러스트는 public/figma에 로컬 저장했습니다.

## 실행

프로젝트의 Node.js 조건(22.12 이상)을 따릅니다. frontend 폴더에서 `npm ci` 후 `npm run dev` 실행, http://localhost:5174 접속. 현재 확인용 서버는 다른 서버와 충돌을 피하기 위해 `npm run dev -- --port 5176`으로 실행했습니다.

`npm run build`로 배포용 dist를 생성할 수 있습니다. 배포 작업은 수행하지 않았습니다.

## 화면

- `/`: 스플래시 → 원본 시작 화면 → 시작하기 버튼으로 로그인 이동
- `/home`: 스크롤형 메인, 원본 배경/일러스트, 예시 질문
- `/categories`: 정책 분야 소개
- `/login`, `/signup`: 로그인/회원가입, 비밀번호 표시, 입력 검증·오류
- `/survey/1` ~ `/survey/5`: 나이, 17개 시·도 거주지역, 현재 상태, 관심 분야, 상세 관심사. 이전 선택 유지, 복수 선택·해당 없음 배타 처리
- `/recommendations`: 맞춤 결과, 상세 보기, 질문/답변·출처·에러 상태
- `/console`, `/external`, `/internal`: 기존 RAG 테스트 화면 유지

## 데모와 실제 서버

기본값은 데모입니다. 실제 계정/정책 추천/LLM을 만들지 않습니다. 입력 비밀번호는 저장하지 않고 로그인 후 지웁니다. 예시 정책은 화면에 명시합니다. STT/TTS는 서버 계약 미확정으로 구현하지 않았으며 지원하는 것처럼 마이크 버튼을 표시하지 않습니다.

실제 연결은 `.env.example`을 `.env.local`로 복사하고 VITE_DEMO_MODE=false 및 서버 주소/경로를 설정합니다. `src/api/youth.js`에서 Java 로그인과 가입의 요청 필드(username/password), 토큰 필드, RAG 응답 계약을 실제 Swagger와 대조하세요. 기존 VITE_RAG_API_URL을 기본 RAG 서버 주소로 사용합니다. 질문 필드는 환경변수로 question/prompt를 선택할 수 있습니다.

인증 요청에는 `credentials: 'include'`를 사용합니다. JWT는 본문이나 Authorization 헤더로 보내지 않으며, 로그인 응답에 토큰이 없어도 정상 처리합니다. 실제 인증/권한은 서버 쿠키로 확인해야 합니다. 현재 로그아웃 버튼은 화면 상태만 초기화하므로 서버 세션 종료 API는 별도 합의가 필요합니다. 실제 사용자 데이터 대신 가상 조건으로 실습하세요. 회원가입 닉네임은 현재 Figma에 없어 추가하지 않았습니다.

추천은 `POST http://localhost:8002/recommend`에 `{ "profile": { age, region, statuses, interests, details, income, employment_status, household_size } }`만 보냅니다. `question`, `source`, `top_k`, ID, JWT는 추천 본문에서 제외합니다. 소득/취업 상태/가구원 수의 미입력 값은 null이며 임의로 추정하지 않습니다. `status: 'needs_profile'` 또는 `needs_profile: true` 응답 시 소득·취업 상태 추가 입력 폼이 표시됩니다. 정확한 실제 응답 스키마는 백엔드와 확인해야 합니다. 응답의 answer/sources 및 policies를 표시합니다. 대화 질문 API는 별개로 기존 `/rag-query`를 유지합니다.

추천 API는 데모 모드와 별도로 실제 요청합니다. 실제 쿠키 로그인을 테스트할 때는 `VITE_DEMO_MODE=false`를 설정하고 개발 서버를 재시작하세요. 서버는 프론트 origin(예: `http://localhost:5176`)과 credential CORS를 허용해야 합니다. 서버에서 question을 여전히 필수로 검증한다면 profile-only 계약과 일치하도록 백엔드 확인이 필요합니다.

검증 테스트: `node --test src/api/youth.test.mjs` (쿠키 요청/본문/필드 유효성).

## 원본과 기능 보정

원본의 보라색 #8738ee와 화면 구성을 유지하고 로그인 버튼 오표기, 설문 진행 숫자 중복을 수정했습니다. 고정 캔버스를 반응형 레이아웃으로 옮겼습니다. 추천 화면은 아직 Figma 원본이 없어 같은 스타일의 기능 화면으로 추가했습니다.

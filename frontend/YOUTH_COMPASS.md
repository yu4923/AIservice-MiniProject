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

기본값은 실제 서버 연결입니다. 명시적으로 `VITE_DEMO_MODE=true`를 설정한 경우에만 로그인·가입을 화면 데모로 처리합니다. 추천/대화 API는 실제 서버에 요청합니다. 입력 비밀번호는 저장하지 않고 로그인 후 지웁니다. STT/TTS 및 파일 업로드는 미연결이며 음성 버튼은 준비 안내만 표시합니다.

인증 기본 서버는 `http://localhost:8080`입니다. 로그인 `POST /api/login`, 가입 `POST /api/signup`은 `{id,password}` JSON을 보냅니다. 성공한 로그인은 응답의 redirect를 외부로 따라가지 않고 프론트 `/home`으로 이동합니다. `/api/auth/login`, `/api/auth/signup` 별칭은 환경변수로 선택할 수 있습니다.

인증 요청에는 `credentials: 'include'`를 사용합니다. JWT는 본문이나 Authorization 헤더로 보내지 않으며, 로그인 응답에 토큰이 없어도 정상 처리합니다. 새로고침 시 `GET /api/auth/check`로 실제 로그인 상태와 id를 확인합니다. 로그아웃은 `POST /api/logout` 성공 후에만 사용자·설문·대화 상태를 지웁니다. 실패하면 오류와 재시도를 표시합니다. 회원가입 닉네임은 현재 Figma에 없어 추가하지 않았습니다.

추천은 `POST http://localhost:8002/recommend`에 `{ "profile": { age, region, statuses, interests, details, income, employment_status, household_size } }`만 보냅니다. `question`, `source`, `top_k`, ID, JWT는 추천 본문에서 제외합니다. 소득/취업 상태/가구원 수의 미입력 값은 null이며 임의로 추정하지 않습니다. `status: 'needs_profile'` 또는 `needs_profile: true` 응답 시 소득·취업 상태 추가 입력 폼이 표시됩니다. 정확한 실제 응답 스키마는 백엔드와 확인해야 합니다. 응답의 answer/sources 및 policies를 표시합니다. 대화 질문 API는 별개로 기존 `/rag-query`를 유지합니다.

추천 API는 데모 모드와 별도로 실제 요청합니다. 현재 Spring Boot는 `http://localhost:5174` origin과 쿠키 인증을 허용하므로 `npm run dev` 후 해당 주소에서 사용하세요. `5176`은 실행 중인 서버에서 ORIGIN_NOT_ALLOWED로 거절됩니다. 다른 포트를 사용할 때는 백엔드 담당자가 FRONTEND_ORIGIN/CORS를 맞춰야 합니다. 서버에서 question을 여전히 필수로 검증한다면 profile-only 계약과 일치하도록 백엔드 확인이 필요합니다.

검증 테스트: `node --test src/api/youth.test.mjs` (쿠키 요청/본문/필드 유효성).

## 원본과 기능 보정

원본의 보라색 #8738ee와 화면 구성을 유지하고 로그인 버튼 오표기, 설문 진행 숫자 중복을 수정했습니다. 고정 캔버스를 반응형 레이아웃으로 옮겼습니다. 추천 화면은 아직 Figma 원본이 없어 같은 스타일의 기능 화면으로 추가했습니다.

# 프론트·RAG 담당자 전달 사항

현재 소스 계약은 `no-id-pw-v2`다. 상세 명세는 [FRONTEND_API.md](FRONTEND_API.md)를 따른다. 이 문서는 전달할 내용이며, 상대 서버 적용·연동 확인 완료를 의미하지 않는다. 다른 담당자에게 직접 전송하지 않았다.

## 프론트 담당자

- Spring 주소: `http://localhost:8080`. 브라우저 호스트는 `localhost`로 통일한다.
- 가입: `POST /api/auth/signup`, 로그인: `POST /api/auth/login`. 입력은 `id`, `password` 두 개다.
- 기본 form 요청: `Content-Type: application/x-www-form-urlencoded`, `new URLSearchParams({ id, password })`. JSON 두 필드도 지원한다.
- 모든 인증 fetch에 `credentials: "include"`를 지정한다. JWT는 HttpOnly 쿠키이므로 JavaScript에서 읽거나 localStorage에 저장하지 않는다.
- 가입 응답은 `{ok:true,no:"7",id:"demo"}`. 인증 확인은 `GET /api/auth/check`, 응답의 `no/sub`는 내부 번호 문자열, `id`는 로그인 아이디다. `user_id/username`을 기대하는 기존 코드는 변경해야 한다.
- 중복 아이디는 409 `ID_EXISTS`. 가입 후 별도로 로그인한다. JWT는 1시간이며 새로고침은 `/api/auth/check`로 상태를 확인한다.
- 허용 Origin은 현재 `http://localhost:5174`. 프론트 포트가 다르면 사용자에게 알려 auth의 `FRONTEND_ORIGIN`과 `LOGIN_SUCCESS_URL`을 맞춘다.

## RAG / FastAPI 담당자

- 기존 `http://localhost:8001` 유지. 프론트가 직접 호출한다. Spring이 RAG 프록시를 수행하지 않는다.
- 브라우저가 보내는 `ACCESS_TOKEN` 쿠키에서 JWT를 읽어 검증한다. FastAPI의 CORS도 실제 프론트 Origin을 명시하고 credentials를 허용해야 한다.
- HS256을 고정하고 Spring과 같은 `JWT_SECRET`, issuer `simple-auth-server`, 필수 `exp/sub/id`를 검증한다. 누락·만료·서명 오류·issuer 오류는 401로 처리한다.
- `sub`는 양의 signed 64-bit 범위 내부 `no`의 문자열이며 `id`는 비어 있지 않은 로그인 문자열이다. `username` claim만 있는 이전 JWT는 사용하지 않고 재로그인한다.
- `JWT_SECRET` 값은 Git·프론트·이 문서·채팅에 넣지 않는다. 사용자가 RAG 담당자의 비공개 서버 환경변수에 별도 전달해야 한다. auth DB 접속 정보는 RAG의 JWT 검증에 필요하지 않다.
- 이 문서는 FastAPI에 검증이 적용됐다는 증거가 아니다. 사용자가 직접 연동 검증한다.

## auth 실행 담당자

현재 소스의 DB 구조는 `no/id/pw`다. 이전 `id/username/password` DB에 새 소스를 연결하기 전 별도 마이그레이션 계획과 승인이 필요하다. 이번 커밋 준비 작업에서 DB 변경·서버 재시작·컨테이너 실행·외부 연동 검증은 수행하지 않는다. 다른 컴퓨터는 비공개 `.env`를 직접 준비해야 하며 키가 포함된 `.env`는 커밋으로 전달되지 않는다.

## 충돌을 줄이는 커밋 경계

auth는 `services/auth/**`, 프론트·RAG는 각자 서비스 경로만 커밋한다. 루트 Compose·공통 설정 변경은 담당자끼리 먼저 합의한다. auth 커밋은 `./scripts/commit_auth.sh "메시지"`로 제한한다. 같은 auth 파일을 다른 사람이 함께 수정하면 충돌할 수 있으므로 소유 범위도 공유한다.

이번 경계 정리에서 새로 만든 파일은 `AGENTS.md`(작업 범위), `scripts/commit_auth.sh`(경로 제한 커밋), 이 문서(전달 계약)다. 커밋 파일 목록 검사와 auth 단위/API fixture 테스트·JAR 빌드는 수행하지만 외부 서버 연동 검증은 사용자가 수행한다. 되돌릴 때 이미 공유한 커밋은 `git revert <커밋>`로 역커밋하며 DB는 별도 대상으로 다룬다.

## 이번 커밋 준비 검증

- 원본 auth에서 `./gradlew --no-daemon --console=plain test bootJar`: BUILD SUCCESSFUL. 테스트 49개, 실패 0, 오류 0.
- `sh -n scripts/commit_auth.sh`: 통과.
- 임시 Git 저장소에 다른 담당자 파일을 미리 스테이징한 뒤 스크립트 실행: auth 파일만 커밋되고 다른 파일의 스테이징 diff와 실제 내용이 유지됨을 확인.
- 실제 스테이징 대상의 auth 경로 제한, 비공개 `.env`·현재 로컬 비밀값·빌드 산출물 제외 검사: 통과.
- 연동 검증·실제 개발 DB 변경·서버 재시작: 이번 작업에서 수행하지 않음.

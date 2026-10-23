# auth 작업 지침

## 0. 구조 변환 정의

기존 Java HttpServer 구현을 Spring Boot 인증 서비스로 옮긴 작업본이다. 이전 구현은 `legacy/java-httpserver`에 보관한다. 수정·생성·삭제 범위는 `services/auth/**`로 제한한다. 프론트·RAG·다른 서비스·루트 공유 파일은 수정하거나 원복하지 않는다.

## 1. UI 유지 선언

프론트 화면과 상태 관리는 프론트 담당 영역이다. auth에서 프론트 파일을 변경하지 않는다. 프론트·RAG 연동 검증은 사용자가 직접 진행한다. 다른 서버를 재시작하거나 설정을 변경하지 않는다.

## 2. API / DB 스펙

단일 계약은 `docs/FRONTEND_API.md`다. 입력은 `id`, `password`다. 현재 소스 DB는 `users(no, id, pw)`, `id`는 고유 로그인 문자열이다. 실제 DB가 이 구조로 이관됐다고 추정하지 않는다. DB 마이그레이션·스키마 적용은 별도 확인을 받는다.

## 3. 인증 / 권한 모델

Spring localhost:8080에서 로그인과 JWT 발급을 담당한다. JWT는 HS256, issuer `simple-auth-server`, 필수 `exp/sub/id`, 유효기간 3600초다. `sub`는 내부 no 문자열이다. 쿠키는 `ACCESS_TOKEN`, HttpOnly, SameSite=Lax, 로컬 Secure=false다. FastAPI localhost:8001의 검증 구현은 RAG 담당 영역이다.

## 4. 환경변수 규칙

실제 키·DB 계정은 비공개 `.env`에 둔다. `.env`, 실제 비밀값, DB 덤프, 빌드 산출물을 커밋하지 않는다. JWT_SECRET은 프론트에 전달하지 않는다. RAG 담당자에게는 승인된 비공개 경로로 별도 전달해야 함을 사용자에게 알린다. 외부 담당자에게 직접 메시지를 보내지 않는다.

## 5. 빌드 / 형상관리

- 서비스 폴더에서 `./gradlew --no-daemon test bootJar`로 단위/API fixture 테스트와 빌드를 수행한다.
- `scripts/evaluate_auth.py`, `scripts/verify_mariadb.py`는 HTTP·DB 검증 도구이므로 사용자의 연동 검증 범위와 구분한다.
- 커밋은 `./scripts/commit_auth.sh "커밋 메시지"`를 사용한다. 이 스크립트는 auth만 스테이징하고 `git commit --only`로 auth만 커밋한다.
- `git add .`, `git add -A`를 경로 없이 실행하지 않는다. 다른 경로의 스테이징·작업 파일을 건드리지 않는다.
- 커밋 직후 `git diff-tree --no-commit-id --name-only -r HEAD`로 모든 변경이 `services/auth/` 아래인지 확인한다.
- auth 내부 같은 파일을 여러 사람이 수정하면 충돌 가능성은 남는다. 커밋 범위 제한이 같은 파일 충돌까지 막지는 않는다. 푸시는 별도 지시가 있을 때만 수행한다.

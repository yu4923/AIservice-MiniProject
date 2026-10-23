# 로컬 Spring Boot 인증 서버

구현 범위는 `services/auth`의 Spring Boot 서버 하나다. 프론트와 FastAPI는 각 담당자가 직접 연결한다. 기존 `localhost:8001` RAG 서버는 변경하거나 종료하지 않는다.

## 실행 주소와 인증 방식

| 항목 | 값 |
| --- | --- |
| Spring API | `http://localhost:8080` |
| 허용 프론트 Origin | `http://localhost:5174` |
| 개발 DB | 전용 MariaDB, `localhost:53301/sql_db` |
| 쿠키 | `ACCESS_TOKEN`, `Path=/`, `HttpOnly`, `SameSite=Lax`, `Secure=false` |
| JWT | HS256, issuer `simple-auth-server`, 유효기간 1시간 |

로그인과 인증 확인은 JWT 하나만 사용한다. 레거시 `SESSION_ID`와 `APP_AUTH`는 발급·인증에 사용하지 않으며 로그아웃에서 이전 브라우저 쿠키를 정리하기 위해 삭제 헤더만 보낸다. `LegacySessionStore`는 이전 코드 비교용이며 Spring Bean으로 등록하지 않는다.

## 처음 실행할 때

현재 로컬 `.env`에는 전용 개발 DB 계정과 JWT 키가 설정돼 있다. 실제 값은 출력하거나 커밋하지 않는다. 다른 개발자는 `.env.local.example`를 참고해 자기 환경을 준비한다. 기존 `.env`를 덮어쓰지 않는다.

서비스 폴더에서 DB와 Spring Boot를 함께 빌드·실행한다.

```sh
./scripts/start.sh
```

위 명령은 `docker compose --env-file .env up --build --abort-on-container-exit`를 실행한다. DB healthcheck가 통과한 뒤 Spring이 시작한다. Ctrl+C 또는 어느 한 컨테이너의 종료 시 두 컨테이너를 모두 종료한다. Docker 데몬 강제 종료·호스트 장애에 대한 원자적 종료를 보장하는 기능은 아니다.

터미널을 분리해 실행할 때는 아래 명령을 사용한다. 이 모드에서는 한 컨테이너의 종료가 다른 컨테이너의 자동 종료로 이어지지 않는다.

```sh
docker compose --env-file .env up -d --build --wait
```

두 컨테이너를 함께 종료·제거하려면 아래 명령을 사용한다. 기존 데이터 볼륨은 남는다.

```sh
docker compose --env-file .env down
```

Compose 프로젝트 `auth-local`과 볼륨 `auth-local_mariadb_data`는 기존 이름을 유지한다. `down -v`나 볼륨 삭제 명령은 사용하지 않는다. Spring의 컨테이너 내부 DB 주소는 `mariadb:3306`이며 `.env`의 호스트용 `DB_URL`을 덮어쓰지 않는다. 컨테이너 내부에서는 `0.0.0.0:8080`에 바인딩하고, 호스트에는 `127.0.0.1:8080`으로만 공개한다.

이미 호스트의 8080에서 auth를 실행 중이라면 해당 프로세스임을 확인한 뒤 종료해야 한다. 다른 프로그램은 임의 종료하지 않는다. 이미지 빌드 시 JDK 21에서 테스트와 bootJar를 수행하며 Java 소스 대상은 17이다. 실행 이미지는 JRE 21과 비루트 사용자를 사용하고, `.env`는 빌드 컨텍스트에서 제외한다.

Compose는 `SPRING_JPA_HIBERNATE_DDL_AUTO=validate`를 명시한다. 테이블이 없으면 `schema.sql`로 생성하지만 기존 테이블은 변경하지 않는다. 기존 DB 구조와 현재 코드가 다르면 시작에 실패하며, 수동 마이그레이션은 백업·승인 후 별도로 진행한다.

프론트는 POST form(`application/x-www-form-urlencoded`)으로 `id`, `password` 두 필드를 보낸다. API 입력 이름 `password`와 DB 컬럼 이름 `pw`를 구분한다. DB는 `users(no, id, pw)` 세 컬럼이다. `no`는 자동 증가 PK, `id`는 고유 로그인 문자열, `pw`는 BCrypt 해시다. API의 `password`를 DB `pw`에 저장한다. 자세한 요청·응답 구분은 [API 계약](docs/FRONTEND_API.md)을 따른다.

## 실제 요청 흐름

```text
프론트 → POST /api/auth/login → 비밀번호 확인 → JWT 쿠키 발급
프론트 → GET /api/auth/check → JWT 검증 → 사용자 정보 반환
프론트 → POST /api/auth/logout → 브라우저 쿠키 삭제
```

Controller는 HTTP와 쿠키, Service는 가입·비밀번호 검사, Repository는 MariaDB 접근을 맡는다. JWT 서명·만료·필수 claim 검증은 `JwtService`, 요청 쿠키 인증은 `CookieAuthenticationFilter`가 담당한다. 요청 ID와 CORS는 `RequestPolicyFilter`, 공통 JSON 오류는 `ApiExceptionHandler`가 담당한다.

브라우저는 JWT를 JavaScript로 읽지 않는다. 프론트는 모든 인증 요청에 `credentials: "include"`를 넣는다. FastAPI 담당자는 같은 비밀키·알고리즘·issuer와 `exp`, `sub`, `id` 검증을 맞춰야 한다. 키를 프론트의 `VITE_*` 설정에 넣지 않는다.

API 계약과 오류 형식은 [FRONTEND_API](docs/FRONTEND_API.md), 실제 검증 결과는 [VERIFICATION](docs/VERIFICATION.md)를 참고한다. 이전 HttpServer 이관 이력은 [MIGRATION](docs/MIGRATION.md)에 남아 있으며 현재 계약은 이 README와 FRONTEND_API를 우선한다.

## 검증 명령

```sh
./gradlew --no-daemon test bootJar
python3 scripts/evaluate_auth.py
```

첫 명령은 fixture와 H2 기반 테스트다. 두 번째 명령은 실행 중인 8080 서버와 전용 MariaDB에 평가용 계정을 새로 만들어 가입·로그인·쿠키·오류·로그아웃을 확인한다. 기대 결과는 `docs/auth-evaluation-cases.json`, 실제 결과는 `docs/auth-evaluation-results.json`으로 분리한다. 생성한 평가 계정의 비밀번호와 JWT는 보고서에 기록하지 않는다.

## 범위와 제한

- 로컬 HTTP와 기초 보안이 현재 범위다. HTTPS, Refresh Token, 역할 권한, JWT 폐기 목록은 추가하지 않는다.
- 비밀번호는 BCrypt cost 12로 저장한다. id/password의 기존 trim 동작을 유지한다.
- JWT는 응답 본문과 로그에 넣지 않는다. 오류 응답에는 내부 SQL·설정값을 노출하지 않는다.
- `GET /health`는 프로세스 응답이며 DB 준비 완료를 보장하지 않는다.
- DB는 기존 스키마 파일과 JPA `validate`를 사용한다. 기존 테이블을 자동 변경하거나 삭제하지 않는다.
- 프론트 로그인 화면과 FastAPI JWT 검증은 이 폴더에서 구현하지 않는다. 그 담당자가 이 API 계약을 연결해야 한다.

## 기존 DB 전환

현재 계약은 no-id-pw-v2다. 기존 숫자 id는 no, username은 id, password는 pw로 이름을 바꿔 기존 계정과 해시를 보존한다. created_at과 updated_at은 제거한다. 새 가입 응답은 {"ok":true,"no":"7","id":"demo"} 형식이며 로그인 입력은 {"id":"demo","password":"..."}다.

기존 DB는 CREATE TABLE IF NOT EXISTS나 JPA validate로 자동 변경되지 않는다. 백업과 별도 승인 후 docs/sql/migrate-users-no-id-pw.sql을 수동 적용해야 한다. 새 코드·DB·프론트·FastAPI 적용 시점을 맞춘다. JWT sub는 내부 no 문자열, id claim은 로그인 문자열이다. 이전 username claim만 가진 토큰은 재로그인이 필요하다.

docs/auth-evaluation-results.json의 historical=true 결과는 이전 계약의 기록이다. 현재 변경의 검증 상태는 docs/VERIFICATION.md를 따른다. 실제 개발 DB와 실행 중인 서버의 변경은 검증용 임시 DB 기동과 구분한다.

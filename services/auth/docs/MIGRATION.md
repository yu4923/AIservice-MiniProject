> 현재 계약은 no-id-pw-v2: users(no, id, pw), 로그인 입력 id/password, JWT sub=no 및 id claim이다. 아래 username 기반 내용은 과거 이력이다. 현재 API는 FRONTEND_API를 따르며 기존 DB 변경은 docs/sql/migrate-users-no-id-pw.sql의 별도 승인 대상이다.

> 2026-10-23 후속 변경: 현재 인증은 JWT 단독이며 프론트 기본 Origin은 localhost:5174다. 아래 표는 이전 이관 시점의 기록이다. 현재 계약은 README와 FRONTEND_API를 따른다.

# Java HttpServer → Spring Boot 전환 기록

대상은 `services/auth`이며 기준은 `backend`의 `35f6811` 소스다. 기존 사용자 변경 `.env.example`는 유지한다. 원본 소스와 Gradle 구조는 [legacy/java-httpserver](../legacy/java-httpserver)에 보관하며 Spring 빌드 대상에서 제외한다. `.env`, DB 데이터, 빌드 산출물은 보관하지 않는다.

## 근거와 적용 범위

2026-10-23 로컬 브라우저에서 확인한 [Notion 명세](https://app.notion.com/p/REST-API-401f99afd91080a6aa56f38fb398a931)는 설계안 v1.0 · 2026-10-22이며, Java 경로·응답은 골격 코드와 대조하여 확정할 제안이라고 명시한다. 현재 명세의 기본 포트 제안은 Spring `8080`, Vue `5173`, FastAPI `8001`이다. 이전 전달의 Vue `5174`와 레거시 `8008`은 기본 설정에 사용하지 않는다.

사용자 지시의 Spring API-only, Spring Data JPA 저장 계층, HttpOnly JWT, SameSite=Lax, 프론트 직접 호출, 레거시 보안·라우팅 호환을 이번 범위로 한다. Spring 내부 인증 처리 외 별도 미들웨어는 추가하지 않는다. 프론트/RAG/Voice 구현·외부 메시지·commit/push는 범위 밖이다.

## 이전 동작 대비

| 항목 | Java HttpServer 기존 동작 | Spring Boot 결과 |
| --- | --- | --- |
| 서버 구조 | Java 17 `workplace.SimpleAuthServer`, 중첩 서비스/저장소, `./gradlew :app:run` | 단일 Spring Boot 서버, 컨트롤러·서비스·저장 계층 분리, `./gradlew bootRun` |
| 포트 | `8080` 하드코딩 | `SERVER_PORT`, 기본 `8080` |
| 환경설정 | `DB_URL`, `DB_USER`, `DB_PASSWORD`, `JWT_SECRET` 필수 | 동일 변수 유지 + 개발/운영 쿠키·프론트 origin 설정; 비밀값 없는 새 템플릿 |
| 가입 경로/DTO | `POST /api/signup`, form `username,password` | 기존 경로 유지 + `/api/auth/signup` 별칭, JSON/form의 동일 DTO |
| 가입 성공 | `302 /login` | `201` JSON `ok,user_id,username`; 프론트가 화면 이동 |
| 가입 중복·검증 | 중복 `400` 일반 텍스트, 누락 `400` 일반 텍스트 | 중복 `409 USERNAME_EXISTS`, 검증 `400 VALIDATION_ERROR`, 공통 JSON 오류 |
| 로그인 경로/DTO | `POST /api/login`, form `username,password` | 기존 경로 유지 + `/api/auth/login` 별칭, JSON/form의 동일 DTO |
| 로그인 성공 | `200 {ok:true,redirect:"http://localhost:8008/index.html"}` | `200 {ok:true,redirect,expires_in:3600}`; `redirect` 기본 현재 프론트 origin이며 `LOGIN_SUCCESS_URL`로 설정 |
| 로그인 실패 | 누락 `400`, 잘못된 자격증명 `401`; 오류 문자열 | 동일 상태 의미, 공통 JSON 오류 `VALIDATION_ERROR` / `INVALID_CREDENTIALS` |
| trim | 가입·로그인 모두 username/password 양 끝 공백 제거 | 기존 trim 유지. username은 기존 DB 한계인 100자를 검증하며 비밀번호 길이·조합 규칙은 추가하지 않음 |
| 비밀번호 | jBCrypt cost 12, 해시만 저장 | 동일 BCrypt 방식·cost 유지, 응답에 비밀번호·해시 없음 |
| JWT | HS256, issuer `simple-auth-server`, 1시간, sub=사용자 ID 문자열, username claim | 동일 유지, 서명·issuer·exp·sub·username 검증. refresh 없음 |
| `ACCESS_TOKEN` | `Path=/; HttpOnly; SameSite=Lax`, 브라우저 세션 쿠키 | 동일 + 운영 `Secure`. JSON 본문·JS 저장소에 JWT를 반환하지 않음 |
| `SESSION_ID` | 서버 메모리 저장소, TTL 없음, HttpOnly/Lax | 최소 호환을 위해 동일 정책 유지. Spring `JSESSIONID` 인증은 사용하지 않음 |
| `APP_AUTH` | JS가 읽는 `1` 표시용 쿠키 | 동일 힌트 유지, 인증 근거로 사용하지 않음 |
| 인증 확인 | `GET /api/auth/check`; session OR JWT, session 우선 | 동일 정책·via 응답 보존. 두 방법이 모두 없거나 무효이면 `401` JSON |
| 보호 `/home` | session 전용 HTML, 미인증 `302 /login` | 인증 보호 JSON 호환 경로. 유효 session 또는 JWT 허용, 미인증 `401` |
| 로그아웃 | `POST /api/logout`, session 삭제 + 세 쿠키 `Max-Age=0`, `302 /login` | 기존 경로 유지 + `/api/auth/logout` 별칭; 동일 삭제 속성, 멱등 `200 {ok:true}`, 프론트가 화면 이동 |
| 쿠키 삭제 | 발급과 동일 Path/HttpOnly/Lax | 발급과 동일 Path/HttpOnly/Lax/Secure + `Max-Age=0` |
| CORS | `/api/auth/check`만 `http://localhost:8008`, credentials 허용 | auth 경로 전체와 보호 경로에 정확한 `FRONTEND_ORIGIN`, credentials와 preflight 지원 |
| Origin/CSRF | 별도 Origin 검증 없음 | 변경 요청의 허용되지 않은 Origin 거부. Origin 없는 기존 CLI 요청은 허용 |
| 오류 | JSON/일반 텍스트/리다이렉트 혼재, 일부 stack trace | 공통 JSON 오류·request_id, 내부 예외·SQL·비밀을 응답하지 않음 |
| 저장 계층·SQL | 직접 JDBC와 PreparedStatement의 `?` 바인딩 | Spring Data JPA의 파생 조회·저장 메서드, 사용자 입력 매개변수 바인딩 유지 |
| DB 스키마 | 주석의 users DDL을 수동 준비 | 단일 공유 `schema.sql`; `CREATE TABLE IF NOT EXISTS`, Hibernate `ddl-auto=validate`, 자동 변경·삭제 없음 |
| 테스트용 DB | 별도 테스트 없음 | H2는 테스트에만 사용, 실행 JAR의 DB는 MariaDB. 실제 MariaDB 검증을 별도 기록 |
| DB 실행 | 각자 임의 DB 준비 | 공식 고정 이미지 + 별도 Compose 프로젝트·named volume·healthcheck·설정 가능한 호스트 `53301` |
| 화면 리소스 | `/`, `/login`, `/signup`, `/static/*` HTML/CSS/JS 제공 | API-only로 해당 화면 경로 `404` JSON, 이전 리소스는 legacy에 보관 |
| 라우트 매칭 | HttpServer context prefix 매칭 | 명시 경로만 매칭. `/api/login/extra`는 로그인 핸들러로 처리하지 않음 |

## 보존한 인증 정책의 한계

`/api/auth/check`는 기존과 같이 session OR JWT이며 session 우선이다. 따라서 JWT 만료·변조를 거부하는 테스트는 유효한 `SESSION_ID` 없이 수행해야 한다. 유효 세션이 있으면 만료된 JWT를 보내도 전체 요청이 성공할 수 있다. 메모리 세션은 앱 재시작 후 사라지며 여러 서버 인스턴스 간 공유되지 않는다.

로그아웃은 현재 브라우저 쿠키와 해당 서버 세션을 지운다. 이미 복사된 JWT는 기존처럼 1시간 만료 전까지 유효할 수 있다. BCrypt의 72바이트 초과 입력 처리도 기존과 같이 유지한다. 새 비밀번호 길이·조합 규칙, JWT 블랙리스트·refresh·세션 TTL 도입은 인증 정책 변경이므로 이번 전환에서 임의로 추가하지 않는다.

`SameSite=Lax`와 HttpOnly는 유지한다. 개발은 동일한 localhost 호스트의 다른 포트에서 직접 호출하고 운영은 HTTPS+Secure와 호환되는 same-site 배치를 사용한다. 서로 다른 site로 프론트와 API를 배치하려면 별도 쿠키·CSRF 정책 합의가 필요하다. `FRONTEND_ORIGIN`을 와일드카드로 넓히지 않는다.

## 팀에서 확정할 차이

| 명세 제안 또는 다음 요구 | 이번 결과와 남은 결정 |
| --- | --- |
| `/api/auth/signup`의 `email,password,nickname` | 별칭 경로는 제공하지만 현재 저장 모델은 기존 `username,password`다. email 고유성·기존 계정 이관·nickname 컬럼 추가는 별도 DB 변경을 합의해야 한다 |
| 로그인 응답의 `access_token` + Vue의 Bearer 전달 | 사용자 HttpOnly 요구에 따라 JWT를 본문에서 노출하지 않는다. 프론트가 JWT를 읽어 RAG에 전달하는 예제를 제공하지 않으며, RAG의 쿠키 지원/서버 간 전달 정책은 관련 담당과 합의할 사항이다 |
| `/api/users/me`, `PUT /api/users/me/profile` | 현재 로그인 기반 구축 범위에서 구현하지 않았다. 경로 접근 시 인증 처리는 적용하지만 해당 업무 API는 제공하지 않는다 |
| 세션 혼용 해제 | 현재 기존 OR 정책을 보존했다. JWT 단독 정책과 세션 만료 도입 여부를 확정해야 한다 |
| DB 자격증명 | 빈 문자열은 미정 placeholder다. 실제 로컬 사용자·비밀번호·root 초기화 값·JWT 키 생성 또는 영구 설정은 별도 승인 후 결정한다 |
| 운영 배치 | 운영 frontend origin과 HTTPS 주소를 확정하고 `prod`, Secure 쿠키를 사용한다 |

## 검증 기록

최종 build/test 수와 단계별 `PASS / FAIL / NOT RUN` 결과 및 실행 증거는 [VERIFICATION](VERIFICATION.md)에 기록한다. JPA/H2 테스트와 실제 MariaDB 이미지 기동·네트워크 연결·브라우저 credentials 검증은 수행 여부를 구분한다. 실제 서비스 자격증명 설정이나 상시 서버 기동은 테스트와 별도다. 기존 프로세스나 컨테이너를 종료하거나 데이터를 삭제해 검증 환경을 만들지 않는다.

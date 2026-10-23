# Spring 인증 API 연결 계약

현재 계약은 no-id-pw-v2다. Spring은 http://localhost:8080, 허용 프론트 Origin은 http://localhost:5174다. 모든 인증 fetch에 credentials: "include"를 사용한다. 프론트 화면과 FastAPI는 별도 담당자가 연결한다.

## DB와 입력 구분

users 테이블은 no, id, pw 세 컬럼이다. no는 DB 자동 증가 PK, id는 사용자가 가입할 때 정하는 고유 로그인 문자열, pw는 BCrypt cost 12 해시다. API에서는 id와 password를 받으며 pw는 입력·응답 필드가 아니다. 이름·이메일·닉네임은 받지 않는다.

| Method | 경로 | 요청 | 성공 응답 |
| --- | --- | --- | --- |
| POST | /api/auth/signup | POST form: id, password | 201, ok, 문자열 no, id |
| POST | /api/auth/login | POST form: id, password | 200, ok, redirect, expires_in; JWT Set-Cookie |
| GET | /api/auth/check | JWT 쿠키 | 200, ok, via: jwt, 문자열 no, id, sub |
| POST | /api/auth/logout | 본문 불필요 | 200, ok: true; 쿠키 삭제 |
| GET | /health | 없음 | 200, status: UP |

프론트 가입·로그인은 POST와 Content-Type: application/x-www-form-urlencoded를 사용하며 필드 이름은 id, password다. DB 컬럼 pw를 form 필드 이름으로 보내지 않는다. 기존 /api/signup, /api/login, /api/logout 별칭과 JSON 입력도 유지한다. GET /home은 인증 확인 JSON 호환 경로다. 가입은 자동 로그인하지 않는다. id는 trim 후 1~100자, password는 trim 후 비어 있지 않은 문자열이다. JSON 숫자 등을 문자열로 자동 변환하지 않는다. 비밀번호 조합 규칙은 추가하지 않는다. no를 로그인 id로 사용하지 않는다.

가입·로그인 form 요청:

~~~http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

id=demo&password=example-password
~~~

가입은 같은 두 필드를 POST /api/auth/signup으로 보낸다. URLSearchParams를 사용하면 비밀번호의 &, +, =, 공백도 form 규칙에 맞게 인코딩된다.

가입 성공:

~~~json
{"ok":true,"no":"7","id":"demo"}
~~~

로그인 성공:

~~~json
{"ok":true,"redirect":"http://localhost:5174","expires_in":3600}
~~~

redirect는 이동 힌트이며 프론트 라우터가 이동한다. 토큰은 본문에 넣지 않는다. no와 sub는 큰 번호의 JavaScript 정밀도 손실을 막기 위해 문자열로 전달한다.

## JWT와 쿠키

ACCESS_TOKEN은 Path=/; HttpOnly; SameSite=Lax 쿠키이며 로컬 HTTP에서는 Secure=false다. SESSION_ID와 APP_AUTH는 인증에 사용하지 않으며 로그아웃에서 잔여 쿠키 삭제만 한다. JavaScript로 토큰을 읽거나 localStorage에 저장하지 않는다.

JWT는 HS256, issuer simple-auth-server, 유효기간 1시간이다. 서명·issuer·exp·sub·id를 검증한다. sub는 양의 signed 64-bit 내부 no 문자열이며 id는 비어 있지 않은 로그인 문자열이다. username claim은 발급·요구하지 않는다. 이전 username claim만 있는 JWT는 재로그인이 필요하다. FastAPI도 동일한 비밀키와 검증 기준으로 변경해야 한다. 키는 VITE_*·Git·메신저·문서에 넣지 않는다.

Refresh Token과 JWT 폐기 목록은 없다. 로그아웃은 브라우저 쿠키를 삭제하며 복사한 JWT는 만료 전까지 유효할 수 있다.

## 오류와 화면 처리

~~~json
{"ok":false,"error":{"code":"INVALID_CREDENTIALS","message":"invalid credentials","details":[]},"request_id":"요청 ID"}
~~~

| 상태 | 대표 코드 | 프론트 처리 |
| --- | --- | --- |
| 400 | VALIDATION_ERROR, INVALID_REQUEST | 입력 형식 수정 |
| 401 | INVALID_CREDENTIALS | 로그인 실패 안내 |
| 401 | UNAUTHORIZED | 보호 요청이면 재로그인 안내 |
| 403 | ORIGIN_NOT_ALLOWED, CORS_NOT_ALLOWED | Origin·사전 요청 확인 |
| 409 | ID_EXISTS | 중복 로그인 아이디 안내 |
| 500 | INTERNAL_ERROR | 일반 오류와 문의 ID 표시 |
| 503 | DATABASE_UNAVAILABLE | DB 오류 안내, 토큰 만료와 구분 |

새로고침 시 /api/auth/check로 상태를 확인한다. 로그인 실패의 401과 보호 API의 401을 구분한다. 응답 request_id 또는 X-Request-Id로 문의하며 비밀번호·쿠키를 공유하지 않는다.

~~~js
await fetch('http://localhost:8080/api/auth/login', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ id, password }),
});
~~~

기존 DB 마이그레이션·서버 재시작·프론트·FastAPI 연동은 별도 적용 대상이다. GET /health는 DB 준비 완료를 보장하지 않는다.

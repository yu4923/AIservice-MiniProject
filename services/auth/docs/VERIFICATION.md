# no·id·pw 변경 검증

현재 계약은 no-id-pw-v2이며 users에는 no·id·pw만 둔다. API 입력은 id·password다.

- Gradle 테스트 및 bootJar: PASS. 임시 복사본에서 49개 테스트, 실패 0개, 오류 0개. 실행 JAR 생성 성공. 원본 services/auth에서도 bootJar를 실행해 BUILD SUCCESSFUL을 확인했다.
- 임시 MariaDB의 신규 스키마·기존 계정 이관·API 검증: PASS. MariaDB 11.4.13, 25개 검사 통과. 생성한 임시 서버·컨테이너는 정리했다.
- Python 스크립트 문법: PASS. 두 스크립트 전체를 ast.parse로 검사했다.
- 기존 개발 DB 적용: 초기 전환 검증 당시 NOT_RUN. 이후 사용자 승인으로 백업 후 기존 계정 4개를 초기화하고 새 users(no, id, pw)를 생성했다. 데이터 보존 마이그레이션은 실행하지 않았다.
- 기존 8080 서버 전환: PASS. 해당 auth 작업 폴더에서 실행 중임을 확인한 뒤 호스트 서버를 종료하고 Compose의 Spring으로 교체했다.
- 프론트·FastAPI 연결: NOT_RUN.

docs/auth-evaluation-results.json은 historical=true인 이전 계약 기록이다. scripts/evaluate_auth.py는 실제 개발 DB에 새 계정을 만들므로 이번 검증에서는 실행하지 않는다.

## 기존 DB 적용과 복구

docs/sql/migrate-users-no-id-pw.sql은 자동 실행 경로 밖에 있다. 기존 id→no, username→id, password→pw로 값은 보존하며 created_at과 updated_at은 삭제한다. DDL은 일반 트랜잭션 ROLLBACK으로 복구할 수 없으므로 실행 전 전체 백업과 승인이 필요하다. 새 코드와 기존 스키마는 호환되지 않아 DB·서버·클라이언트 전환 시점을 맞춘다. 이전 JWT의 username claim을 id로 바꿨으므로 재로그인이 필요하다.

변경 전 소스는 작업 백업 폴더의 before에 보관한다. 기존 미커밋 변경이 있으므로 git reset이나 git checkout으로 일괄 복구하지 않는다. 위 초기 검증 단계에서는 실제 개발 DB를 변경하지 않았다. 이후 승인한 초기화와 현재 복구 기준은 아래 Compose 적용 기록을 따른다.

~~~sh
./gradlew --offline --no-daemon test bootJar
python3 scripts/verify_mariadb.py
~~~

첫 테스트 실행에서는 H2 시스템 스키마 USERS까지 조회해 컬럼 검사가 1건 실패했다. 테스트 쿼리를 PUBLIC 스키마로 제한한 뒤 전체 테스트를 다시 실행해 통과했다. MariaDB 검증은 기존 DB를 사용하지 않고 새 컨테이너에서만 수행했다.

## 바뀐 파일

- src/main/java/workplace/auth/domain/User.java: no와 문자열 id를 분리하는 사용자 모델
- src/main/java/workplace/auth/domain/AuthIdentity.java: no와 문자열 id를 분리하는 사용자 모델
- src/main/java/workplace/auth/repository/UserEntity.java: no PK 및 로그인 id 조회와 pw 해시 매핑
- src/main/java/workplace/auth/repository/UserRepository.java: no PK 및 로그인 id 조회와 pw 해시 매핑
- src/main/java/workplace/auth/repository/JpaUserStore.java: no PK 및 로그인 id 조회와 pw 해시 매핑
- src/main/java/workplace/auth/repository/JpaUserRepository.java: no PK 및 로그인 id 조회와 pw 해시 매핑
- src/main/java/workplace/auth/service/AuthService.java: id/password 인증과 ID_EXISTS 중복 처리
- src/main/java/workplace/auth/web/AuthController.java: 가입·인증 응답을 no/id로 변경
- src/main/java/workplace/auth/security/JwtService.java: JWT sub=no 및 id claim과 내부 모델 반영
- src/main/java/workplace/auth/security/LegacySessionStore.java: JWT sub=no 및 id claim과 내부 모델 반영
- src/main/resources/db/schema.sql: users를 no/id/pw 세 컬럼으로 정의
- src/test/resources/test-schema.sql: 새 스키마와 인증 계약 회귀 검증
- docs/sql/migrate-users-no-id-pw.sql: 기존 계정 보존과 시각 컬럼 삭제용 수동 SQL, 미실행
- src/test/java/workplace/auth/service/AuthServiceTest.java: 새 스키마와 인증 계약 회귀 검증
- src/test/java/workplace/auth/repository/JpaUserRepositoryTest.java: 새 스키마와 인증 계약 회귀 검증
- src/test/java/workplace/auth/security/JwtServiceTest.java: 새 스키마와 인증 계약 회귀 검증
- src/test/java/workplace/auth/AuthApiTest.java: 새 스키마와 인증 계약 회귀 검증
- scripts/evaluate_auth.py: 새 API·DB 계약 평가 및 임시 MariaDB 이관 검증
- scripts/verify_mariadb.py: 새 API·DB 계약 평가 및 임시 MariaDB 이관 검증
- README.md: 새 계약·적용 경계·검증 및 복구 문서
- docs/FRONTEND_API.md: 새 계약·적용 경계·검증 및 복구 문서
- docs/MIGRATION.md: 새 계약·적용 경계·검증 및 복구 문서
- docs/auth-evaluation-cases.json: 새 계약·적용 경계·검증 및 복구 문서
- docs/auth-evaluation-results.json: 기존 결과를 과거 계약으로 명시
- docs/VERIFICATION.md: 새 계약·적용 경계·검증 및 복구 문서

소스 백업 위치: /private/tmp/auth-no-id-pw-fvt_ujbt/before


## 2026-10-23 실제 Compose 적용

- 사용자 승인: 기존 auth DB를 초기화해도 된다는 지시를 받은 뒤 실행했다.
- 초기화 전 sql_db 전체 논리 백업: `.backups/auth-before-compose-reset-20261023-111829.sql`. 디렉터리 권한 700, 덤프 권한 600이며 `.gitignore`와 Docker 빌드 컨텍스트에서 제외한다. 덤프 내용은 출력하지 않았다.
- 기존 users의 계정 4개를 삭제하고 현재 schema.sql로 no/id/pw 세 컬럼을 생성했다. 다른 테이블·DB·기존 볼륨·자격증명은 변경하지 않았다. 적용 직후 계정 수는 0개다.
- auth-local-mariadb-1: healthy, 호스트 127.0.0.1:53301. auth-local-springboot-1: healthy, 호스트 127.0.0.1:8080. DB 볼륨은 기존 auth-local_mariadb_data를 유지했다.
- Spring은 컨테이너 내부 mariadb:3306에 접속하며 `SPRING_JPA_HIBERNATE_DDL_AUTO=validate`를 사용한다. 호스트 application.yaml의 update 설정과 구분한다.
- 현재 소스로 이미지 빌드: PASS. 동일 입력의 테스트·bootJar 성공 레이어를 캐시로 재사용했다. 앞선 이미지 빌드에서 실제 테스트와 bootJar가 통과했다.
- 실제 서버 확인: GET /health 200 UP, 미인증 /api/auth/check 401, 없는 계정의 form 로그인 401. request_id 일치와 localhost:5174 CORS도 확인했다. 실제 DB에 평가용 계정은 만들지 않았다.
- 분리된 임시 Compose 검증: 11개 PASS. 가입·로그인·JWT 쿠키, 양방향 동반 종료, stop/start와 down/up 후 계정·해시 보존, 비루트 실행을 확인했다. 임시 컨테이너와 해당 테스트 볼륨만 정리했다.
- 현재 실행은 scripts/start.sh의 foreground Compose를 백그라운드 감독 프로세스로 유지한다. `.logs/compose.log`에 출력하고 `.logs/compose.pid`에 PID를 기록한다. `--abort-on-container-exit`로 한 컨테이너가 종료되면 다른 컨테이너도 종료한다. detached `up -d` 자체에는 이 동반 종료 보장이 없다.
- 다시 실행: `./scripts/start.sh`. 전체 종료: `docker compose --env-file .env down`. down은 기존 DB 볼륨을 보존하며 `-v`를 사용하지 않는다.
- 최초 재생성 직후 확인 쿼리는 따옴표 오류로 실패했다. SQL을 표준 입력으로 전달하도록 수정해 no/id/pw와 계정 0개를 확인했으며 테이블 삭제는 반복하지 않았다.
- 미검증: 프론트·FastAPI 실제 연동, 백업의 실제 복원, 호스트·Docker 데몬 장애 시 동작. 프론트·RAG 연동은 담당자 검증 범위다.

### 초기화 이전 상태로 복구할 때

전체 중단 후 DB만 실행하고 비공개 SQL 백업을 mariadb 클라이언트의 표준 입력으로 복원한다. 이 백업은 이전 id/username/password/created_at/updated_at 구조이므로 현재 코드와 호환되지 않는다. 백업 복원 시 해당 이전 구조를 사용하는 auth 코드도 함께 복구해야 하며, 현재 코드에 그대로 연결하면 validate가 시작을 거부한다. 실제 복원은 수행하지 않았다. 볼륨 삭제나 Git 일괄 초기화는 사용하지 않는다.

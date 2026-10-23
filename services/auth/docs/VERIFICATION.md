# no·id·pw 변경 검증

현재 계약은 no-id-pw-v2이며 users에는 no·id·pw만 둔다. API 입력은 id·password다.

- Gradle 테스트 및 bootJar: PASS. 임시 복사본에서 49개 테스트, 실패 0개, 오류 0개. 실행 JAR 생성 성공. 원본 services/auth에서도 bootJar를 실행해 BUILD SUCCESSFUL을 확인했다.
- 임시 MariaDB의 신규 스키마·기존 계정 이관·API 검증: PASS. MariaDB 11.4.13, 25개 검사 통과. 생성한 임시 서버·컨테이너는 정리했다.
- Python 스크립트 문법: PASS. 두 스크립트 전체를 ast.parse로 검사했다.
- 기존 개발 DB 마이그레이션과 백업: NOT_RUN. 별도 승인 필요. 읽기 전용으로 auth-local-mariadb-1의 sql_db.users를 확인했고 기존 5개 컬럼과 uk_users_username 인덱스, 계정 4개가 있다. 실제 계정 값·해시는 조회하거나 출력하지 않았다.
- 기존 8080 서버 재시작: NOT_RUN.
- 프론트·FastAPI 연결: NOT_RUN.

docs/auth-evaluation-results.json은 historical=true인 이전 계약 기록이다. scripts/evaluate_auth.py는 실제 개발 DB에 새 계정을 만들므로 이번 검증에서는 실행하지 않는다.

## 기존 DB 적용과 복구

docs/sql/migrate-users-no-id-pw.sql은 자동 실행 경로 밖에 있다. 기존 id→no, username→id, password→pw로 값은 보존하며 created_at과 updated_at은 삭제한다. DDL은 일반 트랜잭션 ROLLBACK으로 복구할 수 없으므로 실행 전 전체 백업과 승인이 필요하다. 새 코드와 기존 스키마는 호환되지 않아 DB·서버·클라이언트 전환 시점을 맞춘다. 이전 JWT의 username claim을 id로 바꿨으므로 재로그인이 필요하다.

변경 전 소스는 작업 백업 폴더의 before에 보관한다. 기존 미커밋 변경이 있으므로 git reset이나 git checkout으로 일괄 복구하지 않는다. 실제 개발 DB는 변경하지 않는다. 향후 DB 적용 뒤에는 삭제 전 백업으로 복원한다.

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

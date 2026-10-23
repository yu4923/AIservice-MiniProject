# Java HttpServer 원본 보관

전환 전 `backend` 브랜치 `35f6811`의 auth 소스와 Gradle 구조를 보관한다. Spring Boot의 소스·리소스·빌드 대상에는 포함하지 않는다.

`app/src/main/java/workplace/SimpleAuthServer.java`가 기존 진입점이며, 기존 실행 명령은 이 디렉터리에서 `./gradlew :app:run --no-configuration-cache`였다. 기존 서버는 8080 고정 포트와 `DB_URL`, `DB_USER`, `DB_PASSWORD`, `JWT_SECRET` 환경변수를 사용한다. 원본 안의 종료·삭제 예시는 과거 주석으로 보관한 것이며 실행 절차가 아니다. 기존 프로세스·컨테이너·데이터를 정리하기 위해 이 주석을 실행하지 않는다.

실제 `.env`, 자격증명, DB 데이터, `.gradle` 캐시, `build`·`target` 산출물은 보관 대상에서 제외했다. Gradle wrapper JAR는 버전 관리되는 실행 도구이므로 원본 구조와 함께 보관했다. 사용자 수정 `.env.example`는 원래 서비스 루트에 그대로 남긴다.

새 서버 실행은 서비스 루트의 [README](../../README.md)를 따른다. 동작 비교는 [MIGRATION](../../docs/MIGRATION.md)을 참고한다.

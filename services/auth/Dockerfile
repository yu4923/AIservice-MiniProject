FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /workspace
COPY gradlew settings.gradle build.gradle gradle.properties ./
COPY gradle/ gradle/
RUN chmod +x gradlew
COPY src/ src/
RUN --mount=type=cache,target=/root/.gradle ./gradlew --no-daemon test bootJar

FROM eclipse-temurin:21-jre-alpine AS runtime
WORKDIR /app
COPY --from=build --chown=10001:10001 /workspace/build/libs/auth-service-*.jar app.jar
# JWT_code: 비관리자 프로세스가 전용 인증 로그를 기록할 수 있게 한다.
RUN mkdir -p /app/jwt_log && chown 10001:10001 /app/jwt_log && chmod 700 /app/jwt_log
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

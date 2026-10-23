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
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

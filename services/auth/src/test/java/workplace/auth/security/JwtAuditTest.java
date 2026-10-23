package workplace.auth.security;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import jakarta.servlet.http.Cookie;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import workplace.auth.domain.User;
import static org.assertj.core.api.Assertions.assertThat;

/** JWT_code: 실제 필터의 성공·실패 로그와 민감정보 제외를 검증한다. */
class JwtAuditTest {
    private static final String KEY = "audit-public-fixture-only-not-for-deployment";
    private final JwtService jwt = new JwtService(KEY, "simple-auth-server");
    private final Logger logger = (Logger) LoggerFactory.getLogger("workplace.auth.jwt");
    private ListAppender<ILoggingEvent> appender;

    @BeforeEach void capture() {
        appender = new ListAppender<>();
        appender.start();
        logger.addAppender(appender);
    }

    @AfterEach void cleanup() {
        logger.detachAppender(appender);
        appender.stop();
        SecurityContextHolder.clearContext();
    }

    private MockHttpServletRequest request(String route) {
        var request = new MockHttpServletRequest("GET", route);
        request.setAttribute("request_id", UUID.randomUUID().toString());
        return request;
    }

    private void filter(MockHttpServletRequest request, String token) throws Exception {
        if (token != null) request.setCookies(new Cookie("ACCESS_TOKEN", token));
        new CookieAuthenticationFilter(jwt).doFilter(request, new MockHttpServletResponse(), (req, res) -> { });
    }

    @Test void acceptedLogCorrelatesWithoutIdentityOrToken() throws Exception {
        var request = request("/api/auth/check");
        String token = jwt.create(new User(7, "private-login-name", "private-password-hash"));
        filter(request, token);
        assertThat(appender.list).hasSize(1);
        assertThat(appender.list.get(0).getFormattedMessage())
                .contains("\"result\":\"accepted\"", "\"reason\":\"valid\"", request.getAttribute("request_id").toString())
                .doesNotContain(token, KEY, "private-login-name", "private-password-hash");
    }

    @Test void expiredLogKeepsFailureReason() throws Exception {
        String token = JWT.create().withIssuer("simple-auth-server").withSubject("7").withClaim("id", "fixture")
                .withExpiresAt(Instant.now().minusSeconds(30)).sign(Algorithm.HMAC256(KEY));
        filter(request("/api/auth/check"), token);
        assertThat(appender.list.get(0).getFormattedMessage()).contains("\"reason\":\"expired\"", "\"auth_status\":401");
    }

    @Test void signatureFailureIsDistinctFromMalformedToken() throws Exception {
        String token = JWT.create().withIssuer("simple-auth-server").withSubject("7").withClaim("id", "fixture")
                .withExpiresAt(Instant.now().plusSeconds(60)).sign(Algorithm.HMAC256("different-public-key"));
        filter(request("/api/auth/check"), token);
        filter(request("/api/auth/check"), "private-invalid-token");
        assertThat(appender.list.get(0).getFormattedMessage()).contains("invalid_signature");
        assertThat(appender.list.get(1).getFormattedMessage()).contains("invalid_token").doesNotContain("private-invalid-token");
    }

    @Test void missingCookieOnProtectedPathIsRecorded() throws Exception {
        filter(request("/api/auth/check"), null);
        assertThat(appender.list.get(0).getFormattedMessage()).contains("missing_cookie");
    }

    @Test void publicAndHealthRequestsDoNotGenerateMissingCookieNoise() throws Exception {
        for (String route : new String[]{"/health", "/api/login", "/api/signup", "/api/logout"}) filter(request(route), null);
        assertThat(appender.list).isEmpty();
    }

    @Test void arbitraryRequestValuesCannotEnterLogs() {
        var request = request("/api/private-path-secret");
        request.setAttribute("request_id", "private-id\nforged-log");
        request.setQueryString("password=private-password");
        request.addHeader("Authorization", "Bearer private-token");
        JwtAudit.record(request, "jwt_auth", "rejected", "missing_cookie", 401);
        assertThat(appender.list.get(0).getFormattedMessage())
                .contains("\"request_id\":\"-\"", "\"path\":\"[other]\"")
                .doesNotContain("private-", "forged-log");
    }
}

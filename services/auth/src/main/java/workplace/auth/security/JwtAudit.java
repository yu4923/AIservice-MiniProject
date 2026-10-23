package workplace.auth.security;

import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** JWT_code: 사용자 정보 없이 발급·검증 결과와 요청 ID를 기록한다. */
public final class JwtAudit {
    private static final Logger LOG = LoggerFactory.getLogger("workplace.auth.jwt");
    private static final Set<String> ROUTES = Set.of(
            "/api/login", "/api/auth/login", "/api/logout", "/api/auth/logout",
            "/api/auth/check", "/home");
    private static final Set<String> METHODS = Set.of("GET", "POST", "OPTIONS");

    private JwtAudit() { }

    /** JWT_code: URL·헤더의 임의 값이 로그에 섞이지 않도록 허용한 값만 사용한다. */
    public static void record(HttpServletRequest request, String event, String result,
                              String reason, int status) {
        String requestId = "-";
        try {
            requestId = UUID.fromString(String.valueOf(request.getAttribute("request_id"))).toString();
        } catch (IllegalArgumentException ignored) {
            // JWT_code: 요청 ID가 없을 때 원래 입력을 출력하지 않는다.
        }
        String path = ROUTES.contains(request.getRequestURI()) ? request.getRequestURI() : "[other]";
        String method = METHODS.contains(request.getMethod()) ? request.getMethod() : "OTHER";
        // JWT_code: auth_status는 인증 판정이며 이후 업무 처리의 최종 HTTP 상태와 다를 수 있다.
        LOG.info("{\"timestamp\":\"{}\",\"service\":\"auth\",\"event\":\"{}\","
                        + "\"result\":\"{}\",\"reason\":\"{}\",\"auth_status\":{},"
                        + "\"request_id\":\"{}\",\"method\":\"{}\",\"path\":\"{}\"}",
                Instant.now(), event, result, reason, status, requestId, method, path);
    }
}

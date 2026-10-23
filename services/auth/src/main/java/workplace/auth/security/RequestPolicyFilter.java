package workplace.auth.security;

import java.io.IOException;
import java.util.Set;
import java.util.UUID;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

/** Direct browser API access: exact origin, credentials, and origin checks for unsafe requests. */
public class RequestPolicyFilter extends OncePerRequestFilter {
    private static final Set<String> METHODS = Set.of("GET", "POST", "OPTIONS");
    private final String frontendOrigin;
    private final ApiResponseWriter writer;

    public RequestPolicyFilter(String frontendOrigin, ApiResponseWriter writer) {
        this.frontendOrigin = frontendOrigin;
        this.writer = writer;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String requestId = UUID.randomUUID().toString();
        request.setAttribute("request_id", requestId);
        response.setHeader("X-Request-Id", requestId);
        response.setHeader("Cache-Control", "no-store");
        response.addHeader("Vary", "Origin");
        response.addHeader("Vary", "Access-Control-Request-Method");
        response.addHeader("Vary", "Access-Control-Request-Headers");
        String origin = request.getHeader("Origin");
        boolean preflight = "OPTIONS".equals(request.getMethod()) && origin != null
                && request.getHeader("Access-Control-Request-Method") != null;
        String ownOrigin = request.getScheme() + "://" + request.getServerName();
        int port = request.getServerPort();
        if (!(request.isSecure() && port == 443) && !(!request.isSecure() && port == 80)) ownOrigin += ":" + port;
        if (origin != null && !origin.equals(frontendOrigin) && !origin.equals(ownOrigin)) {
            writer.error(request, response, 403, "ORIGIN_NOT_ALLOWED", "Origin is not allowed");
            return;
        }
        if (frontendOrigin.equals(origin)) {
            response.setHeader("Access-Control-Allow-Origin", origin);
            response.setHeader("Access-Control-Allow-Credentials", "true");
            response.setHeader("Access-Control-Expose-Headers", "X-Request-Id");
        }
        if (preflight) {
            String method = request.getHeader("Access-Control-Request-Method");
            String headers = request.getHeader("Access-Control-Request-Headers");
            if (!METHODS.contains(method) || (headers != null && !java.util.Arrays.stream(headers.split(","))
                    .allMatch(h -> "content-type".equalsIgnoreCase(h.trim())))) {
                writer.error(request, response, 403, "CORS_NOT_ALLOWED", "CORS request is not allowed");
                return;
            }
            response.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
            response.setHeader("Access-Control-Allow-Headers", "Content-Type");
            response.setStatus(204);
            return;
        }
        chain.doFilter(request, response);
    }
}

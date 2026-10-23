package workplace.auth.security;

import java.io.IOException;
import java.util.List;
import java.util.Set;
import com.auth0.jwt.exceptions.TokenExpiredException;
import com.auth0.jwt.exceptions.SignatureVerificationException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;
import workplace.auth.domain.AuthIdentity;

/** Spring과 FastAPI가 동일하게 ACCESS_TOKEN 하나로 인증하도록 처리한다. */
public class CookieAuthenticationFilter extends OncePerRequestFilter {
    private final JwtService jwt;
    // JWT_code: 공개 경로의 쿠키 부재와 주기적인 health 확인은 인증 실패로 세지 않는다.
    private static final Set<String> PUBLIC = Set.of("/api/login", "/api/auth/login",
            "/api/signup", "/api/auth/signup", "/api/logout", "/api/auth/logout", "/error");

    public CookieAuthenticationFilter(JwtService jwt) {
        this.jwt = jwt;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String token = AuthCookies.read(request, "ACCESS_TOKEN");
        if (token != null && !token.isBlank()) {
            try {
                AuthIdentity identity = jwt.verify(token);
                SecurityContextHolder.getContext().setAuthentication(
                        new UsernamePasswordAuthenticationToken(identity, null, List.of()));
                JwtAudit.record(request, "jwt_auth", "accepted", "valid", 200);
            } catch (com.auth0.jwt.exceptions.JWTVerificationException | IllegalArgumentException ex) {
                // JWT_code: 예외 메시지 대신 고정된 분류만 남겨 토큰·설정 유출을 막는다.
                String reason = ex.getCause() instanceof TokenExpiredException ? "expired"
                        : ex.getCause() instanceof SignatureVerificationException ? "invalid_signature" : "invalid_token";
                JwtAudit.record(request, "jwt_auth", "rejected", reason, 401);
            }
        } else if (!"OPTIONS".equals(request.getMethod()) && !PUBLIC.contains(request.getRequestURI())
                && (request.getRequestURI().startsWith("/api/") || "/home".equals(request.getRequestURI()))) {
            JwtAudit.record(request, "jwt_auth", "rejected", "missing_cookie", 401);
        }
        chain.doFilter(request, response);
    }
}

package workplace.auth.security;

import java.io.IOException;
import java.util.List;
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
            } catch (com.auth0.jwt.exceptions.JWTVerificationException | IllegalArgumentException ignored) {
                // 토큰 원문은 기록하지 않고 보호 경로의 공통 401 응답으로 연결한다.
            }
        }
        chain.doFilter(request, response);
    }
}

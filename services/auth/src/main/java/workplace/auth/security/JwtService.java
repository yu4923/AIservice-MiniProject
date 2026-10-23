package workplace.auth.security;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import workplace.auth.domain.AuthIdentity;
import workplace.auth.domain.User;

/** 내부 번호를 sub, 로그인 아이디를 id claim에 담아 JWT를 발급·검증한다. */
@Service
public class JwtService {
    public static final long TTL_SECONDS = 3600;

    private final Algorithm algorithm;
    private final JWTVerifier verifier;
    private final String issuer;

    public JwtService(@Value("${auth.jwt-secret}") String secret,
                      @Value("${auth.jwt-issuer}") String issuer) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException("JWT signing configuration is required");
        }
        if (issuer == null || issuer.isBlank()) {
            throw new IllegalStateException("JWT issuer configuration is required");
        }
        this.issuer = issuer;
        this.algorithm = Algorithm.HMAC256(secret);
        this.verifier = JWT.require(algorithm)
                .withIssuer(issuer)
                .withClaimPresence("exp")
                .withClaimPresence("sub")
                .withClaimPresence("id")
                .build();
    }

    public String create(User user) {
        Instant now = Instant.now();
        return JWT.create()
                .withIssuer(issuer)
                .withIssuedAt(now)
                .withExpiresAt(now.plusSeconds(TTL_SECONDS))
                .withSubject(Long.toString(user.no()))
                .withClaim("id", user.id())
                .sign(algorithm);
    }

    public AuthIdentity verify(String token) {
        try {
            if (token == null || token.isBlank()) {
                throw new JWTVerificationException("Invalid access token");
            }
            DecodedJWT decoded = verifier.verify(token);
            String subject = decoded.getSubject();
            String id = decoded.getClaim("id").asString();
            if (subject == null || !subject.matches("[1-9][0-9]{0,18}")
                    || id == null || id.isBlank()) {
                throw new JWTVerificationException("Invalid access token");
            }
            long no = Long.parseLong(subject);
            return new AuthIdentity(no, id, "jwt");
        } catch (JWTVerificationException | IllegalArgumentException ex) {
            // Keep token contents and signing configuration out of exception messages.
            // JWT_code: 원인은 만료·서명 실패 분류에만 쓰고 예외 원문은 로그에 남기지 않는다.
            throw new JWTVerificationException("Invalid access token", ex);
        }
    }
}

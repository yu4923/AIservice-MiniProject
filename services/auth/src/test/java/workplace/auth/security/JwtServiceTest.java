package workplace.auth.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTCreator;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import workplace.auth.domain.AuthIdentity;
import workplace.auth.domain.User;

class JwtServiceTest {
    private static final String SECRET = "unit-test-only-signing-fixture-do-not-use";
    private static final String ISSUER = "simple-auth-server";
    private final JwtService service = new JwtService(SECRET, ISSUER);

    @Test
    void issuesOneHourHs256TokenWithNoAndLoginId() {
        String token = service.create(new User(7, "test-user", "unused-test-hash"));
        var decoded = JWT.decode(token);
        assertThat(decoded.getAlgorithm()).isEqualTo("HS256");
        assertThat(decoded.getIssuer()).isEqualTo(ISSUER);
        assertThat(decoded.getSubject()).isEqualTo("7");
        assertThat(decoded.getClaim("id").asString()).isEqualTo("test-user");
        assertThat(decoded.getClaim("username").isMissing()).isTrue();
        assertThat(decoded.getExpiresAtAsInstant().getEpochSecond()
                - decoded.getIssuedAtAsInstant().getEpochSecond()).isEqualTo(3600);
        assertThat(service.verify(token)).isEqualTo(new AuthIdentity(7, "test-user", "jwt"));
    }

    @Test
    void rejectsChangedSignature() {
        String token = service.create(new User(7, "test-user", "unused-test-hash"));
        int signatureStart = token.lastIndexOf('.') + 1;
        char replacement = token.charAt(signatureStart) == 'A' ? 'B' : 'A';
        String changed = token.substring(0, signatureStart) + replacement + token.substring(signatureStart + 1);
        assertRejected(changed);
    }

    @Test
    void rejectsExpiredToken() {
        assertRejected(base().withExpiresAt(Instant.now().minusSeconds(30)).sign(Algorithm.HMAC256(SECRET)));
    }

    @Test
    void rejectsWrongIssuerAndAlgorithmAndKey() {
        assertRejected(base().withIssuer("other-issuer").sign(Algorithm.HMAC256(SECRET)));
        assertRejected(base().sign(Algorithm.HMAC512(SECRET)));
        assertRejected(base().sign(Algorithm.HMAC256("other-unit-test-key")));
    }

    @Test
    void rejectsMissingRequiredClaims() {
        assertRejected(JWT.create().withSubject("7").withClaim("id", "test-user")
                .withExpiresAt(Instant.now().plusSeconds(60)).sign(Algorithm.HMAC256(SECRET)));
        assertRejected(JWT.create().withIssuer(ISSUER).withSubject("7").withClaim("id", "test-user")
                .sign(Algorithm.HMAC256(SECRET)));
        assertRejected(JWT.create().withIssuer(ISSUER).withClaim("id", "test-user")
                .withExpiresAt(Instant.now().plusSeconds(60)).sign(Algorithm.HMAC256(SECRET)));
        assertRejected(JWT.create().withIssuer(ISSUER).withSubject("7")
                .withExpiresAt(Instant.now().plusSeconds(60)).sign(Algorithm.HMAC256(SECRET)));
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "-1", "abc", "9223372036854775808", "01", "+1"})
    void rejectsInvalidSubject(String subject) {
        assertRejected(base().withSubject(subject).sign(Algorithm.HMAC256(SECRET)));
    }

    @Test
    void rejectsWrongTypeOrBlankLoginId() {
        assertRejected(base().withClaim("id", 123).sign(Algorithm.HMAC256(SECRET)));
        assertRejected(base().withClaim("id", " ").sign(Algorithm.HMAC256(SECRET)));
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {" ", "invalid.jwt", "a.b.c"})
    void rejectsMalformedToken(String token) {
        assertRejected(token);
    }

    @Test
    void rejectsMissingConfigurationWithoutEchoingValues() {
        assertThatThrownBy(() -> new JwtService(" ", ISSUER))
                .isInstanceOf(IllegalStateException.class).hasMessage("JWT signing configuration is required");
        assertThatThrownBy(() -> new JwtService(SECRET, ""))
                .isInstanceOf(IllegalStateException.class).hasMessage("JWT issuer configuration is required");
    }

    private JWTCreator.Builder base() {
        return JWT.create().withIssuer(ISSUER).withSubject("7").withClaim("id", "test-user")
                .withExpiresAt(Instant.now().plusSeconds(60));
    }

    private void assertRejected(String token) {
        assertThatThrownBy(() -> service.verify(token)).isInstanceOf(JWTVerificationException.class)
                .hasMessage("Invalid access token");
    }
}

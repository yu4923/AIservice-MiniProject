package workplace.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.sql.SQLException;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mindrot.jbcrypt.BCrypt;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import workplace.auth.domain.User;
import workplace.auth.repository.UserRepository;
import workplace.auth.web.ApiException;

class AuthServiceTest {
    private final UserRepository users = mock(UserRepository.class);
    private final AuthService service = new AuthService(users);

    @Test
    void signupTrimsLegacyInputAndStoresOnlyBcryptCostTwelveHash() {
        when(users.findByLoginId("fixture")).thenReturn(Optional.empty());
        when(users.save(eq("fixture"), anyString())).thenAnswer(invocation ->
                new User(1, invocation.getArgument(0), invocation.getArgument(1)));

        User user = service.signup(" fixture ", " fixture-password ");

        var hash = ArgumentCaptor.forClass(String.class);
        verify(users).save(eq("fixture"), hash.capture());
        assertThat(hash.getValue()).startsWith("$2a$12$").isNotEqualTo("fixture-password");
        assertThat(BCrypt.checkpw("fixture-password", hash.getValue())).isTrue();
        assertThat(user.id()).isEqualTo("fixture");
        assertThat(user.no()).isEqualTo(1);
        assertThat(user.toString()).doesNotContain(hash.getValue(), "fixture-password");
    }

    @Test
    void loginAcceptsExistingLegacyBcryptHashAndTrimsBothInputs() {
        User user = new User(4, "fixture", BCrypt.hashpw("fixture-password", BCrypt.gensalt(4)));
        when(users.findByLoginId("fixture")).thenReturn(Optional.of(user));

        assertThat(service.login(" fixture ", " fixture-password ")).isSameAs(user);
    }

    @Test
    void invalidPasswordAndMissingUserHaveSamePublicError() {
        User user = new User(4, "fixture", BCrypt.hashpw("fixture-password", BCrypt.gensalt(4)));
        when(users.findByLoginId("fixture")).thenReturn(Optional.of(user));
        when(users.findByLoginId("absent")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.login("fixture", "wrong"))
                .isInstanceOf(ApiException.class).hasMessage("invalid credentials")
                .satisfies(error -> assertThat(((ApiException) error).getStatus()).isEqualTo(HttpStatus.UNAUTHORIZED));
        assertThatThrownBy(() -> service.login("absent", "wrong"))
                .isInstanceOf(ApiException.class).hasMessage("invalid credentials");
    }

    @Test
    void corruptStoredHashCannotLeakItsContent() {
        when(users.findByLoginId("fixture")).thenReturn(Optional.of(new User(4, "fixture", "bad-stored-hash")));
        assertThatThrownBy(() -> service.login("fixture", "test-password"))
                .isInstanceOf(ApiException.class).hasMessage("invalid credentials");
    }

    @Test
    void concurrentDuplicateSignupIsTranslatedToPublicConflict() {
        when(users.findByLoginId("fixture")).thenReturn(Optional.empty());
        when(users.save(eq("fixture"), anyString())).thenThrow(new DuplicateKeyException("sensitive-driver-message"));

        assertThatThrownBy(() -> service.signup("fixture", "test-password"))
                .isInstanceOf(ApiException.class).hasMessage("id already exists")
                .satisfies(error -> {
                    assertThat(((ApiException) error).getStatus()).isEqualTo(HttpStatus.CONFLICT);
                    assertThat(((ApiException) error).getCode()).isEqualTo("ID_EXISTS");
                });
    }

    @ParameterizedTest
    @CsvSource({"23000,1062", "23505,23505"})
    void jpaUniqueConstraintFailuresAreTranslatedForMariaDbAndH2(String state, int code) {
        when(users.findByLoginId("fixture")).thenReturn(Optional.empty());
        var failure = new DataIntegrityViolationException("private-sql-details",
                new RuntimeException(new SQLException("private-driver-details", state, code)));
        when(users.save(eq("fixture"), anyString())).thenThrow(failure);

        assertThatThrownBy(() -> service.signup("fixture", "test-password"))
                .isInstanceOf(ApiException.class).hasMessage("id already exists")
                .satisfies(error -> {
                    assertThat(((ApiException) error).getStatus()).isEqualTo(HttpStatus.CONFLICT);
                    assertThat(((ApiException) error).getCode()).isEqualTo("ID_EXISTS");
                });
    }

    @Test
    void otherIntegrityFailuresRemainAvailableForSanitizedDatabaseErrorHandler() {
        when(users.findByLoginId("fixture")).thenReturn(Optional.empty());
        var failure = new DataIntegrityViolationException("private-sql-details",
                new SQLException("private-not-null-details", "23000", 1048));
        when(users.save(eq("fixture"), anyString())).thenThrow(failure);

        assertThatThrownBy(() -> service.signup("fixture", "test-password")).isSameAs(failure);
    }

    @Test
    void existingLongPasswordRemainsAcceptedForLegacyCompatibility() {
        String password = "fixture".repeat(12);
        User user = new User(4, "fixture", BCrypt.hashpw(password, BCrypt.gensalt(4)));
        when(users.findByLoginId("fixture")).thenReturn(Optional.of(user));
        assertThat(service.login("fixture", password)).isSameAs(user);
    }

    @Test
    void invalidInputIsRejectedBeforeAnySql() {
        assertThatThrownBy(() -> service.signup(" ", "test-password")).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.login("fixture", null)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.signup("x".repeat(101), "test-password")).isInstanceOf(ApiException.class);
        verifyNoInteractions(users);
    }
}

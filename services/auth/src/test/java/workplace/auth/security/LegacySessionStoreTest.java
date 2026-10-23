package workplace.auth.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import workplace.auth.domain.AuthIdentity;
import workplace.auth.domain.User;

class LegacySessionStoreTest {
    @Test
    void resolvesOnlyIssuedSessionAndInvalidatesItOnLogout() {
        LegacySessionStore store = new LegacySessionStore();
        String first = store.create(new User(7, "test-user", "unused-test-hash"));
        String second = store.create(new User(7, "test-user", "unused-test-hash"));
        assertThat(first).isNotEqualTo(second);
        assertThat(store.resolve(first)).contains(new AuthIdentity(7, "test-user", "session"));
        assertThat(store.resolve("unknown")).isEmpty();
        assertThat(store.resolve(null)).isEmpty();
        store.remove(first);
        store.remove(first);
        store.remove(null);
        assertThat(store.resolve(first)).isEmpty();
        assertThat(store.resolve(second)).isPresent();
    }
}

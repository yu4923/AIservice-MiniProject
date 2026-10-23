package workplace.auth.security;

import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import workplace.auth.domain.AuthIdentity;
import workplace.auth.domain.User;

/** 이전 세션 구현의 비교·테스트용 보관 코드이며 현재 인증에는 등록하지 않는다. */
public class LegacySessionStore {
    private final Map<String, AuthIdentity> sessions = new ConcurrentHashMap<>();

    public String create(User user) {
        String sessionId = UUID.randomUUID().toString();
        sessions.put(sessionId, new AuthIdentity(user.no(), user.id(), "session"));
        return sessionId;
    }

    public Optional<AuthIdentity> resolve(String sessionId) {
        return sessionId == null ? Optional.empty() : Optional.ofNullable(sessions.get(sessionId));
    }

    public void remove(String sessionId) {
        if (sessionId != null) {
            sessions.remove(sessionId);
        }
    }
}

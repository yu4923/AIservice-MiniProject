package workplace.auth.service;

import java.sql.SQLException;
import org.mindrot.jbcrypt.BCrypt;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import workplace.auth.domain.User;
import workplace.auth.repository.UserRepository;
import workplace.auth.web.ApiException;

/** 문자열 id와 비밀번호로 가입·로그인을 처리하고 중복 아이디를 거절한다. */
@Service
public class AuthService {
    private final UserRepository users;

    public AuthService(UserRepository users) {
        this.users = users;
    }

    public User signup(String id, String password) {
        Credentials credentials = validate(id, password);
        if (users.findByLoginId(credentials.id()).isPresent()) {
            throw duplicateId();
        }
        String hash = BCrypt.hashpw(credentials.password(), BCrypt.gensalt(12));
        try {
            return users.save(credentials.id(), hash);
        } catch (DataIntegrityViolationException ex) {
            // The unique key also handles concurrent signups after the lookup.
            if (isDuplicateKey(ex)) {
                throw duplicateId();
            }
            throw ex;
        }
    }

    public User login(String id, String password) {
        Credentials credentials = validate(id, password);
        User user = users.findByLoginId(credentials.id()).orElseThrow(AuthService::invalidCredentials);
        boolean matches;
        try {
            matches = BCrypt.checkpw(credentials.password(), user.passwordHash());
        } catch (IllegalArgumentException ignored) {
            // Corrupt or unsupported stored hashes must not reveal database details.
            matches = false;
        }
        if (!matches) {
            throw invalidCredentials();
        }
        return user;
    }

    private static Credentials validate(String id, String password) {
        String normalizedId = id == null ? "" : id.trim();
        String normalizedPassword = password == null ? "" : password.trim();
        if (normalizedId.isEmpty() || normalizedPassword.isEmpty()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "id and password are required");
        }
        if (normalizedId.codePointCount(0, normalizedId.length()) > 100) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "id must be at most 100 characters");
        }
        return new Credentials(normalizedId, normalizedPassword);
    }

    private static ApiException duplicateId() {
        return new ApiException(HttpStatus.CONFLICT, "ID_EXISTS", "id already exists");
    }

    private static boolean isDuplicateKey(DataIntegrityViolationException failure) {
        if (failure instanceof DuplicateKeyException) return true;
        for (Throwable cause = failure; cause != null; cause = cause.getCause()) {
            if (cause instanceof SQLException sql) {
                for (SQLException error = sql; error != null; error = error.getNextException()) {
                    if (error.getErrorCode() == 1062 || "23505".equals(error.getSQLState())) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    private static ApiException invalidCredentials() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "invalid credentials");
    }

    /** 검증된 입력을 전달하되 로그에서 비밀번호를 숨긴다. */
    private record Credentials(String id, String password) {
        @Override
        public String toString() { return "Credentials[redacted]"; }
    }
}

package workplace.auth.repository;

import java.util.Optional;
import workplace.auth.domain.User;

/** 로그인 아이디로 사용자를 조회하고 가입 정보를 저장한다. */
public interface UserRepository {
    Optional<User> findByLoginId(String id);
    User save(String id, String passwordHash);
}

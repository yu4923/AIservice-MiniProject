package workplace.auth.repository;

import java.util.Optional;
import org.springframework.stereotype.Repository;
import workplace.auth.domain.User;

/** JPA 엔티티를 no·id 기반 사용자 모델로 변환한다. */
@Repository
public class JpaUserRepository implements UserRepository {
    private final JpaUserStore users;

    public JpaUserRepository(JpaUserStore users) {
        this.users = users;
    }

    @Override
    public Optional<User> findByLoginId(String id) {
        // Spring Data binds this derived query's argument as a parameter.
        return users.findByLoginId(id).map(JpaUserRepository::toDomain);
    }

    @Override
    public User save(String id, String passwordHash) {
        // Flush within the repository call so duplicate-key errors reach AuthService.
        return toDomain(users.saveAndFlush(new UserEntity(id, passwordHash)));
    }

    private static User toDomain(UserEntity entity) {
        return new User(entity.getNo(), entity.getLoginId(), entity.getPasswordHash());
    }
}

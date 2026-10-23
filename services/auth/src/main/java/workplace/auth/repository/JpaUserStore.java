package workplace.auth.repository;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

/** 내부 PK 조회와 별개로 로그인 id의 바인딩 조회를 제공한다. */
public interface JpaUserStore extends JpaRepository<UserEntity, Long> {
    Optional<UserEntity> findByLoginId(String loginId);
}

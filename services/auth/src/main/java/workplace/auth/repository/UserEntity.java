package workplace.auth.repository;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

/** users의 no·id·pw 세 컬럼을 매핑하고 비밀번호 해시를 숨긴다. */
@Entity
@Table(name = "users", uniqueConstraints = @UniqueConstraint(name = "uk_users_id", columnNames = "id"))
public class UserEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "no")
    private Long no;

    // Spring Data의 findById가 PK를 뜻하므로 로그인 식별자와 자바 이름도 구분한다.
    @Column(name = "id", nullable = false, length = 100)
    private String loginId;

    @Column(name = "pw", nullable = false, length = 255)
    private String passwordHash;

    protected UserEntity() {}

    public UserEntity(String loginId, String passwordHash) {
        this.loginId = loginId;
        this.passwordHash = passwordHash;
    }

    public Long getNo() { return no; }
    public String getLoginId() { return loginId; }
    public String getPasswordHash() { return passwordHash; }

    @Override
    public String toString() { return "UserEntity[no=" + no + "]"; }
}

-- 기존 테이블의 데이터는 변경하지 않는다. 마이그레이션은 별도 승인 후 수동 적용한다.
CREATE TABLE IF NOT EXISTS users (
    no BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id VARCHAR(100) NOT NULL,
    pw VARCHAR(255) NOT NULL,
    PRIMARY KEY (no),
    UNIQUE KEY uk_users_id (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

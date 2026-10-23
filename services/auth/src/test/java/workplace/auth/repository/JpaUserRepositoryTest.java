package workplace.auth.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@DataJpaTest(showSql = false, properties = {
        "spring.datasource.url=jdbc:h2:mem:jpa_auth;MODE=MariaDB;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa", "spring.datasource.password=test-fixture",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.sql.init.mode=always",
        "spring.sql.init.schema-locations=classpath:test-schema.sql",
        "spring.jpa.hibernate.ddl-auto=validate",
        "spring.jpa.defer-datasource-initialization=false",
        "logging.level.org.hibernate.orm.jdbc.error=OFF",
        "logging.level.org.hibernate.engine.jdbc.spi.SqlExceptionHelper=OFF"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaUserRepository.class)
// Exercise the real repository transaction boundary, including rollback on duplicate inserts.
@Transactional(propagation = Propagation.NOT_SUPPORTED)
class JpaUserRepositoryTest {
    @Autowired JpaUserRepository repository;
    @Autowired JpaUserStore store;
    @Autowired org.springframework.jdbc.core.JdbcTemplate jdbc;

    @BeforeEach
    void resetFixtureDatabase() {
        store.deleteAllInBatch();
    }

    @Test
    void saveUsesGeneratedIdAndRoundTripsExistingSchemaColumns() {
        var user = repository.save("fixture", "$2a$test-only-hash");

        assertThat(user.no()).isPositive();
        assertThat(repository.findByLoginId("fixture")).contains(user);
        assertThat(store.findById(user.no())).isPresent();
        assertThat(store.findById(user.no()).orElseThrow().toString()).doesNotContain("$2a$test-only-hash");
    }

    @Test
    void sqlMetacharactersRemainDataForReadAndWrite() {
        repository.save("fixture", "fixture-hash");
        String injection = "' OR 1=1 --";

        assertThat(repository.findByLoginId(injection)).isEmpty();
        var maliciousName = repository.save(injection, "fixture-hash-two");
        assertThat(repository.findByLoginId(injection)).contains(maliciousName);
        assertThat(store.count()).isEqualTo(2);
    }

    @Test
    void uniqueConstraintRejectsDuplicateAndRollsBackOnlyFailedInsert() {
        var original = repository.save("fixture", "fixture-hash");

        assertThatThrownBy(() -> repository.save("fixture", "another-fixture-hash"))
                .isInstanceOf(DataIntegrityViolationException.class);

        assertThat(store.count()).isEqualTo(1);
        assertThat(repository.findByLoginId("fixture")).contains(original);
    }

    @Test
    void schemaContainsExactlyNoIdPw() {
        assertThat(jdbc.queryForList("SELECT LOWER(column_name) FROM information_schema.columns "
                + "WHERE table_schema = 'PUBLIC' AND LOWER(table_name) = 'users' ORDER BY ordinal_position", String.class))
                .containsExactly("no", "id", "pw");
    }
}

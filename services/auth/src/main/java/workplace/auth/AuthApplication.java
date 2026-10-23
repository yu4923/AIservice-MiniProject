package workplace.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(exclude = org.springframework.boot.security.autoconfigure.UserDetailsServiceAutoConfiguration.class)
public class AuthApplication {
    public static void main(String[] args) {
        // Fail before datasource initialization without exposing configuration values.
        for (String name : new String[]{"DB_USER", "DB_PASSWORD", "JWT_SECRET"}) {
            if (System.getenv(name) == null || System.getenv(name).isBlank()) {
                System.err.println("Required environment variable is missing: " + name);
                System.exit(1);
            }
        }
        try {
            SpringApplication.run(AuthApplication.class, args);
        } catch (Exception ignored) {
            System.err.println("Auth server startup failed. Check local configuration and database availability.");
            System.exit(1);
        }
    }
}

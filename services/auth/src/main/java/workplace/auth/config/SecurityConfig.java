package workplace.auth.config;

import jakarta.servlet.DispatcherType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import workplace.auth.security.*;

@Configuration
public class SecurityConfig {
        @Bean
        SecurityFilterChain securityFilterChain(HttpSecurity http, JwtService jwt,
                        ApiResponseWriter writer, @Value("${auth.frontend-origin}") String frontendOrigin)
                        throws Exception {
                java.net.URI origin = java.net.URI.create(frontendOrigin);
                if (!java.util.Set.of("http", "https").contains(origin.getScheme()) || origin.getHost() == null
                                || origin.getRawQuery() != null || origin.getRawFragment() != null
                                || origin.getUserInfo() != null
                                || (origin.getPath() != null && !origin.getPath().isEmpty())) {
                        throw new IllegalStateException(
                                        "FRONTEND_ORIGIN must be an exact HTTP(S) origin without a path");
                }
                http.csrf(csrf -> csrf.disable()) // Cookie SameSite=Lax plus unsafe-request Origin checking below.
                                .sessionManagement(session -> session
                                                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                                .requestCache(cache -> cache.disable())
                                .formLogin(form -> form.disable())
                                .httpBasic(basic -> basic.disable())
                                .logout(logout -> logout.disable())
                                .authorizeHttpRequests(auth -> auth
                                                .dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                                                .requestMatchers("/api/login",
                                                                "/api/auth/login",
                                                                "/api/signup",
                                                                "/api/auth/signup",
                                                                "/api/logout",
                                                                "/api/auth/logout",
                                                                "/error")
                                                .permitAll()
                                                .requestMatchers(HttpMethod.GET, "/health").permitAll()
                                                .requestMatchers("/api/**", "/home").authenticated()
                                                .anyRequest().permitAll())
                                .exceptionHandling(errors -> errors
                                                .authenticationEntryPoint((request, response, ex) -> writer.error(
                                                                request,
                                                                response,
                                                                401,
                                                                "UNAUTHORIZED",
                                                                "Authentication is required"))
                                                .accessDeniedHandler((request, response, ex) -> writer.error(request,
                                                                response, 403, "FORBIDDEN", "Access is denied")))
                                .addFilterBefore(new RequestPolicyFilter(frontendOrigin, writer),
                                                UsernamePasswordAuthenticationFilter.class)
                                .addFilterBefore(new CookieAuthenticationFilter(jwt),
                                                UsernamePasswordAuthenticationFilter.class);
                return http.build();
        }
}

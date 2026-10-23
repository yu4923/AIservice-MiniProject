package workplace.auth.web;

import java.util.LinkedHashMap;
import java.util.Map;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import workplace.auth.domain.AuthIdentity;
import workplace.auth.domain.User;
import workplace.auth.security.*;
import workplace.auth.service.AuthService;

/** 아이디·비밀번호 입력과 인증 HTTP 응답을 담당한다. */
@RestController
public class AuthController {
    private final AuthService auth;
    private final JwtService jwt;
    private final AuthCookies cookies;
    private final String redirect;

    public AuthController(AuthService auth, JwtService jwt, AuthCookies cookies,
                          @Value("${auth.login-success-url}") String redirect) {
        this.auth = auth; this.jwt = jwt; this.cookies = cookies; this.redirect = redirect;
    }

    /** 요청 아이디와 비밀번호를 전달하되 로그에는 값을 숨긴다. */
    public record Credentials(String id, String password) {
        @Override public String toString() { return "Credentials[redacted]"; }
    }

    @PostMapping(value = {"/api/login", "/api/auth/login"}, consumes = MediaType.APPLICATION_JSON_VALUE)
    Map<String, Object> loginJson(@RequestBody Map<String, Object> body, HttpServletRequest request,
                                  HttpServletResponse response) {
        return login(credentials(body), request, response);
    }

    @PostMapping(value = {"/api/login", "/api/auth/login"}, consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    Map<String, Object> loginForm(@RequestParam(required = false) String id,
            @RequestParam(required = false) String password, HttpServletRequest request, HttpServletResponse response) {
        return login(new Credentials(id, password), request, response);
    }

    private static Credentials credentials(Map<String, Object> body) {
        if (body == null || (body.get("id") != null && !(body.get("id") instanceof String))
                || (body.get("password") != null && !(body.get("password") instanceof String))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_REQUEST", "id and password must be strings");
        }
        return new Credentials((String) body.get("id"), (String) body.get("password"));
    }

    private Map<String, Object> login(Credentials credentials, HttpServletRequest request, HttpServletResponse response) {
        User user = auth.login(credentials.id(), credentials.password());
        String token = jwt.create(user);
        cookies.issue(response, token);
        return Map.of("ok", true, "redirect", redirect, "expires_in", JwtService.TTL_SECONDS);
    }

    @PostMapping(value = {"/api/signup", "/api/auth/signup"}, consumes = MediaType.APPLICATION_JSON_VALUE)
    ResponseEntity<Map<String, Object>> signupJson(@RequestBody Map<String, Object> body) { return signup(credentials(body)); }

    @PostMapping(value = {"/api/signup", "/api/auth/signup"}, consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    ResponseEntity<Map<String, Object>> signupForm(@RequestParam(required = false) String id,
            @RequestParam(required = false) String password) { return signup(new Credentials(id, password)); }

    private ResponseEntity<Map<String, Object>> signup(Credentials credentials) {
        User user = auth.signup(credentials.id(), credentials.password());
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("ok", true, "no", Long.toString(user.no()), "id", user.id()));
    }

    @GetMapping({"/api/auth/check", "/home"})
    Map<String, Object> check(Authentication authentication) {
        AuthIdentity identity = (AuthIdentity) authentication.getPrincipal();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("ok", true); body.put("via", identity.via()); body.put("id", identity.id());
        body.put("no", Long.toString(identity.no()));
        if ("jwt".equals(identity.via())) body.put("sub", Long.toString(identity.no()));
        return body;
    }

    @PostMapping({"/api/logout", "/api/auth/logout"})
    Map<String, Boolean> logout(HttpServletRequest request, HttpServletResponse response) {
        cookies.clear(response);
        return Map.of("ok", true);
    }

    @GetMapping("/health")
    Map<String, String> health() { return Map.of("status", "UP"); }
}

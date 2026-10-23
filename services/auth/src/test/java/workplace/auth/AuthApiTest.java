package workplace.auth;

import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import jakarta.servlet.http.Cookie;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import workplace.auth.security.AuthCookies;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:http_auth;MODE=MariaDB;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa", "spring.datasource.password=test-fixture",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.sql.init.schema-locations=classpath:test-schema.sql",
        "auth.jwt-secret=http-test-fixture-only-never-use-outside-tests",
        "auth.cookie-secure=false", "auth.frontend-origin=http://localhost:5174",
        "auth.login-success-url=http://localhost:5174"
})
@AutoConfigureMockMvc
class AuthApiTest {
    private static final String SECRET = "http-test-fixture-only-never-use-outside-tests";
    private static final String BODY = "{\"id\":\"demo\",\"password\":\"test-fixture-password\"}";
    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach void resetFixture() { jdbc.update("DELETE FROM users"); }

    private void signup() throws Exception {
        mvc.perform(post("/api/signup").contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.id").value("demo"))
                .andExpect(jsonPath("$.password").doesNotExist()).andExpect(jsonPath("$.pw").doesNotExist())
                .andExpect(jsonPath("$.no").isString()).andExpect(jsonPath("$.username").doesNotExist());
    }
    private MvcResult login() throws Exception {
        return mvc.perform(post("/api/login").contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andExpect(status().isOk()).andReturn();
    }
    private Cookie cookie(MvcResult login, String name) {
        return login.getResponse().getCookie(name);
    }

    @Test void signupLoginAndCheckWithJwt() throws Exception {
        signup();
        MvcResult result = login();
        mvc.perform(get("/api/auth/check").cookie(cookie(result,"ACCESS_TOKEN")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.via").value("jwt"))
                .andExpect(jsonPath("$.id").value("demo"));
        assertThat(result.getResponse().getContentAsString()).contains("\"expires_in\":3600")
                .doesNotContain("access_token", "test-fixture-password");
        assertThat(jdbc.queryForObject("SELECT pw FROM users WHERE id = ?",String.class,"demo"))
                .startsWith("$2a$12$");
    }

    @Test void canonicalAliasAcceptsJsonAndLegacyAliasAcceptsForm() throws Exception {
        mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andExpect(status().isCreated());
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andExpect(status().isOk());
        mvc.perform(post("/api/login").contentType(MediaType.APPLICATION_FORM_URLENCODED)
                        .param("id"," demo ").param("password"," test-fixture-password "))
                .andExpect(status().isOk());
    }

    @Test void formSignupAndDuplicateSignupUseBoundRepository() throws Exception {
        mvc.perform(post("/api/signup").contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .param("id","demo").param("password","test-fixture-password")).andExpect(status().isCreated());
        mvc.perform(post("/api/signup").contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.error.code").value("ID_EXISTS"));
    }

    @Test void loginRejectsWrongPasswordMissingUserAndSqlInjection() throws Exception {
        signup();
        for(String name: List.of("demo", "absent", "' OR 1=1 --")) {
            mvc.perform(post("/api/login").contentType(MediaType.APPLICATION_FORM_URLENCODED)
                            .param("id",name).param("password","wrong-fixture"))
                    .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.error.code").value("INVALID_CREDENTIALS"))
                    .andExpect(header().doesNotExist("Set-Cookie"));
        }
    }

    @Test void jwtCookieAuthenticatesWithoutSession() throws Exception {
        signup();
        MvcResult result = login();
        mvc.perform(get("/api/auth/check").cookie(cookie(result,"ACCESS_TOKEN")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.via").value("jwt"))
                .andExpect(jsonPath("$.sub").isString()).andExpect(jsonPath("$.no").isString())
                .andExpect(jsonPath("$.id").value("demo")).andExpect(jsonPath("$.username").doesNotExist());
        mvc.perform(get("/home").cookie(cookie(result,"ACCESS_TOKEN")))
                .andExpect(status().isOk()).andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON));
    }

    @Test void missingTamperedExpiredAndWrongIssuerTokensGet401() throws Exception {
        mvc.perform(get("/api/auth/check")).andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.reason").value("UNAUTHORIZED"));
        String expired = JWT.create().withIssuer("simple-auth-server").withSubject("1").withClaim("id","demo")
                .withExpiresAt(Instant.now().minusSeconds(60)).sign(Algorithm.HMAC256(SECRET));
        String wrongIssuer = JWT.create().withIssuer("wrong").withSubject("1").withClaim("id","demo")
                .withExpiresAt(Instant.now().plusSeconds(60)).sign(Algorithm.HMAC256(SECRET));
        signup();
        String valid = cookie(login(),"ACCESS_TOKEN").getValue();
        String tampered = valid.substring(0, valid.lastIndexOf('.') + 1) + "invalid-signature";
        for(String token: List.of(expired, wrongIssuer, tampered, "not-a-jwt")) {
            mvc.perform(get("/api/auth/check").cookie(new Cookie("ACCESS_TOKEN",token)))
                    .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.error.code").value("UNAUTHORIZED"));
        }
    }

    @Test void legacySessionCannotBypassInvalidJwt() throws Exception {
        signup();
        MvcResult result = login();
        mvc.perform(get("/api/auth/check").cookie(new Cookie("SESSION_ID","old-session"),new Cookie("ACCESS_TOKEN","invalid")))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/auth/check").cookie(new Cookie("APP_AUTH","1")))
                .andExpect(status().isUnauthorized());
    }

    @Test void onlyJwtIsIssuedWithHttpOnlyLaxAttributes() throws Exception {
        signup();
        MvcResult result = login();
        assertThat(result.getResponse().getHeaders("Set-Cookie")).hasSize(1).allSatisfy(value ->
                assertThat(value).contains("Path=/", "SameSite=Lax").doesNotContain("Domain=", "Secure", "Max-Age="));
        assertThat(cookie(result,"ACCESS_TOKEN").isHttpOnly()).isTrue();
        assertThat(cookie(result,"SESSION_ID")).isNull();
        assertThat(cookie(result,"APP_AUTH")).isNull();
        var response = new org.springframework.mock.web.MockHttpServletResponse();
        new AuthCookies(true).issue(response,"fixture-token");
        assertThat(response.getHeaders("Set-Cookie")).allSatisfy(value -> assertThat(value).contains("Secure"));
        new AuthCookies(true).clear(response);
        assertThat(response.getHeaders("Set-Cookie").subList(1,4)).allSatisfy(value ->
                assertThat(value).contains("Secure", "SameSite=Lax", "Max-Age=0", "Path=/"));
    }

    @Test void logoutClearsJwtAndOldCookiesAndIsIdempotent() throws Exception {
        signup();
        MvcResult result = login();
        for(String route: List.of("/api/logout", "/api/auth/logout")) {
            var logout = mvc.perform(post(route).cookie(cookie(result,"ACCESS_TOKEN")))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.ok").value(true)).andReturn();
            assertThat(logout.getResponse().getHeaders("Set-Cookie")).hasSize(3).allSatisfy(value ->
                    assertThat(value).contains("Max-Age=0", "Path=/", "SameSite=Lax"));
        }
        mvc.perform(get("/api/auth/check").cookie(new Cookie("SESSION_ID","old-session"))).andExpect(status().isUnauthorized());
        // Stateless JWT revocation has never been part of legacy logout.
        mvc.perform(get("/api/auth/check").cookie(cookie(result,"ACCESS_TOKEN"))).andExpect(status().isOk());
    }

    @Test void allBrowserAuthRoutesSupportCredentialedCorsPreflight() throws Exception {
        for(String route: List.of("/api/login","/api/signup","/api/logout","/api/auth/login","/api/auth/signup","/api/auth/logout","/api/auth/check")) {
            mvc.perform(options(route).header("Origin","http://localhost:5174")
                    .header("Access-Control-Request-Method",route.endsWith("check")?"GET":"POST")
                    .header("Access-Control-Request-Headers","content-type"))
                    .andExpect(status().isNoContent())
                    .andExpect(header().string("Access-Control-Allow-Origin","http://localhost:5174"))
                    .andExpect(header().string("Access-Control-Allow-Credentials","true"));
        }
        mvc.perform(get("/api/auth/check").header("Origin","http://localhost:5174"))
                .andExpect(status().isUnauthorized()).andExpect(header().string("Access-Control-Allow-Credentials","true"));
    }

    @Test void disallowedOriginSimplePostAndPreflightAreRejectedWithJson() throws Exception {
        mvc.perform(post("/api/logout").header("Origin","https://untrusted.example"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.error.code").value("ORIGIN_NOT_ALLOWED"));
        mvc.perform(options("/api/login").header("Origin","http://localhost:5174")
                .header("Access-Control-Request-Method","POST").header("Access-Control-Request-Headers","X-Unapproved"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.error.code").value("CORS_NOT_ALLOWED"));
        mvc.perform(post("/api/logout").header("Origin","http://localhost"))
                .andExpect(status().isOk());
    }

    @Test void malformedMissingAndWrongTypeRequestsAreSafe400() throws Exception {
        for(String body: List.of("{}", "null", "{bad", "{\"id\":12,\"password\":\"fixture\"}")) {
            mvc.perform(post("/api/login").contentType(MediaType.APPLICATION_JSON).content(body))
                    .andExpect(status().isBadRequest()).andExpect(jsonPath("$.ok").value(false))
                    .andExpect(jsonPath("$.request_id").isString()).andExpect(jsonPath("$.reason").doesNotExist());
        }
        mvc.perform(post("/api/login").contentType(MediaType.TEXT_PLAIN).content("private-fixture-body"))
                .andExpect(status().isUnsupportedMediaType()).andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("private-fixture-body"))));
    }

    // 두 필드만으로 가입·로그인할 수 있고, 잘못된 아이디는 SQL 호출 전에 거절돼야 한다.
    @Test void idIsRequiredForBothSignupAndLogin() throws Exception {
        for (String route : List.of("/api/auth/signup", "/api/auth/login")) {
            for (String body : List.of(
                    "{\"username\":\"demo\",\"password\":\"fixture\"}",
                    "{\"id\":\" \",\"password\":\"fixture\"}",
                    "{\"id\":12,\"password\":\"fixture\"}",
                    "{\"id\":\"demo\"}")) {
                mvc.perform(post(route).contentType(MediaType.APPLICATION_JSON).content(body))
                        .andExpect(status().isBadRequest()).andExpect(header().doesNotExist("Set-Cookie"));
            }
        }
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM users", Integer.class)).isZero();
    }

    @Test void apiOnlyRoutesHaveExactMatchesAndMethodErrors() throws Exception {
        mvc.perform(get("/login")).andExpect(status().isNotFound()).andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
        mvc.perform(get("/api/login")).andExpect(status().isMethodNotAllowed());
        mvc.perform(get("/api/users/me")).andExpect(status().isUnauthorized());
        signup();
        MvcResult result = login();
        mvc.perform(post("/api/login/extra").cookie(cookie(result,"ACCESS_TOKEN"))
                .contentType(MediaType.APPLICATION_JSON).content(BODY)).andExpect(status().isNotFound());
        mvc.perform(get("/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
    }

    @Test void dbPrimaryKeyCannotBeUsedAsLoginId() throws Exception {
        signup();
        Long no = jdbc.queryForObject("SELECT no FROM users WHERE id = ?", Long.class, "demo");
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_FORM_URLENCODED)
                        .param("id", Long.toString(no)).param("password", "test-fixture-password"))
                .andExpect(status().isUnauthorized());
    }

    @Test void anotherAccountsPasswordCannotAuthenticate() throws Exception {
        signup();
        mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"second\",\"password\":\"another-password\"}"))
                .andExpect(status().isCreated());
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"demo\",\"password\":\"another-password\"}"))
                .andExpect(status().isUnauthorized());
    }
}

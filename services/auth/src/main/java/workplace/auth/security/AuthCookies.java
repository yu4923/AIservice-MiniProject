package workplace.auth.security;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

@Component
public class AuthCookies {
    private final boolean secure;
    public AuthCookies(@Value("${auth.cookie-secure}") boolean secure) { this.secure = secure; }

    /** JWT만 발급해 세션과 JWT의 만료 판정이 달라지는 일을 막는다. */
    public void issue(HttpServletResponse response, String jwt) {
        set(response, "ACCESS_TOKEN", jwt, true, false);
    }

    public void clear(HttpServletResponse response) {
        set(response, "SESSION_ID", "", true, true);
        set(response, "ACCESS_TOKEN", "", true, true);
        set(response, "APP_AUTH", "", false, true);
    }

    private void set(HttpServletResponse response, String name, String value, boolean httpOnly, boolean delete) {
        ResponseCookie.ResponseCookieBuilder cookie = ResponseCookie.from(name, value)
                .path("/").httpOnly(httpOnly).secure(secure).sameSite("Lax");
        if (delete) cookie.maxAge(0);
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.build().toString());
    }

    public static String read(HttpServletRequest request, String name) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) return null;
        for (Cookie cookie : cookies) if (name.equals(cookie.getName())) return cookie.getValue();
        return null;
    }
}

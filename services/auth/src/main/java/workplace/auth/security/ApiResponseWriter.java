package workplace.auth.security;

import java.io.IOException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;
import workplace.auth.web.ApiError;

@Component
public class ApiResponseWriter {
    private final ObjectMapper mapper;
    public ApiResponseWriter(ObjectMapper mapper) { this.mapper = mapper; }

    public void error(HttpServletRequest request, HttpServletResponse response,
                      int status, String code, String message) throws IOException {
        ApiError body = ApiError.of(request, status, code, message);
        response.setStatus(status);
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        response.setHeader("X-Request-Id", body.request_id());
        mapper.writeValue(response.getWriter(), body);
    }
}

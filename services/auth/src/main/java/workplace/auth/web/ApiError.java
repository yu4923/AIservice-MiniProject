package workplace.auth.web;

import java.util.List;
import java.util.UUID;
import jakarta.servlet.http.HttpServletRequest;

@com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL)
public record ApiError(boolean ok, String reason, ErrorDetail error, String request_id) {
    public record ErrorDetail(String code, String message, List<Object> details) {}

    public static ApiError of(HttpServletRequest request, int status, String code, String message) {
        String id = (String) request.getAttribute("request_id");
        if (id == null) {
            id = UUID.randomUUID().toString();
            request.setAttribute("request_id", id);
        }
        return new ApiError(false, status == 401 ? "UNAUTHORIZED" : null,
                new ErrorDetail(code, message, List.of()), id);
    }
}

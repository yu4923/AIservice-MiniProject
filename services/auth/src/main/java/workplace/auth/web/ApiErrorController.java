package workplace.auth.web;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.webmvc.error.ErrorController;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ApiErrorController implements ErrorController {
    @RequestMapping("/error")
    ResponseEntity<ApiError> error(HttpServletRequest request) {
        Object value = request.getAttribute(RequestDispatcher.ERROR_STATUS_CODE);
        int status = value instanceof Integer number ? number : 500;
        HttpStatus resolved = HttpStatus.resolve(status);
        String message = resolved == null ? "Request failed" : resolved.getReasonPhrase();
        ApiError body = ApiError.of(request, status, status == 404 ? "NOT_FOUND" : "REQUEST_FAILED", message);
        return ResponseEntity.status(status).header("X-Request-Id", body.request_id()).body(body);
    }
}

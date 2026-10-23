package workplace.auth.web;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(ApiException.class)
    ResponseEntity<ApiError> handleApi(ApiException ex, HttpServletRequest request) {
        return response(request, ex.getStatus().value(), ex.getCode(), ex.getMessage());
    }

    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
    ResponseEntity<ApiError> handleMalformedJson(HttpServletRequest request) {
        return response(request, 400, "INVALID_REQUEST", "A valid JSON object is required");
    }

    @ExceptionHandler(DataAccessException.class)
    ResponseEntity<ApiError> handleDatabase(HttpServletRequest request) {
        return response(request, 503, "DATABASE_UNAVAILABLE", "Database is temporarily unavailable");
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> handleUnexpected(Exception ex, HttpServletRequest request) {
        if (ex instanceof ErrorResponse error) {
            int status = error.getStatusCode().value();
            String code = switch (status) {
                case 400 -> "INVALID_REQUEST";
                case 404 -> "NOT_FOUND";
                case 405 -> "METHOD_NOT_ALLOWED";
                case 415 -> "UNSUPPORTED_MEDIA_TYPE";
                default -> "INVALID_REQUEST";
            };
            return response(request, status, code, HttpStatus.valueOf(status).getReasonPhrase());
        }
        // Do not log request bodies, headers, SQL messages, configuration, or exception text.
        return response(request, 500, "INTERNAL_ERROR", "An internal error occurred");
    }

    private ResponseEntity<ApiError> response(HttpServletRequest request, int status, String code, String message) {
        ApiError body = ApiError.of(request, status, code, message);
        return ResponseEntity.status(status).header("X-Request-Id", body.request_id()).body(body);
    }
}

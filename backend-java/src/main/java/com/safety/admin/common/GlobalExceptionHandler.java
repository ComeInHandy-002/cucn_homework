package com.safety.admin.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<Result<Void>> business(BusinessException exc) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Result.error(exc.getCode(), exc.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> validation(MethodArgumentNotValidException exc) {
        String detail = exc.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(FieldError::getDefaultMessage)
                .orElse("参数校验失败");
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Result.error(400, detail));
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Result<Void>> uploadTooLarge(MaxUploadSizeExceededException exc) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Result.error(400, "上传文件超过大小限制"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> unexpected(Exception exc) {
        log.error("未处理异常", exc);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Result.error(500, "服务器内部错误：" + exc.getMessage()));
    }
}

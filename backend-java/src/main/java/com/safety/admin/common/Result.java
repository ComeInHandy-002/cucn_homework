package com.safety.admin.common;

/**
 * 统一响应格式：{code, message, data}。code=0 表示成功，非 0 为业务错误码。
 */
public record Result<T>(int code, String message, T data) {

    public static <T> Result<T> ok(T data) {
        return new Result<>(0, "success", data);
    }

    public static Result<Void> ok() {
        return new Result<>(0, "success", null);
    }

    public static <T> Result<T> error(int code, String message) {
        return new Result<>(code, message, null);
    }
}

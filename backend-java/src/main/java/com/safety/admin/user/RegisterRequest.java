package com.safety.admin.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank(message = "用户名不能为空") @Size(min = 3, max = 50, message = "用户名长度需在 3-50 之间") String username,
        @NotBlank(message = "密码不能为空") @Size(min = 6, max = 64, message = "密码长度需在 6-64 之间") String password,
        String realName,
        String email) {
}

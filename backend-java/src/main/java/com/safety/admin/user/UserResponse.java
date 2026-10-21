package com.safety.admin.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

public record UserResponse(
        Long id,
        String username,
        String role,
        String realName,
        String email,
        boolean enabled,
        LocalDateTime createdAt) {

    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(), user.getUsername(), user.getRole(),
                user.getRealName(), user.getEmail(), user.isEnabled(), user.getCreatedAt());
    }

    public record UpdateRequest(
            @NotBlank(message = "角色不能为空") String role,
            String realName,
            String email,
            Boolean enabled,
            @Size(min = 6, max = 64, message = "密码长度需在 6-64 之间") String password) {
    }
}

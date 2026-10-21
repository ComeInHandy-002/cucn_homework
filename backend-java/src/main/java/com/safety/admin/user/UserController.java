package com.safety.admin.user;

import com.safety.admin.common.Result;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 用户管理接口（管理域）。列表/新增/修改/删除要求 admin 角色（JwtAuthFilter 控制），
 * 注册与登录为公开接口。
 */
@RestController
@RequestMapping("/auth")
public class UserController {

    private final UserService service;

    public UserController(UserService service) {
        this.service = service;
    }

    @PostMapping("/register")
    public Result<Map<String, Object>> register(@Valid @RequestBody RegisterRequest request) {
        return Result.ok(service.register(request));
    }

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        return Result.ok(service.login(request));
    }

    @GetMapping("/me")
    public Result<Map<String, Object>> me(jakarta.servlet.http.HttpServletRequest request) {
        return Result.ok(Map.of(
                "uid", request.getAttribute("uid"),
                "username", request.getAttribute("username"),
                "role", request.getAttribute("role")));
    }
}

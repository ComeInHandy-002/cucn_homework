package com.safety.admin.user;

import com.safety.admin.common.Result;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/** 用户管理 CRUD（/api/users/** 由 JwtAuthFilter 强制 admin 角色）。 */
@RestController
@RequestMapping("/api/users")
public class UserAdminController {

    private final UserService service;

    public UserAdminController(UserService service) {
        this.service = service;
    }

    @GetMapping
    public Result<List<UserResponse>> list() {
        return Result.ok(service.list());
    }

    @PostMapping
    public Result<UserResponse> create(@Valid @RequestBody RegisterRequest request) {
        return Result.ok(service.create(request, "operator"));
    }

    @PutMapping("/{id}")
    public Result<UserResponse> update(@PathVariable Long id, @Valid @RequestBody UserResponse.UpdateRequest request) {
        return Result.ok(service.update(id, request));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        service.delete(id);
        return Result.ok();
    }
}

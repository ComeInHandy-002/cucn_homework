package com.safety.admin.user;

import com.safety.admin.common.BusinessException;
import com.safety.admin.security.JwtService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class UserService {

    private final UserRepository repository;
    private final JwtService jwtService;
    private final PasswordEncoder encoder = new BCryptPasswordEncoder();

    public UserService(UserRepository repository, JwtService jwtService) {
        this.repository = repository;
        this.jwtService = jwtService;
    }

    public Map<String, Object> register(RegisterRequest request) {
        if (repository.existsByUsername(request.username())) {
            throw new BusinessException(409, "用户名已存在");
        }
        User user = new User();
        user.setUsername(request.username());
        user.setPasswordHash(encoder.encode(request.password()));
        user.setRole("operator");
        user.setRealName(request.realName());
        user.setEmail(request.email());
        repository.save(user);
        return Map.of("id", user.getId(), "username", user.getUsername());
    }

    public Map<String, Object> login(LoginRequest request) {
        User user = repository.findByUsername(request.username())
                .orElseThrow(() -> new BusinessException(401, "用户名或密码错误"));
        if (!user.isEnabled() || !encoder.matches(request.password(), user.getPasswordHash())) {
            throw new BusinessException(401, "用户名或密码错误");
        }
        String token = jwtService.issue(user.getId(), user.getUsername(), user.getRole());
        return Map.of("token", token, "user", UserResponse.from(user));
    }

    public List<UserResponse> list() {
        return repository.findAll().stream().map(UserResponse::from).toList();
    }

    public UserResponse create(RegisterRequest request, String role) {
        if (repository.existsByUsername(request.username())) {
            throw new BusinessException(409, "用户名已存在");
        }
        User user = new User();
        user.setUsername(request.username());
        user.setPasswordHash(encoder.encode(request.password()));
        user.setRole(role);
        user.setRealName(request.realName());
        user.setEmail(request.email());
        repository.save(user);
        return UserResponse.from(user);
    }

    public UserResponse update(Long id, UserResponse.UpdateRequest request) {
        User user = repository.findById(id).orElseThrow(() -> new BusinessException(404, "用户不存在"));
        if (!"admin".equals(request.role()) && !"operator".equals(request.role())) {
            throw new BusinessException(400, "角色只能是 admin 或 operator");
        }
        user.setRole(request.role());
        user.setRealName(request.realName());
        user.setEmail(request.email());
        if (request.enabled() != null) {
            user.setEnabled(request.enabled());
        }
        if (request.password() != null && !request.password().isBlank()) {
            user.setPasswordHash(encoder.encode(request.password()));
        }
        return UserResponse.from(user);
    }

    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new BusinessException(404, "用户不存在");
        }
        repository.deleteById(id);
    }

    /** 首次启动初始化内置 admin 账号（admin / admin123），供演示与联调。 */
    public void ensureDefaultAdmin() {
        if (!repository.existsByUsername("admin")) {
            User user = new User();
            user.setUsername("admin");
            user.setPasswordHash(encoder.encode("admin123"));
            user.setRole("admin");
            user.setRealName("系统管理员");
            repository.save(user);
        }
    }
}

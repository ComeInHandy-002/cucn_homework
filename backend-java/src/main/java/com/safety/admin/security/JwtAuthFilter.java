package com.safety.admin.security;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * JWT 认证过滤器：白名单直接放行；其余接口必须携带有效 Bearer token，
 * 并将 uid/role 写入请求属性供 Controller 读取。管理接口额外要求 admin 角色。
 */
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final List<String> WHITELIST = List.of("/", "/auth/login", "/auth/register", "/error");

    private final JwtService jwtService;

    public JwtAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        // 白名单必须精确匹配：startsWith("/") 会放行所有路径，导致鉴权整体失效
        if (WHITELIST.contains(path) || "OPTIONS".equalsIgnoreCase(request.getMethod())) {
            chain.doFilter(request, response);
            return;
        }

        String header = request.getHeader("Authorization");
        String token = header != null && header.startsWith("Bearer ") ? header.substring(7) : null;
        Claims claims = token == null ? null : jwtService.verify(token);
        if (claims == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"message\":\"未登录或令牌已过期\",\"data\":null}");
            return;
        }
        request.setAttribute("uid", claims.get("uid", Long.class));
        request.setAttribute("username", claims.getSubject());
        request.setAttribute("role", claims.get("role", String.class));

        if (path.startsWith("/api/users") && !"admin".equals(claims.get("role", String.class))) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":403,\"message\":\"需要管理员权限\",\"data\":null}");
            return;
        }
        chain.doFilter(request, response);
    }
}

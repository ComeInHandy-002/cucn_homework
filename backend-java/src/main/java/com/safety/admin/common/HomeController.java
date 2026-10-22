package com.safety.admin.common;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 根路径引导页：管理域是纯 REST 服务，直接用浏览器访问时给出正确的入口提示，
 * 避免误以为 401 是服务故障。
 */
@RestController
public class HomeController {

    @GetMapping("/")
    public String index() {
        return """
                <!doctype html>
                <html lang="zh-CN">
                <head><meta charset="utf-8"><title>工业安全智能监测系统 · 管理域 API</title>
                <style>body{font-family:"Microsoft YaHei",sans-serif;background:#0b1724;color:#cfe0ee;display:grid;place-items:center;height:100vh;margin:0}
                .card{max-width:560px;padding:36px 42px;border:1px solid #1e3a52;border-radius:12px;background:#0f2033}
                h1{font-size:20px;margin:0 0 12px}p{font-size:13px;line-height:1.9;color:#8fa9c0;margin:6px 0}
                a{color:#4db8ff}code{color:#7fd0a0;font-size:12px}</style></head>
                <body><div class="card">
                <h1>✔ 管理域 API 服务运行中（端口 8081）</h1>
                <p>本服务是纯后端 REST 接口，没有网页界面；浏览器直接访问会返回 401 JSON，属正常现象。</p>
                <p>管理界面请从监测工作台进入：</p>
                <p><a href="http://127.0.0.1:8010/admin/users">http://127.0.0.1:8010/admin/users</a>（用户管理）</p>
                <p><a href="http://127.0.0.1:8010/admin/models">http://127.0.0.1:8010/admin/models</a>（数据集与模型）</p>
                <p>接口清单：<code>POST /auth/login · POST /auth/register · GET/POST/PUT/DELETE /api/users · /api/datasets · POST /api/models/train · GET /api/models/evaluation</code></p>
                </div></body></html>
                """;
    }
}

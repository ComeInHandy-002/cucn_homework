"""实验四/五报告的核心代码片段素材：从真实源码按行截取并渲染代码图。"""

from __future__ import annotations

from pathlib import Path

from render_code_asset import render_code

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "backend-java" / "src" / "main" / "java" / "com" / "safety" / "admin"
FRONT = ROOT / "frontend" / "src"
E4 = ROOT / "results" / "experiment4"
E5 = ROOT / "results" / "experiment5"


def snippet(path: Path, start: int, end: int) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[start - 1 : end]


def build_code_assets() -> None:
    E4.mkdir(parents=True, exist_ok=True)
    E5.mkdir(parents=True, exist_ok=True)

    # ---- 实验四：Java 核心代码 ----
    render_code(
        snippet(JAVA / "user" / "UserService.java", 24, 48),
        E4 / "c1_user_register_login.png",
        "user/UserService.java — 注册（BCrypt 加密）与登录（JWT 签发）",
    )
    render_code(
        snippet(JAVA / "security" / "JwtAuthFilter.java", 20, 62),
        E4 / "c2_jwt_filter.png",
        "security/JwtAuthFilter.java — 统一鉴权过滤器（白名单/401/403）",
    )
    render_code(
        snippet(JAVA / "modeltask" / "ModelTrainService.java", 57, 76)
        + [""]
        + snippet(JAVA / "modeltask" / "ModelTrainService.java", 88, 118),
        E4 / "c3_train_async.png",
        "modeltask/ModelTrainService.java — 异步训练任务创建与 ProcessBuilder 调用",
    )
    render_code(
        (ROOT / "backend-java" / "src" / "main" / "resources" / "application.yml").read_text(encoding="utf-8").splitlines(),
        E4 / "c4_application_yml.png",
        "src/main/resources/application.yml — 数据源/端口/CORS/训练配置",
        size=7.2,
    )
    render_code(
        snippet(JAVA / "common" / "GlobalExceptionHandler.java", 15, 44),
        E4 / "c5_exception_handler.png",
        "common/GlobalExceptionHandler.java — 全局异常与统一错误响应",
    )

    # ---- 实验五：Vue 核心代码 ----
    render_code(
        snippet(FRONT / "adminApi.js", 8, 44),
        E5 / "c1_axios_interceptors.png",
        "src/adminApi.js — Axios 实例与请求/响应拦截器",
    )
    render_code(
        snippet(FRONT / "components" / "AdminGate.vue", 5, 33),
        E5 / "c2_admingate.png",
        "components/AdminGate.vue — 管理域登录门（独立 JWT + logged-in 事件）",
    )
    render_code(
        snippet(FRONT / "views" / "AdminModelsView.vue", 40, 52)
        + [""]
        + snippet(FRONT / "views" / "AdminModelsView.vue", 88, 104),
        E5 / "c3_train_poll.png",
        "views/AdminModelsView.vue — 训练任务 5 秒自动轮询与发起",
    )
    render_code(
        snippet(FRONT / "views" / "OverviewView.vue", 16, 52),
        E5 / "c4_echarts_donut.png",
        "views/OverviewView.vue — ECharts 告警环形图数据绑定",
    )


if __name__ == "__main__":
    build_code_assets()
    print("code assets:", sorted(p.name for p in list(E4.glob("c*.png")) + list(E5.glob("c*.png"))))

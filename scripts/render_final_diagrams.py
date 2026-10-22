"""期末报告补充图表：架构图 v2（浅色现代风）/ 用例图 / 告警生命周期 / 视频流水线 / 前端结构。

风格与 ER 关系图统一：白底、圆角实体框、蓝色系（Java/管理域）、
绿色系（Python/算法域）、橙色（前端）、箭头带关系标注。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "midterm"

BLUE_D, BLUE_L = "#1F4E79", "#EAF1F8"
GREEN_D, GREEN_L = "#548235", "#EDF5EA"
ORANGE_D, ORANGE_L = "#C55A11", "#FDF0E7"
PURPLE_D, PURPLE_L = "#7030A0", "#F3EBFA"
INK = "#24292F"


def _panel(ax, x, y, w, h, title, face, edge, title_color=None, title_dy=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                linewidth=1.2, edgecolor=edge, facecolor=face, zorder=1))
    ax.text(x + w / 2, y + h - (title_dy if title_dy is not None else 0.045), title,
            ha="center", va="center", fontsize=10, color=title_color or edge, fontweight="bold", zorder=2)


def _box(ax, x, y, w, h, text, face, edge, fs=8.0, tc=INK, lw=1.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.003,rounding_size=0.008",
                                linewidth=lw, edgecolor=edge, facecolor=face, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc, zorder=4)


def _arrow(ax, p1, p2, label="", color="#44607A", rad=0.0, label_dy=0.018, fs=7.4, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=13,
                                 linewidth=1.5, color=color, zorder=2,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + label_dy, label,
                ha="center", va="bottom", fontsize=7.4, color=color, zorder=2)


def save(fig, name):
    out = OUT_DIR / name
    fig.savefig(out, facecolor="#FBFCFE", bbox_inches="tight")
    plt.close(fig)
    return out


# ---------- 1. 系统总体架构 v2 ----------
def render_architecture(path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11.6, 7.0), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    # 顶层：用户浏览器 / Vue3 工作台
    _panel(ax, 0.14, 0.76, 0.72, 0.20, "用户浏览器 · Vue3 工作台（Element Plus + ECharts + Pinia + Vue Router）",
           ORANGE_L, ORANGE_D, ORANGE_D, 0.05)
    routes = ["监控总览", "智能检测", "任务中心", "模型实验", "告警中心", "设备与区域", "用户管理", "数据集/模型"]
    for i, route in enumerate(routes):
        _box(ax, 0.165 + i * 0.0885, 0.775, 0.078, 0.075, route, "#FFFFFF", ORANGE_D, fs=7.2, tc=INK)
    ax.text(0.5, 0.7635, "Axios 双域调用（监测域 JWT + 管理域 JWT 相互独立）",
            ha="center", va="top", fontsize=7.6, color=ORANGE_D, zorder=2)

    # 左下：Python 算法域
    _panel(ax, 0.03, 0.10, 0.44, 0.52, "Python 算法域 FastAPI（:8010）", GREEN_L, GREEN_D, GREEN_D, 0.05)
    for i, comp in enumerate(["FastAPI 路由层", "YOLOv8 推理（GPU/CPU）", "ByteTrack 跟踪", "规则引擎（PPE/越界/确认/冷却）", "WebSocket 实时推送", "SQLite / PostgreSQL"]):
        col, row = i % 2, i // 2
        _box(ax, 0.055 + col * 0.205, 0.44 - row * 0.105, 0.19, 0.085, comp, "#FFFFFF", GREEN_D, fs=7.6)

    # 右下：Spring Boot 管理域
    _panel(ax, 0.53, 0.10, 0.44, 0.52, "Java 管理域 Spring Boot（:8081）", BLUE_L, BLUE_D, BLUE_D, 0.05)
    for i, comp in enumerate(["Controller 接口层", "Service 业务层", "Repository 持久层", "JwtAuthFilter 鉴权", "数据集/训练任务", "MySQL（safety_admin）"]):
        col, row = i % 2, i // 2
        _box(ax, 0.555 + col * 0.205, 0.44 - row * 0.105, 0.19, 0.085, comp, "#FFFFFF", BLUE_D, fs=7.6)

    # 连接箭头
    _arrow(ax, (0.32, 0.76), (0.30, 0.62), "REST + WebSocket\n（监测域 JWT）", GREEN_D, rad=0.0, fs=7.4, label_dy=0.0)
    _arrow(ax, (0.68, 0.76), (0.70, 0.62), "REST\n（管理域 JWT）", BLUE_D, rad=0.0, fs=7.4, label_dy=0.0)
    _arrow(ax, (0.53, 0.22), (0.47, 0.22), "ProcessBuilder 训练子进程", PURPLE_D, rad=0.0, fs=7.4, label_dy=0.028)

    ax.text(0.5, 0.03, "职责划分：Java 承担业务编排与事务（用户/数据集/训练任务），Python 承担深度学习推理与实时告警，前端统一入口",
            ha="center", fontsize=8, color="#6B7A88", style="italic")
    return save(fig, "final_architecture_v2.png")


# ---------- 2. 用例图 ----------
def render_usecase(path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11.2, 6.4), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    # 系统边界
    ax.add_patch(FancyBboxPatch((0.24, 0.06), 0.52, 0.86, boxstyle="round,pad=0.004,rounding_size=0.012",
                                linewidth=1.4, edgecolor="#44607A", facecolor="#F4F8FB", zorder=1))
    ax.text(0.5, 0.885, "工业安全智能监测系统", ha="center", fontsize=10.5,
            color="#1F4E79", fontweight="bold", zorder=2)

    def actor(x, y, name):
        ax.add_patch(Circle((x, y + 0.10), 0.022, fill=False, linewidth=1.6, edgecolor=INK, zorder=3))
        ax.plot([x, x], [y + 0.078, y - 0.01], color=INK, linewidth=1.6, zorder=3)
        ax.plot([x - 0.035, x + 0.035], [y + 0.045, y + 0.045], color=INK, linewidth=1.6, zorder=3)
        ax.plot([x, x - 0.028], [y - 0.01, y - 0.055], color=INK, linewidth=1.6, zorder=3)
        ax.plot([x, x + 0.028], [y - 0.01, y - 0.055], color=INK, linewidth=1.6, zorder=3)
        ax.text(x, y - 0.095, name, ha="center", fontsize=9.5, color=INK, fontweight="bold", zorder=3)

    def usecase(x, y, text, color):
        ax.add_patch(Ellipse((x, y), 0.19, 0.085, facecolor="white", edgecolor=color, linewidth=1.4, zorder=3))
        ax.text(x, y, text, ha="center", va="center", fontsize=7.8, color=INK, zorder=4)

    operator_cases = [("图片安全检测", 0.40, 0.76), ("视频安全检测", 0.40, 0.62), ("告警确认与闭环", 0.40, 0.48), ("查看统计与实验", 0.40, 0.34)]
    admin_cases = [("用户管理（CRUD）", 0.60, 0.76), ("数据集上传管理", 0.60, 0.62), ("在线训练与评估", 0.60, 0.48), ("危险区域配置", 0.60, 0.34)]
    login_case = ("登录认证（JWT）", 0.50, 0.16)

    actor(0.09, 0.50, "操作员")
    actor(0.91, 0.50, "系统管理员")
    for text, x, y in operator_cases:
        usecase(x, y, text, GREEN_D)
    for text, x, y in admin_cases:
        usecase(x, y, text, BLUE_D)
    usecase(login_case[1], login_case[2], login_case[0], PURPLE_D)

    for _, x, y in operator_cases:
        _arrow(ax, (0.125, 0.50), (x - 0.095, y), "", GREEN_D, rad=0.10, style="-")
    for _, x, y in admin_cases:
        _arrow(ax, (0.875, 0.50), (x + 0.095, y), "", BLUE_D, rad=-0.10, style="-")
    for source in ((0.125, 0.40), (0.875, 0.40)):
        _arrow(ax, source, (login_case[1] - (0.08 if source[0] < 0.5 else -0.08), login_case[2]), "", PURPLE_D, rad=-0.18, style="-")

    ax.text(0.5, 0.015, "include 关系：全部用例均需先经过 JWT 登录认证；管理域用例额外要求 admin 角色",
            ha="center", fontsize=8, color="#6B7A88", style="italic")
    return save(fig, "final_usecase.png")


# ---------- 3. 告警生命周期 ----------
def render_alert_lifecycle(path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11.2, 3.4), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    states = [
        (0.06, "open 待处理", "规则引擎产生\n连续 3 帧确认\nWebSocket 推送", "#C00000"),
        (0.40, "acknowledged 已确认", "操作员人工确认\n责任到人", "#DB8900"),
        (0.74, "resolved 已关闭", "闭环完成\n计入统计", "#2E8B57"),
    ]
    for x, title, detail, color in states:
        _box(ax, x, 0.42, 0.22, 0.34, "", "#FFFFFF", color, lw=1.6)
        ax.text(x + 0.11, 0.68, title, ha="center", fontsize=9.2, color=color, fontweight="bold", zorder=4)
        ax.text(x + 0.11, 0.53, detail, ha="center", va="center", fontsize=7.8, color=INK, zorder=4)

    _arrow(ax, (0.28, 0.59), (0.40, 0.59), "确认", "#DB8900")
    _arrow(ax, (0.62, 0.59), (0.74, 0.59), "关闭", "#2E8B57")
    _arrow(ax, (0.17, 0.90), (0.17, 0.775), "", "#C00000")
    ax.text(0.175, 0.86, "规则引擎触发（no_helmet / no_vest / intrusion）", ha="left",
            fontsize=7.8, color="#C00000", zorder=2)
    ax.text(0.51, 0.30, "同一事件重复触发受 10 秒冷却与连续 3 帧确认约束；证据截图随事件留存",
            ha="center", fontsize=8, color="#6B7A88", style="italic")
    return save(fig, "final_alert_lifecycle.png")


# ---------- 4. 视频推理流水线 ----------
def render_pipeline(path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11.6, 5.2), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    lanes = [
        (0.68, "线程 1 · 解码", GREEN_L, GREEN_D, ["FFmpeg / OpenCV 读取", "帧入有界队列（≤16）"]),
        (0.36, "线程 2 · 批量推理", "#FFF3E7", "#C55A11", ["凑批（batch=8）", "GPU 批量推理 FP16"]),
        (0.04, "线程 3 · 保序后处理", BLUE_L, BLUE_D, []),
    ]
    for y, title, bg, edge, items in lanes:
        ax.add_patch(FancyBboxPatch((0.03, y), 0.94, 0.24, boxstyle="round,pad=0.004,rounding_size=0.01",
                                    linewidth=1.1, edgecolor=edge, facecolor=bg, zorder=1))
        ax.text(0.05, y + 0.195, title, fontsize=9.5, color=edge, fontweight="bold", zorder=2)
        for i, item in enumerate(items):
            _box(ax, 0.24 + i * 0.30, y + 0.06, 0.27, 0.115, item, "#FFFFFF", edge, fs=8.0)

    # 队列连接
    _arrow(ax, (0.60, 0.775), (0.24, 0.545), "decode_queue", "#44607A", rad=-0.12)
    _arrow(ax, (0.60, 0.455), (0.24, 0.225), "inference_queue", "#44607A", rad=-0.12)

    # 线程 3 内部链
    chain = ["ByteTrack 跟踪", "规则引擎\n确认/冷却/宽限", "证据截图\n事件入库", "标注帧编码"]
    for i, item in enumerate(chain):
        _box(ax, 0.045 + i * 0.235, 0.075, 0.20, 0.13, item, "#FFFFFF", BLUE_D, fs=7.8)
        if i:
            _arrow(ax, (0.045 + (i - 1) * 0.235 + 0.20, 0.14), (0.045 + i * 0.235, 0.14), "", BLUE_D)

    ax.text(0.5, 0.955, "严格按原始帧序执行：检测可批量乱序加速，跟踪与规则在保序队列后逐帧处理，缺帧即报错终止",
            ha="center", fontsize=8.2, color="#6B7A88", style="italic")
    return save(fig, "final_pipeline.png")


# ---------- 5. 前端结构 ----------
def render_frontend(path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11.6, 5.6), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    _panel(ax, 0.03, 0.62, 0.94, 0.32, "App.vue（侧边导航 · 顶栏状态 · 双域登录态）", ORANGE_L, ORANGE_D, ORANGE_D, 0.885)
    monitor = ["监控总览", "智能检测", "任务中心", "模型实验", "告警中心", "设备与区域"]
    admin = ["用户管理", "数据集/模型"]
    for i, route in enumerate(monitor):
        _box(ax, 0.055 + i * 0.093, 0.655, 0.083, 0.09, route, "#FFFFFF", ORANGE_D, fs=7.4)
    ax.text(0.66, 0.70, "管理域 →", fontsize=8, color=BLUE_D, zorder=2)
    for i, route in enumerate(admin):
        _box(ax, 0.755 + i * 0.105, 0.655, 0.095, 0.09, route, "#FFFFFF", BLUE_D, fs=7.4)

    _panel(ax, 0.03, 0.06, 0.455, 0.48, "监测域支撑（Pinia · api.js fetch 封装）", GREEN_L, GREEN_D, GREEN_D, 0.485)
    for i, comp in enumerate(["REST 接口调用", "WebSocket 实时告警", "演示素材一键载入", "危险区域画布"]):
        col, row = i % 2, i // 2
        _box(ax, 0.055 + col * 0.205, 0.34 - row * 0.12, 0.19, 0.095, comp, "#FFFFFF", GREEN_D, fs=7.8)

    _panel(ax, 0.515, 0.06, 0.455, 0.48, "管理域支撑（adminApi.js Axios 封装）", BLUE_L, BLUE_D, BLUE_D, 0.485)
    for i, comp in enumerate(["请求拦截：JWT 注入", "响应拦截：统一解包/通知", "训练任务 5 秒轮询", "AdminGate 登录门"]):
        col, row = i % 2, i // 2
        _box(ax, 0.54 + col * 0.205, 0.34 - row * 0.12, 0.19, 0.095, comp, "#FFFFFF", BLUE_D, fs=7.8)

    ax.text(0.5, 0.02, "Element Plus 组件库 · ECharts 可视化 · Vite 构建产物由 FastAPI 伺服（SPA history 回退）",
            ha="center", fontsize=8, color="#6B7A88", style="italic")
    return save(fig, "final_frontend.png")


if __name__ == "__main__":
    print(render_architecture(OUT_DIR / "final_architecture_v2.png"))
    print(render_usecase(OUT_DIR / "final_usecase.png"))
    print(render_alert_lifecycle(OUT_DIR / "final_alert_lifecycle.png"))
    print(render_pipeline(OUT_DIR / "final_pipeline.png"))
    print(render_frontend(OUT_DIR / "final_frontend.png"))

"""渲染期末报告用的数据库 ER 关系图（管理域 MySQL + 算法域 双面板）。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

ENTITIES = {
    "users": ("用户表", [
        ("id", "PK 自增"),
        ("username", "UNIQUE"),
        ("password_hash", "BCrypt"),
        ("role", "admin/operator"),
        ("enabled", "BOOLEAN"),
        ("created_at", "DATETIME"),
    ]),
    "datasets": ("数据集表", [
        ("id", "PK 自增"),
        ("name", "VARCHAR"),
        ("original_filename", "VARCHAR"),
        ("stored_path", "VARCHAR"),
        ("sha256", "CHAR(64)"),
        ("uploaded_at", "DATETIME"),
    ]),
    "model_train_tasks": ("训练任务表", [
        ("id", "PK 自增"),
        ("name", "VARCHAR"),
        ("status", "状态机 4 态"),
        ("epochs", "INT"),
        ("best_weights", "VARCHAR"),
        ("metrics_json", "真实指标"),
    ]),
    "cameras": ("监控点表", [
        ("id", "PK 自增"),
        ("name", "VARCHAR"),
        ("source", "VARCHAR"),
        ("enabled", "BOOLEAN"),
    ]),
    "danger_zones": ("危险区域表", [
        ("id", "PK 自增"),
        ("camera_id", "FK"),
        ("polygon", "0-1 相对坐标"),
        ("coordinate_space", "relative"),
        ("enabled", "BOOLEAN"),
    ]),
    "inference_jobs": ("推理任务表", [
        ("id", "UUID PK"),
        ("source_type", "image/video"),
        ("status", "状态机 4 态"),
        ("progress", "FLOAT"),
        ("result_path", "VARCHAR"),
    ]),
    "safety_events": ("安全事件表", [
        ("id", "UUID PK"),
        ("event_type", "3 类违规"),
        ("severity", "4 级"),
        ("track_id", "人员轨迹"),
        ("evidence_path", "证据截图"),
        ("status", "闭环 3 态"),
    ]),
}

HEADER_COLORS = {
    "users": "#1F4E79", "datasets": "#2E75B6", "model_train_tasks": "#1F4E79",
    "cameras": "#548235", "danger_zones": "#70AD47", "inference_jobs": "#548235", "safety_events": "#70AD47",
}
BOX_W, LINE_H, HEADER_H = 0.20, 0.031, 0.048
PANELS = [
    (0.025, "管理域 MySQL（safety_admin）", "#EAF1F8", "#1F4E79"),
    (0.525, "算法域 SQLite / PostgreSQL", "#EDF5EA", "#548235"),
]


def draw_entity(ax, name: str, x: float, y: float):
    zh, fields = ENTITIES[name]
    height = HEADER_H + LINE_H * len(fields) + 0.012
    box = FancyBboxPatch((x, y - height), BOX_W, height, boxstyle="round,pad=0.004,rounding_size=0.008",
                         linewidth=1.2, edgecolor="#44607A", facecolor="white", zorder=3)
    ax.add_patch(box)
    header = FancyBboxPatch((x, y - HEADER_H), BOX_W, HEADER_H, boxstyle="round,pad=0.004,rounding_size=0.008",
                            linewidth=0, facecolor=HEADER_COLORS[name], zorder=4)
    ax.add_patch(header)
    ax.text(x + BOX_W / 2, y - HEADER_H / 2, f"{name}  {zh}", ha="center", va="center",
            fontsize=8.0, color="white", fontweight="bold", zorder=5)
    for i, (field, note) in enumerate(fields):
        row_y = y - HEADER_H - LINE_H * (i + 0.62)
        ax.text(x + 0.010, row_y, field, ha="left", va="center", fontsize=6.8,
                family=["Consolas", "Microsoft YaHei"], color="#24292F", zorder=5)
        ax.text(x + BOX_W - 0.010, row_y, note, ha="right", va="center", fontsize=6.2,
                family=["Consolas", "Microsoft YaHei"], color="#8A97A5", zorder=5)
    return (x, y, x + BOX_W, y - height)


def render_er(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.6, 6.2), dpi=160)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FBFCFE")

    for px, title, bg, accent in PANELS:
        ax.add_patch(FancyBboxPatch((px - 0.012, 0.045), 0.462, 0.90, boxstyle="round,pad=0.004,rounding_size=0.01",
                                    linewidth=1.0, edgecolor=accent, facecolor=bg, zorder=1))
        ax.text(px - 0.012 + 0.231, 0.915, title, ha="center", va="center", fontsize=10.5,
                color=accent, fontweight="bold", zorder=2)

    positions = {
        "users": (0.055, 0.82),
        "model_train_tasks": (0.262, 0.82),
        "datasets": (0.055, 0.44),
        "cameras": (0.548, 0.82),
        "inference_jobs": (0.762, 0.82),
        "danger_zones": (0.548, 0.44),
        "safety_events": (0.762, 0.44),
    }
    boxes = {name: draw_entity(ax, name, x, y) for name, (x, y) in positions.items()}

    def side(box, side_name):
        x1, y1, x2, y2 = box
        return {"right": (x2, (y1 + y2) / 2), "left": (x1, (y1 + y2) / 2),
                "top": ((x1 + x2) / 2, y1), "bottom": ((x1 + x2) / 2, y2)}[side_name]

    edges = [
        ("users", "datasets", "bottom", "top", "#1F4E79", "上传管理 1:N"),
        ("users", "model_train_tasks", "right", "left", "#1F4E79", "发起 1:N"),
        ("cameras", "danger_zones", "bottom", "top", "#548235", "绑定 1:N"),
        ("cameras", "inference_jobs", "right", "left", "#548235", "采集 1:N"),
        ("inference_jobs", "safety_events", "bottom", "top", "#548235", "产生 1:N"),
    ]
    for src, dst, s_side, d_side, color, label in edges:
        (sx, sy), (dx, dy) = side(boxes[src], s_side), side(boxes[dst], d_side)
        arrow = FancyArrowPatch((sx, sy), (dx, dy), arrowstyle="-|>", mutation_scale=13,
                                linewidth=1.4, color=color, zorder=2,
                                connectionstyle="arc3,rad=0.10")
        ax.add_patch(arrow)
        offset_x = 0.035 if s_side in ("right", "left") else 0
        offset_y = 0.015 if s_side in ("top", "bottom") else 0
        ax.text((sx + dx) / 2 + offset_x, (sy + dy) / 2 + offset_y, label,
                ha="center", va="bottom", fontsize=7.2, color=color, zorder=2)

    ax.text(0.5, 0.015, "跨域协作：管理域训练任务经 ProcessBuilder 调用算法域训练脚本，产物（best.pt / results.csv）回写任务表",
            ha="center", va="center", fontsize=8, color="#6B7A88", style="italic")
    fig.savefig(path, facecolor="#FBFCFE", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "results" / "midterm" / "final_db_er.png"
    render_er(out)
    print(out)

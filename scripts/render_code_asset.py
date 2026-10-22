"""把源码片段渲染成白底代码图，用于实验报告插入核心代码。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Consolas", "Microsoft YaHei", "monospace"]
plt.rcParams["axes.unicode_minus"] = False


def render_code(lines: list[str], path: Path, filename: str, *, max_chars: int = 110, size: float = 7.6) -> Path:
    """白底 + 等宽字体 + 行号，模拟 IDE 代码样式。超长行截断。"""
    shown = []
    for index, line in enumerate(lines[:80], start=1):
        line = line.rstrip()
        if len(line) > max_chars:
            line = line[:max_chars] + " …"
        shown.append(f"{index:>3}  {line}")
    if len(lines) > 80:
        shown.append(f"  …（共 {len(lines)} 行，仅展示核心段）")
    fig = plt.figure(figsize=(9.6, 0.178 * len(shown) + 0.42), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_facecolor("#F6F8FA")
    fig.patch.set_facecolor("#F6F8FA")
    # 标题栏（文件名）
    ax.add_patch(plt.Rectangle((0.0, 0.945), 1.0, 0.055, color="#1F4E79", transform=ax.transAxes))
    ax.text(0.012, 0.977, filename, va="top", ha="left", fontsize=8.6, color="#FFFFFF", family=["Consolas", "Microsoft YaHei"], transform=ax.transAxes)
    ax.text(0.012, 0.925, "\n".join(shown), va="top", ha="left", family=["Consolas", "Microsoft YaHei"], fontsize=size, color="#24292F", transform=ax.transAxes, linespacing=1.32)
    fig.savefig(path, facecolor="#F6F8FA", bbox_inches="tight")
    plt.close(fig)
    return path

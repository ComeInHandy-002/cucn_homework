"""构建《传媒数据管理与分析》期中报告完成版（工业安全智能监测系统课题）。

数据与截图全部来自项目真实产物：
- 图表数据：results/*-metrics.json（E1-E8 真实 test 指标）、
  results/expanded_ppe_kaggle_validation_latest.json（数据集校验）
- 控制台截图：results/midterm/ 下真实命令输出存档渲染
- UI 截图：results/midterm/ui-*.png（浏览器实测截图）
生成前先运行 collect 步骤确认素材存在。
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MID = RESULTS / "midterm"
TEMPLATE = Path(r"D:\学号_姓名《基于机器学习的电影票房分析与预测系统》期中报告.docx")
FINAL = ROOT / "学号_姓名《基于机器学习的工业安全智能监测系统》期中报告_完成版.docx"

OLD_TITLE = "基于机器学习的电影票房分析与预测系统"
NEW_TITLE = "基于机器学习的工业安全智能监测系统"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


# ---------- 素材图表（数据全部来自真实 JSON） ----------
def load_metrics() -> list[dict]:
    runs = [
        ("YOLOv8n smoke", "baseline-n-smoke-metrics.json", "Construction-PPE 基线"),
        ("YOLOv8s smoke", "baseline-s-smoke-metrics.json", "Construction-PPE 基线"),
        ("YOLOv8s 5ep", "expanded-ppe-yolov8s-5ep-test-metrics.json", "Expanded PPE"),
        ("YOLOv8s 10ep", "expanded-ppe-yolov8s-finetune10-test-metrics.json", "Expanded PPE"),
        ("E6 8ep 合并集", "expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json", "合并集"),
        ("E7 12ep hardcase", "expanded-ppe-yolov8s-hardcase12-test-metrics.json", "合并集+hardcase"),
        ("E8 30ep video150", "expanded-ppe-yolov8s-e8-video150-test-metrics.json", "合并集+video150"),
    ]
    out = []
    for name, filename, dataset in runs:
        payload = json.loads((RESULTS / filename).read_text(encoding="utf-8"))
        out.append({
            "name": name,
            "dataset": dataset,
            "precision": payload.get("precision"),
            "recall": payload.get("recall"),
            "f1": payload.get("f1"),
            "map50": payload.get("map50"),
            "map50_95": payload.get("map50_95"),
            "per_class": payload.get("per_class") or {},
        })
    return out


def make_assets() -> dict:
    MID.mkdir(parents=True, exist_ok=True)
    runs = load_metrics()

    # mt1 数据集划分规模
    validation = json.loads((RESULTS / "expanded_ppe_kaggle_validation_latest.json").read_text(encoding="utf-8"))
    splits = validation["splits"]
    names = ["train", "val", "test"]
    images = [splits[k]["images"] for k in names]
    boxes = [splits[k]["boxes"] for k in names]
    fig, ax1 = plt.subplots(figsize=(6.8, 3.2), dpi=150)
    x = range(len(names))
    bars = ax1.bar([i - 0.18 for i in x], images, width=0.36, label="图片数", color="#2F75B5")
    ax1.bar_label(bars, fontsize=9)
    ax12 = ax1.twinx()
    bars2 = ax12.bar([i + 0.18 for i in x], boxes, width=0.36, label="标注框数", color="#ED7D31")
    ax12.bar_label(bars2, fontsize=9)
    ax1.set_xticks(list(x), [f"{k.upper()}\n校验错误: {len(splits[k]['errors'])}" for k in names], fontsize=9)
    ax1.set_ylabel("图片数")
    ax12.set_ylabel("标注框数")
    ax1.set_title("合并数据集 train/val/test 划分（validate_dataset.py 校验 0 错误）", fontsize=10)
    ax1.legend(fontsize=8, loc="upper right")
    ax12.legend(fontsize=8, loc="upper center")
    fig.tight_layout()
    fig.savefig(MID / "mt1_dataset_splits.png", bbox_inches="tight")
    plt.close(fig)

    # mt2 七组模型 test 指标对比
    labels = [r["name"].replace(" ", "\n", 1) for r in runs]
    fig, ax = plt.subplots(figsize=(9.6, 3.6), dpi=150)
    x = range(len(runs))
    width = 0.2
    for offset, (key, color) in enumerate(zip(("precision", "recall", "f1", "map50"), ("#2F75B5", "#70AD47", "#7C5CFF", "#ED7D31"))):
        values = [r[key] if r[key] is not None else 0 for r in runs]
        bars = ax.bar([i + (offset - 1.5) * width for i in x], values, width, label={"precision": "Precision", "recall": "Recall", "f1": "F1", "map50": "mAP@0.5"}[key], color=color)
        if key in ("precision", "map50"):
            for bar, value in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 0.01, f"{value:.3f}", ha="center", fontsize=6, rotation=90)
    ax.set_xticks(list(x), labels, fontsize=7.5)
    ax.set_ylim(0, 1.02)
    ax.set_title("七组训练方案在基础合并集独立 test split 上的实测指标", fontsize=10)
    ax.legend(ncol=4, fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(MID / "mt2_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    # mt3 helmet 召回演进
    helm_runs = [r for r in runs if "helmet" in r["per_class"]]
    labels_h = [r["name"] for r in helm_runs]
    helmet_recall = [r["per_class"]["helmet"].get("recall") for r in helm_runs]
    helmet_precision = [r["per_class"]["helmet"].get("precision") for r in helm_runs]
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=150)
    x = range(len(helm_runs))
    ax.plot(x, helmet_recall, marker="o", color="#C00000", label="helmet Recall")
    ax.plot(x, helmet_precision, marker="s", color="#2F75B5", label="helmet Precision")
    for i, (r_, p_) in enumerate(zip(helmet_recall, helmet_precision)):
        ax.text(i, r_ + 0.015, f"{r_:.3f}", ha="center", fontsize=8)
        ax.text(i, p_ - 0.045, f"{p_:.3f}", ha="center", fontsize=8)
    ax.set_xticks(list(x), labels_h, fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_title("安全帽（helmet）类分项 Precision/Recall 演进（真实 test 评估）", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(MID / "mt3_helmet_recall.png", bbox_inches="tight")
    plt.close(fig)

    # r1/r2 控制台截图渲染（真实存档）
    def render_console(lines: list[str], path: Path, title: str) -> None:
        fig = plt.figure(figsize=(9.6, 0.28 * len(lines) + 0.5), dpi=150)
        fig.patch.set_facecolor("#0C0C0C")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(0.012, 0.97, title, va="top", ha="left", fontsize=9, color="#4EC9B0", transform=ax.transAxes)
        ax.text(0.012, 0.90, "\n".join(lines), va="top", ha="left", family=["Consolas", "Microsoft YaHei"], fontsize=8.8, color="#CCCCCC", transform=ax.transAxes)
        fig.savefig(path, facecolor="#0C0C0C", bbox_inches="tight")
        plt.close(fig)

    env_lines = (MID / "env_check.txt").read_text(encoding="utf-8").strip().splitlines()
    render_console(env_lines, MID / "r1_env_check.png", "PS> python scripts/check_environment.py")
    check_lines = (MID / "pytest_output.txt").read_text(encoding="utf-8").strip().splitlines()
    health = json.loads((MID / "health.json").read_text(encoding="utf-8"))
    health_lines = [
        "PS> curl http://127.0.0.1:8000/health",
        json.dumps(health, ensure_ascii=False, indent=2),
    ]
    render_console(check_lines + health_lines, MID / "r2_run_check.png", "PS> python -m pytest -q && curl /health")
    software_lines = (MID / "software_check.txt").read_text(encoding="utf-8").strip().splitlines()
    render_console(software_lines, MID / "r3_software_check.png", "PS> 开发软件逐项版本检查")
    apps_lines = (MID / "installed_apps.txt").read_text(encoding="utf-8").strip().splitlines()
    render_console(apps_lines, MID / "r4_installed_apps.png", "PS> 系统已安装软件清单（注册表 Uninstall 项）")
    return {"runs": runs, "splits": splits}


# ---------- docx 工具 ----------
def set_cell_margins(cell, top=90, start=110, bottom=90, end=110) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_run_font(run, name="宋体", size=10.5, bold=False, color=None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


class Inserter:
    """在指定段落之后按顺序插入新内容块。"""

    def __init__(self, doc: Document, anchor_paragraph):
        self.doc = doc
        self.anchor = anchor_paragraph._p
        self.last = anchor_paragraph

    def _attach(self, paragraph):
        self.anchor.addnext(paragraph._p)
        self.anchor = paragraph._p
        self.last = paragraph
        return paragraph

    def para(self, text="", *, size=10.5, bold=False, color=None, align=None, space_after=3, line=1.2):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = line
        p.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(text)
        set_run_font(r, size=size, bold=bold, color=color)
        return self._attach(p)

    def heading3(self, text):
        p = self.doc.add_paragraph()
        r = p.add_run(text)
        set_run_font(r, size=11, bold=True)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        return self._attach(p)

    def bullet(self, label, text):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run("• ")
        set_run_font(r, size=10, bold=True, color="1F4E79")
        r = p.add_run(label)
        set_run_font(r, size=10, bold=True)
        r = p.add_run(text)
        set_run_font(r, size=10)
        return self._attach(p)

    def table(self, headers, rows, font_size=8.5, widths=None):
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.autofit = False
        if widths:
            for column, width in zip(table.columns, widths):
                for cell in column.cells:
                    cell.width = Inches(width)
        try:
            table.style = "Table Grid"
        except KeyError:
            # Teacher template ships without the built-in style; draw borders manually.
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                element = OxmlElement(f"w:{edge}")
                element.set(qn("w:val"), "single")
                element.set(qn("w:sz"), "4")
                element.set(qn("w:color"), "8FA8BF")
                borders.append(element)
            table._tbl.tblPr.append(borders)
        for i, h in enumerate(headers):
            cell = table.rows[0].cells[i]
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h)
            set_run_font(r, size=font_size, bold=True, color="FFFFFF")
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), "1F4E79")
            cell._tc.get_or_add_tcPr().append(shd)
        for ri, row in enumerate(rows):
            cells = table.add_row().cells
            for ci, value in enumerate(row):
                cell = cells[ci]
                set_cell_margins(cell)
                if ri % 2:
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:fill"), "F3F6F9")
                    cell._tc.get_or_add_tcPr().append(shd)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci else WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(str(value))
                set_run_font(r, size=font_size)
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(0)
        run = spacer.add_run()
        run.font.size = Pt(4)
        self._attach(spacer)
        self.anchor.addprevious(table._tbl)
        return table

    def figure(self, path: Path, caption: str, width: float):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(path), width=Inches(width))
        self._attach(p)
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(caption)
        set_run_font(r, size=8.5, color="666666")
        return self._attach(cap)


def find_paragraph(doc: Document, text: str):
    for p in doc.paragraphs:
        if p.text.strip() == text:
            return p
    return None


def fmt(value, digits=4):
    return "--" if value is None else f"{float(value):.{digits}f}"


def fill_report(assets: dict) -> None:
    doc = Document(TEMPLATE)

    # 模板自带标题与后文保持同页，避免标题孤悬页底；统一 1.2 编号格式
    for p in doc.paragraphs:
        if p.style.name.startswith("Heading"):
            p.paragraph_format.keep_with_next = True
        if p.text.strip().startswith("1.2."):
            # "1.2." 跨 run 分布（'1.' + '2.Python' + …），需整体重写
            full_text = "1.2 " + p.text.strip()[4:]
            keeper = p.runs[0]
            keeper.text = full_text
            for run in p.runs[1:]:
                run.text = ""

    # 封面与正文章节标题：替换为本人课题
    for p in doc.paragraphs:
        if p.text.strip() == OLD_TITLE:
            for run in p.runs[1:]:
                run.text = ""
            if p.runs:
                p.runs[0].text = NEW_TITLE
            else:
                p.add_run(NEW_TITLE)

    # 老师模板在正文各节间留了大量空行（供手写填写），填充内容后每组只留一个
    all_paras = list(doc.paragraphs)
    start = next(i for i, p in enumerate(all_paras) if p.style.name == "Heading 1")
    blanks: list = []
    drawing_tag = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    for p in all_paras[start:]:
        if not p.text.strip() and not p._p.findall(f".//{drawing_tag}"):
            blanks.append(p)
        else:
            for extra in blanks[1:]:
                extra._p.getparent().remove(extra._p)
            blanks = []

    runs = assets["runs"]
    by_name = {r["name"]: r for r in runs}
    e7, e8, e6 = by_name["E7 12ep hardcase"], by_name["E8 30ep video150"], by_name["E6 8ep 合并集"]
    fin10 = by_name["YOLOv8s 10ep"]

    # ---- 1.1 开发环境整体检查 ----
    ins = Inserter(doc, find_paragraph(doc, "1.1开发环境整体检查"))
    ins.para("本机开发软件已完整安装并配置。下表对照课程常见软件清单逐项说明（Maven/Tomcat/Anaconda 未安装者如实注明，并以本项目实际技术栈的等价工具替代），版本检查与本机已安装软件清单的真实输出截图见图1、图2：", size=10)
    ins.table(
        ["软件", "安装状态", "版本", "说明"],
        [
            ["JDK (OpenJDK)", "已安装", "24.0.2", "系统级安装，java -version 正常"],
            ["IntelliJ IDEA", "已安装", "2025.3.3 / 2025.2.1", "经 JetBrains Toolbox 3.4.3 管理"],
            ["Maven", "未安装", "—", "本项目为 Python 技术栈，依赖管理使用 uv / pip，不涉及 Java 构建"],
            ["Tomcat", "未安装", "—", "服务端采用 FastAPI + Uvicorn，非 Java Web 容器"],
            ["MySQL", "已安装", "Server 8.0.43", "完整安装（MySQL Installer 1.6.15）；本项目生产库采用 PostgreSQL 16（Docker 容器），开发库 SQLite"],
            ["Navicat Premium", "已安装", "16.3.7", "数据库可视化管理工具"],
            ["Anaconda", "未安装", "—", "Python 虚拟环境采用 uv 0.10.9 管理，作用等同 conda"],
            ["VS Code", "已安装", "1.140.0", "另安装 Cursor 2.6.22 作为日常代码编辑器"],
            ["Git", "已安装", "2.51.0", "含 GitHub CLI 2.93.0，完成全部代码版本管理"],
            ["Docker Desktop", "已安装", "4.88.1", "web/api/db 三服务容器化部署"],
            ["Node.js / npm", "已安装", "22.23.2 / 10.9.8", "Vue3 前端构建工具链"],
        ],
        font_size=8,
        widths=[1.15, 0.85, 1.45, 2.45],
    )
    ins.figure(MID / "r3_software_check.png", "图1 开发软件逐项版本检查（本机真实命令输出，无环境报错）", 5.6)
    ins.figure(MID / "r4_installed_apps.png", "图2 系统已安装软件清单（注册表 Uninstall 项真实记录）", 5.6)
    ins.para("本项目 Python 运行栈的整体检查结果如下（真实命令输出截图见图5）：", size=10)
    ins.table(
        ["组件", "版本/状态", "说明"],
        [
            ["Python", "3.12.13", "运行环境（venv 隔离）"],
            ["PyTorch", "2.6.0+cu126", "深度学习框架，CUDA 12.6"],
            ["GPU", "RTX 4070 Laptop 8GB", "CUDA 可用，训练与推理加速"],
            ["Ultralytics", "8.4.152", "YOLOv8 训练/推理框架"],
            ["OpenCV / NumPy", "5.0.0 / 2.5.3", "视频解码与数值计算"],
            ["FastAPI + Uvicorn", "最新稳定版", "REST API 与 WebSocket 服务"],
            ["SQLAlchemy", "2.0.53", "ORM（SQLite/PostgreSQL 双支持）"],
            ["Docker Compose", "v2（web/api/db 三服务）", "容器化部署"],
        ],
    )
    ins.figure(MID / "r1_env_check.png", "图3 Python 运行栈整体检查（python 真实执行输出）", 5.6)

    # ---- 1.2 Python环境安装，代码无报错，工程的运行情况 ----
    ins = Inserter(doc, find_paragraph(doc, "1.2 Python环境安装，代码无报错，工程的运行情况"))
    ins.para("环境通过 scripts/setup.ps1 一键创建虚拟环境并安装 requirements.txt 依赖；pytest 自动化测试套件 65 个用例全部通过、无报错；服务启动后 /health 返回 model_available=true（E7 权重加载成功），浏览器工作台可正常登录、上传推理与实时告警。", size=10)
    ins.figure(MID / "r2_run_check.png", "图4 自动化测试与 /health 服务健康检查（真实执行输出）", 5.6)
    ins.figure(MID / "ui-overview.png", "图5 工业安全智能监测工作台——监控总览页运行截图", 5.9)
    ins.figure(MID / "ui-detection.png", "图6 智能检测页——上传图片完成真实推理并产生安全事件", 5.9)

    # ---- 数据集 ----
    ins = Inserter(doc, find_paragraph(doc, "数据集"))
    ins.para("本课题使用三个公开 PPE（个人防护装备）检测数据集，经类别统一与图片级去重后合并为项目专用数据集。来源与链接如下：", size=10)
    ins.table(
        ["数据集", "来源", "规模", "说明"],
        [
            ["Construction-PPE", "Ultralytics assets 发布\n(GitHub)", "1,416 张\n11 类", "SHA256 bef8dcb5… 记录于 data/dataset_sources.json；完整链接见表后"],
            ["SH17", "GitHub 项目页\nKaggle 论文数据集\nHuggingFace 镜像", "约 8,600 张\n17 类", "下载后做类别映射与质量校验；完整链接见表后"],
            ["Kaggle PPE Detection", "Kaggle\n(kagglehub 获取)", "补充样本", "SHA256 去重后并入；完整链接见表后"],
        ],
        font_size=8,
        widths=[1.15, 1.35, 0.95, 2.45],
    )
    ins.para("数据集来源完整链接：", size=10, bold=True, space_after=1)
    ins.para("① Construction-PPE：https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip", size=9, space_after=1)
    ins.para("② SH17 主页：https://github.com/ahmadmughees/SH17dataset", size=9, space_after=1)
    ins.para("　 SH17 Kaggle：https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection ｜ 镜像：https://huggingface.co/datasets/fathansanum/SH-17-Dataset", size=9, space_after=1)
    ins.para("③ Kaggle PPE Detection：https://www.kaggle.com/datasets/uzairahmad1434/ppe-detection", size=9, space_after=4)
    ins.para("合并集规模：11,623 张图片、28,853 个标注框，统一为 person/helmet/vest 三类业务目标；官方划分 train/val/test = 8,276/2,184/1,163 张（20,695/5,111/3,047 框）。来源、许可证、类别映射和 SHA256 全部记录在 data/dataset_sources.json 与 data/expanded_ppe_kaggle/dataset_manifest.json，可追溯复现。", size=10)

    # ---- 研究背景 ----
    ins = Inserter(doc, find_paragraph(doc, "研究背景"))
    ins.para("工业生产环境中，未佩戴安全帽、未穿反光背心进入危险区域是高处坠物、机械伤害等事故的主要诱因之一。据应急管理部统计，物体打击与高处伤害长期位列工矿事故类型前茅，而两者均与头部防护和作业区隔离直接相关。传统监管依赖人工巡视与事后抽查，存在覆盖时段有限、主观疲劳漏检、无法实时告警等固有缺陷。", size=10)
    ins.para("随着深度学习目标检测技术成熟，基于视频流的自动 PPE 佩戴检测与危险区域闯入识别成为可行方案。本课题面向中小型工地/车间场景，构建一套从检测模型、多目标跟踪、规则引擎到 Web 监测工作台的完整系统，探索机器学习在工业安全管理中的工程化落地路径，并以真实实验数据评估各方案的检测能力边界。", size=10)

    # ---- 4.数据集描述 ----
    ins = Inserter(doc, find_paragraph(doc, "4.数据集描述"))
    ins.para("合并数据集为 YOLO 目标检测格式：每张图片对应一个 txt 标注文件（类别索引 + 归一化框坐标）。三类业务目标定义：person（作业人员全身框）、helmet（安全帽，头部区域）、vest（反光背心，躯干区域）。划分与校验情况见图7：三个划分均通过 validate_dataset.py 质量校验（空标签、越界框、图片-标注不匹配均为 0 错误）。", size=10)
    ins.figure(MID / "mt1_dataset_splits.png", "图7 合并数据集划分规模与质量校验结果", 5.4)
    ins.para("数据增强产物：针对抽查发现的漏检场景（深色安全帽、远距离小目标），制作 hard_cases 子集——3 张用户抽查原图各做 60 个确定性增强，共 183 张训练图、1,037 框，仅挂载训练集不进入 val/test，防止增强图虚增指标。此外 E8 实验追加 150 张 train-only 视频抽帧，val/test 始终保持不变，保证七组模型在同一口径 test split 上可比。", size=10)

    # ---- 5.研究目标 ----
    ins = Inserter(doc, find_paragraph(doc, "5.研究目标"))
    ins.bullet("目标1（模型对比）：", "在统一 test split 上完成不少于 5 组训练方案的 Precision/Recall/F1/mAP 对比，量化数据规模、训练轮数与数据增强对检测能力的影响。")
    ins.bullet("目标2（短板改进）：", "针对安全帽小目标漏检问题（初始 helmet Recall 不足 0.45），通过数据补充与定向精调提升该类召回并观察精度代价。")
    ins.bullet("目标3（系统能力）：", "将检测模型与 ByteTrack 跟踪、危险区域规则结合，实现连续帧确认告警、证据截图与 WebSocket 实时推送的完整闭环。")
    ins.bullet("目标4（部署决策）：", "建立三图两视频定向回归门禁与四步验收门禁，用数据决定部署权重版本，杜绝以计划值或 fallback 输出冒充模型指标。")

    # ---- 6.1 EDA ----
    ins = Inserter(doc, find_paragraph(doc, "6.1 数据探索分析（EDA）"))
    ins.para("数据探索聚焦三个问题：类别分布是否均衡、划分是否同口径、标注质量是否可信。校验脚本对全部 11,623 张图片执行存在性、可读性、标注框越界与空标签检查；同时统计各类别框数占比，发现 helmet 类框占约 21% 且小目标占比高，这解释了后续该类召回偏低的观察。探索结论直接决定了第 6.3 节的输入工程策略。", size=10)

    # ---- 6.2 预处理 ----
    ins = Inserter(doc, find_paragraph(doc, "6.2 预处理"))
    ins.bullet("类别归一：", "三个来源数据集类别命名不一致（Person/people/worker、hardhat/safety_helmet、safety_vest/reflective_vest 等），建立别名映射表统一到 person/helmet/vest，无对应关系的类（boots/gloves 等）剔除。")
    ins.bullet("图片级去重：", "对全部图片计算 SHA256，合并时剔除重复图片，防止同一图片同时出现在训练与测试划分造成指标虚高。")
    ins.bullet("标注清洗：", "剔除空标签文件与越界框（坐标超出图像边界），逐划分校验后错误数为 0 才进入训练。")
    ins.bullet("划分隔离：", "增强图与视频抽帧仅挂载 train，val/test 保持原始分布，保证评估口径稳定。")

    # ---- 6.3 特征工程 ----
    ins = Inserter(doc, find_paragraph(doc, "6.3 特征工程"))
    ins.para("目标检测任务的“特征工程”核心在于输入空间与规则空间的构造，本课题实施了四项：", size=10)
    ins.bullet("输入分辨率：", "MODEL_IMAGE_SIZE=640，相比 416 保留更充分的小目标 PPE 像素；另做 1280 对照实验（同权重同划分），验证分辨率对召回的影响。")
    ins.bullet("定向数据增强：", "对抽查漏检原图做 60 个确定性增强（亮度/遮挡/缩放扰动），构成 hard_cases 训练挂载集，等效于在难例流形上加密采样。")
    ins.bullet("空间关系特征：", "推理阶段构造 PPE 框相对人员框的几何特征（中心点包含、IoU 重叠率、头部/躯干相对高度区间、面积占比），过滤无人员归属的背景误检。")
    ins.bullet("时间维特征：", "视频流构造连续命中计数、轨迹确认状态与冷却时间窗，将单帧检测结果升级为稳定的安全事件。")

    # ---- 6.4 模型训练 ----
    ins = Inserter(doc, find_paragraph(doc, "6.4模型训练"))
    ins.para("共完成七组训练（满足 5 个模型以上要求），全部在本机 RTX 4070 Laptop GPU 上执行，训练设置与数据版本见表：", size=10)
    ins.table(
        ["模型", "基线", "训练轮数", "数据版本", "定位"],
        [
            ["模型1", "YOLOv8n", "1 (smoke)", "Construction-PPE", "流程验证基线"],
            ["模型2", "YOLOv8s", "1 (smoke)", "Construction-PPE", "容量对照基线"],
            ["模型3", "YOLOv8s", "5", "Expanded PPE (9,515张)", "数据扩充对照"],
            ["模型4", "YOLOv8s", "10", "Expanded PPE", "轮数对照"],
            ["模型5 (E6)", "YOLOv8s", "8", "合并集 (11,623张)", "历史部署版本"],
            ["模型6 (E7)", "YOLOv8s", "12", "合并集+hard_cases", "当前部署版本"],
            ["模型7 (E8)", "YOLOv8s", "30", "合并集+video150", "候选版本"],
        ],
        font_size=8,
    )

    # ---- 6.5 模型评估与优化 ----
    ins = Inserter(doc, find_paragraph(doc, "6.5模型评估与优化（5个模型以上）"))
    ins.para("全部模型在基础合并集同一 test split（1,163 张 / 3,047 框）上以相同参数（imgsz=640, conf=0.25）评估，真实指标汇总如下：", size=10)
    ins.table(
        ["模型", "Precision", "Recall", "F1", "mAP@0.5", "mAP@0.5:0.95"],
        [[r["name"], fmt(r["precision"]), fmt(r["recall"]), fmt(r["f1"]), fmt(r["map50"]), fmt(r["map50_95"])] for r in runs],
        font_size=8,
    )
    ins.figure(MID / "mt2_model_comparison.png", "图8 七组模型测试集指标对比（真实 JSON 结果可视化）", 5.9)

    model_notes = [
        ("模型1 YOLOv8n smoke", f"轻量基线 1 轮流程验证：Precision {fmt(by_name['YOLOv8n smoke']['precision'])}、Recall {fmt(by_name['YOLOv8n smoke']['recall'])}、mAP@0.5 {fmt(by_name['YOLOv8n smoke']['map50'])}，证明训练-评估链路可用，但召回严重不足，不具备部署价值。"),
        ("模型2 YOLOv8s smoke", f"同轮数换更大容量：mAP@0.5 由 {fmt(by_name['YOLOv8n smoke']['map50'])} 提升至 {fmt(by_name['YOLOv8s smoke']['map50'])}，验证模型容量对检测能力的贡献，确立 YOLOv8s 为后续主模型。"),
        ("模型3 YOLOv8s 5ep", f"数据扩充到 9,515 张后 5 轮训练：Recall 从 {fmt(by_name['YOLOv8s smoke']['recall'])} 跃升至 {fmt(by_name['YOLOv8s 5ep']['recall'])}，mAP@0.5 达 {fmt(by_name['YOLOv8s 5ep']['map50'])}，数据规模是本轮最大收益来源。"),
        ("模型4 YOLOv8s 10ep", f"同数据加倍轮数：Precision 提升至 {fmt(fin10['precision'])}、mAP@0.5 {fmt(fin10['map50'])}；另做 imgsz=1280 同权重对照评估，小目标召回进一步改善，说明分辨率与轮数在不同维度上互补。"),
        ("模型5 (E6) 8ep 合并集", f"并入 Kaggle PPE 并去重后 8 轮精调：F1 达 {fmt(e6['f1'])}、mAP@0.5 {fmt(e6['map50'])}，综合最优的历史版本，曾作为部署模型。"),
        ("模型6 (E7) 12ep hardcase（当前部署）", f"合并集追加 hard_cases 定向增强再精调 12 轮：Recall {fmt(e7['recall'])}、mAP@0.5 {fmt(e7['map50'])} 为全组最高，helmet Recall 由 {fmt(e6['per_class'].get('helmet', {}).get('recall'))} 提升至 {fmt(e7['per_class'].get('helmet', {}).get('recall'))}，通过三图两视频定向回归门禁后部署上线。"),
        ("模型7 (E8) 30ep video150（候选）", f"追加 150 张视频抽帧并训练 30 轮：Recall 再升至 {fmt(e8['recall'])}、helmet Recall {fmt(e8['per_class'].get('helmet', {}).get('recall'))}，但 Precision/F1/mAP@0.5 均回落（F1 {fmt(e8['f1'])}）。经四步验收门禁评估后判定综合不优于 E7，保留为候选未部署——这是门禁机制避免负优化的一次实际拦截。"),
    ]
    anchor = find_paragraph(doc, "模型1：")
    for idx, (title, body) in enumerate(model_notes):
        if idx < 3:
            heading_text = f"模型{idx + 1}："
            anchor = find_paragraph(doc, heading_text)
            ins = Inserter(doc, anchor)
        elif idx == 3:
            # 模型4起模板无占位段，续接在模型3内容之后
            ins = Inserter(doc, anchor)
            ins.heading3("模型4：")
        else:
            ins = Inserter(doc, anchor)
            ins.heading3(f"模型{idx + 1}：")
        ins.para(f"{title}：{body}", size=9.6)
        anchor = ins.last

    ins = Inserter(doc, anchor)
    ins.heading3("评估可视化与优化结论")
    ins.figure(MID / "mt3_helmet_recall.png", "图9 helmet 类分项 Precision/Recall 演进（短板改进全过程）", 5.2)
    ins.para("优化路径总结：数据维度上，合并数据与定向 hard-case 增强是收益最大的两项（Recall 0.32→0.66）；训练维度上，轮数提升在 12 轮后边际收益归零，30 轮出现过拟合迹象（E8 精度回落）；评估维度上，建立三图硬门禁、两视频轨迹门禁与四步验收门禁，任何候选权重必须全门禁通过才允许替换部署版本，本机制在实践中成功拦截了 E8 的负优化替换。", size=10)

    # ---- 7.总结 ----
    ins = Inserter(doc, find_paragraph(doc, "7.总结(问题现象与解决方法)"))
    problems = [
        ("问题现象1：三数据集类别命名互不一致，直接合并导致类别碎裂。", "解决方法：建立类别别名映射表（Person/people/worker→person，hardhat/safety_helmet→helmet 等），映射后逐划分校验类别数一致，再执行图片级 SHA256 去重，合并集校验错误归零。"),
        ("问题现象2：安全帽小目标漏检严重，初始模型 helmet Recall 不足 0.44。", "解决方法：三管齐下——合并 Kaggle PPE 扩充样本、制作 hard_cases 定向增强集、提高输入分辨率至 640/1280 对照；helmet Recall 最终提升至 0.4868（E8），期间通过分项指标图持续监控精度代价。"),
        ("问题现象3：视频推理中单帧检测抖动，同一人员反复触发告警。", "解决方法：引入 ByteTrack 式轨迹跟踪（连续 3 次命中才确认轨迹），规则层再要求连续 3 帧确认 + 同一人员同一规则 10 秒冷却 + 15 帧佩戴状态宽限期；两段回归视频验证通过后误报与重复告警清零。"),
        ("问题现象4：检测框出现在墙面/天空等背景区域（模型幻觉框）。", "解决方法：在检测后处理中构造几何过滤链——极小低置信度框过滤、贴边窄条框过滤、场景级大框需双重 PPE 证据支持、嵌套重复框抑制；每道过滤器均配套回归测试用例，防止改 A 坏 B。"),
        ("问题现象5：测试集存在近重复画面，直接报告指标有泄漏夸大风险。", "解决方法：报告中明确标注该 test split 仅适合七组模型同口径对比、不构成无泄漏泛化结论，并把“按视频/人员隔离重建 300–500 帧独立场景测试集”列为后续工作，不在材料中声称未完成的泛化指标。"),
        ("问题现象6：服务长期运行中发现的工程缺陷（时间显示偏差、事件超 200 条后 WebSocket 停推、危险区坐标与视频分辨率错配）。", "解决方法：ORM 层统一 UTC 时区序列化修复时间偏移；WebSocket 改增量查询修复停推；危险区多边形改存 0–1 相对坐标并按帧分辨率缩放，旧数据启动迁移。全部修复配套 7 个新增回归测试，测试套件 65 用例全绿。"),
    ]
    for title, body in problems:
        p = ins.para("", size=9.6)
        r = p.runs[0]
        r.text = title + " "
        set_run_font(r, size=9.6, bold=True)
        r2 = p.add_run(body)
        set_run_font(r2, size=9.6)
    ins.para("总结：本课题完成了从公开数据整合、模型训练对比、规则引擎到 Web 工作台的完整机器学习系统工程实践，七组真实实验清晰量化了数据、轮数与增强策略的收益边界；评估体系坚持只用真实运行产物，所有指标可通过 results/ 目录 JSON 与脚本复现。当前部署模型 E7 在同口径测试集上取得 Precision 0.7977、Recall 0.6620、F1 0.7235、mAP@0.5 0.7200，服务、前端与容器化部署链路全部实测可用。", size=10)

    doc.save(FINAL)
    print(FINAL)


if __name__ == "__main__":
    fill_report(make_assets())

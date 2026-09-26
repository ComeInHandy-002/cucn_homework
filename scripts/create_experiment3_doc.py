"""Build the completed Experiment 3 report from the teacher's Word template."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"C:\Users\19505\Desktop\学号_姓名_实验三--人工智能算法.doc")
WORK = ROOT / ".docx_task3_work"
TEMPLATE_DOCX = WORK / "template.docx"
FINAL = ROOT / "学号_姓名_实验三--人工智能算法_完成版.docx"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


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


def clear_cell(cell) -> None:
    for p in list(cell.paragraphs):
        p._element.getparent().remove(p._element)
    cell.add_paragraph()


def set_run_font(run, name="宋体", size=10.5, bold=False, color=None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_para(cell, text="", *, size=10.5, bold=False, color=None, align=None, space_before=0, space_after=3, line=1.15):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold, color=color)
    return p


def add_heading(cell, text):
    return add_para(cell, text, size=12, bold=True, space_before=6, space_after=4, line=1.0)


def add_bullet(cell, label, text):
    p = add_para(cell, size=10, space_after=2, line=1.1)
    r = p.add_run("• ")
    set_run_font(r, size=10, bold=True, color="1F4E79")
    r = p.add_run(label)
    set_run_font(r, size=10, bold=True)
    r = p.add_run(text)
    set_run_font(r, size=10)
    return p


def add_table(cell, headers, rows, widths=None, font_size=8.2):
    table = cell.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        set_cell_shading(c, "1F4E79")
        set_cell_margins(c, 70, 80, 70, 80)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        set_run_font(r, size=font_size, bold=True, color="FFFFFF")
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            c = cells[i]
            set_cell_margins(c, 65, 75, 65, 75)
            if ri % 2:
                set_cell_shading(c, "F3F6F9")
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i != 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            set_run_font(r, size=font_size)
    for p in cell.paragraphs[-1:]:
        p.paragraph_format.space_after = Pt(3)
    return table


def make_charts() -> tuple[Path, Path]:
    chart_dir = WORK / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    runs = ["YOLOv8n\nsmoke", "YOLOv8s\nsmoke", "YOLOv8s\n5 epoch", "YOLOv8s\n10 epoch", "E6\n8 epoch", "E7\n12 epoch", "E8\n30 epoch"]
    precision = [0.6844, 0.7545, 0.7705, 0.8361, 0.8332, 0.7977, 0.7803]
    recall = [0.3074, 0.3208, 0.5297, 0.5876, 0.6441, 0.6620, 0.6732]
    map50 = [0.2970, 0.3771, 0.5939, 0.6616, 0.7151, 0.7200, 0.7095]
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(8.2, 3.2), dpi=180)
    x = list(range(len(runs)))
    w = 0.25
    ax.bar([i - w for i in x], precision, width=w, label="Precision", color="#2F75B5")
    ax.bar(x, recall, width=w, label="Recall", color="#70AD47")
    ax.bar([i + w for i in x], map50, width=w, label="mAP@0.5", color="#ED7D31")
    ax.set_ylim(0, 1)
    ax.set_ylabel("score")
    ax.set_xticks(x, runs, fontsize=8)
    ax.set_title("六组训练方案与 E8 候选模型指标对比", fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=3, fontsize=8, loc="upper left")
    fig.tight_layout()
    model_chart = chart_dir / "model_comparison.png"
    fig.savefig(model_chart, bbox_inches="tight")
    plt.close(fig)

    names = ["person", "helmet", "vest"]
    e7 = [0.8267, 0.5292, 0.8040]
    e8 = [0.8254, 0.5224, 0.7806]
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=180)
    x = list(range(len(names)))
    ax.bar([i - 0.18 for i in x], e7, width=0.36, label="E7 当前部署", color="#4472C4")
    ax.bar([i + 0.18 for i in x], e8, width=0.36, label="E8 候选", color="#A5A5A5")
    ax.set_ylim(0, 1)
    ax.set_xticks(x, names)
    ax.set_ylabel("mAP@0.5")
    ax.set_title("业务三类分项 mAP@0.5", fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    class_chart = chart_dir / "class_comparison.png"
    fig.savefig(class_chart, bbox_inches="tight")
    plt.close(fig)
    return model_chart, class_chart


def fill_report() -> None:
    WORK.mkdir(exist_ok=True)
    # The legacy template is converted once through Word before python-docx edits.
    if not TEMPLATE_DOCX.exists():
        raise FileNotFoundError(f"Converted template missing: {TEMPLATE_DOCX}")
    shutil.copy2(TEMPLATE_DOCX, FINAL)
    doc = Document(FINAL)
    first = doc.tables[0].cell(0, 0)
    second = doc.tables[1].cell(0, 0)
    summary = doc.tables[1].cell(1, 0)
    for cell in (first, second, summary):
        clear_cell(cell)
        set_cell_margins(cell)

    add_heading(first, "一、实验目的")
    add_bullet(first, "流程掌握：", "完成 PPE 数据清洗、标注统一、特征关联、模型训练、评估和服务化推理的完整流程。")
    add_bullet(first, "算法实践：", "使用 YOLOv8、ByteTrack 和几何规则实现人员安全帽、反光背心及危险区域监测。")
    add_bullet(first, "指标分析：", "使用 Precision、Recall、F1、mAP@0.5 和 mAP@0.5:0.95 对模型和系统行为进行对比。")

    add_heading(first, "二、实验环境")
    add_bullet(first, "硬件：", "NVIDIA GeForce RTX 4070 Laptop GPU，CUDA 12.6；本机同时支持 CPU fallback。")
    add_bullet(first, "软件：", "Windows 10/11、Python 3.12.13、PowerShell、VS Code、FastAPI、Docker Compose。")
    add_bullet(first, "主要库：", "PyTorch 2.6.0+cu126、Ultralytics 8.4.152、OpenCV、Pillow、NumPy、SQLAlchemy、pytest。")
    add_bullet(first, "数据：", "Construction-PPE、SH17 和 Kaggle PPE 合并集；统一类别为 person、helmet、vest。")

    add_heading(first, "三、实验内容及要求")
    add_para(first, "本实验以工业安全智能监测系统为对象。先按图片 SHA256 去重并检查标签，再将不同来源的类别映射为三类业务目标；训练 YOLOv8n/YOLOv8s，对 test split 计算指标；推理阶段使用 ByteTrack 维持人员 track_id，并通过 PPE 空间关联、危险区域点在多边形内判断和连续帧告警规则完成系统输出。", size=9.4, space_after=4, line=1.12)
    add_para(first, "数据规模：合并集共 11,623 张图片、28,853 个标注框；train/val/test 分别为 8,276/2,184/1,163 张。测试集存在部分重压缩近重复画面，因此结果用于 E6/E7/E8 同口径对比，不包装为无泄漏泛化指标。", size=9.4, space_after=4, line=1.12)
    add_para(first, "六个算法模块及实现方式：", size=9.8, bold=True, space_after=2)
    modules = [
        ("1 YOLOv8n 检测", "轻量基线模型，完成训练、test 评估和误检观察。"),
        ("2 YOLOv8s 检测", "主模型，对比更大容量模型的 Precision、Recall 和 mAP。"),
        ("3 ByteTrack 跟踪", "利用检测框轨迹关联生成稳定 track_id；不做额外梯度训练，以连续命中门限验证。"),
        ("4 PPE 空间关联", "以人员框与 PPE 框的 IoU/中心点包含关系进行安全帽和背心归属。"),
        ("5 危险区多边形判断", "取人员脚底中心点，使用点在多边形内规则判断 intrusion。"),
        ("6 时间确认与冷却", "连续 3 帧确认，同一人员同一规则 10 秒冷却；用回归视频验证误报和重复告警。"),
    ]
    for title, body in modules:
        add_bullet(first, title + "：", body)

    add_heading(first, "四、主要操作步骤（源码、训练结果和运行截图）")
    steps = [
        ("1 环境检查", "运行 `python scripts/check_environment.py`，确认 CUDA、Ultralytics、模型路径和目录权限。"),
        ("2 数据预处理", "执行数据下载、标签转换、SHA256 去重和 `validate_dataset.py`；将类别压缩为 person/helmet/vest。"),
        ("3 模型训练", "先运行 YOLOv8n/YOLOv8s smoke，再进行 Expanded PPE、Kaggle 合并集和 hard-case 精调；每次保存权重、参数和 results.csv。"),
        ("4 评估与对比", "运行 `evaluate_yolo.py` 生成 JSON 指标；运行 `evaluate_demo_set.py` 和 `evaluate_video_cases.py` 检查已知图片/视频回归。"),
        ("5 服务推理", "启动 FastAPI，登录 admin/admin123，上传图片或 MP4；前端展示标注图、检测统计、事件证据和任务进度。"),
        ("6 E8 门禁", "E8 完成 30/30 轮后按 test、hard-case、demo、video 顺序自动验收。E8 Recall 上升但 Precision、F1、mAP@0.5 下降，故保留 E7 部署。"),
    ]
    add_table(first, ["步骤", "实际操作与输出"], steps, font_size=8.3)
    p = first.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("图1  系统图片检测工作台运行截图")
    set_run_font(r, size=8.5, color="666666")
    p = first.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(str(ROOT / "results" / "ui-validation" / "image-result.png"), width=Inches(5.65))

    model_chart, class_chart = make_charts()
    p = first.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("图2  训练方案指标对比（实际 JSON 结果）")
    set_run_font(r, size=8.5, color="666666")
    p = first.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(str(model_chart), width=Inches(5.8))

    add_heading(second, "五、实验思考（问题、分析与解决办法）")
    reflections = [
        ("问题1：安全帽类别漏检和黑色安全帽误判。", "初始模型对小目标、遮挡和深色安全帽的召回较低。解决办法是补充 Kaggle PPE 数据、保留 hard-case 原图及增强图，并在人员框内增加 PPE 空间约束；E7 helmet Recall 提升到 0.4548，E8 进一步为 0.4868，但仍需独立场景数据继续验证。"),
        ("问题2：单帧检测会抖动并重复告警。", "将人员检测送入 ByteTrack，以连续 3 次命中确认轨迹；规则层要求连续 3 帧触发，同一人员同一规则 10 秒冷却。两段视频回归均通过，短暂机械候选不会进入统计和事件。"),
        ("问题3：不同数据集类别名称不一致。", "建立类别别名映射，将 Person/people/worker 归一到 person，将 hardhat/safety_helmet 归一到 helmet，将 safety_vest/reflective_vest 归一到 vest，并对越界框、空标签和重复图像做质量检查。"),
        ("问题4：训练与视频推理显卡利用率不稳定。", "视频管线使用有界队列、batch=8、CUDA half 精度和单 GPU worker；通过内存上限避免并发任务导致显存崩溃。当前配置以稳定演示为优先，正式 720p/15 FPS 仍需单独基准测试。"),
        ("问题5：测试集存在近重复画面。", "报告中明确说明该 test split 适合 E7/E8 同口径比较，不能作为严格无泄漏泛化结论；后续应按视频或人员重新划分 300–500 帧独立场景测试集。"),
    ]
    for title, body in reflections:
        p = add_para(second, size=9.2, space_after=2, line=1.12)
        r = p.add_run(title + " ")
        set_run_font(r, size=9.2, bold=True)
        r = p.add_run(body)
        set_run_font(r, size=9.2)
    p = second.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("图3  模型实验页面与结构化检测结果截图已随项目保留")
    set_run_font(r, size=8.5, color="666666")
    p = second.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(str(class_chart), width=Inches(5.4))

    add_heading(summary, "实验小结")
    add_para(summary, "本实验完成了从公开 PPE 数据下载、清洗、类别统一、模型训练、指标评估到 FastAPI 工作台演示的完整人工智能算法流程。六组训练方案表明，扩大数据和增加训练轮数能够显著提高整体检测能力；E7 在同口径 test split 上取得 Precision 0.7977、Recall 0.6620、F1 0.7235、mAP@0.5 0.7200，当前作为服务部署模型。E8 完成 30 轮训练并通过四项门禁，但综合指标不优于 E7，因此保留为候选模型而不直接替换。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "通过本次实验，我进一步理解了检测模型指标、目标关联、跟踪稳定性和规则告警之间的关系。后续工作是补充按视频/人员隔离的独立场景数据，完成 720p 性能和跟踪规则消融实验，并在更大规模人工标注数据上继续改善安全帽小目标召回。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "证据文件：`docs/EXPERIMENTS.md`、`docs/TEST_REPORT.md`、`results/e8-video150-gate-review.json`；源码与运行说明已随项目提交。", size=8.6, color="666666", line=1.1)

    # Remove empty first paragraph introduced by clear_cell to avoid excess top gap.
    for cell in (first, second, summary):
        if cell.paragraphs and not cell.paragraphs[0].text.strip():
            p = cell.paragraphs[0]
            p._element.getparent().remove(p._element)
    doc.save(FINAL)
    print(FINAL)


if __name__ == "__main__":
    fill_report()

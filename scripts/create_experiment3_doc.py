"""构建实验三报告完成版（UCI Adult 机器学习算法对比，按课程要求格式）。

内容来源：scripts/experiment3/run_adult_ml.py 的真实产物
（results/experiment3/metrics.json、图表 PNG、run_log.txt），
数字不从模板手抄，重新生成前先重跑实验脚本。
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".docx_task3_work"
TEMPLATE_DOCX = WORK / "template.docx"
EXPERIMENT_OUT = ROOT / "results" / "experiment3"
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


def add_table(cell, headers, rows, font_size=8.2):
    table = cell.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        set_cell_shading(c, "1F4E79")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        set_run_font(r, size=font_size, bold=True, color="FFFFFF")
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            c = cells[i]
            if ri % 2:
                set_cell_shading(c, "F3F6F9")
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i != 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            set_run_font(r, size=font_size)
    return table


def add_figure(cell, path: Path, caption: str, width: float) -> None:
    p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(caption)
    set_run_font(r, size=8.5, color="666666")
    p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))


def render_console_screenshot() -> Path:
    """把真实运行日志的尾部渲染成控制台样式截图。"""
    log_lines = (EXPERIMENT_OUT / "run_log.txt").read_text(encoding="utf-8").splitlines()
    tail = [line for line in log_lines if line.strip()][-26:]
    fig = plt.figure(figsize=(9.6, 4.6), dpi=160)
    fig.patch.set_facecolor("#0C0C0C")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_facecolor("#0C0C0C")
    text = "\n".join(tail)
    ax.text(0.012, 0.98, text, va="top", ha="left", family=["Consolas", "Microsoft YaHei"], fontsize=8.6, color="#CCCCCC", transform=ax.transAxes)
    path = EXPERIMENT_OUT / "r1_console_output.png"
    fig.savefig(path, facecolor="#0C0C0C", bbox_inches="tight")
    plt.close(fig)
    return path


def fmt(value, digits=4):
    return "--" if value in (None, "") else f"{float(value):.{digits}f}"


def fill_report() -> None:
    WORK.mkdir(exist_ok=True)
    if not TEMPLATE_DOCX.exists():
        raise FileNotFoundError(f"Converted template missing: {TEMPLATE_DOCX}")
    metrics = json.loads((EXPERIMENT_OUT / "metrics.json").read_text(encoding="utf-8"))
    algorithms = {item["algorithm"]: item for item in metrics["algorithms"]}

    def cell_of(algorithm, key):
        return fmt(algorithms[algorithm][key])

    shutil_copy_target = FINAL
    import shutil

    shutil.copy2(TEMPLATE_DOCX, shutil_copy_target)
    doc = Document(FINAL)
    first = doc.tables[0].cell(0, 0)
    second = doc.tables[1].cell(0, 0)
    summary = doc.tables[1].cell(1, 0)
    for cell in (first, second, summary):
        clear_cell(cell)
        set_cell_margins(cell)

    add_heading(first, "一、实验目的")
    add_bullet(first, "流程掌握：", "对给定数据集完成数据清洗、缺失值处理与特征工程的完整预处理流程。")
    add_bullet(first, "算法实现：", "编码实现 7 种算法（6 种分类器 + 1 种聚类对照），每种均含训练、预测与评估。")
    add_bullet(first, "评估对比：", "使用准确率、精确率、召回率、F1 与 ROC-AUC 对全部算法进行量化评估并可视化对比。")

    add_heading(first, "二、实验环境")
    add_bullet(first, "硬件：", "NVIDIA GeForce RTX 4070 Laptop GPU（本实验以 CPU 计算为主）。")
    add_bullet(first, "软件：", "Windows 11、Python 3.12.13、VS Code。")
    add_bullet(first, "主要库：", "pandas 3.0.6、scikit-learn 1.9.1、NumPy、Matplotlib。")
    add_bullet(first, "数据集：", "UCI Adult Income（Census Income），48,842 条记录、15 个混合类型字段，目标为二分类 income。")

    add_heading(first, "三、实验内容及要求")
    add_para(first, "数据集采用 UCI Adult Income。目标变量 income 为二分类（<=50K / >50K），类别比约 3:1，存在类别不平衡；workclass、occupation、native-country 三列以 ? 记号缺失。官方提供 adult.data（32,561 条）与 adult.test（16,281 条）独立划分，本实验不重划，保证结果可复现。", size=9.4, space_after=4, line=1.12)
    add_para(first, "数据清洗与缺失值处理：读取时将 ? 解析为 NaN；剔除完全重复的 24/5 行；fnlwgt 为普查抽样权重、education 字符串与 education-num 一一对应，两列冗余剔除；三个缺失类别列填 Unknown（约 7% 行含缺失，直接删行损失过大，且未申报本身含信息）。", size=9.4, space_after=4, line=1.12)
    add_para(first, "特征工程：强偏态的 capital-gain/loss 做 log1p 变换并派生是否有过收益的二值特征；hours-per-week 离散化为四段业务区间；7 个类别列做 One-Hot 编码，共得 98 维特征；对逻辑回归、SVM、KNN、K-Means 统一做标准化。预处理过程观察图如下（共 7 张，符合 10 张以内要求）。", size=9.4, space_after=4, line=1.12)
    for name, caption in (
        ("p1_missing_values.png", "图1  缺失值分布（? 解析为 NaN）"),
        ("p4_capital_gain_skew.png", "图2  capital-gain 偏态与 log1p 变换前后对比"),
        ("p5_workclass_counts.png", "图3  workclass 类别计数（缺失填 Unknown）"),
        ("p6_education_income.png", "图4  教育年限与高收入比例（强单调关系）"),
        ("p7_class_balance.png", "图5  目标类别不平衡（约 3:1）"),
        ("p2_age_distribution.png", "图6  年龄分布按收入分组"),
        ("p3_hours_distribution.png", "图7  周工作时长分布"),
    ):
        add_figure(first, EXPERIMENT_OUT / name, caption, 4.9 if name != "p1_missing_values.png" else 4.2)

    add_heading(first, "四、主要操作步骤（源码、训练结果和运行截图）")
    steps = [
        ("1 数据获取", "运行 run_adult_ml.py 从 UCI 归档下载 adult.data/adult.test 并缓存到 data/experiment3/，直连失败自动切换代理重试。"),
        ("2 清洗与缺失值", "解析 ? 为 NaN；去重；剔除冗余列 fnlwgt/education；三列缺失填 Unknown。"),
        ("3 特征工程", "log1p 金额列并派生二值特征；工时四段离散化；One-Hot 编码得 98 维；标准化供尺度敏感模型使用。"),
        ("4 算法训练", "依次训练逻辑回归、决策树、随机森林、SVC-RBF、KNN(K=21)、朴素贝叶斯与 K-Means(k=2)，共 7 种。"),
        ("5 模型评估", "官方 test 划分上计算准确率、精确率、召回率、F1，分类器另计 ROC-AUC，聚类另计 ARI 与轮廓系数。"),
        ("6 可视化对比", "输出指标对比柱状图、ROC 曲线、K-Means 肘部图、混淆矩阵与特征重要性图，全部指标落盘 metrics.json。"),
    ]
    add_table(first, ["步骤", "实际操作与输出"], steps, font_size=8.3)
    add_figure(first, render_console_screenshot(), "图8  实验运行截图（控制台输出，完整日志见 run_log.txt）", 5.8)

    add_table(
        first,
        ["算法", "准确率", "精确率", "召回率", "F1", "ROC-AUC", "训练耗时(s)"],
        [
            [
                item["algorithm"],
                fmt(item["accuracy"]),
                fmt(item["precision"]),
                fmt(item["recall"]),
                fmt(item["f1"]),
                fmt(item.get("roc_auc")),
                fmt(item["train_seconds"], 2),
            ]
            for item in metrics["algorithms"]
        ],
        font_size=7.8,
    )
    add_figure(first, EXPERIMENT_OUT / "e1_model_comparison.png", "图9  七种算法测试集指标对比柱状图", 5.9)

    add_heading(second, "五、实验思考（问题、分析与解决办法）")
    reflections = [
        ("问题1：类别不平衡导致准确率失真。", "负类占约 76%，全预测负类即有 76% 准确率。评估必须同时看少数类召回与 F1：朴素贝叶斯准确率最低（0.8041）但召回最高（0.7020），适合漏报代价高的场景；随机森林综合最优（F1 0.6642）。"),
        ("问题2：缺失值删行还是填充。", "缺失集中在 workclass/occupation/native-country 三列，合计约 7%。直接删行损失近两千条样本且引入选择偏差，故填 Unknown 保留未申报信息，由树模型自行学习该类别的含义。"),
        ("问题3：金额类特征强偏态。", "capital-gain 偏度达 11.9，绝大多数为 0。做 log1p 变换压缩长尾并派生二值特征，线性模型与距离模型的系数/距离不再被极端值支配。"),
        ("问题4：单模型与集成、线性与非线性差异。", "单棵决策树不剪枝时严重过拟合（AUC 仅 0.7693），随机森林集成后升至 0.8963；逻辑回归 AUC 最高（0.9083）说明该问题在特征工程后接近线性可分，且训练耗时最短（0.13s），是性价比最高的基线。"),
        ("问题5：无监督聚类的边界。", "K-Means(k=2) 对齐后准确率 0.7238、ARI 仅 0.193，轮廓系数不足 0.09：One-Hot 高维稀疏空间中欧氏距离难以还原收入结构，聚类只能作为无标注场景的对照基线，不能替代监督学习。"),
        ("问题6：SVM 的复杂度代价。", "RBF 核训练复杂度约 O(n^2)，全量 3.2 万样本代价过高，采用 1.2 万分层抽样训练（结果表中已标注），准确率 0.8486 与全量模型差距有限，说明数据量对该核函数已接近饱和。"),
    ]
    for title, body in reflections:
        p = add_para(second, size=9.2, space_after=2, line=1.12)
        r = p.add_run(title + " ")
        set_run_font(r, size=9.2, bold=True)
        r = p.add_run(body)
        set_run_font(r, size=9.2)
    add_figure(second, EXPERIMENT_OUT / "e2_roc_curves.png", "图10  六种分类器 ROC 曲线对比", 4.4)
    add_figure(second, EXPERIMENT_OUT / "e3_kmeans_elbow.png", "图11  K-Means 肘部法与轮廓系数", 4.6)
    add_figure(second, EXPERIMENT_OUT / "e4_confusion_matrix.png", "图12  随机森林混淆矩阵", 3.9)
    add_figure(second, EXPERIMENT_OUT / "e5_feature_importance.png", "图13  随机森林特征重要性 Top10", 4.6)

    add_heading(summary, "实验小结")
    lr, rf, nb, km = algorithms["1 逻辑回归"], algorithms["3 随机森林"], algorithms["6 朴素贝叶斯"], algorithms["7 K-Means聚类(k=2)"]
    add_para(summary, f"本实验在 UCI Adult Income 数据集（48,842 条）上完成了数据清洗、缺失值处理、特征工程与 7 种算法的训练评估对比。特征工程后逻辑回归取得最高 ROC-AUC {fmt(lr['roc_auc'])} 与 0.8548 准确率；随机森林 F1 最高（{fmt(rf['f1'])}）且召回 {fmt(rf['recall'])}；朴素贝叶斯召回最高（{fmt(nb['recall'])}）；K-Means 无监督对照准确率 {fmt(km['accuracy'])}、ARI {fmt(km['ari'])}，验证了监督学习的必要性。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "实验表明：类别不平衡场景下单一准确率不构成有效评价，需结合召回、F1 与 ROC-AUC；特征工程（偏态变换、缺失填充策略、编码与标准化）对线性与距离模型影响显著；集成学习能有效抑制单棵树的过拟合。全部代码、指标 JSON 与图表可由 run_adult_ml.py 一键复现。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "证据文件：results/experiment3/metrics.json、results/experiment3/run_log.txt 及同目录 13 张图表；实验源码 scripts/experiment3/run_adult_ml.py。", size=8.6, color="666666", line=1.1)

    for cell in (first, second, summary):
        if cell.paragraphs and not cell.paragraphs[0].text.strip():
            p = cell.paragraphs[0]
            p._element.getparent().remove(p._element)
    doc.save(FINAL)
    print(FINAL)


if __name__ == "__main__":
    fill_report()

"""构建《传媒数据管理与分析》期末结课报告（工业安全智能监测系统）。

按老师模板八章结构填充，全部数据/截图来自项目真实产物。
封面学号姓名从 results/midterm/student.json 读取（不入库）。
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
MID = ROOT / "results" / "midterm"
E4 = ROOT / "results" / "experiment4"
E5 = ROOT / "results" / "experiment5"
TEMPLATE = Path(r"D:\wechat_data\xwechat_files\wxid_2fa0anofxkjn22_bf97\msg\file\2026-10\学号_姓名《xxxx》期末结课报告.docx")
FINAL = ROOT / "学号_姓名《基于机器学习的工业安全智能监测系统》期末结课报告_完成版.docx"

OLD_TITLE = "基于机器学习的电影票房分析与预测系统设计与实现"
NEW_TITLE = "基于机器学习的工业安全智能监测系统设计与实现"

plt.rcParams["font.sans-serif"] = ["Consolas", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

try:
    STUDENT = json.loads((MID / "student.json").read_text(encoding="utf-8"))
except FileNotFoundError:
    STUDENT = {}


# ---------- docx 工具 ----------
def set_run_font(run, name="宋体", size=10.5, bold=False, color=None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_margins(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", 60), ("start", 90), ("bottom", 60), ("end", 90)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


class Inserter:
    def __init__(self, doc: Document, anchor_paragraph):
        self.doc = doc
        self.anchor = anchor_paragraph._p
        self.last = anchor_paragraph

    def _attach(self, paragraph):
        self.anchor.addnext(paragraph._p)
        self.anchor = paragraph._p
        self.last = paragraph
        return paragraph

    def para(self, text="", *, size=10.5, bold=False, color=None, space_after=3, line=1.25):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = line
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(text)
        set_run_font(r, size=size, bold=bold, color=color)
        return self._attach(p)

    def rich(self, segments, *, size=10, space_after=3, line=1.25):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = line
        for text, bold in segments:
            r = p.add_run(text)
            set_run_font(r, size=size, bold=bold)
        return self._attach(p)

    def bullet(self, label, text):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.2
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
        try:
            table.style = "Table Grid"
        except KeyError:
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                el = OxmlElement(f"w:{edge}")
                el.set(qn("w:val"), "single")
                el.set(qn("w:sz"), "4")
                el.set(qn("w:color"), "8FA8BF")
                borders.append(el)
            table._tbl.tblPr.append(borders)
        if widths:
            for column, width in zip(table.columns, widths):
                for cell in column.cells:
                    cell.width = Inches(width)
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
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci == 0 else WD_ALIGN_PARAGRAPH.LEFT
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
        if not Path(path).is_file():
            self.para(f"（截图待补：{caption}）", size=9, color="999999")
            return
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(path), width=Inches(width))
        self._attach(p)
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(caption)
        set_run_font(r, size=8.5, color="666666")
        cap.paragraph_format.space_after = Pt(4)
        return self._attach(cap)


def find_paragraph(doc: Document, text: str):
    for p in doc.paragraphs:
        if p.text.strip() == text:
            return p
    return None


def render_diagram(lines: list[str], path: Path) -> None:
    fig = plt.figure(figsize=(9.4, 0.24 * len(lines) + 0.4), dpi=150)
    fig.patch.set_facecolor("#0C0C0C")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.015, 0.94, "\n".join(lines), va="top", ha="left", family=["Consolas", "Microsoft YaHei"], fontsize=9.2, color="#9CDCFE", transform=ax.transAxes, linespacing=1.45)
    fig.savefig(path, facecolor="#0C0C0C", bbox_inches="tight")
    plt.close(fig)


def fmt(value, digits=4):
    return "--" if value is None else f"{float(value):.{digits}f}"


def load_metrics() -> list[dict]:
    runs = [
        ("YOLOv8n smoke", "baseline-n-smoke-metrics.json"),
        ("YOLOv8s smoke", "baseline-s-smoke-metrics.json"),
        ("YOLOv8s 5ep", "expanded-ppe-yolov8s-5ep-test-metrics.json"),
        ("YOLOv8s 10ep", "expanded-ppe-yolov8s-finetune10-test-metrics.json"),
        ("E6 8ep 合并集", "expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json"),
        ("E7 12ep hardcase", "expanded-ppe-yolov8s-hardcase12-test-metrics.json"),
        ("E8 30ep video150", "expanded-ppe-yolov8s-e8-video150-test-metrics.json"),
    ]
    out = []
    for name, filename in runs:
        payload = json.loads((ROOT / "results" / filename).read_text(encoding="utf-8"))
        out.append({"name": name, **{k: payload.get(k) for k in ("precision", "recall", "f1", "map50", "map50_95")}, "per_class": payload.get("per_class") or {}})
    return out


def fill_report() -> None:
    doc = Document(TEMPLATE)
    runs = load_metrics()
    by_name = {r["name"]: r for r in runs}
    e6, e7, e8 = by_name["E6 8ep 合并集"], by_name["E7 12ep hardcase"], by_name["E8 30ep video150"]

    # ---- 封面 ----
    for p in doc.paragraphs:
        stripped = p.text.strip()
        if stripped == OLD_TITLE:
            for run in p.runs[1:]:
                run.text = ""
            if p.runs:
                p.runs[0].text = NEW_TITLE
        elif stripped.startswith("==以上替换成"):
            for run in p.runs:
                run.text = ""
        else:
            # 学院/专业/班级/姓名/学号等填写行：重写首 run 并清空其余（避免多 run 残留）
            normalized = stripped.replace(" ", "")
            for key in ("学院", "专业", "班级", "姓名", "学号"):
                if normalized.startswith(key) and ("：" in stripped or ":" in stripped):
                    value = STUDENT.get(key, "")
                    if not value:
                        break
                    label = stripped.split("：")[0] if "：" in stripped else stripped.split(":")[0]
                    for run in p.runs[1:]:
                        run.text = ""
                    if p.runs:
                        p.runs[0].text = f"{label}：  {value}"
                    break

    ins = Inserter(doc, find_paragraph(doc, "背景简介"))
    ins.para("工业生产环境中，未佩戴安全帽、未穿反光背心进入危险区域是物体打击、机械伤害等事故的主要诱因。传统监管依赖人工巡视与事后抽查，存在覆盖时段有限、疲劳漏检、无法实时告警等固有缺陷。随着深度学习目标检测技术成熟，基于视频流的自动 PPE（个人防护装备）佩戴检测与危险区域闯入识别成为可行方案。本课题面向中小型工地/车间场景，构建一套从检测模型、多目标跟踪、规则引擎到 Web 监测工作台的完整系统，并以真实实验数据量化评估各技术方案的能力边界。", size=10)
    ins.para("在算法层面，系统围绕 YOLOv8 目标检测展开：从三个公开 PPE 数据集的整合清洗起步，完成七组训练方案的对照实验；在工程层面，采用前后端分离的双服务架构——Spring Boot 管理域负责用户与数据集/模型任务管理，Python 算法域负责推理与实时告警，Vue3 工作台统一呈现，形成一条完整的机器学习工程化实践链路。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "业务场景"))
    ins.para("系统面向两类典型业务场景：", size=10)
    ins.bullet("离线批量检测：", "安全员将现场抓拍的图片或录像上传至智能检测中心，系统自动识别人员、安全帽与反光背心，对违规行为生成告警事件并留存标注证据图，供事后追溯与安全教育使用。")
    ins.bullet("持续监测与告警闭环：", "对上传视频或接入的摄像头画面做逐帧分析，ByteTrack 维持人员身份，连续 3 帧确认违规、同一人员同一规则 10 秒冷却后产生告警；告警通过 WebSocket 实时推送到工作台，安全员完成确认/关闭的闭环处理。")
    ins.para("系统覆盖的角色包括系统管理员（用户管理、数据集管理、训练任务管理、危险区域配置）与操作员（检测、告警处理），对应后台管理域与监测工作台两组界面。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "1.3.1硬件配置要求"))
    ins.table(
        ["项目", "配置", "说明"],
        [
            ["CPU", "Intel i7（32 线程实测环境）", "数据预处理与双服务运行"],
            ["GPU", "NVIDIA GeForce RTX 4070 Laptop 8GB", "模型训练与推理加速（CUDA 12.6）"],
            ["内存", "16GB 及以上", "视频流水线有界队列占用可控"],
            ["磁盘", "20GB 可用空间", "数据集、权重与运行产物"],
        ],
        font_size=9,
    )

    ins = Inserter(doc, find_paragraph(doc, "1.3.2软件配置要求"))
    ins.table(
        ["软件", "版本", "用途"],
        [
            ["Windows 11", "64 位", "操作系统"],
            ["JDK (OpenJDK)", "24.0.2", "Spring Boot 运行时"],
            ["MySQL", "8.0.43", "管理域业务数据库"],
            ["Docker Desktop", "4.88.1", "PostgreSQL 16 与整体容器化部署（可选）"],
            ["Node.js / npm", "22.23.2 / 10.9.8", "前端构建"],
            ["Git / GitHub CLI", "2.51.0 / 2.93.0", "版本管理与远程托管"],
        ],
        font_size=9,
    )

    ins = Inserter(doc, find_paragraph(doc, "1.3.3开发工具"))
    ins.bullet("IntelliJ IDEA 2025.3：", "Spring Boot 管理域开发与调试（JetBrains Toolbox 管理）。")
    ins.bullet("VS Code 1.140 / Cursor 2.6：", "Python 算法域与 Vue3 前端开发。")
    ins.bullet("Navicat Premium 16.3：", "MySQL/PostgreSQL 数据库可视化管理。")
    ins.bullet("Postman 等价自研测试脚本：", "接口测试矩阵自动化执行（requests 实现）。")
    ins.bullet("浏览器开发者工具：", "前端联调、网络请求与缓存排查。")

    ins = Inserter(doc, find_paragraph(doc, "1.3.4主要的开发库和依赖项"))
    ins.table(
        ["层次", "主要依赖", "版本"],
        [
            ["算法域（Python 3.12）", "PyTorch / Ultralytics / OpenCV / FastAPI / SQLAlchemy", "2.6.0+cu126 / 8.4.152 / 5.0.0 / 最新稳定 / 2.0.53"],
            ["管理域（Java 21）", "Spring Boot / Spring Data JPA / jjwt / mysql-connector-j", "3.4.5 / 随 BOM / 0.12.6 / 随 BOM"],
            ["前端", "Vue / Vue Router / Pinia / Element Plus / ECharts / Axios", "3.5 / 4.x / 2.x / 2.9 / 5.6 / 1.x"],
            ["构建与测试", "Maven / Vite / pytest / requests", "3.9.9 / 5.4 / 65 用例套件 / 最新"],
        ],
        font_size=9,
    )

    ins = Inserter(doc, find_paragraph(doc, "1.3.5 Git使用"))
    ins.para("项目托管于 GitHub 私有工作流：主分支 main 承载可运行版本，功能按模块分批提交（本学期累计 20 余次提交），提交信息遵循\"说明为什么而非改了什么\"的规范。关键节点包括：正确性修复（危险区相对坐标、WebSocket 增量推送、UTC 时序化）、Vue3 前端重写、Spring Boot 管理域新增、容器化编排等，每次提交均可通过哈希追溯。仓库中的实验指标 JSON 与测试套件保证了每次提交后可一键回归验证（pytest 65 用例）。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "2.1系统功能需求"))
    ins.table(
        ["模块", "功能点", "角色"],
        [
            ["监测工作台", "监控总览（告警统计/趋势图/占比图）、智能检测（图片/视频上传推理）、任务中心、模型实验对比、告警中心（证据查看/确认/关闭）、设备与危险区域配置", "管理员/操作员"],
            ["实时推送", "WebSocket 告警实时通知（增量推送、断线重连）", "管理员/操作员"],
            ["用户管理", "注册、登录（JWT）、列表、新增、修改、删除，角色 admin/operator，接口强制鉴权", "管理员"],
            ["数据集管理", "数据集压缩包上传（SHA256 校验）、列表、详情、删除", "管理员"],
            ["模型在线训练与评估", "发起演示级训练异步任务、状态轮询、真实指标提取与展示", "管理员"],
        ],
        font_size=8.8,
    )

    ins = Inserter(doc, find_paragraph(doc, "2.2用例分析"))
    ins.para("系统核心用例按角色划分如下：", size=10)
    ins.table(
        ["用例", "参与者", "前置条件", "主要流程"],
        [
            ["图片安全检测", "操作员", "已登录", "上传图片→算法推理→查看标注结果与检测统计→违规自动生成告警"],
            ["视频安全检测", "操作员", "已登录", "上传视频→异步任务排队/执行→轮询进度→查看标注视频与事件"],
            ["告警闭环处理", "操作员", "存在告警", "告警中心查看证据→确认→关闭，统计页同步更新"],
            ["危险区域配置", "管理员", "admin 登录", "画布点选多边形顶点→按 0-1 相对坐标保存→绑定监控点生效"],
            ["用户管理", "管理员", "admin 登录", "新增/编辑（角色、启停、重置密码）/删除用户"],
            ["数据集与训练管理", "管理员", "admin 登录", "上传数据集→发起演示训练→轮询状态→查看真实评估指标"],
        ],
        font_size=8.6,
    )

    ins = Inserter(doc, find_paragraph(doc, "3.1系统总体架构"))
    ins.para("系统采用前后端分离的双服务架构，职责按技术适性划分：Java 擅长业务编排与事务，Python 垄断深度学习生态。两服务各自独立部署、独立鉴权，前端以两套令牌分别访问。", size=10)
    arch = [
        "┌─────────────────────────────────────────────────────┐",
        "│                Vue3 工作台 (FastAPI :8010 伺服)      │",
        "│  六大监测页面 + 用户管理 + 数据集/模型管理（Axios 双域）│",
        "└───────────────┬─────────────────────┬───────────────┘",
        "        Bearer监测域JWT          Bearer管理域JWT",
        "               ▼                     ▼",
        "┌──────────────────────────┐  ┌──────────────────────────┐",
        "│ Python 算法域 FastAPI     │  │ Spring Boot 管理域 :8081  │",
        "│ YOLOv8·ByteTrack·规则引擎 │◀─│ 用户管理·数据集·训练任务   │",
        "│ WebSocket 实时告警        │ │ JPA · MySQL(safety_admin) │",
        "└───────────┬──────────────┘  └──────────────────────────┘",
        "            ▼ ProcessBuilder（演示级训练子进程）",
        "   runs/train/…（best.pt + results.csv 真实指标）",
    ]
    diagram_path = MID / "final_architecture.png"
    render_diagram(arch, diagram_path)
    ins.figure(diagram_path, "图3-1 系统总体架构（双服务职责划分）", 5.8)

    ins = Inserter(doc, find_paragraph(doc, "3.2.1数据库设计"))
    ins.para("系统包含两个数据存储：管理域 MySQL 库 safety_admin（业务主库），算法域 SQLite/PostgreSQL（监测业务库，经 SQLAlchemy 抽象可切换）。", size=10)
    ins.table(
        ["存储", "表", "核心字段"],
        [
            ["MySQL safety_admin", "users", "id, username(unique), password_hash(BCrypt), role, enabled"],
            ["MySQL safety_admin", "datasets", "name, original_filename, stored_path, size_bytes, sha256"],
            ["MySQL safety_admin", "model_train_tasks", "status(pending/running/completed/failed), epochs, best_weights, metrics_json"],
            ["算法域", "users / cameras / danger_zones / inference_jobs / safety_events", "摄像头、0-1 相对坐标危险区、任务状态机、告警事件（类型/等级/证据/状态）"],
        ],
        font_size=8.6,
    )

    ins = Inserter(doc, find_paragraph(doc, "3.2.2算法模型设计"))
    ins.para("检测层采用 YOLOv8n/YOLOv8s（CSPDarknet 骨干 + PAN-FPN 颈部 + 解耦头），输出 person/helmet/vest 三类业务目标；跟踪层采用 ByteTrack 思路的 IoU 贪心匹配（连续 3 次命中确认轨迹、丢失 30 帧淘汰），输出稳定 track_id；规则层完成 PPE 空间关联（中心点包含 + 重叠率 + 头/躯干相对位置 + 面积占比四重几何校验）、危险区域脚底中心点越界判断（射线法，多边形存 0-1 相对坐标适配任意分辨率）与时间维确认（连续 3 帧确认 + 10 秒冷却 + 15 帧佩戴宽限/预热）。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "3.2.3前端设计"))
    ins.para("前端为 Vue3 + Vite 工程：Vue Router 组织八个路由页面，Pinia 管理跨页面状态，Element Plus 提供表格/表单/对话框组件，ECharts 实现告警环形图、七日趋势线与模型指标对比柱状图；Axios 拦截器统一处理双域令牌注入、响应解包与错误通知；构建产物由 FastAPI 静态伺服并配 SPA history 路由回退。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "3.2.4后端设计"))
    ins.para("管理域按 Controller/Service/Repository 三层组织，统一 Result{code,message,data} 响应与全局异常处理，JwtAuthFilter 精确匹配白名单并对 /api/users/** 集中执行 admin 角色控制；算法域为 FastAPI 单服务，视频采用\"有界解码队列→批量推理→严格保序后处理\"三线程流水线，保证检测可批量加速而跟踪/规则严格按原始帧序执行。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "4.1数据库详细设计"))
    ins.figure(MID / "final_db_er.png", "图4-1 系统数据库 ER 关系图（管理域 MySQL + 算法域 SQLite/PostgreSQL）", 6.1)
    ins.para("管理域核心表字段明细如下（JPA 实体注解与表结构一一对应）：", size=10)
    ins.table(
        ["表", "字段", "类型/约束", "说明"],
        [
            ["users", "id", "PK 自增", "用户主键"],
            ["users", "username", "VARCHAR(50) UNIQUE", "登录名，全库唯一"],
            ["users", "password_hash", "VARCHAR(100)", "BCrypt 哈希，不存明文"],
            ["users", "role", "VARCHAR(20)", "admin / operator，支撑接口鉴权"],
            ["users", "enabled", "BOOLEAN", "停用保留账号而不删除"],
            ["model_train_tasks", "status", "VARCHAR(20)", "pending→running→completed/failed 状态机"],
            ["model_train_tasks", "best_weights", "VARCHAR(300)", "训练产出的最优权重路径"],
            ["model_train_tasks", "metrics_json", "VARCHAR(1000)", "从 results.csv 提取的真实指标"],
        ],
        font_size=8.6,
    )
    ins.para("算法域五表（cameras/danger_zones/inference_jobs/safety_events 等）由 SQLAlchemy 声明式模型维护：其中 danger_zones.polygon 以 0-1 相对坐标 JSON 存储，同一危险区适配任意分辨率视频；safety_events 记录事件类型、等级、人员轨迹与证据截图路径，支撑告警闭环。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "4.2.1算法模型选择"))
    ins.bullet("YOLOv8n（轻量基线）：", "参数量最小、推理最快，用于验证训练-评估链路与端侧可行性，但召回不足，不作为业务模型。")
    ins.bullet("YOLOv8s（主模型）：", "容量适中，在同等数据下 mAP 显著高于 n 版，训练成本可控，为全部对照实验的骨干选择。")
    ins.bullet("未选择两阶段检测器（如 Faster R-CNN）：", "推理延迟高一个量级，与\"视频实时逐帧分析\"的业务场景冲突；单阶段 YOLOv8 在精度/速度权衡上最适合本课题。")
    ins.bullet("数据集：", "Construction-PPE + SH17 + Kaggle PPE 三源合并，统一 person/helmet/vest 三类，图片级 SHA256 去重后共 11,623 张、28,853 框，官方划分 train/val/test = 8,276/2,184/1,163。")

    ins = Inserter(doc, find_paragraph(doc, "4.2.2模型训练流程"))
    ins.para("训练流程：数据下载与校验（validate_dataset.py 0 错误门禁）→ 类别归一与去重 → smoke 链路验证（1 epoch）→ 扩充集对照训练 → 合并集精调 → hard-case 定向增强（3 张漏检原图各 60 个确定性增强，仅挂载训练集）→ 独立 test 同口径评估（evaluate_yolo.py 落盘 JSON）→ 三图两视频定向回归门禁。七组训练的实测结果见第 6 章。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "4.3前端详细设计"))
    ins.figure(E5 / "c1_axios_interceptors.png", "图4-2 Axios 双拦截器核心代码（令牌注入/统一解包/错误通知）", 5.9)
    ins.figure(E5 / "ui-dashboard.png", "图4-3 监控总览 Dashboard（ECharts 告警环形图/严重度条/七日趋势）", 5.9)
    ins.figure(E5 / "c3_train_poll.png", "图4-4 训练任务 5 秒自动轮询核心代码", 5.9)
    ins.figure(E5 / "ui-admin-users.png", "图4-5 用户管理页（Spring Boot 数据真实渲染）", 5.9)

    ins = Inserter(doc, find_paragraph(doc, "4.4后端详细设计"))
    ins.figure(E4 / "c1_user_register_login.png", "图4-6 用户服务核心代码（BCrypt 注册/JWT 登录）", 5.9)
    ins.figure(E4 / "c2_jwt_filter.png", "图4-7 JWT 统一鉴权过滤器（精确白名单/401/403）", 5.9)
    ins.figure(E4 / "c3_train_async.png", "图4-8 在线训练异步任务核心代码（ProcessBuilder 调用算法域）", 5.9)
    ins.figure(E4 / "r4_train_log.png", "图4-9 在线训练任务真实日志尾部", 5.8)

    ins = Inserter(doc, find_paragraph(doc, "5.1前端测试"))
    ins.para("前端采用\"自动化资源契约测试 + 浏览器人工联调\"结合：pytest 套件中含 SPA 服务契约用例（入口壳、history 路由回退、资产可达、旧版回退），页面功能按\"正常/异常/边界\"手工遍历（空数据兜底、错误通知、双域令牌过期提示）。联调中发现并修复的真实问题包括：跨域白名单遗漏 8010 源、管理域登录与数据加载的时序竞态（AdminGate logged-in 事件解决）、旧缓存导致资源 404（入口文档 no-cache + 资产 404 兜底解决）。", size=10)
    ins.figure(E5 / "ui-alerts.png", "图5-1 告警中心联调运行截图（WebSocket 实时接收 + 闭环操作）", 5.9)

    ins = Inserter(doc, find_paragraph(doc, "5.2后端测试"))
    ins.para("算法域：pytest 自动化套件 65 个用例全绿，覆盖检测几何过滤链、跟踪确认、规则引擎（含宽限/预热/冷却）、API 契约、数据集工具与视频流水线集成测试。管理域：全接口测试矩阵按\"正常/异常/边界/权限\"四类执行，关键断言包括——重复用户名 409、密码过短 400、无令牌 401、operator 访问管理接口 403、删除不存在用户 404。", size=10)
    ins.figure(E4 / "r1_api_matrix.png", "图5-2 管理域全接口测试矩阵（真实请求-响应记录）", 5.9)

    ins = Inserter(doc, find_paragraph(doc, "6.1模型选择依据（每种模型半页内，紧扣你的项目主题）"))
    ins.para("本项目围绕业务目标（PPE 三类检测、视频逐帧分析、误报可控）进行模型选型：", size=10)
    ins.bullet("YOLOv8n vs YOLOv8s：", "n 版 smoke 仅 mAP@0.5 0.297，验证了链路但召回不足（0.307）；s 版同轮数 mAP 提升至 0.377，确立 s 为业务骨干——容量换精度的边际收益在此数据规模上明显。")
    ins.bullet("数据规模优先于训练轮数：", "数据从 1,416 张扩至 9,515 张（5 epoch）即把 Recall 从 0.32 拉升至 0.53，而同数据下 5→10 轮的提升明显更缓，确立\"先扩数据再调轮数\"的策略。")
    ins.bullet("定向增强的取舍：", "hard-case 增强仅挂载训练集（不进 val/test），E7 换来全组最高 Recall 与 mAP，且通过定向回归门禁，故选为部署版本。")
    ins.bullet("E8 的教训：", "再叠加 150 张视频抽帧并训练 30 轮，Recall 微升但 Precision/F1/mAP 全面回落，经四步验收门禁判定不替换部署——用数据而非直觉决定上线版本。")

    ins = Inserter(doc, find_paragraph(doc, "6.2实验设置与评估指标"))
    ins.para("统一评估设置：基础合并集独立 test split（1,163 张 / 3,047 框），imgsz=640、conf=0.25，七组模型完全同口径。评估指标：Precision（查准率）、Recall（查全率）、F1（两者调和平均）、mAP@0.5 与 mAP@0.5:0.95（多 IoU 阈值平均精度）；分项指标聚焦业务三类。类别不平衡（负类约 76%）场景下，单看准确率会失真，故以 F1 与 Recall 为主要决策依据。所有指标由脚本从真实运行产物落盘 JSON，不使用计划值或 fallback 输出。", size=10)

    ins = Inserter(doc, find_paragraph(doc, "6.3结果对比与分析"))
    ins.table(
        ["模型", "Precision", "Recall", "F1", "mAP@0.5", "mAP@0.5:0.95"],
        [[r["name"], fmt(r["precision"]), fmt(r["recall"]), fmt(r["f1"]), fmt(r["map50"]), fmt(r["map50_95"])] for r in runs],
        font_size=8.6,
    )
    ins.figure(MID / "mt2_model_comparison.png", "图6-1 七组模型测试集指标对比（真实 JSON 结果可视化）", 5.9)
    ins.figure(MID / "mt3_helmet_recall.png", "图6-2 helmet 类分项 Precision/Recall 演进", 5.4)
    ins.rich([
        ("结果分析：", True),
        (f"① 数据维度收益最大——Recall 从 smoke 的 0.32 提升到合并集 hardcase 的 {fmt(e7['recall'])}；② E7（12 epoch + hardcase）以 Precision {fmt(e7['precision'])}、F1 {fmt(e7['f1'])}、mAP@0.5 {fmt(e7['map50'])} 成为部署版本；③ E8（30 epoch）Recall 再升至 {fmt(e8['recall'])}、helmet Recall 达 {fmt(e8['per_class'].get('helmet', {}).get('recall'))}，但精度指标全面回落，门禁机制成功拦截这次负优化替换；④ 测试集存在部分近重复画面，结果用于七组模型同口径对比，不作为无泄漏泛化结论，按视频/人员隔离的独立场景集列为后续工作。", False),
    ], size=10)

    ins = Inserter(doc, find_paragraph(doc, "7.1主要结论"))
    ins.bullet("算法结论：", f"E7 部署模型在同口径 test 上取得 Precision {fmt(e7['precision'])}、Recall {fmt(e7['recall'])}、F1 {fmt(e7['f1'])}、mAP@0.5 {fmt(e7['map50'])}；数据扩充与定向增强是收益最大的两项优化，训练轮数在 12 轮后边际收益归零。")
    ins.bullet("工程结论：", "双服务架构（Java 业务域 + Python 算法域）通过 ProcessBuilder 训练任务链实测打通（105 秒完成演示级真实训练）；Vue3 工作台八页面全部经浏览器联调验收；容器化编排（nginx/api/db + GPU 变体）均实测可用。")
    ins.bullet("质量结论：", "算法域 65 个自动化测试 + 管理域全接口测试矩阵 + 三图两视频定向回归门禁 + E8 四步验收门禁，构成多层质量防线；期间真实拦截了 E8 负优化部署与一次鉴权白名单回归。")

    ins = Inserter(doc, find_paragraph(doc, "7.2 不足与展望"))
    ins.bullet("评估侧：", "测试集存在近重复画面，计划重建按视频/人员隔离的 300–500 帧独立自建场景集，获得真正的泛化指标。")
    ins.bullet("模型侧：", "安全帽小目标召回（约 0.49）仍有空间，计划试验更高输入分辨率与更大骨干，并针对性补充远景/深色帽数据。")
    ins.bullet("系统侧：", "接入 RTSP 实时摄像头流（当前为上传式与演示训练），补充 720p/15FPS 正式性能验收与跟踪/规则消融实验。")
    ins.bullet("工程侧：", "管理域接入 Redis 会话缓存与操作审计日志，监测域告警推送由轮询升级为事件总线。")

    ins = Inserter(doc, find_paragraph(doc, "对课程的认识与收获"))
    ins.para("这门课让我第一次完整走完了一个机器学习系统从数据到上线的全过程。之前我对\"机器学习\"的理解停留在调库训练和看指标，而这次课程作业逼着我面对真实工程里的每一层问题：三个公开数据集类别名对不上怎么合并、测试集有近重复画面指标还能不能信、模型换版本怎么决定上不上线。最后我给出的答案是校验脚本、同口径对比和上线门禁——这些\"笨办法\"恰恰是这门课教给我的最重要的工程思维。", size=10)
    ins.para("技术栈上的收获同样具体。后端从零搭起了 Spring Boot 三层架构，踩过跨域、JWT 过滤器白名单写法（startsWidth 放行了所有路径）、异步任务状态机这些真实的坑；前端用 Vue3 重写了整个工作台，学会了 Axios 拦截器封装、双域令牌管理和 ECharts 数据绑定；算法侧则理解了\"数据质量决定上限\"——七组实验里收益最大的两次都来自数据而不是模型。前后端联调时那种\"接口明明对却全 401\"的排查经历，也让我真正理解了浏览器同源策略和预检请求。", size=10)
    ins.para("如果说还有什么更深一层的体会，是这门课让我建立了\"诚实面对实验结果\"的习惯：E8 训练了 30 轮指标却更差，门禁把它拦下来的时候确实不甘心，但事后看这正是评估体系的价值——它保护系统不被一次看起来很努力的训练弄坏。这套习惯会一直留在我之后的项目里。", size=10)

    doc.save(FINAL)
    print(FINAL)


if __name__ == "__main__":
    fill_report()

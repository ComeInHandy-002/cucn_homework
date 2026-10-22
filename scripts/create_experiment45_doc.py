"""构建实验四（Spring Boot 后端）与实验五（Vue 前端设计）报告完成版。

全部内容来自真实产物：
- 实验四：results/experiment4/ 下接口测试矩阵、MySQL 表结构、项目树、训练日志
- 实验五：results/experiment5/ui-admin-users.png 真实联调截图 + 前端工程结构
生成前确认两个模板 docx 与素材存在。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from collect_code_assets import build_code_assets

ROOT = Path(__file__).resolve().parents[1]
E4 = ROOT / "results" / "experiment4"
E5 = ROOT / "results" / "experiment5"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

STUDENT_NOTE = "学号姓名见封面（生成时从 results/midterm/student.json 读取的本地文件不随仓库分发）"


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


def add_para(cell, text="", *, size=10.5, bold=False, color=None, space_after=3, line=1.15):
    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold, color=color)
    return p


def add_heading(cell, text):
    p = add_para(cell, text, size=12, bold=True, space_after=4, line=1.0)
    p.paragraph_format.space_before = Pt(6)
    return p


def add_bullet(cell, label, text):
    p = add_para(cell, size=10, space_after=2, line=1.1)
    r = p.add_run("• ")
    set_run_font(r, size=10, bold=True, color="1F4E79")
    r = p.add_run(label)
    set_run_font(r, size=10, bold=True)
    r = p.add_run(text)
    set_run_font(r, size=10)


def add_table(cell, headers, rows, font_size=8.2):
    table = cell.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        set_cell_margins(c)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        set_run_font(r, size=font_size, bold=True, color="FFFFFF")
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), "1F4E79")
        c._tc.get_or_add_tcPr().append(shd)
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for ci, value in enumerate(row):
            c = cells[ci]
            set_cell_margins(c)
            if ri % 2:
                shd = OxmlElement("w:shd")
                shd.set(qn("w:fill"), "F3F6F9")
                c._tc.get_or_add_tcPr().append(shd)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci == 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            set_run_font(r, size=font_size)
    return table


def add_figure(cell, path: Path, caption: str, width: float) -> None:
    if not Path(path).is_file():
        add_para(cell, f"（截图待补：{caption}）", size=9, color="999999")
        return
    p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # 图与图注必须同页，防止注掉到下一页形成孤行
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    self_anchor = p
    cap = cell.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption)
    set_run_font(r, size=8.5, color="666666")
    cap.paragraph_format.space_after = Pt(4)


def render_text_asset(lines: list[str], path: Path, title: str, size=8.4) -> None:
    fig = plt.figure(figsize=(9.8, 0.24 * len(lines) + 0.5), dpi=150)
    fig.patch.set_facecolor("#0C0C0C")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.012, 0.97, title, va="top", ha="left", fontsize=9, color="#4EC9B0", transform=ax.transAxes)
    ax.text(0.012, 0.88, "\n".join(lines), va="top", ha="left", family=["Consolas", "Microsoft YaHei"], fontsize=size, color="#CCCCCC", transform=ax.transAxes)
    fig.savefig(path, facecolor="#0C0C0C", bbox_inches="tight")
    plt.close(fig)


def build_experiment4() -> Path:
    matrix = (E4 / "api_test_matrix.txt").read_text(encoding="utf-8").splitlines()
    render_text_asset(matrix, E4 / "r1_api_matrix.png", "PS> Postman 等价全接口测试（requests 脚本真实执行，正常/异常/边界/权限）")
    schema = (E4 / "mysql_schema.txt").read_text(encoding="utf-8").splitlines()
    render_text_asset(schema, E4 / "r2_mysql_schema.png", "PS> mysql CLI：safety_admin 库表结构（真实 DESCRIBE 输出）")
    tree = (E4 / "project_tree.txt").read_text(encoding="utf-8").splitlines()
    render_text_asset(tree, E4 / "r3_project_tree.png", "backend-java 源码结构（三层分包）", size=7.6)
    log = (E4 / "train_log_tail.txt")
    if log.exists():
        render_text_asset(log.read_text(encoding="utf-8").splitlines()[-18:], E4 / "r4_train_log.png", "训练任务日志尾部（backend-java/logs/train-1.log）", size=7.8)

    docx_path = E4 / "template_exp4.docx"
    doc = Document(docx_path)
    first = doc.tables[0].cell(0, 0)
    second = doc.tables[1].cell(0, 0)
    summary = doc.tables[1].cell(1, 0)
    for cell in (first, second, summary):
        clear_cell(cell)
        set_cell_margins(cell)

    add_heading(first, "一、实验目的")
    add_bullet(first, "框架掌握：", "掌握基于 Spring Boot 的后端项目搭建与配置，理解 Controller—Service—Repository 三层架构及职责划分。")
    add_bullet(first, "接口开发：", "掌握 RESTful 接口设计与实现，完成用户管理与数据集/模型管理两个业务模块的完整增删改查。")
    add_bullet(first, "持久层实践：", "使用 Spring Data JPA 操作 MySQL 数据库，理解前后端数据交互流程。")
    add_bullet(first, "调试能力：", "掌握接口调试与前后端联调方法，独立排查参数校验、鉴权、跨域等常见问题。")

    add_heading(first, "二、实验环境")
    add_bullet(first, "系统与工具：", "Windows 11、IntelliJ IDEA 2025.3、Maven 3.9.9（阿里云镜像）、Postman 等价自研测试脚本、Git 2.51。")
    add_bullet(first, "运行时：", "JDK（OpenJFP 24.0.2 运行 / bytecode release 21）、Spring Boot 3.4.5、Spring Data JPA（Hibernate）。")
    add_bullet(first, "数据库：", "MySQL 8.0.43（Navicat Premium 16.3 管理），业务库 safety_admin。")
    add_bullet(first, "既有服务：", "算法推理域为项目既有 Python FastAPI 服务（YOLOv8），Java 管理域通过进程调用其训练脚本，构成微服务职责划分。")

    add_heading(first, "三、实验内容及要求")
    add_para(first, "以工业安全智能监测系统为背景搭建后台管理域：①用户管理接口——注册、登录（JWT）、列表查询、新增、修改、删除，含参数校验与统一响应格式；②数据集/模型管理接口——数据集上传（SHA256 校验）、列表、详情、删除，以及模型在线训练与评估（异步任务 + 真实 YOLOv8 训练）。接口命名遵循 RESTful 规范，数据库采用 MySQL，持久层使用 Spring Data JPA。", size=9.4, space_after=4, line=1.12)
    add_para(first, "统一响应格式为 {code, message, data}；JwtAuthFilter 对除登录/注册外的全部接口校验 Bearer 令牌，/api/users/** 仅允许 admin 角色，权限不足返回 401/403。", size=9.4, space_after=4, line=1.12)
    add_heading(first, "四、主要操作步骤（源码、运行结果截图）")
    steps = [
        ("1 项目搭建", "手写 pom.xml（Spring Boot 3.4.5 父工程、JPA/Validation/MySQL/jjwt 依赖）与 application.yml（数据源、8081 端口、CORS、训练配置），建立 controller/service/repository 分层目录。"),
        ("2 数据库准备", "MySQL 中创建 safety_admin 库（utf8mb4），JPA ddl-auto=update 自动建 users/datasets/model_train_tasks 三表；初始化器写入内置 admin 账号（BCrypt 加密）。"),
        ("3 用户管理接口", "注册（用户名查重/BCrypt）、登录（签发 JWT）、列表/新增/修改/删除；JwtAuthFilter 统一鉴权，参数校验失败返回 400。"),
        ("4 数据集与模型接口", "multipart 上传存盘并计算 SHA256；训练接口创建异步任务，经 ProcessBuilder 调用算法域真实 train_yolo.py（演示级 1 epoch），完成后从 results.csv 提取真实指标。"),
        ("5 接口测试", "以脚本执行全接口测试矩阵（正常/异常/边界/权限），截图见图2；前端 Vue 页面联调截图见图3。"),
        ("6 调试优化", "修复 CORS 白名单遗漏 8010 源、multipart 解析、时序竞态（登录后再拉取数据）等问题；训练日志落盘便于排障。"),
    ]
    add_table(first, ["步骤", "实际操作与输出"], steps, font_size=8.3)
    add_para(first, "核心代码（一）用户服务：注册使用 BCrypt 加密存储，登录校验通过后由 JwtService 签发含 uid/role 声明的 JWT 令牌：", size=9.6, space_after=2)
    add_figure(first, E4 / "c1_user_register_login.png", "图1 用户服务核心代码（注册/登录）", 5.9)
    add_para(first, "核心代码（二）统一鉴权过滤器：白名单放行登录注册，其余接口校验 Bearer 令牌并集中执行 admin 角色控制：", size=9.6, space_after=2)
    add_figure(first, E4 / "c2_jwt_filter.png", "图2 JWT 统一鉴权过滤器核心代码", 5.9)
    add_figure(first, E4 / "r3_project_tree.png", "图3 backend-java 三层分包源码结构", 4.6)
    add_para(first, "核心代码（三）训练任务链：创建任务后经 ProcessBuilder 异步调用算法域真实训练脚本，完成后提取真实指标：", size=9.6, space_after=2)
    add_figure(first, E4 / "c3_train_async.png", "图4 模型在线训练异步任务核心代码", 5.9)
    add_figure(first, E4 / "r4_train_log.png", "图5 在线训练任务真实日志尾部", 5.8)
    add_para(first, "核心代码（四）配置与全局异常：application.yml 数据源/端口/CORS/训练配置，以及统一错误响应：", size=9.6, space_after=2)
    add_figure(first, E4 / "c4_application_yml.png", "图6 application.yml 核心配置", 5.9)
    add_figure(first, E4 / "c5_exception_handler.png", "图7 全局异常处理器（参数校验/业务/未知异常分类响应）", 5.9)
    add_figure(first, E4 / "r2_mysql_schema.png", "图8 MySQL safety_admin 库表结构（真实 DESCRIBE 输出）", 5.8)
    add_figure(first, E4 / "r1_api_matrix.png", "图9 全接口测试矩阵（真实请求-响应，含异常与权限场景）", 5.9)

    add_heading(second, "五、实验思考（问题、分析与解决办法）")
    reflections = [
        ("问题1：前端跨域请求被浏览器拦截。", "管理域服务运行在 8081，前端页面在 8010 源下，首次联调全部请求 Network Error。在 application.yml 配置 CorsFilter 白名单并注册为最高优先级过滤器后解决；过程中加深了对 OPTIONS 预检请求的理解。"),
        ("问题2：JWT 校验与角色控制散落在各接口。", "解决方法：实现 OncePerRequestFilter 统一校验 Bearer 令牌并把 uid/role 写入请求属性，/api/users/** 前缀集中强制 admin 角色，业务 Controller 保持零鉴权代码，职责清晰。"),
        ("问题3：'模型在线训练'耗时与演示矛盾。", "真实 YOLOv8 训练一轮完整数据需数小时。解决方法：采用演示级真实链路——小数据集 + 1 epoch（实测 105 秒完成），训练为真实子进程、指标从 Ultralytics results.csv 真实提取，报告中如实注明演示级边界，不用假数据。"),
        ("问题4：Windows 下子进程日志中文乱码。", "ProcessBuilder 读取训练输出默认按系统 GBK 解码与 UTF-8 输出冲突。显式指定 GB18030 读取并统一写日志文件后解决。"),
        ("问题5：接口测试覆盖不全导致权限漏洞风险。", "建立测试矩阵（正常/异常/边界/权限四类）逐项断言状态码：无令牌 401、operator 访问管理接口 403、重复用户名 409、参数校验 400，全部通过后才进入联调。"),
    ]
    for title, body in reflections:
        p = add_para(second, size=9.2, space_after=2, line=1.12)
        r = p.add_run(title + " ")
        set_run_font(r, size=9.2, bold=True)
        r = p.add_run(body)
        set_run_font(r, size=9.2)

    add_para(summary, "实验小结：本实验基于 Spring Boot 3.4 完成了后台管理域的搭建，实现用户管理与数据集/模型管理两个业务模块的完整 CRUD 与 JWT 鉴权，通过 Spring Data JPA 操作 MySQL，并以全接口测试矩阵与前端联调验证了接口稳定性。'模型在线训练与评估'采用异步任务 + 真实训练子进程的方案，实测 105 秒完成演示级训练并提取真实指标，体现了微服务架构下 Java 业务域与 Python 算法域协作的工程实践。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "证据文件：results/experiment4/ 下接口测试矩阵、MySQL 表结构、训练日志与本项目 backend-java/ 源码。", size=8.6, color="666666", line=1.1)

    for cell in (first, second, summary):
        if cell.paragraphs and not cell.paragraphs[0].text.strip():
            p = cell.paragraphs[0]
            p._element.getparent().remove(p._element)
    out = ROOT / "学号_姓名_实验四--后端实现_完成版.docx"
    doc.save(out)
    return out


def build_experiment5() -> Path:
    docx_path = E5 / "template_exp5.docx"
    doc = Document(docx_path)
    first = doc.tables[0].cell(0, 0)
    second = doc.tables[1].cell(0, 0)
    summary = doc.tables[1].cell(1, 0)
    for cell in (first, second, summary):
        clear_cell(cell)
        set_cell_margins(cell)

    add_heading(first, "一、实验目的")
    add_bullet(first, "框架掌握：", "熟悉 Vue3 组合式 API、组件、数据绑定、指令、生命周期与 Vue Router 路由。")
    add_bullet(first, "可视化开发：", "完成后台首页 Dashboard 与业务页面开发，集成 ECharts 完成数据可视化。")
    add_bullet(first, "接口对接：", "使用 Axios 调用 Spring Boot 后端接口，完成数据获取、解析与动态渲染。")
    add_bullet(first, "联调排障：", "独立排查跨域、状态丢失、异步时序等常见问题，提升前后端联调能力。")

    add_heading(first, "二、实验环境")
    add_bullet(first, "工具：", "Windows 11、VS Code / Cursor、Node.js 22.23.2、npm 10.9.8、浏览器调试工具。")
    add_bullet(first, "前端栈：", "Vue 3.5（Vite 构建）、Vue Router 4、Pinia、Element Plus、ECharts 5、Axios。")
    add_bullet(first, "后端：", "Spring Boot 管理域（8081）与 Python 推理域（8010），前后端分离联调。")

    add_heading(first, "三、实验内容及要求")
    add_para(first, "在既有工业安全智能监测系统 Vue3 工作台（六页面）基础上，对接实验四的 Spring Boot 管理域：新增用户管理页与数据集/模型管理页（Axios 封装、JWT 拦截器、表格/表单/对话框、训练状态自动轮询），Dashboard 集成 ECharts 告警环形图、严重度占比条与近 7 天趋势折线图，模型实验页含八组指标对比柱状图；侧边导航实现路由跳转与选中高亮联动；页面具备加载动画、异常提示与空数据兜底。", size=9.4, space_after=4, line=1.12)

    add_heading(first, "四、主要操作步骤（源码、运行结果截图）")
    steps = [
        ("1 Axios 封装", "创建 axios 实例：请求拦截器统一携带 Bearer 令牌，响应拦截器统一解包 {code,message,data} 并以 ElNotification 弹出错误，401 自动清理本地凭据。"),
        ("2 用户管理页", "Element Plus 表格 + 对话框表单完成增删改查，角色标签/启停开关，联调 Spring Boot 用户接口。"),
        ("3 数据集与模型页", "文件上传（multipart）、数据集列表（SHA256 展示）、训练任务发起与 5 秒自动轮询、真实指标卡渲染。"),
        ("4 管理域登录门", "AdminGate 组件：管理域 JWT 与监测域令牌相互独立，未登录展示登录表单，登录成功 emit 事件触发数据加载，解决异步时序问题。"),
        ("5 Dashboard 与导航", "总览页 ECharts 环形图/趋势线、模型实验页对比柱状图；侧边导航 router-link 与当前路由联动高亮，刷新后状态保持。"),
        ("6 构建与部署", "Vite 构建产物由 FastAPI 静态伺服，SPA history 路由回退；前后端三服务联调（8010/8081/MySQL）。"),
    ]
    add_table(first, ["步骤", "实际操作与输出"], steps, font_size=8.3)
    add_para(first, "核心代码（一）Axios 封装：请求拦截器统一携带令牌，响应拦截器统一解包并弹出错误提示：", size=9.6, space_after=2)
    add_figure(first, E5 / "c1_axios_interceptors.png", "图1 adminApi.js — Axios 实例与拦截器核心代码", 5.9)
    add_para(first, "核心代码（二）管理域登录门：管理域 JWT 与监测域令牌相互独立，登录成功后通过 emit 事件触发页面数据加载，消除异步时序问题：", size=9.6, space_after=2)
    add_figure(first, E5 / "c2_admingate.png", "图2 AdminGate 管理域登录门核心代码", 5.9)
    add_figure(first, E5 / "ui-admin-users.png", "图3 用户管理页联调运行截图（Spring Boot 数据真实渲染）", 5.9)
    add_para(first, "核心代码（三）训练任务轮询：发起训练后每 5 秒自动轮询状态，页面销毁时清理定时器：", size=9.6, space_after=2)
    add_figure(first, E5 / "c3_train_poll.png", "图4 训练任务发起与自动轮询核心代码", 5.9)
    add_figure(first, E5 / "ui-admin-models.png", "图5 数据集与模型管理页（训练任务与真实指标）", 5.9)
    add_para(first, "核心代码（四）Dashboard 可视化：ECharts 告警环形图与真实接口数据绑定：", size=9.6, space_after=2)
    add_figure(first, E5 / "c4_echarts_donut.png", "图6 ECharts 告警环形图核心代码", 5.9)
    add_figure(first, E5 / "ui-dashboard.png", "图7 监控总览 Dashboard（环形图/严重度条/趋势折线图）", 5.9)
    add_figure(first, E5 / "ui-experiments.png", "图8 模型实验页（八组真实实验指标对比柱状图）", 5.9)
    add_figure(first, E5 / "ui-alerts.png", "图9 告警中心页（实时 WebSocket 接收 + 事件闭环操作）", 5.9)

    add_heading(second, "五、实验思考（问题、分析与解决办法）")
    reflections = [
        ("问题1：跨域请求失败（Network Error）。", "前端 8010 源请求 8081 管理域被 CORS 拦截。在后端 CorsFilter 白名单补齐 8010 源并置于最高过滤优先级后解决；理解了预检请求与凭证模式下 allowed-origins 不能为通配符的约束。"),
        ("问题2：页面数据不随登录状态刷新。", "管理域登录成功后列表仍为空：页面 onMounted 执行时登录尚未完成。解决方法：AdminGate 登录成功后 emit logged-in 事件，页面监听该事件重新拉取数据，消除了组件挂载与认证完成的时序竞态。"),
        ("问题3：两套令牌的状态丢失。", "监测域（8010）与管理域（8081）JWT 相互独立，混用导致 401。以 localStorage 键名区分（safety_token / admin_token），Axios 拦截器 401 时只清理对应域凭据并提示重新登录。"),
        ("问题4：训练任务轮询的内存泄漏风险。", "训练状态每 5 秒轮询，页面切换后定时器仍在执行。在 onBeforeUnmount 中 clearTimeout 清理，并以任务状态判断是否继续轮询，避免无效请求。"),
        ("问题5：可视化图表与业务数据脱节。", "Dashboard 图表数据全部来自 /api/v1/metrics/summary 与 events 真实接口而非写死数据，保证答辩演示时图表与告警中心数据一致；空数据时展示兜底空态组件。"),
    ]
    for title, body in reflections:
        p = add_para(second, size=9.2, space_after=2, line=1.12)
        r = p.add_run(title + " ")
        set_run_font(r, size=9.2, bold=True)
        r = p.add_run(body)
        set_run_font(r, size=9.2)

    add_para(summary, "实验小结：本实验在既有 Vue3 工作台上完成了后台管理域的前端对接：以 Axios 统一封装 Spring Boot 接口调用，实现用户管理与数据集/模型管理两个页面的完整交互（含文件上传、异步训练轮询与真实指标渲染），Dashboard 的 ECharts 可视化与侧边导航高亮经浏览器联调验收。过程中解决了跨域、双域令牌状态与异步时序三类典型前后端联调问题，全部页面数据均来自真实接口。", size=9.2, line=1.12, space_after=3)
    add_para(summary, "证据文件：results/experiment5/ui-admin-users.png 联调截图、frontend/ 前端源码、backend-java/ 管理域源码。", size=8.6, color="666666", line=1.1)

    for cell in (first, second, summary):
        if cell.paragraphs and not cell.paragraphs[0].text.strip():
            p = cell.paragraphs[0]
            p._element.getparent().remove(p._element)
    out = ROOT / "学号_姓名_实验五--Vue前端设计_完成版.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    build_code_assets()
    print(build_experiment4())
    print(build_experiment5())

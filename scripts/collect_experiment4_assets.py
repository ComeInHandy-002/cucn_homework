"""实验四素材收集：对 Spring Boot 管理域全接口做真实测试矩阵并落盘。

产出 results/experiment4/：
- api_test_matrix.txt   全接口正常/异常/边界场景的真实请求-响应记录
- mysql_schema.txt      MySQL 库表结构（真实 DESCRIBE 输出）
- project_tree.txt      backend-java 源码结构树
- train_log_tail.txt    真实训练任务日志尾部
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "experiment4"
BASE = "http://127.0.0.1:8081"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    lines: list[str] = []

    def record(title: str, method: str, url: str, expect_status: int = None, **kwargs):
        lines.append(f"### {title}")
        lines.append(f">> {method} {BASE}{url}")
        if "json" in kwargs:
            lines.append(f">> body: {json.dumps(kwargs['json'], ensure_ascii=False)}")
        resp = session.request(method, BASE + url, **kwargs)
        try:
            body = json.dumps(resp.json(), ensure_ascii=False)
        except Exception:
            body = resp.text[:200]
        lines.append(f"<< {resp.status_code} {body[:220]}")
        lines.append("")
        return resp

    admin_token = ""
    operator_token = ""

    record("注册新用户（正常）", "POST", "/auth/register", json={"username": "wangwu", "password": "test123456", "realName": "王五"})
    record("注册重复用户名（异常边界）", "POST", "/auth/register", json={"username": "wangwu", "password": "test123456"})
    record("注册密码过短（参数校验）", "POST", "/auth/register", json={"username": "lisi", "password": "123"})
    record("登录成功", "POST", "/auth/login", json={"username": "admin", "password": "admin123"})
    lines[-2] = lines[-2][:200]
    record("登录密码错误（异常）", "POST", "/auth/login", json={"username": "admin", "password": "wrong"})
    resp = record("operator 登录", "POST", "/auth/login", json={"username": "zhangsan", "password": "test123456"})
    operator_token = resp.json()["data"]["token"]
    record("无 token 访问管理接口（应 401）", "GET", "/api/users")
    record("operator 访问管理接口（应 403）", "GET", "/api/users", headers={"Authorization": f"Bearer {operator_token}"})
    admin_token = session.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}).json()["data"]["token"]
    auth = {"Authorization": f"Bearer {admin_token}"}
    record("用户列表（admin）", "GET", "/api/users", headers=auth)
    record("新增用户（admin）", "POST", "/api/users", headers=auth, json={"username": "lisi", "password": "test123456", "realName": "李四"})
    record("修改用户（admin）", "PUT", "/api/users/3", headers=auth, json={"role": "operator", "realName": "李四四", "enabled": True})
    record("删除用户（admin）", "DELETE", "/api/users/3", headers=auth)
    record("删除不存在用户（边界 404）", "DELETE", "/api/users/999", headers=auth)
    (OUT / "api_test_matrix.txt").write_text("\n".join(lines), encoding="utf-8")

    # MySQL 真实表结构
    schema = subprocess.run(
        ["mysql", "-h127.0.0.1", "-uroot", "-p6482727", "-e",
         "USE safety_admin; SHOW TABLES; DESCRIBE users; DESCRIBE datasets; DESCRIBE model_train_tasks;"],
        capture_output=True, text=True, timeout=30)
    (OUT / "mysql_schema.txt").write_text(schema.stdout, encoding="utf-8")

    # 项目结构树
    tree_lines = ["backend-java/"]
    for path in sorted((ROOT / "backend-java" / "src").rglob("*")):
        if path.is_file():
            tree_lines.append("  " + str(path.relative_to(ROOT / "backend-java")))
    (OUT / "project_tree.txt").write_text("\n".join(tree_lines), encoding="utf-8")

    log = ROOT / "backend-java" / "logs" / "train-1.log"
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        (OUT / "train_log_tail.txt").write_text("\n".join(tail), encoding="utf-8")

    print("素材收集完成：", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()

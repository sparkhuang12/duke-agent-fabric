from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from socket import socket
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def find_free_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(port: int, data_dir: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["DUKE_AGENT_DATA_DIR"] = str(data_dir)
    return subprocess.Popen(
        [sys.executable, "-m", "backend.server", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def request(
    base_url: str, path: str, payload: dict[str, Any] | None = None, expected_status: int = 200
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            if response.status != expected_status:
                raise AssertionError(f"{path} returned {response.status}, expected {expected_status}")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{path} returned HTTP {exc.code}: {detail}") from exc


def wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"server exited early:\n{output}")
        try:
            request(base_url, "/api/health")
            return
        except Exception:
            time.sleep(0.2)
    raise TimeoutError("server did not become ready")


def assert_api_flow(base_url: str) -> None:
    assert request(base_url, "/api/health")["status"] == "ok"
    assert len(request(base_url, "/api/agents")["items"]) == 6
    assert request(base_url, "/api/model/status")["ready"] is False

    document = request(
        base_url,
        "/api/documents",
        {
            "title": "API 自动化验证知识文件",
            "category": "policy",
            "department": "测试部门",
            "security_level": "内部",
            "summary": "用于验证知识入库和检索接口。",
            "content": "API 自动化验证包含知识检索、任务创建、人工确认和审计日志。",
        },
        expected_status=201,
    )
    assert document["title"] == "API 自动化验证知识文件"

    search = request(base_url, "/api/knowledge/search", {"keyword": "自动化验证", "category": "policy"})
    assert search["total"] >= 1

    task = request(
        base_url,
        "/api/tasks",
        {
            "title": "API 自动化验证任务",
            "agent_id": "document",
            "owner": "测试部门",
            "priority": "中",
            "summary": "验证任务创建和人工确认。",
        },
        expected_status=201,
    )
    approved = request(base_url, f"/api/tasks/{task['id']}/approve", {})
    assert approved["status"] == "approved"

    run_result = request(base_url, "/api/agents/document/run", {"prompt": "请起草测试通知"})
    assert run_result["model"]["status"] == "model_api_not_configured"

    audit_logs = request(base_url, "/api/audit-logs")["items"]
    assert any("知识文件已入库" in item["message"] for item in audit_logs)
    assert any("任务状态已更新" in item["message"] for item in audit_logs)


def main() -> None:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as data_dir:
        process = start_server(port, Path(data_dir))
        try:
            wait_for_server(base_url, process)
            assert_api_flow(base_url)
            print(f"API check passed: {base_url}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()

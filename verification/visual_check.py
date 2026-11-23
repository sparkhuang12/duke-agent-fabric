from __future__ import annotations

import os
import subprocess
import tempfile
import sys
import time
import urllib.request
from pathlib import Path
from socket import socket

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "verification" / "artifacts"
SCREENSHOT = ARTIFACT_DIR / "prototype-desktop.png"
MOBILE_SCREENSHOT = ARTIFACT_DIR / "prototype-mobile.png"


def run_chrome(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--virtual-time-budget=2500",
            *args,
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=45,
    )


def find_free_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(port: int, data_dir: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "duke_harness.cli", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env={**os.environ, "DUKE_DATA_DIR": data_dir, "DUKE_DATABASE_URL": f"sqlite:///{data_dir}/test.db"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"server exited early:\n{output}")
        try:
            with urllib.request.urlopen(f"{base_url}/api/v1/health/live", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - keep startup diagnostics simple.
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"server did not become ready: {last_error}")


def assert_dom_contains(base_url: str) -> None:
    dom = run_chrome(["--dump-dom", base_url]).stdout
    for term in ("第十三封来信", "章回目录", "没有寄件人的信", "出场人物", "未解伏笔", "续写本章"):
        if term not in dom:
            raise AssertionError(f"Novel desk missing term: {term}")


def inspect_screenshot(path: Path, min_width: int, min_height: int) -> None:
    with Image.open(path) as image:
        width, height = image.size
        if width < min_width or height < min_height:
            raise AssertionError(f"screenshot too small: {width}x{height}")

        rgb = image.convert("RGB")
        sampled = []
        non_background = 0
        total = 0
        for y in range(0, height, 20):
            for x in range(0, width, 20):
                pixel = rgb.getpixel((x, y))
                sampled.append(pixel)
                total += 1
                if pixel not in {(245, 243, 233), (255, 255, 255), (255, 254, 250)}:
                    non_background += 1

        unique_colors = len(set(sampled))
        if unique_colors < 40:
            raise AssertionError(f"screenshot appears visually sparse: {unique_colors} sampled colors")
        if non_background / total < 0.08:
            raise AssertionError("screenshot appears mostly blank")


def assert_screenshots_are_visual(base_url: str) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    run_chrome(["--window-size=1440,1100", f"--screenshot={SCREENSHOT}", base_url])
    run_chrome(["--window-size=390,1200", f"--screenshot={MOBILE_SCREENSHOT}", base_url])

    inspect_screenshot(SCREENSHOT, 1200, 900)
    inspect_screenshot(MOBILE_SCREENSHOT, 360, 900)


def main() -> None:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as data_dir:
        check_desk(base_url, port, data_dir)


def check_desk(base_url: str, port: int, data_dir: str) -> None:
    process = start_server(port, data_dir)
    try:
        wait_for_server(base_url, process)
        assert_dom_contains(base_url)
        assert_screenshots_are_visual(base_url)
        print(f"API and visual check passed: {base_url}")
        print(f"desktop screenshot: {SCREENSHOT}")
        print(f"mobile screenshot: {MOBILE_SCREENSHOT}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()

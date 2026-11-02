"""Real Qt consumers of contextual media, with isolated original fixtures."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.visual


def test_media_labels_are_literal_and_never_fetch_embedded_images(tmp_path: Path) -> None:
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    stream = io.BytesIO()
    Image.new("RGBA", (8, 8), (230, 30, 20, 255)).save(stream, format="PNG")
    image = stream.getvalue()
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    worker.start()
    try:
        # A valid preserved-source filename can start with markup. Its license
        # remains untrusted text even when the original image and hash are valid.
        label = (
            "<html>.png · 24x12 · CC0-1.0 "
            f"<img src='http://127.0.0.1:{server.server_port}/owned-marker.png'>"
        )
        harness = tmp_path / "literal-label.qml"
        harness.write_text(
            (ROOT / "tests/qml/check_native_context_media.qml")
            .read_text()
            .replace("ENGINE_IMPORT", (ROOT / "src/steamzero/ui/qml").as_uri())
        )
        env = dict(os.environ)
        env.update(
            QT_QPA_PLATFORM="offscreen",
            QT_QUICK_BACKEND="software",
            QT_FORCE_STDERR_LOGGING="1",
            QT_LOGGING_RULES="",
        )
        completed = subprocess.run(
            [runtime, str(harness), "--", "--label=" + label],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = completed.stdout + completed.stderr
        assert completed.returncode == 0, output
        assert "NATIVE-CONTEXT-LABEL " in output, output
        report = json.loads(output.split("NATIVE-CONTEXT-LABEL ", 1)[1].splitlines()[0])
        assert requests == [], "metadata display must not authorize network image requests"
        assert report["literal"] and report["popupLiteral"] and report["sceneLiteral"], report
        assert report["searchTitleLiteral"] and report["searchQueryLiteral"], report
        assert report["importLiteral"] and report["importNoticeLiteral"], report
        assert report["text"] == label
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_native_package_restoration_requires_the_users_confirmation() -> None:
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    env = dict(os.environ)
    env.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        QT_FORCE_STDERR_LOGGING="1",
        QT_LOGGING_RULES="",
    )
    completed = subprocess.run(
        [runtime, str(ROOT / "tests/qml/check_theme_editor_import.qml")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert "THEME-IMPORT-RECOVERY " in output, output
    report = json.loads(output.split("THEME-IMPORT-RECOVERY ", 1)[1].splitlines()[0])
    assert report == {"failures": 0, "packageApplyRequests": 2, "restoredWithConfirmation": True}


@pytest.mark.parametrize("dpr", [1, 1.5, 2])
def test_uniform_outline_and_scaled_physical_decode(tmp_path: Path, dpr: float) -> None:
    from PIL import ImageDraw

    if os.environ.get("QT_QUICK_BACKEND") == "software":
        pytest.skip(
            "QML-RHI-ENVIRONMENT-001: uniform outline pixels require RHI; "
            "software fallback is verified by the existing recipe/scene harnesses"
        )
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    image = Image.new("RGBA", (200, 100))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 20, 159, 79), fill=(30, 90, 220, 255))
    draw.rectangle((85, 35, 114, 64), fill=(0, 0, 0, 0))
    master = tmp_path / "original.png"
    image.save(master)
    output = tmp_path / "outline.png"
    if os.environ.get("SZ_CAPTURE_DIR"):
        output = Path(os.environ["SZ_CAPTURE_DIR"]) / f"outline-{dpr}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="rhi",
        QSG_RHI_BACKEND="opengl",
        QT_FORCE_STDERR_LOGGING="1",
        QT_LOGGING_RULES="",
        QT_SCALE_FACTOR=str(dpr),
    )
    result = subprocess.run(
        [
            runtime,
            str(ROOT / "tests/qml/check_asset_outline.qml"),
            "--",
            "--outline=" + json.dumps({"source": master.as_uri(), "output": str(output)}),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    logs = result.stdout + result.stderr
    assert result.returncode == 0, logs
    report = json.loads(logs.split("OUTLINE-DEMAND ", 1)[1].splitlines()[0])
    assert report["width"] == 60 * dpr and report["height"] == 30 * dpr, report
    assert report["state"] == "decoded", report
    with Image.open(output) as pixels:
        ratio = pixels.width / 200

        def white(x: int, y: int) -> bool:
            r, g, b, a = pixels.convert("RGBA").getpixel(
                (int((x + 0.5) * ratio), int((y + 0.5) * ratio))
            )
            # Boundary pixels blend with the source at fractional DPR. The
            # opaque interior below is checked separately from that boundary.
            return min(r, g, b) > 180 and a > 120

        # All four edges and the inner hole have the same four logical pixels.
        assert all(white(x, 25) for x in range(36, 40))
        assert all(white(50, y) for y in range(16, 20))
        assert all(white(x, 25) for x in range(160, 164))
        assert all(white(50, y) for y in range(80, 84))
        assert white(86, 50) and not white(90, 50)
        assert not white(35, 25) and not white(50, 15)
        for x, y in [(37, 25), (50, 17), (161, 25), (50, 81)]:
            assert min(pixels.getpixel((int((x + 0.5) * ratio), int((y + 0.5) * ratio)))) > 240

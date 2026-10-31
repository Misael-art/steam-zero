# SPDX-License-Identifier: GPL-3.0-or-later
"""Native wheel pixels and identity through the shared trusted Qt consumer."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageColor, ImageDraw

from steamzero.domain.asset_recipes import AssetRecipeBook, resolve_asset_recipes
from steamzero.domain.media_pipeline import MediaPipeline
from steamzero.domain.media_registry import Provenance
from steamzero.domain.scene_layout import LayoutBounds, LayoutRecipeBook, resolve_scene_layouts
from steamzero.domain.scene_motion import resolve_scene_motion

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.visual


def _original_master_bytes() -> bytes:
    # Original CC0 fixture, deliberately colorful with transparent holes.
    image = Image.new("RGBA", (240, 120))
    draw = ImageDraw.Draw(image)
    draw.ellipse((15, 15, 100, 105), fill=(240, 35, 60, 255))
    draw.rectangle((110, 15, 150, 105), fill=(25, 220, 70, 255))
    draw.polygon([(160, 105), (195, 15), (225, 105)], fill=(35, 65, 240, 255))
    draw.ellipse((35, 40, 70, 75), fill=(0, 0, 0, 0))
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    return encoded.getvalue()


@pytest.mark.parametrize("backend", ["opengl", "software"])
def test_native_wheel_pixels_identity_rapid_selection_and_decode_feedback(
    tmp_path: Path, backend: str
) -> None:
    if backend == "opengl" and os.environ.get("QT_QUICK_BACKEND") == "software":
        pytest.skip(
            "QML-RHI-ENVIRONMENT-001: pixel effects require RHI; "
            "software has explicit partial feedback"
        )
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    master = MediaPipeline(tmp_path / "media").preserve_source(
        _original_master_bytes(), "original.png", Provenance("fixture", "", "CC0-1.0")
    )
    source_uri = (tmp_path / "media" / master.path).as_uri()
    recipes, _ = resolve_asset_recipes(
        AssetRecipeBook.from_dict(
            {
                "schemaVersion": 1,
                "sourceSlot": "logo",
                "recipes": {
                    "side": {"source": "logo", "nodes": [{"type": "grayscale"}]},
                    "center": {
                        "source": "logo",
                        "nodes": [{"type": "outline", "width": 3, "color": "#ffffff"}],
                    },
                    "black": {
                        "source": "logo",
                        "nodes": [{"type": "silhouette", "color": "#000000"}],
                    },
                },
            }
        )
    )
    motion = resolve_scene_motion(
        {
            "schemaVersion": 1,
            "states": {"normal": {}, "focused": {}},
            "transitions": [
                {
                    "id": "enter",
                    "from": "normal",
                    "to": "focused",
                    "duration": 120,
                    "easing": "cubicOut",
                },
                {
                    "id": "exit",
                    "from": "focused",
                    "to": "normal",
                    "duration": 120,
                    "easing": "quadOut",
                },
                {
                    "id": "move",
                    "from": "normal",
                    "to": "normal",
                    "duration": 120,
                    "easing": "linear",
                },
            ],
        }
    ).to_qml_object()
    layouts = []
    for selected in [0, 1, 2, 1]:
        book = LayoutRecipeBook.from_dict(
            {
                "schemaVersion": 1,
                "layouts": {
                    "wheel": {
                        "source": "library.items",
                        "kind": "wheel",
                        "selected": selected,
                        "item": {"width": 160, "height": 100},
                        "gap": 32,
                        "highlight": {"scale": 1.25, "opacity": 1},
                        "template": {
                            "kind": "image",
                            "id": "art",
                            "properties": {"source": "asset:logo"},
                        },
                        "imageRecipes": {
                            "normal": "black" if len(layouts) == 3 else "side",
                            "focused": "center",
                        },
                        "motion": {
                            "enter": "enter",
                            "exit": "exit",
                            "move": "move",
                            "interruption": "retarget",
                        },
                    }
                },
            }
        )
        result = resolve_scene_layouts(
            book,
            {"library": {"items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}},
            bounds=LayoutBounds(800, 240),
            asset_uris={"logo": source_uri},
            asset_recipes={name: recipe.to_dict() for name, recipe in recipes.items()},
            motion=motion,
        )
        assert not result.diagnostics
        layouts.append(result.to_qml_object()["layouts"]["wheel"])
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    env = os.environ.copy()
    env.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="rhi" if backend == "opengl" else backend,
        QSG_RHI_BACKEND="opengl",
        QT_FORCE_STDERR_LOGGING="1",
        QT_LOGGING_RULES="",
    )
    captures = (
        Path(os.environ.get("SZ_CAPTURE_DIR", str(tmp_path / "captures")))
        / "native-wheel"
        / backend
    )
    captures.mkdir(parents=True, exist_ok=True)
    data = {"layouts": layouts, "corrupt": corrupt.as_uri(), "output": str(captures)}
    completed = subprocess.run(
        [
            runtime,
            str(ROOT / "tests/qml/check_native_wheel.qml"),
            "--",
            "--native-wheel=" + json.dumps(data),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert "NATIVE-WHEEL-RESULT" in output
    assert not any(
        word in output
        for word in (
            "TypeError",
            "ReferenceError",
            "SyntaxError",
            "Unable to assign",
            "Binding loop",
            "Cannot assign",
            "is not a type",
        )
    ), output
    assert ("software-partial" in output) == (backend == "software"), output
    if backend == "opengl":
        with Image.open(captures / "initial.png") as shot:
            side = [
                p for p in shot.convert("RGBA").crop((128, 70, 288, 170)).getdata() if p[3] > 100
            ]
            center = [
                p for p in shot.convert("RGBA").crop((300, 50, 500, 190)).getdata() if p[3] > 200
            ]
        assert side and sum(max(p[:3]) - min(p[:3]) for p in side) / len(side) < 4
        assert sum(max(p[:3]) - min(p[:3]) > 40 for p in center) > 200
        assert sum(min(p[:3]) > 240 for p in center) > 20, "white outline must actually render"
        with Image.open(captures / "silhouette.png") as shot:
            black = [
                p for p in shot.convert("RGBA").crop((128, 70, 288, 170)).getdata() if p[3] > 100
            ]
        assert black and max(max(p[:3]) for p in black) < 8


@pytest.mark.parametrize("compact", [False, True], ids=["wide", "compact-large-text"])
def test_wheel_authoring_controls_use_real_bridge_and_persist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, compact: bool
) -> None:
    import queue
    import re
    import threading

    from tests.integration.test_desktop_ui_bridge import Context
    from tests.integration.test_ui_shell_retrofe_import_late_response import RUNNER

    from steamzero.adapters.desktop_dashboard import DesktopDashboard
    from steamzero.adapters.desktop_ui import DesktopControlServer
    from steamzero.adapters.theme_catalog import ThemeCatalog
    from steamzero.core import paths
    from steamzero.core.state import StateStore
    from steamzero.domain.desktop import ExperienceCoordinator

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    master = MediaPipeline(paths.media_dir()).preserve_source(
        _original_master_bytes(),
        ("CC0-" + "original" * 24 + ".png") if compact else "CC0-original.png",
        Provenance("fixture", "", "CC0-1.0"),
    )
    dashboard = DesktopDashboard()
    created = dashboard.editor_create("Native wheel through controls")
    ready: queue.Queue[DesktopControlServer] = queue.Queue()

    def serve() -> None:
        store = StateStore(tmp_path / "state.db")
        store.migrate()
        server = DesktopControlServer(
            ExperienceCoordinator(Context(), (), store), "native-wheel-token", dashboard
        )
        ready.put(server)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            store.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=5)
    config = ROOT / "build/ui-native-wheel-authoring.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "apiUrl": f"http://127.0.0.1:{server.server_address[1]}",
                "apiToken": "native-wheel-token",
                "created": created,
                "compact": compact,
                "viewportWidth": 840 if compact else 1280,
                "visualScale": 1.5 if compact else 1.0,
                "captureDir": os.environ.get("SZ_CAPTURE_DIR", ""),
            }
        )
    )
    env = os.environ.copy()
    env.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        QT_FORCE_STDERR_LOGGING="1",
        QT_LOGGING_RULES="",
        QML_XHR_ALLOW_FILE_READ="1",
    )
    assert RUNNER is not None
    try:
        completed = subprocess.run(
            [str(RUNNER), "-input", str(ROOT / "tests/qml/check_native_wheel_authoring.qml")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    finally:
        config.unlink(missing_ok=True)
        server.shutdown()
        thread.join(timeout=3)
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert not any(
        word in output
        for word in (
            "ReferenceError",
            "TypeError",
            "Binding loop",
            "Cannot assign",
            "is not a type",
        )
    ), output
    identity = re.search(r"NATIVE-WHEEL-UI-THEME (\S+)", output)
    revision = re.search(r"NATIVE-WHEEL-UI-REVISION (\S+)", output)
    assert identity and revision, output
    manifest = json.loads((paths.themes_dir() / identity[1] / "theme.json").read_text())
    assert manifest["extends"] == "org.steamzero.default"
    assert manifest["assets"]["logo"] == f"master:sha256:{master.digest}"
    assert manifest["sceneLayouts"]["layouts"]["games"]["imageRecipes"] == {
        "normal": "side",
        "focused": "original",
    }
    assert manifest["assetRecipes"]["recipes"]["side"]["nodes"][0]["type"] == "grayscale"
    assert manifest["assetRecipes"]["recipes"]["original"]["nodes"][0]["width"] == 3
    assert manifest["assetRecipes"]["recipes"]["muted"]["nodes"][0]["amount"] == 0.5
    assert manifest["assetRecipes"]["recipes"]["shadow"]["nodes"][0]["color"] == "#000000"
    assert manifest["sceneLayouts"]["layouts"]["games"]["highlight"]["scale"] == 1.35
    assert manifest["sceneLayouts"]["layouts"]["games"]["motion"]["interruption"] == "retarget"
    assert (
        ThemeCatalog().resolve(identity[1]).to_theme_qml_object()["logicalRevision"] == revision[1]
    )
    assert len(list((paths.media_dir() / "masters").rglob("*.png"))) == 1
    assert not list(paths.themes_dir().rglob("*.png"))

    from steamzero.adapters.launcher_ui import LauncherBridge
    from steamzero.domain.scene_layout import LayoutBounds

    bridge = LauncherBridge(
        sections=(), context_path=tmp_path / "context.json", on_launch=lambda _id: None
    )
    runtime_theme = ThemeCatalog().resolve(identity[1]).to_theme_qml_object()
    records = [
        {"id": key, "gameId": key, "title": "Game " + key.upper()}
        for key in ("a", "b", "c", "d", "e", "f", "g", "h", "i")
    ]
    scenes = []
    for selected in records[:3]:
        view = {
            "menuId": "games",
            "menuName": "Native games",
            "journeyId": "fixture.native",
            "generation": 1,
            "resultState": "ready",
            "items": records,
            "selectedItemId": selected["id"],
            "theme": runtime_theme,
        }
        scene = bridge._journey_cinema(
            view,
            "journey:games:" + selected["id"],
            bounds=LayoutBounds(800, 240),
            width=800,
            height=240,
        )
        assert scene["layoutResolutionState"] == "theme"
        assert scene["layoutId"] == "games"
        assert not scene["diagnostics"]
        scenes.append(scene)
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    capture_root = os.environ.get("SZ_CAPTURE_DIR", "")
    capture_path = Path(capture_root or str(tmp_path)) / (
        "launcher-compact.png" if compact else "launcher-wide.png"
    )
    native_rhi = os.environ.get("QT_QUICK_BACKEND") != "software"
    payload = {
        "scenes": scenes,
        "revision": revision[1],
        "capture": str(capture_path),
        "expectEffects": native_rhi,
    }
    runtime_env = dict(env)
    if native_rhi:
        runtime_env.update(QT_QUICK_BACKEND="rhi", QSG_RHI_BACKEND="opengl")
    played = subprocess.run(
        [
            runtime,
            str(ROOT / "tests/qml/check_native_wheel_runtime.qml"),
            "--",
            "--native-runtime=" + json.dumps(payload),
        ],
        cwd=ROOT,
        env=runtime_env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    playback_output = played.stdout + played.stderr
    assert played.returncode == 0, playback_output
    assert "NATIVE-RUNTIME-RESULT" in playback_output
    assert not any(
        word in playback_output
        for word in (
            "ReferenceError",
            "TypeError",
            "SyntaxError",
            "Binding loop",
            "Cannot assign",
            "Unable to assign",
            "is not a type",
        )
    ), playback_output

    with Image.open(capture_path) as rendered:
        background_pixel = rendered.convert("RGB").getpixel((10, 200))
    expected_background = ImageColor.getrgb(runtime_theme["resolved"]["color"]["background"])
    assert (
        max(abs(c - d) for c, d in zip(background_pixel, expected_background[:3], strict=True))
        <= 10
    ), (
        "Launcher must consume the authored theme background with its text palette",
        background_pixel,
        expected_background,
    )

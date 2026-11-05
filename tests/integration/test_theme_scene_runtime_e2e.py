# SPDX-License-Identifier: GPL-3.0-or-later
"""V2 — cenas ES-DE/RetroFE com imagens válidas, desenhadas pelo QML a partir da bridge real."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from tests.integration.test_desktop_ui_bridge import Context
from tests.integration.test_experience_journey_bridge_e2e import _request
from tests.integration.test_experience_journey_bridge_e2e import journey_bridge as journey_bridge
from tests.integration.test_ui_shell_retrofe_import_late_response import RUNNER

from steamzero.adapters.desktop_dashboard import DesktopDashboard
from steamzero.adapters.desktop_ui import DesktopControlServer
from steamzero.adapters.journey_studio import JourneyStudioService
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.core import paths, transaction
from steamzero.core.errors import SteamZeroError
from steamzero.core.state import StateStore
from steamzero.domain import theme_assets, theme_import_retrofe, theme_scene
from steamzero.domain.desktop import ExperienceCoordinator
from steamzero.domain.experience_journey import JourneyStore
from steamzero.launcher.app import _render_journey_xml_scene
from steamzero.launcher.app import main as launcher_main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "themes"
HARNESS = ROOT / "tests" / "qml" / "check_theme_scene_runtime_e2e.qml"
ESDE_ID = "org.steamzero.fixture.esde-mini"
RETROFE_ID = "org.example.retrofe-e2e"


def test_fixtures_sao_imagens_validas_e_licenciadas() -> None:
    from PIL import Image

    for path in (
        FIXTURES / "esde-mini" / "fundo.png",
        FIXTURES / "retrofe-mini" / "assets" / "logo.png",
    ):
        with Image.open(path) as image:
            image.verify()
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    for directory in ("esde-mini", "retrofe-mini"):
        assert "CC0-1.0" in (FIXTURES / directory / "LICENSE.txt").read_text()


def _install_esde() -> None:
    store = theme_assets.ThemeAssetStore(paths.theme_assets_dir())
    assets = {
        source.name: {"digest": store.put(source.name, source.read_bytes()).digest}
        for source in (FIXTURES / "esde-mini").iterdir()
        if source.suffix in {".png", ".xml"}
    }
    directory = paths.themes_dir() / ESDE_ID
    directory.mkdir(parents=True)
    (directory / "theme.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "steamzero-theme-v1",
                "id": ESDE_ID,
                "name": "Fixture ES-DE mínimo",
                "version": "1",
                "license": "CC0-1.0",
                "assets": assets,
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.visual
def test_qml_desenha_pixels_das_cenas_esde_e_retrofe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    isolated = tmp_path / "profile"
    isolated.mkdir(mode=0o700)
    (isolated / "data").mkdir(mode=0o700)
    monkeypatch.setenv("XDG_DATA_HOME", str(isolated / "data"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))
    _install_esde()
    source = tmp_path / "retrofe"
    shutil.copytree(FIXTURES / "retrofe-mini", source)
    layout = source / "layout.xml"
    layout.write_text(
        layout.read_text().replace(
            "/></layout>",
            """><onEnter><set duration="0.5">
            <animate type="alpha" from="0" to="0.85"/>
            <animate type="x" to="480"/>
            <animate type="y" to="25%"/>
            </set></onEnter>
            <onExit><set duration="0.2"><animate type="alpha" to="0"/></set></onExit>
            </image></layout>""",
        )
    )
    dashboard = DesktopDashboard()
    monkeypatch.setattr(
        dashboard,
        "snapshot",
        lambda _status: {
            "emulation": {
                "editorialPlatforms": [
                    {
                        "id": "nes",
                        "games": [{"id": "probe", "platform": "nes", "name": "Probe"}],
                    }
                ]
            },
        },
    )
    dashboard.theme_import_retrofe_apply(
        str(source), "layout", RETROFE_ID, "RetroFE E2E", "Autor", "CC0-1.0"
    )
    ready: queue.Queue[DesktopControlServer] = queue.Queue()

    def run_server() -> None:
        store = StateStore(tmp_path / "state.db")
        store.migrate()
        server = DesktopControlServer(
            ExperienceCoordinator(Context(), (), store), "scene-token", dashboard
        )
        ready.put(server)
        server.serve_forever()
        server.server_close()
        store.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    server = ready.get(timeout=5)
    config = tmp_path / "fixture.json"
    harness = tmp_path / "check_theme_scene_runtime_e2e.qml"
    harness.write_text(
        HARNESS.read_text()
        .replace("../../src/steamzero/ui/qml", (ROOT / "src/steamzero/ui/qml").as_uri())
        .replace("FIXTURE_CONFIG", config.as_uri()),
        encoding="utf-8",
    )
    config.write_text(
        json.dumps(
            {
                "apiUrl": f"http://127.0.0.1:{server.server_port}",
                "apiToken": "scene-token",
                "esdeId": ESDE_ID,
                "retrofeId": RETROFE_ID,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QML_XHR_ALLOW_FILE_READ": "1",
        }
    )

    def run_qt(*cases: str) -> None:
        completed = subprocess.run(
            [str(RUNNER), "-input", str(harness), *cases],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        assert completed.returncode == 0, f"render de cena reprovou:\n{output[-5000:]}"
        assert "FAIL" not in output, output[-5000:]

    try:
        run_qt(
            "ThemeSceneRuntimeE2E::test_01_esde_instalado_desenha_pixels_do_asset",
            "ThemeSceneRuntimeE2E::test_02_retrofe_importado_desenha_pixels_do_asset",
            "ThemeSceneRuntimeE2E::test_03_studio_reabre_e_reproduz_cena_salva",
            "ThemeSceneRuntimeE2E::test_04_jornada_salva_e_previsualiza_cena_retrofe",
        )
    finally:
        server.shutdown()
        thread.join(timeout=3)

    saved = JourneyStore(paths.data_home() / "journeys")
    journey_id = saved.active_id()
    assert journey_id
    document = saved.load(journey_id)
    assert document.menus[0]["appearance"] == {
        "mode": "imported-scene",
        "sceneId": RETROFE_ID,
    }
    copy = server.journey_studio.import_copy(saved.export_copy(document), copy_name="Cópia")
    assert copy["document"]["menus"][0]["appearance"] == document.menus[0]["appearance"]
    assert copy["sceneDependencies"] == [RETROFE_ID] and copy["dependencies"] == []
    preview = dashboard.theme_imported_scene_render(RETROFE_ID)
    with theme_scene.imported_scene_publication(create=False):
        with pytest.raises(SteamZeroError, match="aguarde a gravação"):
            dashboard.theme_store_gc(apply=True)
        assert theme_scene.resolve_journey_imported_scene(RETROFE_ID)["state"] == "busy"
    assert dashboard.theme_store_gc(apply=True)["protectedByImportedScenes"] == 1
    sidecar = paths.scenes_dir() / f"{RETROFE_ID}.assets.json"
    preserved_metadata = sidecar.read_bytes()
    sidecar.write_text("null")
    with pytest.raises(SteamZeroError, match="metadados RetroFE ilegíveis"):
        dashboard.theme_store_gc(apply=True)
    sidecar.write_bytes(preserved_metadata)
    assert dashboard.theme_imported_scene_render(RETROFE_ID)["scene"] == preview["scene"]
    _assert_launcher_resolves_saved_scene(
        isolated, tmp_path, monkeypatch, journey_id, preview, run_qt, config
    )


def _assert_launcher_resolves_saved_scene(
    isolated: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    journey_id: str,
    preview: dict[str, Any],
    run_qt: Callable[[str], None] | None = None,
    config: Path | None = None,
) -> None:
    native = paths.themes_dir() / RETROFE_ID
    shutil.copytree(paths.themes_dir() / ESDE_ID, native)
    manifest = native / "theme.json"
    manifest.write_text(manifest.read_text().replace(ESDE_ID, RETROFE_ID))
    native_scene = _render_journey_xml_scene(RETROFE_ID)
    assert native_scene["scene"]["origin"]["family"] == "esde"
    library = tmp_path / "library.json"
    library.write_text(json.dumps({"games": [{"id": "probe", "platform": "nes", "name": "Probe"}]}))
    launched: list[LauncherBridge] = []

    def capture(bridge: LauncherBridge) -> int:
        launched.append(bridge)
        return 0

    def read_cinema() -> dict[str, Any]:
        bridge = launched[-1]
        current = bridge.journey_current()
        assert current["journeyId"] == journey_id
        item = current["items"][0]
        focus_id = f"journey:{current['menuId']}:{item['id']}"
        return bridge.cinema(focus_id, width=800, height=600)

    with monkeypatch.context() as patch:
        patch.setattr("steamzero.adapters.launcher_ui.launch_launcher_ui", capture)
        patch.delenv("WAYLAND_DISPLAY", raising=False)
        patch.setenv("DISPLAY", ":isolated-launcher-fixture")
        for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
            patch.setenv(key, os.environ.get(key, ""))
        argv = ["--library", str(library), "--isolated-library", "--isolated-root", str(isolated)]
        assert launcher_main(argv) == 0
        cinema = read_cinema()
        theme = cinema["theme"]
        assert (
            theme["requestedSceneId"] == RETROFE_ID and theme["sceneResolutionState"] == "resolved"
        )
        assert theme["compiledScene"] == preview["scene"]
        if run_qt is not None and config is not None:
            config.write_text(json.dumps({"launcher": cinema}))
            run_qt("ThemeSceneRuntimeE2E::test_05_launcher_reproduz_a_mesma_cena")

        manifest = json.loads((paths.scenes_dir() / f"{RETROFE_ID}.assets.json").read_text())
        digest = next(iter(manifest["assets"].values()))["digest"]
        blob = theme_assets.ThemeAssetStore(paths.theme_assets_dir()).blob_path(digest)
        held = tmp_path / "held-asset"
        blob.rename(held)
        assert read_cinema()["theme"]["sceneResolutionState"] == "degraded"
        held.rename(blob)
        assert read_cinema()["theme"]["sceneResolutionState"] == "resolved"

        scene = paths.scenes_dir() / f"{RETROFE_ID}.json"
        preserved = scene.with_suffix(".preserved")
        scene.rename(preserved)
        missing = read_cinema()
        theme = missing["theme"]
        assert theme["sceneResolutionState"] == "failed"
        assert theme["requestedSceneId"] == RETROFE_ID and "compiledScene" not in theme
        if run_qt is not None and config is not None:
            config.write_text(json.dumps({"launcher": missing}))
            run_qt("ThemeSceneRuntimeE2E::test_06_launcher_preserva_a_navegacao_sem_cena")
        scene.write_text('{"views": "corrompido"}')
        assert read_cinema()["theme"]["sceneResolutionState"] == "failed"
        preserved.replace(scene)
        assert read_cinema()["theme"]["compiledScene"] == preview["scene"]


def test_launcher_resolves_imported_scene_without_changing_an_identical_native_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated = tmp_path / "profile"
    isolated.mkdir(mode=0o700)
    (isolated / "data").mkdir(mode=0o700)
    monkeypatch.setenv("XDG_DATA_HOME", str(isolated / "data"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))
    _install_esde()
    theme_import_retrofe.apply(
        str(FIXTURES / "retrofe-mini"),
        "layout",
        scene_id=RETROFE_ID,
        name="RetroFE",
        author="Fixture",
        license_id="CC0-1.0",
    )
    service = JourneyStudioService(paths.data_home() / "journeys")
    initial = service.create(name="Cena importada")
    session = initial["sessionId"]
    updated = service.transact(
        session,
        "set-menu-appearance",
        {"menuId": "home", "appearance": {"mode": "imported-scene", "sceneId": RETROFE_ID}},
    )
    service.save(session)
    service.activate(
        session,
        expected_generation=updated["generation"],
        published_read_models={"library.games": {"id": "string", "name": "string"}},
    )
    _assert_launcher_resolves_saved_scene(
        isolated,
        tmp_path,
        monkeypatch,
        initial["document"]["id"],
        theme_scene.render_imported_scene(RETROFE_ID),
    )


def test_journey_http_reports_missing_scene_and_reuses_its_id_after_reimport(
    journey_bridge: tuple[str, str, Any],
) -> None:
    base, token, _dashboard = journey_bridge
    created = _request(
        base, token, "/journey/studio/create", method="POST", payload={"name": "RetroFE"}
    )
    session = created["sessionId"]
    edited = _request(
        base,
        token,
        "/journey/studio/transact",
        method="POST",
        payload={
            "operation": "set-menu-appearance",
            "payload": {
                "sessionId": session,
                "expectedGeneration": created["generation"],
                "menuId": "home",
                "appearance": {"mode": "imported-scene", "sceneId": RETROFE_ID},
            },
        },
    )
    payload = {"sessionId": session, "menuId": "home", "expectedGeneration": edited["generation"]}
    missing = _request(
        base, token, "/journey/studio/engine-preview", method="POST", payload=payload
    )
    assert missing["themeResolutionState"] == "missing-reference"
    assert missing["importedScenePreview"]["scene"] is None
    theme_import_retrofe.apply(
        str(FIXTURES / "retrofe-mini"),
        "layout",
        scene_id=RETROFE_ID,
        name="RetroFE",
        author="Fixture",
        license_id="CC0-1.0",
    )
    catalog = _request(base, token, "/journey/studio/catalog")
    assert catalog["importedScenes"] == [{"id": RETROFE_ID}]
    result = _request(base, token, "/journey/studio/engine-preview", method="POST", payload=payload)
    assert result["themeResolutionState"] == "custom"
    assert (
        result["importedScenePreview"]["scene"]
        == theme_scene.render_imported_scene(RETROFE_ID)["scene"]
    )
    assert result["coverage"]["stages"][0]["declaredSceneId"] == RETROFE_ID


@pytest.mark.parametrize("first_suffix", ["", ".assets"])
@pytest.mark.parametrize("overwrite", [False, True])
def test_imported_ids_cannot_replace_another_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_suffix: str, overwrite: bool
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    dashboard = DesktopDashboard()
    base = "org.example.collision"
    first = base + first_suffix
    second = base if first_suffix else base + ".assets"
    args = (str(FIXTURES / "retrofe-mini"), "layout")
    dashboard.theme_import_retrofe_apply(*args, first, "First", "Fixture", "CC0-1.0")
    before = {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    with pytest.raises(SteamZeroError):
        dashboard.theme_import_retrofe_apply(
            *args, second, "Second", "Fixture", "CC0-1.0", overwrite=overwrite
        )
    assert before == {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    assert theme_scene.render_imported_scene(first)["assets"]["resolved"] == 1
    assert dashboard.theme_store_gc(apply=True)["orphans"] == 0


@pytest.mark.parametrize("abrupt", [False, True])
def test_imported_publication_recovers_whole_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, abrupt: bool
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    dashboard = DesktopDashboard()
    args = (str(FIXTURES / "retrofe-mini"), "layout", RETROFE_ID)
    dashboard.theme_import_retrofe_apply(*args, "First", "Fixture", "CC0-1.0")
    before = {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    activated = 0

    def fail(stage: str) -> None:
        nonlocal activated
        if stage == "apply.activate":
            activated += 1
            if activated == 1:
                if abrupt:
                    raise transaction.SimulatedKill()
                raise OSError("controlled publication failure")

    transaction.set_crash_hook(fail)
    try:
        with pytest.raises((OSError, transaction.SimulatedKill)):
            dashboard.theme_import_retrofe_apply(
                *args, "Second", "Fixture", "CC0-1.0", overwrite=True
            )
    finally:
        transaction.set_crash_hook(None)
    if abrupt:
        with pytest.raises(SteamZeroError):
            dashboard.theme_store_gc(apply=True)
        assert theme_scene.resolve_journey_imported_scene(RETROFE_ID)["state"] == "failed"
        transaction.recover_all()
    assert before == {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    assert theme_scene.render_imported_scene(RETROFE_ID)["assets"]["resolved"] == 1
    dashboard.theme_import_retrofe_apply(*args, "Retry", "Fixture", "CC0-1.0", overwrite=True)
    assert theme_scene.render_imported_scene(RETROFE_ID)["assets"]["resolved"] == 1


def test_imported_rollback_keeps_previous_artwork_through_gc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    source = tmp_path / "source"
    shutil.copytree(FIXTURES / "retrofe-mini", source)
    dashboard = DesktopDashboard()
    args = (str(source), "layout", RETROFE_ID, "Scene", "Fixture", "CC0-1.0")
    first = dashboard.theme_import_retrofe_apply(*args)
    original = {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    shutil.copyfile(FIXTURES / "esde-mini" / "fundo.png", source / "assets" / "logo.png")
    second = dashboard.theme_import_retrofe_apply(*args, overwrite=True)
    assert first["assets"]["files"] != second["assets"]["files"]
    assert dashboard.theme_store_gc(apply=True)["protectedByRollback"] == 1
    transaction.rollback(second["operationId"])
    assert original == {p.name: p.read_bytes() for p in paths.scenes_dir().iterdir()}
    assert theme_scene.render_imported_scene(RETROFE_ID)["assets"]["resolved"] == 1


@pytest.mark.parametrize("damage", ["missing", "null", "schema", "identity", "link", "revision"])
def test_imported_overwrite_preserves_unknown_previous_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    dashboard = DesktopDashboard()
    args = (str(FIXTURES / "retrofe-mini"), "layout", RETROFE_ID, "Scene", "Fixture", "CC0-1.0")
    saved = dashboard.theme_import_retrofe_apply(*args)
    target = Path(saved["assets"]["manifestPath"])
    original = target.read_bytes()
    if damage == "missing":
        target.unlink()
    elif damage == "null":
        target.write_text("null")
    elif damage == "link":
        other = tmp_path / "owned-test-file"
        other.write_bytes(original)
        target.unlink()
        target.symlink_to(other)
    else:
        value = json.loads(original)
        key = {"schema": "schemaVersion", "identity": "sceneId", "revision": "sceneSha256"}[damage]
        value[key] = "unknown"
        target.write_text(json.dumps(value))
    before_scene = Path(saved["path"]).read_bytes()
    before_manifest = target.read_bytes() if target.exists() else None
    with pytest.raises(SteamZeroError):
        dashboard.theme_import_retrofe_apply(*args, overwrite=True)
    assert Path(saved["path"]).read_bytes() == before_scene
    assert (target.read_bytes() if target.exists() else None) == before_manifest

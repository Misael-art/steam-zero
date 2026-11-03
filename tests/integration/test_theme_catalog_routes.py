# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Rotas do catálogo de temas ES-DE, exercidas pela ponte da UI.

Uma sonda comportamental, não estrutural: cada rota é chamada e o EFEITO é
verificado no disco. Conferir apenas que a ação aparece no contrato provaria
que alguém a declarou, não que ela faz alguma coisa — e um controle declarado
que não age é precisamente o defeito que este projeto vem removendo.
"""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from steamzero.adapters.desktop_contracts import handheld_ui_contracts
from steamzero.adapters.desktop_dashboard import DesktopDashboard
from steamzero.core.errors import SteamZeroError
from steamzero.domain import theme_acquire
from steamzero.domain.theme_sources import ThemeSource

_COMMIT = "b" * 40


@pytest.fixture
def dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DesktopDashboard:
    """Isola o estado do usuário: nenhuma rota pode tocar o HOME real."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    from steamzero.core import paths

    paths.themes_dir().mkdir(parents=True, exist_ok=True)
    return DesktopDashboard()


def _fake_theme(tmp_path: Path, theme_id: str, files: dict[str, bytes]) -> ThemeSource:
    archive = tmp_path / f"{theme_id}.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for name, payload in files.items():
            info = tarfile.TarInfo(f"repo-{_COMMIT[:8]}/{name}")
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))
    return ThemeSource(
        id=theme_id,
        name=theme_id,
        family="esde",
        author="Autora",
        credits=("Autora",),
        license_id="CC0-1.0",
        license_source="LICENSE",
        homepage="",
        forge="github",
        repo="dono/repo",
        commit=_COMMIT,
    )


def _native_removal_target(dashboard: DesktopDashboard) -> tuple[str, Path, bytes]:
    from steamzero.core import paths

    session = str(dashboard.editor_create("Referenced native theme")["sessionId"])
    saved = dashboard.editor_save(session)
    dashboard.editor_cancel(session)
    theme_id = saved["themeId"]
    manifest = paths.themes_dir() / theme_id / "theme.json"
    return theme_id, manifest, manifest.read_bytes()


def test_removal_refuses_active_preference_and_recovers_after_switch(
    dashboard: DesktopDashboard,
) -> None:
    from steamzero.domain.theme_preferences import ThemePreferenceManager

    theme_id, manifest, original = _native_removal_target(dashboard)
    manager = ThemePreferenceManager()
    plan = manager.plan_activate(theme_id, "1.0.0")
    assert plan is not None
    manager.apply(plan.plan_id, plan.confirm_token)
    preference = manager._preference_path().read_bytes()
    with pytest.raises(SteamZeroError, match="E-THEME-ACTIVE"):
        dashboard.theme_catalog_uninstall(theme_id)
    assert manifest.read_bytes() == original
    assert manager._preference_path().read_bytes() == preference
    next_plan = manager.plan_activate("org.steamzero.default", "1.0.0")
    assert next_plan is not None
    manager.apply(next_plan.plan_id, next_plan.confirm_token)
    assert dashboard.theme_catalog_uninstall(theme_id)["removed"]
    assert manager._read_preference()["themeId"] == "org.steamzero.default"


def test_activation_plan_refuses_a_theme_removed_after_preview(dashboard: DesktopDashboard) -> None:
    from steamzero.core import paths

    theme_id, _manifest, _original = _native_removal_target(dashboard)
    planned = dashboard.plan_theme_apply(theme_id)
    assert planned["status"] == "ready"
    assert dashboard.theme_catalog_uninstall(theme_id)["removed"]
    with pytest.raises(SteamZeroError, match=r"E-THEME-NOT-FOUND|E-TX-STALE-PLAN"):
        dashboard.apply_theme_preference(planned["planId"], planned["confirmToken"])
    assert not paths.theme_preference_path().exists()


def test_http_directory_alias_preserves_the_active_theme_then_allows_explicit_recovery(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    import queue
    import threading
    import urllib.error

    from tests.integration.test_desktop_ui_bridge import Context, request_json

    from steamzero.adapters.desktop_ui import DesktopControlServer
    from steamzero.core import paths
    from steamzero.core.state import StateStore
    from steamzero.domain.desktop import ExperienceCoordinator

    theme_id, manifest, original = _native_removal_target(dashboard)
    alias = paths.themes_dir() / "org.example.directory-alias"
    alias.symlink_to(manifest.parent, target_is_directory=True)
    ready: queue.Queue[DesktopControlServer] = queue.Queue()

    def serve() -> None:
        with StateStore(tmp_path / "alias-http-state.db") as state:
            state.migrate()
            server = DesktopControlServer(
                ExperienceCoordinator(Context(), (), state), "owned-alias-token", dashboard
            )
            ready.put(server)
            try:
                server.serve_forever(poll_interval=0.02)
            finally:
                server.server_close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    server = ready.get(timeout=5)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        planned = request_json(base, "owned-alias-token", "/theme/apply", {"themeId": theme_id})
        request_json(
            base,
            "owned-alias-token",
            "/theme/apply/confirm",
            {"planId": planned["planId"], "confirmToken": planned["confirmToken"]},
        )
        preference = paths.theme_preference_path().read_bytes()
        for selected, code in [(alias.name, "E-THEME-UNSAFE"), (theme_id, "E-THEME-ACTIVE")]:
            with pytest.raises(urllib.error.HTTPError) as exc:
                request_json(
                    base, "owned-alias-token", "/theme/catalog/uninstall", {"themeId": selected}
                )
            assert json.loads(exc.value.read())["error"]["code"] == code
            assert manifest.read_bytes() == original
            assert paths.theme_preference_path().read_bytes() == preference
        assert alias.is_symlink()
        alias.unlink()
        planned = request_json(
            base, "owned-alias-token", "/theme/apply", {"themeId": "org.steamzero.default"}
        )
        request_json(
            base,
            "owned-alias-token",
            "/theme/apply/confirm",
            {"planId": planned["planId"], "confirmToken": planned["confirmToken"]},
        )
        removed = request_json(
            base, "owned-alias-token", "/theme/catalog/uninstall", {"themeId": theme_id}
        )
        assert removed["removed"]
        assert not manifest.exists()
        assert (
            json.loads(paths.theme_preference_path().read_text())["themeId"]
            == "org.steamzero.default"
        )
    finally:
        server.shutdown()
        worker.join(timeout=3)
        assert not worker.is_alive()


def test_activation_plan_refuses_a_version_changed_after_preview(
    dashboard: DesktopDashboard,
) -> None:
    from steamzero.core import paths

    theme_id, _manifest, _original = _native_removal_target(dashboard)
    planned = dashboard.plan_theme_apply(theme_id)
    session = str(dashboard.editor_load(theme_id)["sessionId"])
    dashboard.editor_set_metadata(session, "version", "2.0.0")
    dashboard.editor_save(session, overwrite=True)
    dashboard.editor_cancel(session)
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        dashboard.apply_theme_preference(planned["planId"], planned["confirmToken"])
    assert not paths.theme_preference_path().exists()


def test_preference_rollback_refuses_missing_theme_and_recovers_after_reimport(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    from steamzero.core import paths

    theme_id, _manifest, _original = _native_removal_target(dashboard)
    session = str(dashboard.editor_load(theme_id)["sessionId"])
    package = tmp_path / "recovery.zip"
    package.write_bytes(dashboard.editor_export_zip(session))
    dashboard.editor_cancel(session)
    initial_preview = dashboard.theme_import_zip_inspect(str(package))
    assert initial_preview["alreadyInstalled"] and not initial_preview["hasPreservedData"]
    first = dashboard.plan_theme_apply(theme_id)
    dashboard.apply_theme_preference(first["planId"], first["confirmToken"])
    second = dashboard.plan_theme_apply("org.steamzero.default")
    changed = dashboard.apply_theme_preference(second["planId"], second["confirmToken"])
    assert dashboard.theme_catalog_uninstall(theme_id)["removed"]
    current = paths.theme_preference_path().read_bytes()
    with pytest.raises(SteamZeroError, match=r"E-THEME-NOT-FOUND|E-TX-STALE-PLAN"):
        dashboard.rollback_theme(changed["operationId"])
    assert paths.theme_preference_path().read_bytes() == current
    # Removal retains the owned directory/assets. Recovery explicitly confirms
    # replacement rather than treating that preserved data as disposable.
    preview = dashboard.theme_import_zip_inspect(str(package))
    assert not preview["alreadyInstalled"] and preview["hasPreservedData"]
    with pytest.raises(SteamZeroError):
        dashboard.theme_import_zip_apply(str(package))
    assert paths.theme_preference_path().read_bytes() == current
    dashboard.theme_import_zip_apply(str(package), overwrite=True)
    assert dashboard.rollback_theme(changed["operationId"])["status"] == "rolled-back"
    assert json.loads(paths.theme_preference_path().read_text())["themeId"] == theme_id
    assert dashboard.rollback_theme(changed["operationId"])["status"] == "rolled-back"


@pytest.mark.parametrize("draft_kind", ["loaded", "child", "history"])
def test_removal_preserves_open_drafts_and_their_undo_dependencies(
    dashboard: DesktopDashboard, draft_kind: str
) -> None:
    theme_id, manifest, original = _native_removal_target(dashboard)
    if draft_kind == "loaded":
        session = str(dashboard.editor_load(theme_id)["sessionId"])
    else:
        session = str(dashboard.editor_create("Unsaved dependent", theme_id)["sessionId"])
        if draft_kind == "history":
            dashboard.editor_set_metadata(session, "extends", "org.steamzero.default")
    with pytest.raises(SteamZeroError, match="rascunho"):
        dashboard.theme_catalog_uninstall(theme_id)
    assert manifest.read_bytes() == original
    if draft_kind == "history":
        restored = dashboard.editor_undo(session)
        assert restored["manifest"]["extends"] == theme_id
    dashboard.editor_cancel(session)
    assert dashboard.theme_catalog_uninstall(theme_id)["removed"]


@pytest.mark.parametrize(
    "damaged",
    [b"not-json", b"[]", b'{"themeId":42}', b" " * 4097],
    ids=["malformed-json", "wrong-root", "wrong-id", "oversize"],
)
def test_unknown_preference_refuses_removal_without_overwriting_either_file(
    dashboard: DesktopDashboard, damaged: bytes
) -> None:
    from steamzero.core import paths

    theme_id, manifest, original = _native_removal_target(dashboard)
    preference = paths.theme_preference_path()
    preference.parent.mkdir(parents=True, exist_ok=True)
    preference.write_bytes(damaged)
    with pytest.raises(SteamZeroError, match="preferência"):
        dashboard.theme_catalog_uninstall(theme_id)
    assert manifest.read_bytes() == original
    assert preference.read_bytes() == damaged
    preference.unlink()
    assert dashboard.theme_catalog_uninstall(theme_id)["removed"]


@pytest.mark.parametrize("consumer", ["saved", "draft", "history", "bezel"])
def test_http_removal_preserves_journey_consumers_and_recovers_after_release(
    dashboard: DesktopDashboard, tmp_path: Path, consumer: str
) -> None:
    import queue
    import threading
    import urllib.error

    from tests.integration.test_desktop_ui_bridge import Context, request_json

    from steamzero.adapters.desktop_ui import DesktopControlServer
    from steamzero.adapters.journey_studio import JourneyStudioService
    from steamzero.core.state import StateStore
    from steamzero.domain.desktop import ExperienceCoordinator

    theme_id, manifest, original = _native_removal_target(dashboard)
    journeys = JourneyStudioService(tmp_path / "journey-service")
    session = str(journeys.create(name="Dependent", journey_id="org.example.consumer")["sessionId"])
    if consumer == "bezel":
        journeys.transact(
            session,
            "set-stage-bezel",
            {
                "stageId": "bezel",
                "bezelResource": f"asset://bezels/{theme_id}@1.0.0-" + "a" * 64 + ".png",
            },
        )
    else:
        journeys.transact(
            session,
            "set-menu-appearance",
            {"menuId": "home", "appearance": {"mode": "custom", "themeId": theme_id}},
        )
    if consumer == "history":
        journeys.transact(
            session,
            "set-menu-appearance",
            {"menuId": "home", "appearance": {"mode": "inherit-aura"}},
        )
    if consumer == "saved":
        journeys.save(session)
        journeys.close(session)
    before = journeys.snapshot(session) if consumer != "saved" else None
    saved_files = {p: p.read_bytes() for p in (tmp_path / "journey-service").glob("*.journey.json")}
    ready: queue.Queue[DesktopControlServer] = queue.Queue()

    def serve() -> None:
        with StateStore(tmp_path / "journey-bridge.db") as store:
            store.migrate()
            server = DesktopControlServer(
                ExperienceCoordinator(Context(), (), store), "consumer-test", dashboard, journeys
            )
            ready.put(server)
            try:
                server.serve_forever(poll_interval=0.02)
            finally:
                server.server_close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    server = ready.get(timeout=3)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as refused:
            request_json(base, "consumer-test", "/theme/catalog/uninstall", {"themeId": theme_id})
        assert refused.value.code == 409
        failure = json.loads(refused.value.read())
        assert "jornada" in str(failure).lower()
        assert manifest.read_bytes() == original
        assert all(p.read_bytes() == data for p, data in saved_files.items())
        if before is not None:
            assert journeys.snapshot(session) == before
        if consumer == "saved":
            reopened = str(journeys.load("org.example.consumer")["sessionId"])
            journeys.transact(
                reopened,
                "set-menu-appearance",
                {"menuId": "home", "appearance": {"mode": "inherit-aura"}},
            )
            journeys.save(reopened, overwrite=True)
            journeys.close(reopened)
        else:
            journeys.close(session)
        removed = request_json(
            base, "consumer-test", "/theme/catalog/uninstall", {"themeId": theme_id}
        )
        assert removed["removed"] is True
    finally:
        server.shutdown()
        worker.join(timeout=3)
        assert not worker.is_alive()


@pytest.mark.parametrize("compatibility_snapshot", [True, False])
def test_gc_preserves_assets_owned_by_a_live_theme_rollback(
    dashboard: DesktopDashboard, tmp_path: Path, compatibility_snapshot: bool
) -> None:
    from steamzero.core import paths
    from steamzero.domain.theme_assets import live_digests

    source = _fake_theme(
        tmp_path, "org.esde.iconic", {"theme.xml": b"<theme/>", "old.png": b"owned old artwork"}
    )
    store = dashboard._theme_store()
    transaction = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    initial = theme_acquire.ingest_archive(tmp_path / "org.esde.iconic.tar.gz", source, store)
    transaction.install(source, initial)
    manifest = paths.themes_dir() / source.id / "theme.json"
    original = manifest.read_bytes()
    previous = json.loads(original)
    _fake_theme(
        tmp_path, "org.esde.iconic", {"theme.xml": b"<theme/>", "new.png": b"owned new artwork"}
    )
    latest = theme_acquire.ingest_archive(tmp_path / "org.esde.iconic.tar.gz", source, store)
    installed = transaction.install(source, latest, force=True)
    snapshot = paths.staging_for(installed["operationId"]) / "previous-theme.json"
    assert snapshot.is_file()
    if not compatibility_snapshot:
        # The core journal/backup owns recovery even if the compatibility view
        # was not published before an interruption, or was removed afterwards.
        snapshot.unlink()
    collected = dashboard.theme_store_gc(apply=True)
    assert store.verify(live_digests([previous]))["ok"], (
        "GC must preserve the real rollback's assets"
    )
    assert collected["protectedByRollback"] > 0
    assert dashboard.theme_catalog_rollback(source.id, installed["operationId"])["restoredPrevious"]
    assert manifest.read_bytes() == original
    assert store.verify(live_digests([previous]))["ok"]


@pytest.mark.parametrize("stage", ["apply.backup", "apply.verify", "apply.after-commit"])
def test_interrupted_theme_publication_recovers_from_the_core_backup(
    dashboard: DesktopDashboard, stage: str
) -> None:
    from tests.unit.test_theme_acquire import _source

    from steamzero.core import paths, transaction
    from steamzero.domain.theme_assets import live_digests

    store = dashboard._theme_store()
    source = _source()
    old = store.put("theme.xml", b"<theme>previous</theme>")
    new = store.put("theme.xml", b"<theme>replacement</theme>")
    publisher = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": old.digest}),
    )
    manifest = paths.themes_dir() / source.id / "theme.json"
    original = manifest.read_bytes()
    previous = json.loads(original)
    before = set(paths.journal_dir().glob("*.jsonl"))
    code = """
from tests.unit.test_theme_acquire import _source
from steamzero.core import paths
from steamzero.domain.theme_acquire import AcquisitionReport, ThemeTransaction
from steamzero.domain.theme_assets import ThemeAssetStore
import sys
source = _source()
ThemeTransaction(paths.themes_dir(), ThemeAssetStore(paths.theme_assets_dir())).install(
    source, AcquisitionReport(theme_id=source.id, assets={'theme.xml': sys.argv[1]}), force=True
)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", code, new.digest],
        env={
            **os.environ,
            "STEAMZERO_CRASH_AT": stage,
            "PYTHONPATH": os.pathsep.join(sys.path),
        },
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert crashed.returncode == -signal.SIGKILL, crashed.stderr.decode(errors="replace")
    created = set(paths.journal_dir().glob("*.jsonl")) - before
    assert len(created) == 1
    operation_id = created.pop().stem
    assert not (paths.staging_for(operation_id) / "previous-theme.json").exists()
    dashboard.theme_store_gc(apply=True)
    assert store.verify(live_digests([previous]))["ok"]
    recovered = transaction.recover_operation(operation_id)
    if stage == "apply.after-commit":
        assert recovered.outcome == "kept"
        assert manifest.read_bytes() != original
        assert publisher.rollback(source.id, operation_id)["restoredPrevious"]
    else:
        assert recovered.outcome == "rolled-back"
    assert manifest.read_bytes() == original
    assert transaction.recover_operation(operation_id).outcome == "already-terminal"
    assert store.verify(live_digests([previous]))["ok"]


@pytest.mark.parametrize(
    "damage",
    [
        "bytes",
        "symlink",
        "directory",
        "journal",
        "empty-journal",
        "journal-header",
        "journal-identity",
        "journal-kind",
    ],
)
def test_damaged_core_recovery_refuses_collection_and_restoration_then_recovers(
    dashboard: DesktopDashboard, tmp_path: Path, damage: str
) -> None:
    from tests.unit.test_theme_acquire import _source

    from steamzero.core import journal, paths

    source = _source()
    store = dashboard._theme_store()
    old = store.put("theme.xml", b"<theme>before</theme>")
    new = store.put("theme.xml", b"<theme>after</theme>")
    orphan = store.put("orphan.png", b"retained until ownership is known")
    publisher = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": old.digest}),
    )
    manifest = paths.themes_dir() / source.id / "theme.json"
    original = manifest.read_bytes()
    replaced = publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": new.digest}),
        force=True,
    )
    operation_id = replaced["operationId"]
    current = manifest.read_bytes()
    (paths.staging_for(operation_id) / "previous-theme.json").unlink()
    intent = next(r for r in journal.read_records(operation_id) if r["type"] == "action.intent")
    backup = paths.backup_for(operation_id) / intent["actionId"]
    selected = paths.journal_path(operation_id) if "journal" in damage else backup
    preserved = selected.read_bytes()
    selected.unlink()
    if damage == "symlink":
        foreign = tmp_path / "unowned.json"
        foreign.write_bytes(preserved)
        selected.symlink_to(foreign)
    elif damage == "directory":
        selected.mkdir()
    elif damage in {"journal-header", "journal-identity", "journal-kind"}:
        records = [json.loads(line) for line in preserved.splitlines()]
        if damage == "journal-header":
            records[0]["padding"] = "x" * 4096
        elif damage == "journal-identity":
            records[0]["operationId"] = "0" * 26
        else:
            records[0]["kind"] = None
        selected.write_bytes(b"".join(json.dumps(record).encode() + b"\n" for record in records))
    else:
        selected.write_bytes(b"" if damage == "empty-journal" else b"invalid recovery bytes")
    with pytest.raises(SteamZeroError):
        dashboard.theme_store_gc(apply=True)
    with pytest.raises(SteamZeroError):
        publisher.rollback(source.id, operation_id)
    assert manifest.read_bytes() == current
    assert store.blob_path(orphan.digest).read_bytes() == b"retained until ownership is known"
    if damage == "directory":
        selected.rmdir()
    else:
        selected.unlink()
    selected.write_bytes(preserved)
    if damage == "symlink":
        assert foreign.read_bytes() == preserved
    assert publisher.rollback(source.id, operation_id)["restoredPrevious"]
    assert manifest.read_bytes() == original
    assert publisher.rollback(source.id, operation_id)["restoredPrevious"]


def test_gc_shares_the_core_journal_without_claiming_other_domains_or_reopening_undo(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    from tests.unit.test_theme_acquire import _source

    from steamzero.core import paths, transaction

    source = _source()
    store = dashboard._theme_store()
    old = store.put("theme.xml", b"<theme>previous</theme>")
    new = store.put("theme.xml", b"<theme>replacement</theme>")
    publisher = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": old.digest}),
    )
    replacement = publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": new.digest}),
        force=True,
    )
    foreign = tmp_path / "other-domain.cfg"
    foreign.write_bytes(b"before")
    plan = transaction.plan_write_files({foreign: b"after"}, root=tmp_path, kind="emulator.config")
    applied = transaction.apply(plan.plan_id, plan.confirm_token)
    note = paths.journal_dir() / "unowned-note.txt"
    note.write_bytes(b"preserve this unrelated file")
    assert dashboard.theme_store_gc(apply=True)["protectedByRollback"] > 0
    assert foreign.read_bytes() == b"after"
    assert publisher.rollback(source.id, replacement["operationId"])["restoredPrevious"]
    dashboard.theme_store_gc(apply=True)
    assert store.verify([old.digest])["ok"]
    assert not store.blob_path(new.digest).exists()
    assert foreign.read_bytes() == b"after"
    assert note.read_bytes() == b"preserve this unrelated file"
    assert transaction.rollback(applied.operation_id).status == "rolled-back"
    assert foreign.read_bytes() == b"before"


@pytest.mark.parametrize(
    ("budget", "remaining"),
    [
        ("MAX_THEME_JOURNAL_BYTES", 64),
        ("MAX_THEME_JOURNAL_RECORDS", 1),
        ("MAX_THEME_JOURNAL_SCAN_ENTRIES", 1),
        ("MAX_THEME_JOURNAL_SCAN_BYTES", 1),
        ("MAX_ROLLBACK_MANIFEST_BYTES", 1),
        ("MAX_ROLLBACK_MANIFESTS", 0),
        ("MAX_ROLLBACK_TOTAL_BYTES", 1),
    ],
)
def test_exhausted_core_recovery_budget_preserves_data_and_releases_gc_after_retry(
    dashboard: DesktopDashboard,
    monkeypatch: pytest.MonkeyPatch,
    budget: str,
    remaining: int,
) -> None:
    from tests.unit.test_theme_acquire import _source

    from steamzero.core import paths

    source = _source()
    store = dashboard._theme_store()
    old = store.put("theme.xml", b"<theme>previous</theme>")
    new = store.put("theme.xml", b"<theme>replacement</theme>")
    orphan = store.put("orphan.png", b"unreferenced but not disposable before the audit")
    publisher = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": old.digest}),
    )
    manifest = paths.themes_dir() / source.id / "theme.json"
    original = manifest.read_bytes()
    replaced = publisher.install(
        source,
        theme_acquire.AcquisitionReport(theme_id=source.id, assets={"theme.xml": new.digest}),
        force=True,
    )
    operation_id = replaced["operationId"]
    (paths.staging_for(operation_id) / "previous-theme.json").unlink()
    current = manifest.read_bytes()
    journal = paths.journal_path(operation_id).read_bytes()
    with monkeypatch.context() as patch:
        # A deliberately exhausted allowance exercises the real producer's
        # Core backups; production limits and application assertions stay fixed.
        patch.setattr(theme_acquire, budget, remaining)
        with pytest.raises(SteamZeroError, match=r"E-THEME-(LIMIT|MANIFEST)"):
            dashboard.theme_store_gc(apply=True)
    assert manifest.read_bytes() == current
    assert paths.journal_path(operation_id).read_bytes() == journal
    assert store.verify([old.digest, new.digest, orphan.digest])["ok"]
    assert dashboard.theme_store_gc(apply=True)["protectedByRollback"] > 0
    assert not store.blob_path(orphan.digest).exists()
    assert store.verify([old.digest, new.digest])["ok"]
    assert publisher.rollback(source.id, operation_id)["restoredPrevious"]
    assert manifest.read_bytes() == original


@pytest.mark.parametrize(
    "damage", ["invalid-json", "invalid-digest", "symlink", "count", "bytes", "total"]
)
def test_gc_refuses_unknown_rollback_ownership_without_deleting_blobs(
    dashboard: DesktopDashboard, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from steamzero.core import ids, paths

    store = dashboard._theme_store()
    digest = store.put("owned.png", b"owned orphan awaiting explicit collection").digest
    blob = store.blob_path(digest)
    original = blob.read_bytes()
    directory = paths.staging_for(ids.new_ulid())
    directory.mkdir(parents=True)
    snapshot = directory / "previous-theme.json"
    payload = json.dumps({"assets": {"old.png": {"digest": digest}}}).encode()
    snapshot.write_bytes(payload)
    if damage == "invalid-json":
        snapshot.write_bytes(b"{")
    elif damage == "invalid-digest":
        snapshot.write_text('{"assets":{"old.png":{"digest":"unknown"}}}')
    elif damage == "symlink":
        outside = tmp_path / "owned-external-snapshot.json"
        outside.write_bytes(payload)
        snapshot.unlink()
        snapshot.symlink_to(outside)
    elif damage == "count":
        monkeypatch.setattr(theme_acquire, "MAX_ROLLBACK_MANIFESTS", 0)
    elif damage == "bytes":
        monkeypatch.setattr(theme_acquire, "MAX_ROLLBACK_MANIFEST_BYTES", len(payload) - 1)
    else:
        monkeypatch.setattr(theme_acquire, "MAX_ROLLBACK_TOTAL_BYTES", len(payload) - 1)
    before = snapshot.read_bytes()
    with pytest.raises(SteamZeroError, match=r"E-THEME-MANIFEST|E-THEME-LIMIT"):
        dashboard.theme_store_gc(apply=True)
    assert blob.read_bytes() == original
    assert snapshot.read_bytes() == before


def test_every_catalog_action_is_declared_in_the_contract() -> None:
    actions = {action["id"] for action in handheld_ui_contracts()["actions"]}

    assert {
        "theme.catalog.list",
        "theme.catalog.install",
        "theme.catalog.rollback",
        "theme.catalog.uninstall",
        "theme.store.gc",
    } <= actions


def test_destructive_actions_require_explicit_confirmation() -> None:
    """Remover tema e apagar blob não podem acontecer sem pedido."""
    actions = {action["id"]: action for action in handheld_ui_contracts()["actions"]}

    assert actions["theme.catalog.uninstall"]["confirmation"]["required"] is True
    assert actions["theme.catalog.uninstall"]["confirmation"]["mode"] == "explicit"
    assert actions["theme.store.gc"]["confirmation"]["required"] is True
    # Instalar não é destrutivo e não exige confirmação extra.
    assert actions["theme.catalog.install"]["confirmation"]["required"] is False


def test_list_publishes_the_curated_entries_and_the_excluded_ones(
    dashboard: DesktopDashboard,
) -> None:
    """Os excluídos viajam com o motivo: a ausência não pode parecer
    esquecimento."""
    payload = dashboard.theme_catalog_list()

    assert len(payload["entries"]) == 5
    assert all(entry["installed"] is False for entry in payload["entries"])
    assert len(payload["excluded"]) == 4
    for item in payload["excluded"]:
        assert "licen" in item["reason"].casefold()
    assert payload["storeUsage"]["blobs"] == 0


def test_list_marks_what_is_installed_and_whether_it_is_up_to_date(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    from steamzero.core import paths

    source = _fake_theme(tmp_path, "org.esde.iconic", {"theme.xml": b"<theme/>"})
    report = theme_acquire.ingest_archive(
        tmp_path / "org.esde.iconic.tar.gz", source, dashboard._theme_store()
    )
    theme_acquire.ThemeTransaction(paths.themes_dir(), dashboard._theme_store()).install(
        source, report
    )

    entry = next(e for e in dashboard.theme_catalog_list()["entries"] if e["id"] == source.id)

    assert entry["installed"] is True
    # A versão instalada é a do commit falso, não a do catálogo: instalado e
    # atualizado são coisas diferentes, e a rota precisa distingui-las.
    assert entry["installedVersion"] == _COMMIT[:12]
    assert entry["upToDate"] is False


def test_uninstall_removes_the_theme_and_gc_reclaims_only_orphans(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    """O ciclo que o operador pediu: remover sem quebrar o vizinho."""
    from steamzero.core import paths

    shared = b"asset compartilhado" * 32
    store = dashboard._theme_store()
    transaction = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    for theme_id, own in (("org.esde.iconic", b"<a/>"), ("org.esde.modern", b"<b/>")):
        source = _fake_theme(tmp_path, theme_id, {"s.png": shared, "t.xml": own})
        report = theme_acquire.ingest_archive(tmp_path / f"{theme_id}.tar.gz", source, store)
        transaction.install(source, report)
    blobs_before = store.usage()["blobs"]

    dashboard.theme_catalog_uninstall("org.esde.iconic")

    # Remover não apaga blob: o compartilhado ainda tem dono.
    assert store.usage()["blobs"] == blobs_before
    preview = dashboard.theme_store_gc()
    assert preview["dryRun"] is True
    assert preview["orphans"] == 1  # só o XML exclusivo do tema removido

    applied = dashboard.theme_store_gc(apply=True)
    assert applied["orphans"] == 1
    # O vizinho continua íntegro depois da coleta.
    remaining = json.loads(
        (paths.themes_dir() / "org.esde.modern" / "theme.json").read_text(encoding="utf-8")
    )
    assert store.verify(entry["digest"] for entry in remaining["assets"].values())["ok"] is True


def test_rollback_route_restores_the_previous_manifest(
    dashboard: DesktopDashboard, tmp_path: Path
) -> None:
    from steamzero.core import paths

    store = dashboard._theme_store()
    transaction = theme_acquire.ThemeTransaction(paths.themes_dir(), store)
    first = _fake_theme(tmp_path, "org.esde.iconic", {"t.xml": b"<v1/>"})
    transaction.install(
        first,
        theme_acquire.ingest_archive(tmp_path / "org.esde.iconic.tar.gz", first, store),
    )
    manifest_path = paths.themes_dir() / "org.esde.iconic" / "theme.json"
    before = manifest_path.read_bytes()

    second = _fake_theme(tmp_path, "org.esde.iconic", {"t.xml": b"<v2-diferente/>"})
    upgraded = transaction.install(
        second,
        theme_acquire.ingest_archive(tmp_path / "org.esde.iconic.tar.gz", second, store),
        force=True,
    )
    assert manifest_path.read_bytes() != before

    undone = dashboard.theme_catalog_rollback("org.esde.iconic", upgraded["operationId"])

    assert undone["restoredPrevious"] is True
    assert undone["assetsPreserved"] is True
    assert manifest_path.read_bytes() == before


def test_installing_a_theme_outside_the_catalog_is_refused(
    dashboard: DesktopDashboard,
) -> None:
    """A rota não é uma porta para URL arbitrária: só o curado passa."""
    with pytest.raises(SteamZeroError) as excinfo:
        dashboard.theme_catalog_install("org.esde.slick")
    assert excinfo.value.code == "E-THEME-NOT-FOUND"


def test_packaged_builtin_aura_is_visible_to_the_editor_without_a_host_copy(
    dashboard: DesktopDashboard,
) -> None:
    """D-24: o AURA do pacote aparece no catálogo e abre no editor com a
    paleta própria mesmo quando XDG_DATA_HOME é um tmp vazio.

    A visibilidade vem do recurso empacotado (importlib.resources), não de uma
    cópia em ``~/.local/share/steamzero/themes`` — esconder o defeito copiando
    o tema para o estado do usuário é exatamente o que esta trava impede.
    """
    from steamzero.core import paths

    assert list(paths.themes_dir().iterdir()) == []

    entry = next(item for item in dashboard.theme_list() if item["id"] == "org.steamzero.aura")
    assert entry["origin"] == "builtin"
    assert entry["compatible"] is True
    assert entry["state"] == "available"

    opened = dashboard.editor_load("org.steamzero.aura")
    preview = opened["preview"]
    assert isinstance(preview, dict)
    resolved = preview["resolved"]
    assert isinstance(resolved, dict)
    assert resolved["color"]["background"] == "#0b1020"

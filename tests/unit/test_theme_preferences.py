from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamzero.core.errors import SteamZeroError
from steamzero.domain.theme_preferences import ThemePreferenceManager


def _make_manager(tmp_path: Path) -> ThemePreferenceManager:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return ThemePreferenceManager(config_dir=config_dir)


class TestThemePreferencePlan:
    def test_plan_activate_creates_plan(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        target = mgr._preference_path()
        previous = mgr._read_preference()
        assert previous is None

        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=previous)
        assert plan.plan_id
        assert plan.confirm_token
        assert plan.kind == "theme.preference.activate"
        assert len(plan.actions) == 1
        assert plan.actions[0].target == str(target)
        assert not target.exists()

    def test_plan_activate_different_theme(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        previous = {"schemaVersion": 1, "themeId": "org.steamzero.default", "themeVersion": "1.0.0"}
        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=previous)
        assert plan.plan_id

    def test_plan_activate_same_theme_is_informational_noop(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        previous = {"schemaVersion": 1, "themeId": "org.steamzero.default", "themeVersion": "1.0.0"}
        assert mgr.plan_activate("org.steamzero.default", "1.0.0", previous=previous) is None
        assert not list((tmp_path / "state").glob("**/*"))


@pytest.mark.parametrize("version", ["1.0.0", "legacy-revision", "2.0.0rc1"])
def test_removal_reference_uses_the_existing_writer_without_reinterpreting_versions(
    tmp_path: Path, version: str
) -> None:
    manager = _make_manager(tmp_path)
    assert manager.referenced_theme_id() is None
    plan = manager.plan_activate("org.example.active", version)
    assert plan is not None
    manager.apply(plan.plan_id, plan.confirm_token)
    original = manager._preference_path().read_bytes()
    assert manager.referenced_theme_id() == "org.example.active"
    assert manager._preference_path().read_bytes() == original


def test_removal_reference_refuses_symlink_and_read_failure_without_altering_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.domain import theme_preferences as module

    manager = _make_manager(tmp_path)
    outside = tmp_path / "owned-preference.json"
    original = b'{"schemaVersion":1,"themeId":"org.example.active"}'
    outside.write_bytes(original)
    manager._preference_path().symlink_to(outside)
    with pytest.raises(SteamZeroError, match="preferência"):
        manager.referenced_theme_id()
    assert outside.read_bytes() == original
    manager._preference_path().unlink()
    manager._preference_path().write_bytes(original)
    real_open = module.os.open

    def denied(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == manager._preference_path():
            raise PermissionError("owned fixture")
        return real_open(path, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(module.os, "open", denied)
        with pytest.raises(SteamZeroError, match="preferência"):
            manager.referenced_theme_id()
    assert manager._preference_path().read_bytes() == original


@pytest.mark.parametrize("kind", ["owned.unrelated", "theme.preference.activate"])
def test_theme_preference_rollback_refuses_an_unrelated_operation(
    tmp_path: Path, kind: str
) -> None:
    from steamzero.core import transaction

    manager = _make_manager(tmp_path)
    unrelated = tmp_path / "owned-unrelated.txt"
    unrelated.write_bytes(b"before")
    plan = transaction.plan_write_files({unrelated: b"after"}, root=tmp_path, kind=kind)
    applied = transaction.apply(plan.plan_id, plan.confirm_token)
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        manager.rollback(applied.operation_id)
    assert unrelated.read_bytes() == b"after"
    assert transaction.rollback(applied.operation_id).status == "rolled-back"
    assert unrelated.read_bytes() == b"before"


def test_nonregular_preference_refuses_removal_without_waiting_for_a_writer(tmp_path: Path) -> None:
    import os

    manager = _make_manager(tmp_path)
    os.mkfifo(manager._preference_path())
    with pytest.raises(SteamZeroError, match="preferência"):
        manager.referenced_theme_id()
    assert manager._preference_path().exists()


class TestThemePreferenceApplyRollback:
    def test_full_cycle(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        target = mgr._preference_path()

        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=None)
        assert not target.exists()

        with pytest.raises(SteamZeroError, match=r"E-TX-CONFIRM-REQUIRED"):
            mgr.apply(plan.plan_id, "wrong-token")

        result = mgr.apply(plan.plan_id, plan.confirm_token)
        assert result.status == "ok"
        assert target.exists()
        written = json.loads(target.read_text())
        assert written["themeId"] == "org.steamzero.steamdeck"
        assert written["themeVersion"] == "1.0.0"

        rb = mgr.rollback(result.operation_id)
        assert rb.status == "rolled-back"
        assert not target.exists()

    def test_rollback_restores_previous(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        target = mgr._preference_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '{"schemaVersion":1,"themeId":"org.steamzero.default","themeVersion":"1.0.0","revision":0}'
        )

        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=None)
        result = mgr.apply(plan.plan_id, plan.confirm_token)
        assert json.loads(target.read_text())["themeId"] == "org.steamzero.steamdeck"

        rb = mgr.rollback(result.operation_id)
        assert rb.status == "rolled-back"
        assert target.exists()
        restored = json.loads(target.read_text())
        assert restored["themeId"] == "org.steamzero.default"

    def test_rollback_idempotent(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=None)
        result = mgr.apply(plan.plan_id, plan.confirm_token)
        assert result.status == "ok"

        rb1 = mgr.rollback(result.operation_id)
        assert rb1.status == "rolled-back"
        rb2 = mgr.rollback(result.operation_id)
        assert rb2.status == "rolled-back"

    def test_stale_plan_detected(self, tmp_path: Path) -> None:
        mgr = _make_manager(tmp_path)
        plan = mgr.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=None)
        target = mgr._preference_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        with pytest.raises(SteamZeroError, match=r"E-TX-STALE-PLAN"):
            mgr.apply(plan.plan_id, plan.confirm_token)

    def test_wrong_root_plan_rejected(self, tmp_path: Path) -> None:
        mgr_a = _make_manager(tmp_path)
        mgr_b = ThemePreferenceManager(config_dir=tmp_path / "other")
        (tmp_path / "other").mkdir(parents=True, exist_ok=True)
        plan = mgr_a.plan_activate("org.steamzero.steamdeck", "1.0.0", previous=None)
        with pytest.raises(SteamZeroError, match=r"E-TX-STALE-PLAN"):
            mgr_b.apply(plan.plan_id, plan.confirm_token)

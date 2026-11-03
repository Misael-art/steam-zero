# SPDX-License-Identifier: GPL-3.0-or-later
"""M11 — canais de frontend (SRM manifests + ES-DE custom systems) via CLI.

Fluxo ponta a ponta: plan -> apply -> verify (convergido) -> plan noop ->
rollback, com envio de envelopes JSON e estado isolado em XDG dirs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamzero.cli import main as cli

GAMES = [
    {"id": "zelda-botw", "title": "The Legend of Zelda: Breath of the Wild"},
    {"id": "mario-odyssey", "title": "Super Mario Odyssey"},
]


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    state = tmp_path / "state"
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("STEAMZERO_NO_DAEMON", "1")
    return tmp_path, state, config


def _spec_path(tmp_path: Path, *, only: str | None = None) -> Path:
    spec: dict[str, object] = {"srm": {}, "esde": {}}
    if only in (None, "srm"):
        spec["srm"] = {
            "collections": [
                {"slug": "switch", "games": GAMES},
            ]
        }
    if only in (None, "esde"):
        spec["esde"] = {
            "systems": [
                {
                    "name": "steamzero-switch",
                    "label": "Nintendo Switch",
                    "path": "/media/games/switch",
                    "extensions": [".nsp", ".xci"],
                    "platform": "switch",
                    "theme": "switch",
                }
            ]
        }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _run(capsys: pytest.CaptureFixture[str], args: list[str]) -> tuple[int, dict]:
    code = cli.main(args)
    out = capsys.readouterr().out
    return code, json.loads(out)


@pytest.mark.parametrize("target", ["srm", "esde"])
@pytest.mark.parametrize("kind", ["emulator.config", "theme.acquire"])
def test_frontend_rollback_refuses_a_foreign_operation_without_changing_its_files(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path], target: str, kind: str
) -> None:
    from steamzero.core import fs, transaction

    root, _state, _config = isolated
    unrelated = root / "owned-unrelated.cfg"
    fs.write_atomic(unrelated, b"before")
    plan = transaction.plan_write_files({unrelated: b"after"}, root=root, kind=kind)
    applied = transaction.apply(plan.plan_id, plan.confirm_token)
    code, result = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            target,
            "--operation-id",
            applied.operation_id,
            "--json",
        ],
    )
    assert code != 0, result
    assert unrelated.read_bytes() == b"after"
    assert transaction.rollback(applied.operation_id).status == "rolled-back"
    assert unrelated.read_bytes() == b"before"


@pytest.mark.parametrize("producer", ["srm", "esde"])
def test_frontend_rollback_refuses_the_other_frontends_operation(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path], producer: str
) -> None:
    root, _state, config = isolated
    spec = _spec_path(root)
    code, preview = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    plan = preview["data"][producer]
    code, applied = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            producer,
            "--plan-id",
            plan["planId"],
            "--confirm",
            plan["confirmToken"],
            "--json",
        ],
    )
    assert code == 0
    owned = config / (
        "ES-DE/custom_systems/es_systems.xml"
        if producer == "esde"
        else "steam-rom-manager/userData/manifests/steamzero-manifest-switch.json"
    )
    before = owned.read_bytes()
    other = "esde" if producer == "srm" else "srm"
    code, result = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            other,
            "--operation-id",
            applied["data"]["operationId"],
            "--json",
        ],
    )
    assert code != 0, result
    assert owned.read_bytes() == before


@pytest.mark.parametrize("target", ["srm", "esde"])
def test_frontend_rollback_refuses_its_kind_at_an_unrelated_root(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path], target: str
) -> None:
    from steamzero.core import fs, transaction

    root, _state, _config = isolated
    unrelated = (
        root
        / "another-profile"
        / ("es_systems.xml" if target == "esde" else "steamzero-manifest-switch.json")
    )
    fs.write_atomic(unrelated, b"before")
    kind = "frontend.esde-systems.sync" if target == "esde" else "frontend.srm-manifests.sync"
    plan = transaction.plan_write_files({unrelated: b"after"}, root=unrelated.parent, kind=kind)
    applied = transaction.apply(plan.plan_id, plan.confirm_token)
    code, result = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            target,
            "--operation-id",
            applied.operation_id,
            "--json",
        ],
    )
    assert code != 0, result
    assert unrelated.read_bytes() == b"after"


def test_esde_rollback_accepts_a_large_valid_foreign_section_preserved_by_the_adapter(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path]
) -> None:
    root, _state, config = isolated
    owned = config / "ES-DE/custom_systems/es_systems.xml"
    owned.parent.mkdir(parents=True)
    original = (
        "<systemList><system><name>foreign</name><label>"
        + "x" * (3 * 1024 * 1024)
        + "</label></system></systemList>"
    ).encode()
    owned.write_bytes(original)
    spec = _spec_path(root, only="esde")
    code, preview = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    plan = preview["data"]["esde"]
    code, applied = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            "esde",
            "--plan-id",
            plan["planId"],
            "--confirm",
            plan["confirmToken"],
            "--json",
        ],
    )
    assert code == 0
    assert b"x" * (3 * 1024 * 1024) in owned.read_bytes()
    code, result = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            "esde",
            "--operation-id",
            applied["data"]["operationId"],
            "--json",
        ],
    )
    assert code == 0, result
    assert owned.read_bytes() == original


def test_frontends_plan_then_apply_then_verify_then_rollback(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path]
) -> None:
    tmp_path, _state, config = isolated
    spec = _spec_path(tmp_path)
    srm_dir = config / "steam-rom-manager" / "userData" / "manifests"
    esde_file = config / "ES-DE" / "custom_systems" / "es_systems.xml"

    code, env = _run(capsys, ["frontends", "status", "--json"])
    assert code == 0
    assert env["module"] == "frontends" and env["action"] == "status"
    assert env["data"]["srm"]["status"] == "missing"
    assert env["data"]["esde"]["status"] == "missing"

    code, env = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    plan = env["data"]
    assert plan["srm"]["actions"] != [] and plan["esde"]["actions"] != []
    srm_plan_id = plan["srm"]["planId"]
    srm_token = plan["srm"]["confirmToken"]
    esde_plan_id = plan["esde"]["planId"]
    esde_token = plan["esde"]["confirmToken"]

    code, env = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            "srm",
            "--plan-id",
            srm_plan_id,
            "--confirm",
            srm_token,
            "--json",
        ],
    )
    assert code == 0
    assert env["data"]["status"] == "ok"
    assert env["data"]["target"] == "srm"
    srm_operation = env["data"]["operationId"]

    code, env = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            "esde",
            "--plan-id",
            esde_plan_id,
            "--confirm",
            esde_token,
            "--json",
        ],
    )
    assert code == 0
    esde_operation = env["data"]["operationId"]

    assert (srm_dir / "steamzero-manifest-switch.json").is_file()
    assert "steamzero-switch" in esde_file.read_text(encoding="utf-8")

    code, env = _run(capsys, ["frontends", "verify", "--spec", str(spec), "--json"])
    assert code == 0
    assert env["data"]["srm"]["converged"] is True
    assert env["data"]["esde"]["converged"] is True

    code, env = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    assert env["data"]["srm"]["actions"] == []
    assert env["data"]["esde"]["actions"] == []

    code, env = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            "srm",
            "--operation-id",
            srm_operation,
            "--json",
        ],
    )
    assert code == 0
    assert env["data"]["status"] == "rolled-back"
    assert not (srm_dir / "steamzero-manifest-switch.json").exists()
    assert "steamzero-switch" in esde_file.read_text(encoding="utf-8")

    code, env = _run(
        capsys,
        [
            "frontends",
            "rollback",
            "--target",
            "esde",
            "--operation-id",
            esde_operation,
            "--json",
        ],
    )
    assert code == 0
    assert env["data"]["status"] == "rolled-back"
    assert not esde_file.exists() or "steamzero-switch" not in esde_file.read_text(encoding="utf-8")


def test_frontends_rejects_bad_spec_and_wrong_confirm(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path]
) -> None:
    tmp_path, _state, _config = isolated

    bad = tmp_path / "bad.json"
    bad.write_text("[not an object]", encoding="utf-8")
    code, env = _run(capsys, ["frontends", "plan", "--spec", str(bad), "--json"])
    assert code != 0
    assert env["status"] == "failed"
    assert env["error"]["code"] == "E-API-SCHEMA"

    spec = _spec_path(tmp_path)
    code, env = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    srm = env["data"]["srm"]
    code, env = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            "srm",
            "--plan-id",
            srm["planId"],
            "--confirm",
            "token-errado",
            "--json",
        ],
    )
    assert code != 0
    assert env["status"] == "blocked"
    assert env["error"]["code"] == "E-TX-CONFIRM-REQUIRED"

    code, env = _run(capsys, ["frontends", "plan", "--json"])
    assert code != 0
    assert env["error"]["code"] == "E-API-SCHEMA"

    code, env = _run(
        capsys,
        [
            "frontends",
            "apply",
            "--target",
            "nintnintw",
            "--plan-id",
            "x",
            "--confirm",
            "y",
            "--json",
        ],
    )
    assert code != 0
    assert env["error"]["code"] == "E-API-SCHEMA"


def test_frontends_status_tracks_managed_after_apply(
    capsys: pytest.CaptureFixture[str], isolated: tuple[Path, Path, Path]
) -> None:
    tmp_path, _state, _config = isolated
    spec = _spec_path(tmp_path)
    code, env = _run(capsys, ["frontends", "plan", "--spec", str(spec), "--json"])
    assert code == 0
    for target, plan in (("srm", env["data"]["srm"]), ("esde", env["data"]["esde"])):
        code, env_apply = _run(
            capsys,
            [
                "frontends",
                "apply",
                "--target",
                target,
                "--plan-id",
                plan["planId"],
                "--confirm",
                plan["confirmToken"],
                "--json",
            ],
        )
        assert code == 0, env_apply

    code, env = _run(capsys, ["frontends", "status", "--json"])
    assert code == 0
    assert env["data"]["srm"]["status"] == "configured"
    assert env["data"]["srm"]["collections"] == ["switch"]
    assert env["data"]["esde"]["status"] == "configured"
    assert env["data"]["esde"]["systems"] == ["steamzero-switch"]

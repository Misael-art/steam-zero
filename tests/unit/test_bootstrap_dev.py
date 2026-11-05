# SPDX-License-Identifier: GPL-3.0-or-later
"""New-host bootstrap preserves existing environments and verifies downloads."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

import bootstrap_dev as bootstrap


def _asset(tmp_path: Path, *, link: bool = False) -> tuple[Path, dict]:
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        entry = tarfile.TarInfo("upstream/bin/uv")
        content = b"#!/bin/sh\nexit 0\n"
        if link:
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/outside/target"
            package.addfile(entry)
        else:
            entry.size = len(content)
            package.addfile(entry, io.BytesIO(content))
    data = archive.read_bytes()
    return archive, {
        "url": "https://github.com/fixture/tool.tar.gz",
        "version": "fixture",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_plan_never_executes_or_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prefix = tmp_path / "managed"
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *a, **k: pytest.fail("execution"))
    result = bootstrap.plan(tmp_path, prefix, "none")
    assert result["mode"] == "plan" and result["systemChanges"] is False
    assert not prefix.exists() and not (tmp_path / ".venv").exists()


@pytest.mark.parametrize("override", [False, True])
def test_standalone_plan_selects_one_workspace_without_creating_it(
    tmp_path: Path, override: bool
) -> None:
    launcher = tmp_path / "bootstrap-dev.sh"
    launcher.write_text((bootstrap.ROOT / "bootstrap-dev.sh").read_text())
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path / "operator")
    environment.pop("STEAMZERO_WORKSPACE", None)
    expected = tmp_path / "operator" / "Projects" / "SteamZero"
    if override:
        expected = tmp_path / "chosen-workspace"
        environment["STEAMZERO_WORKSPACE"] = str(expected)
    result = subprocess.run(
        ["sh", str(launcher), "--plan"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert str(expected) in result.stdout
    assert not expected.exists()
    assert not (tmp_path / "operator").exists()


def test_nonmanaged_directory_and_environment_are_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "valuable"
    marker.write_text("keep")
    with pytest.raises(bootstrap.BootstrapError, match="sem ownership"):
        bootstrap.owned_directory(tmp_path)
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "valuable").write_text("environment")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with pytest.raises(bootstrap.BootstrapError, match="preservada"):
        bootstrap.apply(tmp_path, tmp_path / "managed")
    assert marker.read_text() == "keep"
    assert (venv / "valuable").read_text() == "environment"


def test_locked_download_verified_reused_and_tampering_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, asset = _asset(tmp_path)
    requests = []

    def fetch(url, timeout):
        requests.append(url)
        return io.BytesIO(archive.read_bytes())

    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fetch)
    prefix = tmp_path / "managed"
    bootstrap.owned_directory(prefix)
    binary = bootstrap.install_tool("uv", asset, prefix)
    assert binary.stat().st_mode & 0o777 == 0o700
    assert bootstrap.install_tool("uv", asset, prefix) == binary
    assert len(requests) == 1
    binary.write_text("modified")
    with pytest.raises(bootstrap.BootstrapError, match="divergiu"):
        bootstrap.install_tool("uv", asset, prefix)


def test_bad_hash_never_publishes_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, asset = _asset(tmp_path)
    asset["sha256"] = "0" * 64
    monkeypatch.setattr(
        bootstrap.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(archive.read_bytes())
    )
    prefix = tmp_path / "managed"
    bootstrap.owned_directory(prefix)
    with pytest.raises(bootstrap.BootstrapError, match="Hash"):
        bootstrap.install_tool("uv", asset, prefix)
    assert not (prefix / "tools").exists()
    assert not list(prefix.rglob("*.part"))


@pytest.mark.parametrize("parent_link", [True, False])
def test_links_cannot_redirect_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_link: bool
) -> None:
    archive, asset = _asset(tmp_path, link=not parent_link)
    monkeypatch.setattr(
        bootstrap.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(archive.read_bytes())
    )
    prefix = tmp_path / "managed"
    bootstrap.owned_directory(prefix)
    outside = tmp_path / "outside"
    outside.mkdir()
    if parent_link:
        (prefix / "tools").symlink_to(outside, target_is_directory=True)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.install_tool("uv", asset, prefix)
    assert list(outside.iterdir()) == []


def test_source_commands_support_paths_with_spaces(tmp_path: Path) -> None:
    root = tmp_path / "Project with spaces"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project.scripts]\nsteamzero="steamzero.cli.main:main"\n')
    prefix = root / ".steamzero-dev"
    bootstrap.owned_directory(prefix)
    env = bootstrap.environment(root, prefix, [])
    bootstrap.write_development_commands(root, prefix, env)
    wrapper = prefix / "bin/steamzero"
    assert subprocess.run(["sh", "-n", str(wrapper)], check=False).returncode == 0
    assert '"$@"' in wrapper.read_text()
    assert env["STEAMZERO_NO_DAEMON"] == "1"
    assert "PYTEST_DEBUG_TEMPROOT" not in env
    assert env["XDG_STATE_HOME"] == str(prefix / "profile/state")
    assert not (tmp_path / ".bashrc").exists()


def test_environment_symlink_is_preserved(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project.scripts]\n")
    prefix = tmp_path / "managed"
    bootstrap.owned_directory(prefix)
    outside = tmp_path / "outside"
    outside.write_text("keep")
    (prefix / "env.sh").symlink_to(outside)
    with pytest.raises(bootstrap.BootstrapError, match="Symlink"):
        bootstrap.write_development_commands(
            tmp_path, prefix, bootstrap.environment(tmp_path, prefix, [])
        )
    assert outside.read_text() == "keep"


def test_bootstrap_lock_pins_public_archives() -> None:
    data = json.loads((bootstrap.ROOT / "tools/dev-bootstrap.lock.json").read_text())
    assert data["python"] == "3.14.7"
    for asset in data["tools"].values():
        assert "/releases/download/" in asset["url"] and "/latest/" not in asset["url"]
        assert len(asset["sha256"]) == 64 and asset["bytes"] > 0

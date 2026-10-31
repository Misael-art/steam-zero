# SPDX-License-Identifier: GPL-3.0-or-later
"""Reconstruct an isolated development environment; never install a host release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OWNER = "SteamZero-Dev-Managed: 1\n"
MARKER = ".steamzero-dev-owner"


class BootstrapError(Exception):
    """A recoverable prerequisite or ownership failure."""


def reject_symlinks(path: Path, prefix: Path) -> None:
    relative = path.relative_to(prefix)
    current = prefix
    for part in ("", *relative.parts):
        current = current / part
        if current.is_symlink():
            raise BootstrapError(f"Symlink em caminho gerenciado; preservado: {current}")


def owned_directory(path: Path) -> None:
    if path.is_symlink():
        raise BootstrapError(f"Diretório gerenciado não pode ser symlink: {path}")
    marker = path / MARKER
    if (
        path.exists()
        and any(path.iterdir())
        and (marker.is_symlink() or not marker.is_file() or marker.read_text() != OWNER)
    ):
        raise BootstrapError(f"Diretório existente sem ownership; preservado: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.write_text(OWNER)


def install_tool(name: str, asset: dict[str, Any], prefix: Path) -> Path:
    """Verify the locked archive before writing a single regular executable."""
    destination = prefix / "tools" / name / str(asset["version"]) / name
    reject_symlinks(destination, prefix)
    if destination.is_symlink():
        raise BootstrapError(f"Executável gerenciado é symlink: {destination}")
    receipt = destination.with_suffix(".json")
    reject_symlinks(receipt, prefix)
    if destination.is_file() and receipt.is_file() and not receipt.is_symlink():
        recorded = json.loads(receipt.read_text())
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if recorded == {"archiveSha256": asset["sha256"], "binarySha256": digest}:
            return destination
        raise BootstrapError(f"Executável gerenciado divergiu; preservado: {destination}")
    if destination.exists():
        raise BootstrapError(f"Executável sem recibo; preservado: {destination}")
    if receipt.exists():
        raise BootstrapError(f"Recibo sem executável; preservado: {receipt}")
    url = str(asset["url"])
    if not url.startswith("https://github.com/"):
        raise BootstrapError("Download exige HTTPS do upstream fixado no lock")
    downloads = prefix / "downloads"
    reject_symlinks(downloads, prefix)
    downloads.mkdir(exist_ok=True)
    archive = downloads / f"{name}-{asset['version']}.tar.gz"
    if archive.is_symlink():
        raise BootstrapError("Cache de download não pode ser symlink")
    if not archive.exists():
        temporary = archive.with_suffix(".part")
        if temporary.exists() or temporary.is_symlink():
            raise BootstrapError(f"Download anterior pendente; inspecione: {temporary}")
        try:
            total = 0
            with (
                urllib.request.urlopen(url, timeout=30) as source,  # noqa: S310 - locked HTTPS
                temporary.open("xb") as target,
            ):
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    if total > int(asset["bytes"]):
                        raise BootstrapError("Download excede o tamanho declarado")
                    target.write(chunk)
            if total != int(asset["bytes"]):
                raise BootstrapError("Download incompleto")
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != asset["sha256"]:
                raise BootstrapError("Hash do download divergiu")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != asset["sha256"]:
        raise BootstrapError("Hash do cache divergiu; nada foi executado")
    with tarfile.open(archive, "r:gz") as package:
        candidates = [entry for entry in package.getmembers() if Path(entry.name).name == name]
        if len(candidates) != 1 or not candidates[0].isreg():
            raise BootstrapError("Archive não contém um executável regular inequívoco")
        member = candidates[0]
        if member.size > 200 * 1024 * 1024:
            raise BootstrapError("Executável excede o orçamento")
        stream = package.extractfile(member)
        if stream is None:
            raise BootstrapError("Executável ausente")
        binary = stream.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary)
    destination.chmod(0o700)
    receipt.write_text(
        json.dumps(
            {"archiveSha256": asset["sha256"], "binarySha256": hashlib.sha256(binary).hexdigest()}
        )
        + "\n"
    )
    return destination


def environment(root: Path, prefix: Path, tool_dirs: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTEST_DEBUG_TEMPROOT", None)
    env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in ("src", "tools", "tests"))
    env["PATH"] = os.pathsep.join(
        [str(prefix / "bin"), str(root / ".venv/bin"), *map(str, tool_dirs), env.get("PATH", "")]
    )
    for name in ("DATA", "STATE", "CONFIG", "CACHE", "RUNTIME"):
        key = f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"
        env[key] = str(prefix / "profile" / name.lower())
    env["STEAMZERO_NO_DAEMON"] = "1"
    env["UV_CACHE_DIR"] = str(prefix / "cache/uv")
    env["UV_PYTHON_INSTALL_DIR"] = str(prefix / "python")
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = "2"
    return env


def write_development_commands(root: Path, prefix: Path, env: dict[str, str]) -> None:
    """Generate only the entry points declared by this checkout, without a wheel."""
    scripts = tomllib.loads((root / "pyproject.toml").read_text())["project"]["scripts"]
    bin_dir = prefix / "bin"
    reject_symlinks(bin_dir, prefix)
    bin_dir.mkdir(exist_ok=True)
    for name, target in scripts.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name) or not re.fullmatch(
            r"steamzero(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+:[a-zA-Z_][a-zA-Z0-9_]*", target
        ):
            raise BootstrapError("Entry point inesperado no pyproject")
        module, function = target.split(":")
        code = f"from {module} import {function}; raise SystemExit({function}())"
        path = bin_dir / name
        if path.is_symlink():
            raise BootstrapError("Wrapper de desenvolvimento não pode ser symlink")
        path.write_text(
            "#!/bin/sh\n"
            + f"PYTHONPATH={shlex.quote(env['PYTHONPATH'])} exec "
            + shlex.quote(str(root / ".venv/bin/python"))
            + " -c "
            + shlex.quote(code)
            + ' "$@"\n'
        )
        path.chmod(0o700)
    keys = ["PYTHONPATH", "STEAMZERO_NO_DAEMON", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR"]
    keys += [k for k in env if k.startswith("XDG_") and str(prefix / "profile") in env[k]]
    lines = ["# SteamZero development shell; no system profile is modified."]
    lines.extend(f"export {key}={shlex.quote(env[key])}" for key in keys)
    # Preserve the shell's current PATH, not the PATH captured on another host.
    managed_path = env["PATH"].removesuffix(os.environ.get("PATH", "")).rstrip(os.pathsep)
    lines.append(f'export PATH={shlex.quote(managed_path)}:"$PATH"')
    reject_symlinks(prefix / "env.sh", prefix)
    (prefix / "env.sh").write_text("\n".join(lines) + "\n")


def run(args: list[str], root: Path, env: dict[str, str], log: Path) -> None:
    with log.open("a") as output:
        output.write("\n$ " + shlex.join(args) + "\n")
        output.flush()
        result = subprocess.run(args, cwd=root, env=env, stdout=output, stderr=output, check=False)
    if result.returncode:
        raise BootstrapError(f"Comando saiu {result.returncode}; diagnóstico em {log}")


def plan(root: Path, prefix: Path, test_mode: str) -> dict[str, Any]:
    return {
        "mode": "plan",
        "workspace": str(root),
        "managedPrefix": str(prefix),
        "venvExists": (root / ".venv").exists(),
        "platform": f"{platform.system().lower()}-{platform.machine()}",
        "freeDiskGiB": round(shutil.disk_usage(root).free / 2**30, 1),
        "tools": {name: shutil.which(name) for name in ("git", "make", "uv", "rtk", "gh")},
        "tests": test_mode,
        "systemChanges": False,
        "hostReleaseInstallation": False,
        "credentialsCopied": False,
        "visualAuthority": "ci/qml-visual/environment.lock.json and matching CI image",
    }


def apply(
    root: Path, prefix: Path, *, check: bool = False, test_mode: str = "none"
) -> dict[str, Any]:
    if os.geteuid() == 0:
        raise BootstrapError("Execute o bootstrap de desenvolvimento como usuário comum")
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise BootstrapError("Lock atual cobre Linux x86_64; outra plataforma exige lock próprio")
    if not shutil.which("git") or not shutil.which("make"):
        raise BootstrapError("git/make ausentes; consulte bootstrap-dev.sh --system-plan")
    if shutil.disk_usage(root).free < 4 * 2**30:
        raise BootstrapError("Menos de 4 GiB livres; bootstrap não iniciado")
    venv = root / ".venv"
    if venv.is_symlink():
        raise BootstrapError(".venv é symlink; preservada")
    if venv.exists() and (
        venv.is_symlink()
        or (venv / MARKER).is_symlink()
        or not (venv / MARKER).is_file()
        or (venv / MARKER).read_text() != OWNER
    ):
        raise BootstrapError(".venv existente não gerenciada foi preservada; não será recriada")
    owned_directory(prefix)
    lock = json.loads((root / "tools/dev-bootstrap.lock.json").read_text())
    for name in ("tools", "downloads", "bin", "profile", "cache", "python"):
        reject_symlinks(prefix / name, prefix)
    python_stamp = venv / ".steamzero-python-version"
    if venv.exists() and (
        python_stamp.is_symlink()
        or not python_stamp.is_file()
        or python_stamp.read_text().strip() != lock["python"]
    ):
        raise BootstrapError("Versão do ambiente existente diverge do lock; ambiente preservado")
    tools = {}
    for name, asset in lock["tools"].items():
        # Existing tools stay untouched; downloaded tools are always hash-pinned.
        tools[name] = Path(shutil.which(name) or install_tool(name, asset, prefix))
    env = environment(root, prefix, [p.parent for p in tools.values()])
    for key in (
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        reject_symlinks(Path(env[key]), prefix)
        Path(env[key]).mkdir(parents=True, exist_ok=True, mode=0o700)
    log_root = root / "build/agent-runs"
    log_root.mkdir(parents=True, exist_ok=True)
    logs = Path(tempfile.mkdtemp(prefix="bootstrap-", dir=log_root))
    log = logs / "bootstrap.log"
    run(
        [str(tools["rtk"]), "proxy", str(sys.executable), "-c", "print('rtk-proxy-ok')"],
        root,
        env,
        log,
    )
    uv = str(tools["uv"])
    if not venv.exists():
        run([uv, "python", "install", lock["python"]], root, env, log)
        run([uv, "venv", "--python", lock["python"], str(venv)], root, env, log)
        (venv / MARKER).write_text(OWNER)
        python_stamp.write_text(lock["python"] + "\n")
    stamp = venv / ".steamzero-requirements-sha256"
    if stamp.is_symlink():
        raise BootstrapError("Stamp do ambiente é symlink; preservado")
    requirements = hashlib.sha256((root / "requirements-dev.lock").read_bytes()).hexdigest()
    if not stamp.is_file() or stamp.read_text().strip() != requirements:
        run(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(venv / "bin/python"),
                "--require-hashes",
                "-r",
                str(root / "requirements-dev.lock"),
            ],
            root,
            env,
            log,
        )
        stamp.write_text(requirements + "\n")
    run([uv, "pip", "check", "--python", str(venv / "bin/python")], root, env, log)
    write_development_commands(root, prefix, env)
    run(
        [str(venv / "bin/python"), "-c", "import steamzero; print(steamzero.__version__)"],
        root,
        env,
        log,
    )
    if check:
        run(
            [
                "make",
                "lint",
                "format-check",
                "typecheck",
                "independence",
                "boundaries",
                "component-lock",
                "capability-matrix",
                "status-check",
            ],
            root,
            env,
            log,
        )
    if test_mode != "none":
        meminfo = Path("/proc/meminfo").read_text()
        match = re.search(r"^MemAvailable:\s+(\d+)", meminfo, re.MULTILINE)
        if match is None or int(match[1]) < 3 * 1024**2 or shutil.disk_usage(root).free < 8 * 2**30:
            raise BootstrapError("Testes exigem 3 GiB disponíveis e 8 GiB livres; nada iniciado")
        args = [str(venv / "bin/python"), "tools/run_tests_isolated.py", "tests", "-q"]
        if test_mode == "core":
            args += ["-m", "not visual"]
        env["COVERAGE_FILE"] = str(logs / ".coverage")
        args += ["--cov=steamzero", f"--cov-report=json:{logs / 'coverage.json'}"]
        run(args, root, env, logs / "tests.log")
    result = plan(root, prefix, test_mode)
    result.update(
        mode="applied",
        requirementsSha256=requirements,
        log=str(log),
        tools={k: str(v) for k, v in tools.items()},
    )
    (logs / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--test", choices=("none", "core", "full"), default="none")
    parser.add_argument(
        "--ui", action="store_true", help="native Arch prerequisites handled by shell"
    )
    parser.add_argument(
        "--system-packages", action="store_true", help="handled only by shell launcher"
    )
    args = parser.parse_args(argv)
    prefix = ROOT / ".steamzero-dev"
    try:
        result = (
            apply(ROOT, prefix, check=args.check, test_mode=args.test)
            if args.apply
            else plan(ROOT, prefix, args.test)
        )
    except (BootstrapError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

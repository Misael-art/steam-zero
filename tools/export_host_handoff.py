# SPDX-License-Identifier: GPL-3.0-or-later
"""Export private application data; verify and restore only into an empty staging directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Any

OWNER = "SteamZero-Private-Handoff: 1\n"


class HandoffError(Exception):
    """Preserve the source and report an incomplete export or restore."""


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def sqlite_snapshot(source: Path, target: Path) -> None:
    started = time.monotonic()

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() - started > 90:
            raise HandoffError("Snapshot SQLite excedeu o prazo; origem preservada")

    with (
        closing(
            sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        ) as src,
        closing(sqlite3.connect(target)) as dst,
    ):
        src.backup(dst, pages=256, progress=progress, sleep=0.01)
        if dst.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise HandoffError("Snapshot SQLite não passou em integrity_check")


def export(output: Path, sources: dict[str, Path]) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise HandoffError("Destino deve ser novo; nenhum backup existente é sobrescrito")
    existing = {name: path for name, path in sources.items() if path.exists()}
    for name, root in existing.items():
        if (
            name not in {"data", "state", "config", "continuity", "saves", "bios"}
            or root.is_symlink()
            or not root.is_dir()
        ):
            raise HandoffError("Fonte inválida ou symlink; revisar inventário")
        if output.resolve().is_relative_to(root.resolve()):
            raise HandoffError("Backup não pode ser criado dentro da própria origem")
    output.mkdir(parents=True, mode=0o700)
    (output / "OWNER").write_text(OWNER)
    archive = output / "steamzero-private.tar.gz"
    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    try:
        with (
            tempfile.TemporaryDirectory(prefix="snapshot-", dir=output) as scratch,
            tarfile.open(archive, "w:gz", compresslevel=1) as package,
        ):
            for name, root in existing.items():
                for path in sorted(root.rglob("*")):
                    relative = PurePosixPath(name, path.relative_to(root).as_posix())
                    if path.is_symlink():
                        skipped.append(str(relative))
                        continue
                    if not path.is_file() or path.name.endswith(("-wal", "-shm")):
                        continue
                    source = path
                    database = path.suffix in {".db", ".sqlite", ".sqlite3"}
                    if database:
                        source = Path(scratch) / f"{len(records)}.db"
                        sqlite_snapshot(path, source)
                    before = source.stat()
                    checksum = digest(source)
                    info = tarfile.TarInfo(str(relative))
                    info.size = before.st_size
                    info.mode = 0o600
                    with source.open("rb") as content:
                        package.addfile(info, content)
                    after = source.stat()
                    if (before.st_size, before.st_mtime_ns) != (
                        after.st_size,
                        after.st_mtime_ns,
                    ):
                        raise HandoffError("Arquivo mudou durante a cópia; exportação não aprovada")
                    records.append(
                        {
                            "path": str(relative),
                            "bytes": info.size,
                            "sha256": checksum,
                            "sqliteSnapshot": database,
                        }
                    )
        archive.chmod(0o600)
        manifest = {
            "schemaVersion": 1,
            "archive": archive.name,
            "archiveSha256": digest(archive),
            "archiveBytes": archive.stat().st_size,
            "files": records,
            "skippedSymlinks": skipped,
            "externallyStored": False,
            "excluded": [
                "ROMs not explicitly selected",
                "cache",
                ".venv",
                "/opt",
                "SSH/GPG keys",
                "Codex login tokens",
            ],
        }
        manifest_path = output / "PRIVATE-MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        manifest_path.chmod(0o600)
        summary = {
            "schemaVersion": 1,
            "archive": archive.name,
            "archiveSha256": manifest["archiveSha256"],
            "archiveBytes": manifest["archiveBytes"],
            "fileCount": len(records),
            "sqliteSnapshots": sum(record["sqliteSnapshot"] for record in records),
            "externallyStored": False,
            "restoreTested": False,
        }
        (output / "PUBLIC-SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException:
        # Keep an explicit failure marker; never publish a partial archive as verified.
        (output / "INCOMPLETE").write_text("Exportação incompleta; origem não foi alterada.\n")
        if archive.exists():
            archive.chmod(0o600)
        raise


def verify(directory: Path) -> dict[str, Any]:
    if (directory / "INCOMPLETE").exists():
        raise HandoffError("Exportação incompleta")
    manifest_path = directory / "PRIVATE-MANIFEST.json"
    if manifest_path.is_symlink():
        raise HandoffError("Manifesto não pode ser symlink")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schemaVersion") != 1 or manifest.get("archive") != "steamzero-private.tar.gz":
        raise HandoffError("Manifesto não reconhecido")
    archive = directory / manifest["archive"]
    if archive.is_symlink() or digest(archive) != manifest["archiveSha256"]:
        raise HandoffError("Hash do archive divergiu")
    expected = {record["path"]: record for record in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise HandoffError("Manifesto contém paths duplicados")
    seen: set[str] = set()
    with tarfile.open(archive, "r:gz") as package:
        for member in package:
            path = PurePosixPath(member.name)
            if (
                not member.isreg()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
            ):
                raise HandoffError("Archive contém path ou tipo não permitido")
            if member.name in seen or member.name not in expected:
                raise HandoffError("Entrada duplicada ou fora do manifesto")
            seen.add(member.name)
            record = expected[member.name]
            if member.size != record["bytes"]:
                raise HandoffError("Tamanho de entrada divergiu")
            content = package.extractfile(member)
            if content is None:
                raise HandoffError("Conteúdo ausente")
            checksum = hashlib.sha256()
            while chunk := content.read(1024 * 1024):
                checksum.update(chunk)
            if checksum.hexdigest() != record["sha256"]:
                raise HandoffError("Hash de entrada divergiu")
    if seen != set(expected):
        raise HandoffError("Entradas faltantes")
    return {
        "ok": True,
        "fileCount": len(seen),
        "archiveSha256": manifest["archiveSha256"],
        "externallyStored": False,
    }


def restore(directory: Path, destination: Path) -> dict[str, Any]:
    result = verify(directory)
    if destination.is_symlink() or destination.exists():
        raise HandoffError("Restaurar somente em diretório novo, nunca sobre os dados do usuário")
    destination.mkdir(parents=True, mode=0o700)
    archive = directory / "steamzero-private.tar.gz"
    with tarfile.open(archive, "r:gz") as package:
        for member in package:
            member_path = PurePosixPath(member.name)
            if (
                not member.isreg()
                or member_path.is_absolute()
                or ".." in member_path.parts
                or "\\" in member.name
            ):
                raise HandoffError("Archive mudou ou contém path não permitido")
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            content = package.extractfile(member)
            if content is None:
                raise HandoffError("Conteúdo ausente na restauração")
            with target.open("xb") as output:
                shutil.copyfileobj(content, output)
            target.chmod(0o600)
    (destination / "RESTORED-FROM.json").write_text(json.dumps(result, indent=2) + "\n")
    return {**result, "restoreTested": True, "destination": str(destination)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "verify", "restore"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "export":
            home = Path.home()
            sources = {
                "data": Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "steamzero",
                "state": Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
                / "steamzero",
                "config": Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "steamzero",
                "continuity": home / "steamzero-continuidade-2026-10-21",
            }
            result = export(args.directory, sources)
        elif args.action == "verify":
            result = verify(args.directory)
        else:
            if args.destination is None:
                raise HandoffError("--destination é obrigatório para restore")
            result = restore(args.directory, args.destination)
    except (HandoffError, OSError, ValueError, sqlite3.Error, tarfile.TarError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

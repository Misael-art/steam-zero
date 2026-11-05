# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Aquisição e instalação transacional de temas ES-DE."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from steamzero.core.errors import SteamZeroError
from steamzero.domain.theme_acquire import (
    AcquisitionReport,
    ThemeTransaction,
    acquire_and_install,
    build_manifest,
    ingest_archive,
)
from steamzero.domain.theme_assets import ThemeAssetStore, live_digests, load_installed_manifests
from steamzero.domain.theme_sources import ThemeSource

_COMMIT = "a" * 40


def _source(theme_id: str = "org.esde.demo", name: str = "Demo") -> ThemeSource:
    return ThemeSource(
        id=theme_id,
        name=name,
        family="esde",
        author="Autora",
        credits=("Autora", "Autor Original"),
        license_id="CC-BY-NC-SA-4.0",
        license_source="README.md",
        homepage="https://exemplo.invalido",
        forge="github",
        repo="dono/repositorio",
        commit=_COMMIT,
    )


def _tarball(path: Path, files: dict[str, bytes], *, root: str = "repositorio-aaaa") -> Path:
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


@pytest.fixture
def store(tmp_path: Path) -> ThemeAssetStore:
    return ThemeAssetStore(tmp_path / "assets")


@pytest.fixture
def themes(tmp_path: Path) -> Path:
    root = tmp_path / "themes"
    root.mkdir()
    return root


def test_ingestion_streams_members_into_the_store(store: ThemeAssetStore, tmp_path: Path) -> None:
    archive = _tarball(
        tmp_path / "t.tar.gz",
        {"theme.xml": b"<theme/>", "art/logo.png": b"conteudo-png"},
    )

    report = ingest_archive(archive, _source(), store)

    # O prefixo `<repo>-<commit>/` some: senão o mesmo arquivo em duas versoes
    # do tema pareceria dois arquivos e a deduplicacao nao aconteceria.
    assert set(report.assets) == {"theme.xml", "art/logo.png"}
    assert report.files == 2
    assert store.usage()["blobs"] == 2


def test_second_theme_with_identical_art_pays_only_for_what_is_new(
    store: ThemeAssetStore, tmp_path: Path
) -> None:
    """A economia prometida, medida: o comum entra uma vez só."""
    shared = b"icone identico nos dois temas" * 64
    # Conteudo PROPRIO de cada tema precisa diferir, senao o store unifica os
    # dois — corretamente — e o teste deixaria de distinguir o compartilhado do
    # exclusivo, que e justamente o que ele existe para medir.
    first = _tarball(tmp_path / "a.tar.gz", {"shared.png": shared, "a.xml": b"<theme>a</theme>"})
    second = _tarball(tmp_path / "b.tar.gz", {"shared.png": shared, "b.xml": b"<theme>bb</theme>"})

    report_a = ingest_archive(first, _source("org.esde.a"), store)
    report_b = ingest_archive(second, _source("org.esde.b"), store)

    assert report_a.bytes_shared_with_installed == 0
    assert report_a.bytes_ingested == len(shared) + len(b"<theme>a</theme>")
    # O segundo tema paga so pelo que e dele, e o reaproveitado e contado na
    # coluna de COMPARTILHAMENTO, nao na de repeticao interna.
    assert report_b.bytes_shared_with_installed == len(shared)
    assert report_b.bytes_repeated_in_package == 0
    assert report_b.bytes_ingested == len(b"<theme>bb</theme>")
    # Tres blobs, nao quatro: o compartilhado tem um so.
    assert store.usage()["blobs"] == 3


def test_content_outside_the_trust_boundary_is_skipped_not_installed(
    store: ThemeAssetStore, tmp_path: Path
) -> None:
    """AGENTS §10: tema de terceiro não traz binário, script nem biblioteca."""
    archive = _tarball(
        tmp_path / "t.tar.gz",
        {"theme.xml": b"<theme/>", "payload.so": b"\x7fELF", "run.sh": b"#!/bin/sh"},
    )

    report = ingest_archive(archive, _source(), store)

    assert set(report.assets) == {"theme.xml"}
    assert store.usage()["blobs"] == 1


def test_symlink_member_is_fatal(store: ThemeAssetStore, tmp_path: Path) -> None:
    """Link é recusado pelo cabeçalho, antes de qualquer leitura."""
    path = tmp_path / "hostil.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("repo-aaaa/atalho.png")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/shadow"
        archive.addfile(info)

    with pytest.raises(SteamZeroError) as excinfo:
        list(ingest_archive(path, _source(), store))
    assert excinfo.value.code == "E-CONTENT-UNSAFE-PATH"


def test_path_traversal_member_is_fatal(store: ThemeAssetStore, tmp_path: Path) -> None:
    archive = _tarball(tmp_path / "t.tar.gz", {"../../../etc/passwd.png": b"x"})

    with pytest.raises(SteamZeroError):
        ingest_archive(archive, _source(), store)


def test_archive_without_usable_content_fails_closed(
    store: ThemeAssetStore, tmp_path: Path
) -> None:
    """Instalar um tema vazio seria pior que falhar: o usuário veria um tema
    que existe e não desenha nada."""
    archive = _tarball(tmp_path / "t.tar.gz", {"run.sh": b"#!/bin/sh"})

    with pytest.raises(SteamZeroError) as excinfo:
        ingest_archive(archive, _source(), store)
    assert excinfo.value.code == "E-CONTENT-INCOMPLETE"


def test_manifest_carries_the_attribution_chain() -> None:
    """CC-BY-NC-SA exige atribuição, e três dos cinco temas são derivados."""
    report = AcquisitionReport(theme_id="org.esde.demo", assets={"a.png": "b" * 64})

    manifest = build_manifest(_source(), report)

    assert manifest["credits"] == ["Autora", "Autor Original"]
    assert manifest["license"] == "CC-BY-NC-SA-4.0"
    assert manifest["origin"]["commit"] == _COMMIT
    assert manifest["version"] == _COMMIT[:12]


def test_install_refuses_a_manifest_pointing_at_missing_blobs(
    store: ThemeAssetStore, themes: Path
) -> None:
    """Senão o tema instalaria quebrado e o defeito só apareceria ao renderizar."""
    report = AcquisitionReport(theme_id="org.esde.demo", assets={"a.png": "c" * 64})

    with pytest.raises(SteamZeroError) as excinfo:
        ThemeTransaction(themes, store).install(_source(), report)
    assert excinfo.value.code == "E-CONTENT-INCOMPLETE"


def test_install_is_refused_when_already_present_unless_forced(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    archive = _tarball(tmp_path / "t.tar.gz", {"theme.xml": b"<theme/>"})
    report = ingest_archive(archive, _source(), store)
    transaction = ThemeTransaction(themes, store)
    transaction.install(_source(), report)

    with pytest.raises(SteamZeroError):
        transaction.install(_source(), report)

    replaced = transaction.install(_source(), report, force=True)
    assert replaced["replaced"] is True


def test_rollback_restores_the_previous_manifest_and_keeps_every_blob(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """O requisito do operador: rollback completo SEM quebrar asset compartilhado."""
    shared = b"asset que os dois temas usam" * 32
    vizinho = _tarball(tmp_path / "v.tar.gz", {"shared.png": shared, "v.xml": b"<theme/>"})
    antigo = _tarball(tmp_path / "1.tar.gz", {"shared.png": shared, "a.xml": b"<theme>v1</theme>"})
    novo = _tarball(tmp_path / "2.tar.gz", {"shared.png": shared, "b.xml": b"<theme>v2</theme>"})

    transaction = ThemeTransaction(themes, store)
    transaction.install(
        _source("org.esde.vizinho"), ingest_archive(vizinho, _source("org.esde.vizinho"), store)
    )
    transaction.install(_source(), ingest_archive(antigo, _source(), store))
    before = (themes / "org.esde.demo" / "theme.json").read_bytes()

    upgraded = transaction.install(_source(), ingest_archive(novo, _source(), store), force=True)
    assert (themes / "org.esde.demo" / "theme.json").read_bytes() != before

    undone = transaction.rollback("org.esde.demo", upgraded["operationId"])

    assert undone["restoredPrevious"] is True
    assert (themes / "org.esde.demo" / "theme.json").read_bytes() == before
    # O vizinho continua íntegro, e o blob compartilhado nunca saiu.
    live = live_digests(load_installed_manifests(themes))
    assert store.verify(live)["ok"] is True


def test_rollback_of_a_first_install_removes_the_theme(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    archive = _tarball(tmp_path / "t.tar.gz", {"theme.xml": b"<theme/>"})
    transaction = ThemeTransaction(themes, store)
    installed = transaction.install(_source(), ingest_archive(archive, _source(), store))

    undone = transaction.rollback("org.esde.demo", installed["operationId"])

    assert undone["restoredPrevious"] is False
    assert not (themes / "org.esde.demo" / "theme.json").exists()
    assert undone["assetsPreserved"] is True


@pytest.mark.parametrize("operation_kind", ["unknown", "other-theme"])
def test_install_rollback_refuses_unknown_or_foreign_operation_without_mutation(
    store: ThemeAssetStore, themes: Path, tmp_path: Path, operation_kind: str
) -> None:
    from steamzero.core import ids

    archive = _tarball(tmp_path / "owned.tar.gz", {"theme.xml": b"<theme/>"})
    transaction = ThemeTransaction(themes, store)
    transaction.install(_source(), ingest_archive(archive, _source(), store))
    operation_id = ids.new_ulid()
    if operation_kind == "other-theme":
        other = _source("org.esde.other")
        operation_id = transaction.install(other, ingest_archive(archive, other, store))[
            "operationId"
        ]
    before = {path: path.read_bytes() for path in themes.glob("*/theme.json")}
    blobs = {digest: store.read(digest) for digest, _ in store.iter_blobs()}
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        transaction.rollback(_source().id, operation_id)
    assert {path: path.read_bytes() for path in themes.glob("*/theme.json")} == before
    assert {digest: store.read(digest) for digest, _ in store.iter_blobs()} == blobs


def test_install_rollback_refuses_a_version_superseded_by_another_install(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    from steamzero.core import paths

    old = _tarball(tmp_path / "old.tar.gz", {"theme.xml": b"<theme>old</theme>"})
    new = _tarball(tmp_path / "new.tar.gz", {"theme.xml": b"<theme>new</theme>"})
    transaction = ThemeTransaction(themes, store)
    first = transaction.install(_source(), ingest_archive(old, _source(), store))
    replacement = transaction.install(_source(), ingest_archive(new, _source(), store), force=True)
    manifest = themes / _source().id / "theme.json"
    undo = paths.staging_for(replacement["operationId"]) / "previous-theme.json"
    before, previous = manifest.read_bytes(), undo.read_bytes()
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        transaction.rollback(_source().id, first["operationId"])
    assert manifest.read_bytes() == before
    assert undo.read_bytes() == previous
    assert store.verify(live_digests([json.loads(before), json.loads(previous)]))["ok"]


def test_repeated_replacement_rollback_preserves_the_restored_theme_and_result(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    old = _tarball(tmp_path / "old.tar.gz", {"theme.xml": b"<theme>old</theme>"})
    new = _tarball(tmp_path / "new.tar.gz", {"theme.xml": b"<theme>new</theme>"})
    transaction = ThemeTransaction(themes, store)
    transaction.install(_source(), ingest_archive(old, _source(), store))
    manifest = themes / _source().id / "theme.json"
    before = manifest.read_bytes()
    replacement = transaction.install(_source(), ingest_archive(new, _source(), store), force=True)
    first = transaction.rollback(_source().id, replacement["operationId"])
    assert first["restoredPrevious"] is True
    assert manifest.read_bytes() == before
    second = transaction.rollback(_source().id, replacement["operationId"])
    assert second == first
    assert manifest.read_bytes() == before
    assert store.verify(live_digests([json.loads(before)]))["ok"]


def test_unproven_legacy_snapshot_is_preserved_without_replacing_the_current_theme(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    from steamzero.core import ids, paths

    archive = _tarball(tmp_path / "current.tar.gz", {"theme.xml": b"<theme>current</theme>"})
    publisher = ThemeTransaction(themes, store)
    publisher.install(_source(), ingest_archive(archive, _source(), store))
    manifest = themes / _source().id / "theme.json"
    current = manifest.read_bytes()
    operation_id = ids.new_ulid()
    directory = paths.staging_for(operation_id)
    directory.mkdir(parents=True)
    snapshot = directory / "previous-theme.json"
    legacy = b'{"assets": {}, "id": "org.esde.unknown"}'
    snapshot.write_bytes(legacy)
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        publisher.rollback(_source().id, operation_id)
    assert manifest.read_bytes() == current
    assert snapshot.read_bytes() == legacy
    assert not paths.journal_path(operation_id).exists()


@pytest.mark.parametrize("action", ["install", "uninstall", "rollback"])
def test_theme_directory_alias_cannot_change_another_theme_or_bypass_its_consumer(
    store: ThemeAssetStore, themes: Path, action: str
) -> None:
    from steamzero.core import paths

    source = _source("org.esde.actual")
    asset = store.put("theme.xml", b"<theme/>")
    report = AcquisitionReport(theme_id=source.id, assets={"theme.xml": asset.digest})
    guarded: list[str] = []
    active = True

    def consumer(theme_id: str) -> None:
        guarded.append(theme_id)
        if active and theme_id == source.id:
            raise SteamZeroError("E-THEME-ACTIVE", detail="owned active consumer")

    publisher = ThemeTransaction(themes, store, removal_guard=consumer)
    installed = publisher.install(source, report)
    manifest = themes / source.id / "theme.json"
    original = manifest.read_bytes()
    operation_id = installed["operationId"]
    journal = paths.journal_path(operation_id).read_bytes()
    alias = themes / "org.esde.alias"
    alias.symlink_to(manifest.parent, target_is_directory=True)
    with pytest.raises(SteamZeroError, match="E-THEME-UNSAFE"):
        if action == "install":
            publisher.install(
                _source(alias.name),
                AcquisitionReport(theme_id=alias.name, assets=report.assets),
                force=True,
            )
        elif action == "uninstall":
            publisher.uninstall(alias.name)
        else:
            publisher.rollback(alias.name, operation_id)
    assert guarded == []
    assert alias.is_symlink()
    assert manifest.read_bytes() == original
    assert paths.journal_path(operation_id).read_bytes() == journal
    assert store.verify([asset.digest])["ok"]
    alias.unlink()
    if action == "install":
        own = publisher.install(
            _source(alias.name), AcquisitionReport(theme_id=alias.name, assets=report.assets)
        )
        assert manifest.read_bytes() == original
        assert not publisher.rollback(alias.name, own["operationId"])["restoredPrevious"]
        assert manifest.read_bytes() == original
    else:
        with pytest.raises(SteamZeroError, match="E-THEME-ACTIVE"):
            if action == "uninstall":
                publisher.uninstall(source.id)
            else:
                publisher.rollback(source.id, operation_id)
        assert manifest.read_bytes() == original
        active = False
        if action == "uninstall":
            assert publisher.uninstall(source.id)["removed"]
        else:
            assert not publisher.rollback(source.id, operation_id)["restoredPrevious"]
        assert not manifest.exists()
    assert store.verify([asset.digest])["ok"]


@pytest.mark.parametrize("failure", ["compatibility-copy", "state-recorder"])
def test_failed_recovery_mirror_restores_the_previous_theme_and_allows_retry(
    store: ThemeAssetStore,
    themes: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from steamzero.core import fs, journal, paths

    source = _source()
    old = ingest_archive(_tarball(tmp_path / "old.tar.gz", {"old.xml": b"<old/>"}), source, store)
    new = ingest_archive(_tarball(tmp_path / "new.tar.gz", {"new.xml": b"<new/>"}), source, store)
    publisher = ThemeTransaction(themes, store)
    publisher.install(source, old)
    manifest = themes / source.id / "theme.json"
    previous = manifest.read_bytes()
    before = set(paths.journal_dir().glob("*.jsonl"))
    stage_bytes = fs.stage_bytes

    def fail_copy(operation_id: str, name: str, payload: bytes) -> Path:
        if name == "previous-theme.json":
            raise OSError("owned recovery mirror fault")
        return stage_bytes(operation_id, name, payload)

    def fail_recorder(_operation_id: str, _state: str) -> None:
        raise OSError("owned operation recorder fault")

    with monkeypatch.context() as patch:
        faulty = publisher
        if failure == "compatibility-copy":
            patch.setattr(fs, "stage_bytes", fail_copy)
        else:
            faulty = ThemeTransaction(themes, store, record_operation=fail_recorder)
        with pytest.raises(OSError, match="owned"):
            faulty.install(source, new, force=True)
    assert manifest.read_bytes() == previous
    created = set(paths.journal_dir().glob("*.jsonl")) - before
    assert len(created) == 1
    operation_id = created.pop().stem
    assert journal.has_type(journal.read_records(operation_id), journal.ROLLBACK)
    assert not paths.staging_for(operation_id).exists()
    assert store.verify(set(old.assets.values()) | set(new.assets.values()))["ok"]
    retried = publisher.install(source, new, force=True)
    assert publisher.rollback(source.id, retried["operationId"])["restoredPrevious"]
    assert manifest.read_bytes() == previous


def test_stale_install_preview_preserves_the_concurrent_write_and_can_be_replanned(
    store: ThemeAssetStore, themes: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.core import paths, transaction

    source = _source()
    report = ingest_archive(
        _tarball(tmp_path / "theme.tar.gz", {"theme.xml": b"<t/>"}), source, store
    )
    publisher = ThemeTransaction(themes, store)
    publisher.install(source, report)
    manifest = themes / source.id / "theme.json"
    concurrent = manifest.read_bytes() + b"\n"
    original_plan = transaction.plan_write_files
    before = set(paths.journal_dir().glob("*.jsonl"))

    def concurrent_write(*args: object, **kwargs: object) -> transaction.Plan:
        # Actual disk write between the domain's before-image read and the
        # Core's real plan. This is a race fixture, not a replacement executor.
        manifest.write_bytes(concurrent)
        return original_plan(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(transaction, "plan_write_files", concurrent_write)
        with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
            publisher.install(source, report, force=True)
    assert manifest.read_bytes() == concurrent
    assert set(paths.journal_dir().glob("*.jsonl")) == before
    retried = publisher.install(source, report, force=True)
    assert publisher.rollback(source.id, retried["operationId"])["restoredPrevious"]
    assert manifest.read_bytes() == concurrent


@pytest.mark.parametrize("damage", ["symlink", "directory"])
def test_unsafe_current_manifest_refuses_rollback_until_the_owned_file_is_repaired(
    store: ThemeAssetStore, themes: Path, tmp_path: Path, damage: str
) -> None:
    from steamzero.core import paths

    source = _source()
    report = ingest_archive(
        _tarball(tmp_path / "theme.tar.gz", {"theme.xml": b"<t/>"}), source, store
    )
    publisher = ThemeTransaction(themes, store)
    installed = publisher.install(source, report)
    operation_id = installed["operationId"]
    manifest = themes / source.id / "theme.json"
    current = manifest.read_bytes()
    foreign = tmp_path / "unowned.json"
    foreign.write_bytes(current)
    manifest.unlink()
    if damage == "symlink":
        manifest.symlink_to(foreign)
    else:
        manifest.mkdir()
    recorded = paths.journal_path(operation_id).read_bytes()
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        publisher.rollback(source.id, operation_id)
    assert paths.journal_path(operation_id).read_bytes() == recorded
    assert foreign.read_bytes() == current
    if damage == "symlink":
        assert manifest.is_symlink()
        manifest.unlink()
    else:
        assert manifest.is_dir()
        manifest.rmdir()
    manifest.write_bytes(current)
    assert not publisher.rollback(source.id, operation_id)["restoredPrevious"]
    assert not manifest.exists()
    assert foreign.read_bytes() == current


def test_hash_owned_opaque_beforeimage_is_restored_byte_exactly(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    source = _source()
    report = ingest_archive(
        _tarball(tmp_path / "theme.tar.gz", {"theme.xml": b"<t/>"}), source, store
    )
    manifest = themes / source.id / "theme.json"
    manifest.parent.mkdir()
    opaque = b"legacy damaged manifest bytes\xff\x00"
    manifest.write_bytes(opaque)
    publisher = ThemeTransaction(themes, store)
    installed = publisher.install(source, report, force=True)
    assert manifest.read_bytes() != opaque
    assert publisher.rollback(source.id, installed["operationId"])["restoredPrevious"]
    assert manifest.read_bytes() == opaque
    assert store.verify(report.assets.values())["ok"]


def test_rollback_refuses_missing_old_asset_and_recovers_after_reingestion(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    from steamzero.core import journal, paths

    old_art = b"owned previous artwork"
    old = _tarball(tmp_path / "old.tar.gz", {"theme.xml": b"<theme/>", "old.png": old_art})
    new = _tarball(tmp_path / "new.tar.gz", {"theme.xml": b"<theme/>", "new.png": b"new"})
    transaction = ThemeTransaction(themes, store)
    initial = ingest_archive(old, _source(), store)
    transaction.install(_source(), initial)
    manifest = themes / _source().id / "theme.json"
    original = manifest.read_bytes()
    replacement = transaction.install(_source(), ingest_archive(new, _source(), store), force=True)
    operation_id = replacement["operationId"]
    current = manifest.read_bytes()
    before_journal = journal.read_records(operation_id)
    snapshot = paths.staging_for(operation_id) / "previous-theme.json"
    store.blob_path(initial.assets["old.png"]).unlink()
    with pytest.raises(SteamZeroError, match="E-CONTENT-INCOMPLETE"):
        transaction.rollback(_source().id, operation_id)
    assert manifest.read_bytes() == current
    assert snapshot.read_bytes() == original
    assert journal.read_records(operation_id) == before_journal
    assert store.put("old.png", old_art).digest == initial.assets["old.png"]
    assert transaction.rollback(_source().id, operation_id)["restoredPrevious"]
    assert manifest.read_bytes() == original


def test_first_install_creates_its_owned_theme_root(store: ThemeAssetStore, tmp_path: Path) -> None:
    root = tmp_path / "fresh-profile" / "themes"
    archive = _tarball(tmp_path / "first.tar.gz", {"theme.xml": b"<theme/>"})
    transaction = ThemeTransaction(root, store)
    result = transaction.install(_source(), ingest_archive(archive, _source(), store))
    assert result["replaced"] is False
    assert json.loads((root / _source().id / "theme.json").read_bytes())["id"] == _source().id
    assert transaction.rollback(_source().id, result["operationId"])["restoredPrevious"] is False


def test_uninstall_never_touches_blobs(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    shared = b"compartilhado"
    a = _tarball(tmp_path / "a.tar.gz", {"s.png": shared, "a.xml": b"<theme/>"})
    b = _tarball(tmp_path / "b.tar.gz", {"s.png": shared, "b.xml": b"<theme/>"})
    transaction = ThemeTransaction(themes, store)
    transaction.install(_source("org.esde.a"), ingest_archive(a, _source("org.esde.a"), store))
    transaction.install(_source("org.esde.b"), ingest_archive(b, _source("org.esde.b"), store))
    blobs_before = store.usage()["blobs"]

    transaction.uninstall("org.esde.a")

    assert store.usage()["blobs"] == blobs_before
    remaining = live_digests(load_installed_manifests(themes))
    assert store.verify(remaining)["ok"] is True


def test_acquire_and_install_cleans_the_archive_but_keeps_the_undo(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """O tarball vai embora; o `previous-theme.json` fica, porque é o rollback."""
    prepared = _tarball(tmp_path / "src.tar.gz", {"theme.xml": b"<theme/>"})
    captured: dict[str, Path] = {}

    def fake_download(source: ThemeSource, *, operation_id: str, **_: object) -> Path:
        from steamzero.core import fs

        staged = fs.stage_bytes(operation_id, "theme.tar.gz", prepared.read_bytes())
        captured["archive"] = staged
        return staged

    result = acquire_and_install(_source(), store, themes, download=fake_download)

    assert result["assetCount"] == 1
    assert not captured["archive"].exists()
    # O DIRETÓRIO também: apagar só o arquivo deixava uma árvore vazia por
    # instalação, que o doctor conta como staging órfã. Este teste antes
    # conferia apenas o arquivo, e foi por essa fresta que o vazamento passou.
    assert not captured["archive"].parent.exists(), "o staging do download ficou para trás"
    assert (themes / "org.esde.demo" / "theme.json").is_file()


def test_a_fresh_install_leaves_no_staging_behind_and_still_rolls_back(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """Instalar sem tema anterior não pode deixar rastro, e ainda assim desfaz.

    O staging do download tem `operation_id` PRÓPRIO, diferente do que
    ``install`` devolve para o rollback. Confundir os dois foi o que fez a
    limpeza parecer perigosa quando não era: sem `previous-theme.json`, desfazer
    é voltar a não ter o tema, e isso não depende de diretório nenhum.
    """
    from steamzero.core import fs, paths

    prepared = _tarball(tmp_path / "src.tar.gz", {"theme.xml": b"<theme/>"})

    def fake_download(source: ThemeSource, *, operation_id: str, **_: object) -> Path:
        return fs.stage_bytes(operation_id, "theme.tar.gz", prepared.read_bytes())

    staging_root = paths.staging_dir()

    def snapshot() -> set[Path]:
        # Instantâneo antes/depois em vez de "o staging está vazio": o diretório
        # de estado é compartilhado na sessão de teste, e uma asserção global
        # mediria sujeira de outro teste em vez do que ESTA chamada deixou.
        return set(staging_root.iterdir()) if staging_root.exists() else set()

    before = snapshot()
    result = acquire_and_install(_source(), store, themes, download=fake_download)

    assert result["replaced"] is False
    assert result["undoPath"] == ""
    left_behind = snapshot() - before
    assert left_behind == set(), f"staging deixado pela instalação: {left_behind}"

    undone = ThemeTransaction(themes, store).rollback("org.esde.demo", result["operationId"])
    assert undone["restoredPrevious"] is False
    assert not (themes / "org.esde.demo" / "theme.json").exists()
    assert undone["assetsPreserved"] is True


def test_theme_id_cannot_escape_the_themes_directory(store: ThemeAssetStore, themes: Path) -> None:
    hostile = ThemeSource(
        id="../../evadido",
        name="x",
        family="esde",
        author="x",
        credits=("x",),
        license_id="CC0-1.0",
        license_source="",
        homepage="",
        forge="github",
        repo="a/b",
        commit=_COMMIT,
    )
    report = AcquisitionReport(theme_id=hostile.id, assets={})

    with pytest.raises(SteamZeroError) as excinfo:
        ThemeTransaction(themes, store).install(hostile, report)
    assert excinfo.value.code == "E-THEME-UNSAFE"


def test_installed_manifest_is_valid_json_with_sorted_assets(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    archive = _tarball(tmp_path / "t.tar.gz", {"z.png": b"z", "a.png": b"a", "theme.xml": b"<t/>"})
    transaction = ThemeTransaction(themes, store)
    transaction.install(_source(), ingest_archive(archive, _source(), store))

    manifest = json.loads((themes / "org.esde.demo" / "theme.json").read_text(encoding="utf-8"))

    assert list(manifest["assets"]) == sorted(manifest["assets"])
    assert manifest["kind"] == "steamzero-theme-v1"


def test_internal_repetition_is_not_counted_as_sharing_with_other_themes(
    store: ThemeAssetStore, tmp_path: Path
) -> None:
    """A distinção foi paga com uma conclusão errada, em 2026-09-03.

    Um contador único de "deduplicado" fez o nso-menu parecer ter reaproveitado
    6,1 MB do xmb-menu já instalado. Medindo blob a blob, os dois temas
    compartilhavam UM arquivo: os 6,1 MB eram o nso deduplicando contra si
    mesmo, 53 arquivos repetidos dentro do próprio pacote.

    Somar as duas causas num número só é o que transforma uma medição numa
    alegação errada, e é isto que este teste impede de voltar.
    """
    repetido = b"o mesmo icone em dois caminhos do proprio pacote" * 16
    archive = _tarball(
        tmp_path / "t.tar.gz",
        {"a/icone.png": repetido, "b/icone.png": repetido, "theme.xml": b"<theme/>"},
    )

    report = ingest_archive(archive, _source(), store)

    # Nenhum outro tema estava instalado: compartilhamento tem de ser zero.
    assert report.bytes_shared_with_installed == 0
    assert report.bytes_repeated_in_package == len(repetido)
    assert report.files == 3
    # Dois blobs para tres arquivos: o repetido entrou uma vez.
    assert store.usage()["blobs"] == 2


def test_the_two_savings_columns_are_reported_separately(
    store: ThemeAssetStore, tmp_path: Path
) -> None:
    """Um pacote pode ter as DUAS economias ao mesmo tempo, e elas não se
    misturam: cada uma responde a uma pergunta diferente."""
    compartilhado = b"veio do tema ja instalado" * 8
    proprio = b"repetido dentro deste pacote" * 8
    primeiro = _tarball(tmp_path / "1.tar.gz", {"s.png": compartilhado, "x.xml": b"<a/>"})
    ingest_archive(primeiro, _source("org.esde.primeiro"), store)

    segundo = _tarball(
        tmp_path / "2.tar.gz",
        {"s.png": compartilhado, "p1.png": proprio, "p2.png": proprio, "y.xml": b"<b/>"},
    )
    report = ingest_archive(segundo, _source("org.esde.segundo"), store)

    assert report.bytes_shared_with_installed == len(compartilhado)
    assert report.bytes_repeated_in_package == len(proprio)
    assert report.bytes_ingested == len(proprio) + len(b"<b/>")


def test_a_replacement_registers_its_operation_so_the_rollback_has_an_owner(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """Staging com dado de rollback PRECISA de linha no banco.

    Sem ela, `state_audit` classifica o diretório como órfão, o doctor avisa e o
    `state cleanup` o coloca em quarentena — apagando o único artefato que torna
    a reinstalação reversível. Medido no host em 2026-09-03: o plano de limpeza
    listava 122 KB de dado de rollback vivo.
    """
    prepared = _tarball(tmp_path / "src.tar.gz", {"theme.xml": b"<theme/>"})
    recorded: list[tuple[str, str]] = []

    def fake_download(source: ThemeSource, *, operation_id: str, **_: object) -> Path:
        from steamzero.core import fs

        return fs.stage_bytes(operation_id, "theme.tar.gz", prepared.read_bytes())

    def recorder(operation_id: str, state: str) -> None:
        recorded.append((operation_id, state))

    first = acquire_and_install(
        _source(), store, themes, download=fake_download, record_operation=recorder
    )
    assert recorded == [], "instalação nova não deixa rollback e não precisa de registro"

    second = acquire_and_install(
        _source(),
        store,
        themes,
        force=True,
        download=fake_download,
        record_operation=recorder,
    )

    assert second["replaced"] is True
    assert first["operationId"] != second["operationId"]
    assert recorded == [(second["operationId"], "active")]


def test_undoing_a_replacement_clears_its_staging_and_closes_the_operation(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """Consumido o desfazer, o staging vira lixo e a operação fecha.

    Mantê-lo faria a auditoria seguinte acusar como órfão algo que já cumpriu a
    função — o mesmo falso positivo, só que uma etapa depois.
    """
    from steamzero.core import paths

    prepared = _tarball(tmp_path / "src.tar.gz", {"theme.xml": b"<theme/>"})
    recorded: list[tuple[str, str]] = []

    def fake_download(source: ThemeSource, *, operation_id: str, **_: object) -> Path:
        from steamzero.core import fs

        return fs.stage_bytes(operation_id, "theme.tar.gz", prepared.read_bytes())

    def recorder(operation_id: str, state: str) -> None:
        recorded.append((operation_id, state))

    acquire_and_install(_source(), store, themes, download=fake_download, record_operation=recorder)
    replacement = acquire_and_install(
        _source(), store, themes, force=True, download=fake_download, record_operation=recorder
    )
    operation_id = replacement["operationId"]
    assert paths.staging_for(operation_id).is_dir()

    undone = ThemeTransaction(themes, store, record_operation=recorder).rollback(
        "org.esde.demo", operation_id
    )

    assert undone["restoredPrevious"] is True
    assert not paths.staging_for(operation_id).exists(), "staging sobrou depois do desfazer"
    assert recorded[-1] == (operation_id, "rolled-back")


def test_the_state_audit_no_longer_calls_live_rollback_data_an_orphan(
    store: ThemeAssetStore, themes: Path, tmp_path: Path
) -> None:
    """A prova de ponta: com o gravador REAL, a auditoria não acusa.

    Os testes acima observam a chamada; este observa a CONSEQUÊNCIA. Sem ele,
    trocar o estado gravado por um que a auditoria não reconhece passaria
    despercebido, e o defeito voltaria com os testes verdes.
    """
    from steamzero.core.state import StateStore
    from steamzero.domain import state_audit

    prepared = _tarball(tmp_path / "src.tar.gz", {"theme.xml": b"<theme/>"})

    def fake_download(source: ThemeSource, *, operation_id: str, **_: object) -> Path:
        from steamzero.core import fs

        return fs.stage_bytes(operation_id, "theme.tar.gz", prepared.read_bytes())

    acquire_and_install(_source(), store, themes, download=fake_download)
    replacement = acquire_and_install(_source(), store, themes, force=True, download=fake_download)

    with StateStore() as state:
        state.migrate()
        report = state_audit.audit(state)

    assert replacement["operationId"] not in report.orphan_staging, (
        "o staging do rollback continua sem dono para a auditoria"
    )


def test_uninstall_preserves_custom_inheritance_consumers(
    themes: Path, store: ThemeAssetStore
) -> None:
    parent = themes / "org.example.parent"
    child = themes / "org.example.child"
    for directory, manifest in [
        (parent, {"id": parent.name}),
        (child, {"id": child.name, "extends": parent.name}),
    ]:
        directory.mkdir()
        (directory / "theme.json").write_text(json.dumps(manifest))
    original = (parent / "theme.json").read_bytes()
    transaction = ThemeTransaction(themes, store, record_operation=lambda *_: None)
    with pytest.raises(SteamZeroError, match=r"org\.example\.child"):
        transaction.uninstall(parent.name)
    assert (parent / "theme.json").read_bytes() == original
    transaction.uninstall(child.name)
    assert transaction.uninstall(parent.name)["removed"]


def test_first_install_rollback_refuses_live_children_and_preserves_blobs(
    tmp_path: Path, themes: Path, store: ThemeAssetStore
) -> None:
    source = _source()
    report = ingest_archive(
        _tarball(tmp_path / "rollback.tar.gz", {"theme.xml": b"<theme/>"}), source, store
    )
    recorded: list[str] = []
    transaction = ThemeTransaction(
        themes, store, record_operation=lambda _id, state: recorded.append(state)
    )
    installed = transaction.install(source, report)
    manifest = themes / source.id / "theme.json"
    original = manifest.read_bytes()
    child = themes / "org.example.child"
    child.mkdir()
    (child / "theme.json").write_text(json.dumps({"id": child.name, "extends": source.id}))
    usage = store.usage()
    with pytest.raises(SteamZeroError, match=r"org\.example\.child"):
        transaction.rollback(source.id, installed["operationId"])
    assert manifest.read_bytes() == original
    assert recorded == []
    assert store.usage() == usage
    transaction.uninstall(child.name)
    assert transaction.rollback(source.id, installed["operationId"])["restoredPrevious"] is False
    assert store.usage() == usage
    assert recorded == ["rolled-back"]


def test_version_restore_does_not_use_the_removal_guard(
    tmp_path: Path, themes: Path, store: ThemeAssetStore
) -> None:
    source = _source()
    first = ingest_archive(
        _tarball(tmp_path / "first.tar.gz", {"theme.xml": b"<theme/>"}), source, store
    )
    called: list[str] = []

    def refuse_removal(theme_id: str) -> None:
        called.append(theme_id)
        raise SteamZeroError("E-THEME-ACTIVE", detail="owned active consumer")

    transaction = ThemeTransaction(
        themes, store, record_operation=lambda *_: None, removal_guard=refuse_removal
    )
    transaction.install(source, first)
    manifest = themes / source.id / "theme.json"
    original = manifest.read_bytes()
    second = ingest_archive(
        _tarball(tmp_path / "second.tar.gz", {"theme.xml": b"<theme changed='1'/>"}), source, store
    )
    replaced = transaction.install(source, second, force=True)
    assert manifest.read_bytes() != original
    assert transaction.rollback(source.id, replaced["operationId"])["restoredPrevious"] is True
    assert manifest.read_bytes() == original
    assert called == []

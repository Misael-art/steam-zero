# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Aquisição e instalação transacional de temas ES-DE.

O operador pediu que temas tivessem o mesmo rigor dos componentes: transação com
rollback completo, **preservando os assets compartilhados** para não quebrar
dependências de outros temas. Este módulo é onde as duas exigências se encontram,
e elas se resolvem juntas por causa de uma propriedade do store.

**Por que o rollback aqui é simples.** Como ``theme_assets`` guarda blobs por
conteúdo e a posse é derivada dos manifestos instalados, a instalação de um tema
NUNCA sobrescreve nem remove um blob: no pior caso ela adiciona blobs que passam
a não ter dono. Desfazer, então, é remover o manifesto e restaurar o anterior —
duas operações de um arquivo só. Nenhum asset precisa ser restaurado porque
nenhum foi destruído, e um blob que outro tema referencia continua referenciado.
O espaço eventualmente ocioso é recuperado por ``collect_garbage``, que é
explícito e seguro de rodar a qualquer momento.

Um contador de referências teria feito o rollback ter que desfazer incrementos,
e um incremento perdido no meio de uma queda corromperia a contabilidade
silenciosamente. É a razão de ele não existir.

**Ingestão em fluxo.** O tarball tem de 60 a 150 MB, quase tudo binário. Cada
membro vai do tar direto ao store, sem materializar a árvore: gasta metade do
espaço e unifica na entrada o que o próprio pacote repete.

**Sobre a economia, com o número medido.** Entre xmb-menu e nso-menu, dois temas
ES-DE reais, os blobs em comum foram **um**. Temas ES-DE trazem a própria arte,
as próprias fontes e o próprio fundo; eles não dividem acervo. A deduplicação
paga em dois casos que existem de verdade — duplicatas dentro do mesmo pacote
(6,1 MB de 80 MB no nso-menu) e duas versões do mesmo tema, onde a maior parte
dos arquivos é idêntica — mas prometer economia entre temas distintos seria
contrariar a medição.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from steamzero.core import fs, ids, journal, log, paths, transaction
from steamzero.core.errors import SteamZeroError
from steamzero.core.net import HttpClient, fetch_bytes
from steamzero.core.safetar import SafeTarLimits, iter_members
from steamzero.domain.theme_assets import (
    ALLOWED_SUFFIXES,
    ThemeAssetStore,
    digest_bytes,
    live_digests,
    load_installed_manifests,
)
from steamzero.domain.theme_sources import ThemeSource

#: Teto do tarball. O maior tema licenciado medido em 2026-09-03 (iconic) fica
#: bem abaixo; o teto existe para que um endereço trocado não vire download sem
#: fim, não para apertar os temas conhecidos.
MAX_ARCHIVE_BYTES = 320 * 1024 * 1024

MAX_ROLLBACK_MANIFESTS = 256
MAX_ROLLBACK_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_ROLLBACK_TOTAL_BYTES = 64 * 1024 * 1024
MAX_THEME_JOURNAL_BYTES = 2 * 1024 * 1024
MAX_THEME_JOURNAL_RECORDS = 4096
MAX_THEME_JOURNAL_SCAN_ENTRIES = 4096
MAX_THEME_JOURNAL_SCAN_BYTES = 16 * 1024 * 1024


def _theme_operation_records(
    operation_id: str,
) -> tuple[list[dict[str, Any]], int] | None:
    """Read the existing core journal, bounded and without following links."""
    try:
        fd = os.open(
            paths.journal_path(operation_id),
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        )
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("journal não é arquivo regular")
        first = stream.readline(4097)
        if not first:
            # An interrupted new journal and a truncated live journal cannot
            # be distinguished here. Preserve data until ownership is known.
            raise ValueError("journal vazio; recuperação não verificável")
        if len(first) > 4096:
            raise ValueError("cabeçalho de journal excede o limite")
        begin = json.loads(first)
        if (
            not isinstance(begin, dict)
            or begin.get("type") != "operation.begin"
            or not isinstance(begin.get("kind"), str)
        ):
            raise ValueError("cabeçalho de journal inválido")
        if begin["kind"] not in {"theme.acquire", "theme.retrofe.import"}:
            return None
        payload = first + stream.read(MAX_THEME_JOURNAL_BYTES + 1)
    if len(payload) > MAX_THEME_JOURNAL_BYTES:
        raise ValueError("journal de tema excede o limite")
    lines = payload.splitlines()
    if len(lines) > MAX_THEME_JOURNAL_RECORDS:
        raise ValueError("journal de tema excede o orçamento de registros")
    records = [json.loads(line) for line in lines if line.strip()]
    if not all(
        isinstance(record, dict)
        and record.get("operationId") == operation_id
        and record.get("seq") == index
        for index, record in enumerate(records)
    ):
        raise ValueError("identidade de journal divergente")
    return records, len(payload)


def _theme_backup_bytes(operation_id: str, action_id: str, undo: dict[str, Any]) -> bytes:
    name = undo.get("backupRel")
    if name != action_id or not isinstance(name, str) or not ids.ULID_RE.fullmatch(name):
        raise ValueError("identidade do backup inválida")
    directory_fd = os.open(
        paths.backup_for(operation_id),
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("backup não é arquivo regular")
            payload = stream.read(MAX_ROLLBACK_MANIFEST_BYTES + 1)
    finally:
        os.close(directory_fd)
    if len(payload) > MAX_ROLLBACK_MANIFEST_BYTES:
        raise ValueError("backup excede o orçamento de manifesto")
    return payload


def _snapshot_digests(payload: bytes) -> set[str]:
    manifest = json.loads(payload)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("assets"), dict):
        raise ValueError("snapshot sem assets reconhecidos")
    digests = live_digests([manifest])
    for asset in manifest["assets"].values():
        digest = asset.get("digest") if isinstance(asset, dict) else asset
        if not isinstance(digest, str) or digest not in digests:
            raise ValueError("snapshot com digest inválido")
    return digests


def _core_rollback_live_digests(count: int = 0, total: int = 0) -> set[str]:
    """Core backups remain owners even before the compatibility copy exists."""
    protected: set[str] = set()
    folder = paths.journal_dir()
    try:
        if folder.is_symlink():
            raise ValueError("journal de recuperação é link")
        if not folder.exists():
            return protected
        journal_bytes = 0
        for scanned, path in enumerate(folder.iterdir(), start=1):
            if scanned > MAX_THEME_JOURNAL_SCAN_ENTRIES:
                raise SteamZeroError("E-THEME-LIMIT", detail="muitos journals para verificar")
            if path.suffix != ".jsonl" or not ids.ULID_RE.fullmatch(path.stem):
                continue
            owned = _theme_operation_records(path.stem)
            if owned is None:
                continue
            records, size = owned
            journal_bytes += size
            if journal_bytes > MAX_THEME_JOURNAL_SCAN_BYTES:
                raise SteamZeroError("E-THEME-LIMIT", detail="journals excedem o orçamento")
            if journal.has_type(records, journal.ROLLBACK):
                continue
            intents = [record for record in records if record.get("type") == "action.intent"]
            if not intents and not journal.has_type(records, journal.COMMIT):
                continue  # No manifest publication preceded a durable intent.
            retrofe = records[0]["kind"] == "theme.retrofe.import"
            if retrofe:
                if len(intents) > 2:
                    raise ValueError("publicação RetroFE com ações inesperadas")
                # Core sorts targets before writing. The sidecar sorts before
                # its scene, including scene IDs that themselves end in .assets.
                intents = intents[:1]
            if len(intents) != 1:
                raise ValueError("journal de tema sem alvo único")
            intent = intents[0]
            undo = intent["undo"]
            target = Path(undo["target"])
            # A different profile/root owns its own asset store. Do not add
            # unrelated test/custom-root backups to this store's live graph.
            if retrofe:
                if (
                    not target.name.endswith(".assets.json")
                    or target.parent != paths.scenes_dir().resolve()
                ):
                    continue
            elif (
                target.name != "theme.json" or target.parent.parent != paths.themes_dir().resolve()
            ):
                continue
            if undo["op"] == "delete":
                continue
            if undo["op"] != "restore":
                raise ValueError("tipo de recuperação desconhecido")
            payload = _theme_backup_bytes(path.stem, intent["actionId"], undo)
            if fs.hash_bytes(payload) != undo["expectHash"]:
                raise ValueError("backup de recuperação adulterado")
            count += 1
            total += len(payload)
            if count > MAX_ROLLBACK_MANIFESTS or total > MAX_ROLLBACK_TOTAL_BYTES:
                raise SteamZeroError("E-THEME-LIMIT", detail="backups excedem o orçamento")
            protected.update(_snapshot_digests(payload))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SteamZeroError(
            "E-THEME-MANIFEST", detail="recuperação de tema inválida; limpeza recusada"
        ) from exc
    return protected


def rollback_live_digests() -> set[str]:
    """Protect assets in owned undo snapshots before any garbage collection.

    Staging already holds the previous manifests; derive ownership there rather
    than maintaining another registry. An unreadable or oversized snapshot must
    stop collection, never silently shrink the set of protected assets.
    """
    protected: set[str] = set()
    count = total = 0
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        root_fd = os.open(paths.staging_dir(), directory_flags)
    except FileNotFoundError:
        return _core_rollback_live_digests()
    except OSError as exc:
        raise SteamZeroError("E-THEME-MANIFEST", detail="staging de recuperação ilegível") from exc
    try:
        for name in os.listdir(root_fd):
            if not ids.ULID_RE.fullmatch(name):
                continue
            operation_fd = os.open(name, directory_flags, dir_fd=root_fd)
            try:
                try:
                    fd = os.open(
                        "previous-theme.json",
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                        dir_fd=operation_fd,
                    )
                except FileNotFoundError:
                    continue
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise ValueError("snapshot não é arquivo regular")
                    count += 1
                    if count > MAX_ROLLBACK_MANIFESTS:
                        raise SteamZeroError(
                            "E-THEME-LIMIT", detail="muitos snapshots de recuperação"
                        )
                    data = stream.read(MAX_ROLLBACK_MANIFEST_BYTES + 1)
                total += len(data)
                if len(data) > MAX_ROLLBACK_MANIFEST_BYTES or total > MAX_ROLLBACK_TOTAL_BYTES:
                    raise SteamZeroError(
                        "E-THEME-LIMIT", detail="snapshots de recuperação excedem o limite"
                    )
                protected.update(_snapshot_digests(data))
            finally:
                os.close(operation_fd)
    except (OSError, ValueError) as exc:
        raise SteamZeroError(
            "E-THEME-MANIFEST", detail="snapshot de recuperação inválido; limpeza recusada"
        ) from exc
    finally:
        os.close(root_fd)
    return protected | _core_rollback_live_digests(count, total)


_INGEST_LIMITS = SafeTarLimits(
    max_entries=20_000,
    max_total_bytes=512 * 1024 * 1024,
    max_entry_bytes=64 * 1024 * 1024,
    max_depth=16,
)


@dataclass
class AcquisitionReport:
    """O que entrou, o que já existia e o que foi recusado.

    A economia é contada em DUAS colunas separadas, e a separação foi paga com
    uma conclusão errada: um único contador de "deduplicado" fez o nso-menu
    parecer ter reaproveitado 6,1 MB do xmb-menu já instalado. Medindo blob a
    blob depois, os dois temas compartilhavam **um** arquivo. Os 6,1 MB eram o
    nso deduplicando contra si mesmo — 53 arquivos repetidos dentro do próprio
    pacote.

    As duas economias são reais e têm causas diferentes:

    - ``bytes_repeated_in_package``: o pacote traz o mesmo arquivo mais de uma
      vez. Acontece sempre, é interno e não diz nada sobre outros temas.
    - ``bytes_shared_with_installed``: o arquivo já estava no store por causa de
      OUTRO tema. É esta que sustenta a promessa de compartilhamento, e é a que
      precisa ser olhada antes de afirmar que dois temas dividem assets.

    Somá-las num número só é o que transforma uma medição em alegação errada.
    """

    theme_id: str
    files: int = 0
    bytes_ingested: int = 0
    bytes_repeated_in_package: int = 0
    bytes_shared_with_installed: int = 0
    skipped: int = 0
    assets: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "themeId": self.theme_id,
            "files": self.files,
            "bytesIngested": self.bytes_ingested,
            "bytesRepeatedInPackage": self.bytes_repeated_in_package,
            "bytesSharedWithInstalled": self.bytes_shared_with_installed,
            "skipped": self.skipped,
            "assetCount": len(self.assets),
        }


def ingest_archive(
    archive: Path,
    source: ThemeSource,
    store: ThemeAssetStore,
) -> AcquisitionReport:
    """Move o conteúdo do tarball para o store, um membro por vez.

    Devolve o mapa ``caminho lógico -> digest`` que vira o manifesto do tema.

    O que já estava no store é classificado por ORIGEM: se este mesmo pacote já
    o trouxe, é repetição interna; se não, veio de outro tema. Sem separar as
    duas, um pacote com muitas duplicatas próprias parece estar reaproveitando
    o acervo alheio — foi exatamente o erro cometido em 2026-09-03.
    """
    report = AcquisitionReport(theme_id=source.id)
    # Digests que ESTE pacote já entregou, para distinguir repetição interna de
    # compartilhamento com o que já estava instalado.
    seen_in_package: set[str] = set()
    for member in iter_members(
        archive,
        limits=_INGEST_LIMITS,
        strip_components=source.root_prefix_components,
        allowed_suffixes=ALLOWED_SUFFIXES,
    ):
        digest = digest_bytes(member.payload)
        already_stored = store.has(digest)
        repeated_here = digest in seen_in_package
        try:
            stored = store.put(member.path, member.payload)
        except SteamZeroError as exc:
            if exc.code != "E-THEME-UNSAFE":
                raise
            # Extensão fora da fronteira: pular é o correto, e a contagem
            # mantém visível que algo do pacote não entrou.
            report.skipped += 1
            continue
        seen_in_package.add(stored.digest)
        report.assets[member.path] = stored.digest
        report.files += 1
        if repeated_here:
            report.bytes_repeated_in_package += member.size
        elif already_stored:
            report.bytes_shared_with_installed += member.size
        else:
            report.bytes_ingested += member.size
    if not report.assets:
        raise SteamZeroError(
            "E-CONTENT-INCOMPLETE",
            detail=f"o pacote de '{source.id}' não trouxe nenhum arquivo utilizável",
        )
    return report


def download_archive(
    source: ThemeSource,
    *,
    operation_id: str,
    http_client: HttpClient | None = None,
    expected_sha256: str | None = None,
) -> Path:
    """Baixa o tarball do commit fixado, para o staging da operação.

    ``expected_sha256`` é opcional **por medição**: os tarballs das duas forges
    se mostraram byte-estáveis entre downloads (verificado em 2026-09-03), mas o
    que garante o conteúdo é o commit, que é o próprio hash da árvore no git.
    Quando o checksum é declarado ele é exigido; sem ele, a identidade continua
    ancorada no commit e não no empacotamento, que a forge pode mudar.
    """
    payload = fetch_bytes(source.archive_url, max_bytes=MAX_ARCHIVE_BYTES, client=http_client)
    if expected_sha256:
        digest = digest_bytes(payload)
        if digest != expected_sha256:
            raise SteamZeroError(
                "E-CONTENT-INCOMPLETE",
                detail=f"checksum do pacote de '{source.id}' não confere",
            )
    return fs.stage_bytes(operation_id, "theme.tar.gz", payload)


def build_manifest(source: ThemeSource, report: AcquisitionReport) -> dict[str, Any]:
    """Manifesto do tema instalado: identidade, crédito e o mapa de assets.

    ``credits`` viaja junto porque CC-BY-NC-SA exige atribuição e três dos cinco
    temas curados são obras derivadas — publicar só o dono do repositório
    apagaria quem fez o trabalho original.
    """
    return {
        "schemaVersion": 1,
        "kind": "steamzero-theme-v1",
        "id": source.id,
        "name": source.name,
        "version": source.commit[:12],
        "author": source.author,
        "credits": list(source.credits),
        "license": source.license_id,
        "homepage": source.homepage,
        "origin": {
            "family": source.family,
            "forge": source.forge,
            "repo": source.repo,
            "commit": source.commit,
        },
        "assets": {path: {"digest": digest} for path, digest in sorted(report.assets.items())},
    }


#: Assinatura do gravador de operação: ``(operation_id, state)``.
OperationRecorder = Callable[[str, str], None]


def record_operation_state(operation_id: str, state: str) -> None:
    """Espelha a operação de tema no State Store.

    Sem esta linha o diretório de staging que guarda o ``previous-theme.json``
    fica sem dono: ``state_audit`` o classifica como órfão, o doctor avisa e o
    ``state cleanup`` o coloca em quarentena — apagando o único artefato que
    torna a reinstalação reversível. Medido no host em 2026-09-03, onde o plano
    de limpeza listava 122 KB de dado de rollback vivo.

    O núcleo transacional é dono do journal/backup. O espelho da cópia de
    compatibilidade no staging não pode apagar esses vínculos ao mudar estado.
    """
    from steamzero.core.state import StateStore

    with StateStore() as store:
        store.migrate()
        previous = store.get_operation(operation_id) or {}
        store.save_operation(
            operation_id,
            state=state,
            journal_path=previous.get("journal_path"),
            backup_path=previous.get("backup_path"),
        )


class ThemeTransaction:
    """Instalação e remoção de tema com desfazer completo.

    A transação cobre exatamente um arquivo — o ``theme.json`` do tema — porque é
    esse arquivo que define o que está instalado. Os blobs ficam fora dela de
    propósito: eles são imutáveis e compartilhados, e incluí-los na transação
    obrigaria a decidir, no rollback, se um blob "pertencia" a esta operação. Essa
    pergunta não tem resposta correta quando dois temas usam o mesmo arquivo, e é
    exatamente onde um contador de referências erra.
    """

    def __init__(
        self,
        themes_root: Path,
        store: ThemeAssetStore,
        *,
        record_operation: OperationRecorder | None = None,
        removal_guard: Callable[[str], None] | None = None,
    ) -> None:
        self._root = themes_root
        self._store = store
        self._removal_guard = removal_guard
        # O registro é padrão, e não algo que o adaptador liga: uma operação que
        # deixa dado de rollback em disco SEM linha no banco parece órfã para o
        # resto do sistema — o doctor a acusa e o `state cleanup` a coloca em
        # quarentena, destruindo justamente o que torna a reinstalação
        # reversível. Injetável só para o teste poder observar a chamada.
        self._record = record_operation or record_operation_state

    def _manifest_path(self, theme_id: str) -> Path:
        directory = self._root / theme_id
        if directory.is_symlink() or directory.resolve().parent != self._root.resolve():
            raise SteamZeroError("E-THEME-UNSAFE", detail=f"id de tema inválido: {theme_id!r}")
        return directory / "theme.json"

    def install(
        self,
        source: ThemeSource,
        report: AcquisitionReport,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Publica o manifesto, guardando o anterior para permitir o desfazer."""
        manifest_path = self._manifest_path(source.id)
        if manifest_path.is_symlink():
            raise SteamZeroError("E-THEME-UNSAFE", detail="destino de manifesto é symlink")

        previous: bytes | None = None
        if manifest_path.is_file():
            if not force:
                raise SteamZeroError(
                    "E-THEME-DOWNLOAD-FAILED",
                    detail=f"tema '{source.id}' já instalado; confirme a substituição",
                )
            previous = manifest_path.read_bytes()

        manifest = build_manifest(source, report)
        # Verificar ANTES de publicar: um manifesto que aponta para blob ausente
        # instalaria um tema quebrado, e o defeito só apareceria ao renderizar.
        verification = self._store.verify(entry["digest"] for entry in manifest["assets"].values())
        if not verification["ok"]:
            raise SteamZeroError(
                "E-CONTENT-INCOMPLETE",
                detail=(
                    f"o store não tem todos os assets de '{source.id}': "
                    f"{len(verification['missing'])} ausente(s), "
                    f"{len(verification['corrupt'])} corrompido(s)"
                ),
            )

        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        plan = transaction.plan_write_files(
            {manifest_path: encoded}, root=self._root, kind="theme.acquire"
        )
        expected = fs.hash_bytes(previous) if previous is not None else None
        if plan.preconditions[0].fingerprint != expected:
            transaction.abort(plan.plan_id, plan.confirm_token)
            raise SteamZeroError("E-TX-STALE-PLAN", detail="tema mudou antes da instalação")
        applied = transaction.apply(plan.plan_id, plan.confirm_token)
        operation_id = applied.operation_id
        undo_path: Path | None = None
        if previous is not None:
            try:
                # Preserve the public undoPath/staging contract. The core's
                # hash-verified backup remains authoritative for rollback.
                undo_path = fs.stage_bytes(operation_id, "previous-theme.json", previous)
                self._record(operation_id, "active")
            except Exception:
                transaction.rollback(operation_id, reason="theme-acquire-mirror-failed")
                raise
        log.get_logger().info("theme_acquire.installed", theme=source.id, operation=operation_id)
        return {
            "themeId": source.id,
            "name": source.name,
            "version": manifest["version"],
            "license": source.license_id,
            "credits": list(source.credits),
            "operationId": operation_id,
            "assetCount": len(manifest["assets"]),
            "replaced": previous is not None,
            "undoPath": str(undo_path) if undo_path else "",
            "activated": False,
        }

    def rollback(self, theme_id: str, operation_id: str) -> dict[str, Any]:
        """Desfaz uma instalação, restaurando o manifesto anterior se havia um.

        Nenhum blob é tocado. É isso que garante que desfazer a instalação de um
        tema não invalide um asset que outro tema referencia — a preocupação que
        motivou o desenho.
        """
        manifest_path = self._manifest_path(theme_id)
        if not isinstance(operation_id, str) or not ids.ULID_RE.fullmatch(operation_id):
            raise SteamZeroError("E-API-SCHEMA", detail="operation_id inválido")
        try:
            owned = _theme_operation_records(operation_id)
            if owned is None:
                raise ValueError("operação sem vínculo verificável; snapshot legado preservado")
            records = owned[0]
            intents = [record for record in records if record.get("type") == "action.intent"]
            if len(intents) != 1:
                raise ValueError("operação de tema exige um alvo")
            undo = intents[0]["undo"]
            if (
                not isinstance(undo, dict)
                or undo.get("op") not in {"restore", "delete"}
                or Path(undo["target"]) != manifest_path.resolve()
            ):
                raise ValueError("operação não pertence a este tema")
            restored = undo["op"] == "restore"
            consumed = journal.has_type(records, journal.ROLLBACK)
            if not consumed:
                if manifest_path.is_symlink() or (
                    manifest_path.exists() and not manifest_path.is_file()
                ):
                    raise ValueError("manifesto atual inseguro")
                current = fs.hash_file(manifest_path) if manifest_path.is_file() else None
                accepted = {undo.get("expectHash"), undo.get("appliedHash")}
                if current is not None and current not in accepted:
                    raise ValueError("manifesto substituído após esta operação")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SteamZeroError(
                "E-TX-STALE-PLAN",
                operation_id=operation_id,
                detail="operação não corresponde ao tema atual; dados de recuperação preservados",
            ) from exc
        if not consumed and not restored and manifest_path.exists():
            self._assert_removable(theme_id)
        if not consumed and restored:
            try:
                previous = _theme_backup_bytes(operation_id, intents[0]["actionId"], undo)
                if fs.hash_bytes(previous) != undo["expectHash"]:
                    raise ValueError("hash de backup divergente")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise SteamZeroError(
                    "E-TX-ROLLBACK-FAILED",
                    operation_id=operation_id,
                    detail="backup indisponível; recuperação preservada",
                ) from exc
            try:
                previous_digests = _snapshot_digests(previous)
            except ValueError:
                # A known, hash-verified before-image can contain old damaged
                # bytes. Preserve the core's exact-byte restore contract.
                log.get_logger().warning(
                    "theme_acquire.legacy_restore_bytes", operation=operation_id
                )
            else:
                verification = self._store.verify(previous_digests)
                if not verification["ok"]:
                    raise SteamZeroError(
                        "E-CONTENT-INCOMPLETE",
                        operation_id=operation_id,
                        detail=(
                            "assets anteriores ausentes ou corrompidos; reingira antes de desfazer"
                        ),
                    )
        transaction.rollback(operation_id, reason="theme-acquire")
        self._record(operation_id, "rolled-back")
        return {
            "themeId": theme_id,
            "operationId": operation_id,
            "restoredPrevious": restored,
            "assetsPreserved": True,
        }

    def uninstall(self, theme_id: str) -> dict[str, Any]:
        """Remove o tema sem tocar nos blobs.

        O espaço não volta aqui, e isso é deliberado: o que ficou ocioso pode ser
        de outro tema que ainda não foi lido. ``collect_garbage`` responde essa
        pergunta olhando todos os manifestos de uma vez, que é a única forma de
        respondê-la corretamente.
        """
        manifest_path = self._manifest_path(theme_id)
        if not manifest_path.is_file():
            raise SteamZeroError(
                "E-THEME-NOT-FOUND", detail=f"tema '{theme_id}' não está instalado"
            )
        self._assert_removable(theme_id)
        fs.remove_file(manifest_path)
        return {"themeId": theme_id, "removed": True, "assetsPreserved": True}

    def _assert_removable(self, theme_id: str) -> None:
        dependents = sorted(
            str(manifest.get("id", "?"))
            for manifest in load_installed_manifests(self._root)
            if manifest.get("extends") == theme_id
        )
        if dependents:
            raise SteamZeroError(
                "E-THEME-MANIFEST",
                detail=(
                    f"tema usado como base por {', '.join(dependents)}; "
                    "altere a herança desses temas antes de remover"
                )[:400],
            )
        if self._removal_guard is not None:
            self._removal_guard(theme_id)


def acquire_and_install(
    source: ThemeSource,
    store: ThemeAssetStore,
    themes_root: Path,
    *,
    force: bool = False,
    http_client: HttpClient | None = None,
    expected_sha256: str | None = None,
    download: Callable[..., Path] | None = None,
    record_operation: OperationRecorder | None = None,
) -> dict[str, Any]:
    """Fluxo completo: baixa, ingere em fluxo e publica o manifesto.

    O staging do DOWNLOAD é sempre limpo. O da instalação, quando existe, guarda
    o ``previous-theme.json`` que permite o rollback e fica — registrado no
    banco, para que a auditoria saiba que tem dono.
    """
    operation_id = ids.new_ulid()
    fetch = download or download_archive
    archive = fetch(
        source,
        operation_id=operation_id,
        http_client=http_client,
        expected_sha256=expected_sha256,
    )
    try:
        report = ingest_archive(archive, source, store)
        transaction = ThemeTransaction(themes_root, store, record_operation=record_operation)
        result = transaction.install(source, report, force=force)
    finally:
        # O tarball já não é necessário depois da ingestão, com ou sem sucesso,
        # e o DIRETÓRIO dele também não: este `operation_id` é o do download, e
        # não o que `install` devolve para o rollback. Apagar só o arquivo
        # deixava uma árvore vazia por instalação, que o doctor conta como
        # staging órfã — três instalações, três órfãs, medido no host.
        fs.remove_tree(paths.staging_for(operation_id))
    return {**result, "acquisition": report.to_dict()}

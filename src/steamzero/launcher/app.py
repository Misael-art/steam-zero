# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Processo do AURA Launcher.

Monta as seções da home, sobe a ponte e abre a cena. A biblioteca vem da fonte
canônica do projeto (``emulation-library-cache-v1.json``), achada sozinha
quando ninguém passou ``--library``; o argumento continua valendo para apontar
outro arquivo. O lançamento de cada jogo é delegado à rota de produto
``emulation launch --game-id``, que resolve emulador, chaves e sessão.

Sem biblioteca, o Launcher **abre assim mesmo**, com a home vazia acionável que
o domínio já resolve. Primeira execução sem acervo é o caso comum, não erro.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from steamzero.adapters.journey_public import (
    journey_public_field_types,
    project_game_row,
)
from steamzero.adapters.launcher_catalog import (
    CatalogGame,
    _platform_label,
    catalog_games,
    catalog_summary,
)
from steamzero.adapters.launcher_media import launcher_media_metadata
from steamzero.adapters.launcher_receipt import (
    LaunchAttempt,
    ReceiptSpawner,
    spawn_receipt,
)
from steamzero.core import fs, ids, paths
from steamzero.core.errors import SteamZeroError
from steamzero.core.title_variants import TITLE_VARIANT_MODES
from steamzero.launcher.journey_runtime import JourneyRuntime
from steamzero.launcher.launch import LaunchPlan, Spawn, consume_context, launch_detached
from steamzero.launcher.navigation import HomeSection

_DEFAULT_SECTION = "library"
_SECTION_TITLES = {
    "continue": "Continuar",
    "library": "Biblioteca",
    "collections": "Coleções",
}
_MAX_LIBRARY_BYTES = 64 * 1024 * 1024


def build_titles(games: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Mapa id -> título exibível.

    O domínio de foco trabalha só com ids; o título viaja à parte para a home
    não acabar mostrando `celeste` onde o usuário espera `Celeste`.

    A biblioteca canônica publica o rótulo em ``name``; ``title`` é aceito como
    alias porque outras fontes o usam. Ler só ``title`` fazia o fallback para o
    id disparar em TODO o acervo real, e a home do Launcher exibia
    ``ae18c7e53583298461a0edea`` no lugar de ``1969 (Homebrew) (SMS)`` —
    observado na release 2.0.0rc1-720928250e1a com os 80 jogos do host.
    """
    titles: dict[str, str] = {}
    for game in games:
        identifier = str(game.get("id", ""))
        if identifier:
            label = game.get("name") or game.get("title")
            titles[identifier] = str(label or identifier)
    return titles


def build_sections(games: Sequence[Mapping[str, Any]]) -> tuple[HomeSection, ...]:
    """Agrupa jogos em seções, preservando a ordem de chegada.

    Jogo sem id utilizável é descartado com o resto intacto: um registro
    corrompido na biblioteca não pode esvaziar a home inteira.
    """
    grouped: dict[str, list[str]] = {}
    for game in games:
        identifier = str(game.get("id", ""))
        section = str(game.get("section", _DEFAULT_SECTION)) or _DEFAULT_SECTION
        try:
            HomeSection(
                id=section,
                title=_SECTION_TITLES.get(section, section),
                items=(identifier,),
            )
        except ValueError:
            continue
        grouped.setdefault(section, []).append(identifier)
    return tuple(
        HomeSection(id=name, title=_SECTION_TITLES.get(name, name), items=tuple(items))
        for name, items in grouped.items()
    )


def canonical_library_path() -> Path:
    """Onde a varredura publica a biblioteca canônica."""
    return paths.data_home() / "emulation-library-cache-v1.json"


def _render_journey_xml_scene(
    theme_id: str,
    *,
    themes_root: Path | None = None,
    asset_store: Any = None,
) -> dict[str, Any]:
    """Resolve an imported portable XML scene for the Launcher renderer.

    The XML compiler and blob store remain the authority for includes and
    assets. A missing XML entry is a normal omission; a declared but invalid
    scene returns a visible diagnostic while leaving the native Cinema path
    available as fallback.
    """
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", theme_id):
        return {
            "state": "failed",
            "scene": None,
            "diagnostic": "O identificador da cena XML não é válido.",
        }
    from steamzero.domain import theme_assets, theme_scene

    root = Path(themes_root) if themes_root is not None else paths.themes_dir()
    package = root / theme_id
    manifest_path = package / "theme.json"
    if package.is_symlink() or manifest_path.is_symlink():
        return {
            "state": "failed",
            "scene": None,
            "diagnostic": "O pacote da cena XML não pode ser um link simbólico.",
        }
    if not manifest_path.is_file():
        return {"state": "omitted", "scene": None, "diagnostic": ""}
    try:
        manifest = theme_scene.load_manifest(root, theme_id)
    except Exception as exc:
        return {
            "state": "failed",
            "scene": None,
            "diagnostic": str(getattr(exc, "detail", "O manifesto XML não pôde ser lido."))[:240],
        }
    declared_assets = manifest.get("assets")
    if not isinstance(declared_assets, Mapping) or "theme.xml" not in declared_assets:
        return {"state": "omitted", "scene": None, "diagnostic": ""}
    store = asset_store or theme_assets.ThemeAssetStore(paths.theme_assets_dir())
    try:
        rendered = theme_scene.render_scene(theme_id, themes_root=root, store=store)
    except Exception as exc:
        return {
            "state": "failed",
            "scene": None,
            "diagnostic": str(getattr(exc, "detail", "A cena XML não pôde ser compilada."))[:240],
        }
    scene = rendered.get("scene")
    if not isinstance(scene, Mapping) or not isinstance(scene.get("views"), list):
        return {
            "state": "failed",
            "scene": None,
            "diagnostic": "O compilador não publicou uma cena XML utilizável.",
        }
    assets = rendered.get("assets")
    includes = rendered.get("includes")
    unresolved = bool(
        (isinstance(assets, Mapping) and assets.get("missing"))
        or (
            isinstance(includes, Mapping)
            and (includes.get("missing") or includes.get("unresolved") or includes.get("refused"))
        )
    )
    return {
        "state": "degraded" if unresolved else "resolved",
        "scene": dict(scene),
        "diagnostic": (
            "A cena XML foi compilada com referências ausentes; "
            "o renderizador preservará o fallback."
            if unresolved
            else ""
        ),
    }


def _read_library_payload(
    path: Path | None,
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any] | None]:
    """Lê o acervo, achando-o sozinho quando ninguém disse onde está.

    Quem abre o Launcher pelo entry point não passa ``--library``, e sem isso a
    home abria vazia mesmo com a biblioteca canônica cheia. O argumento continua
    valendo para apontar outro arquivo; a ausência dele deixou de significar
    "sem acervo".

    Aceita as duas formas: a lista crua que o argumento sempre aceitou, e o
    envelope ``{"games": [...]}`` que a varredura publica. Sem isso, apontar
    ``--library`` para a propria biblioteca canônica devolvia vazio.
    """
    source = path if path is not None else canonical_library_path()
    try:
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return [], None
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_LIBRARY_BYTES:
            return [], None
        encoded = stream.read(_MAX_LIBRARY_BYTES + 1)
    if len(encoded) > _MAX_LIBRARY_BYTES:
        return [], None
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return [], None
    # An empty object marks a valid raw-list source for the availability read
    # model without pretending that it supplied scan counters.
    envelope = payload if isinstance(payload, Mapping) else {}
    if isinstance(payload, Mapping):
        payload = payload.get("games")
    if not isinstance(payload, list):
        return [], None
    return [item for item in payload if isinstance(item, Mapping)], envelope


def _read_library(path: Path | None) -> list[Mapping[str, Any]]:
    return _read_library_payload(path)[0]


def _context_path() -> Path:
    return paths.state_home() / "launcher" / "return.json"


def _configure_isolated_xdg(root: Path) -> Path:
    """Point every mutable/readable XDG surface at an explicit synthetic root."""
    candidate = Path(root).expanduser()
    if candidate.is_symlink():
        raise ValueError("a raiz isolada não pode ser link simbólico")
    home = Path.home().resolve()
    prospective = candidate.resolve(strict=False)
    if prospective == home or home in prospective.parents:
        raise ValueError("a raiz isolada precisa ficar fora do diretório pessoal")
    if not candidate.exists():
        fs.ensure_dir(candidate, mode=0o700)
    resolved = candidate.resolve(strict=True)
    if resolved == home or home in resolved.parents:
        raise ValueError("a raiz isolada precisa ficar fora do diretório pessoal")
    root_mode = stat.S_IMODE(resolved.stat().st_mode)
    if root_mode & 0o077:
        raise ValueError("a raiz isolada precisa ter permissões privadas (0700)")

    for variable, name in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_RUNTIME_DIR", "runtime"),
    ):
        directory = resolved / name
        if directory.is_symlink():
            raise ValueError(f"{name} isolado não pode ser link simbólico")
        try:
            fs.ensure_private_child(resolved, name, mode=0o700)
        except OSError as exc:
            raise ValueError(
                f"{name} isolado precisa ser um diretório privado (0700) sem links"
            ) from exc
        os.environ[variable] = str(directory)
    return resolved


class LaunchRouter:
    """Decide a rota de lançamento de cada jogo e delega o spawn ao adapter.

    A home do Launcher é da biblioteca canônica de emulação, então cada item é
    lançado pela rota de produto ``emulation launch --game-id``. A rota por tipo
    de jogo é uma discriminação futura (Steam AppID → wrapper Steam), feita aqui
    pelo ``kind`` do registro — nunca pela mesma chamada genérica.
    """

    def __init__(
        self,
        *,
        on_spawn: Spawn,
        context_path: Path,
        executable: Callable[[], str] | None = None,
        kinds: Mapping[str, str] | None = None,
        steam_executable: Callable[[], str | None] | None = None,
        receipt_spawner: ReceiptSpawner | None = None,
    ) -> None:
        self._spawn = on_spawn
        self._context_path = Path(context_path)
        self._executable = executable or _steamzero_executable
        self._kinds = dict(kinds or {})
        self._steam_executable = steam_executable or _steam_executable
        self._receipt_spawner = receipt_spawner or spawn_receipt

    def launch(self, game_id: str, focus_id: str = "") -> LaunchAttempt | None:
        """Lança o jogo e devolve a tentativa com recibo capturável.

        Cada pedido tem um requestId próprio: correlacionar resposta a pedido é
        o que impede uma tentativa antiga de liberar ou encerrar uma nova. A
        rota Steam devolve ``None`` — ``steam://rungameid`` não produz recibo
        JSON e o encerramento do cliente Steam não é o encerramento do jogo; o
        contrato de confirmação é da rota de emulação.
        """
        request_id = ids.new_ulid()
        if self._kinds.get(game_id) == "steam":
            plan = LaunchPlan(
                game_id=game_id,
                argv=self._steam_argv(game_id),
                focus_id=focus_id or f"{_DEFAULT_SECTION}:{game_id}",
                context_path=self._context_path,
            )
            launch_detached(plan, spawn=self._spawn)
            return None
        executable = self._executable()
        # ``--json`` é o que o adapter de recibo consome: uma linha de
        # envelope no stdout, aceita ou notStarted, sem saída humana.
        argv = (executable, "emulation", "launch", "--game-id", game_id, "--json")
        plan = LaunchPlan(
            game_id=game_id,
            argv=argv,
            focus_id=focus_id or f"{_DEFAULT_SECTION}:{game_id}",
            context_path=self._context_path,
        )
        collected: list[LaunchAttempt] = []

        def _receipt_spawn(spawn_argv: tuple[str, ...]) -> int:
            attempt = self._receipt_spawner(spawn_argv, request_id=request_id, game_id=game_id)
            collected.append(attempt)
            return attempt.pid

        launch_detached(plan, spawn=_receipt_spawn)
        return collected[0] if collected else None

    def _steam_argv(self, app_id: str) -> tuple[str, ...]:
        if not app_id.isdigit() or len(app_id) > 32:
            raise SteamZeroError("E-API-SCHEMA", detail="AppID Steam inválido")
        executable = self._steam_executable()
        if executable is None:
            raise SteamZeroError("E-COMPONENT-DEGRADED", detail="cliente Steam não encontrado")
        return (executable, f"steam://rungameid/{app_id}")


def _steam_executable() -> str | None:
    return shutil.which("steam")


def _steam_catalog() -> tuple[CatalogGame, ...]:
    """Lê o acervo Steam sem impedir a home quando a leitura degrada."""
    try:
        from steamzero.adapters.launcher_steam import steam_catalog_games

        return steam_catalog_games()
    except Exception:
        return ()


def _steamzero_executable() -> str:
    """Caminho absoluto do `steamzero` para lançar o jogo desacoplado.

    O processo nasce em sessão própria (`start_new_session`) e pode não herdar
    o PATH do launcher. ``shutil.which`` resolve o binário publicado; a falha
    em encontrá-lo é uma falha de integração (o instalador publica
    ``/usr/local/bin/steamzero``) e aparece como erro do spawn, que o
    ``launch_detached`` converte em contexto limpo + exceção — nunca sucesso
    vazio.
    """
    resolved = None
    for candidate in ("/usr/local/bin/steamzero", "/usr/bin/steamzero", "steamzero"):
        path = candidate if "/" in candidate else shutil.which(candidate)
        if not path or not Path(path).is_file():
            continue
        resolved = str(Path(path).resolve())
        break
    if resolved is None:
        raise OSError("steamzero CLI não encontrado no PATH do launcher")
    return resolved


def _sections_from_catalog(catalog: Sequence[CatalogGame]) -> tuple[HomeSection, ...]:
    """Agrupa a home por plataforma, preservando a primeira ordem de chegada.

    A home fullscreen agrupa por sistema: sem isso uma seção única com o acervo
    inteiro tornaria a navegação por controle impraticável. Um jogo cuja
    plataforma não tem seção conhecida cai em ``outros``.
    """
    grouped: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for game in catalog:
        section = game.platform or "outros"
        section_title = game.platform_label or _platform_label(section)
        try:
            HomeSection(id=section, title=section_title, items=(game.id,))
        except ValueError:
            # A recusa pode ser da seção OU do item, e a mensagem não era
            # consultada. Reagir sempre como se fosse a seção fazia a segunda
            # tentativa levantar de novo quando o id do jogo é que estava fora
            # do contrato — e, por estar fora do try, ela derrubava a home
            # inteira por causa de um registro. Aqui a distinção é explícita:
            # seção ruim tem fallback, item ruim descarta só aquele jogo, como
            # build_sections já fazia.
            try:
                HomeSection(id="outros", title="outros", items=(game.id,))
            except ValueError:
                continue
            section = "outros"
        grouped.setdefault(section, []).append(game.id)
        # The first catalog item is authoritative for the section label. Steam
        # and imported records may not carry a manifest label, so later items
        # must not overwrite a resolved human name with a technical id.
        labels.setdefault(section, section_title)
    return tuple(
        HomeSection(
            id=name,
            title=_SECTION_TITLES.get(name, labels.get(name, name)),
            items=tuple(items),
        )
        for name, items in grouped.items()
    )


def _search_catalog_records(
    catalog: Sequence[CatalogGame], library: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], ...]:
    """Join canonical catalog identity with source scope for bridge search."""
    source_by_id = {str(record.get("id")): record for record in library if record.get("id")}
    records: list[dict[str, Any]] = []
    for game in catalog:
        record = dict(source_by_id.get(game.id, {}))
        record.update(
            {
                "id": game.id,
                "title": game.title,
                "platform": game.platform,
                "platformLabel": game.platform_label,
                "titleVariants": list(game.title_variants),
            }
        )
        record.setdefault("platformId", game.platform)
        record.setdefault("systemId", record.get("system") or game.platform)
        record.setdefault("system", record.get("systemId") or game.platform)
        if game.cover_url:
            record.setdefault("coverUrl", game.cover_url)
        records.append(record)
    return tuple(records)


def _sections_from_collections(catalog: Sequence[CatalogGame]) -> tuple[HomeSection, ...]:
    """Adiciona uma seção por coleção persistida, com os membros jogáveis.

    Usa o `CollectionManager` do domínio para resolver as regras (tag/favorite)
    — o Launcher não reimplementa a lógica de coleção. Só entram coleções com
    pelo menos um membro presente no acervo; uma coleção vazia não viraria
    uma seção sem jogos na home.
    """
    from steamzero.domain.collections import CollectionManager

    # O gameRef da coleção usa o prefixo `emulation:` (contrato do domínio);
    # o id do Launcher é o id canônico da biblioteca sem o prefixo.
    games = [{"gameRef": f"emulation:{game.id}"} for game in catalog]
    try:
        state = CollectionManager().state(games)
    except Exception:
        return ()
    sections: list[HomeSection] = []
    for collection in state.get("collections", []):
        title = str(collection.get("name") or "")
        members = tuple(
            str(member).removeprefix("emulation:")
            for member in collection.get("members", [])
            if str(member).startswith("emulation:")
        )
        if not title or not members:
            continue
        try:
            sections.append(
                HomeSection(
                    id=f"collection-{collection.get('id', '')}",
                    title=title,
                    items=members,
                )
            )
        except ValueError:
            continue
    return tuple(sections)


def _host_accessibility() -> dict[str, Any]:
    """Herda as preferências de acessibilidade do host (sem mutar nada).

    Usa as MESMAS probes do dashboard desktop, para que o Launcher respeite o
    alto contraste e a redução de movimento que o usuário já configurou no
    Plasma. Em ambiente sem `kreadconfig6` (ex.: sessão sem Plasma) degrada
    para os padrões — nunca quebra o lançamento.
    """
    from steamzero.adapters.desktop_kde import (
        high_contrast_enabled,
        host_text_scale,
        reduced_motion_enabled,
    )

    return {
        "highContrast": high_contrast_enabled(),
        "reducedMotion": reduced_motion_enabled(),
        "visualScale": host_text_scale(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=None)
    parser.add_argument(
        "--isolated-library",
        action="store_true",
        help="usa somente --library, XDG sintético e desativa lançamentos",
    )
    parser.add_argument(
        "--isolated-root",
        type=Path,
        default=None,
        help="raiz privada fora de HOME para config/data/state/cache/runtime sintéticos",
    )
    parser.add_argument("--context", type=Path, default=None)
    parser.add_argument(
        "--title-mode",
        choices=TITLE_VARIANT_MODES,
        default="full",
        help="forma do nome exibida no launcher (as variantes também são publicadas)",
    )
    args = parser.parse_args(argv)
    if args.isolated_library and args.library is None:
        parser.error("--isolated-library exige um arquivo --library explícito")
    if args.isolated_library and args.isolated_root is None:
        parser.error("--isolated-library exige --isolated-root fora do diretório pessoal")
    if not args.isolated_library and args.isolated_root is not None:
        parser.error("--isolated-root só pode ser usado com --isolated-library")
    if args.isolated_library:
        try:
            isolated_root = _configure_isolated_xdg(args.isolated_root)
        except (OSError, ValueError) as exc:
            parser.error(f"raiz isolada indisponível: {exc}")
        if args.context is not None:
            context_candidate = args.context.expanduser()
            if context_candidate.is_symlink():
                parser.error("--context isolado não pode ser link simbólico")
            state_root = (isolated_root / "state").resolve()
            resolved_context = context_candidate.resolve(strict=False)
            if state_root not in resolved_context.parents:
                parser.error("--context precisa ficar dentro do XDG_STATE_HOME isolado")

    from steamzero.adapters.launcher_process import spawn_detached
    from steamzero.adapters.launcher_ui import LauncherBridge, launch_launcher_ui

    context_path = args.context or _context_path()
    # Um contexto pendente significa que a sessão anterior lançou algo. Consumir
    # aqui evita que um retorno antigo posicione o foco de uma sessão nova.
    restored_context = consume_context(context_path)
    return_context = restored_context if isinstance(restored_context, Mapping) else None

    library, payload = _read_library_payload(args.library)
    emulation = catalog_games(library)
    steam = () if args.isolated_library else _steam_catalog()
    catalog = (*emulation, *steam)
    sections = _sections_from_catalog(catalog) + _sections_from_collections(emulation)
    titles = {game.id: game.title for game in catalog}
    covers = {game.id: game.cover_url for game in catalog if game.cover_url}

    router = LaunchRouter(
        on_spawn=spawn_detached,
        context_path=context_path,
        kinds={game.id: game.kind for game in catalog},
    )

    def launch_game(game_id: str, focus_id: str) -> LaunchAttempt | None:
        if args.isolated_library:
            raise SteamZeroError(
                "E-API-UNKNOWN-ACTION",
                detail="lançamento não publicado no modo de catálogo isolado",
            )
        return router.launch(game_id, focus_id)

    accessibility = (
        {"highContrast": False, "reducedMotion": False, "visualScale": 1.0}
        if args.isolated_library
        else _host_accessibility()
    )
    from steamzero.adapters.session_overlay import SessionOverlayAdapter
    from steamzero.launcher.cinema import cinema_metadata

    if args.isolated_library:
        observe_session = None
        session_overlay = None
    else:
        from steamzero.adapters.launcher_session import observe_game_session
        from steamzero.adapters.session_control import resolve_remote_session_control

        def observe_session(game_id: str) -> dict[str, Any]:
            return observe_game_session(paths.state_db(), game_id)

        session_overlay = SessionOverlayAdapter(
            observe=observe_session,
            resolve_control=lambda session_id, game_id: cast(
                Any,
                resolve_remote_session_control(session_id, game_id, observe=observe_session),
            ),
        )

    metadata = {}
    registry_media = launcher_media_metadata(
        media_root=paths.media_dir(),
        platform_by_game={game.id: game.platform for game in catalog},
    )
    for record in library:
        game_id = record.get("id")
        if not game_id:
            continue
        projected = cinema_metadata(record)
        projected.update(registry_media.get(str(game_id), {}))
        metadata[str(game_id)] = projected
        if not covers.get(str(game_id)):
            cover_url = projected.get("coverUrl")
            if isinstance(cover_url, str) and cover_url:
                covers[str(game_id)] = cover_url

    catalog_records = _search_catalog_records(catalog, library)
    kind_by_game_id = {game.id: game.kind for game in catalog}
    journey_rows = []
    for record in catalog_records:
        game_id = str(record.get("id", ""))
        row = project_game_row(
            dict(record),
            source="steam" if kind_by_game_id.get(game_id) == "steam" else "emulation",
        )
        if row is not None:
            journey_rows.append(row)
    platform_rows_by_id: dict[str, dict[str, Any]] = {}
    for game in catalog:
        platform_id = game.platform or "outros"
        platform_row = platform_rows_by_id.setdefault(
            platform_id,
            {
                "id": platform_id,
                "name": game.platform_label or _platform_label(platform_id),
                "shortName": game.platform_label or _platform_label(platform_id),
                "state": "available",
                "gameCount": 0,
            },
        )
        platform_row["gameCount"] += 1
    published_journey_models = {
        "library.games": journey_public_field_types(),
        "library.platforms": {
            "id": "string",
            "name": "string",
            "shortName": "string",
            "state": "string",
            "gameCount": "integer",
        },
    }
    source_available = payload is not None or bool(library) or bool(steam)
    journey_read_models = {
        "library.games": journey_rows if source_available else None,
        "library.platforms": list(platform_rows_by_id.values()) if source_available else None,
    }
    journey_states = {
        "library.games": "available" if source_available else "unavailable",
        "library.platforms": "available" if source_available else "unavailable",
    }
    journey_runtime = None
    journey_diagnostic: dict[str, str] = {
        "code": "JOURNEY-NOT-ACTIVE",
        "message": "Nenhuma Jornada foi ativada; a Home AURA continua disponível.",
        "recoveryAction": "activate-in-studio",
    }
    try:
        from steamzero.adapters.theme_catalog import ThemeCatalog
        from steamzero.core import paths as core_paths
        from steamzero.domain.experience_journey import JourneyStore
        from steamzero.domain.theme_effects import PerformanceTier

        journey_store = JourneyStore(core_paths.data_home() / "journeys")
        active_journey_id = journey_store.active_id()
        if active_journey_id is not None:
            document = journey_store.load(active_journey_id)
            theme_catalog = ThemeCatalog()
            theme_entries = {str(item.get("id")): item for item in theme_catalog.list_catalog()}
            resolved_themes: dict[str, dict[str, Any]] = {}

            def resolve_journey_theme(_menu_id: str, appearance: object) -> Mapping[str, Any]:
                requested_theme_id = (
                    str(appearance.get("themeId"))
                    if isinstance(appearance, Mapping)
                    and appearance.get("mode") == "custom"
                    and isinstance(appearance.get("themeId"), str)
                    else "org.steamzero.default"
                )
                if requested_theme_id not in resolved_themes:
                    resolved = theme_catalog.resolve(
                        requested_theme_id,
                        performance_tier=PerformanceTier.BALANCED,
                        high_contrast=bool(accessibility.get("highContrast", False)),
                        reduced_motion=bool(accessibility.get("reducedMotion", False)),
                    )
                    theme = resolved.to_theme_qml_object()
                    entry = theme_entries.get(requested_theme_id, {})
                    entry_state = str(entry.get("state", ""))
                    resolution_state = (
                        "resolved"
                        if resolved.id == requested_theme_id
                        else "invalid"
                        if entry_state == "invalid"
                        else "incompatible"
                        if entry_state == "incompatible"
                        else "missing-reference"
                    )
                    theme["requestedThemeId"] = requested_theme_id
                    theme["resolutionState"] = resolution_state
                    theme["resolutionDiagnostic"] = (
                        ""
                        if resolution_state == "resolved"
                        else str(
                            entry.get("error")
                            or (
                                "Tema ausente, inválido ou incompatível; "
                                "a composição nativa usa AURA."
                            )
                        )[:240]
                    )
                    xml_scene = _render_journey_xml_scene(requested_theme_id)
                    theme["sceneResolutionState"] = xml_scene["state"]
                    theme["sceneDiagnostic"] = xml_scene["diagnostic"]
                    if xml_scene["scene"] is not None:
                        theme["compiledScene"] = xml_scene["scene"]
                    resolved_themes[requested_theme_id] = theme
                return resolved_themes[requested_theme_id]

            journey_runtime = JourneyRuntime(
                document,
                read_models=journey_read_models,
                published_read_models=published_journey_models,
                source_states=journey_states,
                launchable_game_ids=(
                    [] if args.isolated_library else [game.id for game in catalog]
                ),
                theme_resolver=resolve_journey_theme,
            )
            journey_diagnostic = {}
    except Exception:
        # A damaged active package never blocks the user's existing Home.
        journey_runtime = None
        journey_diagnostic = {
            "code": "JOURNEY-ACTIVE-PACKAGE-UNAVAILABLE",
            "message": (
                "A Jornada ativa não pôde ser carregada. A Home AURA continua disponível; "
                "reabra o Studio para revisar o documento."
            ),
            "recoveryAction": "review-active-journey",
        }

    bridge = LauncherBridge(
        sections=sections,
        titles=titles,
        title_variants={game.id: game.title_variants for game in catalog},
        title_mode=args.title_mode,
        covers=covers,
        catalog_records=catalog_records,
        metadata=metadata,
        session_observer=observe_session,
        session_overlay=session_overlay,
        context_path=context_path,
        on_launch=launch_game,
        accessibility=accessibility,
        return_context=return_context,
        catalog_summary=catalog_summary(payload, catalog, library),
        journey_runtime=journey_runtime,
        journey_diagnostic=journey_diagnostic,
    )
    return launch_launcher_ui(bridge)


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())

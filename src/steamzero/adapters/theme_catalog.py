from __future__ import annotations

import contextlib
import hashlib
import importlib.resources
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from steamzero.core.errors import SteamZeroError
from steamzero.domain.asset_recipes import validate_asset_source, validate_retroarch_bezel_source
from steamzero.domain.theme_effects import PerformanceTier
from steamzero.domain.themes import (
    THEME_API_VERSION,
    THEME_DEFAULT_ID,
    ResolvedTheme,
    ThemeManifest,
    ThemeResolver,
)

_THEME_PACKAGE = "steamzero.themes"
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_VALIDATION_DETAIL = 400
_MAX_FILES = 128
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_ASSET_BYTES = 16 * 1024 * 1024
_MAX_ASSET_DIMENSION = 8192
_MAX_DIR_DEPTH = 4
_MAX_THEMES = 100
_MAX_BEZEL_BYTES = 16 * 1024 * 1024
_BEZEL_THEME_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")
_BEZEL_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_ALLOWED_RASTER = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_ALLOWED_SVG_EXT = ".svg"
_PROHIBITED_FILES = frozenset(
    {
        ".qml",
        ".js",
        ".py",
        ".so",
        ".wasm",
        ".wasm64",
        ".html",
        ".htm",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
    }
)


@dataclass(frozen=True)
class BezelResource:
    """Validated public identity for one theme-owned bezel asset."""

    id: str
    resource_id: str
    asset_url: str
    label: str
    origin: str
    theme_id: str
    version: str
    license: str
    format: str
    size: int
    available: bool
    compatible: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resourceId": self.resource_id,
            "assetUrl": self.asset_url,
            "label": self.label,
            "origin": self.origin,
            "themeId": self.theme_id,
            "version": self.version,
            "license": self.license,
            "format": self.format,
            "size": self.size,
            "available": self.available,
            "compatible": self.compatible,
            "adapterId": "retroarch-flatpak",
            "applyMode": "next-launch",
            "reason": self.reason,
        }


def _load_manifest_schema() -> dict[str, Any]:
    schemas = importlib.resources.files("steamzero.schemas")
    ref = schemas.joinpath("theme-manifest-v1.schema.json")
    with importlib.resources.as_file(ref) as path:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    # ``jsonschema.validate`` não recebe o registry multi-arquivo usado pela API.
    # Injetar o schema empacotado preserva a mesma validação sem buscar a rede.
    asset_schemas = []
    for name in ("asset-recipe-v1.schema.json", "asset-recipe-v2.schema.json"):
        asset_ref = schemas.joinpath(name)
        with importlib.resources.as_file(asset_ref) as path:
            asset_schemas.append(json.loads(path.read_text(encoding="utf-8")))
    loaded["properties"]["assetRecipes"] = {"oneOf": asset_schemas}
    layout_ref = schemas.joinpath("scene-layout-v1.schema.json")
    with importlib.resources.as_file(layout_ref) as path:
        loaded["properties"]["sceneLayouts"] = json.loads(path.read_text(encoding="utf-8"))
    palette_ref = schemas.joinpath("dynamic-palette-v1.schema.json")
    with importlib.resources.as_file(palette_ref) as path:
        loaded["properties"]["dynamicPalette"] = json.loads(path.read_text(encoding="utf-8"))
    glass_ref = schemas.joinpath("glass-panel-v1.schema.json")
    with importlib.resources.as_file(glass_ref) as path:
        loaded["properties"]["glass"] = json.loads(path.read_text(encoding="utf-8"))
    motion_ref = schemas.joinpath("scene-motion-v1.schema.json")
    with importlib.resources.as_file(motion_ref) as path:
        loaded["properties"]["sceneMotion"] = json.loads(path.read_text(encoding="utf-8"))
    surface_ref = schemas.joinpath("scene-surfaces-v1.schema.json")
    with importlib.resources.as_file(surface_ref) as path:
        loaded["properties"]["sceneSurfaces"] = json.loads(path.read_text(encoding="utf-8"))
    container_ref = schemas.joinpath("scene-containers-v1.schema.json")
    with importlib.resources.as_file(container_ref) as path:
        loaded["properties"]["sceneContainers"] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


_MANIFEST_SCHEMA = _load_manifest_schema()


def list_builtin_theme_ids() -> list[str]:
    """Lista IDs de temas builtin empacotados via importlib.resources."""
    ref: object = importlib.resources.files(_THEME_PACKAGE)
    ids: list[str] = []
    if not _is_resource_dir(ref):
        return ids
    for entry in _iter_resource(ref):
        if _is_resource_dir(entry) and _resource_has(entry, "theme.json"):
            ids.append(_resource_name(entry))
    return sorted(ids)


def _is_resource_dir(ref: object) -> bool:
    try:
        if hasattr(ref, "is_dir") and callable(ref.is_dir):
            return bool(ref.is_dir())
        return False
    except Exception:
        return False


def _iter_resource(ref: object) -> list[object]:
    with contextlib.suppress(Exception):
        if hasattr(ref, "iterdir") and callable(ref.iterdir):
            return list(ref.iterdir())
    return []


def _resource_has(ref: object, name: str) -> bool:
    with contextlib.suppress(Exception):
        if hasattr(ref, "joinpath") and callable(ref.joinpath):
            child = ref.joinpath(name)
            if hasattr(child, "exists") and callable(child.exists):
                return bool(child.exists())
    return False


def _resource_name(ref: object) -> str:
    with contextlib.suppress(Exception):
        if hasattr(ref, "name"):
            return str(ref.name)
    return ""


def read_builtin_manifest(theme_id: str) -> ThemeManifest:
    """Lê e valida o manifesto de um tema builtin."""
    ref = importlib.resources.files(_THEME_PACKAGE).joinpath(theme_id, "theme.json")
    try:
        with importlib.resources.as_file(ref) as path:
            raw = json.loads(path.read_bytes())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SteamZeroError("E-THEME-MANIFEST", detail=str(exc)) from exc
    _validate_manifest(raw)
    return ThemeManifest.from_dict(raw)


def validate_source_path(source_path: str) -> Path:
    """Valida que source_path é um diretório local acessível."""
    path = Path(source_path).resolve()
    if not path.is_dir():
        raise SteamZeroError("E-THEME-MANIFEST", detail=f"origem não encontrada: {source_path}")
    return path


def read_user_manifest_from(source_path: Path) -> ThemeManifest:
    """Lê e valida o manifesto de um pacote de tema do usuário."""
    manifest_path = source_path / "theme.json"
    if not manifest_path.is_file():
        raise SteamZeroError("E-THEME-MANIFEST", detail="theme.json ausente no pacote")
    try:
        raw = json.loads(manifest_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise SteamZeroError("E-THEME-MANIFEST", detail=str(exc)) from exc
    _validate_manifest(raw)
    return ThemeManifest.from_dict(raw)


@cache
def _manifest_validator() -> Draft202012Validator:
    """Validador do manifesto de tema, compilado uma vez por processo.

    ``jsonschema.validate`` recheca o proprio schema empacotado a cada chamada:
    medido em 305 ms por manifesto na ponte do produto, o que dominava o bloco
    ``theme`` do /status (4,1 s de 8,9 s na baseline RC-01). Validar o schema
    que nos empacotamos nao e a checagem de seguranca do lote; a validacao da
    instancia do manifesto permanece identica, inclusive a primeira ordem de
    erro e a mensagem.
    """
    return Draft202012Validator(_MANIFEST_SCHEMA)


def _validation_detail(exc: jsonschema.ValidationError) -> str:
    """Descrição curta e estável da falha: caminho JSON + mensagem, sem despejo.

    ``str(exc)`` faz pprint do schema *e* da instância. Com quatro pacotes ES-DE
    malformados no diretório de temas do host, isso custava 1,2 s de CPU por
    composição do ``theme`` no /status, e o ``theme.list`` publicava os 1,1 MB
    resultantes na UI do Estúdio de Temas, onde ninguém consegue ler um dump de
    schema. O caminho e a mensagem preservam o diagnóstico.
    """
    return f"{exc.json_path}: {exc.message}"[:_MAX_VALIDATION_DETAIL]


def _validate_manifest(raw: dict[str, Any]) -> None:
    try:
        _manifest_validator().validate(raw)
    except jsonschema.ValidationError as exc:
        raise SteamZeroError("E-THEME-MANIFEST", detail=_validation_detail(exc)) from exc
    api = raw.get("compatibility", {}).get("themeApi", 0)
    if api != THEME_API_VERSION:
        raise SteamZeroError(
            "E-THEME-INCOMPATIBLE", detail=f"tema requer themeApi={api}, atual={THEME_API_VERSION}"
        )


def _check_path_safety(directory: Path) -> None:
    resolved_root = directory.resolve()
    depth = 0
    for entry in sorted(directory.rglob("*"), key=lambda p: str(p)):
        if not entry.exists():
            continue
        depth = len(entry.relative_to(directory).parts)
        if depth > _MAX_DIR_DEPTH:
            raise SteamZeroError(
                "E-THEME-LIMIT", detail=f"profundidade excedida: {depth} > {_MAX_DIR_DEPTH}"
            )
        try:
            resolved = entry.resolve()
        except OSError as exc:
            raise SteamZeroError("E-THEME-UNSAFE", detail=str(exc)) from exc
        if resolved_root not in resolved.parents and resolved != resolved_root:
            raise SteamZeroError("E-THEME-UNSAFE", detail=f"caminho fora da raiz: {entry}")
        if entry.is_symlink():
            raise SteamZeroError("E-THEME-UNSAFE", detail=f"symlink não permitido: {entry}")
        if entry.is_socket() or entry.is_fifo():
            raise SteamZeroError(
                "E-THEME-UNSAFE", detail=f"arquivo especial não permitido: {entry}"
            )
        if entry.is_block_device() or entry.is_char_device():
            raise SteamZeroError(
                "E-THEME-UNSAFE", detail=f"arquivo especial não permitido: {entry}"
            )


def _check_file_limits(directory: Path) -> tuple[int, int]:
    total_bytes = 0
    file_count = 0
    for entry in sorted(directory.rglob("*"), key=lambda p: str(p)):
        if not entry.is_file():
            continue
        file_count += 1
        if file_count > _MAX_FILES:
            raise SteamZeroError(
                "E-THEME-LIMIT", detail=f"número de arquivos excedido: {file_count}"
            )
        size = entry.stat().st_size
        total_bytes += size
        if total_bytes > _MAX_TOTAL_BYTES:
            raise SteamZeroError("E-THEME-LIMIT", detail=f"tamanho total excedido: {total_bytes}")
        ext = entry.suffix.lower()
        if ext in _PROHIBITED_FILES:
            raise SteamZeroError("E-THEME-UNSAFE", detail=f"tipo de arquivo proibido: {ext}")
        if ext in _ALLOWED_RASTER | {_ALLOWED_SVG_EXT} and size > _MAX_ASSET_BYTES:
            raise SteamZeroError(
                "E-THEME-LIMIT", detail=f"asset muito grande: {entry.name} ({size} bytes)"
            )
        if ext == _ALLOWED_SVG_EXT:
            try:
                validate_asset_source(entry.read_bytes())
            except (OSError, ValueError) as exc:
                raise SteamZeroError("E-THEME-UNSAFE", detail=f"{entry.name}: {exc}") from exc
    return file_count, total_bytes


def _check_manifest_limits(raw: dict[str, Any]) -> None:
    serialized = json.dumps(raw)
    if len(serialized.encode()) > _MAX_MANIFEST_BYTES:
        raise SteamZeroError("E-THEME-LIMIT", detail="manifesto excede 256 KiB")
    extends = raw.get("extends")
    if extends is not None and not isinstance(extends, str):
        raise SteamZeroError("E-THEME-MANIFEST", detail="extends precisa ser string")


def validate_theme_directory(directory: Path) -> ThemeManifest:
    """Valida um diretório de tema. Levanta SteamZeroError se inválido."""
    _check_path_safety(directory)
    manifest = read_user_manifest_from(directory)
    _check_manifest_limits(manifest.to_dict())
    _check_file_limits(directory)
    theme_id = manifest.id
    if directory.name != theme_id:
        raise SteamZeroError(
            "E-THEME-MANIFEST",
            detail=f"nome do diretório ({directory.name}) difere do id ({theme_id})",
        )
    return manifest


class ThemeCatalog:
    """Catálogo que descobre temas builtin e do usuário."""

    def __init__(self, user_themes_dir: Path | None = None) -> None:
        from steamzero.core import paths

        self._user_themes_dir = user_themes_dir or paths.themes_dir()

    def list_catalog(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tid in list_builtin_theme_ids():
            try:
                manifest = read_builtin_manifest(tid)
                seen.add(tid)
                entries.append(
                    {
                        "id": tid,
                        "name": manifest.name,
                        "version": manifest.version,
                        "author": manifest.author,
                        "license": manifest.license,
                        "state": "available",
                        "origin": "builtin",
                        "compatible": True,
                    }
                )
            except SteamZeroError as exc:
                entries.append(
                    {
                        "id": tid,
                        "name": tid,
                        "version": "",
                        "author": "",
                        "license": "",
                        "state": "invalid",
                        "origin": "builtin",
                        "compatible": False,
                        "error": exc.detail,
                    }
                )
        if self._user_themes_dir is not None and self._user_themes_dir.is_dir():
            for entry in sorted(self._user_themes_dir.iterdir(), key=str):
                if not entry.is_dir():
                    continue
                tid = entry.name
                if tid in seen:
                    continue
                try:
                    manifest = validate_theme_directory(entry)
                    seen.add(tid)
                    api = manifest.compatibility.get("themeApi", 0)
                    compatible = api == THEME_API_VERSION
                    entries.append(
                        {
                            "id": tid,
                            "name": manifest.name,
                            "version": manifest.version,
                            "author": manifest.author,
                            "license": manifest.license,
                            "state": "available" if compatible else "incompatible",
                            "origin": "user",
                            "compatible": compatible,
                        }
                    )
                except SteamZeroError as exc:
                    entries.append(
                        {
                            "id": tid,
                            "name": tid,
                            "version": "",
                            "author": "",
                            "license": "",
                            "state": "invalid",
                            "origin": "user",
                            "compatible": False,
                            "error": exc.detail,
                        }
                    )
        return entries

    def resolve(
        self,
        theme_id: str,
        *,
        effect_capabilities: frozenset[str] | None = None,
        performance_tier: PerformanceTier | None = None,
        high_contrast: bool = False,
        reduced_motion: bool = False,
    ) -> ResolvedTheme:
        manifests: dict[str, ThemeManifest] = {}
        for tid in list_builtin_theme_ids():
            with contextlib.suppress(SteamZeroError):
                manifests[tid] = read_builtin_manifest(tid)
        if self._user_themes_dir is not None and self._user_themes_dir.is_dir():
            for entry in self._user_themes_dir.iterdir():
                if not entry.is_dir():
                    continue
                tid = entry.name
                with contextlib.suppress(SteamZeroError):
                    manifests[tid] = validate_theme_directory(entry)
        resolver = ThemeResolver(manifests)
        try:
            return resolver.resolve(
                theme_id,
                effect_capabilities=effect_capabilities,
                performance_tier=performance_tier,
                high_contrast=high_contrast,
                reduced_motion=reduced_motion,
            )
        except ValueError:
            if theme_id == THEME_DEFAULT_ID:
                raise
            # Pacote inválido, incompatível ou ausente não derruba a central:
            # o builtin seguro permanece o único consumidor visível.
            return resolver.resolve(
                THEME_DEFAULT_ID,
                effect_capabilities=effect_capabilities,
                performance_tier=performance_tier,
                high_contrast=high_contrast,
                reduced_motion=reduced_motion,
            )


_BEZEL_RESOURCE_URI = re.compile(
    r"^asset://bezels/(?P<theme>[a-z0-9]+(?:[.-][a-z0-9]+)+)@"
    r"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)-(?P<digest>[0-9a-f]{64})"
    r"(?P<suffix>\.[a-z0-9]+)$"
)


def _read_bounded_theme_asset(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("asset precisa ser um arquivo regular")
        if metadata.st_size <= 0 or metadata.st_size > _MAX_BEZEL_BYTES:
            raise ValueError("asset excede o limite de 16 MiB")
        data = stream.read(_MAX_BEZEL_BYTES + 1)
    if len(data) > _MAX_BEZEL_BYTES:
        raise ValueError("asset excede o limite de 16 MiB")
    return data


def _theme_bezel_path(theme_dir: Path, logical_path: str) -> Path:
    relative = PurePosixPath(logical_path)
    if (
        not logical_path.startswith("assets/")
        or relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or "\\" in logical_path
    ):
        raise ValueError("referência de bezel fora do namespace assets/")
    candidate = theme_dir.joinpath(*relative.parts)
    if candidate.is_symlink():
        raise ValueError("asset não pode ser link simbólico")
    resolved = candidate.resolve(strict=True)
    root = theme_dir.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("asset fora do pacote do tema")
    return candidate


def _unavailable_bezel(
    theme_id: str, label: str, version: str, license_id: str, reason: str
) -> BezelResource:
    safe_theme_id = theme_id if _BEZEL_THEME_ID.fullmatch(theme_id) else "unknown"
    version_label = version if _BEZEL_VERSION.fullmatch(version) else "unknown"
    safe_license = (
        license_id
        if re.fullmatch(r"(?:LicenseRef-[a-zA-Z0-9._-]+|[A-Za-z0-9._+-]+)", license_id)
        else "unknown"
    )
    identity = hashlib.sha256(f"{safe_theme_id}:{version_label}".encode()).hexdigest()[:20]
    return BezelResource(
        id=f"unavailable-{identity}",
        resource_id="",
        asset_url="",
        label=" ".join((label or safe_theme_id).split())[:128],
        origin="custom-theme",
        theme_id=safe_theme_id,
        version=version_label,
        license=safe_license[:128],
        format="unknown",
        size=0,
        available=False,
        compatible=False,
        reason=reason[:240],
    )


def _user_bezel_resources(user_themes_dir: Path | None) -> list[BezelResource]:
    if user_themes_dir is None or user_themes_dir.is_symlink() or not user_themes_dir.is_dir():
        return []
    resources: list[BezelResource] = []
    for entry in sorted(user_themes_dir.iterdir(), key=str):
        if entry.is_symlink() or not entry.is_dir():
            continue
        manifest_path = entry / "theme.json"
        try:
            if manifest_path.is_symlink() or not manifest_path.is_file():
                continue
            raw_bytes = manifest_path.read_bytes()
            if len(raw_bytes) > _MAX_MANIFEST_BYTES:
                continue
            raw = json.loads(raw_bytes)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        raw_assets = raw.get("assets")
        if not isinstance(raw_assets, dict) or "bezel" not in raw_assets:
            continue
        theme_id = str(raw.get("id") or entry.name)
        name = str(raw.get("name") or theme_id)
        version = str(raw.get("version") or "unknown")
        license_id = str(raw.get("license") or "unknown")
        compatibility = raw.get("compatibility")
        if (
            not _BEZEL_THEME_ID.fullmatch(theme_id)
            or not _BEZEL_VERSION.fullmatch(version)
            or not isinstance(compatibility, Mapping)
            or compatibility.get("themeApi") != THEME_API_VERSION
        ):
            resources.append(
                _unavailable_bezel(
                    theme_id,
                    name,
                    version,
                    license_id,
                    "O tema do bezel está ausente, inválido ou usa uma API incompatível.",
                )
            )
            continue
        try:
            manifest = validate_theme_directory(entry)
            logical_path = manifest.assets.get("bezel")
            if not isinstance(logical_path, str):
                raise ValueError("o manifesto não publica um asset de bezel")
            asset_path = _theme_bezel_path(entry, logical_path)
            data = _read_bounded_theme_asset(asset_path)
            suffix = asset_path.suffix.casefold()
            digest = hashlib.sha256(data).hexdigest()
            resource_id = f"asset://bezels/{manifest.id}@{manifest.version}-{digest}{suffix}"
            supported_format = suffix == ".png"
            reason = ""
            if supported_format:
                try:
                    validate_retroarch_bezel_source(data)
                except ValueError as exc:
                    supported_format = False
                    reason = str(exc)
            else:
                with contextlib.suppress(ValueError):
                    validate_asset_source(data)
                reason = "RetroArch Flatpak aceita bezel personalizado em PNG validado."
            resources.append(
                BezelResource(
                    id=resource_id,
                    resource_id=resource_id,
                    asset_url=resource_id,
                    label=manifest.name[:128],
                    origin="custom-theme",
                    theme_id=manifest.id,
                    version=manifest.version,
                    license=manifest.license,
                    format=suffix.removeprefix("."),
                    size=len(data),
                    available=supported_format,
                    compatible=supported_format,
                    reason=reason,
                )
            )
        except (OSError, ValueError, SteamZeroError):
            resources.append(
                _unavailable_bezel(
                    theme_id,
                    name,
                    version,
                    license_id,
                    "O asset do bezel não passou na validação do pacote e do formato.",
                )
            )
    return resources[:_MAX_THEMES]


def list_bezel_resources(user_themes_dir: Path | None = None) -> list[dict[str, Any]]:
    """List AURA and validated theme resources without publishing local paths."""
    if user_themes_dir is None:
        from steamzero.core import paths

        user_themes_dir = paths.themes_dir()
    manifest = read_builtin_manifest(THEME_DEFAULT_ID)
    asset_root = Path(__file__).resolve().parents[1] / "ui" / "assets"
    aura_path = asset_root / "aura-bezel.png"
    aura_data = _read_bounded_theme_asset(aura_path)
    validate_retroarch_bezel_source(aura_data)
    aura = BezelResource(
        id="aura-default",
        resource_id="aura-default",
        asset_url="asset://bezels/aura-bezel.svg",
        label="AURA Cinema",
        origin="aura",
        theme_id=manifest.id,
        version=manifest.version,
        license=manifest.license,
        format="png",
        size=len(aura_data),
        available=True,
        compatible=True,
        reason="",
    )
    return [aura.to_dict(), *(item.to_dict() for item in _user_bezel_resources(user_themes_dir))]


def resolve_bezel_resource(resource_id: str, user_themes_dir: Path | None = None) -> dict[str, Any]:
    """Resolve and revalidate one logical resource immediately before launch."""
    if user_themes_dir is None:
        from steamzero.core import paths

        user_themes_dir = paths.themes_dir()
    if resource_id == "aura-default":
        manifest = read_builtin_manifest(THEME_DEFAULT_ID)
        asset_path = Path(__file__).resolve().parents[1] / "ui" / "assets" / "aura-bezel.png"
        data = _read_bounded_theme_asset(asset_path)
        validate_retroarch_bezel_source(data)
        return {
            "id": "aura-default",
            "resourceId": "aura-default",
            "assetUrl": "asset://bezels/aura-bezel.svg",
            "label": "AURA Cinema",
            "origin": "aura",
            "themeId": manifest.id,
            "version": manifest.version,
            "license": manifest.license,
            "format": "png",
            "size": len(data),
            "available": True,
            "compatible": True,
            "adapterId": "retroarch-flatpak",
            "applyMode": "next-launch",
            "reason": "",
            "_sourceBytes": data,
        }
    match = _BEZEL_RESOURCE_URI.fullmatch(resource_id)
    if match is None or match.group("suffix") != ".png":
        raise SteamZeroError("E-THEME-UNSAFE", detail="URI lógico de bezel inválido")
    theme_id = match.group("theme")
    if not _BEZEL_THEME_ID.fullmatch(theme_id):
        raise SteamZeroError("E-THEME-UNSAFE", detail="namespace do bezel inválido")
    if user_themes_dir.is_symlink():
        raise SteamZeroError("E-THEME-UNSAFE", detail="raiz de temas não pode ser link simbólico")
    theme_dir = user_themes_dir / theme_id
    if theme_dir.is_symlink():
        raise SteamZeroError("E-THEME-UNSAFE", detail="pacote de tema não pode ser link simbólico")
    if not theme_dir.is_dir():
        raise SteamZeroError("E-THEME-NOT-FOUND", detail="o tema do bezel não está instalado")
    try:
        manifest = validate_theme_directory(theme_dir)
        if manifest.id != theme_id or manifest.version != match.group("version"):
            raise ValueError("a versão do tema mudou desde a seleção do bezel")
        logical_path = manifest.assets.get("bezel")
        if not isinstance(logical_path, str):
            raise ValueError("o tema não publica mais um asset de bezel")
        asset_path = _theme_bezel_path(theme_dir, logical_path)
        data = _read_bounded_theme_asset(asset_path)
        validate_retroarch_bezel_source(data)
        if hashlib.sha256(data).hexdigest() != match.group("digest"):
            raise ValueError("o conteúdo do bezel mudou desde a seleção")
    except FileNotFoundError as exc:
        raise SteamZeroError(
            "E-THEME-NOT-FOUND", detail="o asset do bezel selecionado não está instalado"
        ) from exc
    except (OSError, ValueError, SteamZeroError) as exc:
        detail = str(getattr(exc, "detail", "")) or str(exc)
        raise SteamZeroError("E-THEME-INCOMPATIBLE", detail=detail[:240]) from exc
    return {
        "id": resource_id,
        "resourceId": resource_id,
        "assetUrl": resource_id,
        "label": manifest.name,
        "origin": "custom-theme",
        "themeId": manifest.id,
        "version": manifest.version,
        "license": manifest.license,
        "format": "png",
        "size": len(data),
        "available": True,
        "compatible": True,
        "adapterId": "retroarch-flatpak",
        "applyMode": "next-launch",
        "reason": "",
        "_sourceBytes": data,
    }

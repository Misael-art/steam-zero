"""Contextual images must agree across the public preview and Launcher models."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from steamzero.adapters.desktop_ui import _project_journey_catalog
from steamzero.adapters.journey_public import game_record_public_field_types
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.core import paths
from steamzero.domain.media_pipeline import MediaPipeline
from steamzero.domain.media_registry import MediaMasterEntry, MediaRegistry, Provenance
from steamzero.domain.scene_layout import LayoutBounds, LayoutRecipeBook, resolve_scene_layouts


@pytest.fixture
def canonical_art(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Original CC0 artwork; real synthetic catalog identity, shared role references."""
    root = tmp_path / "media"
    stream = io.BytesIO()
    Image.new("RGBA", (24, 12), (220, 40, 20, 180)).save(stream, format="PNG")
    source = MediaPipeline(root).preserve_source(
        stream.getvalue(), "owned-context.png", Provenance("fixture", "owned", "CC0-1.0")
    )
    registry = MediaRegistry.load(root)
    registry.add_entry(
        MediaMasterEntry(
            "game-a",
            "title-a",
            "a" * 64,
            "Owned game A",
            platform_id="test-platform",
            masters={
                role: source.path
                for role in ("logo", "box2d", "fanart", "icon", "marquee", "screenshot")
            },
        )
    )
    registry.save(root)
    monkeypatch.setattr(paths, "media_dir", lambda: root)
    return root / source.path


@pytest.mark.parametrize(
    "field", ["logoUrl", "coverUrl", "fanartUrl", "iconUrl", "marqueeUrl", "screenshotUrl"]
)
def test_preview_publishes_the_canonical_media_role(canonical_art: Path, field: str) -> None:
    result = _project_journey_catalog(
        [{"id": "game-a", "title": "Owned game A", "platformId": "test-platform"}],
        game_record_public_field_types(),
        {"id": "string", "name": "string", "gameCount": "integer"},
    )["library.games"]
    assert result["fields"].get(field) == "string", "a selectable role must be published"
    assert result["rows"][0].get(field) == canonical_art.as_uri()


def test_cinema_keeps_cover_already_resolved_in_the_public_row(
    canonical_art: Path, tmp_path: Path
) -> None:
    bridge = LauncherBridge(
        sections=(), context_path=tmp_path / "return.json", on_launch=lambda *_: None
    )
    scene = bridge._journey_cinema(
        {
            "menuId": "games",
            "selectedItemId": "emulation:game-a",
            "items": [
                {
                    "id": "emulation:game-a",
                    "gameId": "game-a",
                    "title": "Owned game A",
                    "coverUrl": canonical_art.as_uri(),
                }
            ],
        },
        "journey:games:emulation:game-a",
        bounds=LayoutBounds(640, 360),
        width=640,
        height=360,
    )
    assert scene["items"][0]["coverUrl"] == canonical_art.as_uri()
    assert scene["layouts"][scene["layoutId"]]["entries"][0]["source"] == canonical_art.as_uri()


def _bound_image(binding: str, value: object) -> dict:
    book = LayoutRecipeBook.from_dict(
        {
            "schemaVersion": 1,
            "layouts": {
                "logos": {
                    "source": "context.items",
                    "kind": "wheel",
                    "item": {"width": 120, "height": 60},
                    "template": {
                        "id": "art",
                        "kind": "image",
                        "properties": {"source": {"binding": "item." + binding, "fallback": ""}},
                    },
                    "imageRecipes": {"normal": "original"},
                }
            },
        }
    )
    return resolve_scene_layouts(
        book,
        {"context": {"items": [{"id": "game-a", binding: value}]}},
        bounds=LayoutBounds(640, 360),
        asset_uris={"logo": "file:///wrong-theme-logo.png"},
        asset_recipes={"original": {"source": "logo", "nodes": []}},
    ).to_qml_object()


def test_missing_contextual_image_never_substitutes_the_recipe_master() -> None:
    result = _bound_image("logoUrl", "")
    node = result["layouts"]["logos"]["entries"][0]
    assert node["source"] == "", "missing game artwork must not become a different image"
    assert node["resourceDegraded"]
    assert any("item.logoUrl" in row["reason"] for row in result["diagnostics"])


@pytest.mark.parametrize("field", ["title", "description", "videoUrl"])
def test_text_metadata_is_not_an_authorized_image_reference(field: str) -> None:
    result = _bound_image(field, "file:///owned-but-not-published-as-media.png")
    node = result["layouts"]["logos"]["entries"][0]
    assert node["source"] == ""
    assert node["resourceDegraded"]


@pytest.mark.parametrize(
    "uri",
    [
        "http://127.0.0.1/untrusted.png",
        "https://example.invalid/untrusted.png",
        "file://foreign/untrusted.png",
    ],
)
def test_public_media_binding_does_not_authorize_network_access(uri: str) -> None:
    result = _bound_image("logoUrl", uri)
    node = result["layouts"]["logos"]["entries"][0]
    assert node["source"] == ""
    assert node["resourceDegraded"]


def test_contextual_role_survives_save_reopen_export_import_and_common_launcher(
    canonical_art: Path,
    tmp_path: Path,
) -> None:
    from steamzero.adapters.theme_catalog import ThemeCatalog, validate_theme_directory
    from steamzero.domain.theme_editor import ThemeEditorManager
    from steamzero.domain.theme_install import ThemeInstaller

    manager = ThemeEditorManager()
    sid = manager.create("Contextual wheel")["sessionId"]
    manager.create_layout(sid, "games", "wheel", "image")
    manager.set_layout(sid, "games", "source", "context.items")
    manager.edit_layout_binding(sid, "games", "source", binding="item.logoUrl", fallback="")
    saved = manager.save(sid)
    reopened = manager.load(saved["themeId"])
    row = {"id": "game-a", "gameId": "game-a", "title": "Owned", "logoUrl": canonical_art.as_uri()}
    read_model = {"context": {"items": [row]}}
    preview = manager.preview(reopened["sessionId"], scene_layout_read_model=read_model)["preview"]
    package = tmp_path / "context.zip"
    package.write_bytes(manager.export_zip(reopened["sessionId"]))
    installed = ThemeInstaller(validate=validate_theme_directory).install(str(package), force=True)
    runtime = ThemeCatalog().resolve(installed["themeId"]).to_theme_qml_object()
    assert runtime["logicalRevision"] == preview["logicalRevision"]
    bridge = LauncherBridge(
        sections=(), context_path=tmp_path / "return.json", on_launch=lambda *_: None
    )
    scene = bridge._journey_cinema(
        {"menuId": "games", "items": [row], "selectedItemId": "game-a", "theme": runtime},
        "journey:games:game-a",
        bounds=LayoutBounds(640, 360),
        width=640,
        height=360,
    )
    expected = preview["sceneLayoutPreview"]["layouts"]["games"]["entries"][0]
    actual = scene["layouts"]["games"]["entries"][0]
    assert expected["source"] == actual["source"] == canonical_art.as_uri()
    assert actual["key"] == "game-a"
    assert not scene["diagnostics"]


def test_missing_cover_reports_resource_loss_without_replacing_the_selected_layout(
    tmp_path: Path,
) -> None:
    bridge = LauncherBridge(
        sections=(), context_path=tmp_path / "return.json", on_launch=lambda *_: None
    )
    scene = bridge._journey_cinema(
        {
            "menuId": "games",
            "items": [{"id": "game-a", "gameId": "game-a", "title": "Owned"}],
            "selectedItemId": "game-a",
        },
        "journey:games:game-a",
        bounds=LayoutBounds(640, 360),
        width=640,
        height=360,
    )
    assert scene["resourceResolutionState"] == "partial"
    assert scene["diagnostics"] and scene["layoutDiagnostic"]
    node = scene["layouts"][scene["layoutId"]]["entries"][0]
    assert node["source"] == "" and node["resourceDegraded"]

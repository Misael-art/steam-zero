"""Native authoring must use the public layout, recipe, motion and source contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from steamzero.core.errors import SteamZeroError
from steamzero.domain.scene_layout import LayoutBounds, LayoutRecipeBook, resolve_scene_layouts
from steamzero.domain.theme_editor import ThemeEditorManager


@pytest.fixture
def editor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ThemeEditorManager:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return ThemeEditorManager()


def test_layout_created_without_demo_supports_history_save_reopen(
    editor: ThemeEditorManager,
) -> None:
    session = editor.create("Wheel original")
    sid = session["sessionId"]
    created = editor.create_layout(sid, "games", "wheel", "image")
    assert created["manifest"]["extends"] == "org.steamzero.default"
    assert created["declared"]["sceneLayouts"]["layouts"]["games"]["kind"] == "wheel"
    assert len(created["preview"]["sceneLayoutPreview"]["layouts"]["games"]["entries"]) == 4
    editor.set_layout(sid, "games", "highlight.scale", 1.35)
    editor.set_layout(sid, "games", "offset.minScale", 0.6)
    editor.set_layout(sid, "games", "imageRecipes.normal", "side")
    before = editor.preview(sid)
    with pytest.raises(SteamZeroError):
        editor.set_layout(sid, "games", "offset.minScale", 9)
    assert editor.preview(sid) == before
    editor.undo(sid)
    assert "normal" not in editor.preview(sid)["preview"]["sceneLayouts"]["layouts"]["games"].get(
        "imageRecipes", {}
    )
    editor.redo(sid)
    editor.save(sid)
    reopened = editor.load(created["manifest"]["id"])
    layout = reopened["declared"]["sceneLayouts"]["layouts"]["games"]
    assert layout["highlight"]["scale"] == 1.35
    assert layout["offset"]["minScale"] == 0.6
    assert layout["imageRecipes"]["normal"] == "side"
    assert (
        reopened["preview"]["logicalRevision"] == editor.preview(sid)["preview"]["logicalRevision"]
    )


def test_layout_recipe_links_resolve_states_and_report_missing_dependencies() -> None:
    book = LayoutRecipeBook.from_dict(
        {
            "schemaVersion": 1,
            "layouts": {
                "games": {
                    "source": "library.items",
                    "kind": "wheel",
                    "selected": 1,
                    "item": {"width": 120, "height": 80},
                    "template": {
                        "id": "art",
                        "kind": "image",
                        "properties": {"source": "asset:logo"},
                    },
                    "imageRecipes": {"normal": "side", "focused": "center"},
                }
            },
        }
    )
    recipes = {
        "side": {"source": "logo", "nodes": [{"type": "grayscale", "parameters": {"amount": 1}}]},
        "center": {
            "source": "logo",
            "nodes": [{"type": "outline", "parameters": {"width": 2, "color": "#ffffff"}}],
        },
    }
    rows = {"library": {"items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}}
    result = resolve_scene_layouts(
        book,
        rows,
        bounds=LayoutBounds(640, 200),
        asset_uris={"logo": "file:///fixture.png"},
        asset_recipes=recipes,
    )
    entries = result.to_qml_object()["layouts"]["games"]["entries"]
    assert [e["recipeName"] for e in entries] == ["side", "center", "side"]
    assert [e["key"] for e in entries] == ["a", "b", "c"]
    assert {e["source"] for e in entries} == {"file:///fixture.png"}
    assert not result.diagnostics
    missing = resolve_scene_layouts(book, rows, bounds=LayoutBounds(640, 200))
    assert any("side" in d.reason for d in missing.diagnostics)
    assert all(e.node["source"] == "" for e in missing.layouts["games"].entries)


def test_failed_save_preserves_previous_complete_theme(
    editor: ThemeEditorManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.core import fs

    sid = editor.create("Original preserved")["sessionId"]
    saved = editor.save(sid)
    target = Path(saved["path"])
    previous = (target / "theme.json").read_bytes()
    editor.set_metadata(sid, "name", "New draft")
    original = fs.write_atomic

    def fail_manifest(path: Path, data: bytes, **kwargs: object) -> None:
        if path.name == "theme.json":
            raise OSError("simulated interrupted write")
        original(path, data, **kwargs)

    monkeypatch.setattr(fs, "write_atomic", fail_manifest)
    with pytest.raises(OSError):
        editor.save(sid, overwrite=True)
    assert (target / "theme.json").read_bytes() == previous
    assert editor.preview(sid)["preview"]["themeId"] == saved["themeId"]
    monkeypatch.setattr(fs, "write_atomic", original)
    editor.save(sid, overwrite=True)
    assert (target / "theme.json").read_bytes() != previous


def test_launcher_accepts_native_wheel_instead_of_falling_back_to_aura() -> None:
    from steamzero.adapters.launcher_ui import LauncherBridge

    raw = {
        "source": "library.items",
        "kind": "wheel",
        "item": {"width": 120, "height": 80},
        "template": {"kind": "image", "id": "logo", "properties": {"source": "asset:logo"}},
    }
    recipe, state, diagnostic = LauncherBridge._journey_cinema_recipe(
        {"theme": {"sceneLayouts": {"schemaVersion": 1, "layouts": {"myWheel": raw}}}}, 800
    )
    assert recipe.id == "myWheel"
    assert state == "theme"
    assert diagnostic == ""


def test_two_native_themes_created_in_same_clock_tick_have_distinct_identity(
    editor: ThemeEditorManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.core import ids

    values = iter(f"01m67eqe0000000000000000{i:02}" for i in range(4))
    monkeypatch.setattr(ids, "new_ulid", lambda: next(values))
    first = editor.create("First")
    second = editor.create("Second")
    assert first["sessionId"] != second["sessionId"]
    assert first["manifest"]["id"] != second["manifest"]["id"]


def test_one_master_two_consumers_and_portable_round_trip(
    editor: ThemeEditorManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import zipfile

    from tests.unit.test_media_sources import source_bytes

    from steamzero.adapters.theme_catalog import ThemeCatalog, validate_theme_directory
    from steamzero.core import paths
    from steamzero.domain.media_pipeline import MediaPipeline
    from steamzero.domain.media_registry import MediaRegistry, Provenance
    from steamzero.domain.theme_install import ThemeInstaller

    master = MediaPipeline(paths.media_dir()).preserve_source(
        source_bytes(), "color.png", Provenance("local-import", "", "CC0-1.0")
    )
    sid = editor.create("Portable wheel")["sessionId"]
    editor.set_source(sid, "logo", master.digest)
    editor.edit_asset_recipe(sid, "initialize", source_slot="logo")
    editor.edit_asset_recipe(sid, "create-recipe", name="side")
    editor.edit_asset_recipe(sid, "add", recipe="side", node_type="grayscale")
    editor.edit_asset_recipe(sid, "add", recipe="original", node_type="outline")
    editor.create_layout(sid, "games", "wheel")
    editor.set_layout(sid, "games", "imageRecipes.normal", "side")
    editor.set_layout(sid, "games", "imageRecipes.focused", "original")
    editor.edit_motion(
        sid,
        "set_transition",
        timeline="enter",
        value={"from": "normal", "to": "focused", "duration": 240, "easing": "cubicOut"},
    )
    editor.set_layout(sid, "games", "motion.enter", "enter")
    saved = editor.save(sid)
    before = editor.preview(sid)["preview"]
    runtime = ThemeCatalog().resolve(saved["themeId"]).to_theme_qml_object()
    assert runtime["logicalRevision"] == before["logicalRevision"]
    assert runtime["assetUris"] == before["assetUris"]
    assert (
        before["sceneLayoutPreview"]["layouts"]["games"]["entries"][0]["source"]
        == runtime["assetUris"]["logo"]
    )
    second = editor.create("Another composition")["sessionId"]
    editor.set_source(second, "logo", master.digest)
    editor.save(second)
    assert len(list((paths.media_dir() / "masters").rglob("*.png"))) == 1
    assert not list(paths.themes_dir().rglob("*.png"))
    package_data = editor.export_zip(sid)
    with zipfile.ZipFile(io.BytesIO(package_data)) as package:
        assert sum(name.endswith(".png") for name in package.namelist()) == 1
    package_path = tmp_path / "wheel.zip"
    package_path.write_bytes(package_data)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "fresh-data"))
    imported = ThemeInstaller(validate=validate_theme_directory).install(str(package_path))
    reopened = ThemeEditorManager().load(imported["themeId"])
    assert reopened["manifest"] == editor._get_session(sid).manifest
    assert reopened["preview"]["logicalRevision"] == before["logicalRevision"]
    assert (
        MediaRegistry.resolve_source(paths.media_dir(), master.digest).read_bytes()
        == source_bytes()
    )
    assert len(list((paths.media_dir() / "masters").rglob("*.png"))) == 1
    assert not list(paths.themes_dir().rglob("*.png"))
    assert not list(paths.themes_dir().rglob("media-sources"))


def test_logical_revision_is_independent_of_accessibility_preview_context(
    editor: ThemeEditorManager,
) -> None:
    sid = editor.create("One logical revision")["sessionId"]
    normal = editor.preview(sid)["preview"]
    accessible = editor.preview(sid, high_contrast=True, reduced_motion=True)["preview"]
    assert normal["resolved"] != accessible["resolved"]
    assert normal["logicalRevision"] == accessible["logicalRevision"]
    editor.set_metadata(sid, "description", "New authored revision")
    assert editor.preview(sid)["preview"]["logicalRevision"] != normal["logicalRevision"]


@pytest.mark.parametrize(
    "source", ["https://example.invalid/track.png", "file:///outside/fixture.png", "../outside.png"]
)
def test_literal_layout_sources_cannot_bypass_the_resource_resolver(source: str) -> None:
    book = LayoutRecipeBook.from_dict(
        {
            "schemaVersion": 1,
            "layouts": {
                "wheel": {
                    "source": "library.items",
                    "kind": "wheel",
                    "item": {"width": 120, "height": 80},
                    "template": {"kind": "image", "id": "art", "properties": {"source": source}},
                }
            },
        }
    )
    result = resolve_scene_layouts(
        book, {"library": {"items": [{"id": "a"}]}}, bounds=LayoutBounds(640, 200)
    )
    assert result.layouts["wheel"].entries[0].node["source"] == ""
    assert any(d.code == "THEME-LAYOUT-RESOURCE-006" for d in result.diagnostics)


@pytest.mark.parametrize("source, expected_count", [("context.items", 3), ("unpublished.items", 0)])
def test_cinema_respects_authored_limit_and_published_source(
    source: str, expected_count: int
) -> None:
    from steamzero.domain.scene_layout import LayoutRecipe
    from steamzero.launcher.cinema import resolve_cinema_covers

    recipe = LayoutRecipe.from_dict(
        "wheel",
        {
            "source": source,
            "kind": "wheel",
            "maxItems": 3,
            "item": {"width": 120, "height": 80},
            "template": {
                "kind": "text",
                "id": "title",
                "properties": {"text": {"binding": "item.title"}},
            },
        },
    )
    result = resolve_cinema_covers(
        recipe,
        [{"id": str(i), "title": str(i)} for i in range(12)],
        9,
        bounds=LayoutBounds(640, 200),
    )
    assert len(result["layouts"]["wheel"]["entries"]) == expected_count
    if expected_count:
        assert result["sourceIndices"][result["selected"]] == 9
    else:
        assert any(d["code"] == "THEME-LAYOUT-SOURCE-001" for d in result["diagnostics"])


def test_new_native_layout_uses_shared_context_contract(editor: ThemeEditorManager) -> None:
    sid = editor.create("Shared scene context")["sessionId"]
    created = editor.create_layout(sid, "wheel", "wheel")
    assert created["declared"]["sceneLayouts"]["layouts"]["wheel"]["source"] == "context.items"


def test_interrupted_staging_is_not_discovered_as_an_installed_dependency(
    editor: ThemeEditorManager,
) -> None:
    import json

    from steamzero.adapters.theme_catalog import ThemeCatalog

    parent = editor.create("Installed parent")["sessionId"]
    installed = editor.save(parent)
    target = Path(installed["path"])
    candidate = target.parent / ("." + target.name + ".stage.fixture")
    candidate.mkdir()
    manifest = json.loads((target / "theme.json").read_text())
    manifest["tokens"] = {"color": {"accent": "#ff0000"}}
    (candidate / "theme.json").write_text(json.dumps(manifest))
    child = editor.create("Child", extends=installed["themeId"])
    child_id = child["manifest"]["id"]
    editor.save(child["sessionId"])
    runtime = ThemeCatalog().resolve(child_id).to_theme_qml_object()
    assert child["preview"]["logicalRevision"] == runtime["logicalRevision"]
    assert not any(entry["id"].startswith(".") for entry in ThemeCatalog().list_catalog())


@pytest.mark.parametrize("invalid", ["{", '{"id":"../../escaped"}', '{"id": null}'])
def test_native_import_rejects_invalid_manifest_before_publication(
    editor: ThemeEditorManager, tmp_path: Path, invalid: str
) -> None:
    import zipfile

    from steamzero.core import paths
    from steamzero.domain.theme_install import ThemeInstaller

    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("org.test.candidate/theme.json", invalid)
    with pytest.raises(SteamZeroError, match="E-THEME-MANIFEST"):
        ThemeInstaller().install(str(package))
    assert not (paths.themes_dir() / "org.test.candidate").exists()
    assert not (paths.themes_dir().parent / "escaped").exists()


def test_native_inherited_package_asset_has_same_owner_in_studio_and_launcher(
    editor: ThemeEditorManager,
) -> None:
    import json

    from tests.unit.test_media_sources import source_bytes

    from steamzero.adapters.theme_catalog import ThemeCatalog
    from steamzero.core import paths

    parent = paths.themes_dir() / "org.test.parent"
    (parent / "assets").mkdir(parents=True)
    image = parent / "assets/color.png"
    image.write_bytes(source_bytes())
    manifest = {
        "schemaVersion": 1,
        "kind": "steamzero-theme-v1",
        "id": parent.name,
        "name": "Parent",
        "version": "1.0.0",
        "author": "Fixture",
        "license": "CC0-1.0",
        "compatibility": {"themeApi": 1},
        "assets": {"logo": "assets/color.png"},
    }
    (parent / "theme.json").write_text(json.dumps(manifest))
    sid = editor.create("Inherited composition")["sessionId"]
    editor.set_metadata(sid, "extends", parent.name)
    editor.create_layout(sid, "games", "wheel")
    preview = editor.preview(sid)["preview"]
    assert (
        preview["sceneLayoutPreview"]["layouts"]["games"]["entries"][0]["source"] == image.as_uri()
    )
    saved = editor.save(sid)
    runtime_theme = ThemeCatalog().resolve(saved["themeId"])
    runtime = runtime_theme.to_theme_qml_object()
    assert runtime["assetUris"]["logo"] == image.as_uri()
    assert preview["logicalRevision"] == runtime["logicalRevision"]
    image.unlink()
    image.symlink_to(parent / "theme.json")
    missing = ThemeCatalog().resolve(saved["themeId"]).to_theme_qml_object()
    assert "logo" not in missing["assetUris"]
    assert missing["themeId"] == "org.steamzero.default"
    from steamzero.domain.themes import bind_theme_sources

    rebound = bind_theme_sources(runtime_theme, paths.media_dir()).to_theme_qml_object()
    assert "logo" not in rebound["assetUris"]
    assert any(d["element"] == "logo" for d in rebound["assetSourceDiagnostics"])


@pytest.mark.parametrize("existed", [False, True])
def test_atomic_theme_publication_rolls_back_failed_durability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existed: bool
) -> None:
    from steamzero.core import fs

    stage, target = tmp_path / ".candidate", tmp_path / "published"
    stage.mkdir()
    (stage / "theme.json").write_text("new complete")
    if existed:
        target.mkdir()
        (target / "theme.json").write_text("old complete")
    sync = fs._fsync_dir

    def fail_sync(path: Path) -> None:
        raise OSError("controlled directory durability failure")

    monkeypatch.setattr(fs, "_fsync_dir", fail_sync)
    with pytest.raises(OSError, match="controlled"):
        fs.publish_tree(stage, target, replace_existing=existed)
    assert (stage / "theme.json").read_text() == "new complete"
    if existed:
        assert (target / "theme.json").read_text() == "old complete"
    else:
        assert not target.exists()
    monkeypatch.setattr(fs, "_fsync_dir", sync)
    fs.publish_tree(stage, target, replace_existing=existed)
    assert (target / "theme.json").read_text() == "new complete"
    if existed:
        assert (stage / "theme.json").read_text() == "old complete"


def test_atomic_theme_publication_unsupported_filesystem_preserves_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.core import fs

    stage, target = tmp_path / ".candidate", tmp_path / "published"
    for path, value in [(stage, "new"), (target, "old")]:
        path.mkdir()
        (path / "theme.json").write_text(value)
    monkeypatch.setattr(fs, "_renameat2", lambda *args: False)
    with pytest.raises(SteamZeroError, match="filesystem sem publicação atômica"):
        fs.publish_tree(stage, target, replace_existing=True)
    assert (stage / "theme.json").read_text() == "new"
    assert (target / "theme.json").read_text() == "old"


def test_native_composition_identifier_round_trips_through_catalog(
    editor: ThemeEditorManager,
) -> None:
    from steamzero.adapters.theme_catalog import ThemeCatalog

    sid = editor.create("Named composition")["sessionId"]
    editor.create_layout(sid, "games-wheel", "wheel")
    saved = editor.save(sid)
    resolved = ThemeCatalog().resolve(saved["themeId"])
    assert resolved.id == saved["themeId"]
    assert resolved.scene_layouts is not None
    assert "games-wheel" in resolved.scene_layouts.layouts


def test_package_svg_does_not_publish_external_resource_to_renderer(
    editor: ThemeEditorManager,
) -> None:
    import json

    from steamzero.core import paths

    parent = paths.themes_dir() / "org.test.svg"
    (parent / "assets").mkdir(parents=True)
    (parent / "assets/art.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///outside.png"/></svg>'
    )
    (parent / "theme.json").write_text(
        json.dumps(
            {
                "id": parent.name,
                "name": "SVG",
                "version": "1.0.0",
                "assets": {"logo": "assets/art.svg"},
            }
        )
    )
    sid = editor.create("Untrusted package image")["sessionId"]
    editor.set_metadata(sid, "extends", parent.name)
    preview = editor.preview(sid)["preview"]
    assert "logo" not in preview["assetUris"]
    assert any(d["element"] == "logo" for d in preview["assetSourceDiagnostics"])


def test_native_preview_publishes_and_uses_its_actual_viewport(editor: ThemeEditorManager) -> None:
    sid = editor.create("Explicit preview context")["sessionId"]
    editor.create_layout(sid, "games", "wheel")
    preview = editor.preview(sid, viewport_width=800, viewport_height=300)["preview"]
    scene = preview["sceneLayoutPreview"]
    assert scene["viewport"] == {"width": 800, "height": 300}
    assert scene["layouts"]["games"]["entries"][0]["y"] == 110


@pytest.mark.parametrize(
    "action, payload",
    [
        ("set-layout", {"layoutId": "games", "field": "highlight.scale", "value": 1.35}),
        ("set-layout", {"layoutId": "games", "field": "motion.enter", "value": None}),
        (
            "edit-motion",
            {
                "op": "set_transition",
                "timeline": "enter",
                "value": {"from": "normal", "to": "focused", "duration": 180, "easing": "cubicOut"},
            },
        ),
        (
            "edit-binding",
            {"layoutId": "games", "prop": "source", "binding": "item.logoUrl", "fallback": ""},
        ),
    ],
)
def test_native_authoring_payloads_match_published_action_contracts(
    action: str, payload: dict
) -> None:
    import jsonschema

    from steamzero.adapters.desktop_contracts import handheld_ui_contracts

    schema = handheld_ui_contracts()["byId"]["theme.editor." + action]["inputSchema"]
    jsonschema.validate({"sessionId": "fixture", **payload}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"sessionId": "fixture", **payload, "execute": "arbitrary"}, schema)

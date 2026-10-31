// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtTest
import "../../src/steamzero/ui/qml"

Item {
    id: harness
    width: 1280
    height: 900
    property var cfg: ({})
    property var errors: []
    function xhr(method, path, payload, callback, failed) {
        if (!cfg.apiUrl) return
        const r = new XMLHttpRequest()
        r.open(method, cfg.apiUrl + path)
        r.setRequestHeader("X-SteamZero-Token", cfg.apiToken)
        r.setRequestHeader("Content-Type", "application/json")
        r.onreadystatechange = function() {
            if (r.readyState !== XMLHttpRequest.DONE) return
            let body = ({})
            try { body = JSON.parse(r.responseText || "{}") } catch (e) {}
            if (r.status === 200) callback(body)
            else {
                const message = JSON.stringify(body.error || body)
                errors.push(message)
                if (failed) failed(message)
            }
        }
        r.send(method === "GET" ? undefined : JSON.stringify(payload || ({})))
    }
    function action(id, payload, callback, failed) {
        xhr("POST", "/" + id.split(".").join("/"), payload, callback, failed)
        return true
    }
    ThemeEditorPanel {
        id: panel; anchors.fill: parent; request: harness.xhr; requestAction: harness.action
        visualScale: harness.cfg.visualScale || 1
        compactLayout: harness.cfg.compact === true
    }
    TestCase {
        name: "NativeWheelAuthoring"
        when: windowShown
        function find(item, name) {
            if (!item) return null
            if (item.objectName === name) return item
            const children = item.children || []
            for (let i = 0; i < children.length; ++i) {
                const hit = find(children[i], name)
                if (hit) return hit
            }
            return null
        }
        function reveal(item) {
            for (let attempt = 0; attempt < 4; ++attempt) {
                let flick = item.parent
                while (flick && flick.contentY === undefined) flick = flick.parent
                if (!flick) return
                const point = item.mapToItem(flick, 0, 0)
                if (point.y < 40) flick.contentY = Math.max(0, flick.contentY + point.y - 40)
                else if (point.y + item.height > flick.height - 40)
                    flick.contentY += point.y + item.height - flick.height + 40
                wait(60)
            }
        }
        function control(name) {
            const item = find(panel, name)
            verify(item !== null, "missing control " + name)
            if (panel.compactLayout && !item.visible) {
                const tabs = find(panel, "themeEditorCompactPane")
                for (let i = 0; i < tabs.count && !item.visible; ++i) {
                    mouseClick(tabs.itemAt(i))
                    wait(0)
                }
            }
            tryVerify(function() { return item.visible && item.enabled }, 3000, name + " unavailable")
            reveal(item)
            verify(item.width >= 48 && item.height >= 48, "small target " + name)
            const point = item.mapToItem(harness, 0, 0)
            verify(point.x >= 0 && point.y >= 0 && point.x + item.width <= harness.width && point.y + item.height <= harness.height, "outside viewport " + name + ": " + point.x + "," + point.y + " " + item.width + "×" + item.height)
            return item
        }
        function click(name) {
            const item = control(name)
            mousePress(item, item.width / 2, item.height / 2)
            verify(item.pressed, "control did not receive touch " + name)
            mouseRelease(item, item.width / 2, item.height / 2)
        }
        function type(name, text) {
            const item = control(name)
            const editor = typeof item.selectAll === "function" ? item : item.contentItem
            mouseClick(editor)
            editor.selectAll()
            for (let i = 0; i < text.length; ++i) keyClick(text.charAt(i))
            keyClick(Qt.Key_Return)
        }
        function choose(name, value) {
            const combo = control(name)
            const index = combo.model.indexOf(value)
            verify(index >= 0, "missing option " + name + ": " + value)
            const previous = combo.currentIndex
            mouseClick(combo, combo.width / 2, combo.height / 2)
            tryVerify(function() { return combo.popup.visible }, 3000)
            for (let i = 0; i < Math.abs(index - previous); ++i)
                keyClick(index >= previous ? Qt.Key_Down : Qt.Key_Up)
            keyClick(Qt.Key_Return)
            tryCompare(combo, "currentText", value, 3000)
        }
        function settled() {
            tryVerify(function() { return !panel.editorMutationInFlight && panel.editorMutationQueue.length === 0 }, 5000)
        }
        function test_native_creation_from_canonical_master() {
            const r = new XMLHttpRequest()
            r.open("GET", Qt.resolvedUrl("../../build/ui-native-wheel-authoring.json"), false)
            r.send()
            harness.cfg = JSON.parse(r.responseText)
            harness.width = harness.cfg.viewportWidth
            harness.Window.window.width = harness.width
            const created = harness.cfg.created
            panel._openEditor(created.sessionId, created.manifest, created.preview, created.declared, created.effectSchema, created.motionSchema, created.assetRecipeSchema)
            click("nativeMasterRefresh")
            tryVerify(function() { return panel.nativeSources.length === 1 }, 5000)
            control("nativeMasterPicker")
            click("nativeMasterBind")
            settled()
            verify(panel.editorManifest.assets.logo.startsWith("master:sha256:"))
            type("nativeLayoutName", "games")
            click("nativeLayoutCreate")
            settled()
            compare(panel.editorDeclared.sceneLayouts.layouts.games.kind, "wheel")
            verify(!panel.assetRecipeDemoActive)
            choose("assetRecipeSourceSlotPicker", "logo")
            click("assetRecipeInitializeButton")
            settled()
            type("assetRecipeNewNameField", "side")
            click("assetRecipeCreateRecipeButton")
            settled()
            choose("assetRecipePicker", "side")
            choose("assetRecipeNodeTypePicker", "grayscale")
            click("assetRecipeAddNodeButton")
            settled()
            type("assetRecipeNewNameField", "muted")
            click("assetRecipeCreateRecipeButton")
            settled()
            choose("assetRecipePicker", "muted")
            choose("assetRecipeNodeTypePicker", "saturation")
            click("assetRecipeAddNodeButton")
            settled()
            choose("assetRecipeFieldPicker", "amount")
            type("assetRecipeNumberEditor", "0.5")
            settled()
            compare(panel.assetRecipeCurrentNode.amount, 0.5)
            type("assetRecipeNewNameField", "shadow")
            click("assetRecipeCreateRecipeButton")
            settled()
            choose("assetRecipePicker", "shadow")
            choose("assetRecipeNodeTypePicker", "silhouette")
            click("assetRecipeAddNodeButton")
            settled()
            compare(panel.assetRecipeCurrentNode.color, "#000000")
            choose("assetRecipePicker", "original")
            choose("assetRecipeNodeTypePicker", "outline")
            click("assetRecipeAddNodeButton")
            settled()
            choose("assetRecipeFieldPicker", "width")
            type("assetRecipeNumberEditor", "3")
            settled()
            choose("nativeLayoutNormalRecipe", "side")
            choose("nativeLayoutFocusRecipe", "original")
            choose("nativeMotionEasing", "cubicOut")
            type("nativeMotionDuration", "180")
            click("nativeMotionApply")
            settled()
            choose("nativeMotionEvent", "exit")
            choose("nativeMotionFrom", "focused")
            choose("nativeMotionTo", "normal")
            choose("nativeMotionEasing", "quadIn")
            type("nativeMotionDuration", "90")
            click("nativeMotionApply")
            settled()
            choose("nativeMotionInterruption", "snap")
            settled()
            compare(panel.editorDeclared.sceneLayouts.layouts.games.motion.interruption, "snap")
            choose("nativeMotionInterruption", "retarget")
            settled()
            type("nativeLayout_highlight_scale", "1.35")
            settled()
            type("nativeLayout_selected", "1")
            settled()
            compare(panel.editorDeclared.sceneLayouts.layouts.games.selected, 1)
            compare(panel.editorDeclared.sceneLayouts.layouts.games.imageRecipes.normal, "side")
            compare(panel.editorDeclared.sceneLayouts.layouts.games.imageRecipes.focused, "original")
            const transitions = panel.editorDeclared.sceneMotion.transitions
            verify(transitions.some(function(t) { return t.easing === "cubicOut" && t.duration === 180 }))
            verify(transitions.some(function(t) { return t.easing === "quadIn" && t.duration === 90 }))
            verify(panel.sceneLayoutPreviewActive)
            if (panel.compactLayout) {
                const tabs = control("themeEditorCompactPane")
                const previewTab = tabs.itemAt(1)
                mouseClick(previewTab)
                tryCompare(tabs, "currentIndex", 1, 3000)
            }
            tryVerify(function() { const item = panel.sceneLayoutPreviewEntryAt(1); return item && item.sourceStatus === Image.Ready }, 5000)
            verify(waitForRendering(panel, 3000), "preview geometry must reach an actual frame")
            const item = panel.sceneLayoutPreviewEntryAt(1)
            const surface = find(panel, "sceneLayoutRepeater")
            compare(surface.width, panel.editorPreviewObject.sceneLayoutPreview.viewport.width)
            compare(surface.height, panel.editorPreviewObject.sceneLayoutPreview.viewport.height)
            const feedback = find(panel, "nativeLayoutRenderFeedback")
            const artBottom = item.mapToItem(panel, 0, item.height).y
            verify(artBottom <= feedback.mapToItem(panel, 0, 0).y,
                   "composition cannot paint over resource diagnostics: " + JSON.stringify({
                       artBottom: artBottom, feedbackTop: feedback.mapToItem(panel, 0, 0).y,
                       viewport: panel.editorPreviewObject.sceneLayoutPreview.viewport,
                       surfaceHeight: surface.height, surfaceScale: surface.scale,
                       frameHeight: surface.parent.height}))
            verify(item.fallbackActive, "software must report partial effects")
            click("themeEditorSave")
            tryCompare(panel, "editorDirty", false, 5000)
            compare(harness.errors.length, 0, JSON.stringify(harness.errors))
            if (harness.cfg.captureDir) {
                reveal(item)
                let captured = false
                panel.grabToImage(function(result) {
                    verify(result.saveToFile(harness.cfg.captureDir + (panel.compactLayout ? "/studio-compact.png" : "/studio-wide.png")))
                    captured = true
                })
                tryVerify(function() { return captured }, 3000)
            }
            console.log("NATIVE-WHEEL-UI-THEME " + panel.editorManifest.id)
            console.log("NATIVE-WHEEL-UI-REVISION " + panel.editorPreviewObject.logicalRevision)
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Autoria direta de cena e mapa da Jornada pela bridge real (offscreen).

import QtQuick
import QtQuick.Controls
import QtTest
import "../../src/steamzero/ui/qml"

Item {
    id: harness
    width: 1440
    height: 900
    property var bridgeConfig: ({})
    property var contracts: ({byId: ({})})
    property bool bridgeReady: false

    function readConfig() {
        const request = new XMLHttpRequest()
        request.open("GET", Qt.resolvedUrl("../../build/studio-scene-e2e.json"), false)
        request.send()
        return JSON.parse(request.responseText)
    }

    function requestAction(actionId, payload, success, failure) {
        const action = contracts.byId ? contracts.byId[actionId] : null
        if (!action || !action.endpoint || !action.method)
            return false
        const request = new XMLHttpRequest()
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE)
                return
            const value = request.responseText ? JSON.parse(request.responseText) : ({})
            if (request.status >= 200 && request.status < 300)
                success(value)
            else if (failure)
                failure(value)
        }
        request.open(action.method, bridgeConfig.apiUrl + action.endpoint, true)
        request.setRequestHeader("X-SteamZero-Token", bridgeConfig.apiToken)
        request.setRequestHeader("Content-Type", "application/json")
        request.send(JSON.stringify(payload || {}))
        return true
    }

    Loader {
        id: loader
        width: harness.width
        height: harness.height
        active: false
        sourceComponent: StudioSceneEditor {
            projectId: "org.test.scene-e2e"
            requestAction: harness.requestAction
        }
    }

    JourneyGraphMap {
        id: graph
        x: 0; y: 0
        width: 900; height: 400
        visible: false
        menus: [
            {id: "a", name: "A", nature: "platforms"},
            {id: "b", name: "B", nature: "games", layout: {x: 400, y: 40}}
        ]
        entryMenuId: "a"
    }
    SignalSpy { id: layoutSpy; target: graph; signalName: "layoutRequested" }
    SignalSpy { id: linkSpy; target: graph; signalName: "connectRequested" }

    TestCase {
        name: "StudioSceneAuthoring"
        when: windowShown

        function find(name) { return findChild(loader.item, name) }
        function liveLayer(stage, layerId) {
            for (let i = 0; i < stage.children.length; ++i) {
                const child = stage.children[i]
                if (child.objectName === "sceneLayer-" + layerId)
                    return child
            }
            return null
        }
        function liveHandle(layer, name) {
            for (let i = 0; i < layer.children.length; ++i)
                if (layer.children[i].objectName === name)
                    return layer.children[i]
            return null
        }

        function test_01_direct_scene_authoring() {
            bridgeConfig = readConfig()
            const request = new XMLHttpRequest()
            request.open("GET", bridgeConfig.apiUrl + "/contracts", false)
            request.setRequestHeader("X-SteamZero-Token", bridgeConfig.apiToken)
            request.send()
            contracts = JSON.parse(request.responseText)
            loader.active = true
            const editor = loader.item
            tryVerify(function() { return editor.snapshot !== null }, 5000)
            editor.importFile("file://" + bridgeConfig.photoA, "folder")
            tryVerify(function() { return editor.masters.length === 1 }, 5000)
            editor.importFile("file://" + bridgeConfig.photoB, "library")
            tryVerify(function() { return editor.masters.length === 2 }, 5000)
            editor.libraryOrigin = "folder"
            compare(editor.filteredMasters.length, 1)
            editor.libraryOrigin = ""

            editor.edit("drop", {mediaId: editor.masters[0].id, x: 0.3, y: 0.4})
            tryVerify(function() { return editor.layers.length === 1 }, 5000)
            editor.edit("drop", {mediaId: editor.masters[1].id, x: 0.75, y: 0.7, width: 0.2})
            tryVerify(function() { return editor.layers.length === 2 }, 5000)

            const stage = find("sceneStage")
            const first = editor.layers[0]
            const layerItem = find("sceneLayer-" + first.id)
            verify(layerItem !== null)
            // Move with the mouse: press on the body, drag, release.
            const startX = layerItem.x + layerItem.width / 2, startY = layerItem.y + layerItem.height / 2
            mousePress(stage, startX, startY)
            mouseMove(stage, startX + stage.width * 0.05, startY, 20, Qt.LeftButton)
            mouseMove(stage, startX + stage.width * 0.1, startY, 20, Qt.LeftButton)
            mouseRelease(stage, startX + stage.width * 0.1, startY)
            tryVerify(function() { return Math.abs(editor.layers[0].x - (first.x + 0.1)) < 0.02 }, 5000)

            // Select by click, then resize through the south-east handle.
            mouseClick(find("sceneLayer-" + first.id), 10, 10)
            tryVerify(function() { return editor.selection.length === 1 }, 5000)
            const before = editor.layers[0]
            let handle = null
            tryVerify(function() {
                const live = liveLayer(stage, first.id)
                handle = live ? liveHandle(live, "sceneHandle-se") : null
                return handle !== null
            }, 5000)
            verify(handle !== null)
            const hp = handle.mapToItem(stage, 6, 6)
            mousePress(stage, hp.x, hp.y)
            mouseMove(stage, hp.x + stage.width * 0.1, hp.y + stage.height * 0.02, 20, Qt.LeftButton)
            mouseRelease(stage, hp.x + stage.width * 0.1, hp.y + stage.height * 0.02)
            tryVerify(function() { return editor.layers[0].w > before.w + 0.05 }, 5000)
            fuzzyCompare(editor.layers[0].w / editor.layers[0].h, before.w / before.h, 0.001)

            // Shift-select second layer and align tops.
            mouseClick(find("sceneLayer-" + editor.layers[1].id), 5, 5, Qt.LeftButton, Qt.ShiftModifier)
            tryVerify(function() { return editor.selection.length === 2 }, 5000)
            mouseClick(find("sceneAlign-top"))
            tryVerify(function() { return Math.abs(editor.layers[0].y - editor.layers[1].y) < 1e-9 }, 5000)

            editor.edit("select", {layerId: editor.layers[0].id})
            tryVerify(function() { return editor.selectedLayer !== null }, 5000)
            editor.edit("set-recipe", {layerId: editor.layers[0].id, recipe: {preset: "mono", brightness: 0.2}})
            tryVerify(function() { return editor.layers[0].recipe.preset === "mono" }, 5000)
            const composed = JSON.stringify(editor.layers)

            // Window resize: pixels change, normalized composition does not.
            const pxBefore = find("sceneLayer-" + editor.layers[0].id).width
            loader.width = 1024; loader.height = 740
            wait(50)
            verify(find("sceneLayer-" + editor.layers[0].id).width < pxBefore)
            compare(JSON.stringify(editor.layers), composed)

            mouseClick(find("sceneUndo"))
            tryVerify(function() { return editor.layers[0].recipe.preset === "none" }, 5000)
            mouseClick(find("sceneRedo"))
            tryVerify(function() { return editor.layers[0].recipe.preset === "mono" }, 5000)

            mouseClick(find("sceneSave"))
            tryVerify(function() { return editor.notice.indexOf("salvo") >= 0 }, 5000)
            editor.open(false)
            tryVerify(function() { return JSON.stringify(editor.layers) === composed }, 5000)
            compare(editor.snapshot.media.filter(function(m) { return m.status === "available" }).length, 2)
        }

        function test_02_graph_drag_and_link() {
            graph.visible = true
            const a = findChild(graph, "journeyCard-a")
            verify(a !== null)
            const surface = a.parent
            mousePress(surface, a.x + 20, a.y + 20)
            mouseMove(surface, a.x + 60, a.y + 80, 20, Qt.LeftButton)
            mouseMove(surface, 140, 180, 20, Qt.LeftButton)
            mouseRelease(surface, 140, 180)
            tryCompare(layoutSpy, "count", 1)
            compare(layoutSpy.signalArguments[0][0], "a")
            mouseClick(findChild(graph, "journeyCardOutput-a"))
            compare(graph.linkSourceId, "a")
            mouseClick(findChild(graph, "journeyCard-b"), 20, 20)
            tryCompare(linkSpy, "count", 1)
            compare(linkSpy.signalArguments[0][0], "a")
            compare(linkSpy.signalArguments[0][1], "b")
        }
    }
}

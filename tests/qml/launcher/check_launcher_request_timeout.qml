// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Um peer loopback pode aceitar TCP e depois congelar. XMLHttpRequest.timeout
// não resolve isso em todas as versões de Qt; este harness prova o watchdog
// independente da cena antes de a ponte física ser suspensa no host.
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 800

    Component { id: sceneComponent; LauncherMain {} }

    TestCase {
        name: "LauncherRequestTimeout"
        when: windowShown

        function capture(scene, name) {
            const input = new XMLHttpRequest()
            input.open("GET", Qt.resolvedUrl("bridge-evidence.json"), false)
            input.send()
            const directory = JSON.parse(input.responseText).directory
            if (directory === "") return
            let saved = false
            verify(scene.contentItem.grabToImage(function(result) {
                saved = result.saveToFile(directory + "/" + name + ".png")
            }))
            tryVerify(function() { return saved }, 3000)
        }
        function channel(scene, prefix) {
            scene.api = "http://127.0.0.1:18169/" + prefix
            scene.token = "qml-timeout-test"
        }
        function flag(scene, path) {
            let ready = false
            let elapsed = 0
            while (!ready && elapsed < 2000) {
                scene._request("GET", path, null, function(status, text) {
                    ready = status === 200 && JSON.parse(text).ready
                })
                wait(50)
                elapsed += 50
            }
            verify(ready)
        }
        function test_model_retry_keeps_shell_focus_details_and_session_lock() {
            const scene = createTemporaryObject(sceneComponent, harness)
            channel(scene, "retry")
            scene._start()
            tryCompare(scene, "loadState", "ready")
            const shell = scene._activeLauncherShell()
            verify(shell !== null)
            shell.homeFocus = "library:second"
            verify(shell.openGame("second"))
            shell.sessionGameId = "second"
            shell.observedSessionId = "session-fixture"
            shell.launchState = "emulator-visible"
            scene._retry()
            compare(scene._activeLauncherShell(), shell)
            tryCompare(scene, "loadState", "error")
            compare(scene._activeLauncherShell(), shell)
            compare(shell.gamePage.gameId, "second")
            const retry = findChild(scene.contentItem, "launcherRetry")
            verify(retry !== null && retry.visible)
            retry.forceActiveFocus()
            capture(scene, "02-query-unavailable")
            keyClick(Qt.Key_Return)
            tryCompare(scene, "loadState", "ready")
            compare(scene._activeLauncherShell(), shell)
            compare(shell.homeFocus, "library:second")
            compare(shell.observedSessionId, "session-fixture")
            compare(shell.launchState, "emulator-visible")
            compare(shell.launchFocused(), false)
            capture(scene, "03-query-recovered")
        }
        function test_escape_dismisses_refresh_error_and_preserves_keyboard_return() {
            const scene = createTemporaryObject(sceneComponent, harness)
            channel(scene, "escape")
            scene._start()
            tryCompare(scene, "loadState", "ready")
            const shell = scene._activeLauncherShell()
            shell.homeFocus = "library:second"
            verify(shell.openGame("second"))
            scene._retry()
            tryCompare(scene, "loadState", "error")
            const retry = findChild(scene.contentItem, "launcherRetry")
            retry.forceActiveFocus()
            keyClick(Qt.Key_Escape)
            compare(scene.loadState, "ready")
            compare(shell.gamePage.gameId, "second")
            keyClick(Qt.Key_Escape)
            compare(shell.gamePage, null)
            compare(shell.homeFocus, "library:second")
        }
        function test_invalid_refresh_keeps_last_valid_catalog_data() {
            return [{tag: "null", prefix: "invalid"}, {tag: "focus", prefix: "invalid-shape"}]
        }
        function test_invalid_refresh_keeps_last_valid_catalog(data) {
            const scene = createTemporaryObject(sceneComponent, harness)
            channel(scene, data.prefix)
            scene._start()
            tryCompare(scene, "loadState", "ready")
            const original = scene.model
            const shell = scene._activeLauncherShell()
            scene._retry()
            tryCompare(scene, "loadState", "error")
            compare(scene.model, original)
            compare(scene._activeLauncherShell(), shell)
            scene._retry()
            tryCompare(scene, "loadState", "ready")
        }
        function test_old_catalog_response_cannot_replace_a_new_retry() {
            const scene = createTemporaryObject(sceneComponent, harness)
            channel(scene, "old")
            scene._start()
            flag(scene, "/started")
            scene._retry()
            tryCompare(scene, "loadState", "ready")
            scene._request("GET", "/release", null, function() {})
            flag(scene, "/finished")
            wait(100)
            compare(scene.loadState, "ready")
            verify(scene.model !== null)
        }
        function test_suspended_loopback_peer_returns_actionable_timeout() {
            const scene = createTemporaryObject(sceneComponent, harness)
            verify(scene !== null)
            scene.api = "http://127.0.0.1:18169"
            scene.token = "qml-timeout-test"
            let completed = false
            let status = -1
            const pending = scene._request("GET", "/hold", null, function(resultStatus, text) {
                status = resultStatus
                completed = true
            })
            tryVerify(function() { return completed }, scene.requestTimeoutMs + 1500,
                      "ponte suspensa não pode deixar a cena em preparação")
            compare(status, 0)
            compare(pending.readyState, XMLHttpRequest.UNSENT)
        }
    }
}

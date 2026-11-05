// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 800
    Component { id: sceneComponent; LauncherMain {} }
    TestCase {
        name: "LauncherLostAck"
        when: windowShown
        function capture(scene, config, name) {
            if (!config.capture) return
            let saved = false
            verify(scene.contentItem.grabToImage(function(result) {
                saved = result.saveToFile(config.capture + "/" + name + "-" + config.mode + ".png")
            }))
            tryVerify(function() { return saved }, 3000)
        }
        function test_ack_lost_keeps_lock_and_recovers_from_correlated_observation() {
            const configRequest = new XMLHttpRequest()
            configRequest.open("GET", Qt.resolvedUrl("ack-config.json"), false)
            configRequest.send()
            const config = JSON.parse(configRequest.responseText)
            const scene = createTemporaryObject(sceneComponent, harness)
            scene.width = 1280
            scene.height = 800
            scene.api = config.api
            scene.token = config.token
            scene._start()
            tryCompare(scene, "loadState", "ready")
            const shell = scene._activeLauncherShell()
            shell.homeFocus = "library:second"
            verify(shell.openGame("second"))
            const play = findChild(shell, "gameAction")
            tryVerify(function() { return play !== null && play.modelData.enabled === true }, 3000)
            keyClick(Qt.Key_Return)
            if (config.mode === "notAccepted") {
                wait(1000)
                compare(shell.launchState, "launching")
                verify(shell.launchError.indexOf("não foi confirmado") >= 0)
                compare(shell.launchFocused(), false)
                compare(shell.observedSessionId, "")
                compare(shell.observeSession({gameId: "second", clientRequestId: "foreign",
                    state: "closed", sessionId: "foreign-session"}), false)
                compare(shell.launchState, "launching")
                capture(scene, config, "01-unconfirmed")
                return
            }
            if (config.mode === "notStarted") {
                tryCompare(shell, "launchState", "failed", 5000)
                verify(shell.launchError.indexOf("TEST-NOT-STARTED") >= 0)
                tryCompare(findChild(shell, "launchFailureOverlay"), "opacity", 1)
                tryVerify(function() { return findChild(shell, "launchFailureRetry").activeFocus },
                    2000, "focus=" + (scene.activeFocusItem ? scene.activeFocusItem.objectName : "none")
                    + "; retry.focus=" + findChild(shell, "launchFailureRetry").focus)
                capture(scene, config, "02-not-started")
                keyClick(Qt.Key_Return)
                compare(shell.launchState, "recovered")
                keyClick(Qt.Key_Return)
            }
            tryCompare(shell, "launchState", "emulator-visible", 5000)
            compare(shell.observedSessionId, "session-ack")
            if (config.mode === "delayedAck") {
                wait(scene.requestTimeoutMs + 250)
                compare(shell.launchState, "emulator-visible")
                compare(shell.observedSessionId, "session-ack")
            }
            compare(shell.launchFocused(), false)
            compare(shell.observeSession({gameId: "second",
                clientRequestId: shell.expectedClientRequestId,
                attempt: {requestId: "foreign", state: "notStarted"}}), false)
            compare(shell.launchState, "emulator-visible")
            capture(scene, config, "03-confirmed")
            scene._request("GET", "/ack-control/close", null, function() {})
            tryCompare(shell, "launchState", "recovered", 5000)
            compare(shell.gamePage, null)
            compare(shell.homeFocus, "library:second")
            capture(scene, config, "04-return")
        }
    }
}

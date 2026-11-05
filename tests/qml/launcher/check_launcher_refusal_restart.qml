// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"
Item {
    id: harness
    width: 1280; height: 800
    Component { id: sceneComponent; LauncherMain {} }
    TestCase {
        name: "LauncherRefusalRestart"
        when: windowShown
        function capture(scene, config, name) {
            if (!config.capture) return
            let saved = false
            verify(scene.contentItem.grabToImage(function(result) {
                saved=result.saveToFile(config.capture + "/" + name + ".png")
            }))
            tryVerify(function() { return saved }, 3000)
        }
        function test_restore_refusal_and_explicit_retry() {
            const request = new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("refusal-config.json"), false)
            request.send()
            const config = JSON.parse(request.responseText)
            const scene = createTemporaryObject(sceneComponent, harness)
            scene.api=config.api; scene.token=config.token; scene._start()
            tryCompare(scene, "loadState", "ready")
            const shell = scene._activeLauncherShell()
            tryCompare(shell, "launchState", "failed", 6000)
            verify(shell.launchError.indexOf("E-CONTENT-UNSUPPORTED") >= 0)
            verify(shell.launchError.indexOf("private-fixture-path") < 0)
            compare(shell.homeFocus, "library:lifetime-probe")
            let count = -1
            scene._request("GET", "/refusal-control/count", null, function(status, value) {
                if (status === 200) count=JSON.parse(value).count
            })
            tryVerify(function() { return count === 0 }, 2000)
            tryVerify(function() { return findChild(shell, "launchFailureRetry").activeFocus }, 2000)
            capture(scene, config, "01-restored-refusal")
            if (config.mode === "observe") return
            keyClick(Qt.Key_Return)
            compare(shell.launchState, "recovered")
            keyClick(Qt.Key_Return)
            tryVerify(function() { return shell.gamePage !== null }, 3000)
            const play = findChild(shell, "gameAction")
            tryVerify(function() { return play !== null && play.modelData.enabled === true }, 3000)
            keyClick(Qt.Key_Return)
            tryCompare(shell, "launchState", "emulator-visible", 6000)
            verify(shell.observedSessionId !== "")
            compare(shell.homeFocus, "library:lifetime-probe")
            compare(shell.launchFocused(), false)
            capture(scene, config, "02-explicit-retry-running")
            scene._request("GET", "/refusal-control/finish", null, function() {})
            tryCompare(shell, "launchState", "recovered", 5000)
            compare(shell.gamePage, null)
            compare(shell.homeFocus, "library:lifetime-probe")
            tryVerify(function() { return !findChild(shell, "returnFadeLayer").visible }, 2000)
            capture(scene, config, "03-canonical-return")
        }
    }
}

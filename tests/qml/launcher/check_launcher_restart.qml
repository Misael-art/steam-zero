// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"
Item {
    id: harness
    width: 1280; height: 800
    Component { id: sceneComponent; LauncherMain {} }
    TestCase {
        name: "LauncherRestart"
        when: windowShown
        function capture(scene, config, name) {
            if (!config.capture) return
            let saved=false
            verify(scene.contentItem.grabToImage(function(result) {
                saved=result.saveToFile(config.capture + "/" + name + ".png")
            }))
            tryVerify(function() { return saved }, 3000)
        }
        function test_restore_observes_exact_session_without_launching() {
            const configRequest = new XMLHttpRequest()
            configRequest.open("GET", Qt.resolvedUrl("restart-config.json"), false)
            configRequest.send()
            const config = JSON.parse(configRequest.responseText)
            const scene = createTemporaryObject(sceneComponent, harness)
            scene.api = config.api; scene.token = config.token
            scene._start()
            tryCompare(scene, "loadState", "ready")
            const shell = scene._activeLauncherShell()
            if (config.pending) {
                wait(600)
                compare(shell.launchState, "launching")
                compare(shell.launchFocused(), false)
                capture(scene, config, "01-awaiting-exact-session")
                scene._request("GET", "/restart-control/publish", null, function() {})
            }
            tryCompare(shell, "launchState", "emulator-visible", 5000)
            compare(shell.sessionGameId, "lifetime-probe")
            compare(shell.homeFocus, "library:lifetime-probe")
            compare(shell.launchFocused(), false)
            keyClick(Qt.Key_Return)
            compare(shell.launchState, "emulator-visible")
            capture(scene, config, "02-session-restored")
            if (config.mode === "return") {
                scene._request("GET", "/restart-control/finish", null, function() {})
                tryCompare(shell, "launchState", "recovered", 5000)
                compare(shell.homeFocus, "library:lifetime-probe")
                compare(shell.gamePage, null)
                const fade = findChild(shell, "returnFadeLayer")
                verify(fade !== null)
                tryVerify(function() { return !fade.visible }, 2000)
                capture(scene, config, "03-canonical-return")
            }
        }
    }
}

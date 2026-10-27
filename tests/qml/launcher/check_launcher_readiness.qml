// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 960
    height: 640
    property var calls: []
    property var callbacks: []
    property var productWindow: null

    function reply(game, state, canPrepare) {
        return JSON.stringify({gameId: game, state: state,
            playable: state === "ready", preparing: state === "preparing",
            canPrepare: canPrepare === true, reason: state === "blocked" ? "Fixture: extração necessária" : ""})
    }
    function find(item, name) {
        if (!item)
            return null
        if (item.objectName === name)
            return item
        const children = item.children || []
        for (let i = 0; i < children.length; ++i) {
            const result = find(children[i], name)
            if (result)
                return result
        }
        return null
    }
    LauncherReadiness {
        id: status
        width: 540
        gameTitle: "Fixture"
    }
    Component {
        id: productComponent
        LauncherMain {
            visibility: Window.Windowed
            width: 960
            height: 640
        }
    }

    TestCase {
        name: "AReadinessObservation"
        when: windowShown
        function init() {
            harness.Window.window.requestActivate()
            status.active = false
            status.gameId = "first"
            status.requestFunction = function(method, path, body, done) {
                harness.calls.push({method: method, path: path, body: body})
                done(200, harness.reply(status.gameId, "blocked", true))
            }
            status.active = true
            harness.calls = []
            harness.callbacks = []
        }
        function cleanup() { status.active = false }

        function test_status_and_keyboard_prepare_without_launch() {
            compare(status.observation.state, "blocked")
            verify(status.statusText.indexOf("preparação") >= 0)
            status.requestFunction = function(method, path, body, done) {
                harness.calls.push({method: method, path: path, body: body})
                done(method === "POST" ? 202 : 200,
                    harness.reply(status.gameId, method === "POST" ? "preparing" : "blocked", method !== "POST"))
            }
            harness.calls = []
            const button = harness.find(status, "readinessAction")
            verify(button !== null && button.enabled)
            button.forceActiveFocus()
            tryCompare(button, "activeFocus", true)
            keyClick(Qt.Key_Return)
            compare(harness.calls.length, 1)
            compare(harness.calls[0].method, "POST")
            compare(harness.calls[0].path, "/prepare")
            compare(harness.calls[0].body.gameId, "first")
            compare(status.preparing, true)
            compare(button.enabled, false)
            compare(status.prepare(), false)
        }

        function test_failed_observation_data() {
            return [
                {tag: "offline", code: 0, text: ""},
                {tag: "http", code: 503, text: "{}"},
                {tag: "malformed", code: 200, text: "{"},
                {tag: "null", code: 200, text: "null"},
                {tag: "wrong-game", code: 200, text: harness.reply("outside", "ready")},
                {tag: "unconfirmed-ready", code: 200,
                    text: JSON.stringify({gameId: "first", state: "ready", playable: null})}
            ]
        }
        function test_failed_observation(data) {
            status.requestFunction = function(method, path, body, done) { done(data.code, data.text) }
            compare(status.observation.state, "unknown")
            compare(status.requestPending, false)
            compare(status.observation.canPrepare, false)
            verify(status.statusText.indexOf("não verificada") >= 0)
            status.requestFunction = function(method, path, body, done) {
                done(200, harness.reply(status.gameId, "ready"))
            }
            compare(status.observation.state, "ready")
        }

        function test_old_game_and_closed_page_callbacks_are_ignored() {
            status.requestFunction = function(method, path, body, done) { harness.callbacks.push(done) }
            compare(status.requestPending, true)
            status.gameId = "second"
            compare(harness.callbacks.length, 2)
            harness.callbacks[1](200, harness.reply("second", "ready"))
            harness.callbacks[0](200, harness.reply("first", "blocked", true))
            compare(status.observation.state, "ready")
            compare(status.observation.gameId, "second")
            status.refresh()
            status.active = false
            harness.callbacks[2](200, harness.reply("second", "blocked", true))
            compare(status.observation.state, "unknown")
        }

        function test_lost_prepare_response_is_observed_without_repeating_post() {
            status.requestFunction = function(method, path, body, done) {
                harness.calls.push({method: method})
                if (method === "POST")
                    done(0, "")
                else
                    done(200, harness.reply(status.gameId,
                        harness.calls.some(function(call) { return call.method === "POST" }) ? "ready" : "blocked", true))
            }
            harness.calls = []
            verify(status.prepare())
            compare(status.observation.state, "unknown")
            tryVerify(function() { return status.observation.state === "ready" }, 3000)
            compare(harness.calls.filter(function(call) { return call.method === "POST" }).length, 1)
            verify(harness.calls.some(function(call) { return call.method === "GET" }))
        }

        function test_duplicate_callback_is_ignored() {
            status.requestFunction = function(method, path, body, done) {
                done(200, harness.reply(status.gameId, "ready"))
                done(200, harness.reply(status.gameId, "blocked", true))
            }
            compare(status.observation.state, "ready")
        }
    }

    TestCase {
        name: "ZLauncherRootReadiness"
        when: windowShown
        function cleanup() {
            if (harness.productWindow !== null) {
                harness.productWindow.destroy()
                harness.productWindow = null
            }
        }
        function test_root_details_uses_authenticated_bridge_and_prepares_without_launching() {
            status.active = false
            harness.productWindow = productComponent.createObject(null)
            const product = harness.productWindow
            verify(product !== null)
            const fixture = new XMLHttpRequest()
            fixture.open("GET", Qt.resolvedUrl("bridge.json"), false)
            fixture.send()
            const channel = JSON.parse(fixture.responseText)
            product.api = channel.api
            product.token = channel.token
            product._start()
            product.requestActivate()
            tryCompare(product, "loadState", "ready", 5000)
            const shell = product._activeLauncherShell()
            verify(shell !== null)
            verify(shell.openGame("game"))
            const readiness = harness.find(shell, "gameReadiness")
            verify(readiness !== null)
            tryVerify(function() { return readiness.observation.state === "blocked" }, 5000)
            const button = harness.find(readiness, "readinessAction")
            verify(button !== null && button.text.indexOf("Fixture") >= 0)
            mouseClick(button)
            tryCompare(readiness, "preparing", true, 3000)
            tryVerify(function() { return readiness.observation.state === "ready" }, 5000)
            compare(shell.launchState, "idle")
            compare(shell.gamePage.gameId, "game")
        }
    }
}

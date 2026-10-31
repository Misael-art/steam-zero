// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import "../../src/steamzero/ui/qml"

Window {
    id: harness
    visible: true
    width: 800
    height: 240
    color: "transparent"
    property int failures: 0
    property int phase: 0
    property var originalObjects: []
    readonly property var input: {
        const prefix = "--native-wheel="
        for (let i = 0; i < Qt.application.arguments.length; ++i)
            if (Qt.application.arguments[i].startsWith(prefix))
                return JSON.parse(Qt.application.arguments[i].slice(prefix.length))
        return ({})
    }
    function check(value, message) {
        if (!value) { failures += 1; console.error("NATIVE-WHEEL-FAIL " + message) }
    }
    function capture(name, callback) {
        canvas.grabToImage(function(result) {
            check(result.saveToFile(input.output + "/" + name + ".png"), "save " + name)
            callback()
        })
    }
    Item {
        id: canvas
        anchors.fill: parent
        SceneRepeater { id: composition; anchors.fill: parent; layout: harness.input.layouts ? harness.input.layouts[1] : null }
    }
    Timer {
        id: step
        interval: 240
        repeat: false
        running: true
        onTriggered: {
            if (phase === 0) {
                check(composition.entryCount === 3, "three entries")
                for (let i = 0; i < 3; ++i) {
                    const item = composition.entryAt(i)
                    check(item !== null && item.sourceStatus === Image.Ready, "decoded source " + i)
                    originalObjects.push(item)
                }
                check(composition.entryAt(1).model.recipeName === "center", "selected recipe")
                capture("initial", function() {
                    for (let i = 0; i < 42; ++i)
                        composition.layout = harness.input.layouts[i % 3]
                    phase = 1; step.restart()
                })
            } else if (phase === 1) {
                for (let i = 0; i < 3; ++i) {
                    const item = composition.entryAt(i)
                    check(item === originalObjects[i], "stable item identity " + i)
                    check(item.sourceDecodeCount === 1, "no image reopening " + i)
                    check(Math.abs(item.x - item.model.x) < 0.1, "latest geometry " + i)
                }
                check(composition.entryAt(2).model.recipeName === "center", "latest selected recipe")
                capture("rapid-final", function() {
                    composition.layout = harness.input.layouts[3]
                    phase = 2; step.restart()
                })
            } else if (phase === 2) {
                capture("silhouette", function() {
                    const failed = JSON.parse(JSON.stringify(harness.input.layouts[3]))
                    failed.entries[0].source = harness.input.corrupt
                    composition.layout = failed
                    phase = 3; step.restart()
                })
            } else {
                check(composition.entryAt(0).renderState === "decodeFailed", "invalid decode is never rendered success")
                check(composition.entryAt(0).renderDiagnostic !== "", "decode recovery is explicit")
                console.log("NATIVE-WHEEL-RESULT " + JSON.stringify({
                    failures: failures,
                    renderer: composition.entryAt(1).softwareEffectsUnavailable ? "software-partial" : "rhi",
                    decoded: originalObjects.length,
                    finalSelection: composition.entryAt(1).model.key,
                    decodeFailure: composition.entryAt(0).renderState
                }))
                Qt.exit(failures === 0 ? 0 : 1)
            }
        }
    }
    Timer { interval: 10000; running: true; onTriggered: { console.error("NATIVE-WHEEL-FAIL timeout"); Qt.exit(1) } }
}

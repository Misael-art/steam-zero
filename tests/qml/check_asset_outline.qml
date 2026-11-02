// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import "../../src/steamzero/ui/qml"

Window {
    width: 360
    height: 180
    visible: true
    color: "transparent"
    readonly property var input: {
        for (const arg of Qt.application.arguments)
            if (arg.startsWith("--outline=")) return JSON.parse(arg.slice(10))
        return ({})
    }
    Item {
        id: canvas
        width: 200
        height: 100
        AssetRecipePreview {
            anchors.fill: parent
            source: input.source || ""
            recipe: ({source: "logo", nodes: [{type: "outline", parameters: {
                width: 4, color: "#ffffff", opacity: 1}}]})
        }
    }
    SceneRecipeImage {
        id: scaled
        x: 230
        model: ({id: "demand", x: 230, y: 40, width: 40, height: 20,
            scale: 1.5, opacity: 1, visible: true, source: input.source || ""})
    }
    Timer {
        interval: 400
        running: true
        onTriggered: canvas.grabToImage(function(result) {
            if (!result.saveToFile(input.output)) Qt.exit(1)
            console.log("OUTLINE-DEMAND " + JSON.stringify({
                dpr: Screen.devicePixelRatio,
                width: scaled.decodeDemand.width, height: scaled.decodeDemand.height,
                state: scaled.renderState
            }))
            Qt.exit(0)
        })
    }
}

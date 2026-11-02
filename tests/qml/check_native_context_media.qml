import QtQuick
import QtQuick.Window
import "ENGINE_IMPORT"

Window {
    id: root
    visible: true
    width: 640
    height: 240

    property string label: {
        for (const argument of Qt.application.arguments)
            if (argument.startsWith("--label=")) return argument.slice(8)
        return ""
    }
    SteamComboBox {
        id: picker
        x: 16
        y: 16
        width: 608
        model: [root.label]
    }
    SceneEsdeView {
        id: scene
        y: 80
        width: 600
        height: 100
        viewData: ({id: "text", elements: [{id: "metadata", kind: "text", text: root.label,
            layout: {width: 1, height: 1}}]})
    }
    Timer {
        interval: 200
        running: true
        onTriggered: picker.popup.open()
    }
    Timer {
        interval: 800
        running: true
        onTriggered: {
            const popupItem = picker.popup.contentItem.itemAtIndex(0)
            console.log("NATIVE-CONTEXT-LABEL " + JSON.stringify({
                literal: picker.contentItem.textFormat === Text.PlainText,
                sceneLiteral: scene.elementAt(0).textFormat === Text.PlainText,
                popupLiteral: popupItem !== null && popupItem.contentItem.textFormat === Text.PlainText,
                text: picker.contentItem.text
            }))
            Qt.exit(0)
        }
    }
}

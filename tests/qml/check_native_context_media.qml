import QtQuick
import QtQuick.Window
import QtTest
import "ENGINE_IMPORT"
import "ENGINE_IMPORT/launcher" as Launcher

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
    Launcher.LauncherMain {
        id: launcher
        visibility: Window.Windowed
        width: 800
        height: 600
    }
    property bool searchTitleLiteral: false
    ThemeEditorPanel {
        id: editor
        width: 800
        height: 600
        visible: false
        request: function(method, path, payload, callback, errorCallback) {
            callback({themes: []})
        }
        requestAction: function(action, payload, callback, errorCallback) {
            callback({themeId: "org.example.metadata", name: root.label,
                author: root.label, license: root.label, version: "1.0.0",
                hasPreservedData: true, alreadyInstalled: false})
        }
    }
    TestCase { id: lookup; when: false }
    function findText(item, exact) {
        if (!item) return null
        if (item.textFormat !== undefined && typeof item.text === "string"
                && (exact ? item.text === root.label
                    : item.text !== root.label && item.text.indexOf(root.label) >= 0))
            return item
        const children = item.children || []
        for (let i = 0; i < children.length; ++i) {
            const hit = findText(children[i], exact)
            if (hit) return hit
        }
        return null
    }
    Timer {
        interval: 200
        running: true
        onTriggered: {
            launcher.searching = true
            launcher.searchResults = [{id: "owned-result", title: root.label, coverUrl: ""}]
            picker.popup.open()
            editor.packageImportSource = "/owned/metadata.zip"
            editor.inspectPackageImport()
            editor.packageImportNotice = root.label
            lookup.findChild(editor, "themeImportPackageDialog").open()
        }
    }
    Timer {
        interval: 450
        running: true
        onTriggered: {
            const result = root.findText(launcher.contentItem, true)
            root.searchTitleLiteral = result !== null && result.textFormat === Text.PlainText
            launcher.searchQuery = root.label
            launcher.searchResults = []
        }
    }
    Timer {
        interval: 800
        running: true
        onTriggered: {
            const popupItem = picker.popup.contentItem.itemAtIndex(0)
            const query = root.findText(launcher.contentItem, false)
            const metadata = lookup.findChild(editor, "packageImportPreviewLabel")
            const notice = lookup.findChild(editor, "packageImportNoticeLabel")
            console.log("NATIVE-CONTEXT-LABEL " + JSON.stringify({
                literal: picker.contentItem.textFormat === Text.PlainText,
                sceneLiteral: scene.elementAt(0).textFormat === Text.PlainText,
                popupLiteral: popupItem !== null && popupItem.contentItem.textFormat === Text.PlainText,
                searchTitleLiteral: root.searchTitleLiteral,
                searchQueryLiteral: query !== null && query.textFormat === Text.PlainText,
                importLiteral: metadata !== null && metadata.textFormat === Text.PlainText
                    && metadata.text.indexOf(root.label) >= 0,
                importNoticeLiteral: notice !== null && notice.textFormat === Text.PlainText
                    && notice.text === root.label,
                text: picker.contentItem.text
            }))
            Qt.exit(0)
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "../../src/steamzero/ui/qml"

// Fechar a janela da Central com um tema em edição: a janela espera a escolha
// do diálogo do editor em vez de perder o rascunho.
Main {
    id: window
    visible: true
    width: 949
    height: 593
    property int failures: 0
    property int step: 0
    property var editor: null

    // Mantém o processo vivo depois que a janela principal fecha de verdade.
    Window { visible: true; width: 1; height: 1 }

    function check(condition, message) {
        if (!condition) {
            failures += 1
            console.error("FAIL: " + message)
        }
    }

    function find(item, name) {
        if (!item)
            return null
        if (item.objectName === name)
            return item
        const groups = [item.children || [], item.contentChildren || []]
        if (item.contentItem)
            groups.push([item.contentItem])
        for (let g = 0; g < groups.length; g++) {
            for (let i = 0; i < groups[g].length; i++) {
                const found = find(groups[g][i], name)
                if (found)
                    return found
            }
        }
        return null
    }

    function openDirty() {
        editor._openEditor("s1", {
            "id": "org.steamzero.close-guard", "name": "Rascunho", "version": "1.0.0",
            "author": "SteamZero contributors", "license": "CC0-1.0"
        }, {
            "schemaVersion": 1, "themeId": "org.steamzero.close-guard", "themeVersion": "1.0.0",
            "highContrast": false, "reducedMotion": true, "resolved": {"color": {}}
        }, null, null, null, null, false)
        editor.editorDirty = true
    }

    readonly property var scenario: [
        function() {
            editor = find(window.contentItem, "themeEditorPanel")
            check(editor !== null, "painel do editor ausente na Central")
            openDirty()
            window.sectionIndex = 0
            window.close()
        },
        function() {
            check(window.visible === true, "janela fechou com rascunho sem perguntar")
            check(window.sectionIndex === window.sectionIndexOf("themes"),
                  "fechar com rascunho precisa levar ao editor")
            check(editor.draftExitDialogOpen === true, "diálogo de saída não abriu")
            const keep = find(window.Overlay.overlay, "themeEditorDraftContinue")
            check(keep !== null, "Continuar editando ausente")
            keep.clicked()
        },
        function() {
            check(window.visible === true, "Continuar editando fechou a janela")
            check(editor.editorSessionId === "s1" && editor.editorDirty === true,
                  "Continuar editando perdeu o rascunho")
            check(window.closeAfterThemeDraft === false, "fechamento ficou armado após continuar")
            window.close()
        },
        function() {
            check(window.visible === true, "segundo fechar não perguntou")
            const discard = find(window.Overlay.overlay, "themeEditorDraftDiscard")
            check(discard !== null, "Descartar ausente")
            discard.clicked()
        },
        function() {
            check(editor.editorSessionId === "", "Descartar não encerrou a sessão")
            check(window.visible === false, "janela não fechou após a escolha")
        }
    ]

    Timer {
        interval: 250
        repeat: true
        running: true
        onTriggered: {
            const current = window.scenario[window.step]
            if (!current) {
                stop()
                Qt.exit(window.failures === 0 ? 0 : 1)
                return
            }
            try {
                current()
            } catch (error) {
                window.check(false, "passo " + window.step + " lançou: " + error)
            }
            window.step += 1
        }
    }
}

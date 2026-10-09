// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "../../src/steamzero/ui/qml"

// Saída do editor de temas com rascunho ou pedido em voo, e histórico das
// edições de metadados. A ponte é substituída por uma fila que o próprio
// harness responde, para controlar a ordem de cada resposta.
Window {
    id: harness
    visible: true
    width: 1100
    height: 720
    color: "#071019"
    property int failures: 0
    property var pending: []
    property var sent: []

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

    function manifest(name) {
        return {
            "id": "org.steamzero.draft-guard", "name": name, "version": "1.0.0",
            "author": "SteamZero contributors", "license": "CC0-1.0"
        }
    }

    function open(sessionId) {
        panel._openEditor(sessionId, manifest("Original"), {
                              "schemaVersion": 1, "themeId": "org.steamzero.draft-guard",
                              "themeVersion": "1.0.0", "highContrast": false,
                              "reducedMotion": true, "resolved": {"color": {}}
                          },
                          null, null, null, null, false)
    }

    function take(actionId) {
        check(pending.length > 0, "nenhum pedido pendente; esperado " + actionId)
        if (pending.length === 0)
            return null
        const entry = pending.shift()
        check(entry.actionId === actionId,
              "pedido inesperado: " + entry.actionId + "; esperado " + actionId)
        return entry
    }

    function count(actionId) {
        let total = 0
        for (let i = 0; i < sent.length; i++)
            if (sent[i] === actionId)
                total += 1
        return total
    }

    ThemeEditorPanel {
        id: panel
        anchors.fill: parent
        compactLayout: false
        request: function(_method, _path, _payload, callback, _errorCallback) {
            callback({"themes": []})
        }
        requestAction: function(actionId, payload, callback, errorCallback) {
            harness.sent.push(actionId)
            harness.pending.push({
                actionId: actionId, payload: payload,
                callback: callback, errorCallback: errorCallback
            })
            return true
        }
    }

    Timer {
        id: steps
        interval: 60
        repeat: true
        property int index: 0
        onTriggered: {
            const step = harness.scenario[index]
            if (!step) {
                stop()
                Qt.exit(harness.failures === 0 ? 0 : 1)
                return
            }
            // Um passo que lança conta como falha e não repete: sem isto o
            // harness giraria no mesmo passo até o timeout.
            try {
                step()
            } catch (error) {
                harness.check(false, "passo " + index + " lançou: " + error)
            }
            index += 1
        }
    }

    property var scenario: [
        function() {
            // 1. Metadado editado: o histórico devolvido habilita Desfazer.
            harness.pending = []
            harness.sent = []
            open("s1")
            check(panel.editorHasUnsavedDraft === false, "editor recém-aberto não tem rascunho")
            panel.setMetadata("name", "Original")
            check(count("theme.editor.set-metadata") === 0,
                  "valor idêntico não pode virar edição")
            panel.setMetadata("name", "Renomeado")
            const edit = take("theme.editor.set-metadata")
            edit.callback({
                "manifest": manifest("Renomeado"),
                "history": {"canUndo": true, "canRedo": false, "dirty": true}
            })
            check(panel.editorManifest.name === "Renomeado", "manifesto não refletiu a edição")
            check(panel.editorHistory.canUndo === true,
                  "histórico da edição de metadado não foi consumido")
            check(panel.editorDirty === true, "edição de metadado precisa sujar o rascunho")
            const undo = find(panel, "themeEditorUndo")
            check(undo !== null && undo.enabled === true,
                  "Desfazer precisa habilitar após editar metadado")
        },
        function() {
            // 2. Fechar com rascunho pergunta; Continuar preserva tudo.
            check(panel.requestCloseEditor() === false, "fechar com rascunho não pode encerrar")
            check(panel.editorSessionId === "s1", "sessão foi encerrada sem escolha")
        },
        function() {
            check(panel.draftExitDialogOpen === true, "diálogo de saída não abriu")
            const keep = find(harness.Overlay.overlay, "themeEditorDraftContinue")
            check(keep !== null, "botão Continuar editando ausente")
            if (keep) {
                check(keep.height >= 48, "alvo de Continuar editando menor que 48 px")
                keep.clicked()
            }
        },
        function() {
            check(panel.draftExitDialogOpen === false, "Continuar editando não fechou o diálogo")
            check(panel.editorSessionId === "s1" && panel.editorDirty === true,
                  "Continuar editando perdeu o rascunho")
            check(count("theme.editor.cancel") === 0, "Continuar editando cancelou a sessão")
        },
        function() {
            // 3. Salvar que falha preserva o rascunho e explica.
            panel.requestCloseEditor()
            panel.saveDraftAndClose()
            check(panel.editorCloseSaving === true, "save em andamento não foi sinalizado")
            panel.saveDraftAndClose()
            check(count("theme.editor.save") === 1, "save duplicado durante o save em voo")
            take("theme.editor.save").errorCallback("disco cheio.")
            check(panel.editorSessionId === "s1", "save falho encerrou a sessão")
            check(panel.editorDirty === true, "save falho limpou o rascunho")
            check(panel.editorCloseSaving === false, "save falho deixou o diálogo travado")
            check(panel.editorCloseNotice.indexOf("disco cheio") >= 0,
                  "motivo do save falho não chegou ao usuário")
        },
        function() {
            check(panel.draftExitDialogOpen === true, "diálogo fechou apesar do save falho")
            // 4. Salvar que conclui fecha sem cancelar a sessão.
            panel.saveDraftAndClose()
            const save = take("theme.editor.save")
            check(save.payload.sessionId === "s1", "save foi para outra sessão")
            save.callback({"history": {"canUndo": true, "canRedo": false, "dirty": false}})
            check(panel.editorSessionId === "", "save concluído não fechou o editor")
            check(count("theme.editor.cancel") === 0, "save concluído não pode descartar a sessão")
        },
        function() {
            check(panel.draftExitDialogOpen === false, "diálogo ficou aberto após salvar")
            // 5. Pedido em voo também protege a saída; Descartar cancela a sessão e a
            //    resposta atrasada não reabre nem altera a sessão seguinte.
            harness.pending = []
            harness.sent = []
            open("s2")
            panel.setMetadata("author", "Outra pessoa")
            check(panel.editorHasUnsavedDraft === true, "pedido em voo não protegeu a saída")
            check(panel.requestCloseEditor() === false, "fechou com pedido em voo")
        },
        function() {
            const late = take("theme.editor.set-metadata")
            panel.discardDraftAndClose()
            check(panel.editorSessionId === "", "Descartar não fechou o editor")
            open("s3")
            late.callback({
                "manifest": manifest("Fantasma"),
                "history": {"canUndo": true, "canRedo": false, "dirty": true}
            })
            check(panel.editorSessionId === "s3", "resposta atrasada trocou a sessão")
            check(panel.editorManifest.name === "Original",
                  "resposta atrasada alterou outra sessão")
            check(panel.editorDirty === false, "resposta atrasada sujou outra sessão")
        },
        function() {
            check(count("theme.editor.cancel") === 1, "Descartar precisa cancelar a sessão no backend")
            // 6. Sem rascunho, fechar é imediato e sem pergunta.
            check(panel.requestCloseEditor() === true, "fechar limpo não pode perguntar")
            check(panel.editorSessionId === "", "fechar limpo não encerrou")
            check(panel.draftExitDialogOpen === false, "fechar limpo abriu o diálogo")
        }
    ]

    Component.onCompleted: steps.start()
}

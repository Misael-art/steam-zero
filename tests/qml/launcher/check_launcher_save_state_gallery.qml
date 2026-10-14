// SPDX-License-Identifier: GPL-3.0-or-later
//
// Prova o foco, fallback e dispatch semântico da galeria; nenhum emulador é
// controlado pelo QML.
import QtQuick
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 800

    property int failures: 0
    property int checks: 0
    property var requested: []
    property bool closed: false
    property var overlayActionRequests: []
    property var overlaySaveRequests: []

    function check(condition, message) {
        checks += 1
        if (!condition) {
            failures += 1
            console.error("FAIL #" + checks + ": " + message)
        }
    }

    readonly property var readyModel: ({
        "schemaVersion": 1,
        "state": "ready",
        "available": true,
        "saveAvailable": true,
        "loadAvailable": true,
        "reason": "",
        "entries": [
            {"slot": 1, "timestamp": "2026-09-13T20:00:00Z",
             "playtimeSeconds": 600, "thumbnailUrl": "asset://save/1.png",
             "thumbnailFallback": false, "compatibility": "native",
             "available": true, "backupAvailable": true, "reason": ""},
            {"slot": 2, "timestamp": "2026-09-13T20:10:00Z",
             "playtimeSeconds": 900, "thumbnailUrl": "",
             "thumbnailFallback": true, "compatibility": "unknown",
             "available": true, "backupAvailable": false, "reason": ""}
        ]
    })

    // D-20: read model de uma sessão cujo adapter não oferece save-state (nenhum
    // save existente): a galeria não abre e não há slot escolhível na tela.
    readonly property var noSaveOverlayModel: ({
        "sessionId": "session-1",
        "gameId": "castlevania",
        "state": "running",
        "visible": true,
        "focusedAction": "saveState",
        "actions": [
            {"id": "saveState", "label": "Salvar estado", "enabled": true, "reason": ""},
            {"id": "loadState", "label": "Carregar estado", "enabled": true, "reason": ""}
        ],
        "saveStates": {"state": "unavailable", "available": false, "saveAvailable": false,
                       "loadAvailable": false, "reason": "O adapter não oferece save-state.",
                       "entries": []},
        "criticalError": null,
        "diagnostic": null
    })

    LauncherSaveStateGallery {
        id: gallery
        anchors.fill: parent
        onSlotRequested: function(actionId, slot) {
            harness.requested.push({"actionId": actionId, "slot": slot})
        }
        onCloseRequested: harness.closed = true
    }

    LauncherSessionOverlay {
        id: sessionOverlay
        anchors.fill: parent
        gameTitle: "Castlevania Legends"
        onActionRequested: function(actionId) {
            harness.overlayActionRequests.push(actionId)
        }
        onSaveStateRequested: function(actionId, slot) {
            harness.overlaySaveRequests.push({"actionId": actionId, "slot": slot})
        }
    }

    Timer {
        interval: 100
        running: true
        repeat: false
        onTriggered: {
            gallery.setModel(harness.readyModel)
            gallery.openGallery("loadState")
            // O carimbo ISO não pode chegar cru ao jogador.
            const stamp = gallery.formatTimestamp("2026-09-17T23:31:11.913622+00:00")
            harness.check(/^\d{2}\/\d{2}\/2026 \d{2}:\d{2}$/.test(stamp),
                          "o carimbo precisa ser formatado como data e hora: " + stamp)
            harness.check(gallery.formatTimestamp("") === "Data indisponível"
                          && gallery.formatTimestamp("ontem") === "Data indisponível",
                          "carimbo ausente ou inválido precisa ser dito, não inventado")
            harness.check(gallery.compatibilityLabel("native") === "formato nativo"
                          && gallery.compatibilityLabel("") === "compatibilidade desconhecida",
                          "a compatibilidade precisa de rótulo legível")
            harness.check(gallery.visible, "a galeria disponível precisa abrir")
            harness.check(gallery.entries.length === 2, "a galeria precisa renderizar os slots")
            harness.check(gallery.selectedEntry.slot === 1, "o primeiro slot precisa receber foco")
            harness.check(gallery.activateFocused(), "slot compatível precisa aceitar seleção")
            harness.check(harness.requested.length === 1
                          && harness.requested[0].actionId === "loadState"
                          && harness.requested[0].slot === 1,
                          "a seleção precisa publicar actionId e slot")
            harness.check(gallery.move("right"), "a navegação horizontal precisa mover o foco")
            harness.check(gallery.selectedEntry.slot === 2, "o segundo slot precisa receber foco")
            gallery.mode = "saveState"
            harness.check(gallery.activateFocused(), "save-state deve aceitar um slot vazio")
            harness.check(harness.requested[1].actionId === "saveState"
                          && harness.requested[1].slot === 2,
                          "salvar deve preservar o slot selecionado")
            gallery.setModel({"state": "unavailable", "available": false,
                              "saveAvailable": false, "loadAvailable": false,
                              "reason": "O adapter não oferece save-state.", "entries": []})
            harness.check(gallery.entries.length === 0, "fallback sem mídia não pode inventar slots")
            harness.check(gallery.closeGallery(), "fechar a galeria deve ser acionável")
            harness.check(harness.closed, "fechar deve avisar o overlay")

            // D-20: sem galeria, o toque em Salvar estado ainda precisa chegar ao
            // adapter com um slot inteiro — nunca pelo despacho sem slot, que o
            // adapter recusa e transforma o toque do jogador em uma recusa.
            sessionOverlay.openOverlay(harness.noSaveOverlayModel)
            harness.check(!sessionOverlay.saveGalleryOpen,
                          "sem save disponível a galeria não pode abrir")
            harness.check(sessionOverlay.focusAction("saveState"),
                          "saveState habilitado precisa receber foco mesmo sem galeria")
            harness.check(sessionOverlay.activateFocused() === true,
                          "saveState habilitado precisa despachar mesmo sem galeria")
            harness.check(harness.overlayActionRequests.length === 0,
                          "saveState sem galeria não pode usar o despacho sem slot (D-20)")
            harness.check(harness.overlaySaveRequests.length === 1
                          && harness.overlaySaveRequests[0].actionId === "saveState"
                          && harness.overlaySaveRequests[0].slot === 0
                          && Number.isInteger(harness.overlaySaveRequests[0].slot),
                          "saveState sem galeria deve despachar saveStateRequested com o slot livre padrão 0")

            // loadState sem save existente não tem o que carregar: comportamento
            // preservado, nenhum slot inventado (D-20 trata só o caminho de salvar).
            harness.check(sessionOverlay.focusAction("loadState"),
                          "loadState precisa continuar focável")
            harness.check(sessionOverlay.activateFocused() === true,
                          "loadState habilitado precisa despachar")
            harness.check(harness.overlayActionRequests.length === 1
                          && harness.overlayActionRequests[0] === "loadState"
                          && harness.overlaySaveRequests.length === 1,
                          "loadState mantém o despacho original; slot 0 é exclusivo do fallback de salvar")

            console.info("checks=" + harness.checks + " failures=" + harness.failures)
            Qt.exit(harness.failures === 0 ? 0 : 1)
        }
    }
}

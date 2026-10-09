// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Superfície visual do OSD de sessão. O componente não executa operações nem
// interpreta capabilities: só desenha o read model allowlisted e encaminha a
// ação semântica escolhida para a ponte.

import QtQuick
import QtQuick.Controls

Item {
    id: overlay

    property var overlayModel: null
    property var accessibility: ({"highContrast": false, "visualScale": 1.0,
        "reducedMotion": false})
    property string gameTitle: ""
    property string bridgeError: ""
    property string localError: ""
    property bool overlayOpen: false
    property bool saveGalleryOpen: false
    property bool peripheralOpen: false
    property bool requestPending: false
    property int selectedIndex: _initialIndex()
    readonly property var actions: overlayModel && Array.isArray(overlayModel.actions)
        ? _visibleActions(overlayModel.actions) : []
    readonly property var saveStates: overlayModel && overlayModel.saveStates
        ? overlayModel.saveStates : null
    readonly property var peripherals: overlayModel && overlayModel.peripherals
        ? overlayModel.peripherals : null
    readonly property var criticalError: overlayModel
        ? overlayModel.criticalError : null
    readonly property var journeyAppearance: overlayModel && overlayModel.journeyAppearance
        ? overlayModel.journeyAppearance : ({})
    readonly property var journeyTheme: journeyAppearance.theme || ({})
    readonly property var themeTokens: journeyTheme.resolved || ({})
    readonly property var themeColors: themeTokens.color || ({})
    readonly property var sceneSurfaceBook: journeyTheme.sceneSurfaces || ({})
    readonly property var sceneSurfaceSlots: sceneSurfaceBook.slots || ({})
    readonly property var sceneSurfaceComponents: sceneSurfaceBook.components || ({})
    readonly property bool highContrast: !!(accessibility && accessibility.highContrast)
        || journeyTheme.highContrast === true
    readonly property bool reducedMotion: !!(accessibility && accessibility.reducedMotion)
        || journeyTheme.reducedMotion === true
    readonly property real visualScale: accessibility && Number(accessibility.visualScale) > 0
        ? Number(accessibility.visualScale) : 1.0
    readonly property string activeSurfaceSlot: journeyAppearance.stageId === "saves"
        ? "saveStates" : journeyAppearance.stageId === "bezel" ? "bezel" : "osd"
    readonly property var activeSurface: _surfaceComponent(activeSurfaceSlot)
    readonly property color backgroundColor: highContrast ? "#000000"
        : _safeColor(themeColors.background, "#071019")
    readonly property color panelColor: highContrast ? "#000000"
        : _safeColor(themeColors.surface, "#101c2b")
    readonly property color accentColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.accent, "#7dd3fc")
    readonly property color primaryTextColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.text, "#f8fafc")
    readonly property color mutedTextColor: highContrast ? "#e8e8e8"
        : _safeColor(themeColors.textMuted, "#a8b8ca")
    readonly property color borderColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.border, "#2b4963")
    readonly property int motionDuration: reducedMotion ? 0
        : Math.max(0, Math.min(1000, Number(themeTokens.motion
            && themeTokens.motion.durationNormal || 160)))
    readonly property string currentActionId: selectedIndex >= 0 && selectedIndex < actions.length
        ? String(actions[selectedIndex].id || "") : ""

    signal actionRequested(string actionId)
    signal saveStateRequested(string actionId, int slot)
    signal discRequested(string discId)
    signal appearanceStageRequested(string stageId)
    signal closeRequested()

    function _safeColor(value, fallback) {
        if (typeof value !== "string")
            return fallback
        const candidate = value.trim()
        return /^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(candidate)
            ? candidate : fallback
    }

    function _surfaceComponent(slotId) {
        const slot = sceneSurfaceSlots[String(slotId)]
        return slot && typeof slot.component === "string"
            ? sceneSurfaceComponents[slot.component] || null : null
    }

    function _visibleActions(source) {
        let result = source
        if (activeSurface && Array.isArray(activeSurface.items) && activeSurface.items.length > 0) {
            result = source.filter(function(action) {
                return activeSurface.items.indexOf(String(action.id || "")) >= 0
            })
        }
        if (activeSurface && Number(activeSurface.maxItems) > 0)
            result = result.slice(0, Number(activeSurface.maxItems))
        return result
    }

    function _initialIndex() {
        if (!actions.length)
            return 0
        const requested = String(overlayModel.focusedAction || "")
        for (let i = 0; i < actions.length; ++i)
            if (String(actions[i].id || "") === requested)
                return i
        return 0
    }

    function setModel(value) {
        // O estado da sessão é republicado enquanto o overlay está aberto. A
        // escolha do usuário sobrevive à atualização: voltar ao foco inicial a
        // cada leitura desfazia a seta antes do Enter e deixava Pausar e Sair
        // inalcançáveis pelo teclado.
        const current = overlay.overlayOpen && selectedIndex >= 0 && selectedIndex < actions.length
            ? String(actions[selectedIndex].id || "") : ""
        overlay.overlayModel = value
        if (current === "" || !overlay.focusAction(current))
            overlay.selectedIndex = _initialIndex()
        if (overlay.saveGalleryOpen)
            saveGallery.setModel(overlay.saveStates)
        if (overlay.peripheralOpen)
            peripheralSurface.setModel(overlay.peripherals)
        overlay.localError = ""
    }

    function openOverlay(value) {
        if (value !== undefined)
            setModel(value)
        overlay.overlayOpen = true
        overlay.saveGalleryOpen = false
        overlay.peripheralOpen = false
        saveGallery.visible = false
        peripheralSurface.visible = false
        overlay.forceActiveFocus()
    }

    function closeOverlay() {
        if (!overlay.overlayOpen)
            return false
        overlay.overlayOpen = false
        overlay.saveGalleryOpen = false
        overlay.peripheralOpen = false
        saveGallery.visible = false
        peripheralSurface.visible = false
        exitConfirmation.close()
        overlay.localError = ""
        overlay.closeRequested()
        return true
    }

    readonly property string focusedReason: {
        const action = selectedIndex >= 0 && selectedIndex < actions.length
            ? actions[selectedIndex] : null
        if (!action || action.enabled === true)
            return ""
        return qsTr("%1: %2").arg(String(action.label || action.id || ""))
            .arg(_text(action.reason, qsTr("indisponível nesta sessão.")))
    }

    function stateLabel(state) {
        const labels = {
            "launching": qsTr("iniciando"), "running": qsTr("em jogo"),
            "suspending": qsTr("pausando"), "suspended": qsTr("pausado"),
            "resuming": qsTr("retomando"), "closing": qsTr("encerrando")
        }
        return labels[String(state || "")] || qsTr("indisponível")
    }

    function focusAction(actionId) {
        for (let i = 0; i < actions.length; ++i) {
            if (String(actions[i].id || "") !== String(actionId))
                continue
            overlay.selectedIndex = i
            return true
        }
        return false
    }

    function move(direction) {
        if (actions.length === 0)
            return false
        let step = (direction === "left" || direction === "up") ? -1 : 1
        let next = overlay.selectedIndex
        for (let count = 0; count < actions.length; ++count) {
            next = (next + step + actions.length) % actions.length
            if (actions[next] !== undefined) {
                overlay.selectedIndex = next
                return true
            }
        }
        return false
    }

    function activateFocused() {
        if (requestPending || selectedIndex < 0 || selectedIndex >= actions.length)
            return false
        const action = actions[selectedIndex]
        if (!action || action.enabled !== true) {
            overlay.localError = action && action.reason
                ? String(action.reason)
                : qsTr("Esta ação está indisponível nesta sessão.")
            return false
        }
        if ((String(action.id) === "saveState" || String(action.id) === "loadState")
                && overlay.saveStates
                && (overlay.saveStates.saveAvailable === true
                    || overlay.saveStates.loadAvailable === true)) {
            overlay.saveGalleryOpen = true
            saveGallery.setModel(overlay.saveStates)
            saveGallery.openGallery(String(action.id))
            overlay.appearanceStageRequested("saves")
            return true
        }
        if (String(action.id) === "disc" && overlay.peripherals
                && overlay.peripherals.available === true) {
            overlay.peripheralOpen = true
            peripheralSurface.setModel(overlay.peripherals)
            peripheralSurface.openSurface()
            return true
        }
        if (String(action.id) === "exit") {
            exitConfirmation.open()
            return true
        }
        overlay.localError = ""
        overlay.actionRequested(String(action.id))
        return true
    }

    function closeSaveGallery() {
        if (!overlay.saveGalleryOpen)
            return false
        overlay.saveGalleryOpen = false
        saveGallery.visible = false
        overlay.forceActiveFocus()
        overlay.appearanceStageRequested(
            overlay.overlayModel && overlay.overlayModel.state === "suspended" ? "pause" : "osd")
        return true
    }

    function closePeripheralSurface() {
        if (!overlay.peripheralOpen)
            return false
        overlay.peripheralOpen = false
        peripheralSurface.visible = false
        overlay.forceActiveFocus()
        return true
    }

    function _text(value, fallback) {
        return typeof value === "string" && value.length > 0 ? value : fallback
    }

    visible: overlay.overlayOpen
    focus: overlay.overlayOpen
    // A sessão pode deixar a página de detalhes visível no mesmo frame em que
    // o modal abre. Este é um limite de composição, não só de foco: manter o
    // overlay numa camada explícita e recortada evita que o conteúdo abaixo
    // atravesse a superfície durante a troca de estado.
    z: 100
    clip: true
    layer.enabled: true

    Rectangle {
        objectName: "sessionOverlayBackdrop"
        anchors.fill: parent
        // O OSD precisa ser uma superfície legível sobre a página e sobre
        // qualquer janela de retorno. Opacidade total impede vazamento de
        // títulos/metadados por trás do contraste cinematográfico.
        color: overlay.backgroundColor
        opacity: overlay.overlayOpen ? 1 : 0
        visible: overlay.overlayOpen && !overlay.saveGalleryOpen && !overlay.peripheralOpen
        Behavior on opacity {
            NumberAnimation { duration: overlay.motionDuration }
        }
    }

    Rectangle {
        id: panel
        objectName: "sessionOverlayPanel"
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 900)
        height: Math.min(parent.height - 64, 650)
        radius: 18
        color: overlay.panelColor
        border.width: overlay.highContrast ? 3 : 1
        border.color: overlay.borderColor
        visible: overlay.overlayOpen && !overlay.saveGalleryOpen && !overlay.peripheralOpen
        z: 1
        opacity: 1

        Column {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 18

            Row {
                width: parent.width
                spacing: 18

                Column {
                    width: parent.width - closeButton.width - 18
                    spacing: 4
                    Text {
                        text: qsTr("CONTROLE DA SESSÃO")
                        color: overlay.accentColor
                        font.pixelSize: 13 * overlay.visualScale
                        font.bold: true
                    }
                    Text {
                        text: overlay.gameTitle !== "" ? overlay.gameTitle
                            : _text(overlay.overlayModel ? overlay.overlayModel.gameId : "",
                                    qsTr("Jogo em execução"))
                        color: overlay.primaryTextColor
                        font.pixelSize: 26 * overlay.visualScale
                        font.bold: true
                        elide: Text.ElideRight
                        width: parent.width
                    }
                }

                Rectangle {
                    id: closeButton
                    width: 116
                    height: 44
                    radius: 8
                    color: overlay.panelColor
                    border.width: activeFocus ? 3 : 1
                    border.color: activeFocus ? overlay.accentColor : overlay.borderColor
                    Accessible.name: qsTr("Fechar controle da sessão")
                    Accessible.role: Accessible.Button
                    Text {
                        anchors.centerIn: parent
                        text: qsTr("Fechar")
                        color: overlay.primaryTextColor
                        font.pixelSize: 14 * overlay.visualScale
                    }
                    Accessible.onPressAction: overlay.closeOverlay()
                    TapHandler { onTapped: overlay.closeOverlay() }
                }
            }

            Row {
                spacing: 12
                Text {
                    text: qsTr("Estado: %1").arg(overlay.stateLabel(overlay.overlayModel
                        ? overlay.overlayModel.state : ""))
                    color: overlay.mutedTextColor
                    font.pixelSize: 14 * overlay.visualScale
                }
                Text {
                    visible: overlay.requestPending
                    text: qsTr("Atualizando…")
                    color: overlay.accentColor
                    font.pixelSize: 14 * overlay.visualScale
                }
            }

            Grid {
                id: actionGrid
                width: parent.width
                columns: 4
                rowSpacing: 10
                columnSpacing: 10

                Repeater {
                    model: overlay.actions
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: (actionGrid.width - actionGrid.columnSpacing * 3) / 4
                        height: 58
                        radius: 8
                        color: modelData.enabled === true
                            ? (index === overlay.selectedIndex ? overlay.accentColor : overlay.panelColor)
                            : (index === overlay.selectedIndex ? "#3b2f20" : overlay.backgroundColor)
                        opacity: modelData.enabled === true ? 1 : 0.62
                        border.width: index === overlay.selectedIndex ? 3 : 1
                        border.color: index === overlay.selectedIndex
                            ? (modelData.enabled === true ? overlay.accentColor : "#fbbf24")
                            : overlay.borderColor
                        Accessible.name: String(modelData.label || modelData.id || "")
                        Accessible.role: Accessible.Button
                        Accessible.description: modelData.enabled === true
                            ? qsTr("Ação disponível")
                            : String(modelData.reason || qsTr("Ação indisponível"))
                        Text {
                            anchors.fill: parent
                            anchors.margins: 8
                            text: String(modelData.label || modelData.id || "")
                            color: modelData.enabled === true
                                ? overlay.primaryTextColor : overlay.mutedTextColor
                            font.pixelSize: 13 * overlay.visualScale
                            font.bold: index === overlay.selectedIndex
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.Wrap
                        }
                        Accessible.onPressAction: {
                            overlay.selectedIndex = index
                            overlay.activateFocused()
                        }
                        TapHandler {
                            onTapped: {
                                overlay.selectedIndex = index
                                overlay.activateFocused()
                            }
                        }
                    }
                }
            }

            // O motivo aparece com o foco, não só depois do Enter: a ação
            // esmaecida sem explicação parecia defeito.
            Text {
                objectName: "launcherSessionOverlayFocusedReason"
                width: parent.width
                visible: text !== ""
                text: overlay.focusedReason
                color: overlay.mutedTextColor
                font.pixelSize: 14 * overlay.visualScale
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Rectangle {
                width: parent.width
                height: Math.max(72, errorText.implicitHeight + 24)
                radius: 8
                visible: overlay.bridgeError !== "" || overlay.localError !== ""
                    || (overlay.overlayModel && overlay.overlayModel.diagnostic)
                    || overlay.criticalError !== null
                color: overlay.highContrast ? "#000000" : _safeColor(themeColors.error, "#241a1e")
                border.width: 1
                border.color: _safeColor(themeColors.error, "#fb7185")
                Text {
                    id: errorText
                    anchors.fill: parent
                    anchors.margins: 12
                    text: overlay.bridgeError !== "" ? overlay.bridgeError
                        : overlay.localError !== "" ? overlay.localError
                        : overlay.criticalError !== null
                        ? [_text(overlay.criticalError.code, "AURA-OSD-ERROR-004"),
                           _text(overlay.criticalError.message
                                 || overlay.criticalError.detail,
                                 qsTr("A sessão registrou um erro crítico.")),
                           _text(overlay.criticalError.impact, ""),
                           _text(overlay.criticalError.nextAction,
                                 qsTr("Verifique a sessão e tente novamente."))]
                            .filter(function(value) { return value !== "" }).join("\n")
                        : _text(overlay.overlayModel ? overlay.overlayModel.diagnostic : "",
                                qsTr("A sessão ainda não está disponível para controle."))
                    color: overlay.primaryTextColor
                    font.pixelSize: 14 * overlay.visualScale
                    wrapMode: Text.Wrap
                    maximumLineCount: 5
                    elide: Text.ElideRight
                }
            }

            Item { width: 1; height: 1 }

            Text {
                width: parent.width
                text: qsTr("← ↑ ↓ → Navegar   Enter Selecionar   Esc Fechar")
                color: overlay.mutedTextColor
                font.pixelSize: 13 * overlay.visualScale
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    Dialog {
        id: exitConfirmation
        objectName: "launcherSessionExitConfirmation"
        modal: true
        focus: true
        anchors.centerIn: parent
        width: Math.max(280, Math.min(520, overlay.width - 32))
        padding: 20
        title: qsTr("Sair do jogo?")
        parent: Overlay.overlay
        // 0 = Cancelar, 1 = Sair. O foco nasce em Cancelar: Enter repetido por
        // engano não pode encerrar a sessão.
        property int choice: 0
        readonly property var choices: [qsTr("Cancelar"), qsTr("Sair do jogo")]
        function activateChoice() {
            if (exitConfirmation.choice === 1)
                exitConfirmation.accept()
            else
                exitConfirmation.reject()
        }
        onOpened: {
            exitConfirmation.choice = 0
            exitChoices.forceActiveFocus()
        }
        onAccepted: {
            overlay.localError = ""
            overlay.actionRequested("exit")
            overlay.forceActiveFocus()
        }
        onRejected: overlay.forceActiveFocus()
        // Os botões padrão do estilo não recebiam foco de teclado e o painel
        // branco do sistema deixava o texto do tema ilegível.
        background: Rectangle {
            color: overlay.panelColor
            radius: 12
            border.width: 1
            border.color: overlay.accentColor
        }
        header: Text {
            text: exitConfirmation.title
            color: overlay.primaryTextColor
            font.pixelSize: 20 * overlay.visualScale
            font.bold: true
            padding: 20
            bottomPadding: 0
        }
        contentItem: FocusScope {
            id: exitChoices
            objectName: "launcherSessionExitChoices"
            implicitHeight: exitColumn.implicitHeight
            focus: true
            Keys.onLeftPressed: exitConfirmation.choice = 0
            Keys.onRightPressed: exitConfirmation.choice = 1
            Keys.onReturnPressed: exitConfirmation.activateChoice()
            Keys.onEnterPressed: exitConfirmation.activateChoice()
            Keys.onSpacePressed: exitConfirmation.activateChoice()
            Keys.onEscapePressed: exitConfirmation.reject()
            Column {
                id: exitColumn
                width: parent.width
                spacing: 16
                Text {
                    width: parent.width
                    text: qsTr("Confirme que não há progresso pendente. O SteamZero enviará um pedido de encerramento e aguardará a confirmação real da sessão; não forçará o fechamento.")
                    color: overlay.primaryTextColor
                    font.pixelSize: 14 * overlay.visualScale
                    wrapMode: Text.WordWrap
                }
                Row {
                    anchors.right: parent.right
                    spacing: 12
                    Repeater {
                        model: exitConfirmation.choices
                        delegate: Rectangle {
                            required property string modelData
                            required property int index
                            objectName: index === 1 ? "launcherSessionExitConfirm"
                                                    : "launcherSessionExitCancel"
                            width: Math.max(140, choiceText.implicitWidth + 32)
                            height: Math.max(48, 40 * overlay.visualScale)
                            radius: 8
                            color: overlay.backgroundColor
                            border.width: index === exitConfirmation.choice ? 3 : 1
                            border.color: index === exitConfirmation.choice
                                ? overlay.accentColor : overlay.borderColor
                            Accessible.name: modelData
                            Accessible.role: Accessible.Button
                            Accessible.onPressAction: {
                                exitConfirmation.choice = index
                                exitConfirmation.activateChoice()
                            }
                            TapHandler {
                                onTapped: {
                                    exitConfirmation.choice = index
                                    exitConfirmation.activateChoice()
                                }
                            }
                            Text {
                                id: choiceText
                                anchors.centerIn: parent
                                text: parent.modelData
                                color: overlay.primaryTextColor
                                font.pixelSize: 15 * overlay.visualScale
                                font.bold: parent.index === exitConfirmation.choice
                            }
                        }
                    }
                }
                Text {
                    text: qsTr("← → Escolher   Enter Confirmar   Esc Cancelar")
                    color: overlay.mutedTextColor
                    font.pixelSize: 12 * overlay.visualScale
                }
            }
        }
    }

    LauncherSaveStateGallery {
        id: saveGallery
        objectName: "launcherSessionSaveStateGallery"
        anchors.fill: parent
        model: overlay.saveStates
        accessibility: overlay.accessibility
        theme: overlay.journeyTheme
        onSlotRequested: function(actionId, slot) {
            overlay.saveStateRequested(actionId, slot)
        }
        onCloseRequested: overlay.closeSaveGallery()
    }

    LauncherSessionPeripherals {
        id: peripheralSurface
        anchors.fill: parent
        model: overlay.peripherals
        accessibility: overlay.accessibility
        theme: overlay.journeyTheme
        onDiscRequested: function(discId) {
            overlay.discRequested(discId)
        }
        onCloseRequested: overlay.closePeripheralSurface()
    }

    Keys.onEscapePressed: overlay.saveGalleryOpen ? overlay.closeSaveGallery()
        : overlay.peripheralOpen ? overlay.closePeripheralSurface() : overlay.closeOverlay()
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_F1 || event.key === Qt.Key_Menu) {
            if (overlay.saveGalleryOpen)
                overlay.closeSaveGallery()
            else if (overlay.peripheralOpen)
                overlay.closePeripheralSurface()
            else
                overlay.closeOverlay()
            event.accepted = true
        }
    }
    Keys.onLeftPressed: overlay.saveGalleryOpen ? saveGallery.move("left")
        : overlay.peripheralOpen ? peripheralSurface.move("left") : overlay.move("left")
    Keys.onRightPressed: overlay.saveGalleryOpen ? saveGallery.move("right")
        : overlay.peripheralOpen ? peripheralSurface.move("right") : overlay.move("right")
    Keys.onUpPressed: overlay.saveGalleryOpen ? saveGallery.move("left")
        : overlay.peripheralOpen ? peripheralSurface.move("left") : overlay.move("up")
    Keys.onDownPressed: overlay.saveGalleryOpen ? saveGallery.move("right")
        : overlay.peripheralOpen ? peripheralSurface.move("right") : overlay.move("down")
    Keys.onReturnPressed: overlay.saveGalleryOpen ? saveGallery.activateFocused()
        : overlay.peripheralOpen ? peripheralSurface.activateFocused() : overlay.activateFocused()
    Keys.onEnterPressed: overlay.saveGalleryOpen ? saveGallery.activateFocused()
        : overlay.peripheralOpen ? peripheralSurface.activateFocused() : overlay.activateFocused()
    Keys.onSpacePressed: overlay.saveGalleryOpen ? saveGallery.activateFocused()
        : overlay.peripheralOpen ? peripheralSurface.activateFocused() : overlay.activateFocused()
}

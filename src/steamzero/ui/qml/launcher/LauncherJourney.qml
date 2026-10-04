// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

FocusScope {
    id: journey

    property var view: null
    property var requestFunction: null
    property bool busy: false
    property string message: ""
    property bool messageIsError: false
    property int requestSequence: 0
    property int cinemaRequestSequence: 0
    property int currentIndex: 0
    property bool cinemaMode: false
    property var cinemaScene: null
    property var saveGallery: null
    property var pendingExitRecord: null
    property int saveSlot: 0
    property int minimumInteractiveTarget: 48
    readonly property var items: view && Array.isArray(view.items) ? view.items : []
    readonly property var facets: view && Array.isArray(view.facets) ? view.facets : []
    readonly property var availableEvents: view && Array.isArray(view.availableEvents)
        ? view.availableEvents : []
    readonly property var routeEvents: availableEvents.filter(function(item) {
        return item.action === "navigate" && item.event === "route"
    })
    readonly property var sessionEvents: availableEvents.filter(function(item) {
        return ["pause", "resume", "open-saves", "save", "load", "exit", "retry"].indexOf(item.event) >= 0
    })
    readonly property var sessionCapabilities: view && view.sessionCapabilities
        ? view.sessionCapabilities : ({})
    readonly property var activeItem: currentIndex >= 0 && currentIndex < items.length
        ? items[currentIndex] : null
    readonly property var theme: view && view.theme ? view.theme : ({})
    readonly property var colors: theme && theme.resolved && theme.resolved.color
        ? theme.resolved.color : ({})
    readonly property color pageColor: theme.highContrast === true ? "#000000"
        : String(colors.background || "#071019")
    readonly property color panelColor: theme.highContrast === true ? "#000000"
        : String(colors.surface || "#10202c")
    readonly property color textColor: String(colors.text || "#f2f6fb")
    readonly property color mutedColor: String(colors.textMuted || "#a9b8c4")
    readonly property color accentColor: String(colors.accent || "#22d3ee")
    readonly property string cinemaFocusId: view && activeItem
        ? "journey:" + String(view.menuId || "") + ":" + String(activeItem.id || "") : ""
    signal launchRequested(string gameId, string focusId)

    Dialog {
        id: exitConfirmation
        objectName: "journeyExitConfirmation"
        modal: true
        focus: true
        width: Math.max(280, Math.min(520, journey.width - 40))
        implicitHeight: Math.max(176, Math.min(220, journey.height - 40))
        title: qsTr("Sair do jogo?")
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: {
            const selected = journey.pendingExitRecord
            journey.pendingExitRecord = null
            if (selected)
                journey.sendEvent("exit", selected, {confirmed: true})
        }
        onRejected: journey.pendingExitRecord = null
        contentItem: Text {
            width: exitConfirmation.availableWidth
            text: qsTr("Confirme que não há progresso pendente. O SteamZero pedirá o encerramento e só considerará a sessão fechada após confirmação real.")
            color: journey.textColor
            wrapMode: Text.WordWrap
        }
    }

    function supportsEvent(eventId) {
        return availableEvents.some(function(item) { return String(item.event) === String(eventId) })
    }

    function sessionEventAvailable(eventId) {
        const capability = sessionCapabilities[String(eventId)]
        return !!capability && capability.available === true
    }

    function refreshCinema() {
        if (!cinemaMode || !view || view.active !== true || typeof requestFunction !== "function") {
            ++cinemaRequestSequence
            cinemaScene = null
            return false
        }
        if (!activeItem || !cinemaFocusId) {
            cinemaScene = null
            message = qsTr("CINEMA-JOURNEY-EMPTY-001\nSelecione um resultado para abrir o Cinema.")
            messageIsError = false
            return false
        }
        const serial = ++cinemaRequestSequence
        const expectedMenuId = String(view.menuId || "")
        const expectedGeneration = Number(view.generation || 0)
        const expectedFocusId = cinemaFocusId
        const path = "/cinema?focus=" + encodeURIComponent(expectedFocusId)
            + "&width=" + Math.max(1, Math.round(width))
            + "&height=" + Math.max(1, Math.round(height))
        requestFunction("GET", path, null, function(status, text) {
            if (serial !== cinemaRequestSequence || !cinemaMode
                    || expectedFocusId !== cinemaFocusId
                    || expectedGeneration !== Number(view.generation || 0)
                    || expectedMenuId !== String(view.menuId || ""))
                return
            if (status !== 200) {
                cinemaScene = null
                message = qsTr("CINEMA-JOURNEY-OFFLINE-002\nA cena não respondeu. A lista da Jornada continua disponível.")
                messageIsError = true
                return
            }
            try {
                const scene = JSON.parse(text)
                if (scene.focusId !== expectedFocusId
                        || scene.journeyId !== view.journeyId
                        || scene.menuId !== expectedMenuId
                        || Number(scene.journeyGeneration) !== expectedGeneration
                        || !scene.layouts || !scene.layoutId || !scene.layouts[scene.layoutId]) {
                    cinemaScene = null
                    message = qsTr("CINEMA-JOURNEY-STALE-003\nA cena pertence a outra seleção. Atualize para recuperá-la.")
                    messageIsError = true
                    return
                }
                cinemaScene = scene
                message = scene.layoutResolutionState === "aura-fallback"
                    ? String(scene.layoutDiagnostic || "") : ""
                messageIsError = false
            } catch (error) {
                cinemaScene = null
                message = qsTr("CINEMA-JOURNEY-RESPONSE-004\nA cena recebida está ilegível. A lista continua disponível.")
                messageIsError = true
            }
        })
        return true
    }

    function activateCinemaCurrent() {
        if (supportsEvent("select"))
            return activateCurrent()
        if (supportsEvent("play"))
            return playCurrent()
        return false
    }

    function applyView(next) {
        if (!next || next.active !== true)
            return false
        const previousMenuId = view ? String(view.menuId || "") : ""
        journey.view = next
        let restored = -1
        if (next.selectedItemId) {
            for (let i = 0; i < items.length; ++i) {
                if (String(items[i].id || "") === String(next.selectedItemId)) {
                    restored = i
                    break
                }
            }
        }
        currentIndex = restored >= 0 ? restored
            : previousMenuId !== String(next.menuId || "") ? 0
            : Math.min(currentIndex, Math.max(0, items.length - 1))
        Qt.callLater(function() {
            if (next.scrollPosition !== undefined)
                resultList.contentY = Math.max(0, Number(next.scrollPosition || 0))
            if (cinemaMode)
                refreshCinema()
        })
        return true
    }

    function refresh() {
        if (typeof requestFunction !== "function")
            return false
        const serial = ++requestSequence
        busy = true
        requestFunction("GET", "/journey/current", null, function(status, text) {
            if (serial !== requestSequence)
                return
            busy = false
            if (status !== 200) {
                message = qsTr("JOURNEY-LAUNCHER-OFFLINE-001\nA Jornada não respondeu. A Home AURA continua disponível.")
                messageIsError = true
                return
            }
            try {
                const response = JSON.parse(text)
                if (!applyView(response)) {
                    message = String(response.diagnosticMessage || qsTr("Nenhuma Jornada ativa."))
                    messageIsError = false
                    return
                }
                message = ""
                messageIsError = false
            } catch (error) {
                message = qsTr("JOURNEY-LAUNCHER-RESPONSE-002\nA resposta da Jornada está ilegível.")
                messageIsError = true
            }
        })
        return true
    }

    function sendEvent(eventId, row, extra) {
        if (busy || typeof requestFunction !== "function" || !view)
            return false
        const serial = ++requestSequence
        const requestId = "journey-" + Date.now().toString(36) + "-"
            + serial.toString(36) + "-" + Math.random().toString(36).slice(2, 8)
        const body = Object.assign({
            requestId: requestId,
            event: String(eventId),
            menuId: String(view.menuId || ""),
            generation: Number(view.generation || 0),
            scrollPosition: Math.max(0, Number(resultList.contentY || 0)),
            focusId: row ? "item:" + String(row.id || "") : String(view.focusId || "")
        }, extra || {})
        if (row && row.id !== undefined)
            body.recordId = String(row.id)
        busy = true
        message = ""
        requestFunction("POST", "/journey/event", body, function(status, text) {
            if (serial !== requestSequence)
                return
            busy = false
            if (status !== 200) {
                message = qsTr("JOURNEY-LAUNCHER-EVENT-003\nA ação não foi aceita (%1). Tente novamente.").arg(status)
                messageIsError = true
                return
            }
            let result
            try {
                result = JSON.parse(text)
            } catch (error) {
                message = qsTr("JOURNEY-LAUNCHER-EVENT-004\nA resposta da ação está ilegível.")
                messageIsError = true
                return
            }
            if (String(result.requestId || "") !== requestId)
                return
            if (result.view)
                applyView(result.view)
            if (result.saveStates)
                saveGallery = result.saveStates
            else if (result.view && result.view.saveStates && saveGallery !== null)
                saveGallery = result.view.saveStates
            if (result.operationRequest && result.operationRequest.action === "launch") {
                const operation = result.operationRequest
                journey.launchRequested(String(operation.gameId || ""), String(operation.focusId || ""))
            }
            if (result.state === "operation-confirmed") {
                const operation = result.operationResult || {}
                message = qsTr("Operação confirmada pela sessão · %1").arg(operation.state || "")
                messageIsError = false
            } else if (result.state === "operation-pending") {
                message = qsTr("JOURNEY-SESSION-EXIT-PENDING\nEncerramento solicitado; aguardando a confirmação real de closed.")
                messageIsError = false
            } else if (result.diagnosticMessage) {
                message = String(result.diagnosticCode || "") + "\n" + String(result.diagnosticMessage)
                messageIsError = result.state !== "unmatched" && result.state !== "recovery-required"
            } else if (result.state === "unmatched") {
                message = qsTr("Este evento ainda não tem uma conexão. Edite o mapa da Jornada no Studio.")
                messageIsError = false
            }
        })
        return true
    }

    function chooseFacet(fieldId, option) {
        if (!option)
            return
        const extra = {fieldId: String(fieldId)}
        if (option.kind === "all")
            extra.clear = true
        else if (option.kind === "unknown")
            extra.unknown = true
        else
            extra.value = option.value
        sendEvent("facet", null, extra)
    }

    function activateCurrent() {
        if (!activeItem)
            return false
        return sendEvent("select", activeItem)
    }

    function playCurrent() {
        if (!supportsEvent("play") || !activeItem || !activeItem.gameId)
            return false
        return sendEvent("play", activeItem)
    }

    function back() {
        if (view && view.canGoBack === true)
            return sendEvent("back", null)
        return false
    }

    onViewChanged: {
        if (view && view.diagnosticMessage) {
            message = String(view.diagnosticCode || "") + "\n" + String(view.diagnosticMessage)
            messageIsError = view.resultState === "source-unavailable"
                || view.resultState === "invalid-filter"
        }
        if (cinemaMode)
            Qt.callLater(refreshCinema)
    }

    onCinemaModeChanged: {
        if (cinemaMode)
            Qt.callLater(refreshCinema)
        else {
            ++cinemaRequestSequence
            cinemaScene = null
        }
    }

    onCurrentIndexChanged: {
        if (cinemaMode)
            Qt.callLater(refreshCinema)
    }

    Keys.onUpPressed: currentIndex = Math.max(0, currentIndex - 1)
    Keys.onDownPressed: currentIndex = Math.min(items.length - 1, currentIndex + 1)
    Keys.onReturnPressed: activateCurrent()
    Keys.onEnterPressed: activateCurrent()
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_P && supportsEvent("play")) {
            playCurrent()
            event.accepted = true
        }
    }

    Keys.onEscapePressed: {
        if (saveGallery !== null)
            saveGallery = null
        else
            back()
    }
    focus: visible

    Rectangle {
        anchors.fill: parent
        color: journey.pageColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Label {
                objectName: "journeyMenuTitle"
                text: view ? String(view.menuName || view.journeyName || qsTr("Jornada")) : qsTr("Jornada")
                color: journey.textColor
                font.pixelSize: 26
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
                Accessible.role: Accessible.Heading
            }
            Label {
                objectName: "journeyResultCount"
                text: view ? qsTr("%1 de %2").arg(view.resultCount || 0).arg(view.totalCount || 0) : ""
                color: journey.mutedColor
                font.pixelSize: 16
            }
            Button {
                objectName: "journeyRefresh"
                text: qsTr("Atualizar")
                Accessible.name: text
                enabled: !journey.busy
                Layout.minimumHeight: journey.minimumInteractiveTarget
                onClicked: journey.refresh()
            }
            Button {
                objectName: "journeyCinemaToggle"
                text: journey.cinemaMode ? qsTr("Lista") : qsTr("Cinema")
                Accessible.name: text
                visible: journey.items.length > 0 || journey.cinemaMode
                enabled: !journey.busy
                Layout.minimumHeight: journey.minimumInteractiveTarget
                onClicked: journey.cinemaMode = !journey.cinemaMode
            }
            Button {
                objectName: "journeyPlay"
                text: qsTr("Jogar")
                Accessible.name: text
                visible: journey.supportsEvent("play")
                enabled: !journey.busy && journey.activeItem !== null
                    && !!journey.activeItem.gameId
                Layout.minimumHeight: journey.minimumInteractiveTarget
                onClicked: journey.playCurrent()
            }
        }

        RowLayout {
            objectName: "journeyFacets"
            Layout.fillWidth: true
            spacing: 10
            Repeater {
                model: journey.facets
                delegate: ComboBox {
                    required property var modelData
                    objectName: "journeyFacet_" + String(modelData.fieldId)
                    Layout.fillWidth: true
                    Layout.minimumWidth: 150
                    Layout.minimumHeight: journey.minimumInteractiveTarget
                    Accessible.name: String(modelData.label || modelData.fieldId)
                    textRole: "label"
                    model: modelData.options || []
                    currentIndex: {
                        const options = modelData.options || []
                        for (let i = 0; i < options.length; ++i) {
                            const option = options[i]
                            if (!modelData.selected && option.kind === "all")
                                return i
                            if (modelData.selected && modelData.selectedValue === null
                                    && option.kind === "unknown")
                                return i
                            if (modelData.selected && option.kind === "value"
                                    && option.value === modelData.selectedValue)
                                return i
                        }
                        return 0
                    }
                    enabled: !journey.busy && count > 1
                    onActivated: journey.chooseFacet(String(modelData.fieldId), model[currentIndex])
                }
            }
            Item { Layout.fillWidth: true }
            Button {
                objectName: "journeyBack"
                text: qsTr("Voltar")
                Accessible.name: text
                enabled: !journey.busy && view && view.canGoBack === true
                Layout.minimumHeight: journey.minimumInteractiveTarget
                onClicked: journey.back()
            }
        }

        RowLayout {
            objectName: "journeyRouteChoices"
            visible: journey.routeEvents.length > 0
            Layout.fillWidth: true
            Repeater {
                model: journey.routeEvents
                delegate: Button {
                    required property var modelData
                    objectName: "journeyRoute_" + String(modelData.connectionId || modelData.event)
                    text: String(modelData.label || modelData.event)
                    Accessible.name: text
                    enabled: !journey.busy && journey.activeItem !== null
                    Layout.minimumHeight: journey.minimumInteractiveTarget
                    onClicked: journey.sendEvent("route", journey.activeItem,
                        {connectionId: String(modelData.connectionId || "")})
                }
            }
            Item { Layout.fillWidth: true }
        }

        Label {
            objectName: "journeyStatus"
            visible: journey.message !== ""
            text: journey.message
            color: journey.messageIsError ? "#ff8990" : journey.mutedColor
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: items.length === 0
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width, 680)
                Label {
                    text: view && view.sourceState === "unavailable"
                        ? qsTr("Fonte indisponível") : qsTr("Nenhum resultado")
                    color: journey.textColor
                    font.pixelSize: 24
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }
                Label {
                    text: view && view.diagnosticMessage ? String(view.diagnosticMessage)
                        : qsTr("Limpe uma faceta, verifique os filtros ou atualize a fonte no Studio.")
                    color: journey.mutedColor
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Button {
                    text: qsTr("Tentar novamente")
                    Accessible.name: text
                    Layout.alignment: Qt.AlignHCenter
                    Layout.minimumHeight: journey.minimumInteractiveTarget
                    onClicked: journey.refresh()
                }
            }
        }

        ListView {
            id: resultList
            objectName: "journeyResultList"
            visible: items.length > 0 && (!journey.cinemaMode || journey.cinemaScene === null)
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: journey.items
            currentIndex: journey.currentIndex
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                required property var modelData
                required property int index
                objectName: "journeyResult_" + String(modelData.id || index)
                width: resultList.width
                height: 62
                radius: 8
                color: index === journey.currentIndex ? journey.panelColor : "transparent"
                border.width: index === journey.currentIndex ? 2 : 1
                border.color: index === journey.currentIndex ? journey.accentColor : "#526779"
                Accessible.role: Accessible.ListItem
                Accessible.name: String(modelData.title || modelData.name || modelData.id || "")
                Accessible.selected: index === journey.currentIndex
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    Label {
                        text: String(modelData.title || modelData.name || modelData.id || "")
                        color: journey.textColor
                        font.pixelSize: 18
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Label {
                        text: [modelData.platformName || modelData.platformId,
                               modelData.year, modelData.genre]
                            .filter(function(value) { return value !== undefined && value !== null && value !== "" })
                            .join(" · ")
                        color: journey.mutedColor
                        font.pixelSize: 14
                        elide: Text.ElideRight
                    }
                }
                TapHandler {
                    onTapped: {
                        journey.currentIndex = index
                        journey.activateCurrent()
                    }
                }
            }
            onCurrentIndexChanged: journey.currentIndex = currentIndex
            onContentYChanged: {
                if (journey.view && !journey.busy)
                    journey.view.scrollPosition = contentY
            }
        }

        LauncherCinema {
            id: journeyCinema
            objectName: "journeyCinema"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: journey.cinemaMode && journey.cinemaScene !== null
            scene: journey.cinemaScene
            currentFocus: journey.cinemaFocusId
            accessibility: ({
                highContrast: theme.highContrast === true,
                reducedMotion: theme.reducedMotion === true,
                visualScale: Number(colors.visualScale || 1)
            })
            focus: visible
            onActivated: journey.activateCinemaCurrent()
            onMoveRequested: function(direction) {
                const delta = direction === "left" || direction === "up" ? -1 : 1
                journey.currentIndex = Math.max(0, Math.min(items.length - 1,
                    journey.currentIndex + delta))
                resultList.positionViewAtIndex(journey.currentIndex, ListView.Contain)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: journey.supportsEvent("play")
                    ? qsTr("↑ ↓ navegar · Enter abrir · P jogar · Esc voltar · Ações de sessão ao lado")
                    : qsTr("↑ ↓ navegar · Enter abrir · Esc voltar · Ações de sessão ao lado")
                color: journey.mutedColor
                Layout.fillWidth: true
            }
            Repeater {
                model: journey.sessionEvents
                delegate: Button {
                    required property var modelData
                    objectName: "journeySessionEvent_" + String(modelData.event)
                    text: String(modelData.label || modelData.event)
                    Accessible.name: text
                    Accessible.description: String(journey.sessionCapabilities[String(modelData.event)]
                        ? journey.sessionCapabilities[String(modelData.event)].reason || ""
                        : "Capability ainda não publicada.")
                    enabled: !journey.busy && journey.activeItem !== null
                        && journey.sessionEventAvailable(String(modelData.event))
                    Layout.minimumHeight: journey.minimumInteractiveTarget
                    ToolTip.visible: hovered && !enabled
                    ToolTip.text: Accessible.description
                    onClicked: {
                        if (String(modelData.event) === "exit") {
                            journey.pendingExitRecord = journey.activeItem
                            exitConfirmation.open()
                            return
                        }
                        journey.sendEvent(String(modelData.event), journey.activeItem,
                            (modelData.event === "save" || modelData.event === "load")
                                ? {slot: journey.saveSlot} : {})
                    }
                }
            }
        }
    }

    Rectangle {
        objectName: "journeySavesDialog"
        anchors.fill: parent
        z: 20
        visible: journey.saveGallery !== null
        color: "#c9000000"

        Rectangle {
            anchors.centerIn: parent
            width: Math.max(320, Math.min(parent.width - 40, 720))
            height: Math.max(300, Math.min(parent.height - 40, 560))
            radius: 12
            color: journey.panelColor
            border.width: 2
            border.color: journey.accentColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: qsTr("Save-states da sessão")
                        color: journey.textColor
                        font.pixelSize: 22
                        font.bold: true
                        Layout.fillWidth: true
                    }
                    Button {
                        objectName: "journeySavesClose"
                        text: qsTr("Fechar")
                        Accessible.name: text
                        Layout.minimumHeight: journey.minimumInteractiveTarget
                        onClicked: journey.saveGallery = null
                    }
                }

                Label {
                    text: journey.saveGallery
                        ? qsTr("Estado: %1 · %2").arg(String(journey.saveGallery.state || "unknown"))
                            .arg(String(journey.saveGallery.reason || ""))
                        : ""
                    color: journey.mutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: qsTr("Slot"); color: journey.textColor }
                    SpinBox {
                        objectName: "journeySaveSlot"
                        from: 0
                        to: 999
                        value: journey.saveSlot
                        editable: true
                        Accessible.name: qsTr("Slot de save-state")
                        Layout.minimumHeight: journey.minimumInteractiveTarget
                        onValueModified: journey.saveSlot = value
                    }
                    Button {
                        objectName: "journeySaveSlotSave"
                        text: qsTr("Salvar neste slot")
                        Accessible.name: text
                        visible: journey.supportsEvent("save")
                        enabled: !journey.busy && journey.sessionEventAvailable("save")
                        Layout.minimumHeight: journey.minimumInteractiveTarget
                        onClicked: journey.sendEvent("save", journey.activeItem,
                            {slot: journey.saveSlot})
                    }
                }

                ListView {
                    objectName: "journeySaveEntries"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 6
                    model: journey.saveGallery && Array.isArray(journey.saveGallery.entries)
                        ? journey.saveGallery.entries : []
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 56
                        radius: 6
                        color: "#172b39"
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 8
                            Label {
                                text: qsTr("Slot %1 · %2").arg(modelData.slot)
                                    .arg(String(modelData.timestamp || ""))
                                color: journey.textColor
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Button {
                                objectName: "journeySaveLoad_" + String(modelData.slot)
                                text: qsTr("Carregar")
                                Accessible.name: qsTr("Carregar slot %1").arg(modelData.slot)
                                enabled: !journey.busy && modelData.available === true
                                    && journey.supportsEvent("load")
                                    && journey.sessionEventAvailable("load")
                                Layout.minimumHeight: journey.minimumInteractiveTarget
                                onClicked: {
                                    journey.saveSlot = Number(modelData.slot)
                                    journey.sendEvent("load", journey.activeItem,
                                        {slot: Number(modelData.slot)})
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls

Column {
    id: readiness
    property string gameId: ""
    property string gameTitle: ""
    property bool active: false
    property bool interactive: true
    property bool compact: false
    property int observationDelayMs: 0
    property int requestTimeoutMs: 8000
    property string requestMethod: "GET"
    property var requestFunction: null
    property var accessibility: ({})
    property bool initialized: false
    property bool requestPending: false
    property int generation: 0
    property bool verifyPreparation: false
    property var observation: ({"state": "unknown", "canPrepare": false, "reason": ""})
    readonly property bool preparing: observation.state === "preparing"
    readonly property real textScale: Math.max(1, Number(accessibility.visualScale || 1))
    readonly property string statusText: requestPending && !preparing
        ? qsTr("Verificando prontidão…") : preparing ? qsTr("Preparando o jogo…")
        : observation.state === "ready" ? qsTr("Requisitos de lançamento verificados")
        : observation.state === "blocked" ? qsTr("O jogo precisa de preparação")
        : observation.state === "failed" ? qsTr("A preparação não foi concluída")
        : qsTr("Prontidão não verificada")
    readonly property string badgeText: requestPending && !preparing
        ? qsTr("Verificando…") : preparing ? qsTr("Preparando…")
        : observation.state === "ready" ? qsTr("Requisitos verificados")
        : observation.state === "blocked" ? (observation.canPrepare === true
            ? qsTr("Preparação necessária") : qsTr("Requisitos pendentes"))
        : observation.state === "failed" ? qsTr("Falha na preparação")
        : qsTr("Prontidão não verificada")
    visible: active
    spacing: 8

    function reset() {
        if (!initialized)
            return
        ++generation
        requestPending = false
        verifyPreparation = false
        observation = {"state": "unknown", "canPrepare": false, "reason": ""}
        deferredObservation.stop()
        requestDeadline.stop()
        if (active) {
            if (observationDelayMs > 0)
                deferredObservation.restart()
            else
                refresh()
        }
    }
    onGameIdChanged: reset()
    onActiveChanged: reset()
    onRequestFunctionChanged: reset()
    Component.onCompleted: { initialized = true; reset() }

    function refresh() { return send("GET") }
    function activateAction() {
        return observation.canPrepare === true ? prepare() : refresh()
    }
    function prepare() {
        if (!interactive || observation.canPrepare !== true || preparing)
            return false
        return send("POST")
    }
    function send(method) {
        if (!active || gameId === "" || requestPending || typeof requestFunction !== "function")
            return false
        const requestedGame = gameId
        const requestId = ++generation
        requestMethod = method
        requestPending = true
        requestDeadline.restart()
        let completed = false
        function done(status, text) {
            if (completed || requestId !== generation || requestedGame !== gameId || !active)
                return
            completed = true
            requestDeadline.stop()
            requestPending = false
            try {
                if (status !== 200 && status !== 202 && status !== 409)
                    throw new Error("unavailable")
                const result = JSON.parse(text)
                if (!result || result.gameId !== requestedGame
                        || ["ready", "blocked", "preparing", "failed", "unknown"].indexOf(result.state) < 0
                        || (result.state === "ready" && result.playable !== true)
                        || (result.state === "preparing" && result.preparing !== true))
                    throw new Error("invalid")
                observation = result
                verifyPreparation = false
            } catch (error) {
                observation = {"state": "unknown", "canPrepare": false,
                    "reason": qsTr("Não foi possível verificar. Tente novamente; o lançamento ainda será validado pelo serviço.")}
                // A lost POST response does not prove that preparation did not
                // start. Observe once; never repeat the mutation automatically.
                verifyPreparation = method === "POST"
            }
        }
        try {
            const accepted = requestFunction(method,
                method === "GET" ? "/readiness?gameId=" + encodeURIComponent(requestedGame) : "/prepare",
                method === "GET" ? null : {"gameId": requestedGame}, done)
            if (accepted === false && requestPending)
                done(0, "")
        } catch (error) {
            done(0, "")
        }
        return true
    }

    Timer {
        id: deferredObservation
        interval: Math.max(1, readiness.observationDelayMs)
        onTriggered: readiness.refresh()
    }
    Timer {
        id: requestDeadline
        interval: Math.max(1, readiness.requestTimeoutMs)
        onTriggered: {
            ++readiness.generation
            readiness.requestPending = false
            readiness.observation = {"state": "unknown", "canPrepare": false,
                "reason": qsTr("A verificação demorou demais. Abra os detalhes para tentar novamente.")}
            readiness.verifyPreparation = readiness.requestMethod === "POST"
        }
    }
    Timer {
        interval: 750
        repeat: true
        running: readiness.active && !readiness.requestPending
                 && (readiness.preparing || readiness.verifyPreparation)
        onTriggered: {
            readiness.verifyPreparation = false
            readiness.refresh()
        }
    }
    Row {
        width: parent.width
        spacing: 8
        BusyIndicator {
            palette.windowText: "#55d8ff"
            palette.dark: "#55d8ff"
            palette.highlight: "#55d8ff"
            width: 28
            height: 28
            visible: readiness.requestPending || readiness.preparing
            running: visible && !readiness.accessibility.reducedMotion
        }
        Text {
            objectName: "readinessStatus"
            width: parent.width - 36
            text: readiness.compact ? readiness.badgeText : readiness.statusText
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "#ffffff"
            font.pixelSize: (readiness.compact ? 14 : 16) * readiness.textScale
            Accessible.name: text
        }
    }
    Text {
        objectName: "readinessReason"
        width: parent.width
        visible: text !== ""
        text: String(readiness.observation.reason || "")
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: readiness.accessibility.highContrast ? "#ffffff" : "#c6d0db"
        font.pixelSize: (readiness.compact ? 12 : 14) * readiness.textScale
        maximumLineCount: readiness.compact ? 2 : 100
        elide: Text.ElideRight
        Accessible.name: text
    }
    ProgressBar {
        objectName: "readinessProgress"
        width: parent.width
        visible: readiness.preparing && !readiness.accessibility.reducedMotion
        indeterminate: true
        Accessible.name: qsTr("Preparação em andamento; progresso sem porcentagem disponível")
    }
    Button {
        objectName: "readinessAction"
        visible: readiness.interactive && readiness.observation.state !== "ready"
        enabled: !readiness.requestPending && !readiness.preparing
                 && typeof readiness.requestFunction === "function"
        width: Math.min(parent.width, implicitWidth)
        height: Math.max(48, implicitHeight)
        text: readiness.observation.canPrepare === true
            ? qsTr("Preparar %1").arg(readiness.gameTitle)
            : qsTr("Verificar novamente %1").arg(readiness.gameTitle)
        Accessible.name: text
        onClicked: readiness.activateAction()
        Keys.onReturnPressed: readiness.activateAction()
        Keys.onEnterPressed: readiness.activateAction()
        contentItem: Text {
            text: parent.text
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "#ffffff"
            font.pixelSize: 14 * readiness.textScale
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: readiness.accessibility.highContrast ? "#000000" : "#173148"
            border.color: parent.activeFocus ? "#55d8ff" : "#8a9baa"
            border.width: parent.activeFocus ? 3 : 1
            radius: 8
        }
    }
}

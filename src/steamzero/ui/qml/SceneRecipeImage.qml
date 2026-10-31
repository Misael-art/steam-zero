// SPDX-License-Identifier: GPL-3.0-or-later
// Trusted consumer of resolved native layout, recipe and motion contracts.
import QtQuick

Item {
    id: root
    required property var model
    property real visualScale: 1
    objectName: String(model.id || "")
    readonly property int sourceStatus: artwork.sourceStatus
    readonly property int sourceDecodeCount: artwork.sourceDecodeCount
    readonly property bool softwareEffectsUnavailable: GraphicsInfo.api === GraphicsInfo.Software
        && model.recipe && (model.recipe.nodes || []).length > 0
    readonly property bool fallbackActive: artwork.fallbackActive || softwareEffectsUnavailable || model.resourceDegraded === true
    readonly property string renderState: !visible || opacity <= 0 ? "hidden" : sourceStatus === Image.Error ? "decodeFailed"
        : sourceStatus !== Image.Ready ? "missing" : fallbackActive ? "partial" : "decoded"
    readonly property string renderDiagnostic: model.resourceDiagnostic ? String(model.resourceDiagnostic) : renderState === "decodeFailed"
        ? qsTr("A imagem não pôde ser decodificada. Reimporte o master preservado.")
        : renderState === "missing" ? qsTr("Imagem ausente ou carregando.")
        : fallbackActive ? qsTr("A fonte está disponível; há efeitos indisponíveis neste renderer.") : ""
    readonly property real appliedSaturation: artwork.appliedSaturation
    readonly property bool outlineActive: artwork.outlineActive
    property bool _initialized: false
    property string _lastState: ""
    property int _duration: 0
    property int _easing: Easing.Linear
    property var _bezier: [0.42, 0, 0.58, 1, 1, 1]
    property real _targetX: 0
    property real _targetY: 0
    property real _targetScale: 1
    property real _targetOpacity: 1
    property real _targetRotation: 0
    property real rotationY: 0

    width: model.width
    height: model.height
    z: model.z === undefined ? 0 : model.z
    visible: model.visible !== false
    transform: Rotation {
        origin.x: root.width / 2
        origin.y: root.height / 2
        axis.y: 1
        angle: root.rotationY
    }

    // Only engine-owned enum names can reach this table. Themes never provide
    // expressions, callbacks or executable interpolation functions.
    function easingType(name) {
        const table = {
            linear: Easing.Linear,
            quadIn: Easing.InQuad, quadOut: Easing.OutQuad, quadInOut: Easing.InOutQuad,
            cubicIn: Easing.InCubic, cubicOut: Easing.OutCubic, cubicInOut: Easing.InOutCubic,
            quartIn: Easing.InQuart, quartOut: Easing.OutQuart, quartInOut: Easing.InOutQuart,
            quintIn: Easing.InQuint, quintOut: Easing.OutQuint, quintInOut: Easing.InOutQuint,
            expoIn: Easing.InExpo, expoOut: Easing.OutExpo, expoInOut: Easing.InOutExpo,
            circIn: Easing.InCirc, circOut: Easing.OutCirc, circInOut: Easing.InOutCirc,
            backIn: Easing.InBack, backOut: Easing.OutBack, backInOut: Easing.InOutBack,
            elasticIn: Easing.InElastic, elasticOut: Easing.OutElastic, elasticInOut: Easing.InOutElastic,
            bounceIn: Easing.InBounce, bounceOut: Easing.OutBounce, bounceInOut: Easing.InOutBounce,
            cubicBezier: Easing.BezierSpline
        }
        return table[name] === undefined ? Easing.Linear : table[name]
    }

    function applyTarget(first) {
        if (!model)
            return
        const interrupted = movement.running
        movement.stop()
        const state = String(model.state || "normal")
        const event = first || (state !== _lastState && state === "focused")
            ? "enter" : state !== _lastState ? "exit" : "move"
        const transition = (model.motionTransitions || ({}))[event] || ({})
        _duration = interrupted && model.interruption === "snap"
            ? 0 : Number(transition.duration || 0)
        _easing = easingType(String(transition.easing || "linear"))
        _bezier = transition.easing === "cubicBezier"
            ? [transition.x1, transition.y1, transition.x2, transition.y2, 1, 1]
            : [0.42, 0, 0.58, 1, 1, 1]
        const states = model.motionStates || ({})
        const snapshot = states[transition.to || state] || ({})
        _targetX = Number(model.x) + Number(snapshot.translateX || 0)
        _targetY = Number(model.y) + Number(snapshot.translateY || 0)
        _targetScale = Number(model.scale === undefined ? 1 : model.scale)
            * Number(snapshot.scale === undefined ? 1 : snapshot.scale)
        _targetOpacity = Number(model.opacity === undefined ? 1 : model.opacity)
            * Number(snapshot.opacity === undefined ? 1 : snapshot.opacity)
        _targetRotation = Number(model.rotationY || 0)
        if (first) {
            const start = states[transition.from] || snapshot
            x = Number(model.x) + Number(start.translateX || 0)
            y = Number(model.y) + Number(start.translateY || 0)
            scale = Number(model.scale === undefined ? 1 : model.scale)
                * Number(start.scale === undefined ? 1 : start.scale)
            opacity = Number(model.opacity === undefined ? 1 : model.opacity)
                * Number(start.opacity === undefined ? 1 : start.opacity)
            rotationY = _targetRotation
        }
        _lastState = state
        if (_duration <= 0) {
            x = _targetX; y = _targetY; scale = _targetScale
            opacity = _targetOpacity; rotationY = _targetRotation
        } else {
            movement.start()
        }
    }

    onModelChanged: if (_initialized) applyTarget(false)
    Component.onCompleted: {
        _initialized = true
        applyTarget(true)
    }

    ParallelAnimation {
        id: movement
        NumberAnimation { target: root; property: "x"; to: root._targetX; duration: root._duration; easing.type: root._easing; easing.bezierCurve: root._bezier }
        NumberAnimation { target: root; property: "y"; to: root._targetY; duration: root._duration; easing.type: root._easing; easing.bezierCurve: root._bezier }
        NumberAnimation { target: root; property: "scale"; to: root._targetScale; duration: root._duration; easing.type: root._easing; easing.bezierCurve: root._bezier }
        NumberAnimation { target: root; property: "opacity"; to: root._targetOpacity; duration: root._duration; easing.type: root._easing; easing.bezierCurve: root._bezier }
        NumberAnimation { target: root; property: "rotationY"; to: root._targetRotation; duration: root._duration; easing.type: root._easing; easing.bezierCurve: root._bezier }
    }

    AssetRecipePreview {
        id: artwork
        anchors.fill: parent
        source: String(root.model.source || "")
        recipe: root.model.recipe || ({"source": "", "nodes": [], "fallback": "source"})
        fillMode: Image[String(root.model.fillMode || "PreserveAspectFit")]
        transitionDuration: root._duration
        transitionEasing: root._easing
        transitionBezier: root._bezier
        decodeSize: Qt.size(Math.ceil(root.width), Math.ceil(root.height))
    }
    Text {
        anchors.fill: parent
        visible: artwork.sourceStatus === Image.Error || artwork.source.toString() === ""
        text: qsTr("Imagem indisponível")
        textFormat: Text.PlainText
        color: "#e8eef6"
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.pixelSize: 12 * root.visualScale
    }
}

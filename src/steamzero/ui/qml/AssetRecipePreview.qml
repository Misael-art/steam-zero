// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Renderer confiável do slice asset-único. A receita já chega validada e
// negociada pelo domínio; o pacote nunca fornece QML, JavaScript ou shader.
import QtQuick
import QtQuick.Effects

Item {
    id: root

    required property url source
    property var recipe: ({"source": "logo", "nodes": [], "fallback": "source"})
    property int fillMode: Image.PreserveAspectFit
    property string cacheKey: ""
   property size decodeSize: Qt.size(-1, -1)
   property int transitionDuration: 0
   property int transitionEasing: Easing.Linear
   property var transitionBezier: [0.42, 0, 0.58, 1, 1, 1]

    readonly property int sourceStatus: sourceImage.status
    readonly property int sourceDecodeCount: root._sourceDecodeCount
    readonly property real outlineWidth: outlineNode ? Number(outlineNode.parameters.width) : 0
    readonly property real outlineScale: 1 + (2 * outlineWidth / Math.max(1, Math.min(width, height)))
    // Degradação tem duas origens e as duas precisam chegar ao consumidor:
    // a receita pode ter perdido nós ainda no domínio (chega vazia, com
    // ``degraded``), ou o runtime pode não conseguir instanciar o node de cor.
    readonly property bool recipeDegraded: recipe && recipe.degraded === true
    readonly property int droppedNodeCount: recipe && recipe.droppedNodes !== undefined
        ? Number(recipe.droppedNodes) : 0
    readonly property bool softwareBackend: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool rendererUnavailable: softwareBackend && recipe && (recipe.nodes || []).length > 0
    readonly property bool fallbackActive: unsupportedNodeCount > 0
        || recipeDegraded || colorTransform.unsupported || rendererUnavailable
    readonly property int unsupportedNodeCount: {
        const supported = ["recolor", "grayscale", "silhouette", "outline",
                           "glow", "shadow", "invert", "hueRotate", "saturation"]
        let count = 0
        const entries = recipe && recipe.nodes ? recipe.nodes : []
        for (let i = 0; i < entries.length; ++i) {
            if (supported.indexOf(entries[i].type) < 0)
                count += 1
        }
        return count
    }
    readonly property real appliedColorization: fillLayer.visible ? fillLayer.colorization : 0
    readonly property real appliedSaturation: fillLayer.visible ? fillLayer.saturation : 0
    readonly property bool outlineActive: outlineLayer.visible
    readonly property bool colorTransformAvailable: colorTransform.available && !softwareBackend

    property int _sourceDecodeCount: 0
    property bool _sourceReadySeen: false

    function node(recipeValue, type) {
        // ``recipeValue`` explícito torna a dependência observável pelo engine
        // de bindings quando o usuário troca a variante no preview.
        const entries = recipeValue && recipeValue.nodes ? recipeValue.nodes : []
        for (let i = 0; i < entries.length; ++i) {
            if (entries[i].type === type)
                return entries[i]
        }
        return null
    }

    readonly property var recolorNode: node(root.recipe, "recolor")
    readonly property var grayscaleNode: node(root.recipe, "grayscale")
    readonly property var saturationNode: node(root.recipe, "saturation")
    readonly property var silhouetteNode: node(root.recipe, "silhouette")
    readonly property var outlineNode: node(root.recipe, "outline")
    readonly property var invertNode: node(root.recipe, "invert")
    readonly property var hueRotateNode: node(root.recipe, "hueRotate")
    readonly property var glowNode: node(root.recipe, "glow")
    readonly property var shadowNode: node(root.recipe, "shadow")
    readonly property var colorNode: silhouetteNode || recolorNode
    readonly property var ambientNode: glowNode || shadowNode

    Image {
        id: sourceImage
        anchors.fill: parent
        source: root.source
        sourceSize: root.decodeSize
        fillMode: root.fillMode
        asynchronous: false
        cache: true
        visible: root.softwareBackend || root.fallbackActive
        onStatusChanged: {
            if (status === Image.Ready && !root._sourceReadySeen) {
                root._sourceReadySeen = true
                root._sourceDecodeCount += 1
            }
            if (status === Image.Null || status === Image.Error)
                root._sourceReadySeen = false
        }
    }

    // Uma única textura é compartilhada entre preenchimento, outline e
    // glow/shadow. Trocar a receita não muda ``source`` nem abre outro Image.
    MultiEffect {
        id: outlineLayer
        anchors.fill: parent
        source: sourceImage
        visible: root.outlineNode !== null && !root.fallbackActive
        colorization: 1
        colorizationColor: root.outlineNode
            ? root.outlineNode.parameters.color : "#ffffff"
        opacity: root.outlineNode ? root.outlineNode.parameters.opacity : 0
        shadowEnabled: visible
        shadowColor: root.outlineNode
            ? root.outlineNode.parameters.color : "#ffffff"
        shadowOpacity: root.outlineNode ? root.outlineNode.parameters.opacity : 0
        shadowBlur: 0
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0
        shadowScale: root.outlineScale
       Behavior on shadowScale { NumberAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
       Behavior on opacity { NumberAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
    }

    // Invert e hue rotate saem de um node builtin: o tema nomeia a semântica,
    // a engine decide como (e avisa quando o runtime não consegue).
    AssetColorTransform {
        id: colorTransform
        anchors.fill: parent
        source: sourceImage
        visible: requested && available && !root.fallbackActive
        mode: root.invertNode ? "invert" : (root.hueRotateNode ? "hueRotate" : "")
        hue: root.hueRotateNode ? root.hueRotateNode.parameters.degrees / 360.0 : 0
    }

    MultiEffect {
        id: fillLayer
        anchors.fill: parent
        source: sourceImage
        visible: !colorTransform.visible && !root.softwareBackend && !root.fallbackActive
        // Node inesperado nunca produz tela vazia: mostra a fonte e publica
        // ``fallbackActive`` para diagnóstico do consumidor.
        saturation: root.grayscaleNode && !root.fallbackActive
            ? -root.grayscaleNode.parameters.amount
            : root.saturationNode && !root.fallbackActive ? root.saturationNode.parameters.amount - 1 : 0
        Behavior on saturation { NumberAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
       Behavior on brightness { NumberAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
       Behavior on colorization { NumberAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
       Behavior on colorizationColor { ColorAnimation { duration: root.transitionDuration; easing.type: root.transitionEasing; easing.bezierCurve: root.transitionBezier } }
       // Normaliza RGB para branco antes do colorize. O alpha permanece o da
        // fonte, portanto recolor e silhueta não dependem de threshold RGB.
        brightness: root.colorNode && !root.fallbackActive ? 1 : 0
        colorization: root.colorNode && !root.fallbackActive ? 1 : 0
        colorizationColor: root.colorNode
            ? root.colorNode.parameters.color : "#ffffff"
        opacity: root.colorNode && !root.fallbackActive
            ? root.colorNode.parameters.opacity : 1
        shadowEnabled: root.ambientNode !== null && !root.fallbackActive
        shadowColor: root.ambientNode
            ? root.ambientNode.parameters.color : "#00000000"
        shadowOpacity: root.glowNode
            ? root.glowNode.parameters.strength
            : root.shadowNode ? root.shadowNode.parameters.opacity : 0
        shadowBlur: root.ambientNode ? root.ambientNode.parameters.blur / 48 : 0
        shadowHorizontalOffset: root.shadowNode ? root.shadowNode.parameters.offsetX : 0
        shadowVerticalOffset: root.shadowNode ? root.shadowNode.parameters.offsetY : 0
        shadowScale: root.glowNode ? 1.04 : 1
    }
}

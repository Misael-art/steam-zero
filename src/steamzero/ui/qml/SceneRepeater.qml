// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Consumidor QML de um layout já resolvido pela Theme Engine. O modelo contém
// somente nós finais: esta peça não lê read model, não calcula grid e não
// interpreta binding algum.
import QtQuick

Item {
    id: sceneRepeater

    required property var layout
    property real visualScale: 1.0
    readonly property var entries: layout && layout.entries ? layout.entries : []
    readonly property int entryCount: entries.length
    readonly property var renderFeedback: {
        const feedback = []
        const readyDelegates = nodes.count
        for (let i = 0; i < entries.length; ++i) {
            const entry = entries[i]
            if (entry.kind !== "image") continue
            const item = i < readyDelegates ? entryAt(i) : null
            const status = item ? (item.sourceStatus === undefined ? item.status : item.sourceStatus) : Image.Loading
            const state = item && item.renderState ? String(item.renderState) : status === Image.Error ? "decodeFailed"
                : status === Image.Ready ? (item.fallbackActive ? "partial" : "decoded")
                : status === Image.Loading ? "loading" : "missing"
            feedback.push({element: String(entry.id), key: String(entry.key || entry.id),
                state: state, reason: item && item.renderDiagnostic ? String(item.renderDiagnostic)
                    : state === "decodeFailed" ? qsTr("Imagem inválida; reimporte ou escolha outra fonte.")
                    : state === "missing" ? qsTr("Vincule uma imagem disponível.") : ""})
        }
        return feedback
    }
    // A maioria dos itens não tem destaque. Manter um Rectangle invisível para
    // cada um cria uma segunda árvore visual que o compositor ainda percorre;
    // o contrato já entrega a decisão de destaque, então filtrá-la aqui não
    // muda o desenho e reduz o trabalho por frame.
    readonly property var outlinedEntries: {
        const out = []
        for (let i = 0; i < sceneRepeater.entries.length; ++i) {
            const entry = sceneRepeater.entries[i]
            if (Number(entry.outlineWidth || 0) > 0 && entry.visible !== false)
                out.push(entry)
        }
        return out
    }

    readonly property url textSource: Qt.resolvedUrl("SceneText.qml")
    readonly property url imageSource: Qt.resolvedUrl("SceneImage.qml")
    readonly property url recipeImageSource: Qt.resolvedUrl("SceneRecipeImage.qml")
    readonly property url badgeSource: Qt.resolvedUrl("SceneBadge.qml")

    function sourceFor(kind, entry) {
        if (kind === "image")
            return entry && (entry.recipe || entry.motionTransitions || entry.resourceDegraded) ? recipeImageSource : imageSource
        if (kind === "badge")
            return badgeSource
        return textSource
    }

    // Keep delegates keyed by public item identity. Reordering a selection
    // retargets existing objects instead of reopening every image/animation.
    ListModel { id: stableEntries }

    function syncEntries() {
        const seen = new Set()
        for (let i = 0; i < entries.length; ++i) {
            const entry = entries[i]
            let key = String(entry.key || entry.id || i)
            if (seen.has(key)) key += ":" + i
            seen.add(key)
            let found = -1
            for (let j = i; j < stableEntries.count; ++j)
                if (stableEntries.get(j).entryKey === key) { found = j; break }
            if (found < 0)
                stableEntries.insert(i, {entryKey: key, nodeJson: JSON.stringify(entry)})
            else {
                if (found !== i) stableEntries.move(found, i, 1)
                stableEntries.setProperty(i, "nodeJson", JSON.stringify(entry))
            }
        }
        if (stableEntries.count > entries.length)
            stableEntries.remove(entries.length, stableEntries.count - entries.length)
    }
    onEntriesChanged: syncEntries()
    Component.onCompleted: syncEntries()

    function entryAt(index) {
        const loader = nodes.itemAt(index)
        return loader ? loader.item : null
    }

    function outlineAt(index) {
        return outlines.itemAt(index)
    }

    // Moldura de destaque do item central (e dos vizinhos, quando o tema declara
    // tratamento). Largura, cor e visibilidade chegam resolvidas; o QML não
    // decide quem é o centro nem quanto contorno aplicar.
    Repeater {
        id: outlines
        model: sceneRepeater.outlinedEntries

        delegate: Rectangle {
            required property var modelData
            readonly property real outlineWidth: modelData && modelData.outlineWidth !== undefined
                ? Number(modelData.outlineWidth) : 0

            x: modelData.x
            y: modelData.y
            width: modelData.width !== undefined ? modelData.width : 0
            height: modelData.height !== undefined ? modelData.height : 0
            z: (modelData.z !== undefined ? modelData.z : 0) - 1
            scale: modelData.scale !== undefined ? modelData.scale : 1
            visible: outlineWidth > 0 && modelData.visible !== false
            color: "transparent"
            border.width: outlineWidth
            border.color: modelData.outlineColor !== undefined ? modelData.outlineColor : "#ffffff"
            radius: 4
        }
    }

    Repeater {
        id: nodes
        model: stableEntries

        delegate: Loader {
            required property string nodeJson
            readonly property var modelData: JSON.parse(nodeJson)

            function loadEntry() {
                if (modelData === undefined)
                    return
                const source = sceneRepeater.sourceFor(modelData.kind, modelData)
                if (item !== null && String(source) === String(this.source)) {
                    item.model = modelData
                    item.visualScale = sceneRepeater.visualScale
                    return
                }
                // `SceneText`/`SceneImage` exigem `model` na construção. Atribuir
                // em onLoaded é tarde demais e o Qt recusa o componente.
                setSource(source, {
                    "model": modelData,
                    "visualScale": sceneRepeater.visualScale
                })
            }

            onModelDataChanged: loadEntry()
            Component.onCompleted: loadEntry()
        }
    }
}

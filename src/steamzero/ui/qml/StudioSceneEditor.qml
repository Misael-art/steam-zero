// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Autoria direta de cena: trazer fotos, soltar, mover, redimensionar pelas
// alças, alinhar com guias, camadas, receitas e histórico. Todo gesto termina
// num pedido transacional studio.scene.* — o serviço valida e devolve o
// documento. Geometria normalizada no palco 16:9 preserva a composição quando
// a janela muda de tamanho. Nenhum QML de pacote é executado aqui.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: editor
    objectName: "studioSceneEditor"

    property var requestAction: function(_id, _payload, _cb, _ecb) { return false }
    property color surfaceColor: "#0d1924"
    property color raisedColor: "#122131"
    property color borderColor: "#2a3a49"
    property color textColor: "#f2f6fb"
    property color mutedColor: "#9eabba"
    property color accentColor: "#13bdf2"
    property color errorColor: "#ff6b73"
    property real minimumInteractiveTarget: 40
    property string projectId: "org.steamzero.scene-draft"
    property var snapshot: null
    property var guides: []
    property string notice: ""
    property bool noticeIsError: false
    property string libraryQuery: ""
    property string libraryOrigin: ""
    signal closeRequested()

    readonly property var documentData: snapshot ? snapshot.document : null
    readonly property var currentScene: {
        if (!documentData)
            return null
        for (let i = 0; i < documentData.scenes.length; ++i)
            if (documentData.scenes[i].id === snapshot.sceneId)
                return documentData.scenes[i]
        return null
    }
    readonly property var layers: currentScene ? currentScene.layers : []
    readonly property var selection: snapshot ? snapshot.selection : []
    readonly property var selectedLayer: {
        if (selection.length !== 1)
            return null
        for (let i = 0; i < layers.length; ++i)
            if (layers[i].id === selection[0])
                return layers[i]
        return null
    }
    readonly property var masters: documentData ? documentData.masters : []
    readonly property var mediaStatus: {
        const out = {}
        const report = snapshot && snapshot.media ? snapshot.media : []
        for (let i = 0; i < report.length; ++i)
            out[report[i].mediaId] = report[i].status
        return out
    }
    readonly property var filteredMasters: masters.filter(function(item) {
        return (editor.libraryOrigin === "" || item.origin === editor.libraryOrigin)
            && (editor.libraryQuery === ""
                || String(item.name).toLowerCase().indexOf(editor.libraryQuery.toLowerCase()) >= 0)
    })

    function call(action, payload, onSuccess) {
        const dispatched = requestAction(action, payload, function(result) {
            editor.noticeIsError = false
            if (onSuccess)
                onSuccess(result || ({}))
        }, function(error) {
            editor.notice = typeof error === "string" ? error
                : (error && error.detail ? String(error.detail) : qsTr("A edição foi recusada"))
            editor.noticeIsError = true
        })
        if (dispatched === false) {
            editor.notice = qsTr("As ações de cena não estão disponíveis nesta sessão.")
            editor.noticeIsError = true
        }
    }

    function apply(result) {
        if (result.snapshot)
            result = result.snapshot
        editor.snapshot = result
        editor.guides = result.guides || []
    }

    function open(newProject) {
        call(newProject ? "studio.scene.create" : "studio.scene.load",
             newProject ? {projectId: projectId, name: qsTr("Experiência")} : {projectId: projectId},
             apply)
    }

    function edit(operation, payload) {
        if (!snapshot)
            return
        call("studio.scene.transact", {sessionId: snapshot.sessionId, operation: operation,
                                       payload: payload || ({})}, apply)
    }

    function importFile(url, origin) {
        if (!snapshot)
            return
        const path = decodeURIComponent(String(url).replace(/^file:\/\//, ""))
        call("studio.scene.import-media", {sessionId: snapshot.sessionId, path: path, origin: origin},
             function(result) {
                 editor.apply(result)
                 editor.notice = qsTr("Foto disponível na biblioteca do projeto.")
             })
    }

    function save() {
        if (!snapshot)
            return
        call("studio.scene.save", {sessionId: snapshot.sessionId}, function(result) {
            editor.apply(result)
            editor.notice = qsTr("Projeto salvo.")
        })
    }

    // Receita → efeitos do renderer compartilhado. O master nunca é alterado.
    function recipeEffects(recipe) {
        if (!recipe)
            return []
        const effects = []
        const saturation = recipe.preset === "mono" ? -1.0 : Number(recipe.saturation) - 1.0
        if (saturation !== 0)
            effects.push({type: "saturation", parameters: {amount: Math.max(-1, Math.min(1, saturation))}})
        if (Number(recipe.brightness) !== 0)
            effects.push({type: "brightness", parameters: {amount: Number(recipe.brightness)}})
        if (recipe.preset === "warm" || recipe.preset === "cool")
            effects.push({type: "colorize", parameters: {strength: 0.25,
                color: recipe.preset === "warm" ? "#ff9a3c" : "#3c9aff"}})
        return effects
    }

    function masterUrl(mediaId) {
        return snapshot && snapshot.masterRoot ? "file://" + snapshot.masterRoot + "/" + mediaId : ""
    }

    Component.onCompleted: open(true)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Label { text: qsTr("Cena"); color: editor.textColor; font.bold: true }
            ComboBox {
                objectName: "sceneScenePicker"
                model: editor.documentData ? editor.documentData.scenes.map(function(s) { return s.name }) : []
                onActivated: function(index) { editor.edit("open-scene", {sceneId: editor.documentData.scenes[index].id}) }
            }
            Button { text: qsTr("＋ Cena"); onClicked: editor.edit("add-scene", {name: qsTr("Nova cena")}) }
            Button { objectName: "sceneAddText"; text: qsTr("＋ Texto"); onClicked: editor.edit("add-text", {text: qsTr("Título"), x: 0.1, y: 0.1}) }
            Button {
                objectName: "sceneUndo"; text: qsTr("Desfazer")
                enabled: !!editor.snapshot && editor.snapshot.history.canUndo
                onClicked: editor.edit("undo")
            }
            Button {
                objectName: "sceneRedo"; text: qsTr("Refazer")
                enabled: !!editor.snapshot && editor.snapshot.history.canRedo
                onClicked: editor.edit("redo")
            }
            Item { Layout.fillWidth: true }
            Button { objectName: "sceneSave"; text: qsTr("Salvar"); onClicked: editor.save() }
            Button { text: qsTr("Reabrir"); onClicked: editor.open(false) }
            Button { text: qsTr("Fechar"); onClicked: editor.closeRequested() }
        }

        Label {
            text: editor.notice
            visible: editor.notice !== ""
            color: editor.noticeIsError ? editor.errorColor : editor.accentColor
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Biblioteca: busca e origem localizam fotos; não tratam a imagem.
            ColumnLayout {
                Layout.preferredWidth: 220
                Layout.maximumWidth: 220
                Layout.fillHeight: true
                Label { text: qsTr("Biblioteca"); color: editor.textColor; font.bold: true }
                TextField {
                    objectName: "sceneLibrarySearch"
                    placeholderText: qsTr("Buscar foto")
                    Layout.fillWidth: true
                    onTextChanged: editor.libraryQuery = text
                }
                ComboBox {
                    Layout.fillWidth: true
                    model: [qsTr("Todas"), qsTr("Biblioteca"), qsTr("Minhas fotos")]
                    onActivated: function(index) { editor.libraryOrigin = ["", "library", "folder"][index] }
                }
                RowLayout {
                    Button { text: qsTr("Fotos…"); onClicked: photoDialog.open() }
                    Button { text: qsTr("Biblioteca…"); onClicked: libraryDialog.open() }
                }
                ListView {
                    objectName: "sceneLibraryList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: editor.filteredMasters
                    spacing: 4
                    delegate: Rectangle {
                        id: tile
                        required property var modelData
                        width: ListView.view.width
                        height: 48
                        radius: 6
                        color: editor.raisedColor
                        border.color: editor.mediaStatus[modelData.id] === "available" ? editor.borderColor : editor.errorColor
                        Drag.active: tileDrag.drag.active
                        Drag.keys: ["steamzero-master"]
                        Drag.mimeData: ({"text/plain": modelData.id})
                        Drag.hotSpot.x: 24
                        Drag.hotSpot.y: 24
                        property string mediaId: modelData.id
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            width: parent.width - 16
                            elide: Text.ElideRight
                            color: editor.textColor
                            text: tile.modelData.name + (editor.mediaStatus[tile.modelData.id] !== "available"
                                ? qsTr(" · indisponível") : "")
                        }
                        MouseArea {
                            id: tileDrag
                            anchors.fill: parent
                            drag.target: tile
                            onReleased: {
                                tile.Drag.drop()
                                tile.x = 0
                                tile.y = 0
                            }
                        }
                    }
                }
            }

            // Área de criação: palco 16:9 encaixado; posições são normalizadas.
            Rectangle {
                id: area
                objectName: "sceneEditArea"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 320
                Layout.minimumHeight: 180
                color: "#05090d"
                clip: true

                readonly property real stageWidth: Math.min(width, height * 16 / 9)
                readonly property real stageHeight: stageWidth * 9 / 16

                Rectangle {
                    id: stage
                    objectName: "sceneStage"
                    width: area.stageWidth
                    height: area.stageHeight
                    anchors.centerIn: parent
                    color: "#0b1620"
                    border.color: editor.borderColor

                    function toStage(px, py) { return Qt.point(px / width, py / height) }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: editor.edit("select", {layerId: null})
                    }

                    DropArea {
                        anchors.fill: parent
                        keys: ["steamzero-master"]
                        onDropped: function(drop) {
                            const p = stage.toStage(drop.x, drop.y)
                            editor.edit("drop", {mediaId: drop.source.mediaId, x: p.x, y: p.y})
                        }
                    }

                    Repeater {
                        model: editor.layers
                        delegate: Item {
                            id: layerItem
                            required property var modelData
                            required property int index
                            objectName: "sceneLayer-" + modelData.id
                            readonly property bool selected: editor.selection.indexOf(modelData.id) >= 0
                            x: modelData.x * stage.width
                            y: modelData.y * stage.height
                            width: modelData.w * stage.width
                            height: modelData.h * stage.height
                            visible: modelData.visible
                            z: index

                            Image {
                                id: layerImage
                                objectName: "sceneLayerImage"
                                anchors.fill: parent
                                visible: layerItem.modelData.kind === "image"
                                    && (layerEffect.status !== Loader.Ready || layerEffect.item === null)
                                source: layerItem.modelData.kind === "image" ? editor.masterUrl(layerItem.modelData.mediaId) : ""
                                fillMode: layerItem.modelData.recipe.fit === "contain" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                                horizontalAlignment: layerItem.modelData.recipe.focalX < 0.34 ? Image.AlignLeft
                                    : (layerItem.modelData.recipe.focalX > 0.66 ? Image.AlignRight : Image.AlignHCenter)
                                verticalAlignment: layerItem.modelData.recipe.focalY < 0.34 ? Image.AlignTop
                                    : (layerItem.modelData.recipe.focalY > 0.66 ? Image.AlignBottom : Image.AlignVCenter)
                                opacity: layerEffect.status === Loader.Ready
                                    ? 1 : Math.max(0.15, 1 + Math.min(0, layerItem.modelData.recipe.brightness))
                                layer.enabled: layerEffect.status === Loader.Ready
                            }
                            Loader {
                                id: layerEffect
                                objectName: "sceneLayerEffect"
                                anchors.fill: parent
                                readonly property var effects: editor.recipeEffects(layerItem.modelData.recipe)
                                active: layerItem.modelData.kind === "image" && effects.length > 0
                                source: active ? "MediaMultiEffectRenderer.qml" : ""
                                onLoaded: {
                                    item.sourceItem = layerImage
                                    item.effects = Qt.binding(function() { return layerEffect.effects })
                                }
                            }
                            Rectangle {
                                anchors.fill: parent
                                visible: layerItem.modelData.kind === "image"
                                    && editor.mediaStatus[layerItem.modelData.mediaId] !== "available"
                                color: "#33ff6b73"
                                border.color: editor.errorColor
                                Text { anchors.centerIn: parent; color: editor.textColor; text: qsTr("Foto indisponível") }
                            }
                            Text {
                                anchors.fill: parent
                                visible: layerItem.modelData.kind === "text"
                                text: layerItem.modelData.text || ""
                                color: editor.textColor
                                fontSizeMode: Text.Fit
                                font.pixelSize: 64
                                verticalAlignment: Text.AlignVCenter
                            }
                            Rectangle {
                                anchors.fill: parent
                                color: "transparent"
                                border.width: layerItem.selected ? 2 : 0
                                border.color: editor.accentColor
                            }
                            MouseArea {
                                id: body
                                anchors.fill: parent
                                enabled: !layerItem.modelData.locked
                                property point pressAt
                                property bool moved: false
                                onPressed: function(mouse) {
                                    pressAt = mapToItem(stage, mouse.x, mouse.y)
                                    moved = false
                                }
                                onPositionChanged: function(mouse) {
                                    const now = mapToItem(stage, mouse.x, mouse.y)
                                    layerItem.x = layerItem.modelData.x * stage.width + (now.x - pressAt.x)
                                    layerItem.y = layerItem.modelData.y * stage.height + (now.y - pressAt.y)
                                    moved = true
                                }
                                onReleased: function(mouse) {
                                    if (!moved) {
                                        editor.edit("select", {layerId: layerItem.modelData.id,
                                                               extend: (mouse.modifiers & Qt.ShiftModifier) !== 0})
                                        return
                                    }
                                    const now = mapToItem(stage, mouse.x, mouse.y)
                                    const ids = layerItem.selected ? editor.selection : [layerItem.modelData.id]
                                    editor.edit("move", {layerIds: ids,
                                                         dx: (now.x - pressAt.x) / stage.width,
                                                         dy: (now.y - pressAt.y) / stage.height})
                                }
                            }
                            Repeater {
                                model: layerItem.selected && editor.selection.length === 1 && !layerItem.modelData.locked
                                    ? ["nw", "n", "ne", "e", "se", "s", "sw", "w"] : []
                                delegate: Rectangle {
                                    id: handle
                                    required property string modelData
                                    objectName: "sceneHandle-" + modelData
                                    width: 12; height: 12; radius: 2
                                    color: editor.accentColor
                                    x: (modelData.indexOf("w") >= 0 ? 0 : (modelData.indexOf("e") >= 0 ? layerItem.width : layerItem.width / 2)) - 6
                                    y: (modelData.indexOf("n") >= 0 ? 0 : (modelData.indexOf("s") >= 0 ? layerItem.height : layerItem.height / 2)) - 6
                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -6
                                        cursorShape: Qt.SizeAllCursor
                                        onReleased: function(mouse) {
                                            const p = mapToItem(stage, mouse.x, mouse.y)
                                            editor.edit("resize", {
                                                layerId: layerItem.modelData.id, handle: handle.modelData,
                                                x: p.x / stage.width, y: p.y / stage.height,
                                                keepAspect: handle.modelData.length === 2
                                                    ? (mouse.modifiers & Qt.ShiftModifier) === 0 : false
                                            })
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Repeater {
                        model: editor.guides
                        delegate: Rectangle {
                            required property var modelData
                            color: editor.accentColor
                            opacity: 0.8
                            x: modelData.axis === "vertical" ? modelData.at * stage.width : 0
                            y: modelData.axis === "horizontal" ? modelData.at * stage.height : 0
                            width: modelData.axis === "vertical" ? 1 : stage.width
                            height: modelData.axis === "horizontal" ? 1 : stage.height
                            z: 1000
                        }
                    }
                }
            }

            // Camadas e inspetor: alinhamento, ordem, visibilidade, bloqueio e receita.
            ColumnLayout {
                Layout.preferredWidth: 260
                Layout.maximumWidth: 260
                Layout.fillHeight: true
                Label { text: qsTr("Camadas"); color: editor.textColor; font.bold: true }
                ListView {
                    objectName: "sceneLayerList"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    clip: true
                    model: editor.layers.slice().reverse()
                    delegate: RowLayout {
                        required property var modelData
                        width: ListView.view.width
                        CheckBox {
                            checked: modelData.visible
                            Accessible.name: qsTr("Visível")
                            onToggled: editor.edit("set-flag", {layerId: modelData.id, flag: "visible", value: checked})
                        }
                        Button {
                            Layout.fillWidth: true
                            text: modelData.name
                            highlighted: editor.selection.indexOf(modelData.id) >= 0
                            onClicked: editor.edit("select", {layerId: modelData.id})
                        }
                        CheckBox {
                            checked: modelData.locked
                            text: qsTr("🔒")
                            Accessible.name: qsTr("Bloqueada")
                            onToggled: editor.edit("set-flag", {layerId: modelData.id, flag: "locked", value: checked})
                        }
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 4
                    Repeater {
                        model: [["left", "⇤"], ["hcenter", "↔"], ["right", "⇥"], ["top", "⤒"], ["vcenter", "↕"], ["bottom", "⤓"]]
                        delegate: Button {
                            required property var modelData
                            objectName: "sceneAlign-" + modelData[0]
                            text: modelData[1]
                            enabled: editor.selection.length > 0
                            Accessible.name: qsTr("Alinhar %1").arg(modelData[0])
                            onClicked: editor.edit("align", {layerIds: editor.selection, mode: modelData[0]})
                        }
                    }
                }
                RowLayout {
                    enabled: editor.selectedLayer !== null
                    Button { text: qsTr("Frente"); onClicked: editor.edit("reorder", {layerId: editor.selectedLayer.id, index: editor.layers.length}) }
                    Button { text: qsTr("Trás"); onClicked: editor.edit("reorder", {layerId: editor.selectedLayer.id, index: 0}) }
                    Button { text: qsTr("Remover"); onClicked: editor.edit("remove-layer", {layerId: editor.selectedLayer.id}) }
                }
                Label { text: qsTr("Tratamento"); color: editor.textColor; font.bold: true; visible: editor.selectedLayer !== null }
                GridLayout {
                    visible: editor.selectedLayer !== null
                    columns: 2
                    Label { text: qsTr("Preset"); color: editor.mutedColor }
                    ComboBox {
                        objectName: "sceneRecipePreset"
                        model: ["none", "mono", "warm", "cool"]
                        currentIndex: editor.selectedLayer ? model.indexOf(editor.selectedLayer.recipe.preset) : 0
                        onActivated: function(index) { editor.edit("set-recipe", {layerId: editor.selectedLayer.id, recipe: {preset: model[index]}}) }
                    }
                    Label { text: qsTr("Brilho"); color: editor.mutedColor }
                    Slider {
                        from: -1; to: 1
                        value: editor.selectedLayer ? editor.selectedLayer.recipe.brightness : 0
                        onPressedChanged: if (!pressed) editor.edit("set-recipe", {layerId: editor.selectedLayer.id, recipe: {brightness: value}})
                    }
                    Label { text: qsTr("Saturação"); color: editor.mutedColor }
                    Slider {
                        from: 0; to: 2
                        value: editor.selectedLayer ? editor.selectedLayer.recipe.saturation : 1
                        onPressedChanged: if (!pressed) editor.edit("set-recipe", {layerId: editor.selectedLayer.id, recipe: {saturation: value}})
                    }
                    Label { text: qsTr("Enquadrar"); color: editor.mutedColor }
                    ComboBox {
                        model: ["cover", "contain"]
                        currentIndex: editor.selectedLayer ? model.indexOf(editor.selectedLayer.recipe.fit) : 0
                        onActivated: function(index) { editor.edit("set-recipe", {layerId: editor.selectedLayer.id, recipe: {fit: model[index]}}) }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
    }

    FileDialog {
        id: photoDialog
        title: qsTr("Trazer fotos")
        fileMode: FileDialog.OpenFiles
        nameFilters: [qsTr("Imagens (*.png *.jpg *.jpeg *.webp)")]
        onAccepted: selectedFiles.forEach(function(url) { editor.importFile(url, "folder") })
    }
    FileDialog {
        id: libraryDialog
        title: qsTr("Escolher da biblioteca canônica")
        fileMode: FileDialog.OpenFiles
        nameFilters: [qsTr("Imagens (*.png *.jpg *.jpeg *.webp)")]
        onAccepted: selectedFiles.forEach(function(url) { editor.importFile(url, "library") })
    }
}

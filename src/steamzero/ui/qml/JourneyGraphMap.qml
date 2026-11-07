// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Mapa da Jornada: cartões de instância arrastáveis e ligações por saída.
// Lê o mesmo documento da lista e do inspetor; toda mudança volta como pedido
// transacional ao serviço (set-layout / add-connection). Não executa operações.
import QtQuick
import QtQuick.Controls

Flickable {
    id: map
    objectName: "journeyGraphMap"

    property var menus: []
    property var connections: []
    property string entryMenuId: ""
    property string selectedMenuId: ""
    property string linkSourceId: ""
    property color cardColor: "#122131"
    property color borderColor: "#2a3a49"
    property color accentColor: "#13bdf2"
    property color textColor: "#f2f6fb"
    property color mutedColor: "#9eabba"
    property color errorColor: "#ff6b73"
    property var invalidConnectionIds: []
    readonly property real cardWidth: 168
    readonly property real cardHeight: 74
    readonly property var natureLabels: ({
        "free": qsTr("Menu livre"), "platforms": qsTr("Plataformas"),
        "games": qsTr("Jogos"), "categories": qsTr("Categorias"),
        "direct-launch": qsTr("Lançamento direto"), "transition": qsTr("Transição"),
        "session": qsTr("Sessão"), "recovery": qsTr("Recuperação")
    })

    signal menuSelected(string menuId)
    signal layoutRequested(string menuId, real x, real y)
    signal connectRequested(string fromId, string toId)

    clip: true
    contentWidth: Math.max(width, contentExtent().x + cardWidth + 40)
    contentHeight: Math.max(height, contentExtent().y + cardHeight + 40)

    function positionOf(menu, index) {
        if (menu && menu.layout)
            return Qt.point(Number(menu.layout.x), Number(menu.layout.y))
        return Qt.point(24 + (index % 4) * (cardWidth + 48), 24 + Math.floor(index / 4) * (cardHeight + 56))
    }

    function contentExtent() {
        let x = 0, y = 0
        for (let i = 0; i < menus.length; ++i) {
            const p = positionOf(menus[i], i)
            x = Math.max(x, p.x)
            y = Math.max(y, p.y)
        }
        return Qt.point(x, y)
    }

    function indexOf(menuId) {
        for (let i = 0; i < menus.length; ++i)
            if (menus[i].id === menuId)
                return i
        return -1
    }

    function cardCenter(menuId) {
        const index = indexOf(menuId)
        const item = index >= 0 ? cards.itemAt(index) : null
        if (!item)
            return null
        return Qt.point(item.x + cardWidth / 2, item.y + cardHeight / 2)
    }

    onMenusChanged: edges.requestPaint()
    onConnectionsChanged: edges.requestPaint()

    Item {
        id: surface
        width: map.contentWidth
        height: map.contentHeight

        Canvas {
            id: edges
            objectName: "journeyGraphEdges"
            anchors.fill: parent
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                ctx.lineWidth = 2
                for (let i = 0; i < map.connections.length; ++i) {
                    const link = map.connections[i]
                    if (!link.from || link.from.kind !== "menu" || !link.to || link.to.kind !== "menu")
                        continue
                    const a = map.cardCenter(link.from.id)
                    const b = map.cardCenter(link.to.id)
                    if (!a || !b)
                        continue
                    const invalid = map.invalidConnectionIds.indexOf(link.id) >= 0
                    ctx.strokeStyle = invalid ? map.errorColor
                        : (link.when === "user-input" ? map.accentColor : map.mutedColor)
                    ctx.setLineDash(link.when === "user-input" ? [] : [6, 4])
                    ctx.beginPath()
                    ctx.moveTo(a.x, a.y)
                    ctx.bezierCurveTo((a.x + b.x) / 2, a.y, (a.x + b.x) / 2, b.y, b.x, b.y)
                    ctx.stroke()
                }
            }
        }

        Repeater {
            id: cards
            model: map.menus
            delegate: Rectangle {
                id: card
                required property var modelData
                required property int index
                objectName: "journeyCard-" + modelData.id
                readonly property point home: map.positionOf(modelData, index)
                x: home.x
                y: home.y
                width: map.cardWidth
                height: map.cardHeight
                radius: 8
                color: map.cardColor
                border.width: map.selectedMenuId === modelData.id || map.linkSourceId === modelData.id ? 2 : 1
                border.color: map.linkSourceId === modelData.id ? map.accentColor
                    : (map.selectedMenuId === modelData.id ? map.textColor : map.borderColor)
                Accessible.role: Accessible.Button
                Accessible.name: modelData.name + (map.entryMenuId === modelData.id ? qsTr(" (entrada)") : "")
                onXChanged: edges.requestPaint()
                onYChanged: edges.requestPaint()

                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2
                    Text {
                        text: (map.entryMenuId === card.modelData.id ? "▶ " : "") + card.modelData.name
                        color: map.textColor
                        font.bold: true
                        elide: Text.ElideRight
                        width: parent.width
                    }
                    Text {
                        text: map.natureLabels[card.modelData.nature || ""] || qsTr("Menu")
                        color: map.mutedColor
                        font.pixelSize: 11
                    }
                    Text {
                        text: card.modelData.id
                        color: map.mutedColor
                        font.pixelSize: 10
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    drag.target: card
                    drag.threshold: 4
                    onClicked: {
                        if (map.linkSourceId !== "" && map.linkSourceId !== card.modelData.id) {
                            map.connectRequested(map.linkSourceId, card.modelData.id)
                            map.linkSourceId = ""
                        } else {
                            map.menuSelected(card.modelData.id)
                        }
                    }
                    onReleased: {
                        if (drag.active || card.x !== card.home.x || card.y !== card.home.y)
                            map.layoutRequested(card.modelData.id, Math.max(0, card.x), Math.max(0, card.y))
                    }
                }

                Button {
                    objectName: "journeyCardOutput-" + card.modelData.id
                    text: qsTr("Saída →")
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 4
                    height: 24
                    font.pixelSize: 11
                    Accessible.name: qsTr("Ligar uma saída de %1").arg(card.modelData.name)
                    onClicked: map.linkSourceId = map.linkSourceId === card.modelData.id ? "" : card.modelData.id
                }
            }
        }
    }

    ScrollBar.vertical: ScrollBar {}
    ScrollBar.horizontal: ScrollBar {}
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// O que o cartão mostra quando o jogo ainda não tem capa publicada. Repetir o
// título em corpo grande deixava o carrossel como uma pilha de textos cortados
// pelos vizinhos; aqui a ausência de arte tem forma própria e o título, quando
// aparece, é legenda — o nome em destaque já está fora do cartão.
import QtQuick

Item {
    id: fallback

    property string title: ""
    // Cartão vizinho ou miniatura: só a forma, sem legenda.
    property bool showTitle: true
    property bool highContrast: false
    property color accentColor: "#22d3ee"
    property real textScale: 1.0

    // Primeiro caractere alfanumérico: títulos reais começam com aspas,
    // parênteses e colchetes.
    readonly property string monogram: {
        const match = String(fallback.title || "").match(/[0-9A-Za-zÀ-ÿ]/)
        return match ? match[0].toUpperCase() : "?"
    }

    clip: true

    Rectangle {
        anchors.fill: parent
        radius: 6
        gradient: Gradient {
            GradientStop { position: 0.0; color: fallback.highContrast ? "#000000" : "#1d3348" }
            GradientStop { position: 1.0; color: fallback.highContrast ? "#000000" : "#0b1622" }
        }
    }
    Text {
        objectName: "coverFallbackMonogram"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: fallback.showTitle ? -parent.height * 0.10 : 0
        text: fallback.monogram
        textFormat: Text.PlainText
        color: fallback.highContrast ? "#ffffff" : fallback.accentColor
        opacity: fallback.highContrast ? 1 : 0.55
        font.pixelSize: Math.max(24, Math.min(parent.width, parent.height) * 0.42)
        font.bold: true
    }
    Text {
        objectName: "coverFallbackTitle"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Math.max(8, parent.width * 0.07)
        visible: fallback.showTitle
        text: String(fallback.title || qsTr("Sem capa"))
        textFormat: Text.PlainText
        color: fallback.highContrast ? "#ffffff" : "#d8e4ed"
        font.pixelSize: Math.max(12, Math.min(16 * fallback.textScale, parent.width * 0.085))
        wrapMode: Text.Wrap
        maximumLineCount: 3
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
    }
}

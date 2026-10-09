// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Galeria declarativa de save-states. O componente só consome o read model;
// captura, backup e restauração pertencem ao adapter da sessão.

import QtQuick

Item {
    id: gallery

    property var model: null
    property var theme: null
    property var accessibility: ({"highContrast": false, "visualScale": 1.0,
        "reducedMotion": false})
    property string mode: "loadState"
    property int selectedIndex: 0
    readonly property var entries: model && Array.isArray(model.entries) ? model.entries : []
    readonly property var themeTokens: theme && theme.resolved ? theme.resolved : ({})
    readonly property var themeColors: themeTokens.color || ({})
    readonly property var surfaces: theme && theme.sceneSurfaces ? theme.sceneSurfaces : ({})
    readonly property var surfaceSlots: surfaces.slots || ({})
    readonly property var surfaceComponents: surfaces.components || ({})
    readonly property var gallerySlot: surfaceSlots.saveStates || null
    readonly property var galleryComponent: gallerySlot
        ? surfaceComponents[gallerySlot.component] || null : null
    readonly property var visibleEntries: galleryComponent && Number(galleryComponent.maxItems) > 0
        ? entries.slice(0, Number(galleryComponent.maxItems)) : entries
    readonly property bool highContrast: !!(accessibility && accessibility.highContrast)
        || (theme && theme.highContrast === true)
    readonly property bool reducedMotion: !!(accessibility && accessibility.reducedMotion)
        || (theme && theme.reducedMotion === true)
    readonly property real visualScale: accessibility && Number(accessibility.visualScale) > 0
        ? Number(accessibility.visualScale) : 1.0
    readonly property color backgroundColor: highContrast ? "#000000"
        : _safeColor(themeColors.background, "#071019")
    readonly property color panelColor: highContrast ? "#000000"
        : _safeColor(themeColors.surface, "#101c2b")
    readonly property color accentColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.accent, "#7dd3fc")
    readonly property color textColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.text, "#f8fafc")
    readonly property color mutedColor: highContrast ? "#e8e8e8"
        : _safeColor(themeColors.textMuted, "#a8b8ca")
    readonly property color borderColor: highContrast ? "#ffffff"
        : _safeColor(themeColors.border, "#2b4963")
    readonly property var selectedEntry: selectedIndex >= 0 && selectedIndex < visibleEntries.length
        ? visibleEntries[selectedIndex] : null

    signal slotRequested(string actionId, int slot)
    signal closeRequested()

    function setModel(value) {
        gallery.model = value
        gallery.selectedIndex = 0
    }

    function openGallery(actionId) {
        gallery.mode = String(actionId || "loadState")
        gallery.selectedIndex = 0
        gallery.visible = true
        gallery.forceActiveFocus()
    }

    function closeGallery() {
        if (!gallery.visible)
            return false
        gallery.visible = false
        gallery.closeRequested()
        return true
    }

    function move(direction) {
        if (visibleEntries.length === 0)
            return false
        let step = direction === "left" || direction === "up" ? -1 : 1
        gallery.selectedIndex = (gallery.selectedIndex + step + visibleEntries.length) % visibleEntries.length
        return true
    }

    function activateFocused() {
        if (selectedEntry === null || selectedEntry.available !== true)
            return false
        if (mode === "loadState" && model && model.loadAvailable !== true)
            return false
        gallery.slotRequested(mode, Number(selectedEntry.slot))
        return true
    }

    // O carimbo chega em ISO 8601; ninguém lê "2026-09-17T23:31:11.913622+00:00".
    function formatTimestamp(value) {
        const parsed = new Date(String(value || ""))
        if (isNaN(parsed.getTime()))
            return qsTr("Data indisponível")
        return Qt.formatDateTime(parsed, "dd/MM/yyyy HH:mm")
    }

    function compatibilityLabel(value) {
        const labels = {
            "native": qsTr("formato nativo"), "compatible": qsTr("compatível"),
            "incompatible": qsTr("incompatível")
        }
        return labels[String(value || "")] || qsTr("compatibilidade desconhecida")
    }

    function _text(value, fallback) {
        return typeof value === "string" && value.length > 0 ? value : fallback
    }

    function _safeColor(value, fallback) {
        if (typeof value !== "string")
            return fallback
        const candidate = value.trim()
        return /^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(candidate)
            ? candidate : fallback
    }

    visible: false
    focus: visible
    z: 50

    Rectangle {
        anchors.fill: parent
        // A galeria é uma superfície modal exclusiva. Deixá-la translúcida
        // sobre o OSD base duplica títulos, ações e rodapés durante um save.
        color: gallery.backgroundColor
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 1080)
        height: Math.min(parent.height - 64, 560)
        radius: 18
        color: gallery.panelColor
        border.width: gallery.highContrast ? 3 : 1
        border.color: gallery.borderColor

        Column {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 16

            Row {
                width: parent.width
                spacing: 16
                Text {
                    width: parent.width - closeButton.width - 16
                    text: gallery.mode === "saveState"
                        ? qsTr("SAVE-STATE · ESCOLHER SLOT")
                        : qsTr("SAVE-STATE · CARREGAR")
                    color: gallery.accentColor
                    font.pixelSize: 18 * gallery.visualScale
                    font.bold: true
                    elide: Text.ElideRight
                }
                Rectangle {
                    id: closeButton
                    width: 116
                    height: 44
                    radius: 8
                    color: gallery.panelColor
                    border.width: activeFocus ? 3 : 1
                    border.color: activeFocus ? gallery.accentColor : gallery.borderColor
                    Text {
                        anchors.centerIn: parent
                        text: qsTr("Fechar")
                        color: gallery.textColor
                        font.pixelSize: 14 * gallery.visualScale
                    }
                    TapHandler { onTapped: gallery.closeGallery() }
                }
            }

            Text {
                width: parent.width
                text: entries.length > 0
                    ? qsTr("%1 slot(s) · selecione um estado compatível").arg(entries.length)
                    : _text(model ? model.reason : "", qsTr("Nenhum save-state disponível."))
                color: entries.length > 0 ? gallery.mutedColor : gallery.accentColor
                font.pixelSize: 14 * gallery.visualScale
                wrapMode: Text.Wrap
            }

            ListView {
                id: slotList
                width: parent.width
                height: 300
                orientation: ListView.Horizontal
                spacing: 14
                clip: true
                model: gallery.visibleEntries
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: 190
                    height: 270
                    radius: 12
                    color: modelData.available === true
                        ? (index === gallery.selectedIndex ? gallery.backgroundColor : gallery.panelColor)
                        : "#111b27"
                    opacity: modelData.available === true ? 1 : 0.62
                    border.width: index === gallery.selectedIndex ? 3 : 1
                    border.color: index === gallery.selectedIndex ? gallery.accentColor : gallery.borderColor
                    Accessible.name: qsTr("Slot %1").arg(modelData.slot)
                    Accessible.role: Accessible.Button
                    Accessible.description: modelData.available === true
                        ? qsTr("Save-state disponível")
                        : String(modelData.reason || qsTr("Save-state indisponível"))
                    Image {
                        id: thumbnail
                        anchors.top: parent.top
                        anchors.topMargin: 12
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 166
                        height: 132
                        visible: String(modelData.thumbnailUrl || "") !== ""
                        source: String(modelData.thumbnailUrl || "")
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: width * 2
                        sourceSize.height: height * 2
                    }
                    Rectangle {
                        anchors.top: parent.top
                        anchors.topMargin: 12
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 166
                        height: 132
                        visible: modelData.thumbnailFallback === true || !thumbnail.visible
                        color: gallery.panelColor
                        Text {
                            anchors.centerIn: parent
                            text: qsTr("SEM CAPTURA")
                            color: gallery.mutedColor
                            font.pixelSize: 12 * gallery.visualScale
                            font.bold: true
                        }
                    }
                    Column {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.margins: 12
                        spacing: 4
                        Text {
                            text: qsTr("Slot %1").arg(modelData.slot)
                            color: gallery.textColor
                            font.pixelSize: 15 * gallery.visualScale
                            font.bold: true
                        }
                        Text {
                            text: gallery.formatTimestamp(modelData.timestamp)
                            color: gallery.mutedColor
                            font.pixelSize: 11 * gallery.visualScale
                            elide: Text.ElideRight
                            width: parent.width
                        }
                        Text {
                            text: qsTr("%1 min · %2").arg(Math.floor(Number(modelData.playtimeSeconds || 0) / 60))
                                .arg(gallery.compatibilityLabel(modelData.compatibility))
                            color: gallery.mutedColor
                            font.pixelSize: 11 * gallery.visualScale
                        }
                    }
                    TapHandler {
                        onTapped: {
                            gallery.selectedIndex = index
                            gallery.activateFocused()
                        }
                    }
                }
                onCurrentIndexChanged: gallery.selectedIndex = currentIndex
            }

            Text {
                width: parent.width
                text: qsTr("← → Navegar   Enter Selecionar   Esc Fechar")
                color: gallery.mutedColor
                font.pixelSize: 13 * gallery.visualScale
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    Keys.onEscapePressed: gallery.closeGallery()
    Keys.onLeftPressed: gallery.move("left")
    Keys.onRightPressed: gallery.move("right")
    Keys.onUpPressed: gallery.move("left")
    Keys.onDownPressed: gallery.move("right")
    Keys.onReturnPressed: gallery.activateFocused()
    Keys.onEnterPressed: gallery.activateFocused()
    Keys.onSpacePressed: gallery.activateFocused()
}

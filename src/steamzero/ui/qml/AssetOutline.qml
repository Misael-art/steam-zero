// SPDX-License-Identifier: GPL-3.0-or-later
// Engine-owned alpha dilation. Themes can only select the bounded recipe.
import QtQuick

ShaderEffect {
    id: effect
    required property Item source
    property real radius: 1
    property color outlineColor: "white"
    property rect paintedRect: Qt.rect(0, 0, source.width, source.height)
    readonly property real padding: Math.ceil(radius) + 1
    readonly property vector2d outputSize: Qt.vector2d(width, height)
    readonly property vector4d imageRect: Qt.vector4d(
        padding + paintedRect.x, padding + paintedRect.y,
        Math.max(1, paintedRect.width), Math.max(1, paintedRect.height))
    x: -padding
    y: -padding
    width: source.width + 2 * padding
    height: source.height + 2 * padding
    fragmentShader: "shaders/outline.frag.qsb"
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// A superfície de OSD já tinha contrato e componentes, mas não tinha uma
// entrada de teclado na cena raiz. Este harness prova o caminho de produção:
// sessão canônica ativa -> tecla de menu -> OSD aberto -> mesma tecla fecha.
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 800

    readonly property var focusMap: ({
        "initial": "library:game",
        "rows": ["library:game"],
        "diagnostics": [],
        "nodes": {
            "library:game": {"id": "library:game", "section": "library",
                             "column": 0, "up": null, "down": null,
                             "left": null, "right": null, "action": null}
        }
    })
    readonly property var model: ({
        "focusMap": harness.focusMap,
        "sections": [{"id": "library", "title": "Biblioteca",
                      "items": [{"id": "game", "title": "AURA Test"}]}],
        "catalogSummary": {},
        "returnContext": null
    })

    Component { id: sceneComponent; LauncherMain {} }
    Component { id: overlayComponent; LauncherSessionOverlay {} }
    SignalSpy {
        id: actionSpy
        objectName: "sessionOverlayActionSpy"
        signalName: "actionRequested"
    }

    TestCase {
        name: "LauncherSessionOverlayTrigger"
        when: windowShown

        function createActiveSessionScene() {
            const scene = createTemporaryObject(sceneComponent, harness)
            verify(scene !== null)
            scene.model = harness.model
            scene.loadState = "ready"
            scene.requestActivate()
            tryVerify(function() { return scene.active }, 5000)
            const shell = scene._activeLauncherShell()
            verify(shell !== null)
            shell.sessionGameId = "game"
            shell.launchState = "emulator-visible"
            return scene
        }

        function test_menu_key_opens_and_closes_osd_for_active_session() {
            const scene = createActiveSessionScene()
            keyClick(Qt.Key_F1)
            tryCompare(scene, "sessionOverlayOpen", true)
            verify(scene.sessionOverlayError.indexOf("AURA-OSD-") === 0,
                   "sem bridge no harness, o erro precisa continuar diagnosticável")
            keyClick(Qt.Key_F1)
            tryCompare(scene, "sessionOverlayOpen", false)
            keyClick(Qt.Key_Menu)
            tryCompare(scene, "sessionOverlayOpen", true)
            keyClick(Qt.Key_Menu)
            tryCompare(scene, "sessionOverlayOpen", false)
        }

        function test_menu_key_is_ignored_without_canonical_session() {
            const scene = createActiveSessionScene()
            const shell = scene._activeLauncherShell()
            shell.sessionGameId = ""
            compare(scene.sessionOverlayOpen, false)
            compare(scene.toggleSessionOverlay(), false)
            keyClick(Qt.Key_F1)
            compare(shell.sessionGameId, "")
            compare(scene.sessionOverlayOpen, false)
        }

        function test_journey_stage_theme_changes_the_session_consumer() {
            const overlay = createTemporaryObject(overlayComponent, harness,
                {"width": 1280, "height": 800})
            verify(overlay !== null)
            const theme = {
                "highContrast": false,
                "reducedMotion": false,
                "resolved": {"color": {
                    "background": "#010203",
                    "surface": "#121314",
                    "accent": "#cc22dd",
                    "text": "#f0f0f0",
                    "textMuted": "#b0b0b0"
                }},
                "sceneSurfaces": {
                    "slots": {
                        "osd": {"component": "compactOsd"},
                        "saveStates": {"component": "compactSaves"}
                    },
                    "components": {
                        "compactOsd": {"kind": "osd", "items": ["pause"], "maxItems": 1},
                        "compactSaves": {"kind": "saveGallery", "maxItems": 1}
                    }
                }
            }
            const overlayModel = {
                "gameId": "celeste",
                "sessionId": "synthetic-session",
                "state": "suspended",
                "visible": true,
                "focusedAction": "pause",
                "actions": [
                    {"id": "pause", "label": "Retomar", "enabled": true},
                    {"id": "saveState", "label": "Salvar", "enabled": true}
                ],
                "saveStates": {
                    "state": "ready", "available": true, "saveAvailable": true,
                    "loadAvailable": true, "reason": "",
                    "entries": [
                        {"slot": 4, "timestamp": "2026-10-04T12:00:00Z", "available": true},
                        {"slot": 5, "timestamp": "2026-10-04T12:10:00Z", "available": true}
                    ]
                },
                "journeyAppearance": {"stageId": "pause", "theme": theme}
            }
            overlay.setModel(overlayModel)
            overlay.openOverlay()
            compare(String(overlay.accentColor), "#cc22dd")
            compare(overlay.actions.length, 1)
            compare(overlay.actions[0].id, "pause")
            compare(overlay.activeSurfaceSlot, "osd")

            overlay.setModel(Object.assign({}, overlayModel, {
                "journeyAppearance": {"stageId": "saves", "theme": theme}
            }))
            compare(overlay.activeSurfaceSlot, "saveStates")
            const gallery = findChild(overlay, "launcherSessionSaveStateGallery")
            verify(gallery !== null)
            compare(gallery.visibleEntries.length, 1)
        }

        function test_exit_requests_confirmation_before_dispatch() {
            const overlay = createTemporaryObject(overlayComponent, harness,
                {"width": 900, "height": 640})
            verify(overlay !== null)
            overlay.setModel({
                "gameId": "celeste",
                "sessionId": "synthetic-session",
                "state": "running",
                "visible": true,
                "focusedAction": "exit",
                "actions": [
                    {"id": "exit", "label": "Sair do jogo", "enabled": true}
                ]
            })
            overlay.openOverlay()
            actionSpy.target = overlay
            actionSpy.clear()

            verify(overlay.activateFocused())
            const confirmation = findChild(overlay, "launcherSessionExitConfirmation")
            verify(confirmation !== null)
            tryCompare(confirmation, "visible", true)
            confirmation.reject()
            compare(actionSpy.count, 0)

            verify(overlay.activateFocused())
            confirmation.accept()
            compare(actionSpy.count, 1)
            compare(actionSpy.signalArguments[0][0], "exit")
        }
    }
}

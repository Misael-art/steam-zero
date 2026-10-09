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
    Component { id: peripheralsComponent; LauncherSessionPeripherals {} }
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

        function test_model_refresh_keeps_the_action_the_user_moved_to() {
            const overlay = createTemporaryObject(overlayComponent, harness,
                {"width": 1280, "height": 800})
            verify(overlay !== null)
            const model = {
                "state": "running", "focusedAction": "saveState",
                "actions": [
                    {"id": "saveState", "label": "Galeria de saves", "enabled": true},
                    {"id": "pause", "label": "Pausar", "enabled": true},
                    {"id": "exit", "label": "Sair do jogo", "enabled": true}
                ]
            }
            overlay.setModel(model)
            overlay.openOverlay()
            compare(overlay.actions[overlay.selectedIndex].id, "saveState")

            verify(overlay.move("right"))
            compare(overlay.actions[overlay.selectedIndex].id, "pause")
            // A sessão republica o estado enquanto o overlay está aberto.
            overlay.setModel(Object.assign({}, model))
            compare(overlay.actions[overlay.selectedIndex].id, "pause",
                    "a atualização do estado devolveu o foco à ação inicial")

            // Ação que sumiu do modelo: o foco volta ao inicial, não a um índice órfão.
            overlay.setModel(Object.assign({}, model, {"actions": [model.actions[0], model.actions[2]]}))
            compare(overlay.actions[overlay.selectedIndex].id, "saveState")
        }

        function test_exit_confirmation_is_operable_by_keyboard_and_defaults_to_cancel() {
            const overlay = createTemporaryObject(overlayComponent, harness,
                {"width": 1280, "height": 800})
            verify(overlay !== null)
            const requested = []
            overlay.actionRequested.connect(function(actionId) { requested.push(actionId) })
            overlay.setModel({
                "state": "suspended", "focusedAction": "exit",
                "actions": [
                    {"id": "pause", "label": "Retomar", "enabled": true},
                    {"id": "exit", "label": "Sair do jogo", "enabled": true}
                ]
            })
            overlay.openOverlay()
            verify(overlay.activateFocused())
            const dialog = findChild(overlay, "launcherSessionExitConfirmation")
            verify(dialog !== null, "a confirmação de saída não foi encontrada")
            tryCompare(dialog, "opened", true)
            compare(dialog.choice, 0, "o foco da confirmação precisa nascer em Cancelar")

            dialog.activateChoice()
            tryCompare(dialog, "opened", false)
            compare(requested.length, 0, "Cancelar não pode pedir o encerramento")

            verify(overlay.activateFocused())
            tryCompare(dialog, "opened", true)
            compare(dialog.choice, 0, "reabrir precisa voltar o foco para Cancelar")
            dialog.choice = 1
            dialog.activateChoice()
            tryCompare(dialog, "opened", false)
            compare(requested.length, 1)
            compare(requested[0], "exit")
        }

        function test_action_labels_state_and_unavailable_reason_are_readable() {
            const overlay = createTemporaryObject(overlayComponent, harness,
                {"width": 1280, "height": 800})
            verify(overlay !== null)
            overlay.setModel({
                "state": "running", "focusedAction": "rewind",
                "actions": [
                    {"id": "rewind", "label": "Rebobinar", "enabled": false,
                     "reason": "O adapter não declarou suporte para esta ação."},
                    {"id": "pause", "label": "Pausar", "enabled": true}
                ]
            })
            overlay.openOverlay()
            compare(overlay.stateLabel("running"), "em jogo")
            compare(overlay.stateLabel("suspended"), "pausado")
            compare(overlay.focusedReason,
                    "Rebobinar: O adapter não declarou suporte para esta ação.")
            verify(overlay.move("right"))
            compare(overlay.focusedReason, "")
        }

        function test_session_bezel_reports_launch_configuration_without_claiming_pixels() {
            const peripherals = createTemporaryObject(peripheralsComponent, harness,
                {"width": 1280, "height": 800})
            verify(peripherals !== null)
            const resourceId = "asset://bezels/org.test.bezel@1.2.3-" + "a".repeat(64) + ".png"
            peripherals.setModel({
                "state": "ready",
                "selectedBezel": resourceId,
                "appliedBezel": null,
                "bezelExecutionState": "launch-configured-unconfirmed",
                "bezelApplyMode": "next-launch",
                "bezels": [{
                    "id": resourceId,
                    "label": "Bezel de teste",
                    "assetUrl": resourceId,
                    "available": true,
                    "compatible": true,
                    "selected": true,
                    "applied": false,
                    "origin": "custom-theme",
                    "version": "1.2.3",
                    "license": "CC-BY-4.0",
                    "applyMode": "next-launch",
                    "executionState": "launch-configured-unconfirmed",
                    "reason": "runtime e pixels ainda não confirmados"
                }]
            })
            peripherals.openSurface()
            const execution = findChild(peripherals, "sessionBezelExecutionStatus")
            verify(execution !== null)
            verify(execution.text.indexOf("ainda não confirmaram") >= 0, execution.text)
            verify(execution.text.indexOf("próximo launch") >= 0, execution.text)
            const catalog = findChild(peripherals, "sessionBezelCatalog")
            verify(catalog !== null)
            compare(catalog.count, 1)
            verify(catalog.itemAt(0).text.indexOf("CC-BY-4.0") >= 0)
            verify(catalog.itemAt(0).text.indexOf("selecionado") >= 0)
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

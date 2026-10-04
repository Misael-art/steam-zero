// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1100
    height: 820

    property var requests: []
    property var delayedResponse: null
    property bool delayNextPlay: false
    property string launchedGameId: ""
    property var nextView: ({
        "active": true,
        "journeyId": "org.steamzero.qml-journey",
        "journeyName": "Jornada QML",
        "menuId": "platforms",
        "menuName": "Plataformas",
        "generation": 0,
        "selectedItemId": "nes",
        "scrollPosition": 0,
        "focusId": "row:nes",
        "canGoBack": false,
        "sourceState": "available",
        "resultState": "available",
        "totalCount": 2,
        "resultCount": 2,
        "items": [
            {"id": "nes", "title": "NES"},
            {"id": "snes", "title": "Super Nintendo"}
        ],
        "availableEvents": [
            {"event": "select", "action": "navigate", "label": "Abrir"},
            {"event": "route", "connectionId": "platforms-years",
             "action": "navigate", "label": "Explorar por ano"}
        ],
        "facets": [],
        "diagnosticCode": "",
        "diagnosticMessage": "",
        "recoveryAction": ""
    })
    property var cinemaScene: ({
        "focusId": "library:celeste",
        "selected": 0,
        "items": [],
        "layoutId": "journeyCovers",
        "layouts": {"journeyCovers": {"entries": [
            {"x": 120, "y": 80, "width": 300, "height": 420,
             "scale": 1, "opacity": 1, "z": 0, "highlighted": true}
        ]}},
        "performanceTier": "balanced",
        "theme": {
            "resolutionState": "resolved",
            "sceneResolutionState": "resolved",
            "compiledScene": {"views": [{"id": "gamelist", "elements": [
                {"id": "xml-heading", "kind": "text", "text": "Cena XML executada",
                 "layout": {"x": 0.08, "y": 0.08, "width": 0.42, "height": 0.08},
                 "appearance": {}}
            ]}]},
            "highContrast": false,
            "reducedMotion": false,
            "resolved": {
                "color": {"accent": "#cc22dd", "text": "#112233", "textMuted": "#445566"},
                "motion": {"durationNormal": 345},
                "performance": {"defaultTier": "balanced"}
            },
            "effects": {
                "contextualBackdrop": [
                    {"type": "vignette", "parameters": {"color": "#000000", "strength": 0.4}}
                ],
                "focusedCover": [],
                "peripheralCover": []
            }
        }
    })

    LauncherJourney {
        id: journey
        anchors.fill: parent
        view: harness.nextView
        requestFunction: function(method, path, body, done) {
            if (method === "GET" && path === "/journey/current") {
                done(200, JSON.stringify(harness.nextView))
                return true
            }
            if (method === "GET" && path.indexOf("/cinema?") === 0) {
                done(200, JSON.stringify(Object.assign({}, harness.cinemaScene, {
                    "focusId": journey.cinemaFocusId,
                    "journeyId": journey.view.journeyId,
                    "menuId": journey.view.menuId,
                    "journeyGeneration": journey.view.generation,
                    "layoutId": "journeyCovers"
                })))
                return true
            }
            harness.requests = harness.requests.concat([body])
            if (body.event === "select") {
                done(200, JSON.stringify({
                    "requestId": body.requestId,
                    "state": "navigated",
                    "view": {
                        "active": true,
                        "journeyId": "org.steamzero.qml-journey",
                        "journeyName": "Jornada QML",
                        "menuId": "games",
                        "menuName": "Jogos",
                        "generation": Number(body.generation) + 1,
                        "selectedItemId": "game:celeste",
                        "scrollPosition": 0,
                        "focusId": "row:celeste",
                        "canGoBack": true,
                        "sourceState": "available",
                        "resultState": "available",
                        "totalCount": 1,
                        "resultCount": 1,
                        "items": [
                            {"id": "game:celeste", "gameId": "celeste", "title": "Celeste"}
                        ],
                        "availableEvents": [{"event": "play", "action": "launch", "label": "Jogar"}],
                        "facets": [{
                            "fieldId": "year",
                            "label": "Ano",
                            "type": "integer",
                            "selected": false,
                            "options": [
                                {"kind": "all", "label": "Todos", "count": 1},
                                {"kind": "value", "value": 2018, "label": "2018", "count": 1}
                            ]
                        }],
                        "diagnosticCode": "",
                        "diagnosticMessage": "",
                        "recoveryAction": ""
                    }
                }))
                return true
            }
            if (body.event === "play" && harness.delayNextPlay) {
                harness.delayNextPlay = false
                harness.delayedResponse = done
                return true
            }
            if (body.event === "play") {
                done(200, JSON.stringify({
                    "requestId": body.requestId,
                    "state": "operation-request",
                    "operationRequest": {
                        "action": "launch",
                        "gameId": "celeste",
                        "focusId": "library:celeste"
                    }
                }))
                return true
            }
            if (body.event === "open-saves") {
                done(200, JSON.stringify({
                    "requestId": body.requestId,
                    "state": "operation-confirmed",
                    "saveStates": {
                        "state": "ready",
                        "available": true,
                        "saveAvailable": true,
                        "loadAvailable": true,
                        "reason": "",
                        "entries": [{
                            "slot": 4,
                            "timestamp": "2026-10-04T12:00:00Z",
                            "available": true,
                            "compatibility": "native"
                        }]
                    },
                    "view": Object.assign({}, journey.view, {
                        "generation": Number(body.generation) + 1
                    })
                }))
                return true
            }
            if (body.event === "exit") {
                done(200, JSON.stringify({
                    "requestId": body.requestId,
                    "state": "operation-pending",
                    "diagnosticCode": "JOURNEY-SESSION-EXIT-PENDING",
                    "diagnosticMessage": "aguardando closed",
                    "view": journey.view
                }))
                return true
            }
            if (body.event === "route" && body.connectionId === "platforms-years") {
                done(200, JSON.stringify({
                    "requestId": body.requestId,
                    "state": "navigated",
                    "view": Object.assign({}, harness.nextView, {
                        "menuId": "years",
                        "menuName": "Anos",
                        "generation": Number(body.generation) + 1,
                        "selectedItemId": "emulation:celeste",
                        "items": [{"id": "emulation:celeste", "gameId": "celeste", "title": "Celeste"}]
                    })
                }))
                return true
            }
            done(200, JSON.stringify({
                "requestId": body.requestId,
                "state": "filtered",
                "view": Object.assign({}, journey.view, {
                    "generation": Number(body.generation) + 1,
                    "filters": {"year": 2018},
                    "selected": true
                })
            }))
            return true
        }
        onLaunchRequested: function(gameId, _focusId) { harness.launchedGameId = gameId }
    }

    LauncherCinema {
        id: cinema
        x: 0
        y: 0
        width: 1
        height: 1
        visible: false
        scene: harness.cinemaScene
    }

    TestCase {
        name: "LauncherJourneyKeyboardAndTheme"
        when: windowShown

        function test_keyboard_facets_theme_and_stale_response_recovery() {
            journey.forceActiveFocus(Qt.OtherFocusReason)
            tryVerify(function() { return journey.activeFocus }, 2000,
                      "LauncherJourney precisa receber foco antes das teclas")
            compare(journey.items.length, 2)
            compare(cinema.motionDuration, 345)
            compare(String(cinema.accentColor), "#cc22dd")
            compare(String(cinema.primaryTextColor), "#112233")
            compare(cinema.contextualEffectStack.length, 1)
            compare(cinema.contextualEffectStack[0].type, "vignette")

            keyClick(Qt.Key_Down)
            compare(journey.currentIndex, 1)
            keyClick(Qt.Key_Return)
            compare(harness.requests.length, 1)
            compare(harness.requests[0].event, "select")
            compare(harness.requests[0].recordId, "snes")
            compare(journey.view.menuId, "games")
            compare(journey.items[0].gameId, "celeste")

            journey.chooseFacet("year", {"kind": "value", "value": 2018})
            compare(harness.requests[1].event, "facet")
            compare(harness.requests[1].fieldId, "year")
            compare(harness.requests[1].value, 2018)

            journey.cinemaMode = true
            tryVerify(function() { return journey.cinemaScene !== null })
            const cinemaComponent = findChild(journey, "journeyCinema")
            verify(cinemaComponent !== null)
            compare(journey.cinemaScene.menuId, "games")
            compare(journey.cinemaScene.theme.resolved.color.accent, "#cc22dd")
            compare(cinemaComponent.activeLayout.entries[0].width, 300)
            compare(cinemaComponent.externalSceneAvailable, true)
            compare(cinemaComponent.externalViewData.id, "gamelist")
            compare(findChild(cinemaComponent, "launcherCinemaXmlScene").drawnCount, 1)
            compare(journey.cinemaMode, true)

            harness.delayNextPlay = true
            verify(journey.playCurrent())
            verify(typeof harness.delayedResponse === "function")
            const staleResponse = harness.delayedResponse
            verify(journey.refresh())
            staleResponse(200, JSON.stringify({
                "requestId": "late",
                "state": "operation-unavailable",
                "diagnosticCode": "STALE",
                "diagnosticMessage": "resposta atrasada"
            }))
            compare(journey.view.menuId, "platforms")
            compare(journey.message, "")
            compare(journey.busy, false)

            journey.view = Object.assign({}, harness.nextView, {
                "menuId": "games",
                "menuName": "Jogos",
                "generation": 3,
                "selectedItemId": "game:celeste",
                "items": [{"id": "game:celeste", "gameId": "celeste", "title": "Celeste"}],
                "availableEvents": [
                    {"event": "play", "action": "launch", "label": "Jogar"},
                    {"event": "open-saves", "action": "open-saves", "label": "Saves"},
                    {"event": "save", "action": "save", "label": "Salvar"},
                    {"event": "load", "action": "load", "label": "Carregar"}
                ],
                "sessionCapabilities": {
                    "open-saves": {"available": true, "reason": ""},
                    "save": {"available": true, "reason": ""},
                    "load": {"available": true, "reason": ""}
                },
                "facets": []
            })
            journey.forceActiveFocus(Qt.OtherFocusReason)
            keyClick(Qt.Key_P)
            compare(harness.requests[harness.requests.length - 1].event, "play")
            verify(journey.playCurrent())
            compare(harness.launchedGameId, "celeste")

            const savesButton = findChild(journey, "journeySessionEvent_open-saves")
            verify(savesButton !== null)
            verify(savesButton.enabled)
            mouseClick(savesButton)
            tryVerify(function() { return journey.saveGallery !== null })
            verify(findChild(journey, "journeySavesDialog").visible)
            const saveButton = findChild(journey, "journeySaveSlotSave")
            verify(saveButton !== null && saveButton.enabled)
            journey.saveSlot = 7
            mouseClick(saveButton)
            compare(harness.requests[harness.requests.length - 1].event, "save")
            compare(harness.requests[harness.requests.length - 1].slot, 7)

            const loadButton = findChild(journey, "journeySaveLoad_4")
            verify(loadButton !== null && loadButton.enabled)
            mouseClick(loadButton)
            compare(harness.requests[harness.requests.length - 1].event, "load")
            compare(harness.requests[harness.requests.length - 1].slot, 4)

            journey.view = Object.assign({}, harness.nextView, {
                "availableEvents": [
                    {"event": "select", "action": "navigate", "label": "Abrir"},
                    {"event": "route", "connectionId": "platforms-years",
                     "action": "navigate", "label": "Explorar por ano"}
                ]
            })
            journey.currentIndex = 0
            const routeButton = findChild(journey, "journeyRoute_platforms-years")
            verify(routeButton !== null && routeButton.enabled)
            mouseClick(routeButton)
            compare(harness.requests[harness.requests.length - 1].event, "route")
            compare(harness.requests[harness.requests.length - 1].connectionId, "platforms-years")
            compare(journey.view.menuId, "years")

            journey.view = Object.assign({}, harness.nextView, {
                "menuId": "games",
                "menuName": "Jogos",
                "generation": 4,
                "selectedItemId": "emulation:celeste",
                "items": [{"id": "emulation:celeste", "gameId": "celeste", "title": "Celeste"}],
                "availableEvents": [{"event": "exit", "action": "exit", "label": "Sair do jogo"}],
                "sessionCapabilities": {"exit": {"available": true, "reason": ""}},
                "facets": []
            })
            const beforeExit = harness.requests.length
            const exitButton = findChild(journey, "journeySessionEvent_exit")
            verify(exitButton !== null && exitButton.enabled)
            mouseClick(exitButton)
            const confirmation = findChild(journey, "journeyExitConfirmation")
            verify(confirmation !== null)
            tryCompare(confirmation, "visible", true)
            compare(harness.requests.length, beforeExit)
            confirmation.reject()
            compare(harness.requests.length, beforeExit)
            mouseClick(exitButton)
            confirmation.accept()
            compare(harness.requests.length, beforeExit + 1)
            compare(harness.requests[harness.requests.length - 1].event, "exit")
            compare(harness.requests[harness.requests.length - 1].confirmed, true)
            compare(journey.message.indexOf("aguardando") >= 0, true)
        }
    }
}

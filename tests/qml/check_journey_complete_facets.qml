// SPDX-License-Identifier: GPL-3.0-or-later
// Seleção e retorno da Jornada completa pela LauncherJourney e pela bridge HTTP real.

import QtQuick
import QtQuick.Controls
import QtTest
import "../../src/steamzero/ui/qml"
import "../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1100
    height: 820
    property var bridgeConfig: ({})
    property var requests: []

    function readConfig() {
        const request = new XMLHttpRequest()
        request.open("GET", Qt.resolvedUrl("../../build/journey-complete-facets-e2e.json"), false)
        request.send()
        if (request.status !== 0 && request.status !== 200)
            throw new Error("configuração da bridge de facetas não foi lida")
        return JSON.parse(request.responseText)
    }

    function bridgeRequest(method, path, body, onDone) {
        const entry = {method: method, path: path, body: body, done: false, status: 0}
        harness.requests = harness.requests.concat([entry])
        const index = harness.requests.length - 1
        const request = new XMLHttpRequest()
        request.open(method, harness.bridgeConfig.apiUrl + path)
        request.setRequestHeader("X-SteamZero-Token", harness.bridgeConfig.apiToken)
        if (body !== null)
            request.setRequestHeader("Content-Type", "application/json")
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE)
                return
            const updated = harness.requests.slice()
            updated[index] = Object.assign({}, updated[index], {
                done: true,
                status: request.status
            })
            harness.requests = updated
            onDone(request.status, request.responseText)
        }
        request.send(body === null ? null : JSON.stringify(body))
    }

    Item {
        id: stage
        width: 1100
        height: 300
        LauncherJourney {
            id: journey
            objectName: "journeyFacetSurface"
            anchors.fill: parent
            requestFunction: harness.bridgeRequest
        }
    }

    ExperienceJourneyPanel {
        id: studio
        objectName: "journeyFacetPreview"
        width: 1100
        height: 820
        visible: false
        requestAction: function(_actionId, _payload, _success, _failure) { return false }
    }

    TestCase {
        name: "JourneyCompleteFacets"
        when: windowShown

        function initTestCase() {
            harness.bridgeConfig = harness.readConfig()
        }

        function find(root, name) {
            if (!root)
                return null
            if (root.objectName === name)
                return root
            const objects = root.childItems !== undefined ? root.childItems : root.children
            for (let i = 0; i < (objects || []).length; ++i) {
                const hit = find(objects[i], name)
                if (hit)
                    return hit
            }
            return null
        }

        function byName(root, name) {
            const result = find(root, name)
            verify(result !== null, "controle QML ausente: " + name)
            return result
        }

        function waitIdle(menuId) {
            tryVerify(function() {
                return journey.view && journey.view.menuId === menuId && journey.busy !== true
            }, 5000, "menu " + menuId + " não ficou estável: "
                + (journey.view ? journey.view.menuId : "sem view")
                + " / " + journey.message)
        }

        function focusJourney() {
            journey.forceActiveFocus(Qt.OtherFocusReason)
            tryVerify(function() { return journey.activeFocus }, 2000,
                      "a Jornada não recebeu foco")
        }

        function titles() {
            const values = []
            for (let i = 0; i < journey.items.length; ++i)
                values.push(String(journey.items[i].title || journey.items[i].name || ""))
            return values
        }

        function showMeta(index, expected) {
            const list = byName(journey, "journeyResultList")
            tryVerify(function() { return list.count > index && list.height > 0 }, 2000,
                      "a lista ainda não desenhou a linha " + index)
            list.positionViewAtIndex(index, ListView.Contain)
            tryVerify(function() {
                return find(journey, "journeyResultMeta_" + index) !== null
            }, 2000, "a linha " + index + " não foi desenhada")
            compare(byName(journey, "journeyResultMeta_" + index).text, expected)
        }

        function test_studio_preview_uses_groups_only_when_the_menu_groups() {
            if (harness.bridgeConfig.mode !== "navigate")
                skip("a prévia do Studio roda uma vez, no modo navigate")
            studio.session = {
                sessionId: "preview",
                generation: 1,
                budgets: {maxMenus: 8},
                document: {
                    entryMenuId: "genres",
                    menus: [
                        {id: "genres", name: "Gêneros", groupBy: ["genre"],
                         source: {readModelId: "library.games"}},
                        {id: "games", name: "Jogos", groupBy: [],
                         source: {readModelId: "library.games"}}
                    ]
                }
            }
            studio.selectedMenuId = "genres"
            studio.previewResult = {
                groups: [
                    {values: {genre: "Action"}, count: 2},
                    {values: {genre: "RPG"}, count: 1},
                    {values: {genre: null}, count: 1}
                ],
                rows: [
                    {id: "emulation:alpha", title: "Alpha"},
                    {id: "emulation:beta", title: "Beta"},
                    {id: "emulation:gamma", title: "Gamma"},
                    {id: "emulation:delta", title: "Delta"}
                ],
                resultCount: 4,
                totalCount: 4,
                returnedCount: 4,
                resultState: "results",
                diagnosticMessage: ""
            }
            const facets = studio.previewEntries()
            compare(facets.length, 3)
            compare(facets[0].title, "Action")
            compare(facets[0].count, 2)
            compare(facets[0].facet, true)
            compare(facets[2].title, "Desconhecido")
            compare(facets[2].count, 1)
            studio.visible = true
            const scroll = byName(studio, "journeyInspectorScroll")
            const list = byName(studio, "journeyPreviewRows")
            const flickable = scroll.contentItem
            const point = list.mapToItem(flickable, 0, 0)
            flickable.contentY = Math.max(0, point.y)
            tryVerify(function() { return list.count === 3 }, 2000,
                      "a lista de prévia não publicou as três facetas")
            compare(byName(studio, "journeyPreviewResultCount").text,
                    "3 facetas · 4 jogos correspondentes")
            tryVerify(function() { return list.itemAtIndex(0) !== null }, 2000,
                      "o delegado da faceta não foi criado")
            compare(list.itemAtIndex(0).text, "Action · 2 jogos")
            compare(list.itemAtIndex(2).text, "Desconhecido · 1 jogos")
            studio.selectedMenuId = "games"
            const games = studio.previewEntries()
            compare(games.length, 4)
            compare(games[0].title, "Alpha")
            compare(games[0].facet, undefined)
            tryVerify(function() { return list.count === 4 && list.itemAtIndex(0) !== null },
                      2000, "a prévia sem groupBy não voltou a listar jogos")
            compare(list.itemAtIndex(0).text, "Alpha")
            compare(byName(studio, "journeyPreviewResultCount").text,
                    "4 resultados de 4 itens na fonte · exibindo 4")
            studio.visible = false
        }

        function openPlatforms() {
            journey.refresh()
            waitIdle("platforms")
            compare(titles(), ["NES", "Master System"])
            focusJourney()
        }

        function test_navigation_selection_return_unknown_and_stale_response() {
            if (harness.bridgeConfig.mode !== "navigate")
                skip("modo diferente de navigate")
            openPlatforms()
            keyClick(Qt.Key_Return)
            waitIdle("genres")
            compare(journey.view.filters.platformId, "nes-famicom")
            compare(titles(), ["Action", "RPG", "Desconhecido"])
            showMeta(0, "2 jogos")
            showMeta(1, "1 jogo")
            showMeta(2, "1 jogo")
            compare(journey.items[0].facet, true)
            compare(journey.items[0].gameId, undefined)

            const list = byName(journey, "journeyResultList")
            tryVerify(function() { return list.contentHeight > list.height + 16 }, 1000,
                      "a lista de gêneros não tem rolagem")
            list.contentY = 16
            tryVerify(function() { return Math.abs(list.contentY - 16) < 1 }, 1000,
                      "a lista não manteve a rolagem")
            const scrolled = list.contentY
            focusJourney()
            keyClick(Qt.Key_Return)
            waitIdle("games")
            compare(journey.view.menuId, "games")
            compare(journey.view.filters.genre, "Action")
            compare(titles(), ["Alpha", "Beta"])
            const select = harness.requests.filter(function(entry) {
                return entry.body && entry.body.event === "select" && entry.body.menuId === "genres"
            })
            compare(select.length, 1)
            compare(select[0].body.scrollPosition, scrolled)
            const actionFocus = select[0].body.focusId

            focusJourney()
            keyClick(Qt.Key_Escape)
            waitIdle("genres")
            compare(journey.view.selectedItemId, journey.items[0].id)
            compare(journey.currentIndex, 0)
            compare(journey.view.focusId, actionFocus)
            compare(journey.view.filters.platformId, "nes-famicom")
            compare(journey.view.filters.genre, undefined)
            tryVerify(function() {
                const restored = byName(journey, "journeyResultList")
                return Math.abs(restored.contentY - scrolled) < 1
                    && Math.abs(Number(journey.view.scrollPosition) - scrolled) < 1
            }, 1000, "a volta não restaurou a rolagem")

            focusJourney()
            keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Return)
            waitIdle("games")
            compare(titles(), ["Delta"])
            verify(journey.view.filters.genre === null, "gênero desconhecido não filtrou isUnknown")

            focusJourney()
            keyClick(Qt.Key_Escape)
            waitIdle("genres")
            focusJourney()
            keyClick(Qt.Key_Escape)
            waitIdle("platforms")
            mouseClick(byName(journey, "journeyRoute_platforms-years"))
            waitIdle("years")
            compare(journey.view.filters.platformId, "nes-famicom")
            compare(titles(), ["1987", "1986", "Desconhecido"])
            showMeta(0, "1 jogo")
            showMeta(1, "2 jogos")
            showMeta(2, "1 jogo")
            focusJourney()
            keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Return)
            waitIdle("games")
            compare(journey.view.filters.year, 1986)
            compare(titles(), ["Alpha", "Beta"])
            focusJourney()
            keyClick(Qt.Key_Escape)
            waitIdle("years")
            focusJourney()
            keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Return)
            waitIdle("games")
            compare(titles(), ["Delta"])
            verify(journey.view.filters.year === null, "ano desconhecido não filtrou isUnknown")

            const keptMenu = journey.view.menuId
            const keptGeneration = journey.view.generation
            journey.sendEvent("select", journey.items[0], {generation: 0})
            tryVerify(function() { return journey.busy !== true }, 5000, "resposta tardia não terminou")
            compare(journey.view.menuId, keptMenu)
            compare(journey.view.generation, keptGeneration)
            compare(titles(), ["Delta"])
            verify(journey.message.indexOf("JOURNEY-RESPONSE-STALE") >= 0,
                   "a resposta tardia não publicou o diagnóstico: " + journey.message)
        }

        function test_late_http_response_does_not_replace_the_visible_menu() {
            if (harness.bridgeConfig.mode !== "late")
                skip("modo diferente de late")
            openPlatforms()
            const generation = journey.view.generation
            focusJourney()
            keyClick(Qt.Key_Return)
            journey.refresh()
            tryVerify(function() {
                const post = harness.requests.find(function(entry) {
                    return entry.body && entry.body.event === "select" && entry.done
                })
                return post && journey.busy !== true && journey.view.menuId === "platforms"
            }, 5000, "a resposta atrasada ainda não foi descartada: " + journey.message)
            compare(journey.view.generation, generation)
            compare(titles(), ["NES", "Master System"])
            journey.refresh()
            waitIdle("genres")
            compare(journey.view.filters.platformId, "nes-famicom")
            compare(titles(), ["Action", "RPG", "Desconhecido"])
        }

        function test_empty_library_shows_zero_results() {
            if (harness.bridgeConfig.mode !== "empty")
                skip("modo diferente de empty")
            openPlatforms()
            keyClick(Qt.Key_Return)
            waitIdle("genres")
            compare(journey.items.length, 0)
            compare(journey.view.resultState, "zero-results")
            compare(journey.view.sourceState, "available")
            compare(byName(journey, "journeyEmptyTitle").text, "Nenhum resultado")
        }

        function test_unavailable_source_stays_distinct_from_empty() {
            if (harness.bridgeConfig.mode !== "unavailable")
                skip("modo diferente de unavailable")
            openPlatforms()
            keyClick(Qt.Key_Return)
            waitIdle("genres")
            compare(journey.items.length, 0)
            compare(journey.view.sourceState, "unavailable")
            compare(journey.view.resultState, "source-unavailable")
            compare(byName(journey, "journeyEmptyTitle").text, "Fonte indisponível")
        }
    }
}

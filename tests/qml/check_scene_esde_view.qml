// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// O renderizador do IR de cena. Os dois casos que importam aqui nasceram de
// defeitos medidos: cor com alfa lida ao contrário e elemento sem geometria
// desenhado no tamanho natural cobrindo a tela inteira.
import QtQuick
import QtTest
import "../../src/steamzero/ui/qml"

    Item {
    width: 1000
    height: 800
    property string lastActivated: ""
    property string lastItemFocused: ""
    property string lastItemActivated: ""

    SceneEsdeView {
        id: view
        anchors.fill: parent
        interactive: true
        runtimeModel: ({
            "items": [{"id": "1", "name": "Metroid", "coverUrl": "", "genre": "Ação"},
                      {"id": "2", "name": "Zelda", "coverUrl": "", "genre": "Aventura"}],
            "selectedIndex": 0,
            "selected": {"id": "1", "name": "Metroid", "genre": "Ação", "rating": "4.5"},
            "system": {"id": "nes", "name": "Nintendo Entertainment System"},
            "status": {"label": "Jogos inventariados"},
            "actions": ["Selecionar", "Detalhes", "Jogar"]
        })
        onElementActivated: lastActivated = elementId
        onItemFocused: lastItemFocused = itemId
        onItemActivated: lastItemActivated = itemId
        viewData: ({
            "id": "system",
            "elements": [
                {"id": "com-geometria", "kind": "image", "name": "fundo",
                 "layout": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.25},
                 "source": "qrc:/inexistente.png"},
                {"id": "sem-geometria", "kind": "image", "name": "solto",
                 "source": "qrc:/inexistente.png"},
                {"id": "texto", "kind": "text", "name": "titulo",
                 "layout": {"x": 0.1, "y": 0.6, "width": 0.3, "height": 0.05},
                 "text": "Olá", "interactive": true},
                {"id": "vinculo", "kind": "text", "name": "bind",
                 "layout": {"x": 0.1, "y": 0.7, "width": 0.3, "height": 0.05},
                 "binding": {"field": "title"}},
                {"id": "carrossel", "kind": "carousel", "name": "car",
                 "layout": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0,
                            "itemWidth": 0.1, "itemHeight": 0.15, "maxItemCount": 4}},
                {"id": "menu-only", "kind": "helpSystem", "name": "help-menu",
                 "layout": {"x": 0.5, "y": 0.98, "width": 0.3, "height": 0.04,
                            "scope": "menu"}},
                {"id": "medalhas", "kind": "badges", "name": "bg",
                 "layout": {"x": 0.5, "y": 0.5, "width": 0.2, "height": 0.1}},
                {"id": "escondido", "kind": "image", "name": "oculto",
                 "layout": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
                 "appearance": {"visible": false},
                 "source": "qrc:/inexistente.png"}
            ]
        })
    }

    TestCase {
        name: "SceneEsdeView"
        when: windowShown

        function test_decode_failure_is_not_a_rendered_element() {
            const previous = view.viewData
            view.viewData = {id: "invalid", elements: [
                {id: "missing", kind: "image", source: "qrc:/missing-owned-fixture.png",
                 layout: {width: 0.5, height: 0.2}},
                {id: "hidden", kind: "text", text: "Hidden", appearance: {opacity: 0},
                 layout: {width: 0.5, height: 0.2}}]}
            tryVerify(function() { return view.renderObservations.length === 2
                && view.renderObservations[0].state === "decodeFailed" })
            compare(view.renderedCount, 0)
            compare(view.renderObservations[1].state, "hidden")
            view.viewData = previous
        }

        function test_imported_timelines_are_explicitly_unavailable() {
            const previous = view.viewData
            view.viewData = {id: "motion", elements: [{id: "probe", kind: "text", text: "Probe",
                layout: {width: 0.5, height: 0.2},
                on: {highlightEnter: [{duration: 1, animations: [{property: "alpha", to: 0}]}]}}]}
            compare(view.unsupportedTimelines.length, 1)
            compare(view.unsupportedTimelines[0].id, "probe")
            compare(view.unsupportedTimelines[0].event, "highlightEnter")
            verify(view.unsupportedTimelines[0].reason.length > 0)
            view.viewData = previous
        }

        function test_imported_entry_timeline_plays_in_order_and_respects_reduced_motion() {
            const previous = view.viewData
            const animated = {
                id: "motion", elements: [{id: "probe", kind: "text", text: "Probe",
                    layout: {x: 0.1, width: 0.5, height: 0.2},
                    on: {enter: [
                        {duration: 0.4, animations: [
                            {property: "alpha", from: 0, to: 0.8, easing: "easeIn"},
                            {property: "x", to: 0.3}
                        ]},
                        {duration: 0.2, animations: [{property: "alpha", to: 0.6}]}
                    ]}}]
            }
            try {
                view.viewData = animated
                compare(view.unsupportedTimelines.length, 0)
                const node = view.elementAt(0).parent
                tryVerify(function() {
                    return node.opacity > 0 && node.opacity < 0.6
                        && node.x > view.width * 0.1 && node.x < view.width * 0.3
                }, 1000)
                tryCompare(node, "opacity", 0.6, 1500)
                compare(node.x, view.width * 0.3)
                view.visible = false
                view.visible = true
                compare(node.opacity, 0)
                view.reducedMotion = true
                compare(node.opacity, 0.6)
                compare(node.x, view.width * 0.3)
                view.reducedMotion = false
                compare(node.opacity, 0.6)
            } finally {
                view.viewData = previous
                view.visible = true
                view.reducedMotion = false
            }
        }

        function test_an_element_without_geometry_is_not_drawn() {
            // Desenhá-lo no tamanho natural em (0,0) inventaria layout e, na
            // medição real, cobria a cena inteira com uma arte esticada.
            const reasons = view.notDrawn.filter(function(e) { return e.id === "sem-geometria" })
            compare(reasons.length, 1)
            compare(reasons[0].reason, "sem geometria declarada")
        }

        function test_compiled_visual_kinds_have_a_renderer() {
            // Todos os tipos visuais compilados entram na superfície. `sound`
            // permanece não visual e continua sendo tratado como diagnóstico.
            const badges = view.notDrawn.filter(function(e) { return e.id === "medalhas" })
            compare(badges.length, 0)
        }

        function test_a_data_driven_kind_draws_its_structure() {
            // O conteúdo do carrossel vem do runtime, mas a MOLDURA e os
            // compartimentos são do tema, e o tema pediu que aparecessem.
            const carousel = view.notDrawn.filter(function(e) { return e.id === "carrossel" })
            compare(carousel.length, 0)
        }

        function test_a_menu_scoped_element_stays_out_of_the_base_view() {
            // `scope: menu` descreve o elemento COM UM MENU ABERTO. Desenhá-lo
            // na base empilhava um segundo helpsystem sobre o do tema, com
            // outra posição e outra cor, disputando o rodapé.
            const scoped = view.notDrawn.filter(function(e) { return e.id === "menu-only" })
            compare(scoped.length, 1)
            verify(scoped[0].reason.indexOf("escopo \'menu\'") === 0)
        }

        function test_an_element_the_theme_hides_is_not_counted_as_drawn() {
            // `visible: false` é escolha do tema. Contá-lo inflaria a fidelidade
            // com um elemento que o próprio tema manda esconder.
            const hidden = view.notDrawn.filter(function(e) { return e.id === "escondido" })
            compare(hidden.length, 1)
            compare(hidden[0].reason, "o tema declara invisivel")
        }

        function test_text_and_binding_both_count_as_drawable() {
            // 2 textos + o carrossel + badges. O oculto e a arte sem geometria
            // ficam de fora.
            compare(view.drawnCount, 5)
        }

        function test_a_binding_shows_the_field_instead_of_inventing_a_title() {
            // O campo agora vem do read model; sem ele a superfície usa o
            // fallback legível, nunca um placeholder de implementação.
            const bound = view.notDrawn.filter(function(e) { return e.id === "vinculo" })
            compare(bound.length, 0)
            compare(view.textFor({"binding": {"source": "metadata", "field": "name"}},
                                 view.selectedItem, ""), "Metroid")
        }

        function test_esde_colour_is_reordered_for_qml() {
            // ES-DE escreve RRGGBBAA; QML lê AARRGGBB. Sem reordenar, o alfa
            // vira vermelho e só um branco opaco sobreviveria por acaso.
            compare(view.esdeColor("ff000080", "#000000"), "#80ff0000")
            compare(view.esdeColor("ff0000", "#000000"), "#ff0000")
            compare(view.esdeColor("", "#123456"), "#123456")
            compare(view.esdeColor(undefined, "#123456"), "#123456")
        }

        function test_geometry_is_normalised_against_the_surface() {
            compare(view.width, 1000)
            compare(view.numberOr({"x": 0.5}, "x", 0), 0.5)
            compare(view.numberOr({}, "x", 0.25), 0.25)
            compare(view.numberOr(null, "x", 0.75), 0.75)
        }

        function test_interactive_scene_moves_focus_by_direction() {
            view.resetFocus()
            compare(view.currentFocusId, "texto")
            keyClick(Qt.Key_Up)
            compare(view.currentFocusId, "carrossel")
        }

        function test_interactive_scene_activates_the_focused_element() {
            view.resetFocus()
            keyClick(Qt.Key_Up)
            keyClick(Qt.Key_Return)
            compare(lastActivated, "carrossel")
            compare(lastItemActivated, "1")
        }

        function test_carousel_arrows_change_the_catalog_item_and_wrap() {
            view.resetFocus()
            keyClick(Qt.Key_Up)
            compare(view.selectedItem.id, "1")
            keyClick(Qt.Key_Right)
            compare(view.selectedItem.id, "2")
            compare(lastItemFocused, "2")
            keyClick(Qt.Key_Right)
            compare(view.selectedItem.id, "1")
            compare(lastItemFocused, "1")
        }
    }
}

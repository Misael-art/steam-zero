// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// Golden objetivo do D-10: com as seis ações de sessão visíveis, a linha de
// atalhos do rodapé precisa caber inteira — sem corte e sem elisão. A
// evidência da jornada física (capturas L22/L24, janela 1280x801 física com
// escala de interface 1.5 — o viewport lógico medido na captura é 853x534,
// onde "Pausar" nasce em ~94px lógicos e a linha de atalhos é cortada em
// "...· Açõe") mostrou o texto truncado quando Pausar/Retomar/Abrir saves/
// Salvar estado/Carregar estado/Sair do jogo aparecem. As asserções medem o
// nó da própria linha de atalhos: largura real >= largura implícita,
// elide == Text.ElideNone (elisão não é correção — esconde em vez de caber)
// e o extremo direito do texto dentro da janela. Não há inspeção subjetiva
// de captura aqui.
//
// A correção pertence ao RowLayout do rodapé em LauncherJourney.qml —
// superfície reservada à Tarefa 13. Este harness é o portão que avisa quando
// ela aterrissar (XPASS strict re-pina a régua).
import QtQuick
import QtQuick.Controls
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 853
    height: 534

    // O exato estado publicado pela ponte para uma sessão em execução sem
    // seleção: os seis eventos declarados no menu de jogos do documento.
    readonly property var sessionView: ({
        "active": true,
        "journeyId": "org.steamzero.footer-d10",
        "journeyName": "Rodapé D-10",
        "menuId": "games",
        "menuName": "Jogos",
        "entryMenuId": "games",
        "generation": 1,
        "selectedItemId": null,
        "filters": [],
        "scrollPosition": 0,
        "focusId": "item:emulation:celeste",
        "canGoBack": false,
        "sourceState": "available",
        "resultState": "available",
        "items": [{
            "id": "emulation:celeste",
            "gameId": "celeste",
            "title": "Celeste",
            "platform": "nes",
            "year": 2018,
            "genre": "Platformer"
        }],
        "totalCount": 1,
        "resultCount": 1,
        "availableEvents": [
            {"event": "select", "connectionId": "c1", "action": "navigate", "label": "Abrir jogos"},
            {"event": "back", "connectionId": "c2", "action": "back", "label": "Voltar"},
            {"event": "play", "connectionId": "c3", "action": "launch", "label": "Jogar"},
            {"event": "pause", "connectionId": "c4", "action": "pause", "label": "Pausar"},
            {"event": "resume", "connectionId": "c5", "action": "resume", "label": "Retomar"},
            {"event": "open-saves", "connectionId": "c6", "action": "open-saves", "label": "Abrir saves"},
            {"event": "save", "connectionId": "c7", "action": "save", "label": "Salvar estado"},
            {"event": "load", "connectionId": "c8", "action": "load", "label": "Carregar estado"},
            {"event": "exit", "connectionId": "c9", "action": "exit", "label": "Sair do jogo"}
        ],
        "sessionCapabilities": {
            "pause": {"available": true, "reason": ""},
            "resume": {"available": false, "reason": "A sessão precisa estar confirmada como pausada para retomar."},
            "open-saves": {"available": true, "reason": ""},
            "save": {"available": true, "reason": ""},
            "load": {"available": true, "reason": ""},
            "exit": {"available": true, "reason": ""}
        }
    })

    Item {
        id: stage
        anchors.fill: parent
        LauncherJourney {
            id: journey
            anchors.fill: parent
            view: harness.sessionView
        }
    }

    TestCase {
        name: "LauncherSessionFooterLayout"
        when: windowShown

        function test_shortcut_line_fits_when_session_actions_are_visible() {
            const pause = findChild(journey, "journeySessionEvent_pause")
            verify(pause !== null, "as ações de sessão precisam estar visíveis no golden")
            const row = pause.parent
            verify(row !== null, "o rodapé precisa agrupar a linha de atalhos e as ações")

            // A linha de atalhos é o único item do rodapé cujo texto descreve
            // a navegação; não tem objectName — é o próprio produto.
            let shortcut = null
            const children = row.children
            for (let i = 0; i < children.length; ++i) {
                const child = children[i]
                if (typeof child.text === "string"
                        && String(child.text).indexOf("navegar") >= 0) {
                    shortcut = child
                    break
                }
            }
            verify(shortcut !== null, "a linha de atalhos do rodapé precisa existir")

            // Elision nunca é uma correção para o D-10: o objetivo é CABER.
            verify(shortcut.elide === Text.ElideNone,
                   "a linha de atalhos não pode ser elidida para esconder o corte")
            // clip true apenas esconderia o problema; sem clip, o texto
            // transborda sobre os botões. O portão exige que caiba.
            verify(!shortcut.clip || shortcut.width >= shortcut.implicitWidth,
                   "com clip, a largura ainda precisa acomodar o texto inteiro")

            // Medida objetiva: o layout deu à linha de atalhos pelo menos a
            // largura que ela pede (a jornada física media o corte aqui).
            verify(shortcut.width + 0.5 >= shortcut.implicitWidth,
                    "D-10: a linha de atalhos fica cortada quando as ações de sessão aparecem ("
                    + "largura medida " + shortcut.width + " < implícita " + shortcut.implicitWidth + ")")

            // O texto inteiro precisa permanecer dentro da janela 1280x801.
            const origin = shortcut.mapToItem(harness, Qt.point(0, 0))
            verify(origin.x + shortcut.implicitWidth <= harness.width + 0.5,
                   "D-10: o fim da linha de atalhos ultrapassa a janela no viewport lógico 853x534")
        }
    }
}

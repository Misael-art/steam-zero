// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// D-12/D-22 na cena real: o rodapé de sessão do LauncherMain habilita
// Pausar/Salvar/Sair a partir da SESSÃO OBSERVADA, sem o botão "Atualizar".
// A ponte é a LauncherBridge real (mesmo processo do pytest, em loopback);
// o processo QML consome /model ao nascer — quando ainda não há sessão, o
// snapshot nasce com as capacidades indisponíveis, exatamente como na
// jornada física. O lançamento passa pelo mesmo POST /launch do shell, o
// polling de 400 ms observa a sessão em execução e é a transição de estado
// que devolve as capacidades ao rodapé. O harness nunca toca em
// "journeyRefresh"; o estado análogo à régua AT-SPI
// (docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/
// 17-arvore-atspi-central-pos-bateria.txt) é medido como
// ENABLED -> button.enabled === true e FOCUSABLE -> focusPolicy !== NoFocus.
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 801
    property var bridgeConfig: ({})
    property var launchBody: ""

    function readConfig() {
        const request = new XMLHttpRequest()
        request.open("GET", Qt.resolvedUrl(
            "../../../build/launcher-session-footer-e2e.json"), false)
        request.send()
        if (request.status !== 0 && request.status !== 200)
            throw new Error("configuração da bridge do rodapé não foi lida")
        return JSON.parse(request.responseText)
    }

    Component {
        id: sceneComponent
        LauncherMain {}
    }

    TestCase {
        name: "LauncherSessionFooter"
        when: windowShown

        function initTestCase() {
            harness.bridgeConfig = harness.readConfig()
        }

        function test_footer_uses_the_observed_session_not_the_refresh_button() {
            const scene = createTemporaryObject(sceneComponent, harness)
            verify(scene !== null, "a cena raiz do Launcher precisa instanciar")
            scene.api = harness.bridgeConfig.apiUrl
            scene.token = harness.bridgeConfig.apiToken
            scene._start()
            tryCompare(scene, "loadState", "ready", 5000)

            const journey = findChild(scene.contentItem, "launcherJourney")
            verify(journey !== null, "a superfície da Jornada precisa carregar")
            const pause = findChild(journey, "journeySessionEvent_pause")
            const save = findChild(journey, "journeySessionEvent_save")
            const exit = findChild(journey, "journeySessionEvent_exit")
            const resume = findChild(journey, "journeySessionEvent_resume")
            verify(pause !== null && save !== null && exit !== null && resume !== null,
                   "as ações de sessão nascem visíveis no rodapé")

            // Snapshot do processo: nenhuma sessão observada ainda — o estado
            // que a jornada física registrou como ponto de partida do D-12.
            tryVerify(function() { return journey.view !== null }, 5000)
            compare(journey.view.selectedItemId, null,
                    "D-22: o cenário exige seleção nula com sessão em curso")
            compare(pause.enabled, false)
            compare(String(pause.Accessible.description).indexOf("Selecione"), 0,
                    "antes da sessão o motivo publicado é a ausência de sessão observável")

            // O lançamento usa o mesmo canal do shell: POST /launch na bridge.
            let launchStatus = 0
            scene._request("POST", "/launch",
                           {"gameId": "celeste", "focusId": "library:celeste"},
                           function(status, text) {
                launchStatus = status
                harness.launchBody = text
            })
            tryCompare(scene, "loadState", "ready", 5000)
            tryVerify(function() { return launchStatus === 200 }, 5000,
                      "o lançamento pela bridge real falhou (status=" + launchStatus + ")")

            // O shell entra no estado pós-emulador: é ele que liga o polling
            // de 400 ms que observa a sessão canônica em execução.
            const shell = scene._activeLauncherShell()
            verify(shell !== null, "o shell precisa estar carregado")
            shell.sessionGameId = "celeste"
            shell.launchState = "emulator-visible"

            // D-12: sem nenhum toque em "Atualizar", a transição observada
            // devolve ENABLED|FOCUSABLE a Pausar/Salvar/Sair.
            tryVerify(function() {
                return pause.enabled === true && save.enabled === true
                    && exit.enabled === true
            }, 8000, "o rodapé não habilitou Pausar/Salvar/Sair a partir da sessão observada")
            compare(pause.focusPolicy !== Qt.NoFocus, true, "Pausar precisa nascer FOCUSABLE")
            compare(save.focusPolicy !== Qt.NoFocus, true, "Salvar precisa nascer FOCUSABLE")
            compare(exit.focusPolicy !== Qt.NoFocus, true, "Sair precisa nascer FOCUSABLE")
            compare(journey.busy, false)
            compare(resume.enabled, false, " sessão em execução não oferece Retomar")
            compare(String(pause.Accessible.description), "",
                    "D-22: o rodapé não pode culpar a seleção ausente com sessão observada")
        }
    }
}

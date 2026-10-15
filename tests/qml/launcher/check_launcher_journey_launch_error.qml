// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 SteamZero contributors
//
// D-08 na cena real: o 409 estruturado do lançamento precisa aparecer na
// sobreposição de jornada com code, motivo e a única ação que resolve.
// Reprodução do registro físico (docs/09-operations/evidence/
// 2026-10-12-jornada-fisica-2b7eb541b4a5/logs/12-defeitos-registrados.txt):
// P na Jornada produz o intent de lançamento, a ponte responde o POST /launch
// com o 409 estruturado da D-17 — e a overlay voltava ao estado normal, com o
// erro vivendo só na API. A ponte é a LauncherBridge real em loopback; o
// caminho exercitado é exatamente o de produção: playCurrent() →
// /journey/event → launchRequested → /launch → 409 → restauração da overlay.
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 801
    property var bridgeConfig: ({})
    readonly property string privateDetail: "recusa privada /caminho-local/celeste.rom"

    function readConfig() {
        const request = new XMLHttpRequest()
        request.open("GET", Qt.resolvedUrl(
            "../../../build/launcher-journey-launch-error-d08.json"), false)
        request.send()
        if (request.status !== 0 && request.status !== 200)
            throw new Error("configuração da bridge do D-08 não foi lida")
        return JSON.parse(request.responseText)
    }

    Component {
        id: sceneComponent
        LauncherMain {}
    }

    TestCase {
        name: "LauncherJourneyLaunchError"
        when: windowShown

        function initTestCase() {
            harness.bridgeConfig = harness.readConfig()
        }

        function test_structured_409_surfaces_on_the_journey_overlay() {
            const scene = createTemporaryObject(sceneComponent, harness)
            verify(scene !== null, "a cena raiz do Launcher precisa instanciar")
            scene.api = harness.bridgeConfig.apiUrl
            scene.token = harness.bridgeConfig.apiToken
            scene._start()
            tryCompare(scene, "loadState", "ready", 5000)

            const journey = findChild(scene.contentItem, "launcherJourney")
            verify(journey !== null, "a superfície da Jornada precisa carregar")
            tryVerify(function() {
                return journey.view !== null && journey.supportsEvent("play")
            }, 5000, "a Jornada precisa nascer ativa no menu com evento Jogar")
            tryVerify(function() { return journey.busy === false }, 5000)
            verify(journey.activeItem !== null
                       && String(journey.activeItem.gameId) === "celeste",
                   "o item ativo precisa ser o jogo lançável da ponte")

            // Caminho de produção: P na overlay dispara o intent e o
            // lançamento passam pelos mesmos pedidos do shell.
            verify(journey.playCurrent() === true,
                   "playCurrent precisa aceitar o evento play na Jornada ativa")
            const shell = scene._activeLauncherShell()
            verify(shell !== null, "o shell precisa estar carregado para o lançamento")

            // D-08: o 409 estruturado (code + motivo + impacto + única ação)
            // tem de chegar à sobreposição — hoje ela volta ao estado normal.
            tryVerify(function() {
                return String(journey.message).indexOf("LAUNCHER-LAUNCH-FAILED-001") === 0
            }, 8000, "D-08: o code do 409 não chegou à sobreposição de jornada")
            verify(journey.messageIsError === true,
                   "o erro de lançamento precisa nascer como erro, não estado neutro")
            verify(String(journey.message).indexOf("Não foi possível preparar o lançamento.") >= 0,
                   "D-08: o motivo publicado pela ponte precisa aparecer na overlay")
            verify(String(journey.message).indexOf("O Launcher não confirmou o início do jogo.") >= 0,
                   "D-08: o impacto publicado precisa aparecer na overlay")
            verify(String(journey.message).indexOf("Consulte o diagnóstico") >= 0,
                   "D-08: a única ação que resolve (nextAction) precisa aparecer na overlay")

            // A overlay volta visível e o estado da janela é o erro — não o
            // estado normal de sempre que a evidência física registrou.
            verify(scene.journeyOverlayVisible === true,
                   "a jornada precisa voltar visível após a recusa")
            const status = findChild(journey, "journeyStatus")
            verify(status !== null && status.visible === true,
                   "a linha de estado da Jornada precisa publicar o erro")
            compare(shell.launchState, "failed")

            // D-17 vale também aqui: o texto privado da exceção jamais pode
            // vazar para a superfície.
            verify(String(journey.message).indexOf(harness.privateDetail) === -1,
                   "D-08 vaza o texto privado da exceção para a overlay")
        }
    }
}

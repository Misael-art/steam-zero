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
// Fix round 1: a cena também prova o ciclo de vida do 409 pendente — ele é
// publicado uma única vez por um refresh limpo e é descartado por refreshs
// que não o consomem (não-200 ou applyView recusado), sem ressurgir depois.
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

        // Monta a cena real sobre a ponte em loopback até a Jornada ativa,
        // lançável e ociosa — pré-requisito compartilhado pelas três provas.
        function mountReadyJourney() {
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
            return {"scene": scene, "journey": journey}
        }

        // Entrega a recusa real pelo caminho de produção: playCurrent →
        // POST /journey/event → launchRequested → POST /launch → 409 →
        // restauração da sobreposição, que publica o erro na overlay.
        function refuseLaunch(journey) {
            verify(journey.playCurrent() === true,
                   "playCurrent precisa aceitar o evento play na Jornada ativa")
            tryVerify(function() {
                return String(journey.message).indexOf("LAUNCHER-LAUNCH-FAILED-001") === 0
            }, 8000, "D-08: o code do 409 não chegou à sobreposição de jornada")
            tryVerify(function() { return journey.busy === false }, 5000)
        }

        function test_structured_409_surfaces_on_the_journey_overlay() {
            const ready = mountReadyJourney()
            const scene = ready.scene
            const journey = ready.journey

            // Caminho de produção: P na overlay dispara o intent e o
            // lançamento passam pelos mesmos pedidos do shell.
            refuseLaunch(journey)
            const shell = scene._activeLauncherShell()
            verify(shell !== null, "o shell precisa estar carregado para o lançamento")

            // D-08: o 409 estruturado (code + motivo + impacto + única ação)
            // tem de chegar à sobreposição — hoje ela volta ao estado normal.
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

            // Fix round 1 (D-08): a publicação é de uma vez só. O refresh de
            // restauração da sobreposição já publicou o 409 pendente; o
            // próximo refresh limpo tem de voltar ao estado normal em vez de
            // reexibir o erro de uma recusa passada.
            verify(journey.pendingLaunchError === "",
                   "o refresh limpo da restauração precisa consumir o 409 pendente")
            verify(journey.refresh() === true,
                   "o refresh limpo subsequente precisa usar a ponte real")
            tryCompare(journey, "busy", false, 5000)
            verify(String(journey.message).indexOf("LAUNCHER-LAUNCH-FAILED-001") === -1,
                   "D-08: o 409 publicado uma vez não pode ser reexibido por outro refresh limpo")
            verify(journey.messageIsError === false,
                   "D-08: após a publicação única a overlay volta ao estado normal")
            // Drena o ciclo de cinema religado pela mudança de view: a cena
            // efêmera morre no fim do teste e uma resposta órfã atingiria um
            // watchdog já destruído (QWARN na saída do gate).
            wait(150)
        }

        // Fix round 1 (D-08): se o refresh que sucede a recusa NÃO consumiu o
        // 409 pendente (aqui: respondeu não-200 e sobrescreveu `message`), o
        // pendente precisa ser descartado — sobreviver faria o erro ressurgir
        // numa janela posterior sem recusa recente.
        function test_pending_launch_error_does_not_resurface_after_a_failed_refresh() {
            const ready = mountReadyJourney()
            const journey = ready.journey
            refuseLaunch(journey)

            const detail = String(journey.message)
            const realRequest = journey.requestFunction
            // O shell entrega a recusa exatamente por este contrato
            // (LauncherMain.restoreJourneyAfterLaunch → showLaunchError):
            // `message` imediato e `pendingLaunchError` à espera do refresh.
            journey.showLaunchError(detail)
            verify(journey.pendingLaunchError === detail,
                   "showLaunchError precisa deixar o 409 pendente para o refresh")
            journey.requestFunction = function(method, path, body, onDone) {
                onDone(503, "")
                return true
            }
            verify(journey.refresh() === true,
                   "o refresh não-200 precisa ser aceito pela Jornada")
            verify(String(journey.message).indexOf("JOURNEY-LAUNCHER-OFFLINE-001") === 0,
                   "o refresh não-200 precisa publicar o estado offline na mensagem")
            verify(journey.messageIsError === true,
                   "o estado offline precisa nascer como erro")
            verify(journey.pendingLaunchError === "",
                   "D-08: um refresh não-200 que sobrescreveu a mensagem não pode manter o 409 pendente")

            journey.requestFunction = realRequest
            verify(journey.refresh() === true,
                   "o refresh limpo subsequente precisa usar a ponte real")
            tryCompare(journey, "busy", false, 5000)
            verify(String(journey.message).indexOf("LAUNCHER-LAUNCH-FAILED-001") === -1,
                   "D-08: o 409 pendente não pode ressurgir depois de um refresh não-200")
            verify(journey.messageIsError === false,
                   "D-08: o refresh limpo posterior publica o estado normal")
            wait(150)
        }

        // Fix round 1 (D-08): o mesmo vale quando o refresh responde 200 mas
        // `applyView` falha (sem Jornada ativa) — a mensagem é sobrescrita e
        // o pendente precisa morrer junto.
        function test_pending_launch_error_is_cleared_when_apply_view_fails() {
            const ready = mountReadyJourney()
            const journey = ready.journey
            refuseLaunch(journey)

            const detail = String(journey.message)
            const realRequest = journey.requestFunction
            journey.showLaunchError(detail)
            verify(journey.pendingLaunchError === detail,
                   "showLaunchError precisa deixar o 409 pendente para o refresh")
            journey.requestFunction = function(method, path, body, onDone) {
                onDone(200, JSON.stringify({"active": false}))
                return true
            }
            verify(journey.refresh() === true,
                   "o refresh com applyView recusado precisa ser aceito pela Jornada")
            verify(String(journey.message).indexOf("Nenhuma Jornada ativa") >= 0,
                   "a falha de applyView precisa publicar sua própria mensagem")
            verify(journey.pendingLaunchError === "",
                   "D-08: um refresh cujo applyView falhou não pode manter o 409 pendente")

            journey.requestFunction = realRequest
            verify(journey.refresh() === true,
                   "o refresh limpo subsequente precisa usar a ponte real")
            tryCompare(journey, "busy", false, 5000)
            verify(String(journey.message).indexOf("LAUNCHER-LAUNCH-FAILED-001") === -1,
                   "D-08: o 409 pendente não pode ressurgir depois de uma falha de applyView")
            verify(journey.messageIsError === false,
                   "D-08: o refresh limpo posterior publica o estado normal")
            wait(150)
        }
    }
}

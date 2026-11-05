// SPDX-License-Identifier: GPL-3.0-or-later
//
// V2 — a cena resolvida pela bridge REAL é desenhada pelo SceneEsdeView e a
// imagem é de fato decodificada: o teste lê pixels do quadro renderizado, não só
// a URI. Dois consumidores de origem: tema ES-DE instalado (`theme.scene.render`)
// e cena RetroFE importada (`theme.scene.render-imported`), ambos com dados
// sintéticos isolados. URL e token são efêmeros (build/).
import QtQuick
import QtTest
import "../../src/steamzero/ui/qml"
import "../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 800
    height: 600

    SceneEsdeView {
        id: view
        anchors.fill: parent
        viewData: ({"id": "vazia", "elements": []})
        runtimeModel: ({})
    }

    Component {
        id: editorComponent
        ThemeEditorPanel {
            anchors.fill: parent
            requestAction: function(actionId, payload, callback, errorCallback) {
                if (actionId !== "theme.scene.render-imported")
                    return false
                const response = suite.post(suite.readConfig(), "/theme/scene/render-imported", payload)
                if (response.status === 200)
                    callback(response.body)
                else
                    errorCallback(response.body.error)
                return true
            }
        }
    }

    Component {
        id: journeyComponent
        ExperienceJourneyPanel {
            anchors.fill: parent
            compactLayout: true
            requestAction: function(actionId, payload, callback, errorCallback) {
                const operation = actionId.replace("journey.studio.", "")
                const method = ["list", "catalog"].includes(operation) ? "GET" : "POST"
                const response = suite.request(suite.readConfig(), method,
                    "/journey/studio/" + operation, payload)
                if (response.status === 200)
                    callback(response.body)
                else
                    errorCallback(response.body.error)
                return true
            }
        }
    }

    Component {
        id: cinemaComponent
        LauncherCinema { anchors.fill: parent }
    }

    TestCase {
        id: suite
        name: "ThemeSceneRuntimeE2E"
        when: windowShown

        function readConfig() {
            const r = new XMLHttpRequest()
            r.open("GET", "FIXTURE_CONFIG", false)
            r.send()
            return JSON.parse(r.responseText)
        }

        function post(cfg, path, payload) {
            return request(cfg, "POST", path, payload)
        }

        function request(cfg, method, path, payload) {
            const r = new XMLHttpRequest()
            r.open(method, cfg.apiUrl + path, false)
            r.setRequestHeader("X-SteamZero-Token", cfg.apiToken)
            r.setRequestHeader("Content-Type", "application/json")
            r.send(method === "POST" ? JSON.stringify(payload) : null)
            return {status: r.status, body: JSON.parse(r.responseText || "{}")}
        }

        function find(root, name) {
            if (!root)
                return null
            if (root.objectName === name)
                return root
            const kids = root.childItems !== undefined ? root.childItems : root.children
            for (let i = 0; kids && i < kids.length; i++) {
                const hit = find(kids[i], name)
                if (hit)
                    return hit
            }
            return null
        }

        // O Image fica dentro do Loader do SceneEsdeView, sem objectName: acha-se pela
        // URL de origem que a cena resolvida declarou (blob endereçado por hash).
        function imageFor(root, fileName) {
            if (!root)
                return null
            if (root.status !== undefined && root.fillMode !== undefined && root.source !== undefined
                    && String(root.source) === fileName)
                return root
            const kids = root.childItems !== undefined ? root.childItems : root.children
            for (let i = 0; kids && i < kids.length; i++) {
                const hit = imageFor(kids[i], fileName)
                if (hit)
                    return hit
            }
            return null
        }

        function show(rendered) {
            view.runtimeModel = rendered.runtimeModel
            view.viewData = rendered.scene.views[0]
        }

        // O gradiente do fixture muda da esquerda para a direita; uma imagem não
        // decodificada (ou um placeholder) não tem essa variação de pixel.
        function assertGradient(imageItem, firstDominant, lastDominant, captureItem) {
            tryCompare(imageItem, "status", Image.Ready, 5000, imageItem.objectName + " não decodificou")
            verify(imageItem.sourceSize.width > 0 && imageItem.sourceSize.height > 0)
            wait(100)
            const target = captureItem || imageItem
            const origin = imageItem.mapToItem(target, 0, 0)
            const grabbed = grabImage(target)
            verify(grabbed !== null && grabbed.width > 8, "captura vazia")
            const inset = Math.min(8, Math.floor(imageItem.width / 8))
            const centerY = Math.floor(origin.y + imageItem.height / 2)
            const left = grabbed.pixel(Math.floor(origin.x) + inset, centerY)
            const right = grabbed.pixel(Math.floor(origin.x + imageItem.width) - 1 - inset, centerY)
            const channel = function(c, i) { return 255 * [c.r, c.g, c.b][i] }
            verify(channel(left, firstDominant) > channel(left, lastDominant) + 40,
                   "lado esquerdo sem a cor esperada: " + left + " · " + grabbed.width + "×" + grabbed.height)
            verify(channel(right, lastDominant) > channel(right, firstDominant) + 40,
                   "lado direito sem a cor esperada")
        }

        function test_01_esde_instalado_desenha_pixels_do_asset() {
            const cfg = readConfig()
            const response = post(cfg, "/theme/scene/render",
                {themeId: cfg.esdeId, aspectRatio: "16:10", synthetic: true})
            compare(response.status, 200)
            show(response.body)
            const declared = response.body.scene.views[0].elements.filter(
                function(e) { return e.name === "fundo" })[0].source
            tryVerify(function() { return imageFor(view, declared) !== null }, 5000,
                      "a imagem 'fundo' não foi instanciada pelo SceneEsdeView")
            const fundo = imageFor(view, declared)
            assertGradient(fundo, 0, 2)  // vermelho → azul
            compare(response.body.runtimeModel.isolated, true)
            // asset ausente: diagnóstico no resultado, sem trocar por outra cena
            verify(JSON.stringify(response.body.assets).indexOf("nao-existe.png") >= 0)
        }

        function test_02_retrofe_importado_desenha_pixels_do_asset() {
            const cfg = readConfig()
            const response = post(cfg, "/theme/scene/render-imported", {sceneId: cfg.retrofeId})
            compare(response.status, 200)
            compare(response.body.origin, "retrofe")
            show(response.body)
            const declared = response.body.scene.views[0].elements.filter(
                function(e) { return e.source })[0].source
            tryVerify(function() { return imageFor(view, declared) !== null }, 5000,
                      "o logo RetroFE não foi instanciado pelo SceneEsdeView")
            const logo = imageFor(view, declared)
            const node = view.elementAt(0).parent
            tryCompare(node, "opacity", 0.85, 1500)
            compare(node.x, view.width * 0.25)
            compare(node.y, view.height * 0.25)
            assertGradient(logo, 1, 0, view)  // verde → magenta
            compare(view.unsupportedTimelines.length, 1)
            compare(view.unsupportedTimelines[0].event, "exit")
        }

        function test_03_studio_reabre_e_reproduz_cena_salva() {
            const cfg = readConfig()
            const editor = createTemporaryObject(editorComponent, harness)
            verify(editor)
            editor.retrofeImportDialogControl.open()
            tryCompare(editor.retrofeImportDialogControl, "opened", true)
            editor.retrofeImportSceneId = cfg.retrofeId
            const play = find(editor.retrofeImportDialogControl.contentItem.parent, "themeImportRetrofePlay")
            verify(play && play.enabled)
            mouseClick(play)
            const dialog = findChild(editor, "themeRetrofePlaybackDialog")
            verify(dialog)
            tryCompare(dialog, "opened", true)
            const preview = dialog.contentItem
            compare(preview.rendered.themeId, cfg.retrofeId)
            compare(preview.rendered.runtimeModel.isolated, true)
            const scene = find(preview, "sceneView")
            tryVerify(function() { return scene.elementAt(0) !== null })
            tryCompare(scene.elementAt(0).parent, "opacity", 0.85, 1500)
            verify(find(preview, "notDrawnLine").text.indexOf("1") !== -1)
            dialog.close()
            tryCompare(dialog, "opened", false)
            editor.retrofeImportSceneId = "../missing"
            mouseClick(play)
            tryCompare(dialog, "opened", true)
            compare(preview.rendered, null)
            verify(preview.errorText.length > 0)
            dialog.close()
            tryCompare(dialog, "opened", false)
            editor.retrofeImportDialogControl.close()
        }

        function test_04_jornada_salva_e_previsualiza_cena_retrofe() {
            const cfg = readConfig()
            const journey = createTemporaryObject(journeyComponent, harness)
            verify(journey)
            journey.refresh()
            compare(journey.catalog.importedScenes.length, 1)
            compare(journey.catalog.importedScenes[0].id, cfg.retrofeId)
            journey.createJourney("")
            tryVerify(function() { return journey.session && !journey.busy })
            journey.compactPane = "inspector"
            const button = find(journey, "journeyApplyImportedScene")
            const picker = find(journey, "journeyImportedScenePicker")
            tryVerify(function() { return button && button.visible && button.enabled })
            compare(picker.currentValue, cfg.retrofeId)
            const inspector = find(journey, "journeyInspectorScroll").contentItem
            tryVerify(function() {
                const point = button.mapToItem(inspector, 0, 0)
                if (button.height <= 0 || inspector.height <= 0)
                    return false
                if (point.y >= 0 && point.y + button.height <= inspector.height)
                    return true
                inspector.contentY = Math.max(0, inspector.contentY + point.y - 8)
                return false
            }, 3000, "ação fora da área visível do inspetor")
            mouseClick(button)
            tryVerify(function() {
                return journey.currentMenu.appearance
                    && journey.currentMenu.appearance.mode === "imported-scene"
            }, 3000, "não atribuiu a cena: " + journey.notice)
            compare(journey.currentMenu.appearance.sceneId, cfg.retrofeId)
            journey.preview()
            tryCompare(journey, "themePreviewMode", "imported")
            const preview = find(journey, "journeyImportedScenePreview")
            verify(preview.visible)
            const title = find(journey, "journeyScenePreviewTitle")
            verify(title.text.indexOf(cfg.retrofeId) !== -1)
            tryVerify(function() {
                const point = preview.mapToItem(inspector, 0, 0)
                if (point.y >= 0 && point.y + preview.height <= inspector.height)
                    return true
                inspector.contentY = Math.max(0, Math.min(inspector.contentHeight - inspector.height,
                    inspector.contentY + point.y - title.height - 8))
                return false
            }, 3000, "prévia não está visível na área do inspetor")
            const scene = find(preview, "sceneView")
            tryVerify(function() { return scene.elementAt(0) !== null })
            tryCompare(scene.elementAt(0).parent, "opacity", 0.85, 1500)
            journey.saveJourney()
            tryVerify(function() { return journey.session.isNew === false && !journey.busy })
            const id = journey.journeyDocument.id
            journey.loadJourney(id)
            compare(journey.currentMenu.appearance.sceneId, cfg.retrofeId)
            verify(journey.activateJourney())
            tryCompare(journey, "activeJourneyId", id)
        }

        function test_05_launcher_reproduz_a_mesma_cena() {
            const cfg = readConfig()
            const cinema = createTemporaryObject(cinemaComponent, harness)
            verify(cinema)
            cinema.currentFocus = cfg.launcher.focusId
            cinema.scene = cfg.launcher
            const scene = find(cinema, "launcherCinemaXmlScene")
            verify(scene && scene.visible)
            const node = scene.elementAt(0).parent
            tryVerify(function() { return node.opacity > 0 && node.opacity < 0.85 }, 1000)
            tryCompare(node, "opacity", 0.85, 1500)
            compare(node.x, scene.width * 0.25)
            compare(node.y, scene.height * 0.25)
            const loss = find(cinema, "importedSceneLossBanner")
            const text = find(cinema, "importedSceneLossText")
            const footer = find(cinema, "cinemaFooter")
            verify(loss.visible)
            compare(String(text.color), "#ffffff")
            verify(loss.y + loss.height < footer.y)
            assertGradient(imageFor(scene, scene.elements[0].source), 1, 0, scene)
        }

        function test_06_launcher_preserva_a_navegacao_sem_cena() {
            const cfg = readConfig()
            const cinema = createTemporaryObject(cinemaComponent, harness)
            verify(cinema)
            cinema.currentFocus = cfg.launcher.focusId
            cinema.scene = cfg.launcher
            compare(cinema.selectionReady, true)
            compare(cinema.externalSceneAvailable, false)
            const notice = find(cinema, "launcherExternalSceneDiagnostic")
            verify(notice && notice.visible)
            compare(String(notice.color), "#ffffff")
            verify(notice.text.indexOf(cfg.launcher.theme.requestedSceneId) !== -1)
        }
    }
}

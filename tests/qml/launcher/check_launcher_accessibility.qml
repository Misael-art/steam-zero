// SPDX-License-Identifier: GPL-3.0-or-later
//
// Acessibilidade herdada no Launcher: quando o host reporta alto contraste, a
// home e a página de jogo trocam as cores fixas pelos valores high-contrast da
// central (UiTokens) — sem refatorar para tokens, para não arriscar o layout.
// Se o QML ignorar `accessibility.highContrast`, o usuário que configurou alto
// contraste no Plasma continuaria vendo o tema escuro padrão.
import QtQuick
import "../../../src/steamzero/ui/qml/launcher"

Item {
    id: harness
    width: 1280
    height: 800

    property int failures: 0
    property int checkIndex: 0
    function check(condition, message) {
        checkIndex += 1
        if (!condition) {
            failures += 1
            console.error("FAIL #" + checkIndex + ": " + message)
        }
    }

    readonly property var sections: [
        {"id": "library", "title": "Biblioteca",
         "items": [{"id": "celeste", "title": "Celeste"}]}
    ]
    readonly property var focusMap: ({
        "initial": "header:home",
        "rows": ["header:home", "library:celeste"],
        "diagnostics": [],
        "nodes": {
            "header:home": {"id": "header:home", "section": "header", "column": 0,
                            "up": null, "down": "library:celeste", "left": null,
                            "right": null, "action": null},
            "library:celeste": {"id": "library:celeste", "section": "library", "column": 0,
                                "up": "header:home", "down": null, "left": null,
                                "right": null, "action": null}
        }
    })

    LauncherHome {
        id: home
        anchors.fill: parent
        focusMap: harness.focusMap
        sections: harness.sections
    }

    // D-19: dois controles chamados "Jogar" na mesma janela são armadilha de
    // foco — a árvore AT-SPI não distingue qual ativa o quê. Os nomes
    // acessíveis de ativação das duas superfícies reais da janela (página de
    // jornada e página de jogo) precisam ser distinguíveis e únicos por janela.
    // A prova usa as superfícies do produto, não réplicas de string.
    readonly property var journeyView: ({
        "active": true, "journeyId": "d19-prova", "menuId": "games",
        "menuName": "Jogos", "generation": 0, "resultCount": 1, "totalCount": 1,
        "items": [{"id": "emulation:celeste", "gameId": "celeste", "title": "Celeste"}],
        "availableEvents": [{"event": "play", "connectionId": "games-play",
                             "action": "launch", "label": "Jogar"}],
        "facets": [], "sessionCapabilities": ({}), "canGoBack": false
    })

    readonly property var mainModel: ({
        "focusMap": harness.focusMap,
        "sections": harness.sections,
        "catalogSummary": {},
        // Sem esta chave o Loader da jornada avalia `undefined` para a
        // propriedade bool `active` e o driver reprova o harness pelo
        // diagnóstico "Unable to assign". A cena D-19 não usa a jornada
        // embutida: a sonda de jornada é o LauncherJourney montado acima.
        "journey": {"active": false},
        "returnContext": null
    })

    LauncherJourney {
        id: journeyProbe
        objectName: "d19JourneyProbe"
        visible: false
        anchors.fill: parent
        view: harness.journeyView
    }

    Component {
        id: mainSceneComponent
        LauncherMain {}
    }

    function highContrastPayload() {
        return ({"highContrast": true, "visualScale": 1.0, "reducedMotion": false})
    }

    function findByObjectName(node, name) {
        if (node === null || node === undefined)
            return null
        if (node.objectName === name)
            return node
        for (var i = 0; i < node.children.length; ++i) {
            var found = findByObjectName(node.children[i], name)
            if (found !== null)
                return found
        }
        return null
    }

    Timer {
        interval: 80
        running: true
        onTriggered: {
            // Sem alto contraste: `_hc` devolve o valor original (tema atual).
            harness.check(home._hc("#f2f6fb", "#ffffff") === "#f2f6fb",
                          "sem highContrast texto claro permanece o original")
            harness.check(home._hc("#22d3ee", "#55d8ff") === "#22d3ee",
                          "sem highContrast o acento é o original")

            // Aplicar highContrast e reler: agora devolve a variante acessível.
            home.accessibility = harness.highContrastPayload()
            harness.check(home._hc("#f2f6fb", "#ffffff") === "#ffffff",
                          "home._hc deve trocar texto claro por branco em highContrast")
            harness.check(home._hc("#8b93a8", "#c6d0db") === "#c6d0db",
                          "home._hc deve trocar muted por muted-highContrast")
            harness.check(home._hc("#0b1622", "#03080c") === "#03080c",
                          "home._hc deve trocar fundo escuro por quase-preto")
            harness.check(home._hc("#22d3ee", "#55d8ff") === "#55d8ff",
                          "com highContrast o acento vira a variante clara")

            // Ler a cor real do cabeçalho (deve refletir o alto contraste).
            var header = findByObjectName(home, "launcherHeader")
            harness.check(header !== null, "o cabeçalho da home precisa existir para a leitura")
            if (header !== null) {
                harness.check(header.color.toString() === "#55d8ff",
                              "cabeçalho focado em highContrast deve ser #55d8ff, é " + header.color)
            }

            // Desligar de volta: a home volta ao tema original.
            home.accessibility = ({"highContrast": false, "visualScale": 1.0, "reducedMotion": false})
            harness.check(home._hc("#8b93a8", "#c6d0db") === "#8b93a8",
                          "desligar highContrast restaura a cor muted original")

            // D-19: unicidade por janela sobre as duas superfícies de ativação.
            var journeyPlay = harness.findByObjectName(journeyProbe, "journeyPlay")
            harness.check(journeyPlay !== null,
                          "a página de jornada precisa publicar seu controle de jogar")
            var journeyName = journeyPlay === null ? "" : String(journeyPlay.Accessible.name)

            var gameName = ""
            var scene = mainSceneComponent.createObject(harness)
            harness.check(scene !== null,
                          "a cena do Launcher precisa instanciar para a prova D-19")
            if (scene !== null) {
                scene.model = harness.mainModel
                var page = scene._resolveGamePage("celeste")
                harness.check(page !== null && page.actions.length === 1,
                              "a página de jogo precisa publicar a ação de lançar")
                if (page !== null && page.actions.length === 1)
                    gameName = String(page.actions[0].label)
                scene.destroy()
            }

            harness.check(journeyName === "Continuar jornada",
                          "D-19: a jornada nomeia a ação pelo fluxo; obteve \"" + journeyName + "\"")
            harness.check(gameName === "Jogar Celeste",
                          "D-19: a página de jogo nomeia a ação com o título; obteve \"" + gameName + "\"")

            var names = [journeyName, gameName]
            for (var n = 0; n < names.length; ++n) {
                harness.check(names[n] !== "",
                              "D-19: nome acessível vazio é armadilha de foco")
                for (var m = n + 1; m < names.length; ++m)
                    harness.check(names[n] !== names[m],
                                  "D-19: dois controles ativáveis compartilham \"" + names[n]
                                  + "\" na mesma janela")
            }
            harness.check(names.indexOf("Jogar") === -1,
                          "D-19: o nome ambíguo \"Jogar\" puro não pode permanecer na janela")

            console.log("check_launcher_accessibility: " + harness.checkIndex
                        + " verificações, " + harness.failures + " falhas")
            Qt.exit(harness.failures === 0 ? 0 : 1)
        }
    }
}

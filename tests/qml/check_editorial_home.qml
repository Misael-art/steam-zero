// SPDX-License-Identifier: GPL-3.0-or-later
// Fixture visual/dev: os dados abaixo não são apresentados pelo produto.
import QtQuick
import QtQuick.Window
import "../../src/steamzero/ui/qml"

Window {
    id: harness
    visible: true
    width: optionNumber("--capture-width=", 1280)
    height: optionNumber("--capture-height=", 800)
    property int failures: 0
    property int phase: 0
    readonly property string captureOutput: {
        const args = Qt.application.arguments
        for (let i = 0; i < args.length; ++i) {
            if (args[i].startsWith("--capture-output="))
                return args[i].slice("--capture-output=".length)
        }
        return ""
    }
    property string requestedSystem: ""
    property string requestedCollection: ""
    property bool continueWasRequested: false
    property string requestedMaintenance: ""

    function optionNumber(prefix, fallback) {
        const args = Qt.application.arguments
        for (let i = 0; i < args.length; ++i) {
            if (args[i].startsWith(prefix)) {
                const parsed = Number(args[i].slice(prefix.length))
                if (Number.isFinite(parsed) && parsed > 0)
                    return Math.floor(parsed)
            }
        }
        return fallback
    }

    function check(condition, message) {
        if (!condition) {
            failures += 1
            console.error("FAIL: " + message)
        }
    }

    EditorialHome {
        id: home
        anchors.fill: parent
        steamGames: [
            {"id": "10", "name": "Fixture Steam", "coverUrl": "", "state": "installed"},
            {"id": "20", "name": "Fixture Steam Two", "coverUrl": "", "state": "installed"}
        ]
        emulation: ({
            "editorialPlatforms": [
                {"id": "switch", "name": "Fixture Switch", "state": "attention",
                    "statusLabel": "BIOS pendente", "games": [{"id": "rom-1", "name": "Fixture ROM"}]},
                {"id": "playstation", "name": "Fixture PlayStation", "state": "unverified",
                    "statusLabel": "Nenhum jogo inventariado", "games": []}
            ],
            "platforms": [{"id": "switch", "name": "Fixture Switch", "state": "attention",
                "statusLabel": "BIOS pendente", "games": [{"id": "rom-1", "name": "Fixture ROM"}]}],
            "jobs": [
                {"type": "library.scan", "jobId": "scan-current", "state": "running",
                    "updatedAt": "2026-10-05T23:20:00+00:00"},
                {"type": "library.scan", "jobId": "scan-previous", "state": "succeeded",
                    "updatedAt": "2026-10-05T22:20:00+00:00",
                    "result": {"status": "scanned", "games": 4, "filesFound": 7,
                        "updates": 1, "dlcs": 0, "roots": 1}}
            ]
        })
        playtime: ({"games": [{"gameId": "10", "title": "Fixture Steam", "source": "steam", "playedSeconds": 5400,
            "action": {"kind": "steam-continue", "label": "Continuar", "enabled": true}}]})
        collections: ({"favorites": ["steam:20"], "collections": [{
            "id": "fixture-collection", "name": "Coleção fixture", "members": ["steam:10", "steam:20"]
        }]})
        components: [{"id": "fixture-emulator", "state": "missing"}]
        sync: ({"pending": 1, "conflicted": 1})
        doctor: ({"state": "attention"})
        libraryHealth: ({"counts": {"suspect": 1, "missing": 0, "error": 0}})
        backgroundColor: "#e7eceb"
        surfaceColor: "#f4f7f5"
        raisedColor: "#ffffff"
        borderColor: "#aebdbe"
        textColor: "#16212a"
        mutedColor: "#53616b"
        cyanColor: "#006f99"
        cyanDarkColor: "#005471"
        greenColor: "#167a45"
        amberColor: "#a35d00"
        typography: ({"scale": 1.5, "display": 36, "heading": 24, "title": 20,
            "body": 16, "metadata": 14, "badge": 12, "caption": 12,
            "controlHint": 14, "diagnostic": 14})
        onLibraryRequested: function(systemId) { harness.requestedSystem = systemId }
        onCollectionRequested: function(collectionId) { harness.requestedCollection = collectionId }
        onContinueRequested: function(game) { harness.continueWasRequested = game.gameId === "10" }
        onMaintenanceRequested: function(area) { harness.requestedMaintenance = area }
    }

    Timer {
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            if (phase === 0) {
                check(home.typeSize("display") === 54 && home.typeSize("badge") === 18,
                      "papéis tipográficos devem respeitar escala de 150%")
                check(home.catalog.length === 3, "Home deve unificar Steam e emulação")
                check(home.scannedGameCount === 4,
                      "Home deve ler jogos canônicos do último scan concluído")
                check(home.catalogCountLabel.indexOf("3 títulos publicados no catálogo Steam + emulação") >= 0,
                      "Home deve rotular o catálogo agregado")
                check(home.catalogCountLabel.indexOf("4 jogos canônicos") >= 0,
                      "Home deve apresentar jogos canônicos")
                check(home.catalogCountLabel.indexOf("7 arquivos") >= 0,
                      "Home deve apresentar arquivos")
                check(home.catalogCountLabel.indexOf("1 raiz") >= 0,
                      "Home deve apresentar raízes")
                check(home.catalogCountLabel.indexOf("varredura mais recente em andamento") >= 0,
                      "Home deve sinalizar a tentativa mais nova sem misturar seus dados ao snapshot anterior")
                check(home.formattedScanTimestamp(home.latestLibraryScan).length > 0,
                      "Home deve associar o snapshot concluído a um horário")
                const priorEmulation = home.emulation
                home.emulation = ({
                    "editorialPlatforms": priorEmulation.editorialPlatforms,
                    "platforms": priorEmulation.platforms,
                    "jobs": [
                        {"type": "library.scan", "jobId": "scan-failed", "state": "failed"},
                        {"type": "library.scan", "jobId": "scan-previous", "state": "succeeded",
                            "updatedAt": "2026-10-05T22:20:00+00:00",
                            "result": {"status": "scanned", "games": 4, "filesFound": 7,
                                "updates": 1, "dlcs": 0, "roots": 1}}
                    ]
                })
                check(home.catalogCountLabel.indexOf("última tentativa falhou; dados abaixo são do último sucesso") >= 0
                      && home.scannedGameCount === 4,
                      "uma tentativa falha deve ficar distinta do snapshot válido anterior")
                check(home.recent.length === 1, "Recentes deve usar somente sessões publicadas")
                check(home.favorites.length === 1 && home.favorites[0].gameRef === "steam:20",
                      "favoritos devem usar gameRef publicado")
                check(home.collectionItems.length === 1
                      && home.primaryCollection.id === "fixture-collection",
                      "coleções devem vir do read model publicado")
                check(home.systems.length === 3 && home.systems[2].id === "playstation",
                      "Home deve publicar plataformas canônicas sem jogo inventado")
                check(home.attentionSystems.length === 2, "pendência deve refletir estado da plataforma")
                check(home.componentAttention === 1 && home.syncAttention === 2 && home.libraryAttention === 1,
                      "Home deve resumir somente pendências operacionais publicadas")
                check(home.implicitHeight > home.height,
                      "Home deve publicar sua altura de conteúdo ao layout pai")
                home.libraryRequested("switch")
                check(requestedSystem === "switch", "ação de sistema deve preservar o destino")
                home.collectionRequested(home.primaryCollection.id)
                check(requestedCollection === "fixture-collection",
                      "coleção deve preservar o filtro publicado")
                home.continueRequested(home.featured)
                check(continueWasRequested, "retomada publicada deve preservar o jogo real")
                home.maintenanceRequested("sync")
                check(requestedMaintenance === "sync", "manutenção deve preservar o destino operacional")
                if (captureOutput !== "") {
                    contentItem.grabToImage(function(result) {
                        result.saveToFile(captureOutput)
                        width = 800
                        height = 1280
                        phase = 1
                    })
                    return
                }
                width = 800
                height = 1280
                phase = 1
                return
            }
            check(home.compact, "Home deve reflow em retrato")
            Qt.exit(failures === 0 ? 0 : 1)
        }
    }
}

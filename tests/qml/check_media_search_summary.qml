import QtQuick
import QtQuick.Window
import "../../src/steamzero/ui/qml"

// R2: o resumo da busca de dados e mídias diz o que aconteceu com os
// metadados; resultado degradado não pode parecer sucesso.
Window {
    id: harness
    visible: true
    width: 1280
    height: 800

    property int failures: 0

    Component {
        id: mainComp
        Main {}
    }

    function check(condition, message) {
        if (!condition) {
            failures += 1
            console.log("FAIL: " + message)
        }
    }

    function summary(main, result) {
        return main.taskResultSummary({"state": "completed", "type": "media.search", "result": result})
    }

    Timer {
        interval: 120
        running: true
        repeat: false
        onTriggered: {
            const main = mainComp.createObject(harness)
            check(main !== null, "Main deve instanciar")
            if (main) {
                const degraded = summary(main, {
                    "candidate_count": 0,
                    "provider_errors": {"screenscraper": "E-SCRAPE-PROVIDER-UNREACHABLE"},
                    "metadata": {"state": "no-metadata", "changed": [], "conflicts": []}
                })
                check(degraded.indexOf("degradado") >= 0, "provider degradado deve aparecer: " + degraded)
                check(degraded.indexOf("existentes foram mantidos") >= 0,
                      "sem metadado recebido, o resumo deve dizer que os dados foram mantidos: " + degraded)
                const updated = summary(main, {
                    "candidate_count": 2, "provider_errors": {},
                    "metadata": {"state": "updated", "changed": ["developer", "genres"],
                                 "conflicts": ["description"]}
                })
                check(updated.indexOf("2 campo(s) atualizado(s)") >= 0, "campos atualizados contados: " + updated)
                check(updated.indexOf("1 valor(es) manual(is) preservado(s)") >= 0,
                      "valor manual preservado deve ser dito: " + updated)
                const legacy = summary(main, {"candidate_count": 1, "provider_errors": {}})
                check(legacy.indexOf("1 candidato(s)") >= 0, "resultado sem metadados continua legível: " + legacy)
                main.destroy()
            }
            Qt.exit(failures === 0 ? 0 : 1)
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../../src/steamzero/ui/qml/job_result_presentation.js" as Presentation

Item {
    property int failures: 0

    function check(condition, message) {
        if (condition)
            return
        failures += 1
        console.error("FAIL: " + message)
    }

    Component.onCompleted: {
        const linkedRollback = {
            "type": "component.apply", "rawState": "rolled-back",
            "operationId": "operation-test"
        }
        const unlinkedFailure = {
            "type": "component.apply", "rawState": "rolled-back",
            "operationId": null
        }
        check(Presentation.componentJobOutcome(linkedRollback) === "rollback-complete",
              "rollback ligado a uma operação precisa ser distinto de falha")
        check(Presentation.componentJobOutcome(unlinkedFailure) === "failure-unlinked",
              "rolled-back sem operationId não pode alegar rollback confirmado")
        check(Presentation.componentJobOutcome({
            "type": "component.apply", "rawState": "rollback-failed"
        }) === "rollback-failed", "rollback-failed precisa permanecer explícito")
        check(Presentation.componentJobOutcome({
            "type": "component.apply", "rawState": "completed"
        }) === "succeeded", "completed precisa representar aplicação verificada")
        const trace = Presentation.componentJobTrace({
            "type": "component.apply", "adapterId": "demo-emulator",
            "action": "install", "executor": "engine", "artifact": "demo-payload",
            "targetVersion": "1.2.3", "sourceRevision": "revision-123",
            "artifactDigest": "abcdef1234567890",
            "correlationId": "request-test", "jobId": "job-test", "planId": "plan-test",
            "operationId": "operation-test"
        })
        check(trace.identity === "demo-emulator · install · engine",
              "identidade do componente deve ser exposta")
        check(trace.artifact === "demo-payload" && trace.targetVersion === "1.2.3",
              "artefato e versão planejada devem acompanhar a tarefa")
        check(trace.sourceRevision === "revision-123"
              && trace.artifactDigest === "abcdef1234567890",
              "revisão da fonte deve ser separada do digest do artefato")
        check(trace.correlationId === "request-test" && trace.jobId === "job-test"
              && trace.planId === "plan-test" && trace.operationId === "operation-test",
              "pedido, tarefa, plano e operação devem ser correlacionáveis")
        if (failures === 0)
            console.log("PASS: component job outcome and trace")
        Qt.exit(failures === 0 ? 0 : 1)
    }
}

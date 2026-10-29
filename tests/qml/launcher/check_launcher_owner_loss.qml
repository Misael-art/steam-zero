// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../../../src/steamzero/ui/qml/launcher"
Item {
    id: harness
    width: 1280; height: 800
    Component { id: sceneComponent; LauncherMain {} }
    Component { id: shellComponent; LauncherShell {} }
    TestCase {
        name: "LauncherOwnerLoss"
        when: windowShown
        function capture(scene, config, name) {
            if (!config.capture) return
            let saved=false
            verify(scene.contentItem.grabToImage(function(result) {
                saved=result.saveToFile(config.capture + "/" + name + ".png")
            }))
            tryVerify(function() { return saved }, 3000)
        }
        function waitForLostTerminal(scene) {
            let counts=null
            let pending=false
            tryVerify(function() {
                if (counts && counts.terminalDrops > 0) return true
                if (!pending) {
                    pending=true
                    scene._request("GET","/owner-control/count",null,function(status,text) {
                        pending=false
                        if(status===200) counts=JSON.parse(text)
                    })
                }
                return false
            },5000)
            compare(counts.launches,0)
            return counts
        }
        function test_owner_loss_recovery_is_explicit() {
            const request=new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("owner-loss-config.json"), false)
            request.send()
            const config=JSON.parse(request.responseText)
            const scene=createTemporaryObject(sceneComponent,harness)
            scene.api=config.api; scene.token=config.token; scene._start()
            tryCompare(scene,"loadState","ready")
            const shell=scene._activeLauncherShell()
            if (config.mode === "restart-lost-terminal") {
                compare(shell.observedSessionId,config.identity)
                const repeated=waitForLostTerminal(scene)
                compare(repeated.recoveries,0)
                verify(shell.launchState!=="failed")
                compare(shell.homeFocus,"library:lifetime-probe")
                capture(scene,config,"02-terminal-get-lost-again")
                return
            }
            if (config.mode === "observe") {
                tryCompare(shell,"launchState","emulator-visible",5000)
                compare(shell.sessionUncertain,false)
                compare(shell.requestSessionRecovery(),false)
                capture(scene,config,"01-game-survives-owner-loss")
                scene._request("GET","/owner-control/finish",null,function(){})
            }
            if (config.mode !== "recover-reopened") {
                tryCompare(shell,"sessionUncertain",true,5000)
                tryCompare(shell,"sessionRecoveryAvailable",true,3000)
                compare(shell.launchFocused(),false)
            }
            let counts=null
            scene._request("GET","/owner-control/count",null,function(status,text){
                if(status===200)counts=JSON.parse(text)
            })
            tryVerify(function(){return counts!==null},2000)
            compare(counts.launches,0); compare(counts.recoveries,0)
            if (config.mode !== "recover-reopened") {
                tryVerify(function(){return findChild(shell,"sessionRecoveryButton").activeFocus},2000)
                capture(scene,config,"02-explicit-recovery-available")
                if(config.mode === "observe") return
                keyClick(Qt.Key_Return)
                compare(shell.requestSessionRecovery(),false)
                if(config.mode === "lost-terminal") {
                    const lost=waitForLostTerminal(scene)
                    compare(lost.recoveries,1)
                    verify(shell.launchState!=="failed")
                    capture(scene,config,"01-terminal-get-lost")
                    return
                }
            }
            tryCompare(shell,"launchState","failed",6000)
            compare(shell.observedSessionId,config.identity)
            verify(shell.launchError.indexOf("E-SESSION-ORPHANED")>=0)
            compare(shell.sessionUncertain,false)
            tryVerify(function(){return findChild(shell,"launchFailureRetry").activeFocus},2000)
            capture(scene,config,"03-canonical-failure-without-estimate")
            keyClick(Qt.Key_Return)
            compare(shell.launchState,"recovered")
            keyClick(Qt.Key_Return)
            tryVerify(function(){return shell.gamePage!==null},3000)
            const play=findChild(shell,"gameAction")
            tryVerify(function(){return play!==null && play.modelData.enabled===true},3000)
            keyClick(Qt.Key_Return)
            tryCompare(shell,"launchState","emulator-visible",6000)
            compare(shell.launchFocused(),false)
            capture(scene,config,"04-explicit-retry-running")
            scene._request("GET","/owner-control/finish",null,function(){})
            tryCompare(shell,"launchState","recovered",5000)
            compare(shell.gamePage,null)
            compare(shell.homeFocus,"library:lifetime-probe")
            tryVerify(function(){return !findChild(shell,"returnFadeLayer").visible},2000)
            capture(scene,config,"05-canonical-return")
        }
        function test_transient_uncertainty_still_accepts_canonical_close() {
            const shell=createTemporaryObject(shellComponent,harness,{
                focusMap:{initial:"",nodes:{}},sections:[],
                launchState:"emulator-visible",sessionGameId:"probe",observedSessionId:"exact"})
            verify(shell!==null)
            verify(shell.observeSession({gameId:"probe",sessionId:"exact",state:"unknown",recovery:{available:false}}))
            compare(shell.sessionUncertain,true)
            verify(shell.observeSession({gameId:"probe",sessionId:"exact",state:"closed"}))
            compare(shell.launchState,"recovered")
            compare(shell.sessionUncertain,false)
        }
    }
}

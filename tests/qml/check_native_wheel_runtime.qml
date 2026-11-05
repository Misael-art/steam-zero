// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import "../../src/steamzero/ui/qml/launcher"

Window {
    id: harness
    visible: true
    width: 1280
    height: 800
    color: "#071019"
    property int failures: 0
    property int phase: 0
    property var objects: ({})
    readonly property var input: {
        const prefix = "--native-runtime="
        for (let i = 0; i < Qt.application.arguments.length; ++i)
            if (Qt.application.arguments[i].startsWith(prefix))
                return JSON.parse(Qt.application.arguments[i].slice(prefix.length))
        return ({})
    }
    function check(value, message) {
        if (!value) { failures += 1; console.error("NATIVE-RUNTIME-FAIL " + message) }
    }
    function find(item, name) {
        if (!item) return null
        if (item.objectName === name) return item
        const children = item.children || []
        for (let i = 0; i < children.length; ++i) {
            const child = find(children[i], name)
            if (child) return child
        }
        return null
    }
    LauncherCinema {
        id: cinema
        anchors.fill: parent
        scene: harness.input.scenes ? harness.input.scenes[1] : null
        currentFocus: scene ? scene.focusId : ""
    }
    Timer {
        id: step
        interval: 280
        repeat: false
        running: true
        onTriggered: {
            const composition = find(cinema, "cinemaNativeComposition")
            check(composition !== null && composition.visible, "native composition is visible in Launcher")
            check(cinema.activeTheme.logicalRevision === input.revision, "persisted revision matches Studio")
            check(find(cinema, "cinemaHeader").text.indexOf(cinema.activeTheme.themeName) === 0,
                  "Launcher identifies the authored theme")
            check(cinema.activeLayout.kind === "wheel", "wheel is not replaced by a different layout")
            const expected = cinema.scene.layouts[cinema.scene.layoutId].entries.length
            let ready = composition && composition.entryCount === expected && expected > 0
            for (let i = 0; ready && i < composition.entryCount; ++i)
                ready = composition.entryAt(i) && composition.entryAt(i).sourceStatus === Image.Ready
            if (!ready) { step.restart(); return }
            if (phase === 0) {
                for (let i = 0; i < composition.entryCount; ++i) {
                    const item = composition.entryAt(i)
                    check(item.sourceStatus === Image.Ready, "actual Launcher image decode")
                    objects[item.model.key] = item
                }
                check(cinema.selectedGame.id === "b", "initial metadata belongs to selection")
                cinema.currentFocus = input.scenes[2].focusId
                check(Object.keys(cinema.selectedGame).length === 0, "stale metadata is withheld")
                check(cinema.videoSource === "", "stale audiovisual source is stopped")
                for (let i = 0; i < 42; ++i) {
                    cinema.currentFocus = input.scenes[i % 3].focusId
                    cinema.scene = input.scenes[i % 3]
                }
                phase = 1; step.restart()
            } else {
                check(cinema.selectedGame.id === "c", "final metadata belongs to latest selection")
                check(find(cinema, "cinemaSelectedTitle").text === "Game C", "visible title is latest")
                const selected = composition.entryAt(Number(cinema.scene.selected))
                check(selected.model.key === cinema.selectedGame.id, "artwork and metadata identities agree")
                check(selected.model.recipeName === "original", "center recipe from authored document executes")
                for (let i = 0; i < composition.entryCount; ++i) {
                    const item = composition.entryAt(i)
                    const key = item.model.key
                    const retained = input.scenes.every(function(scene) {
                        return scene.layouts[scene.layoutId].entries.some(function(entry) { return entry.key === key })
                    })
                    if (retained && objects[key])
                        check(objects[key] === item, "window reorder preserves continuously retained source instance " + key)
                    check(item.sourceStatus === Image.Ready, "new window entry is actually decoded")
                    if (input.expectEffects) {
                        check(!item.fallbackActive, "persisted recipe executes in the Launcher RHI context")
                        if (key === cinema.selectedGame.id)
                            check(item.outlineActive && Math.abs(item.appliedSaturation) < 0.01, "center retains source colors and outline")
                        else check(item.appliedSaturation < -0.99, "side recipe actually applies grayscale")
                    }
                    check(item.sourceDecodeCount === 1, "window reorder does not reopen the source")
                }
                console.log("NATIVE-RUNTIME-RESULT " + JSON.stringify({failures: failures, revision: cinema.activeTheme.logicalRevision, selected: cinema.selectedGame.id}))
                if (input.capture) {
                    cinema.grabToImage(function(result) {
                        check(result.saveToFile(input.capture), "capture actual Launcher composition")
                        Qt.exit(failures === 0 ? 0 : 1)
                    })
                } else Qt.exit(failures === 0 ? 0 : 1)
            }
        }
    }
    Timer { interval: 10000; running: true; onTriggered: { console.error("NATIVE-RUNTIME-FAIL timeout"); Qt.exit(1) } }
}

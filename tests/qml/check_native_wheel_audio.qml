import "LAUNCHER_IMPORT"
// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window

Window {
    id: harness

    property int phase: 0
    property int ticks: 0
    property int failures: 0
    property bool capturing: false
    property var foregroundPoint: []
    property int visibilityStopChecks: 0

    function arg(name) {
        for (let i = 0; i < Qt.application.arguments.length; ++i) if (Qt.application.arguments[i].startsWith(name + "=")) {
            return Qt.application.arguments[i].slice(name.length + 1);
        }
        return "";
    }

    function check(value, message) {
        if (!value) {
            failures++;
            console.error("AV-FAIL " + message);
        }
    }

    function scene(key, source) {
        return {
            "focusId": key,
            "selected": 0,
            "layoutId": "wheel",
            "performanceTier": "cinematic",
            "viewport": {
                "width": 640,
                "height": 240
            },
            "layouts": {
                "wheel": {
                    "kind": "wheel",
                    "entries": [{id: "art", key: key, kind: "image", x: 288, y: 88,
                        width: 64, height: 64, opacity: 1, scale: 1,
                        source: arg("--foreground"), recipe: {source: "logo", nodes: []}}]
                }
            },
            "theme": {
                "logicalRevision": "fixture-av-revision",
                "resolved": {
                }
            },
            "items": [{
                "id": key,
                "title": key,
                "videoUrl": source
            }]
        };
    }

    function find(item, name) {
        if (!item)
            return null;

        if (item.objectName === name)
            return item;

        const children = item.children || [];
        for (let i = 0; i < children.length; ++i) {
            const hit = find(children[i], name);
            if (hit)
                return hit;

        }
        return null;
    }

    visible: true
    width: 640
    height: 480

    Item {
        id: cinemaOwner
        anchors.fill: parent

        LauncherCinema {
            id: cinema
            anchors.fill: parent
            scene: harness.scene("a", harness.arg("--clip-a"))
            currentFocus: "a"
        }
    }

    Timer {
        interval: 50
        running: true
        repeat: true
        onTriggered: {
            ticks++;
            if (ticks > 220) {
                console.error("AV-FAIL timeout " + cinema.mediaPlaybackState + " " + cinema.mediaDiagnostic);
                Qt.exit(1);
                return ;
            }
            const backdrop = harness.find(cinema, "cinemaVideoBackdrop");
            if (phase === 0 && cinema.decodedVideoFrames > 2 && backdrop.player.position > 600) {
                const previous = backdrop.player;
                cinema.visible = false;
                check(!previous.playing, "hiding Cinema stops actual playback synchronously");
                check(backdrop.player === null && cinema.mediaSelectionKey === "", "hidden Cinema clears the media owner");
                check(cinema.mediaPlaybackState === "idle", "hidden Cinema reports idle");
                if (!previous.playing && backdrop.player === null)
                    visibilityStopChecks++;
                cinema.visible = true;
                phase = 10;
            } else if (phase === 10 && cinema.decodedVideoFrames > 2 && backdrop.player.position > 600) {
                check(cinema.mediaSelectionKey === "a", "revealing Cinema resumes the current owner");
                const previous = backdrop.player;
                cinemaOwner.visible = false;
                check(!previous.playing, "hiding an ancestor stops actual playback synchronously");
                check(backdrop.player === null && cinema.mediaSelectionKey === "", "hidden ancestor clears the media owner");
                check(cinema.mediaPlaybackState === "idle", "hidden ancestor reports idle");
                if (!previous.playing && backdrop.player === null)
                    visibilityStopChecks++;
                cinemaOwner.visible = true;
                phase = 11;
            } else if (phase === 11 && cinema.decodedVideoFrames > 2 && backdrop.player.position > 600) {
                check(cinema.mediaSelectionKey === "a", "initial owner");
                check(backdrop.player.hasAudio, "clip must contain an audio track");
                for (let i = 0; i < 18; ++i) {
                    cinema.currentFocus = "transition-" + i;
                    check(cinema.mediaSelectionKey === "", "old media stops before replacement");
                    cinema.scene = harness.scene("transition-" + i, harness.arg("--clip-a"));
                }
                cinema.currentFocus = "c";
                cinema.scene = harness.scene("c", harness.arg("--clip-b"));
                phase = 1;
            } else if (phase === 1 && cinema.mediaSelectionKey === "c" && cinema.decodedVideoFrames > 5 && backdrop.player.position > 1200 && !capturing) {
                capturing = true;
                check(backdrop.ready && backdrop.visible, "decoded video is revealed");
                backdrop.grabToImage(function(result) {
                    check(result.saveToFile(harness.arg("--capture")), "actual video pixels captured");
                    const composition = harness.find(cinema, "cinemaNativeComposition")
                    const artwork = composition.entryAt(0)
                    check(artwork.sourceStatus === Image.Ready, "foreground is actually decoded")
                    const point = artwork.mapToItem(cinema, 32, 32)
                    harness.foregroundPoint = [point.x, point.y]
                    cinema.grabToImage(function(composed) {
                        check(composed.saveToFile(harness.arg("--foreground-capture")), "capture composed video and artwork")
                        cinema.currentFocus = "broken";
                        cinema.scene = harness.scene("broken", harness.arg("--clip-bad"));
                        phase = 2;
                    })
                });
            } else if (phase === 2 && cinema.mediaPlaybackState === "failed") {
                check(cinema.decodedVideoFrames === 0 && !backdrop.ready, "failed media cannot reuse old frames");
                check(cinema.mediaDiagnostic !== "", "failed decoder gives recovery information");
                console.log("AV-RESULT " + JSON.stringify({
                    "failures": failures,
                    "visibilityStopChecks": visibilityStopChecks,
                    "finalOwner": cinema.mediaSelectionKey,
                    "foregroundPoint": harness.foregroundPoint,
                    "failed": cinema.mediaPlaybackState
                }));
                Qt.exit(failures === 0 ? 0 : 1);
            }
        }
    }

}

// SPDX-License-Identifier: GPL-3.0-or-later
// Engine-owned audiovisual primitive. A theme supplies data, never player code.
import QtQuick
import QtMultimedia

Item {
    id: root
    property url source
    property string selectionKey: ""
    property bool active: true
    property bool muted: false
    property real volume: 1
    property int fillMode: VideoOutput.PreserveAspectCrop
    property int loops: MediaPlayer.Infinite
    property int decodedFrames: 0
    property bool _completed: false
    readonly property bool playing: player.playbackState === MediaPlayer.PlayingState
    readonly property bool hasAudio: player.hasAudio
    readonly property bool hasVideo: player.hasVideo
    readonly property bool audioOutputAvailable: devices.audioOutputs.length > 0
    readonly property string audioState: !hasAudio ? "absent" : muted || volume <= 0 ? "muted"
        : !audioOutputAvailable ? "unavailable" : playing ? "submitted" : "idle"
    readonly property string audioDiagnostic: audioState === "unavailable"
        ? qsTr("A mídia contém áudio, mas não há saída de áudio disponível. Selecione uma saída no sistema e tente novamente.") : ""
    readonly property real position: player.position
    readonly property string errorMessage: player.error === MediaPlayer.NoError ? "" : player.errorString
    // LoadedMedia is metadata, not a rendered frame. The consumer may reveal
    // this surface only after the sink has received actual decoded video.
    readonly property bool ready: active && playing && decodedFrames > 0
    readonly property string playbackState: errorMessage !== "" ? "failed"
        : !active || source.toString() === "" ? "idle"
        : ready ? (audioState === "unavailable" ? "partial" : "playing")
        : playing && hasAudio && !hasVideo ? (audioState === "unavailable" ? "partial" : "audioPlaying") : "loading"

    function restart() {
        player.stop()
        decodedFrames = 0
        if (_completed && active && source.toString() !== "") player.play()
    }
    function stop() { player.stop(); decodedFrames = 0 }
    onSourceChanged: { decodedFrames = 0; if (_completed) restart() }
    onActiveChanged: if (_completed) restart()
    Component.onCompleted: { _completed = true; restart() }
    Component.onDestruction: if (player) player.stop()

    MediaDevices { id: devices }
    AudioOutput { id: sound; device: devices.defaultAudioOutput; volume: root.volume; muted: root.muted }
    MediaPlayer {
        id: player
        source: root.source
        loops: root.loops
        audioOutput: sound
        videoOutput: output
    }
    VideoOutput { id: output; anchors.fill: parent; fillMode: root.fillMode }
    Connections {
        target: output.videoSink
        function onVideoFrameChanged(frame) {
            if (root.active && output.videoSink.videoSize.width > 0
                    && output.videoSink.videoSize.height > 0)
                root.decodedFrames = Math.min(root.decodedFrames + 1, 1000000000)
        }
    }
}

# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Qt playback into an isolated virtual sink, never the user's audio graph.

Generated color/sine clips are CC0 fixtures. PCM capture proves software audio
output; this does not certify physical speakers, latency or hardware FPS.
"""

from __future__ import annotations

import array
import collections
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.visual

CORE_CONFIG = """
context.properties = { core.daemon = true core.name = pipewire-0
 support.dbus = false
 default.clock.rate = 48000 }
context.spa-libs = {
 audio.convert.* = audioconvert/libspa-audioconvert
 support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-link-factory }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-spa-node-factory }
 { name = libpipewire-module-access }
]
context.objects = [
 { factory = metadata args = { metadata.name = default } }
 { factory = spa-node-factory args = { factory.name =
 support.node.driver
 node.name = Dummy-Driver priority.driver = 20000 } }
 { factory = adapter args = { factory.name =
 support.null-audio-sink
 node.name = steamzero_fixture
 node.description = "SteamZero isolated fixture" media.class = Audio/Sink
 audio.channels = 2
 audio.position = [ FL FR ]
 adapter.auto-port-config = { mode = dsp monitor = true position = preserve } } }
]
"""

PULSE_CONFIG = """
context.properties = { support.dbus = false }
context.spa-libs = {
 audio.convert.* = audioconvert/libspa-audioconvert
 support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-protocol-pulse args = { server.address = [ "unix:PULSE_SOCKET" ] } }
]
"""


CLIENT_CONFIG = """
context.properties = { support.dbus = false }
context.spa-libs = {
 audio.convert.* = audioconvert/libspa-audioconvert
 support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-metadata }
]
stream.properties = { adapter.auto-port-config = { mode = dsp } }
"""


def _run(argv: list[str], env: dict[str, str], *, timeout: float = 3) -> str:
    completed = subprocess.run(
        argv, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )
    assert completed.returncode == 0, f"{argv[0]}: {completed.stderr} {completed.stdout}"
    return completed.stdout


def _wire_owned_streams(
    env: dict[str, str],
    qml_pid: int,
    reader_pid: int,
    linked: set[tuple[int, int]],
    configured: set[int],
) -> dict:
    objects = json.loads(_run(["pw-dump"], env))
    nodes = {
        o["id"]: o.get("info", {}).get("props", {}) for o in objects if o["type"].endswith(":Node")
    }
    sinks = [node for node, p in nodes.items() if p.get("node.name") == "steamzero_fixture"]
    assert len(sinks) == 1, "private fixture sink must be unique"
    # This private server loads no hardware/session/portal/RT modules.
    assert not any(p.get("device.api") for p in nodes.values())
    clients = {
        o["id"]: o.get("info", {}).get("props", {})
        for o in objects
        if o["type"].endswith(":Client")
    }
    outputs = [
        node
        for node, p in nodes.items()
        if str(
            p.get(
                "application.process.id",
                clients.get(p.get("client.id"), {}).get(
                    "pipewire.sec.pid",
                    clients.get(p.get("client.id"), {}).get("application.process.id"),
                ),
            )
        )
        == str(qml_pid)
        and p.get("media.class") == "Stream/Output/Audio"
    ]
    readers = [
        node for node, p in nodes.items() if str(p.get("application.process.id")) == str(reader_pid)
    ]
    ports = [
        (o["id"], o.get("info", {}).get("props", {}))
        for o in objects
        if o["type"].endswith(":Port")
    ]

    for node in outputs + readers:
        serial = int(nodes[node]["object.serial"])
        if serial not in configured:
            direction = "Output" if node in outputs else "Input"
            _run(
                [
                    "pw-cli",
                    "set-param",
                    str(node),
                    "PortConfig",
                    "{ direction = " + direction + " mode = dsp }",
                ],
                env,
            )
            configured.add(serial)

    def channel_ports(ids: list[int], direction: str) -> list[tuple[int, int, str]]:
        return [
            (pid, int(p["object.serial"]), str(p.get("audio.channel", "")))
            for pid, p in ports
            if p.get("node.id") in ids and p.get("port.direction") == direction
        ]

    for sending, receiving in [
        (channel_ports(outputs, "out"), channel_ports(sinks, "in")),
        (channel_ports(sinks, "out"), channel_ports(readers, "in")),
    ]:
        for target, target_serial, channel in receiving:
            candidates = [
                (source, serial)
                for source, serial, source_channel in sending
                if source_channel == channel
            ]
            if not candidates and len(sending) == 1:
                candidates = [(sending[0][0], sending[0][1])]
            for source, source_serial in candidates:
                if (source_serial, target_serial) not in linked:
                    subprocess.run(
                        ["pw-link", str(source), str(target)],
                        env=env,
                        capture_output=True,
                        timeout=2,
                        check=True,
                    )
                    linked.add((source_serial, target_serial))

    return {
        "nodes": nodes,
        "clients": clients,
        "ports": ports,
        "outputs": outputs,
        "readers": readers,
        "states": {
            o["id"]: o.get("info", {}).get("state") for o in objects if o["type"].endswith(":Node")
        },
        "linkStates": [o.get("info", {}) for o in objects if o["type"].endswith(":Link")],
    }


def _power(samples: list[int], frequency: float) -> float:
    coefficient = 2 * math.cos(2 * math.pi * frequency / 48000)
    first = second = 0.0
    for sample in samples:
        current = sample + coefficient * first - second
        second, first = first, current
    return first * first + second * second - coefficient * first * second


def _fixture_clip(clip: Path, color: str, frequency: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64:r=12:d=2",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=2",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            "-q:v",
            "4",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-shortest",
            str(clip),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )


def test_native_video_audio_output_owner_changes_and_invalid_decode(tmp_path: Path) -> None:
    required = (
        "ffmpeg",
        "pipewire",
        "pipewire-pulse",
        "pw-dump",
        "pw-link",
        "pw-cli",
        "pactl",
        "parec",
    )
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        pytest.skip("NATIVE-AV-ENV-001: isolated audio tools unavailable: " + ", ".join(missing))
    if os.environ.get("QT_QUICK_BACKEND") == "software":
        pytest.skip("NATIVE-AV-ENV-002: actual video pixel proof requires the RHI context")
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    clips = []
    for name, color, frequency in [("a", "red", "440"), ("b", "blue", "880")]:
        clip = tmp_path / f"{name}.mp4"
        _fixture_clip(clip, color, frequency)
        clips.append(clip)
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"invalid video fixture")
    harness = tmp_path / "av.qml"
    harness.write_text(
        (ROOT / "tests/qml/check_native_wheel_audio.qml")
        .read_text()
        .replace("LAUNCHER_IMPORT", (ROOT / "src/steamzero/ui/qml/launcher").as_uri())
    )
    foreground = tmp_path / "foreground.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(foreground)
    capture = tmp_path / "last-video-frame.png"
    foreground_capture = tmp_path / "foreground-composition.png"
    with tempfile.TemporaryDirectory(prefix="sz-audio-", dir="/tmp") as private:
        own = Path(private)
        (own / "pulse").mkdir(mode=0o700)
        core = own / "core.conf"
        core.write_text(CORE_CONFIG)
        pulse = own / "pulse.conf"
        pulse.write_text(
            PULSE_CONFIG.replace("PULSE_SOCKET", str(own / "pulse/native"))
            + "\nstream.properties = { adapter.auto-port-config = { mode = dsp } }\n"
        )
        (own / "client.conf").write_text(CLIENT_CONFIG)
        client = own / "pulse-client.conf"
        client.write_text("autospawn = no\n")
        env = os.environ.copy()
        env.update(
            XDG_RUNTIME_DIR=str(own),
            PIPEWIRE_RUNTIME_DIR=str(own),
            PIPEWIRE_CONFIG_DIR=str(own),
            PIPEWIRE_REMOTE="pipewire-0",
            PULSE_RUNTIME_PATH=str(own / "pulse"),
            PULSE_SERVER="unix:" + str(own / "pulse/native"),
            PULSE_CLIENTCONFIG=str(client),
            DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(own / "no-bus"),
            QT_FORCE_STDERR_LOGGING="1",
            QT_LOGGING_RULES="",
            QT_QPA_PLATFORM="offscreen",
            QT_QUICK_BACKEND="rhi",
            QSG_RHI_BACKEND="opengl",
        )
        processes: list[subprocess.Popen[bytes]] = []
        logs = []
        chunks: collections.deque[bytes] = collections.deque(maxlen=1024)
        reader_thread = None
        graph_history = []
        try:
            for command in (["pipewire", "-c", str(core)], ["pipewire-pulse", "-c", str(pulse)]):
                log = (tmp_path / (Path(command[0]).name + ".log")).open("wb")
                logs.append(log)
                process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                processes.append(process)
                expected = own / ("pipewire-0" if command[0] == "pipewire" else "pulse/native")
                deadline = time.monotonic() + 5
                while (
                    not expected.exists() and process.poll() is None and time.monotonic() < deadline
                ):
                    time.sleep(0.05)
                assert expected.exists(), Path(log.name).read_text()
            deadline = time.monotonic() + 3
            sinks = []
            while time.monotonic() < deadline:
                sinks = json.loads(_run(["pactl", "--format=json", "list", "sinks"], env))
                if any(sink.get("name") == "steamzero_fixture" for sink in sinks):
                    break
                time.sleep(0.05)
            assert any(sink.get("name") == "steamzero_fixture" for sink in sinks), (
                sinks,
                _run(["pw-dump"], env),
                (tmp_path / "pipewire.log").read_text(),
                (tmp_path / "pipewire-pulse.log").read_text(),
            )
            _run(["pactl", "set-default-sink", "steamzero_fixture"], env)
            recorder = subprocess.Popen(
                [
                    "parec",
                    "--device=steamzero_fixture.monitor",
                    "--raw",
                    "--format=s16le",
                    "--rate=48000",
                    "--channels=2",
                    "--latency-msec=20",
                    "--process-time-msec=10",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(recorder)

            def drain() -> None:
                assert recorder.stdout is not None
                while chunk := recorder.stdout.read(4096):
                    chunks.append(chunk)

            reader_thread = threading.Thread(target=drain, daemon=True)
            reader_thread.start()
            player = subprocess.Popen(
                [
                    runtime,
                    str(harness),
                    "--",
                    "--clip-a=" + clips[0].as_uri(),
                    "--clip-b=" + clips[1].as_uri(),
                    "--clip-bad=" + bad.as_uri(),
                    "--capture=" + str(capture),
                    "--foreground=" + foreground.as_uri(),
                    "--foreground-capture=" + str(foreground_capture),
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(player)
            linked: set[tuple[int, int]] = set()
            configured: set[int] = set()
            deadline = time.monotonic() + 15
            while player.poll() is None and time.monotonic() < deadline:
                live_graph = _wire_owned_streams(env, player.pid, recorder.pid, linked, configured)
                graph = {
                    "outputs": live_graph["outputs"],
                    "readers": live_graph["readers"],
                    "ports": [
                        (
                            i,
                            p.get("object.serial"),
                            p.get("node.id"),
                            p.get("audio.channel"),
                            p.get("port.direction"),
                        )
                        for i, p in live_graph["ports"]
                    ],
                    "states": live_graph["states"],
                    "links": live_graph["linkStates"],
                }
                if not graph_history or graph != graph_history[-1]:
                    graph_history.append(graph)
                time.sleep(0.05)
            stdout, stderr = player.communicate(timeout=2)
            output = (stdout + stderr).decode(errors="replace")
            assert player.returncode == 0, output
            assert "AV-RESULT" in output, output
            assert not any(
                word in output
                for word in (
                    "TypeError",
                    "ReferenceError",
                    "SyntaxError",
                    "Binding loop",
                    "Cannot assign",
                )
            ), output
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            if reader_thread is not None:
                reader_thread.join(timeout=2)
            for log in logs:
                log.close()
    import re

    report_match = re.search(r"AV-RESULT (.+)", output)
    assert report_match is not None
    report = json.loads(report_match[1])
    assert report["visibilityStopChecks"] == 2
    with Image.open(foreground_capture) as composed:
        foreground_pixel = composed.convert("RGB").getpixel(
            tuple(round(v) for v in report["foregroundPoint"])
        )
    assert foreground_pixel[0] > 245 and max(foreground_pixel[1:]) < 8, (
        "backdrop video must remain behind native artwork",
        foreground_pixel,
    )
    pcm = array.array("h")
    pcm.frombytes(b"".join(chunks))
    mono = list(pcm[::2])
    active = [
        i for i in range(0, len(mono), 480) if max(map(abs, mono[i : i + 480]), default=0) > 256
    ]
    assert active, json.dumps(
        {
            "failure": "Qt must output actual non-silent PCM to the private sink",
            "samples": len(pcm),
            "links": list(linked),
            "qml": output,
            "graphs": graph_history,
            "recorder": recorder.stderr.read().decode(errors="replace"),
        }
    )
    end = min(len(mono), active[-1] + 480)
    tail = mono[max(0, end - 24000) : end]
    assert len(tail) >= 12000
    assert _power(tail, 880) > _power(tail, 440) * 20, json.dumps(
        {
            "failure": "final audio must belong to latest selection",
            "sampleCount": len(mono),
            "activeEnd": end,
            "rawGraphs": graph_history,
            "links": list(linked),
            "graphs": [
                {"outputs": graph["outputs"], "readers": graph["readers"], "ports": graph["ports"]}
                for graph in graph_history
            ],
        }
    )
    with Image.open(capture) as frame:
        pixel = frame.convert("RGBA").getpixel((frame.width // 2, frame.height // 2))
    assert pixel[2] > pixel[0] + 100 and pixel[2] > pixel[1] + 100, (
        "actual final video frame must be blue"
    )

    capture_root = os.environ.get("SZ_CAPTURE_DIR", "")
    if capture_root:
        destination = Path(capture_root) / "native-wheel-av"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(capture, destination / "latest-video-frame.png")
        (destination / "software-output.json").write_text(
            json.dumps(
                {
                    "source": "generated CC0 color and sine fixtures",
                    "context": "Qt and private PipeWire virtual sink",
                    "physicalAudioCertified": False,
                    "visibilityStopChecks": report["visibilityStopChecks"],
                    "sampleRate": 48000,
                    "channels": 2,
                    "capturedFrames": len(mono),
                    "analysisFrames": len(tail),
                    "finalSignalHz": 880,
                    "staleSignalHz": 440,
                    "finalSignalPower": _power(tail, 880),
                    "staleSignalPower": _power(tail, 440),
                    "requiredPowerRatio": 20,
                    "finalVideoCenterRGBA": pixel,
                    "recorderLatencyRequestedMs": 20,
                    "recorderProcessTimeRequestedMs": 10,
                },
                indent=2,
            )
            + "\n"
        )


def test_native_video_keeps_frames_but_reports_missing_audio_device(tmp_path: Path) -> None:
    required = ("ffmpeg", "pipewire", "pw-dump")
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        pytest.skip("NATIVE-AV-ENV-001: isolated audio tools unavailable: " + ", ".join(missing))
    if os.environ.get("QT_QUICK_BACKEND") == "software":
        pytest.skip("NATIVE-AV-ENV-002: decoded video requires the RHI context")
    runtime = shutil.which("qml6") or shutil.which("qml")
    assert runtime is not None
    clip = tmp_path / "with-audio.mp4"
    _fixture_clip(clip, "blue", "880")
    harness = tmp_path / "no-output.qml"
    harness.write_text(
        """
import QtQuick
import QtQuick.Window
import "ENGINE_IMPORT"
Window {
 id: root; width: 128; height: 128; visible: true; property int ticks: 0
 SceneMediaPlayer { id: media; anchors.fill: parent; source: "CLIP_URI" }
 Timer { interval: 50; running: true; repeat: true; onTriggered: {
  root.ticks++
  if (root.ticks > 100) { console.error("AV-NO-OUTPUT timeout"); Qt.exit(1); return }
  if (media.decodedFrames > 1 && media.hasAudio && media.playing) {
   const accepted = media.ready && media.audioState === "unavailable"
       && media.audioDiagnostic !== "" && media.playbackState === "partial"
   console.log("AV-NO-OUTPUT " + JSON.stringify({accepted: accepted,
       audioState: media.audioState, playbackState: media.playbackState,
       diagnostic: media.audioDiagnostic, frames: media.decodedFrames}))
   Qt.exit(accepted ? 0 : 1)
  }
 } }
}
""".replace("ENGINE_IMPORT", (ROOT / "src/steamzero/ui/qml").as_uri()).replace(
            "CLIP_URI", clip.as_uri()
        )
    )
    with tempfile.TemporaryDirectory(prefix="sz-audio-unavailable-", dir="/tmp") as private:
        own = Path(private)
        config = own / "core.conf"
        config.write_text(CORE_CONFIG.split(" { factory = adapter args", 1)[0] + "]\n")
        (own / "client.conf").write_text(CLIENT_CONFIG)
        pulse = own / "pulse-client.conf"
        pulse.write_text("autospawn = no\n")
        env = os.environ.copy()
        env.update(
            XDG_RUNTIME_DIR=str(own),
            PIPEWIRE_RUNTIME_DIR=str(own),
            PIPEWIRE_CONFIG_DIR=str(own),
            PIPEWIRE_REMOTE="pipewire-0",
            PULSE_SERVER="unix:" + str(own / "no-pulse"),
            PULSE_CLIENTCONFIG=str(pulse),
            DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(own / "no-bus"),
            QT_AUDIO_BACKEND="pipewire",
            QT_QPA_PLATFORM="offscreen",
            QT_QUICK_BACKEND="rhi",
            QSG_RHI_BACKEND="opengl",
            QT_FORCE_STDERR_LOGGING="1",
            QT_LOGGING_RULES="",
        )
        with (tmp_path / "no-output-server.log").open("wb") as log:
            server = subprocess.Popen(
                ["pipewire", "-c", str(config)], env=env, stdout=log, stderr=log
            )
            try:
                deadline = time.monotonic() + 5
                while (
                    not (own / "pipewire-0").exists()
                    and server.poll() is None
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.05)
                assert (own / "pipewire-0").exists(), Path(log.name).read_text()
                objects = json.loads(_run(["pw-dump"], env))
                node_props = [
                    o.get("info", {}).get("props", {})
                    for o in objects
                    if o["type"].endswith(":Node")
                ]
                assert not any(
                    p.get("media.class") == "Audio/Sink" or p.get("device.api") for p in node_props
                )
                result = subprocess.run(
                    [runtime, str(harness)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                output = result.stdout + result.stderr
                assert result.returncode == 0, output
                assert "AV-NO-OUTPUT" in output
                assert not any(
                    word in output for word in ("TypeError", "ReferenceError", "SyntaxError")
                ), output
            finally:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)

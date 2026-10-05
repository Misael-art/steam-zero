# SPDX-License-Identifier: GPL-3.0-or-later
"""Contratos QML executados no compositor offscreen quando Qt está disponível."""

from __future__ import annotations

import functools
import http.client
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path

import pytest

from steamzero.adapters.desktop_contracts import handheld_ui_contracts

QML = shutil.which("qml6")
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class _CentralLoadingRun:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


#: Ambiente visual ausente. Não é motivo para verde.
#:
#: Um `skip` aqui produz suíte verde num host onde NADA visual foi verificado —
#: e foi exatamente assim que a regressão de ícones da a37 atravessou os gates.
#: O marcador `visual` roteia este módulo ao gate canônico, que reprova sem
#: runtime em vez de transformar a ausência em verde.
DIAG_VISUAL_ENVIRONMENT = "QML-VISUAL-ENVIRONMENT-001"
pytestmark = pytest.mark.visual


def _qml_environment() -> dict[str, str]:
    """Keep Qt diagnostics observable even when the host routes them to journald."""
    env = os.environ.copy()
    env.update(
        {
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QT_QPA_PLATFORM": "offscreen",
            "QML_DISABLE_DISK_CACHE": "1",
        }
    )
    return env


@pytest.fixture(autouse=True)
def _require_qml_runtime() -> None:
    """Ambiente sem QML reprova o gate visual com diagnóstico explícito."""
    if QML is None:
        pytest.fail(
            f"{DIAG_VISUAL_ENVIRONMENT}: qml6/qml ausente; o harness visual não pode ser verificado"
        )


# Harnesses que carregam um asset SVG do pacote. A imagem canônica do gate
# declara qt6-svg; a sonda continua sendo uma defesa contra uma imagem publicada
# sem o plugin que o contrato visual exige.
_SVG_HARNESSES = frozenset(
    {
        "check_asset_recipe_preview.qml",
        "check_editorial_library.qml",
        "check_packaged_assets.qml",
        "check_theme_editor_asset_recipes.qml",
    }
)


@functools.lru_cache(maxsize=1)
def _qml_decodes_svg() -> bool:
    """Descobre, executando, se o runtime consegue decodificar SVG."""
    if QML is None:
        return False
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">'
        '<rect width="8" height="8" fill="#22d3ee"/></svg>'
    )
    with tempfile.TemporaryDirectory(prefix="steamzero-svg-probe-") as tmp:
        root = Path(tmp)
        (root / "probe.svg").write_text(svg, encoding="utf-8")
        (root / "probe.qml").write_text(
            "import QtQuick\n"
            "Item {\n"
            "    Image { id: img; source: 'probe.svg' }\n"
            "    Timer {\n"
            "        interval: 200; running: true; repeat: false\n"
            "        onTriggered: Qt.exit(img.status === Image.Ready ? 0 : 3)\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [str(QML), str(root / "probe.qml")],
            capture_output=True,
            text=True,
            env=_qml_environment(),
            timeout=60,
            check=False,
        )
    return completed.returncode == 0


def _assert_qml_clean(
    completed: subprocess.CompletedProcess[str] | _CentralLoadingRun, label: str
) -> None:
    if getattr(completed, "timed_out", False):
        raise AssertionError(
            f"{label} excedeu o prazo do subprocesso QML\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    diagnostics = (
        "Binding loop",
        "Unable to assign",
        "TypeError:",
        "ReferenceError:",
        "Cannot open:",
    )
    assert completed.returncode == 0, (
        f"{label} falhou ({completed.returncode})\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    unexpected = [
        line
        for line in completed.stderr.splitlines()
        if any(marker in line for marker in diagnostics)
    ]
    assert not unexpected, f"{label} publicou diagnósticos QML inesperados:\n" + "\n".join(
        unexpected
    )


def _run_qml(harness: str, *arguments: str, scale_factor: int | None = None) -> None:
    """Executa um harness com os diagnósticos do Qt preservados."""
    env = _qml_environment()
    if scale_factor is not None:
        env["QT_SCALE_FACTOR"] = str(scale_factor)
    completed = subprocess.run(
        [str(QML), f"tests/qml/{harness}", "--", *arguments],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_qml_clean(completed, " ".join((harness, *arguments)))


class _ErrorServerHandler(BaseHTTPRequestHandler):
    """Retorna 200 em /status e 400 com error-v1 em /emulation/action/plan."""

    def do_GET(self) -> None:
        if self.path == "/status":
            self._ok({"status": "ok"})
        else:
            self._error(404, "not found")

    def do_POST(self) -> None:
        if self.path == "/emulation/action/plan":
            self._error(
                400,
                {
                    "error": {
                        "code": "E-TX-001",
                        "operationId": "op-transactional-789",
                        "title": "Falha na aplicação do plano",
                        "what": "Plano de ação conflitou com estado atual do emulador.",
                        "impact": "Nenhuma alteração foi aplicada.",
                        "autoAction": "",
                        "manualAction": "Revise o plano e tente novamente.",
                        "probableCause": (
                            "Um plano mais recente foi aplicado entre a leitura e a confirmação."
                        ),
                    }
                },
            )
        else:
            self._error(404, "not found")

    def _ok(self, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, code: int, body: dict | str) -> None:
        if isinstance(body, dict):
            payload = json.dumps(body).encode("utf-8")
        else:
            payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def _error_server() -> tuple[int, threading.Thread, HTTPServer]:
    host = "127.0.0.1"
    for port in range(42000, 43000):
        try:
            server = HTTPServer((host, port), _ErrorServerHandler)
        except OSError:
            continue
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return port, thread, server
    raise RuntimeError("nenhuma porta livre para o servidor de teste ErrorCard")


# Marcado como visual porque é onde o runtime existe de verdade: o job
# `quality` gastava 76 s tentando provisionar Qt via apt e terminava com
# "qml6 indisponível", então estes harnesses nunca rodaram no CI. A imagem
# canônica do gate visual traz o Qt fixado por digest.
@pytest.mark.visual
@pytest.mark.parametrize(
    "harness",
    [
        "check_handheld_shell.qml",
        "check_main_emulation.qml",
        "check_emulation.qml",
        "check_steam_gameplay_responsive.qml",
        "check_editorial_home.qml",
        "check_editorial_library.qml",
        "check_editorial_canonical_systems.qml",
        "check_media_effect_layer.qml",
        "check_asset_recipe_preview.qml",
        "check_scene_repeater.qml",
        "check_scene_containers.qml",
        # Navegação por controle do AURA Launcher. Capacidade separada da AURA
        # UI: mora em seu próprio diretório e não promove o estado dela.
        "launcher/check_launcher_home.qml",
        "launcher/check_launcher_game_page.qml",
        "launcher/check_launcher_shell.qml",
        "launcher/check_launcher_activation.qml",
        "launcher/check_launcher_accessibility.qml",
        "launcher/check_launcher_covers.qml",
        "launcher/check_launcher_session_osd.qml",
        "launcher/check_launcher_save_state_gallery.qml",
        "launcher/check_launcher_session_peripherals.qml",
        "check_asset_color_transform.qml",
        "check_glass_panel.qml",
        "check_scene_motion.qml",
        "check_scene_surfaces.qml",
        "check_theme_studio_canvas.qml",
        "check_operational_metric_card.qml",
        "check_handheld_layout_focus.qml",
        # UX-03: a superfície lê o contrato de prontidão (estado, medição, causa,
        # próxima ação). A regra de cor vivia inteiramente no QML, e é ali que ela
        # voltaria a morar se alguém reimplementá-la por página.
        "check_readiness_surface.qml",
        # UX-04: armazenamento em unidades compreensíveis. As quatro superfícies
        # executadas lado a lado porque o defeito é justamente a divergência entre
        # elas — o mesmo 1073741824 B lido como GiB, GB e MB conforme a tela.
        "check_storage_units.qml",
        "check_main_handheld_sections.qml",
        "check_credentials.qml",
        "check_credential_dialog_responsive.qml",
        "check_high_contrast.qml",
        # UX-01: a tinta dos avisos sobre superfície fixa é calculada, e o
        # cálculo precisa sobreviver ao tema escuro e ao alto contraste.
        "check_warning_surface_contrast.qml",
        # Prova Image.Ready de cada asset empacotado, não apenas o caminho.
        "check_packaged_assets.qml",
        # Identidade AURA no editor: preview no ThemeBridge, cancelar restaura.
        "check_theme_editor_aura.qml",
        "check_theme_editor_asset_recipes.qml",
        "check_responsive_components.qml",
    ],
)
def test_qml_handheld_harness_offscreen(harness: str) -> None:
    if harness in _SVG_HARNESSES and not _qml_decodes_svg():
        pytest.fail(
            f"{DIAG_VISUAL_ENVIRONMENT}: runtime sem plugin de imagem SVG; "
            f"{harness} carrega asset .svg"
        )
    completed = subprocess.run(
        [str(QML), f"tests/qml/{harness}"],
        cwd=ROOT,
        env=_qml_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_qml_clean(completed, harness)


def test_darkbutton_stays_readable_on_the_light_theme(tmp_path: Path) -> None:
    """P0-1/P0-2 da auditoria: DarkButton legível no tema claro.

    O label segue a paleta do pai (nada de texto claro hardcodado sobre fundo
    claro) e o texto renderiza escuro sobre o fundo claro: o harness salva a
    cena e este teste conta os pixels escuros dentro do retângulo do botão da
    sidebar (x220-420, y100-148 no canvas 640x300).
    """
    output = tmp_path / "darkbutton-theme.png"
    _run_qml("check_darkbutton_theme.qml", f"--capture-output={output}")
    from PIL import Image

    im = Image.open(output).convert("RGB")
    dark = 0
    for y in range(100, 148):
        for x in range(220, 420):
            r, g, b = im.getpixel((x, y))
            if 0.299 * r + 0.587 * g + 0.114 * b < 115:
                dark += 1
    assert dark > 40, (
        f"texto do botão não aparece escuro sobre o fundo claro (pixels escuros: {dark})"
    )


def test_media_effect_layer_refuses_a_surface_without_a_decode_ceiling() -> None:
    """Uma superfície que esquece o teto de decode não carrega.

    O teto é `required` justamente porque o esquecimento seria silencioso: a
    mídia apareceria igual e o custo só surgiria como rolagem travada num
    aparelho que o autor da superfície talvez não tenha. Este teste guarda a
    garantia contra o conserto tentador — devolver um valor padrão à propriedade
    faria o erro de carregamento sumir junto com a proteção.
    """
    qml_directory = ROOT / "src" / "steamzero" / "ui" / "qml"
    with tempfile.TemporaryDirectory(prefix="steamzero-decode-ceiling-") as tmp:
        probe = Path(tmp) / "probe.qml"
        probe.write_text(
            "import QtQuick\n"
            f'import "{qml_directory.as_uri()}"\n'
            "Item {\n"
            '    MediaEffectLayer { source: "cover.png" }\n'
            "    Timer { interval: 50; running: true; onTriggered: Qt.exit(0) }\n"
            "}\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [str(QML), str(probe)],
            cwd=ROOT,
            env=_qml_environment(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert completed.returncode != 0, (
        "MediaEffectLayer aceitou uma superfície sem teto de decode declarado\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert "Required property decodeSize was not initialized" in completed.stderr, (
        "a recusa deve nomear o teto de decode, senão o autor da superfície não "
        f"sabe o que declarar\nstderr:\n{completed.stderr}"
    )


def test_media_effect_layer_composes_with_the_advanced_renderer() -> None:
    """O caminho de produção compõe: Qt >= 6.5 publica a capacidade e o launcher a passa.

    Sem este teste, todo o gate de mídia rodava no caminho degradado. As camadas
    que só existem para alimentar o MultiEffect (textura intermediária e máscara
    gradiente) nunca eram exercitadas com um consumidor real, e um gate delas
    passaria igual estando errado nos dois sentidos.
    """
    _run_qml("check_media_effect_layer.qml", "--steamzero-qtquick-effects")


def test_editorial_library_renders_at_logical_scale_200() -> None:
    """A composição editorial continua utilizável em 4K físico a 200% lógico."""
    _run_qml("check_editorial_library.qml", scale_factor=2)


@pytest.mark.parametrize(
    ("arguments", "label"),
    [
        (("--system-count=37",), "37 sistemas em 1280x800"),
        (
            (
                "--system-count=37",
                "--long-system-status",
                "--capture-width=800",
                "--capture-height=1280",
                "--capture-high-contrast",
                "--geometry-only",
            ),
            "37 sistemas com rótulo longo em 800x1280 e alto contraste",
        ),
    ],
)
def test_editorial_system_cards_keep_the_minimum_geometry(
    arguments: tuple[str, ...], label: str
) -> None:
    """G36 — a grade dá a todos os cards, inclusive o último, a altura contratada."""
    _run_qml("check_editorial_library.qml", *arguments)


@pytest.mark.parametrize("stage", ("systems", "system", "library", "dossier", "launch"))
def test_editorial_capture_requested_stage_is_independent(tmp_path: Path, stage: str) -> None:
    """Cada etapa editorial captura o frame pedido sem depender do timer da jornada."""
    output = tmp_path / f"editorial-{stage}.png"
    _run_qml(
        "check_editorial_library.qml",
        f"--capture-stage={stage}",
        f"--capture-output={output}",
    )
    assert output.is_file() and output.stat().st_size > 0


def test_qml_emulation_error_card_via_transactional_failure(
    _error_server: tuple[int, threading.Thread, HTTPServer],
) -> None:
    port, _thread, _server = _error_server
    completed = subprocess.run(
        [
            str(QML),
            "tests/qml/check_emulation_error_active_errors.qml",
            "--steamzero-api",
            f"http://127.0.0.1:{port}",
            "--steamzero-token",
            "test",
        ],
        cwd=ROOT,
        env=_qml_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_qml_clean(completed, "Harness ErrorCard transacional")


@pytest.mark.visual
def test_scene_text_renders_what_the_adapter_emits() -> None:
    """VS-02 — o Qt precisa ACEITAR o payload do adapter, não só recebê-lo.

    Os testes em Python provam o mapeamento. Nenhum deles prova que
    `Text["AlignHCenter"]` resolve para o enum do Qt, que `font.weight: 600` é
    aceito, ou que `#80112233` não vira "Invalid property assignment" — o mesmo
    erro que já derrubou `rgba(212,84,84,0.08)` neste repositório.

    Ambiente sem Qt reprova explicitamente. Verde só existe quando alguém de fato
    renderizou.
    """
    if QML is None:
        pytest.fail(
            f"{DIAG_VISUAL_ENVIRONMENT}: qml6 ausente. O contrato entre o adapter "
            "e SceneText.qml não pode ser verificado sem runtime QML, e declarar "
            "verde sem verificar é o que deixou a regressão de ícones passar."
        )
    completed = subprocess.run(
        [str(QML), "tests/qml/check_scene_text.qml"],
        cwd=ROOT,
        env=_qml_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_qml_clean(completed, "check_scene_text.qml")


@pytest.mark.visual
def test_controls_profile_card_never_shows_green_without_proof() -> None:
    """G45 — a tela precisa separar perfil salvo, traduzido e valendo.

    O perfil de controle era resolvido, gravado e desenhado por ninguém, então
    o usuário não tinha como distinguir "escolhi um perfil" de "o perfil vale no
    emulador". O harness percorre os oito estados publicados e cobra a regra que
    importa: só `applied` pode ficar verde. `pending-write` tem todos os bindings
    resolvidos e mesmo assim não é pronto — o arquivo ainda não existe.

    Sem `skip`: um verde num host onde nada foi renderizado é exatamente como a
    regressão de ícones da a37 atravessou os gates (G13).
    """
    if QML is None:
        pytest.fail(
            f"{DIAG_VISUAL_ENVIRONMENT}: qml6 ausente. Os estados do cartão de "
            "perfil de controle não podem ser verificados sem runtime QML, e "
            "declarar verde sem renderizar é o defeito que a G45 registra."
        )
    completed = subprocess.run(
        [str(QML), "tests/qml/check_controls_profile_card.qml"],
        cwd=ROOT,
        env=_qml_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_qml_clean(completed, "check_controls_profile_card.qml")


def _central_loading_status() -> dict[str, object]:
    """Um /status mínimo, mas com a forma que o `Main.qml` consome.

    Não é o payload do produto: é a menor leitura que ainda exercita os bindings
    reais. Se uma chave obrigatória faltar, o Qt reclama em stderr e
    `_assert_qml_clean` reprova — que é exatamente o contrato que a RC-01 abriu.
    """
    return {
        "truthState": "stale",
        "desiredProfile": "handheld-desktop",
        "appliedProfile": None,
        "observedProfile": None,
        "effectiveProfile": "handheld-desktop",
        "recommendedProfile": "handheld-desktop",
        "statusReasons": ["A leitura da cena encontrou perfil desejado não aplicado."],
        "recoveryRequired": False,
        "independentRuntime": True,
        "observation": {
            "checkedEffects": [],
            "unavailableEffects": [],
            "ambiguousCandidates": [],
            "errors": [],
        },
        "context": {
            "deviceKind": "deck-lcd",
            "displays": [],
            "capabilities": [],
            "conflicts": [],
        },
        "dashboard": {
            "accessibility": {"reducedMotion": False, "highContrast": False},
            "components": [
                {
                    "id": "dolphin",
                    "name": "Dolphin",
                    "description": "Emulador de Wii e GameCube",
                    "iconName": "dolphin-emu",
                    "systems": ["Wii", "GameCube"],
                    "state": "installed",
                    "statusLabel": "Instalado",
                    "versionLabel": "2407",
                    "targetVersion": "2407",
                    "detail": "Dolphin 2407 medido pela ponte.",
                    "blockedReason": "",
                    "action": {
                        "kind": "detail",
                        "label": "Detalhes",
                        "enabled": False,
                    },
                }
            ],
            "steam": [],
            "sync": {
                "pending": 0,
                "conflicted": 0,
                "done": 0,
                "items": [],
                "dependency": "Cena RC-01; nenhuma mutação exposta.",
            },
            "doctor": {"state": "healthy", "checks": []},
            "playtime": {"schemaVersion": 1, "totalPlayedSeconds": 0, "games": []},
            "collections": {"schemaVersion": 1, "favorites": [], "tags": [], "collections": []},
            "libraryHealth": {
                "schemaVersion": 1,
                "state": "unchecked",
                "counts": {
                    "verified": 0,
                    "suspect": 0,
                    "missing": 0,
                    "error": 0,
                    "unavailable": 0,
                    "unchecked": 0,
                },
            },
            "emulation": {
                "schemaVersion": 1,
                "truthState": "ready",
                "contextLabel": "Cena RC-01",
                "platforms": [],
                "jobs": [],
            },
            "steamGameplay": {"schemaVersion": 1, "games": [], "environment": []},
            "uiContracts": {"schemaVersion": 1, "states": [], "actions": [], "byId": {}},
        },
    }


_CENTRAL_LOADING_BARRIER_SECONDS = 10.0


@dataclass
class _CentralLoadingTrace:
    """Per-server request timeline; payloads and authorization values are omitted."""

    instance_id: str
    port: int
    hold_first_response: bool
    lock: threading.Lock
    release_first_response: threading.Event
    first_response_waiting: threading.Event
    events: list[dict[str, object]]
    request_sequence: int = 0
    status_sequence: int = 0
    barrier_release_source: str | None = None
    barrier_release_monotonic_ns: int | None = None

    def begin(self, method: str, path: str, peer: str) -> dict[str, object]:
        with self.lock:
            self.request_sequence += 1
            status_sequence: int | None = None
            if method == "GET" and path == "/status":
                self.status_sequence += 1
                status_sequence = self.status_sequence
            event: dict[str, object] = {
                "instanceId": self.instance_id,
                "port": self.port,
                "requestSequence": self.request_sequence,
                "statusSequence": status_sequence,
                "peer": peer,
                "method": method,
                "path": path,
                "receiptMonotonicNs": time.monotonic_ns(),
                "responseStatus": None,
                "responseStartMonotonicNs": None,
                "responseEndMonotonicNs": None,
                "barrierWaitStartMonotonicNs": None,
                "barrierReleaseMonotonicNs": None,
                "barrierReleaseSource": None,
                "barrierOutcome": "not-applicable",
                "transportErrorMonotonicNs": None,
                "transportError": None,
            }
            self.events.append(event)
            return event

    def release_barrier(self, source: str) -> None:
        with self.lock:
            if self.barrier_release_source is None:
                self.barrier_release_source = source
                self.barrier_release_monotonic_ns = time.monotonic_ns()
                self.release_first_response.set()

    def mark_barrier(self, event: dict[str, object], released: bool) -> None:
        with self.lock:
            event["barrierOutcome"] = "released" if released else "deadline-exceeded"
            event["barrierReleaseSource"] = self.barrier_release_source if released else None
            event["barrierReleaseMonotonicNs"] = (
                self.barrier_release_monotonic_ns if released else time.monotonic_ns()
            )

    def response_started(self, event: dict[str, object], status: int) -> None:
        with self.lock:
            event["responseStatus"] = status
            event["responseStartMonotonicNs"] = time.monotonic_ns()

    def response_finished(self, event: dict[str, object], error: OSError | None) -> None:
        with self.lock:
            event["responseEndMonotonicNs"] = time.monotonic_ns()
            if error is not None:
                event["transportErrorMonotonicNs"] = time.monotonic_ns()
                event["transportError"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }

    def snapshot(self) -> list[dict[str, object]]:
        with self.lock:
            return [dict(event) for event in self.events]

    @property
    def status_count(self) -> int:
        with self.lock:
            return self.status_sequence


class _OwnedThreadingHTTPServer(ThreadingHTTPServer):
    """Threading bridge that owns and joins every request-handler thread."""

    daemon_threads = False
    block_on_close = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler]):
        self._active_handler_lock = threading.Lock()
        self._active_handlers: set[threading.Thread] = set()
        super().__init__(server_address, handler)

    def process_request_thread(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        thread = threading.current_thread()
        with self._active_handler_lock:
            self._active_handlers.add(thread)
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._active_handler_lock:
                self._active_handlers.discard(thread)

    @property
    def active_handler_count(self) -> int:
        with self._active_handler_lock:
            return len(self._active_handlers)


class _CentralLoadingHandler(BaseHTTPRequestHandler):
    """Controlled RC-01 bridge with per-instance accounting and timed responses."""

    def _trace(self) -> _CentralLoadingTrace:
        return self.server.central_loading_trace  # type: ignore[attr-defined, no-any-return]

    def do_GET(self) -> None:
        path = self.path.split("?", maxsplit=1)[0]
        trace = self._trace()
        event = trace.begin(
            self.command, path, f"{self.client_address[0]}:{self.client_address[1]}"
        )

        if path == "/_test/ready":
            self._send(204, "", event)
            return
        if path == "/_test/release-first":
            trace.release_barrier("qml-harness")
            self._send(204, "", event)
            return
        if path != "/status":
            self._send(404, "rota fora da cena", event)
            return

        status_sequence = int(event["statusSequence"])
        if status_sequence == 1 and trace.hold_first_response:
            with trace.lock:
                event["barrierWaitStartMonotonicNs"] = time.monotonic_ns()
            trace.first_response_waiting.set()
            released = trace.release_first_response.wait(_CENTRAL_LOADING_BARRIER_SECONDS)
            trace.mark_barrier(event, released)
            if not released:
                self._send(504, "barreira de status inicial excedeu o prazo", event)
                return

        if status_sequence == 2:
            self._send(
                500,
                json.dumps(
                    {
                        "error": {
                            "code": "E-STATUS-SCENE",
                            "title": "A renovação do estado falhou",
                            "detail": "A central não pôde reler o host nesta tentativa.",
                            "what": "Leitura GET /status recusou.",
                            "impact": "O último estado lido permanece na tela.",
                            "autoAction": "",
                            "manualAction": "Tente novamente.",
                            "probableCause": "Cena controlada pelo teste.",
                            "operationId": "",
                        }
                    }
                ),
                event,
            )
            return
        self._send(200, json.dumps(_central_loading_status()), event)

    def _send(self, code: int, body: str, event: dict[str, object]) -> None:
        payload = body.encode("utf-8")
        trace = self._trace()
        trace.response_started(event, code)
        error: OSError | None = None
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
        except OSError as exc:
            error = exc
        finally:
            trace.response_finished(event, error)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


@dataclass
class _CentralLoadingBridge:
    server: _OwnedThreadingHTTPServer
    thread: threading.Thread
    trace: _CentralLoadingTrace
    port: int
    closed: bool = False

    def __enter__(self) -> _CentralLoadingBridge:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        # A timed-out/failing QML process must not strand a handler on its gate.
        self.trace.release_barrier("bridge-close")
        try:
            try:
                self.server.shutdown()
            finally:
                self.server.server_close()
        finally:
            self.thread.join(timeout=5.0)
            self.closed = not self.thread.is_alive() and self.server.fileno() == -1
        if self.thread.is_alive():
            raise AssertionError(f"ponte {self.trace.instance_id} deixou serve_forever vivo")
        if self.server.active_handler_count:
            raise AssertionError(
                f"ponte {self.trace.instance_id} deixou "
                f"{self.server.active_handler_count} handler(s) vivo(s)"
            )
        if self.server.fileno() != -1:
            raise AssertionError(f"socket da ponte {self.trace.instance_id} não foi fechado")


def _central_loading_http_get(bridge: _CentralLoadingBridge, path: str) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", bridge.port, timeout=5.0)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def _start_central_loading_bridge(*, hold_first_response: bool = True) -> _CentralLoadingBridge:
    host = "127.0.0.1"
    instance_id = uuid.uuid4().hex[:12]
    server = _OwnedThreadingHTTPServer((host, 0), _CentralLoadingHandler)
    port = int(server.server_address[1])
    trace = _CentralLoadingTrace(
        instance_id=instance_id,
        port=port,
        hold_first_response=hold_first_response,
        lock=threading.Lock(),
        release_first_response=threading.Event(),
        first_response_waiting=threading.Event(),
        events=[],
    )
    if not hold_first_response:
        trace.release_barrier("test-no-barrier")
    server.central_loading_trace = trace  # type: ignore[attr-defined]
    thread = threading.Thread(
        target=server.serve_forever,
        name=f"steamzero-central-loading-{instance_id}",
        daemon=False,
    )
    try:
        thread.start()
    except BaseException:
        server.server_close()
        raise
    bridge = _CentralLoadingBridge(server=server, thread=thread, trace=trace, port=port)
    try:
        ready_status = _central_loading_http_get(bridge, "/_test/ready")
        if ready_status != 204:
            raise RuntimeError(f"ponte {instance_id} respondeu readiness HTTP {ready_status}")
    except BaseException:
        bridge.close()
        raise
    return bridge


def _central_loading_qml_trace(
    completed: _CentralLoadingRun,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    parse_errors: list[dict[str, object]] = []
    marker = "CENTRAL-TRACE "
    for stream_name, stream in (("stdout", completed.stdout), ("stderr", completed.stderr)):
        for line_number, line in enumerate(stream.splitlines(), start=1):
            if marker not in line:
                continue
            raw_event = line.split(marker, maxsplit=1)[1]
            try:
                event = json.loads(raw_event)
            except json.JSONDecodeError as exc:
                parse_errors.append(
                    {
                        "stream": stream_name,
                        "line": line_number,
                        "error": str(exc),
                        "raw": raw_event,
                    }
                )
                continue
            if not isinstance(event, dict):
                parse_errors.append(
                    {
                        "stream": stream_name,
                        "line": line_number,
                        "error": "QML trace event is not a JSON object",
                        "raw": raw_event,
                    }
                )
                continue
            events.append({"stream": stream_name, "line": line_number, **event})
    return events, parse_errors


def _assert_central_loading_run(
    bridge: _CentralLoadingBridge,
    completed: _CentralLoadingRun,
    *,
    expected_status_reads: int,
    label: str,
) -> None:
    failures: list[str] = []
    # Always validate the child process first; retain its complete output if any
    # later bridge assertion also fails.
    try:
        _assert_qml_clean(completed, label)
    except AssertionError as exc:
        failures.append(f"QML: {exc}")

    events = bridge.trace.snapshot()
    status_events = [
        event for event in events if event["method"] == "GET" and event["path"] == "/status"
    ]
    if len(status_events) != expected_status_reads:
        failures.append(
            f"a ponte {bridge.trace.instance_id} esperava {expected_status_reads} GET /status, "
            f"recebeu {len(status_events)}"
        )
    transport_errors = [event for event in events if event["transportError"] is not None]
    if transport_errors:
        failures.append(f"respostas HTTP com erro de transporte: {transport_errors!r}")
    qml_trace, qml_trace_parse_errors = _central_loading_qml_trace(completed)
    logical_attempts = [
        int(event["statusAttempt"])
        for event in qml_trace
        if isinstance(event.get("statusAttempt"), int)
    ]
    diagnostic = {
        "bridgeInstance": bridge.trace.instance_id,
        "port": bridge.port,
        "closed": bridge.closed,
        "serveThreadAlive": bridge.thread.is_alive(),
        "activeHandlers": bridge.server.active_handler_count,
        "listeningSocketFd": bridge.server.fileno(),
        "expectedStatusReads": expected_status_reads,
        "actualStatusReads": len(status_events),
        "statusEvents": status_events,
        "allHttpEvents": events,
        "qmlTraceEvents": qml_trace,
        "qmlTraceParseErrors": qml_trace_parse_errors,
        "qmlLogicalAttemptMax": max(logical_attempts, default=0),
        "qmlReturnCode": completed.returncode,
        "qmlTimedOut": completed.timed_out,
        "qmlStdout": completed.stdout,
        "qmlStderr": completed.stderr,
    }
    assert not failures, "\n".join(
        [
            *failures,
            "central-loading diagnostic:",
            json.dumps(diagnostic, ensure_ascii=False, indent=2),
        ]
    )


@pytest.mark.visual
def test_central_loading_bridges_isolate_sequences_and_close_owned_resources() -> None:
    with ExitStack() as stack:
        bridge_a = stack.enter_context(_start_central_loading_bridge(hold_first_response=False))
        bridge_b = stack.enter_context(_start_central_loading_bridge(hold_first_response=False))
        a_first = _central_loading_http_get(bridge_a, "/status")
        b_first = _central_loading_http_get(bridge_b, "/status")
        a_second = _central_loading_http_get(bridge_a, "/status")
        b_count_after_a = bridge_b.trace.status_count
        b_second = _central_loading_http_get(bridge_b, "/status")

    a_status_events = [event for event in bridge_a.trace.snapshot() if event["path"] == "/status"]
    b_status_events = [event for event in bridge_b.trace.snapshot() if event["path"] == "/status"]
    assert (a_first, b_first, a_second, b_second) == (200, 200, 500, 500)
    assert b_count_after_a == 1, "uma leitura no servidor A renumerou o servidor B"
    assert [event["statusSequence"] for event in a_status_events] == [1, 2]
    assert [event["statusSequence"] for event in b_status_events] == [1, 2]
    assert bridge_a.trace.instance_id != bridge_b.trace.instance_id
    assert bridge_a.port != bridge_b.port
    assert bridge_a.closed and bridge_b.closed
    assert not bridge_a.thread.is_alive() and not bridge_b.thread.is_alive()
    assert bridge_a.server.active_handler_count == bridge_b.server.active_handler_count == 0
    assert bridge_a.server.fileno() == bridge_b.server.fileno() == -1


@pytest.mark.visual
@pytest.mark.parametrize("exit_mode", ("failure", "timeout"))
def test_central_loading_bridge_closes_held_request_after_failure_or_timeout(
    monkeypatch: pytest.MonkeyPatch, exit_mode: str
) -> None:
    bridge = _start_central_loading_bridge()
    response_statuses: list[int] = []
    request_errors: list[Exception] = []

    def held_status_request() -> None:
        try:
            response_statuses.append(_central_loading_http_get(bridge, "/status"))
        except Exception as exc:  # Preserve worker failures for the assertion.
            request_errors.append(exc)

    client_thread = threading.Thread(
        target=held_status_request,
        name=f"steamzero-central-loading-client-{bridge.trace.instance_id}",
        daemon=False,
    )

    def enter_scenario() -> None:
        client_thread.start()
        assert bridge.trace.first_response_waiting.wait(timeout=5.0), (
            f"ponte {bridge.trace.instance_id} não observou a primeira resposta bloqueada"
        )

    if exit_mode == "failure":
        with bridge, pytest.raises(RuntimeError, match="falha controlada do harness"):
            enter_scenario()
            raise RuntimeError("falha controlada do harness")
    else:
        with bridge:
            enter_scenario()

            def timeout_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
                raise subprocess.TimeoutExpired(
                    "qml6",
                    timeout=30,
                    output=(
                        b'CENTRAL-TRACE {"sequence":42,"event":"simulated",'
                        b'"statusAttempt":5}\ntrace QML parcial'
                    ),
                    stderr=b"aviso QML parcial",
                )

            monkeypatch.setattr(subprocess, "run", timeout_run)
            completed = _run_central_loading_harness(bridge)
            assert completed.timed_out is True
            assert "trace QML parcial" in completed.stdout
            assert "aviso QML parcial" in completed.stderr
            with pytest.raises(AssertionError) as failure:
                _assert_central_loading_run(
                    bridge,
                    completed,
                    expected_status_reads=1,
                    label="timeout injetado",
                )
            assert "trace QML parcial" in str(failure.value)
            assert "aviso QML parcial" in str(failure.value)
            assert '"qmlLogicalAttemptMax": 5' in str(failure.value)

    client_thread.join(timeout=5.0)
    assert not client_thread.is_alive(), "o cliente do pedido bloqueado não foi encerrado"
    assert not request_errors, f"o cliente do pedido bloqueado falhou: {request_errors!r}"
    assert response_statuses == [200]
    assert bridge.closed
    assert not bridge.thread.is_alive()
    assert bridge.server.active_handler_count == 0
    assert bridge.server.fileno() == -1
    first_status = next(
        event
        for event in bridge.trace.snapshot()
        if event["method"] == "GET" and event["path"] == "/status"
    )
    assert first_status["barrierReleaseSource"] == "bridge-close"
    assert first_status["transportError"] is None


@pytest.mark.visual
def test_central_loading_phases_are_observable_offscreen() -> None:
    """RC-01 (UX-02) — a Central tem de ser legível enquanto carrega.

    O `/status` do host real leva segundos; durante esse intervalo a Home
    publicava os fallbacks como se fossem medições ("Não instalado", "Nenhum
    jogo publicado ainda", "Nenhuma pendência" em verde). Este teste roda o
    `Main.qml` contra uma ponte que demora, falha e recupera, e cobra as quatro
    fases no objeto vivo.

    Sem runtime QML o teste reprova: verde sem renderização é o modo como a
    regressão de ícones já atravessou os gates (G13).
    """
    if QML is None:
        pytest.fail(
            f"{DIAG_VISUAL_ENVIRONMENT}: qml6 ausente. As fases de carregamento "
            "da Central não podem ser verificadas sem runtime QML, e declarar "
            "verde sem renderizar é o defeito que a RC-01 combate."
        )
    bridge = _start_central_loading_bridge()
    with bridge:
        completed = _run_central_loading_harness(bridge)
    # Inicial, renovação recusada, retry, leitura durante a sondagem e drenagem
    # da única relênia coerçada. O helper reúne essa contagem com o veredito e a
    # saída integral do processo QML antes de reprovar qualquer divergência.
    _assert_central_loading_run(
        bridge,
        completed,
        expected_status_reads=5,
        label="ponte de cena da RC-01",
    )


def _run_central_loading_harness(bridge: _CentralLoadingBridge, *extra: str) -> _CentralLoadingRun:
    """Roda o harness da RC-01 contra a ponte de cena na porta dada.

    O `--` é obrigatório: sem ele o `qml6` trata cada argumento como outro
    arquivo de componente e gasta um load falho por parâmetro.
    """
    command = [
        str(QML),
        "tests/qml/check_central_loading.qml",
        "--",
        "--steamzero-api",
        f"http://127.0.0.1:{bridge.port}",
        "--steamzero-token",
        "cena-rc01",
        *extra,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=_qml_environment(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else exc.stdout or ""
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else exc.stderr or ""
        )
        return _CentralLoadingRun(
            returncode=124,
            stdout=stdout,
            stderr=f"qml6 timeout after 30 seconds\n{stderr}",
            timed_out=True,
        )
    return _CentralLoadingRun(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


@pytest.mark.visual
@pytest.mark.parametrize("phase", ("loading", "stale", "ready"))
def test_central_loading_frames_are_capturable(tmp_path: Path, phase: str) -> None:
    """RC-01 — o quadro que as asserções descrevem pode virar evidência.

    A fase aferida tem de ser gravável sem depender de timing humano: a
    capturing é pedida ao harness, que só sai depois de o frame compor. Um PNG
    em branco passaria por evidência, então a cena real também é medida.
    """
    if QML is None:
        pytest.fail(f"{DIAG_VISUAL_ENVIRONMENT}: qml6 ausente; nenhum frame é gravável")
    output = tmp_path / f"central-{phase}.png"
    bridge = _start_central_loading_bridge()
    with bridge:
        completed = _run_central_loading_harness(
            bridge,
            f"--capture-phase={phase}",
            f"--capture-output={output}",
        )
    _assert_central_loading_run(
        bridge,
        completed,
        expected_status_reads=5,
        label=f"captura {phase} da Central",
    )
    assert output.is_file() and output.stat().st_size > 0, (
        f"harness pediu o quadro `{phase}` e nenhuma imagem foi gravada em {output}"
    )
    from PIL import Image

    image = Image.open(output)
    image.load()
    assert image.width >= 1280 and image.height >= 800, (
        f"o quadro `{phase}` saiu com {image.width}x{image.height}, menor que a janela"
    )
    # Um frame ainda não composto seria uma superfície vazia de uma cor só.
    colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
    distinct = len(colors) if colors is not None else 1_000_000
    assert distinct > 8, f"o quadro `{phase}` tem {distinct} cores: não mostra a cena aferida"


#: Cena RC-01 (UX-02, governança de estado): a re-consulta provocada por uma
#: mutação não pode ser descartada porque existe uma leitura antiga no ar.
_STATUS_REFRESH_LOCK = threading.Lock()
_STATUS_REFRESH_CALLS: list[str] = []
_STATUS_REFRESH_MUTATION_SEEN = threading.Event()
#: Registrado pela ponte: se a mutação chegou enquanto a leitura #2 estava aberta.
_STATUS_REFRESH_OVERLAP: list[bool] = []

#: Gerações que a ponte publica. A tela tem de terminar na pós-mutação.
_STATUS_GENERATION_BEFORE = "2407"
_STATUS_GENERATION_AFTER = "2412"

#: Quantos centésimos cada leitura segura a resposta, e qual delas a ponte recusa.
_STATUS_REFRESH_SCENES: dict[str, dict[str, object]] = {
    "success": {"fail_on_read": None, "read_seconds": {1: 0.25, 2: 0.15, 3: 0.15}},
    "in-flight-fails": {"fail_on_read": 2, "read_seconds": {1: 0.25, 2: 0.15, 3: 0.4}},
    "refresh-fails": {"fail_on_read": 3, "read_seconds": {1: 0.25, 2: 0.15, 3: 0.15}},
}


def _status_refresh_payload(generation: str) -> dict[str, object]:
    """/status da cena: a forma real do produto, com contratos publicados.

    Os contratos vêm de `handheld_ui_contracts()`, o mesmo catálogo que a ponte do
    host serve. Sem eles o `requestAction` recusaria a mutação com "a bridge não
    publicou o contrato", e o teste exercitaria uma cena que não existe.
    """
    status = _central_loading_status()
    dashboard = dict(status["dashboard"])  # type: ignore[index]
    row = dict(dashboard["components"][0])  # type: ignore[index]
    row["versionLabel"] = generation
    row["targetVersion"] = generation
    row["detail"] = f"Dolphin {generation} medido pela ponte."
    dashboard["components"] = [row]
    dashboard["uiContracts"] = handheld_ui_contracts()
    status["dashboard"] = dashboard
    return status


def _status_refresh_error(code: str) -> str:
    return json.dumps(
        {
            "error": {
                "code": code,
                "title": "A renovação do estado falhou",
                "detail": "A central não pôde reler o host nesta tentativa.",
                "what": "Leitura GET /status recusada pela cena.",
                "impact": "O último estado lido permanece na tela.",
                "autoAction": "",
                "manualAction": "Tente novamente.",
                "probableCause": "Cena controlada pelo teste.",
                "operationId": "",
            }
        }
    )


_STATUS_REFRESH_SCENE: dict[str, object] = {
    "name": "success",
    "fail_on_read": None,
    "read_seconds": {1: 0.25, 2: 0.15, 3: 0.15},
}


class _StatusRefreshHandler(BaseHTTPRequestHandler):
    """Ponte que abre uma leitura, segura-a até a mutação acontecer e responde.

    A sobreposição não é pedida por aposta de timing: a leitura #2 dorme o mínimo e
    depois espera o evento que a mutação levanta. Se a mutação não chegar em 5 s, a
    ponte responde mesmo assim e a asserção de sequência reprova a cena.
    """

    def do_GET(self) -> None:
        if self.path.split("?")[0] != "/status":
            self._send(404, "rota fora da cena")
            return
        with _STATUS_REFRESH_LOCK:
            reads = 1 + sum(1 for call in _STATUS_REFRESH_CALLS if call.startswith("GET "))
            _STATUS_REFRESH_CALLS.append(f"GET /status#{reads}")
            scene = dict(_STATUS_REFRESH_SCENE)
        seconds = float(scene["read_seconds"][reads])  # type: ignore[index]
        time.sleep(seconds)
        if reads == 2:
            _STATUS_REFRESH_OVERLAP.append(_STATUS_REFRESH_MUTATION_SEEN.wait(timeout=5.0))
        # O marcador é escrito antes de qualquer resposta: ele diz que a leitura em
        # andamento fechou, e uma recusa fecha tanto quanto um 200.
        with _STATUS_REFRESH_LOCK:
            _STATUS_REFRESH_CALLS.append(f"answered#{reads}")
        if scene["fail_on_read"] == reads:
            self._send(500, _status_refresh_error("E-STATUS-SCENE"))
            return
        generation = _STATUS_GENERATION_AFTER if reads >= 3 else _STATUS_GENERATION_BEFORE
        self._send(200, json.dumps(_status_refresh_payload(generation)))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        route = self.path.split("?")[0]
        if route != "/emulation/library/scan":
            self._send(404, "rota fora da cena")
            return
        with _STATUS_REFRESH_LOCK:
            _STATUS_REFRESH_CALLS.append(f"POST {route}")
        self._send(200, json.dumps({"games": 7}))
        _STATUS_REFRESH_MUTATION_SEEN.set()

    def _send(self, code: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def _start_status_refresh_bridge(scene: str) -> int:
    """Sobe a ponte da cena de re-consulta e zera o estado compartilhado."""
    config = _STATUS_REFRESH_SCENES[scene]
    with _STATUS_REFRESH_LOCK:
        del _STATUS_REFRESH_CALLS[:]
        del _STATUS_REFRESH_OVERLAP[:]
    _STATUS_REFRESH_SCENE.update(
        {
            "name": scene,
            "fail_on_read": config["fail_on_read"],
            "read_seconds": config["read_seconds"],
        }
    )
    _STATUS_REFRESH_MUTATION_SEEN.clear()
    host = "127.0.0.1"
    for port in range(44000, 45000):
        try:
            # ThreadingHTTPServer: a cena exige que a leitura #2 fique aberta
            # enquanto o POST é servido. Um servidor serializado mataria a
            # sobreposição que se quer reproduzir.
            server = ThreadingHTTPServer((host, port), _StatusRefreshHandler)
        except OSError:
            continue
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return port
    raise RuntimeError("nenhuma porta livre para a ponte de re-consulta da RC-01")


def _run_status_refresh_harness(port: int, scene: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(QML),
            "tests/qml/check_status_refresh_coalesced.qml",
            "--",
            "--steamzero-api",
            f"http://127.0.0.1:{port}",
            "--steamzero-token",
            "cena-rc01",
            f"--scene={scene}",
        ],
        cwd=ROOT,
        env=_qml_environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


#: A única sequência que prova o contrato: uma leitura nova depois que a antiga
#: resolveu, disparada pela mutação que aconteceu *com* a antiga no ar.
_STATUS_REFRESH_EXPECTED = [
    "GET /status#1",
    "answered#1",
    "GET /status#2",
    "POST /emulation/library/scan",
    "answered#2",
    "GET /status#3",
    "answered#3",
]


@pytest.mark.visual
@pytest.mark.parametrize("scene", ("success", "in-flight-fails", "refresh-fails"))
def test_a_mutation_refresh_is_not_discarded_by_an_in_flight_read(scene: str) -> None:
    """RC-01 — mutação confirmada tem de terminar em leitura do estado pós-mutação.

    Reproduz o defeito apontado na revisão de 2026-09-26: com `statusInFlight`
    verdadeiro, `refreshStatus()` descarta a re-consulta. A leitura antiga chega
    depois, regrava o estado pré-mutação e nenhuma nova consulta sai — a tela
    afirma "Biblioteca atualizada" mostrando os dados de antes. Os três ramos
    cobrem a consulta em andamento dando certo (success) e dando errado
    (in-flight-fails), mais a re-consulta coerçada falhando (refresh-fails).
    """
    port = _start_status_refresh_bridge(scene)
    completed = _run_status_refresh_harness(port, scene)
    with _STATUS_REFRESH_LOCK:
        calls = list(_STATUS_REFRESH_CALLS)
    # A cena só vale se a sobreposição aconteceu de verdade: sem isso, um verde
    # poderia vir de uma cena em que a leitura #2 já tinha respondido.
    assert _STATUS_REFRESH_OVERLAP == [True], (
        f"a ponte não segurou a leitura #2 aberta até a mutação: {calls}"
    )
    assert calls == _STATUS_REFRESH_EXPECTED, (
        f"cena {scene} produziu outra sequência de requisições:\n"
        + "\n".join(calls)
        + "\nesperado:\n"
        + "\n".join(_STATUS_REFRESH_EXPECTED)
    )
    # O `console.log` do Qt sai pelo stderr — exigir stdout produziria um gate que
    # nunca vê o denominador.
    published = completed.stdout + completed.stderr
    assert f"verificações da cena {scene}" in published, (
        f"o harness não publicou seu denominador de verificações:\n{published}"
    )
    summary = [line for line in published.splitlines() if f"verificações da cena {scene}" in line]
    assert len(summary) == 1 and ", 0 falhas" in summary[0], (
        f"o harness não publicou um denominador legível: {summary}"
    )
    assert "FAIL:" not in published, f"cena {scene} publicou falhas de contrato:\n{published}"
    _assert_qml_clean(completed, f"cena de re-consulta {scene}")

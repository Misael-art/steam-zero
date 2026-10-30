# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Lançamento de jogo e retorno ao contexto, no AURA Launcher.

Dois requisitos da Definition of Done moldam este módulo:

* o jogo continua rodando se o launcher reiniciar (item 5) — por isso o
  processo nasce em sessão própria, e não como filho preso ao launcher;
* o retorno recai no mesmo contexto (item 4) — por isso o contexto vai para
  disco **antes** do processo existir.

A ordem importa: gravar depois do spawn abriria uma janela em que o jogo já
roda e o lugar do usuário ainda não foi salvo. Se o launcher morresse ali, a
volta cairia na home genérica.

O argv é uma sequência já separada. String de shell não é aceita: montar
comando por concatenação é como um caminho de jogo com aspas vira execução de
outra coisa.

Nada aqui toca o sistema diretamente: a escrita passa por ``core.fs`` e quem
cria o processo é injetado por quem chama, porque `subprocess` pertence aos
adapters. A primeira versão deste módulo fazia as duas coisas à mão e o gate de
fronteiras a recusou — com razão, porque a gravação atômica já existia pronta.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steamzero.core import fs, ids
from steamzero.core.errors import SteamZeroError
from steamzero.launcher.identifiers import is_focus_id, is_identifier

DIAG_CONTEXT_LOST = "LAUNCHER-CONTEXT-LOST-001"
MAX_ARGV = 64
CONTEXT_OWNER = "steamzero-launcher-context"
MAX_CONTEXT_BYTES = 65536
_UNSAFE_ARGUMENT = re.compile(r"[;&|`$\n\r]")

Spawn = Callable[[tuple[str, ...]], int]


@dataclass(frozen=True)
class LaunchPlan:
    game_id: str
    argv: Sequence[str]
    focus_id: str
    context_path: Path
    launch_request_id: str | None = None

    def __post_init__(self) -> None:
        if not is_identifier(self.game_id):
            raise ValueError(f"game id inválido: {self.game_id!r}")
        if not is_focus_id(self.focus_id):
            raise ValueError(f"focus id inválido: {self.focus_id!r}")
        if self.launch_request_id is not None and not ids.is_ulid(self.launch_request_id):
            raise ValueError("launch request id inválido")
        if isinstance(self.argv, str) or not isinstance(self.argv, tuple | list):
            raise ValueError("argv precisa ser sequência já separada, não string de shell")
        if not self.argv or len(self.argv) > MAX_ARGV:
            raise ValueError(f"argv precisa ter 1..{MAX_ARGV} elementos")
        for item in self.argv:
            if not isinstance(item, str) or not item:
                raise ValueError("argv aceita somente strings não vazias")
            if _UNSAFE_ARGUMENT.search(item):
                raise ValueError(f"argumento com metacaractere de shell: {item!r}")
        if ".." in Path(self.argv[0]).parts:
            raise ValueError("executável com travessia de diretório")
        object.__setattr__(self, "context_path", Path(self.context_path))

    def context_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"gameId": self.game_id, "focusId": self.focus_id}
        if self.launch_request_id is not None:
            payload.update(
                schemaVersion=2, owner=CONTEXT_OWNER, launchRequestId=self.launch_request_id
            )
        return payload


def recovery_context(payload: object) -> dict[str, str] | None:
    """A v2 references a preallocated canonical identity; it proves no state."""
    if (
        not isinstance(payload, dict)
        or type(payload.get("schemaVersion")) is not int
        or payload.get("schemaVersion") != 2
    ):
        return None
    request_id = payload.get("launchRequestId")
    if (
        payload.get("owner") != CONTEXT_OWNER
        or not is_identifier(payload.get("gameId"))
        or not is_focus_id(payload.get("focusId"))
        or not isinstance(request_id, str)
        or not ids.is_ulid(request_id)
    ):
        return None
    return {
        "gameId": payload["gameId"],
        "focusId": payload["focusId"],
        "requestId": request_id,
        "sessionId": request_id,
    }


def _context_text(target: Path) -> str:
    if target.is_symlink():
        raise OSError("contexto é link simbólico")
    data = fs.read_at(target, 0, MAX_CONTEXT_BYTES + 1)
    if len(data) > MAX_CONTEXT_BYTES:
        raise OSError("contexto excede o limite")
    return data.decode("utf-8")


def forget_context(path: Path, request_id: str) -> bool:
    """Only the terminal owner may consume this exact owned v2 record."""
    try:
        recovered = recovery_context(json.loads(_context_text(path)))
        if recovered is None or recovered["requestId"] != request_id:
            return False
        fs.remove_file(path)
    except (OSError, ValueError):
        return False
    return True


def read_recovery_context(path: Path) -> dict[str, str] | None:
    """Observe an owned v2 context without consuming or repairing any file."""
    try:
        return recovery_context(json.loads(_context_text(path)))
    except (OSError, ValueError, RecursionError):
        return None


@dataclass(frozen=True)
class LaunchHandle:
    pid: int
    game_id: str


def launch_detached(plan: LaunchPlan, *, spawn: Spawn) -> LaunchHandle:
    """Grava o contexto e então lança o jogo desacoplado do launcher.

    ``spawn`` é obrigatório: quem cria processo é o adapter, não o domínio.

    A ordem é deliberada e testada: o contexto vai para o disco ANTES do spawn,
    para que um crash no meio da criação do processo não perca o lugar do
    usuário. V1 mantém o rollback legado. V2 é publicada exclusivamente e
    conserva a referência em falhas incertas; uma recusa de execução conhecida
    remove somente o registro próprio. Estado vivo depende da sessão canônica.
    """
    if plan.context_path.is_symlink() or (
        plan.launch_request_id is not None and plan.context_path.exists()
    ):
        raise SteamZeroError(
            "E-TX-LOCKED", detail="contexto de lançamento pendente; consulte a sessão"
        )
    if plan.context_path.exists():
        try:
            pending = recovery_context(json.loads(_context_text(plan.context_path)))
        except (OSError, ValueError):
            pending = None
        if pending is not None:
            raise SteamZeroError("E-TX-LOCKED", detail="contexto rastreado ainda pendente")
    payload = json.dumps(plan.context_payload(), ensure_ascii=False)
    if plan.launch_request_id is None:
        fs.write_atomic_text(plan.context_path, payload)
    else:
        temporary = fs.write_tmp(plan.context_path.parent, payload.encode("utf-8"))
        try:
            fs.publish_link(temporary, plan.context_path)
        except FileExistsError as exc:
            fs.discard_tmp(temporary)
            raise SteamZeroError("E-TX-LOCKED", detail="contexto concorrente preservado") from exc
        except BaseException:
            fs.discard_tmp(temporary)
            raise
    try:
        pid = spawn(tuple(plan.argv))
    except BaseException as exc:
        if plan.launch_request_id is None:
            fs.remove_file(plan.context_path)
        elif isinstance(exc, (FileNotFoundError, PermissionError)):
            forget_context(plan.context_path, plan.launch_request_id)
        raise
    return LaunchHandle(pid=pid, game_id=plan.game_id)


def consume_context(path: Path | str, *, with_diagnostics: bool = False) -> Any:
    """Consume legacy focus once; retain owned v2 for validated explicit reuse.

    Contexto ausente é normal: significa que ninguém lançou nada. Contexto
    ilegível é anomalia e vira diagnóstico — adivinhar um retorno plausível
    levaria o usuário para um lugar que ele não escolheu.
    """
    target = Path(path)
    diagnostics: list[dict[str, str]] = []
    try:
        raw = _context_text(target)
    except FileNotFoundError:
        return (None, diagnostics) if with_diagnostics else None
    except (OSError, UnicodeError) as exc:
        diagnostics.append(
            {
                "code": DIAG_CONTEXT_LOST,
                "reason": f"contexto ilegível: {exc}",
                "fallback": "home",
            }
        )
        return (None, diagnostics) if with_diagnostics else None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        fs.remove_file(target)
        diagnostics.append(
            {
                "code": DIAG_CONTEXT_LOST,
                "reason": f"contexto corrompido: {exc.msg}",
                "fallback": "home",
            }
        )
        return (None, diagnostics) if with_diagnostics else None
    if not isinstance(payload, dict):
        fs.remove_file(target)
        diagnostics.append(
            {
                "code": DIAG_CONTEXT_LOST,
                "reason": "contexto não é objeto",
                "fallback": "home",
            }
        )
        return (None, diagnostics) if with_diagnostics else None
    if payload.get("schemaVersion", 1) != 1 or "owner" in payload:
        if recovery_context(payload) is None:
            diagnostics.append(
                {
                    "code": DIAG_CONTEXT_LOST,
                    "reason": "contexto versionado sem identidade/ownership válido",
                    "fallback": "home",
                }
            )
            return (None, diagnostics) if with_diagnostics else None
    else:
        fs.remove_file(target)
    return (payload, diagnostics) if with_diagnostics else payload

from __future__ import annotations

import importlib.resources
import json
import logging
import os
import stat
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from steamzero.core import fs, ids, journal, paths, transaction
from steamzero.core.errors import SteamZeroError

_PREFERENCE_FILENAME = "theme-preference-v1.json"
_MAX_REFERENCE_BYTES = 4096
_LOG = logging.getLogger(__name__)


def _reference_bytes(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("preferência não é arquivo regular")
        if metadata.st_size > _MAX_REFERENCE_BYTES:
            raise ValueError("preferência excede o limite de leitura")
        payload = stream.read(_MAX_REFERENCE_BYTES + 1)
    if len(payload) > _MAX_REFERENCE_BYTES:
        raise ValueError("preferência excede o limite de leitura")
    return payload


@cache
def _reference_validator() -> Draft202012Validator:
    schema = json.loads(
        importlib.resources.files("steamzero.schemas")
        .joinpath("theme-preference-v1.schema.json")
        .read_text(encoding="utf-8")
    )
    # Only reference fields govern removal. Older presentation/version values
    # remain readable; identifiers still follow the existing canonical schema.
    return Draft202012Validator(
        {
            "type": "object",
            "required": ["schemaVersion", "themeId"],
            "properties": {key: schema["properties"][key] for key in ("schemaVersion", "themeId")},
        }
    )


class ThemePreferenceManager:
    """Gerencia a preferência de tema ativo com plano/preview/confirmacao/rollback.

    Segue o padrao transactional do SteamZero: plan_activate -> apply -> rollback.
    Cada ativacao de tema cria um plano transacional; a preferencia e persistida
    em theme-preference-v1.json no diretorio XDG config.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or paths.config_home()
        self._path = self._config_dir / _PREFERENCE_FILENAME

    def _preference_path(self) -> Path:
        return self._path

    def _read_preference(self) -> dict[str, Any] | None:
        path = self._path
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_bytes())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict):
            return None
        return raw

    def referenced_theme_id(self) -> str | None:
        """Read the consumer before removal; unknown state refuses destruction."""
        try:
            payload = _reference_bytes(self._path)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise SteamZeroError(
                "E-THEME-MANIFEST", detail="preferência de tema indisponível; remoção recusada"
            ) from exc
        try:
            raw = json.loads(payload)
            _reference_validator().validate(raw)
            return str(raw["themeId"])
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise SteamZeroError(
                "E-THEME-MANIFEST", detail="preferência de tema inválida; remoção recusada"
            ) from exc

    def _serialize(self, theme_id: str, version: str, previous: dict[str, Any] | None) -> bytes:
        revision = (previous.get("revision", 0) + 1) if previous else 0
        pref = {
            "schemaVersion": 1,
            "themeId": theme_id,
            "themeVersion": version,
            "revision": revision,
        }
        return json.dumps(pref, indent=2, ensure_ascii=False).encode("utf-8")

    def plan_activate(
        self, theme_id: str, version: str, *, previous: dict[str, Any] | None = None
    ) -> transaction.Plan | None:
        """Cria um plano transacional para ativar um tema.

        Se *previous* for fornecido (preferencia atual lida pelo chamador),
        retorna ``None`` quando o tema já está ativo. Essa é uma operação
        informativa: não cria plano, não pede confirmação e não altera a
        preferência persistida.
        """
        if previous and previous.get("themeId") == theme_id:
            return None
        content = self._serialize(theme_id, version, previous)
        target = self._preference_path()
        return transaction.plan_write_files(
            {target: content},
            root=self._config_dir,
            kind="theme.preference.activate",
        )

    def load_plan(self, plan_id: str) -> transaction.Plan:
        plan = transaction.load_plan(plan_id)
        if not plan.kind.startswith("theme.preference."):
            raise SteamZeroError(
                "E-TX-STALE-PLAN",
                detail=f"plano {plan_id} nao pertence a preferencias de tema (kind={plan.kind})",
            )
        return plan

    def apply(
        self,
        plan_id: str,
        confirm_token: str,
        *,
        verify_reference: Callable[[str, str], None] | None = None,
    ) -> transaction.ApplyResult:
        """Aplica o plano de ativacao de tema."""
        plan = self.load_plan(plan_id)
        self._validate_plan_ownership(plan)
        theme_id, version = self._planned_reference(plan)
        if verify_reference is not None:
            verify_reference(theme_id, version)

        def verify() -> None:
            path = Path(plan.actions[0].target)
            if not path.is_file():
                raise RuntimeError("preferencia de tema nao foi escrita")
            try:
                raw = json.loads(path.read_bytes())
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(f"preferencia de tema ilegivel: {exc}") from exc
            if not isinstance(raw.get("themeId"), str):
                raise RuntimeError("preferencia de tema sem themeId valido")

        return transaction.apply(plan_id, confirm_token, smoke=verify)

    def _planned_reference(self, plan: transaction.Plan) -> tuple[str, str]:
        try:
            if len(plan.actions) != 1:
                raise ValueError("preferência exige uma ação")
            action = plan.actions[0]
            if action.kind != "write" or Path(action.target).resolve() != self._path.resolve():
                raise ValueError("destino não pertence à preferência")
            encoded_limit = 4 * ((_MAX_REFERENCE_BYTES + 2) // 3)
            if (
                action.new_size > _MAX_REFERENCE_BYTES
                or len(action.new_content_b64) > encoded_limit
            ):
                raise ValueError("preferência excede o orçamento")
            payload = action.new_content()
            if len(payload) != action.new_size or len(payload) > _MAX_REFERENCE_BYTES:
                raise ValueError("tamanho de preferência inconsistente")
            raw = json.loads(payload)
            _reference_validator().validate(raw)
            if not isinstance(raw.get("themeVersion"), str):
                raise ValueError("versão da preferência inválida")
            return str(raw["themeId"]), raw["themeVersion"]
        except (OSError, UnicodeError, ValueError, TypeError, ValidationError) as exc:
            raise SteamZeroError(
                "E-TX-STALE-PLAN", detail="plano de preferência inválido; refaça a prévia"
            ) from exc

    def rollback(
        self,
        operation_id: str,
        *,
        verify_reference: Callable[[str, str], None] | None = None,
    ) -> transaction.RollbackResult:
        if not isinstance(operation_id, str) or not ids.ULID_RE.fullmatch(operation_id):
            raise SteamZeroError("E-API-SCHEMA", detail="operation_id inválido")
        try:
            records = journal.read_records(operation_id)
            if not all(isinstance(record, dict) for record in records):
                raise ValueError("journal inválido")
            begin = next(record for record in records if record.get("type") == "operation.begin")
            if not str(begin.get("kind", "")).startswith("theme.preference."):
                raise ValueError("operação não pertence a preferências")
            intents = [record for record in records if record.get("type") == "action.intent"]
            if len(intents) > 1:
                raise ValueError("preferência não possui múltiplos alvos")
            for record in intents:
                undo = record["undo"]
                if (
                    undo.get("op") not in {"restore", "delete"}
                    or Path(undo["target"]).resolve() != self._path.resolve()
                ):
                    raise ValueError("alvo não pertence a esta preferência")
        except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
            raise SteamZeroError(
                "E-TX-STALE-PLAN", detail="operação não pertence às preferências deste perfil"
            ) from exc
        if verify_reference is not None and not journal.has_type(records, journal.ROLLBACK):
            for record in intents:
                undo = record["undo"]
                if undo["op"] != "restore":
                    continue
                name = undo.get("backupRel")
                if (
                    not isinstance(name, str)
                    or name in {".", ".."}
                    or Path(name).name != name
                    or name != record["actionId"]
                ):
                    raise SteamZeroError(
                        "E-TX-ROLLBACK-FAILED", detail="backup de preferência inválido"
                    )
                try:
                    payload = _reference_bytes(paths.backup_for(operation_id) / name)
                except OSError as exc:
                    raise SteamZeroError(
                        "E-TX-ROLLBACK-FAILED", detail="backup de preferência indisponível"
                    ) from exc
                except ValueError:
                    # Unknown legacy bytes still restore through the core's
                    # verified ownership/hash path, preserving the old contract.
                    _LOG.warning(
                        "THEME-PREFERENCE-ROLLBACK-LEGACY-001: vínculo anterior desconhecido"
                    )
                    continue
                if fs.hash_bytes(payload) != undo.get("expectHash"):
                    raise SteamZeroError(
                        "E-TX-ROLLBACK-FAILED", detail="backup de preferência adulterado"
                    )
                try:
                    raw = json.loads(payload)
                    _reference_validator().validate(raw)
                except (ValueError, UnicodeError, ValidationError):
                    _LOG.warning(
                        "THEME-PREFERENCE-ROLLBACK-LEGACY-001: vínculo anterior desconhecido"
                    )
                    continue
                version = raw.get("themeVersion", "")
                verify_reference(str(raw["themeId"]), version if isinstance(version, str) else "")
        return transaction.rollback(operation_id, reason="theme-preference")

    def _validate_plan_ownership(self, plan: transaction.Plan) -> None:
        actual_root = str(Path(plan.root).resolve())
        expected_root = str(self._config_dir.resolve())
        if actual_root != expected_root:
            raise SteamZeroError(
                "E-TX-STALE-PLAN",
                detail=f"plano tem root {actual_root} mas o manager espera {expected_root}",
            )

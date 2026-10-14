# Lote de coesão visual e botões reais — plano de execução

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** fechar os defeitos reproduzidos da jornada física de 2026-10-12 (D-17, D-23, D-26, D-27, D-28, D-29 e a
classe de atritos da Central/Launcher) de modo que nenhum controle alegue o que não executa e a paleta publicada
sustente o próprio texto.

**Arquitetura:** quatro lotes verticais independentes — (A) lançamento e ciclo de sessão no adapter, (B) vocabulário de
ações publicadas (contratos + OSD), (C) tokens de tema e superfícies da UI, (D) checkpoint de gates e registro. Cada
lote fecha com testes focados verdes e commit funcional próprio; nenhum lote depende da entrega do anterior para ser
revisado.

**Tech Stack:** Python 3.14 (`.venv`), PySide6/QML 6 (Qt Quick Controls), pytest, ruff, mypy, JSONL de `core.log`,
`theme.json` com cadeia `extends`, harness QML offscreen (`tests/qml/**.qml` + `tests/integration/test_qml_*.py`).

**Spec (ler na ordem, antes de editar qualquer linha):**

1. `AGENTS.md` — §1 (instalação), §2 (branch e claims), §6 (gates), §9 (ciclo de entrega e prova), §10 (AURA).
2. `docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/README.md` — matriz A–F, com o limite de cada
   linha. É o documento que diz o que **não** pode ser alegado sem prova nova.
3. `docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/12-defeitos-registrados.txt` — D-01…D-29
   com arquivo, linha e evidência de cada um.
4. `docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/18-censo-controles-backend.txt` e
   `logs/19-auditoria-de-cores.txt` — contagem integral por eixo; as tabelas por tema.
5. `docs/01-product/AURA-SURFACES.md` e `docs/01-product/THEME-ENGINE-AND-STUDIO.md` (exigência do §10 antes de tocar
   tema/UI/Launcher).
6. `IMPLEMENTATION-PROMPT.md` — prompt canônico de A_CODIGO. Este plano **não** cria roadmap paralelo: ele é uma
   rodada de correção dentro das prioridades V1–V4 já declaradas lá.

## Restrições globais (valem para toda tarefa)

- Worktree único: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`. Nenhum clone, worktree ou diretório `v2`;
  nenhum `git reset`/`clean`/`stash` automático. Se o executor for Codex CLI, prefixe shell com `rtk`.
- Base: `codex/jornada-fisica-bateria-2026-10-12` em `c2456726`, cujo `baseRef` é `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7`
  (cabeça de `origin/main` à época da prova, PR #257). Release ativa observada: `2.0.0rc1-2b7eb541b4a5`. **Reconfira
  branch/HEAD/claims antes de editar**; base obsoleta tem sintoma conhecido (AGENTS §3).
- **Sem autorização nesta rodada:** instalar, reverter, ciclar serviço, publicar release, `push`, `merge`, `sudo`.
  Só `bigsudo` pelo fluxo de `tools/release_host.py`, com token exato, mediante autorização nova na thread do executor.
  Nunca chamar `tools/install_host.py` à mão.
- **Sem injeção de entrada GUI neste host** (`misael-jupiter`): nada de `ydotool`/`xdotool`/clique sintético em
  janela real. Prova visual adicional exige sessão descartável ou autorização nomeando a injeção; sem PNG, a linha
  continua "aberto", não "consertado".
- Não editar configuração de terceiros, nem `~/.local/share/steamzero/themes/**` pessoal, nem `/etc`, `/usr/local`,
  `/opt`, `/boot`. O resíduo da prova (3 pares de save-state e a jornada de teste inerte listados em `logs/13`) é
  **certificado, não apagado**; apagar é destrutivo e não está autorizado.
- Nunca enfraqueça, delete ou pule um teste para ficar verde. Se um contrato mudou de verdade, diga qual e por quê no
  commit. Cobertura não regride.
- Gates no lote (AGENTS §6): durante o trabalho, apenas testes focados + `.venv/bin/ruff check <arquivos>` +
  `.venv/bin/ruff format --check <arquivos>`. Os gates integrais rodam **uma** vez, no checkpoint (Tarefa 14):
  `.venv/bin/python tools/run_tests_isolated.py tests -q`, `.venv/bin/ruff check src tools tests`,
  `.venv/bin/ruff format --check src tools tests`, `.venv/bin/mypy src`, `make independence boundaries`,
  `make status-check`.
- Status é governado: item em `docs/status/items/*.json` + cartão em `docs/status/workstreams/*.json`, views com
  `.venv/bin/python tools/project_status.py render --write` (o python do sistema não tem `jsonschema`). `docs/WORKLOG.md`
  é append-only, só no fechamento.
- **Aprovação por unidade de design:** Tarefas 3, 6, 7 e 9 mudam comportamento visível ou paleta. Apresente as opções
  com a medição, pare, e só aplique a unidade que o operador aprovar. Um lote proposto não é um lote aprovado.
- Não referencie PhaseZero/RetroDECK/LinuxToys em código, string, path ou comentário (ADR-0019; `make independence`
  reprova a presença).
- Nenhuma afirmação de FPS, desempenho GPU ou fidelidade visual sem medição no hardware; offscreen não certifica.

## Estrutura de arquivos

| Arquivo | Responsabilidade neste lote |
|---|---|
| `src/steamzero/adapters/launcher_ui.py` | corpo do 409 de lançamento (D-17) e validação de `/session/action` (D-20) |
| `src/steamzero/adapters/session_control.py` | estados aceitos, gate de canal suspenso (D-23), faixa de slot (D-20) |
| `src/steamzero/adapters/session_overlay.py` | capacidades publicadas no OSD (D-23, D-28) |
| `src/steamzero/domain/session_overlay.py` | `OSD_ACTIONS`, rótulos, `_capability` (D-28) |
| `src/steamzero/adapters/emulation.py` / `domain/emulation_workspace.py` | catálogo de ações de emulação, `enabled` (D-27) |
| `src/steamzero/ui/qml/Main.qml` | ramo local `performEmulationAction` (D-27), nomes acessíveis (D-19) |
| `src/steamzero/ui/qml/launcher/LauncherSessionOverlay.qml` / `LauncherMain.qml` | porta do `slot`, despacho do OSD (D-20, D-23) |
| `src/steamzero/themes/*/theme.json` | tokens de cor (D-29) |
| `src/steamzero/domain/themes.py` / `ui/qml/ThemeBridge.qml` | resolução de `inherit-aura` e tema por menu (D-06, D-07) |
| `tests/unit/`, `tests/integration/`, `tests/qml/` | um teste por contrato novo, no arquivo do módulo já existente |
| `docs/09-operations/evidence/2026-10-13-lote-coesao-ui/` | evidência desta rodada (baseline, saída dos gates, capturas quando houver autorização) |

---

## Lote 0 — Pré-voo (sem esta tarefa, nenhuma edição é válida)

- [ ] **Step 1: Conferir o checkout**

```bash
cd "/home/misael/Projects/Steam Zero/Canonical/2026-09-21"
git status --short && git branch --show-current && git log --oneline -3
ls -l /opt/steamzero/current
```

Esperado: worktree limpo, branch do lote, `/opt/steamzero/current` ainda em `releases/2.0.0rc1-2b7eb541b4a5`. Anote a
release ativa no relatório; nada aqui instala.

- [ ] **Step 2: Ler os claims antes de tocar em arquivo reivindicado**

```bash
sed -n '1,40p' docs/ACTIVE-WORK.md
grep -rn "Main.qml\|session_overlay\|themes/\|emulation.py" docs/status/workstreams/*.json | grep exclusivePaths -A2
```

`Main.qml`, `desktop_contracts.py`, `emulation.py`, `launcher/*.qml`, `themes/*/theme.json` e `session_overlay.py`
estão reivindicados por frentes ativas. Se o path que você precisa estiver em outra frente, **pare e registre o handoff
serial** no cartão novo (origem, destino, base com SHA de 40 caracteres, escopo, devolução), como fazem os registros de
2026-10-04 a 2026-10-11 em `docs/ACTIVE-WORK.md`. Não edite o claim de outro workstream sem essa linha.

- [ ] **Step 3: Criar o cartão da frente e o diretório de evidência**

`docs/status/workstreams/lote-coesao-ui-2026-10-13.json` com `item` apontando para o item escolhido no Step 4, `branch`,
`baseRef` completo, `exclusivePaths` = o diretório de evidência novo + o próprio cartão.

```bash
mkdir -p docs/09-operations/evidence/2026-10-13-lote-coesao-ui/{logs,capturas}
```

- [ ] **Step 4: Reproducing baseline (AGENTS §9.1)**

Rode o censo e a auditoria arquivados e salve a saída como linha de base desta rodada:

```bash
python3 docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/harness/sz_censo.py . \
  > docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/00-baseline-censo.txt
python3 docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/harness/sz_cores.py \
  > docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/01-baseline-cores.txt
```

Esperado: `0 sem endpoint com porta ausente`, `43 reprovações` — os dois números são a régua que os lotes 2 e 3 movem.
**Cuidado:** rode a partir da raiz do repo; o harness grava em caminho relativo.

- [ ] **Step 5: Commit de pré-voo**

```bash
git add docs/status/workstreams/lote-coesao-ui-2026-10-13.json docs/09-operations/evidence/2026-10-13-lote-coesao-ui
git commit -m "chore(workstream): abrir o lote de coesao visual com baseline do censo e das cores"
```

---

## Lote A — Lançamento e ciclo de sessão (D-17, D-23, D-26, D-20)

### Tarefa 1: D-17 — o 409 de lançamento publica a causa que existe e um rastro resolúvel

**Files:**
- Modify: `src/steamzero/adapters/launcher_ui.py:238-252` (o `except (OSError, ValueError, SteamZeroError)` que hoje
  colapsa tudo em `LAUNCHER-LAUNCH-FAILED-001`)
- Test: `tests/integration/test_launcher_app.py` (já asserta o code no corpo — linha ~200)

**Interfaces:**
- Consumes: `SteamZeroError(code=…, detail=…, operation_id=…)` de `src/steamzero/core/errors.py:241`;
  `steamzero.core.log.get_logger(correlation_id=…)` com `.error(event, **fields)`; `log.new_correlation_id()`.
- Produz: corpo 409 com `error.code`, `error.cause`, `error.diagnosticId` e o mesmo `diagnosticId` numa linha de
  `~/.local/state/steamzero/logs/core.jsonl`. `diagnosticId` é o único campo novo do contrato.

**Por que assim:** a supressão é deliberada — `launcher_ui.py:236-237` diz que o texto da exceção pode conter caminhos
locais. O defeito não é esconder o texto; é não publicar **nenhum** identificador que leve à linha do journal onde o
texto existe. O `correlationId` já é o mecanismo previsto (ADR-0011).

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/integration/test_launcher_app.py`, espelhando o existente `test_launch_failure_is_reported_without_secrets_and_bridge_recovers`
(linha 181), que já usa `LauncherBridge(...)`, `build_sections(...)`, `bridge.serving()`, `_post(...)` e
`pytest.raises(urllib.error.HTTPError)`:

```python
def test_launch_failure_publishes_resolvable_diagnostic_id(tmp_path: Path, monkeypatch) -> None:
    """D-17: um code genérico não pode ser beco sem saída — tem de apontar para a linha do journal."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    def launch(game: str, focus: str) -> None:
        raise OSError("private-path-and-secret")

    bridge = LauncherBridge(
        sections=build_sections([{"id": "game", "title": "Game", "section": "library"}]),
        context_path=tmp_path / "return.json",
        on_launch=launch,
    )
    with bridge.serving() as base:
        with pytest.raises(urllib.error.HTTPError) as failure:
            _post(f"{base}/launch", bridge.token, {"gameId": "game", "focusId": "library:game"})
        body = json.loads(failure.value.read())

    assert body["error"]["code"] == "LAUNCHER-LAUNCH-FAILED-001"
    diagnostic_id = body["error"]["diagnosticId"]
    assert diagnostic_id
    assert "private-path-and-secret" not in json.dumps(body)
    journal = (tmp_path / "steamzero/logs/core.jsonl").read_text(encoding="utf-8")
    assert diagnostic_id in journal
    assert "OSError" in journal
```

Confira antes o caminho real do journal com `core.paths.core_log()` (`src/steamzero/core/paths.py:238`); se o suite
redirect já redireciona o state home por outro mecanismo, use o dele em vez do `monkeypatch.setenv`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_app.py -k resolvable_diagnostic -q`
Expected: FAIL — `KeyError: 'diagnosticId'`.

- [ ] **Step 3: Implementar**

No `except`, capture o erro, emita uma linha estruturada e publique o id:

```python
        except (OSError, ValueError, SteamZeroError) as exc:
            # Exception text can contain local paths or credentials. Publish a
            # stable recovery contract, never an unfiltered traceback/detail.
            diagnostic_id = log.new_correlation_id()
            log.get_logger(correlation_id=diagnostic_id).error(
                "launcher.launch.failed",
                gameId=game_id,
                errorType=type(exc).__name__,
                errorCode=getattr(exc, "code", ""),
                errorDetail=str(exc)[:MAX_LAUNCH_DETAIL],
            )
            self._send(
                409,
                {
                    "error": {
                        "code": getattr(exc, "code", None) or "LAUNCHER-LAUNCH-FAILED-001",
                        "cause": "Não foi possível preparar o lançamento.",
                        "impact": "O Launcher não confirmou o início do jogo.",
                        "diagnosticId": diagnostic_id,
                        "nextAction": (
                            f"Consulte o diagnóstico {diagnostic_id} em "
                            "`steamzero logs --since 5m` e tente novamente."
                        ),
                    }
                },
            )
            return
```

Não existe subcomando `steamzero logs` (verificado em `src/steamzero/cli/main.py`): no `nextAction`, use o caminho
literal devolvido por `core.paths.core_log()` (`src/steamzero/core/paths.py:238`) com o id. `MAX_LAUNCH_DETAIL = 240`
como constante do módulo.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_app.py tests/integration/test_desktop_ui_bridge.py -q`
Expected: PASS, inclusive o teste antigo que ainda espera `LAUNCHER-LAUNCH-FAILED-001` para erro sem code.

- [ ] **Step 5: Reproduzir o caso real, sem injeção de GUI**

Chame a rota da ponte para o título da prova (`'89 Dennou Kyuusei Uranai (Japan) (zip)`, NES/Mesen) **pelo HTTP da
Central**, como fez `harness/sz_api.py`, e arquive a resposta em
`docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/02-d17-causa.txt` com o `diagnosticId` e a linha do journal
que ele resolve. Isto é consulta de leitura + uma tentativa de lançamento controlada: não é clique, não é prova visual.

- [ ] **Step 6: Gates focados e commit**

```bash
.venv/bin/ruff check src/steamzero/adapters/launcher_ui.py tests/integration/test_launcher_app.py
.venv/bin/ruff format --check src/steamzero/adapters/launcher_ui.py tests/integration/test_launcher_app.py
git add src/steamzero/adapters/launcher_ui.py tests/integration/test_launcher_app.py docs/09-operations/evidence/2026-10-13-lote-coesao-ui
git commit -m "fix(launcher): publicar diagnostico resolvel na recusa de lancamento (D-17)"
```

### Tarefa 2: D-23 — uma sessão suspensa recusa ação de canal **antes** de tocar o socket

**Files:**
- Modify: `src/steamzero/adapters/session_control.py` — o gate entra no **cliente** `RemoteSessionControl`
  (`:471-583`; `_request` em `:502`, os invocadores `save_state`/`load_state`/`list_discs`/`swap_disc`/`list_peripherals`
  em `:568-583`), **não** no `SessionControlServer._dispatch` (`:368`): o servidor do canal vive dentro da árvore que a
  pausa `SIGSTOP`a, é justamente por isso que ele não responde. Também:
  `src/steamzero/adapters/session_overlay.py:160-185` (`capabilities`) e `src/steamzero/domain/session_overlay.py:148-160`
  (`_capability`).
- Test: `tests/unit/test_session_control.py` (o padrão real do arquivo é `SessionControlOwner(...)` +
  `SessionControlServer(owner, control_path(...))` + `resolve_remote_session_control(...)`, como em
  `test_remote_control_uses_owner_transitions_and_never_signals_from_ui:93`), `tests/unit/test_session_overlay.py`,
  `tests/qml/launcher/check_launcher_session_osd.qml`

**Interfaces:**
- Produz: recusa estruturada `{"accepted": False, "state": "suspended", "diagnostic": "AURA-SESSION-ADAPTER-007",
  "detail": …, "nextAction": …}` **sem** abrir conexão; e `capabilities["saveState"|"loadState"|"disc"] =
  {"available": False, "reason": "A sessão está suspensa; retome antes de salvar."}`.
- Consumes: `SessionControlRecord.state`, `DIAG_*` de `adapters/session_overlay.py:29-35` (007 está livre — confira).
  O **código levantado** como exceção não é um `DIAG_*`: `SteamZeroError` recusa código fora do catálogo
  (`core/errors.py:256`) e a área `SESSION` já existe (`:64-68`). Registre
  `"E-SESSION-CHANNEL-SUSPENDED": "SESSION"` em `ERROR_CATALOG` **e** os cinco campos i18n obrigatórios
  (`REQUIRED_FIELDS`: title/what/impact/cause/action) em `src/steamzero/i18n/messages_pt_br.py` — `test_error_catalog`
  exige ambos. Os `DIAG_*` e `"LAUNCHER-LAUNCH-FAILED-001"` continuam sendo strings do corpo da resposta, não códigos
  de exceção.

- [ ] **Step 1: Teste que falha — a recusa não pode tocar o socket**

Em `tests/unit/test_session_control.py`, seguindo o padrão real do arquivo (dono + servidor + cliente de verdade sobre
um `socket_root` em `tmp_path`), com o estado da sessão já em `suspended` via `remote.suspend()` e o `signal_process`
do dono registrando os sinais. A contagem de conexões tem de ser **medida**, não declarada: monkeypatche o
`socket.socket` usado por `RemoteSessionControl._request` (o módulo importa `socket`, então
`monkeypatch.setattr(session_control.socket, "socket", espião)`).

```python
def _owner_and_server(
    tmp_path: Path,
    *,
    signals: list[tuple[int, int]],
    peripheral_control: SessionPeripheralControl | None = None,
    supervised_pids: tuple[int, ...] = (),
) -> tuple[SessionControlOwner, SessionControlServer, str, str]:
    """Dono + canal reais, com os sinais gravados em `signals` em vez de enviados.

    `supervised_pids` é consumido pelo construtor que a unidade 3a introduz (o registro dos grupos
    supervisionados no `suspend`); na Tarefa 2 fica vazio e o dono sinaliza só `self.pid`.
    """
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)  # helper já existente no arquivo
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid, pid),
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
        peripheral_control=peripheral_control,
    )
    server = SessionControlServer(owner, control_path(session_id, root=tmp_path.parent))
    server.start()
    return owner, server, session_id, game_id


def test_save_state_while_suspended_never_reaches_the_control_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-23: um pedido entregue a uma árvore parada é executado depois, contra uma recusa já publicada."""
    signals: list[tuple[int, int]] = []
    connections: list[str] = []
    real_socket = socket.socket

    def spy(family: int, type_: int) -> socket.socket:
        connection = real_socket(family, type_)
        original_connect = connection.connect

        def connect(address: str) -> None:
            connections.append(address)
            original_connect(address)

        connection.connect = connect  # type: ignore[method-assign]
        return connection

    monkeypatch.setattr(session_control.socket, "socket", spy)
    owner, server, session_id, game_id = _owner_and_server(tmp_path, signals=signals)
    try:
        remote = resolve_remote_session_control(
            session_id,
            game_id,
            observe=lambda sid: observe_game_session(tmp_path / "state.db", sid),
            root=tmp_path.parent,
        )
        assert remote is not None
        connections.clear()  # o resolve/observe do caminho de subida não conta
        remote.suspend()
        signals.clear()
        connections.clear()

        with pytest.raises(SteamZeroError) as refusal:
            remote.save_state(1)

        assert refusal.value.code == "E-SESSION-CHANNEL-SUSPENDED"
        assert connections == []  # o socket do canal nunca foi aberto
        assert signals == []      # nem um sinal escondido atrás do pedido
    finally:
        server.close()
```

O `connections.clear()` antes do pedido é o que torna a asserção não-vazia: sem ele, `connections == []` seria
satisfeito por um teste que nunca exerceu o caminho. Importe `socket`, `cast` se precisar, e
`from steamzero.adapters import session_control` no topo do arquivo, e
`from steamzero.adapters.session_peripherals import SessionPeripheralControl` para o tipo do helper.

- [ ] **Step 2:** Run `.venv/bin/python tools/run_tests_isolated.py tests/unit/test_session_control.py -k suspended -q`
  → FAIL (o caminho hoje abre o socket e cai em `"o dono da sessão não respondeu"`).

- [ ] **Step 3: Implementar o gate**

No `RemoteSessionControl`, antes de `_request`, para o conjunto que exige resposta do processo
(`saveState`, `loadState`, `swapDisc`, `listSaveStates`, `listDiscs`, `listPeripherals`):

```python
    def _refuse_if_not_live(self, action: str) -> None:
        """O canal é servido pela árvore que a pausa para: sem processo vivo, o pedido não é entregue, é adiado."""
        record = self.current
        if record is None or record.state not in CHANNEL_READY_STATES:
            raise SteamZeroError(
                DIAG_SUSPENDED_CHANNEL,  # = "E-SESSION-CHANNEL-SUSPENDED", registrado em ERROR_CATALOG
                detail=f"{action} exige uma sessão viva; o pedido não foi enviado ao emulador.",
            )
```

com `CHANNEL_READY_STATES = frozenset({"launching", "running"})`, a constante do módulo nomeada
`DIAG_SUSPENDED_CHANNEL` para o código do catálogo (o nome segue a convenção local de
`DIAG_CONTROL_*`, `session_control.py:35-37`), e os cinco campos i18n em `messages_pt_br.py`.
`_request_data` (usado por `list_save_states`/`list_discs`/`list_peripherals`) recebe o mesmo gate — é o outro
caminho que hoje pendura. Mapeie a exceção em `adapters/session_overlay.py` para
`{"accepted": False, "state": …, "diagnostic": …, "detail": "A sessão está suspensa; o pedido não foi enviado ao
emulador.", "nextAction": "Retome a sessão e tente novamente."}`.

Espelhe o motivo em `adapters/session_overlay.py` onde `capabilities["saveState"]` é montado (linha ~173): com
`state == "suspended"`, `available=False` e exatamente a frase acima — é a armadilha alcançável pela UI que o D-23
descreve ("o OSD oferece Galeria de saves habilitada nesse estado").

- [ ] **Step 4:** Run `.venv/bin/python tools/run_tests_isolated.py tests/unit/test_session_control.py tests/unit/test_session_overlay.py tests/integration/test_launcher_session_composition.py -q`
  → PASS. Depois o harness QML: `.venv/bin/python tools/run_tests_isolated.py tests/integration/test_qml_handheld_offscreen.py -k session_osd -q` → PASS com a
  "Galeria de saves" **desabilitada** em sessão suspensa.

- [ ] **Step 5: Commit** `git commit -m "fix(session): recusar acao de canal com a sessao suspensa, antes do socket (D-23)"`

### Tarefa 3: D-23/C-4 — destravar a árvore que o produto parou (portão de decisão)

**Files:**
- Modify (depois de aprovado): `src/steamzero/adapters/session_control.py:133-143` (`suspend`/`resume` por `killpg`) e
  o registro dos pids supervisionados em `src/steamzero/adapters/launcher_session.py`
- Test: `tests/unit/test_session_control.py`

O fato medido (`logs/11` item 6): a pausa `SIGSTOP`a a árvore do flatpak e o supervisor externo (bwrap externo `T<s`)
fica **fora** do grupo sinalizado; `resume` pelo produto não o alcança, e a recuperação exigiu `kill -CONT` externo.
`request_exit` já resolveu o mesmo problema para saída (`session_control.py:172-186`: SIGTERM pendente + SIGCONT
dirigido, sem publicar `running`).

- [ ] **Step 1: Apresentar ao operador, com esta medição, e esperar a escolha**

Duas unidades, uma resposta por unidade:
- **3a — retomar o que se parou:** registrar os pids do grupo supervisionado no `suspend` e continuar exatamente esse
  conjunto no `resume`/`request_exit`, com verificação de identidade (`_verify_process_identity`) antes de cada sinal.
  Escopo: mesmo padrão do exit já aprovado no código.
- **3b — nunca parar o supervisor:** pausar só a árvore do emulador, deixando o supervisor responsivo; o `saveState`
  deixa de pendurar. Custo: muda a semântica de "pausa" (o supervisor continua correndo) e exige ADR.

Não implemente nenhuma sem resposta escrita do operador. Registre a pergunta e a resposta em
`logs/03-decisao-d23.md`.

- [ ] **Step 2 (após aprovação): teste de que nenhum pid parado fica para trás**

No `tests/unit/test_session_control.py`, sobre o helper `_owner_and_server` da Tarefa 2 (mesmo dono, mesmo canal,
mesmo registro de sinais):

```python
def test_resume_continues_every_group_the_pause_stopped(tmp_path: Path) -> None:
    """C-4/D-23: retomar tem de alcançar o supervisor externo que a pausa parou."""
    signals: list[tuple[int, int]] = []
    owner, server, session_id, game_id = _owner_and_server(tmp_path, signals=signals)
    remote = resolve_remote_session_control(
        session_id,
        game_id,
        observe=lambda sid: observe_game_session(tmp_path / "state.db", sid),
        root=tmp_path.parent,
    )
    assert remote is not None
    try:
        remote.suspend()
        stopped = {pid for pid, _ in signals}
        signals.clear()

        remote.resume()

        assert {pid for pid, _ in signals} == stopped
        assert all(int(sig) == signal.SIGCONT for _, sig in signals)
    finally:
        server.close()
```

A asserção nova é o **conjunto de pids**. `read_process_group_identity` devolve `(pgid, sid)` de **um** pid e o dono
hoje sinaliza somente `self.pid` (`session_control.py:267-299`) — exatamente por isso o bwrap externo medido em
`logs/11` item 6 ficou parado. O parâmetro `supervised_pids` do helper representa o registro extra que a unidade 3a
acrescenta (os pids supervisionados conhecidos no `suspend`): passe dois pids falsos distintos do `self.pid` e o teste
só é não-vacioso se `resume` alcançar **todos** eles. Com o default (nenhum pid extra) ele é verde sem provar nada.

- [ ] **Step 3:** implementar, rodar
  `.venv/bin/python tools/run_tests_isolated.py tests/unit/test_session_control.py tests/integration/test_launcher_return_cycle.py -q`
  → PASS; `ruff`/`ruff format --check` nos arquivos; commit
  `fix(session): retomar a arvore supervisionada que a pausa parou (D-23/C-4)`.

- [ ] **Step 4: Não declare C-4 fechada.** O fechamento físico exige sessão presa real no host; sem autorização de
  injeção, a linha continua "parcial" na matriz com a causa corrigida apontada.

### Tarefa 4: D-26 — recusa que escreve depois é perda de confiança, não detalhe

**Files:**
- Modify: `src/steamzero/adapters/session_control.py:459-468` (o `except Exception` que hoje devolve `accepted: false`
  sem dizer se algo pode ter sido escrito) e `src/steamzero/adapters/session_peripherals.py:434` — `_state_path(slot)`
  já é a autoridade do destino (`<saves>/states/<Core>/<conteúdo>.state[<slot>]`); promova-o para o protocolo
  `SessionPeripheralControl` como `state_path(slot)` e use-o, **não** reimplemente o naming em `save_states.py`.
- Test: `tests/unit/test_save_states.py` (existe) e `tests/unit/test_session_control.py`

**Interfaces:** Produz: `{"accepted": False, …, "written": {"slot": int, "path": str, "exists": bool}}` exatamente
quando o produto **não** pode garantir ausência de efeito — o contrato deixa de afirmar "nada foi feito" quando pode
ter sido feito. Também produz `SessionPeripheralControl.state_path(slot) -> Path`, consumido por `session_control`.

- [ ] **Step 1: Teste de contrato** — mesmo arquivo, sobre o helper `_owner_and_server` da Tarefa 2 (que já recebe
  `peripheral_control`, kwarg real de `SessionControlOwner.__init__`, `session_control.py:107`). O destino real dos saves
  é `paths.saves_dir() / "states"` (a raiz criada por `adapters/session_peripherals.py:87`) e o nome vem de
  `state_path(slot)` do próprio adapter, não de uma montagem do teste.

```python
class _LateWriteControl:
    """O emulador aceita o pedido e o processo morre antes da confirmação."""

    def save_state(self, slot: int) -> None:
        raise RuntimeError("o dono da sessão não respondeu")

    def state_path(self, slot: int) -> Path:
        return paths.saves_dir() / "states" / "Mesen" / f"Jogo de Teste.state{slot}"


def test_refused_save_state_after_dispatch_declares_the_possible_file(tmp_path: Path) -> None:
    signals: list[tuple[int, int]] = []
    owner, server, session_id, game_id = _owner_and_server(
        tmp_path, signals=signals, peripheral_control=_LateWriteControl()
    )
    try:
        result = server._dispatch(
            {"sessionId": session_id, "gameId": game_id, "action": "saveState", "slot": 1}
        )
    finally:
        server.close()
    assert result["accepted"] is False
    assert set(result) >= {"diagnostic", "detail", "written"}
    assert result["written"]["slot"] == 1
    written_path = Path(result["written"]["path"])
    # O destino vem do adapter (state_path); aqui se afirma a raiz gerenciada e a sufixação por slot,
    # não um caminho montado pelo teste.
    assert written_path.is_relative_to(paths.saves_dir() / "states")
    assert written_path.name.endswith(".state1")


def test_refused_save_state_before_dispatch_declares_nothing(tmp_path: Path) -> None:
    signals: list[tuple[int, int]] = []
    owner, server, session_id, game_id = _owner_and_server(tmp_path, signals=signals)
    try:
        result = server._dispatch(
            {"sessionId": session_id, "gameId": game_id, "action": "saveState", "slot": 5_000}
        )
    finally:
        server.close()
    assert result["accepted"] is False
    assert "written" not in result  # validou antes de enviar: efeito garantidamente ausente
```

- [ ] **Step 2:** rodar → FAIL (nenhuma recusa hoje devolve `written`).
- [ ] **Step 3:** distinguir as duas metades do `try` de `_dispatch`: o que falha **antes** de chamar o
  `peripheral_control` (validação de `slot`, sessão ausente) continua sem `written`; o que falha **depois** de
  `owner.save_state(slot)` anexa `{"slot": slot, "path": str(self._peripheral_control.state_path(slot))}` ao
  corpo da recusa. Depois da recusa, consulte o disco uma vez: se o arquivo existir, a recusa diz
  `"exists": true` e o read-model da galeria passa a listar o slot ocupado em vez de fingir que está vazio.
  A Tarefa 2 já cortou o caminho de maior risco (nada é enviado a sessão suspensa).
- [ ] **Step 4:** testes focados + commit `fix(session): declarar o efeito de um save-state recusado em vez de nega-lo (D-26)`.

### Tarefa 5: D-20 — o botão nunca oferece o que a rota exige sem dado

**Files:** `src/steamzero/ui/qml/launcher/LauncherSessionOverlay.qml:205-232`, `LauncherMain.qml:241-261` e
`:876-881`, `src/steamzero/adapters/session_control.py:449`, `src/steamzero/adapters/launcher_ui.py:175-212`
- Test: `tests/qml/launcher/check_launcher_save_state_gallery.qml`, `tests/unit/test_session_control.py`

Causa raiz já demonstrada (E-5): a galeria que fornece `slot` só abre com save existente (`LauncherSessionOverlay.qml:205-212`);
sem save, o toque cai em `actionRequested` (`:227`) → `LauncherMain.qml:876-878` envia `slot=undefined` →
`session_control.py:449` recusa com `AURA-SESSION-ADAPTER-003`.

- [ ] **Step 1:** teste QML asserting que, sem save no slot escolhido, o despacho usa `saveStateRequested(actionId, slot)`
  com `slot` inteiro (0 é o slot livre padrão da UI de gallery), nunca `actionRequested`.
- [ ] **Step 2:** FAIL (hoje o ramo sem galeria emite `actionRequested` sem slot).
- [ ] **Step 3:** alinhar também a mensagem: `session_control.py:449` deve usar a frase de `launcher_ui.py:466`
  ("slot entre 0 e 999", `recoveryAction=choose-valid-slot`), que é melhor e já existe no produto.
- [ ] **Step 4:** testes QML + unitários; commit `fix(osd): oferecer saveState com slot valido e mensagem de faixa unificada (D-20)`.

---

## Lote B — Controles que alegam o que não executam (D-27, D-28)

### Tarefa 6: D-27 — um id, uma publicação; e o clique que não executa não diz "verificado"

**Files:** `src/steamzero/domain/emulation_workspace.py:689,734` (publicações `enabled=false`),
`src/steamzero/adapters/emulation.py:5687,5691` (as mesmas com `enabled` padrão `true`),
`src/steamzero/ui/qml/Main.qml:1565-1570` (ramo local que chama `refreshStatus` e mostra "Ambiente de emulação verificado")
- Test: `tests/unit/test_emulation_controller.py` + teste estático novo no padrão de
  `tests/unit/test_ui_contrast_inventory.py` (que já lê o texto de `Main.qml` e afirma sobre ele)

**Interfaces:** Produz: `plan_action`/catálogo do workspace como **fonte única** de `enabled` por id; `Main.qml` sem o
ramo que alega sucesso para `requirements.verify`.

- [ ] **Step 1: Teste de contrato (falha)** — os dois caminhos são **ambos alcançáveis em processo** e servem o mesmo
  `actionId` por superfícies diferentes: `desktop_dashboard.py:418` publica `build_emulation_workspace()` (lá medido:
  `requirements.verify` → `enabled=False`, label "Validar requisitos") e `adapters/emulation.py:874` sobrescreve a
  `areaData` da plataforma Switch com o `_area_data` do adapter (`:5691` → `enabled` padrão `True`, label "Validar
  novamente"). O contrato é *um valor por id entre as superfícies que a UI consome*:

```python
def _enabled_by_id(payload: object, found: dict[str, set[bool]]) -> None:
    if isinstance(payload, Mapping):
        if "id" in payload and "enabled" in payload:
            found.setdefault(str(payload["id"]), set()).add(bool(payload["enabled"]))
        for value in payload.values():
            _enabled_by_id(value, found)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for item in payload:
            _enabled_by_id(item, found)


def test_requirements_verify_has_one_publication_and_no_claimed_success(
    monkeypatch, tmp_path: Path
) -> None:
    domain: dict[str, set[bool]] = {}
    _enabled_by_id(build_emulation_workspace(), domain)          # superfície do desktop dashboard
    adapter: dict[str, set[bool]] = {}
    _enabled_by_id(_controller(monkeypatch, tmp_path).snapshot({"context": {}}), adapter)

    for action_id in ("requirements.verify", "firmware.import"):
        assert domain[action_id] == adapter[action_id], (action_id, domain[action_id], adapter[action_id])

    source = Path("src/steamzero/ui/qml/Main.qml").read_text(encoding="utf-8")
    branch = source[source.index('action.id === "requirements.verify"') :]
    assert "Ambiente de emulação verificado" not in branch[:2_000]
```

Nada aqui fixa `True` nem `False`: o que se proíbe é o mesmo id ter valores diferentes conforme a superfície. A âncora
QML é literal do arquivo (`Main.qml:1567`) e a segunda asserção é a que fecha o D-27 — nenhum ramo local pode alegar
"verificado" para um id que não emitiu requisição.

- [ ] **Step 2:** `.venv/bin/python tools/run_tests_isolated.py tests/unit/test_emulation_controller.py -k requirements_verify -q` → FAIL.
- [ ] **Step 3: Portão de decisão (unidade de produto).** Duas saídas, uma resposta do operador:
  - **6a — honestidade sem serviço:** publicar `enabled=false` com o motivo que o próprio produto já escreve
    ("Validação pela interface ainda não está conectada ao serviço.") e **remover** o ramo local de
    `requirements.verify`/`emulation.refresh` que hoje confunde os dois; o botão fica visível e explicativo.
  - **6b — conectar o serviço:** `requirements.verify` chama a verificação de requisitos que já existe no domínio
    (o mesmo caminho que popula `game_readiness`), com resultado real. Custo maior, fecha a lacuna de verdade.
- [ ] **Step 4:** aplicar a unidade aprovada; `firmware.import` (workspace `:689` × adapter `:5687`) recebe o mesmo
  tratamento. Testes: o contrato acima + o catálogo estático re-rodado no censo da Tarefa 14.
- [ ] **Step 5:** commit `fix(central): uma publicacao por id de acao e nenhum sucesso alegado sem execucao (D-27)`.

### Tarefa 7: D-28 — o OSD só publica o que o backend de sessão aceita

**Files:** `src/steamzero/domain/session_overlay.py:19-46` (`OSD_ACTIONS`, `_ACTION_LABELS`),
`src/steamzero/adapters/session_overlay.py:28` (`SESSION_ACTIONS = frozenset({"pause"})`) e suas `capabilities`,
`src/steamzero/adapters/session_control.py:395-412` (Modify: extrair o literal aceito para `ACCEPTED_ACTIONS`)
- Test: `tests/unit/test_session_overlay.py`

- [ ] **Step 1: Teste de fronteira (falha)** — hoje o conjunto aceito é um **literal dentro** de
  `SessionControlServer._dispatch` (`session_control.py:395-412`), então a primeira parte da tarefa é extraí-lo para
  `ACCEPTED_ACTIONS: frozenset[str]` no módulo, sem mudar comportamento. O teste importa a constante; antes da extração
  ele falha com `ImportError`, que é o vermelho correto aqui.

```python
def test_osd_publishes_only_actions_the_session_backend_accepts() -> None:
    from steamzero.adapters.session_control import ACCEPTED_ACTIONS

    orphans = set(OSD_ACTIONS) - ACCEPTED_ACTIONS - {"exit"}  # exit tem rota própria com confirmed=true
    assert not orphans, f"OSD publica ação sem porta no backend: {sorted(orphans)}"
```

- [ ] **Step 2:** rodar → FAIL listando `achievement, brightness, control, disc, fastForward, mute, network, rewind,
  screenshot, volume`.
- [ ] **Step 3: Portão de decisão (unidade de produto).** Três opções, com o custo de cada uma apresentado ao operador:
  - **7a — retirar do OSD** as 9 sem adapter (some a fileira inerte; `disc` vira `swapDisc`/`listDiscs`, que **existem**
    no backend).
  - **7b — publicar como indisponível com motivo** (mantém descoberta do que falta, mas a fileira continua sem função).
  - **7c — implementar adapter** para as que têm contraparte real no host (volume/mute/brightness via PipeWire;
    `screenshot` via o backend de captura já existente) — lote à parte, maior.
- [ ] **Step 4:** aplicar a unidade aprovada e **publicar as 5 aceitas que nunca viraram botão**: `listSaveStates`,
  `listDiscs`, `swapDisc`, `listPeripherals`, `resume` (este é a alternativa explícita ao `pause` alternável, que hoje
  é o único id de pausa).
- [ ] **Step 5:** testes + commit `fix(osd): publicar apenas acoes com porta no backend de sessao (D-28)`.

---

## Lote C — Coesão visual (D-29, D-06/D-24, D-07/D-25, rodapé, nomes acessíveis)

### Tarefa 8: gate automático de contraste dos temas do pacote (vermelho antes da paleta)

**Files:**
- Create: `tests/unit/test_theme_token_contrast.py`
- Consumes: `src/steamzero/themes/org.steamzero.{default,aura,steamdeck,asset-recipes-demo}/theme.json` (cadena
  `extends` = `org.steamzero.default`; `tokens.color` é o dicionário achatado, verificado no pacote)

- [ ] **Step 1: Escrever o gate com o mesmo cálculo da auditoria**

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cada tema do pacote deve sustentar o próprio texto — D-29 como gate, não como planilha."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

THEMES = sorted((Path(__file__).resolve().parents[2] / "src/steamzero/themes").glob("*/theme.json"))
TEXT = 4.5
NONTEXT = 3.0
PAIRS_TEXT = [
    ("text", "background"), ("text", "surface"), ("text", "surfaceRaised"),
    ("textMuted", "background"), ("textMuted", "surface"),
    ("accent", "background"), ("accentStrong", "background"),
    ("success", "background"), ("warning", "background"), ("danger", "background"),
]
PAIRS_NONTEXT = [("border", "background"), ("sidebar", "background"), ("focus", "background")]
EXEMPT = {("textDisabled", "background"), ("textDisabled", "surface")}  # WCAG 1.4.3 estado inativo


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    def rgb(h: str) -> tuple[int, int, int]:
        return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)

    l1, l2 = luminance(rgb(fg)), luminance(rgb(bg))
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def colors(theme: Path) -> dict[str, str]:
    data = json.loads(theme.read_text(encoding="utf-8"))
    merged: dict[str, str] = {}
    parent = data.get("extends")
    if parent:
        # THEMES vem de themes/*/theme.json, então o id do tema é o nome do diretório.
        merged.update(colors(next(p for p in THEMES if p.parent.name == parent)))
    # `org.steamzero.asset-recipes-demo` traz `tokens` sem chave `color`: herda inteiro do default.
    merged.update(data.get("tokens", {}).get("color", {}))
    return merged


@pytest.mark.parametrize("theme", THEMES, ids=lambda p: p.parent.name)
def test_semantic_tokens_clear_wcag_aa(theme: Path) -> None:
    palette = colors(theme)
    failures = []
    for fg, bg in PAIRS_TEXT:
        if (fg, bg) in EXEMPT or fg not in palette or bg not in palette:
            continue
        if ratio(palette[fg], palette[bg]) < TEXT:
            failures.append(f"{fg}/{bg} {ratio(palette[fg], palette[bg]):.2f}:1 < {TEXT}:1")
    for fg, bg in PAIRS_NONTEXT:
        if fg in palette and bg in palette and ratio(palette[fg], palette[bg]) < NONTEXT:
            failures.append(f"{fg}/{bg} {ratio(palette[fg], palette[bg]):.2f}:1 < {NONTEXT}:1 (não textual)")
    assert not failures, f"{theme.parent.name}: " + "; ".join(failures)
```

- [ ] **Step 2:** `.venv/bin/python tools/run_tests_isolated.py tests/unit/test_theme_token_contrast.py -q` → FAIL com
  **exatamente 11** casos nos quatro temas do pacote (medido nesta rodada, com este par listador):
  `default` 2 (`border` 1,63 · `sidebar` 1,13), `asset-recipes-demo` 2 (herda os mesmos dois do default),
  `aura` 3 (`accentStrong` 3,53 · `border` 1,44 · `sidebar` 1,03), `steamdeck` 4 (`accent` 2,91 · `focus` 2,91 ·
  `border` 1,63 · `sidebar` 1,13). **Não confunda com o 43 do `logs/19`:** lá entram também os dois temas derivados
  do host (`org.steamzero.01m2qznd` 12 + `org.steamzero.01m3w5a8` 14 = 26), que não estão no pacote, e 6 combinações
  medidas contra o fundo estático do componente (`#FCFCFC`), que um gate de token não alcança. 26 + 6 + 11 = 43 — se a
  sua conta não fechar com 11, o gate está medindo outra coisa; conserte o gate, não a alegação.
- [ ] **Step 3:** commit do gate vermelho junto da Tarefa 9 (não se commita suíte vermelha sozinha).

### Tarefa 9: D-29 — paletas que sustentam o próprio texto (aprovação por tema)

**Files:** `src/steamzero/themes/org.steamzero.default/theme.json`, `…/org.steamzero.aura/theme.json`,
`…/org.steamzero.steamdeck/theme.json`, `src/steamzero/domain/themes.py`, `src/steamzero/ui/qml/ThemeBridge.qml`
(fallbacks), `tests/unit/test_ui_disabled_contrast.py`, `tests/unit/test_default_theme.py`, `tests/unit/test_theme_aura.py`

- [ ] **Step 1: Gerar a mesa de decisão, não uma decisão sua**

Para cada tema reprovado, calcule o candidato mínimo movendo **só o canal de luminância** do token, preservando matiz e
saturação, e apresente ao operador: tema, par, valor atual, valor proposto, razão nova, e o que muda visualmente. Use o
`ratio()` da Tarefa 8. Nada de "escolher cor no editor": o editor de tema (`Esquema de cor`/`Escolher cor`) **não foi
exercitado** nesta prova (limite F-2/aberta 9) — se a solução exigir o editor, isso é outra frente.

- [ ] **Step 2: Portão por unidade.** Um tema é uma unidade de design. Aplique somente os temas aprovados; os
  reprovados restantes permanecem listados como abertos com a razão medida.

- [ ] **Step 3: Regra estrutural, não parche por página** (herança de `Popup`, composição de superfície e `background:`
  próprio de 22 arquivos): a correção entra em `theme.json` + `ThemeBridge.qml`, e **não** em cores fixas por página.
  Se descobrir que o problema é a herança do `Popup`, corrija ali e registre o achado — é a lição do §V1 do
  `IMPLEMENTATION-PROMPT.md`.

- [ ] **Step 4:** `.venv/bin/python tools/run_tests_isolated.py tests/unit -k "contrast or theme" -q` → PASS com os
  temas aprovados; commit `fix(theme): tokens semanticos dos temas aprovados atingem AA (D-29)`.

- [ ] **Step 5:** sem captura, não alegue "visualmente resolvido". A classe D-01 (28 `DarkButton`, 245 `QQC.Button`
  crus, 73 bindings de `palette.buttonText`) fica registrada como **não tratada** salvo aprovação explícita de mudar o
  componente.

### Tarefa 10: D-06/D-24 — "herdar AURA" precisa resolver AURA, e o catálogo do host precisa ver o tema do pacote

**Files:** `src/steamzero/domain/themes.py` (resolver `inherit-aura`), `adapters/theme_catalog.py`,
`ui/qml/Main.qml` (editor de aparência), `tests/unit/test_theme_aura.py`,
`tests/integration/test_theme_catalog_routes.py`

Fato medido: `appearance.mode="inherit-aura"` resolve para `org.steamzero.default` claro (`logs/json/gb-overlay-pos-save.json`);
e o botão "Herdar AURA neste menu" respondeu `E-THEME-NOT-FOUND` embora `themes/org.steamzero.aura/theme.json` exista no
pacote da release — o catálogo do host só tinha `org.esde.*` e dois `org.steamzero.<ULID>`.

- [ ] **Step 1:** teste de resolução: `mode == "inherit-aura"` ⇒ `themeId` do AURA do pacote, com o fundo real do
  `theme.json` empacotado (`#0b1020` em `tokens.color.background`, medido nesta rodada), não o `#e7eceb` do default.
  Teste de catálogo: tema empacotado é visível ao editor sem cópia no host.
- [ ] **Step 2:** FAIL (hoje os dois caem no default / `E-THEME-NOT-FOUND`).
- [ ] **Step 3:** implementar a resolução e a leitura de temas do pacote; **não** escreva em
  `~/.local/share/steamzero/themes` para esconder o erro.
- [ ] **Step 4:** `tests/unit/test_theme_aura.py tests/integration/test_theme_catalog_routes.py -q`; commit
  `fix(theme): inherit-aura resolve o AURA empacotado e o catalogo do host o ve (D-06, D-24)`.

### Tarefa 11: D-07/D-25 — o tema não muda por menu, e recusa não deixa "não salvo"

**Files:** `ui/qml/**` (superfícies por menu), `domain/themes.py`, editor de aparência (undo/dirty flag),
`tests/integration/test_qml_visual_capture.py` (goldens), `tests/qml/check_experience_journey.qml`

- [ ] **Step 1:** reproduzir estaticamente primeiro: localize onde cada seção escolhe a superfície de fundo e por que
  Plataformas↔Jogos alternam claro/escuro (capturas L17…L20, L28). Se a causa for token ausente por menu, é da
  Tarefa 8/9; se for binding divergente, é daqui.
- [ ] **Step 2:** teste de golden: dois menus, mesma jornada, mesmo `background` nos pixels offscreen.
- [ ] **Step 3:** `E-THEME-NOT-FOUND` (recusa com "nenhuma mudança foi feita") **não** pode setar dirty nem habilitar
  Desfazer — assert no estado do editor antes/depois da recusa (D-25, capturas L35 vs L36).
- [ ] **Step 4:** gates focados; commit separado por defeito: `fix(ui): tema consistente entre menus (D-07)` e
  `fix(studio): recusa nao marca o documento como nao salvo (D-25)`.

### Tarefa 12: rodapé da sessão — D-10, D-12, D-22

**Files:** `src/steamzero/ui/qml/launcher/LauncherMain.qml` (rodapé, `:241-261`), `LauncherSessionOverlay.qml`,
`adapters/launcher_ui.py`, `tests/qml/launcher/check_launcher_session_osd.qml`,
`tests/integration/test_qml_handheld_offscreen.py`

- [ ] **Step 1:** em 1280×801 com ações de sessão visíveis, a linha de atalhos não pode ser cortada (D-10): golden com
  `objectName` medido, não inspeção subjetiva.
- [ ] **Step 2:** com sessão `running`, os botões Pausar/Salvar/Sair devem nascer `ENABLED|FOCUSABLE` — sem depender do
  botão "Atualizar" (D-12; a árvore AT-SPI de `logs/17` é a régua).
- [ ] **Step 3:** sessão ativa sem item selecionado ainda expõe Retomar e Sair no rodapé (D-22): o rodapé hoje diz
  "Selecione um jogo com uma sessão observável" enquanto o OSD oferecia as duas ações habilitadas na mesma janela.
- [ ] **Step 4:** testes + commits `fix(launcher): rodape usa a sessao observada, nao a selecao (D-12, D-22)` e
  `fix(launcher): atalhos cabem com as acoes de sessao visiveis (D-10)`.

### Tarefa 13: D-08/D-19/D-21 — o que a API sabe, a tela também sabe

**Files:** `adapters/launcher_ui.py`, `ui/qml/launcher/LauncherJourney.qml`/`LauncherMain.qml`,
`adapters/session_overlay.py` (`thumbnailUrl`), `tests/integration/test_launcher_app.py`,
`tests/qml/launcher/check_launcher_accessibility.qml`

- [ ] **Step 1:** o 409 estruturado de lançamento precisa aparecer na sobreposição de jornada, com `code`, motivo e a
  única ação que resolve (D-08) — hoje o rodapé mostra o normal e o erro vive só na API.
- [ ] **Step 2:** dois controles chamados "Jogar" na mesma janela é armadilha de foco (D-19): nomes acessíveis
    distinguíveis (ex.: "Jogar <título>" na página de jogo e "Continuar jornada" na página de jornada) + teste estático
    no `check_launcher_accessibility.qml` que afirme a unicidade por janela.
- [ ] **Step 3:** miniatura existe em `~/.local/share/steamzero/saves/states/<core>/*.png` (6 418 bytes) e o overlay
    devolve `thumbnailUrl=""` com `thumbnailFallback=true` (D-21) — publicar a URL real do arquivo já escrito.
- [ ] **Step 4:** testes + commits separados por defeito.

---

## Lote D — Fechamento governado

### Tarefa 14: checkpoint único dos gates e da evidência

- [ ] **Step 1: Re-rodar os dois censos e medir o delta real**

```bash
python3 docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/harness/sz_censo.py . \
  > docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/10-censo-pos-lote.txt
python3 docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/harness/sz_cores.py \
  > docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/11-cores-pos-lote.txt
sha256sum docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/*.txt > docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/12-hashes.txt
```

Esperado: `ações de OSD sem porta` = 0 (ou o subconjunto aprovado na Tarefa 7), `publicações com enabled contraditório`
= 0, `reprovações` do `sz_cores.py` = 43 menos os casos dos temas aprovados (a régua do **pacote** é o gate da Tarefa 8:
11 casos, repartidos 2/2/3/4 entre default/asset-recipes-demo/aura/steamdeck; os outros 32 vêm dos dois temas derivados
do host e das combinações contra o fundo estático do componente, que este lote não toca se não houver aprovação de
componente). **Reconcilie a conta**: cada número que caiu tem de ter o commit e o teste que o derrubaram; número que
caiu sem teste é alegação.

- [ ] **Step 2: Gates integrais (uma vez)**

```bash
.venv/bin/python tools/run_tests_isolated.py tests -q
.venv/bin/ruff check src tools tests
.venv/bin/ruff format --check src tools tests
.venv/bin/mypy src
make independence boundaries
make status-check
```

Registre contagens (passed/skipped/failed), o tempo, se o runner saiu 0, e o estado do state home. Se aparecer
`W-TEST-REAL-STATE-EXTERNAL-WRITER`, atribua com honestidade (o daemon da release instalada escreve; não encerre serviço
nem enfraqueça o guard) e declare a atribuição degradada.

- [ ] **Step 3: Status e views**

Atualize o item em `docs/status/items/` com evidência `test`/`diagnostic` por tarefa concluída (sem promover eixo que só
tem teste estático — a liberação física é do operador), o cartão de workstream, regenere
`.venv/bin/python tools/project_status.py render --write`, e rode `check` de novo.

- [ ] **Step 4: WORKLOG (append) e commit documental**

```bash
.venv/bin/python tools/project_status.py check
git add docs/
git commit -m "docs(status): fechar o lote de coesao visual com censos reconciliados"
```

Um commit **funcional** por tarefa (já feitos) e um **documental** aqui — nunca mistos.

### Tarefa 15: o que fica explicitamente aberto (não simule)

Entregue uma tabela final com estas linhas e mais o que você não alcançou — critério → comportamento observado →
evidência → release → limite:

- Prova **visual** de qualquer correção deste lote: exige autorização nomeando a injeção de entrada ou sessão
  descartável; sem PNG, a linha é "corrigida no código, sem prova física".
- B-7 (retorno com foco e rolagem), B-10 (fades), C-4 (sessão presa) — re-execução física pendente.
- 22 dos 25 adapters não testados; 12 sistemas sem `game_readiness` jogável nesta máquina (`logs/09`).
- Gamepad/touch do Deck (`deck.input.keys=warn`).
- `Esquema de cor`/`Escolher cor` nunca exercitados — o editor pode **produzir** combinações piores que as 43 medidas.
- A classe D-01 em 245 `QQC.Button` crus e 22 arquivos com `background:` próprio (D-29 trata dos tokens, não do
  componente).
- Host: `/opt/steamzero/current` permanece `2.0.0rc1-2b7eb541b4a5`; nada foi instalado, revertido ou ciclado; o resíduo
  da prova (3 pares de save-state + jornada de teste inerte) permanece intocado e certificado em `logs/13`.

## Autorevisão do plano (feita pelo autor)

1. **Cobertura da spec:** D-17→T1, D-23→T2/T3, D-26→T4, D-20→T5, D-27→T6, D-28→T7, D-29→T8/T9, D-06→T10, D-24→T10,
   D-07→T11, D-25→T11, D-10→T12, D-12→T12, D-22→T12, D-08→T13, D-19→T13, D-21→T13. Sem tarefa: D-01…D-05 (Studio de
   Jornadas, `logs/06`) e D-09 (18 entradas não lançáveis) — ficam fora deste escopo porque D-01…D-05 pertencem à frente
   do Studio e D-09 é acervo/preparação, não UI; registre como aberto em vez de arrastar.
2. **Placeholders:** o único valor genuinamente em aberto é a cor candidata por tema (T9), porque ela é decisão do
   operador no portão de unidade — o passo dá o critério (mover só luminância, preservar matiz/saturação) e a régua
   (`ratio()` da Tarefa 8). Todos os demais passos têm fixture, arquivo e asserção nomeados; não há "TODO" escondido.
3. **Consistência de tipos:** o campo novo de D-17 chama-se `diagnosticId` na resposta e no journal (`correlation_id`);
   `written` é `{"slot": int, "path": str, "exists": bool}` (sem `written` quando a recusa é prévia ao envio); o
   conjunto aceito de sessão vem do literal de `session_control.py:395-412`, extraído para `ACCEPTED_ACTIONS` na Tarefa
   7, e é a única fonte usada em T2 e T7; `_owner_and_server` é definido na Tarefa 2 e consumido nas Tarefas 3 e 4.

## Execução

Dois caminhos: **(1) Subagent-driven** — um subagente novo por tarefa com revisão entre tarefas (recomendado: cada
tarefa tem teste e commit próprios); **(2) Inline** — executar em lote com checkpoints nos portões de decisão
(Tarefas 3, 6, 7, 9). Em ambos, os portões de decisão são **humanos**: o operador aprova a unidade antes da edição.

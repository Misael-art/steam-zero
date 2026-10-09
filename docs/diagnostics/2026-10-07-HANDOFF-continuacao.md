# Handoff — continuação do diagnóstico de jornadas reais (2026-10-07)

Leia primeiro: `AGENTS.md`, depois `2026-10-07-diagnostico-jornadas-reais-ux.md` (16 pontos, estado de cada um).
Filosofia do operador: melhor experiência do usuário — fluidez e automação. "Jogar" resolve sozinho o que for
seguro; quando não puder, diz o motivo e a única ação que resolve. Ordem de trabalho: do mais complexo ao menos.

## Estado do checkout

- Branch `codex/r05-component-operation-trace-2026-10-05`, HEAD `31f29963` (base `213124ed`), checkout único.
- **Nada commitado, nada instalado, nenhum jogo iniciado, sem push.** Release ativa: `2.0.0rc1-213124ed513b`.
- Handoff serial dos paths reservados (emulation.py, launcher/*, themes) foi autorizado pelo operador na thread
  e registrado em `docs/status/workstreams/diagnostico-jornadas-ux-2026-10-07.json`. **Devolver os claims** (Biblioteca:
  `emulation.py`; Jornada: `launcher/*`, `themes.py`, QML) após o commit.
- Existem deltas documentais de outros workstreams no checkout (status/items, STATUS, COVERAGE, ROADMAP, ACTIVE-WORK).
  Não os coloque no commit funcional.

## O que foi feito (arquivo → efeito → teste)

| Mudança | Arquivos | Testes |
|---|---|---|
| Jogar projeta sozinho a BIOS já importada (`_prepare_launch`); prontidão trata "só falta projetar" como pronta (`projection_ready`) | `adapters/emulation.py` | `tests/unit/test_amiga_bios_launch_preflight.py` |
| `steamzero emulation readiness --game-id` (somente leitura) | `cli/main.py` | `tests/integration/test_cli_emulation.py` |
| `steamzero emulation prepare --game-id` + `prepare_game`/`canPrepare` (extração governada de archive, sem iniciar jogo) | `adapters/emulation.py`, `cli/main.py` | idem acima |
| `POST /launch` consulta a prontidão antes do spawn (409 com código+motivo, home vira `~`); archive bloqueado dispara preparação em segundo plano (`LAUNCHER-PREPARING-001` / `PREPARE-FAILED-001`) | `adapters/launcher_ui.py`, `launcher/app.py`, `adapters/launcher_process.py` (`query_product`) | `tests/integration/test_launcher_app.py` |
| `textDisabled` em AA: aura `#808aa3`, default `#5c6a70` (+ fallbacks do `ThemeBridge.qml`) | `themes/*/theme.json`, `domain/themes.py`, `ui/qml/ThemeBridge.qml` | `tests/unit/test_ui_disabled_contrast.py` |
| Pasta de tema legada (sem `theme.json`) é reportada como preservada, não "não instalado" | `domain/theme_scene.py` | `tests/unit/test_theme_import_to_runtime_journey.py` |
| Cinema com `objectName`/`Accessible.name` | `ui/qml/launcher/LauncherCinema.qml` | `tests/integration/test_qml_handheld_offscreen.py -k launcher` |
| Descoberta de save normal do RetroArch Flatpak (feita antes, outro agente) | `adapters/preservation.py` | `tests/integration/test_preservation.py` (15) |

Lição: o gate `make boundaries` proíbe `subprocess` fora de `core.proc`/`adapters`; por isso a consulta ao produto vive em
`adapters/launcher_process.query_product`.

## Verificação feita

Verdes: `ruff check`, `ruff format --check` (700), `mypy src` (303), `make independence boundaries`, e os testes focados
(controller/CLI/BIOS 170; Launcher 41; temas 120; QML launcher 9).
**Não concluída:** suíte integral (`.venv/bin/python tools/run_tests_isolated.py tests -q`) — o sistema a matou por
falta de memória; não é falha de teste. Antes de rodar, libere memória e não a reinicie sem o operador pedir.
`make status-check` continua falhando nos 5 digests dos custodians (Launcher, Biblioteca, Roadmap Continuation,
Theme Engine, Theme Studio); não recertifique para esconder.

## O que falta (por prioridade)

1. Rodar a integral (memória livre) e `make status-check`; regenerar views de status; criar `docs/status/items/` para
   a capacidade de prontidão/preparação (AGENTS §2 exige item por capacidade).
2. Commits separados: funcional (src+tests) e documental; sem push sem autorização.
3. Validar no host (precisa de release candidata + autorização/token, AGENTS §1): se o id do jogo segue válido após o
   rescan da preparação; extração real de Amiga/X68000; BIOS auto-projetada; mensagem do 409 no Launcher.
4. UX pendente: estado do jogo no cartão *antes* do clique e barra de progresso da preparação (QML); hoje só há mensagem.
5. Bloqueados fora do código: core Saturn/Neo Geo CD (operador fixar URL+SHA-256 no lock), captura/input
   (`ydotool` incompatível — sem PNG não há prova visual), Vita3K, Xbox/xemu config, 3DO BIOS não importada,
   PS3 firmware, credencial ScreenScraper, Switch `stateTarget` (precisa de sessão real), sync/casting.
6. Abertos de baixa prioridade: migração automática de temas legados; token de família tipográfica (schema reservado);
   medir contraste em pixels.

## Não faça

Instalar/reverter release, `sudo`, rodar a integral várias vezes, alegar prova visual sem PNG, inventar hash de core,
apagar pacote de tema pessoal, enfraquecer teste.

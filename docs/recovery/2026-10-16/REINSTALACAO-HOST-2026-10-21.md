# Reinstalação do host — continuidade a partir do GitHub (2026-10-21)

O operador vai formatar o host (BigLinux/Manjaro) e retomar o projeto só pelo
GitHub. Este documento é o ponto de entrada da retomada: o que estava no host,
o que foi preservado onde, como reconstruir o ambiente e como validar que nada
se perdeu. Leia junto com `README.md`, `PLANO.md` e `PROXIMO-AGENTE.md` deste
diretório e com `AGENTS.md`.

## 1. Fotografia no momento da formatação

| Item | Valor |
|---|---|
| Repositório | `Misael-art/steam-zero` (público) |
| `main` | `0979765171a32e7532f1f650a889962ba375d58d` (PR #264), push-run `39636317805` verde |
| Linha de trabalho | `codex/product-recovery-2026-10-16`, mesmo conteúdo de `main` mais commits documentais |
| Release ativa no host apagado | `2.0.0rc1-3f87657c0a6c` (main `3f87657c`, wheel `539db839…`), rollback `2.0.0rc1-60f2d590481f` |
| Candidata não instalada | `2.0.0rc1-0979765171a3` (main `09797651`, wheel `618d0a7a…`) — `PENDENTE_CREDENCIAL` |
| R0/R1 | Fechado e instalado (`SZ-RECOVERY-R0-R1-CENTRAL`, complete/released/dev/degraded/installed) |
| R2 | Slices 1–2 integrados em `main`, sem prova instalada (`SZ-RECOVERY-R2-GAME-DATA`) |

O estado canônico continua sendo `docs/status/items/` e
`docs/status/workstreams/`; esta tabela é só a fotografia.

## 2. O que foi preservado e onde

**No GitHub (nada de Git ficou só no host).** Auditoria de 370 branches locais e 5
stashes: apenas 6 branches e os 5 stashes tinham commits fora de qualquer ref
remota. Todos foram publicados sob `archive/host-2026-10-21/`:

- `archive/host-2026-10-21/codex/integration-axis-honesty-2026-09-25`
- `archive/host-2026-10-21/codex/ui-control-matrix-parallel-2026-09-25`
- `archive/host-2026-10-21/codex/media-registry-contract-2026-09-25`
- `archive/host-2026-10-21/codex/library-derived-cleanup-universal-2026-09-25`
- `archive/host-2026-10-21/codex/controls-profile-scope-honesty-2026-09-25`
- `archive/host-2026-10-21/tmp/rc01-ux03-oldstack`
- `archive/host-2026-10-21/stash-0` … `stash-4` (commits de stash; o primeiro pai é a
  base, o segundo é o índice, o terceiro, quando existe, guarda os não rastreados)

Varredura de segredos nesse conteúdo: só falsos positivos (tokens de design,
tokens de confirmação de plano, teste que exige ausência de `apiKey`). Depois do
push, nenhuma ref local tinha commit fora do GitHub.

**Fora do GitHub, por decisão.** Não vão para um repositório público:

- `~/steamzero-continuidade-2026-10-21/` (20 MB, com `SHA256SUMS`):
  - `evidencia-privada-r0-r1-r2.tar.zst`: diretório privado do executor
    (`~/.cache/phasezero/agent-tmp/steamzero-r0-r1-physical-hvc36cbb`) sem os bundles
    de release. Contém as evidências 19–56 do executor anterior, entre elas as marcadas
    `private`, com caminhos do host. Também traz o perfil isolado de teste, com as ROMs
    sintéticas `R0-R1 NES.zip` e `R0-R1 AMIGA.zip`, e os auxiliares de GUI (`gui/`).
  - `plugins-agents.tar.zst`: `Projects/Steam Zero/plugins` (`codex-quota-resume`,
    que não é repositório Git) e `.agents`.
  - `claude-memoria-projeto.tar.zst`: memória do Claude para o projeto (vazia hoje).
- Os bundles de release ficaram de fora porque se reconstroem do GitHub
  (`tools/release_host.py prepare` no SHA exato e com o run verde).

**Responsabilidade do operador — copiar para fora do host antes de formatar:**

| Caminho | Tamanho aprox. | Conteúdo |
|---|---|---|
| `~/emulation` | 341 GB | ROMs, BIOS e saves do usuário (fonte das provas físicas; nunca baixar ROM/BIOS) |
| `~/.local/share/steamzero` | 2,0 GB | Dados da Central: biblioteca, mídia, backups de save |
| `~/.local/state/steamzero` | 1,4 GB | `state.db` (inclui `game_metadata` v23), jornadas |
| `~/.config/steamzero` | 76 KB | Preferências |
| `~/steamzero-continuidade-2026-10-21` | 20 MB | Pacote da seção acima |
| `~/.ssh`, `~/.gnupg` | — | Chaves |
| `~/.codex` (inclui `RTK.md`), `~/.claude`, `~/.config/ai-memory`, `~/.local/share/ai-memory` | — | Instruções e memória dos agentes; o prompt do programa exige `~/.codex/RTK.md` |

`/opt/steamzero` (7,9 GB, 188 releases) **não** precisa de cópia: a instalação
nova recomeça pelo fluxo governado. O histórico de releases e o rollback
anterior à formatação deixam de existir no host; isso é esperado e fica
registrado aqui.

## 3. Reconstruir o ambiente

1. Pacotes do sistema (os nomes são os do Manjaro/BigLinux observados no host):
   `git github-cli python qt6-base qt6-declarative qt6-svg qt6-multimedia
   qt6-shadertools qt6-5compat pyside6 python-gobject at-spi2-core spectacle
   kdotool-git bigsudo zstd retroarch` e os cores libretro usados nos aceites
   (Mesen para NES, PUAE para Amiga).
2. `ydotool`/`ydotoold` estavam em `~/.local/bin`; reinstale e rode o daemon
   **em nível de usuário** com socket privado, como era antes. Só as provas de GUI
   precisam disso.
3. `gh auth login` e configuração de SSH.
4. Restaurar `~/.codex`, `~/.claude` e a memória `ai-memory` do backup.
5. Clonar no **mesmo caminho canônico** exigido pelo `AGENTS.md`:
   ```
   mkdir -p "$HOME/Projects/Steam Zero/Canonical"
   git clone git@github.com:Misael-art/steam-zero.git "$HOME/Projects/Steam Zero/Canonical/2026-09-21"
   cd "$HOME/Projects/Steam Zero/Canonical/2026-09-21"
   git switch codex/product-recovery-2026-10-16
   make venv
   ```
6. Restaurar `~/emulation` e, se for reaproveitar a biblioteca, os três diretórios
   `steamzero` acima.
7. Opcional: extrair o pacote privado em `~/.cache/phasezero/agent-tmp/` para ter as
   evidências 19–56 e o perfil isolado de teste.

## 4. Validação pós-formatação

Rodar do checkout canônico; cada linha tem o resultado esperado.

| Verificação | Comando | Esperado |
|---|---|---|
| Base | `git rev-parse origin/main` | `0979765171a3…` ou descendente |
| Linha de trabalho | `git log -1 origin/codex/product-recovery-2026-10-16` | Commit documental que inclui este arquivo |
| Arquivo publicado | `git ls-remote origin 'refs/heads/archive/host-2026-10-21/*' \| wc -l` | `11` |
| Ambiente | `make venv && .venv/bin/python -c "import steamzero"` | Sem erro |
| Gates estáticos | `make format-check lint boundaries independence typecheck status-check` | Todos OK |
| Suíte integral (nunca rodada localmente nesta sessão por falta de memória) | `env -u PYTEST_DEBUG_TEMPROOT .venv/bin/python tools/run_tests_isolated.py tests -q --cov=steamzero --cov-report=term` | Verde, cobertura ≥ 85% (CI em `main`: 85,29–85,30%) |
| QML | `.venv/bin/python tools/run_tests_isolated.py tests/integration/test_qml_handheld_offscreen.py -q` | Verde |
| Integridade do pacote | `cd ~/steamzero-continuidade-2026-10-21 && sha256sum -c SHA256SUMS` | Tudo `OK` |
| Release no host novo | `PYTHONPATH=src .venv/bin/python tools/release_host.py inspect` | Nenhuma release; instalação parte do zero |

Registrar o resultado no `WORKLOG.md` como sessão nova (append-only).

## 5. Retomada do trabalho

1. **Primeira instalação no host novo.** Não há release ativa nem rollback.
   Rodar `release_host.py prepare` no tip de `main` com o run verde e depois
   `verify-bundle`. Confirmar com o `inspect` como o instalador trata a primeira
   instalação sem rollback antes de executar `install`: não inventar
   `--rollback-release`. A senha do operador vai no bigsudo, nunca no chat.
2. **Aceite instalado de R2**, no perfil isolado e com fixture rotulado:
   - "Dados do jogo" no NES;
   - "Conteúdo do jogo" com patches, cheats, saves, save states, RetroAchievements e
     HD packs, sem updates, DLC nem mods;
   - linha selecionada legível;
   - seletor de plataforma mantido após uma ação;
   - Amiga e DP-1.
3. **Lacunas abertas de R2:** `GAP-R2-CONTENT-ADAPTERS` (aplicar de fato patches,
   cheats, conquistas e HD packs), `GAP-R2-LAUNCHER-PROJECTION` (`launcher_catalog.py`
   sob claim ativo de WS journey-launcher-session: pedir handoff),
   `GAP-R2-REMOTE-PROVIDER-PROOF` (credencial ScreenScraper) e o residual do bloco
   "Saves e shader cache" do Switch exibido para NES.
4. **Claims:** `Main.qml` está cedido a WS-2026-10-RECOVERY-R2-GAME-DATA; devolver a
   WS-2026-10-STUDIO-DRAFT-HISTORY no fechamento de R2.
5. **Dados de teste:** se o perfil isolado não for restaurado, recriar um perfil com
   XDG próprio e `STEAMZERO_NO_DAEMON=1`, usando ROMs do usuário em `~/emulation` sem
   alterá-las, ou ROMs sintéticas. Não baixar ROM nem BIOS.

## 6. Lições operacionais desta sessão (para o próximo executor)

- `pgrep -f`/`pkill -f` com o texto do próprio comando derruba o shell; mate por PID.
- A rolagem do painel lateral do jogo não foi alcançada por ydotool/AT-SPI em
  multi-tela; para capturar o painel inteiro, redimensionar a janela além da altura
  da tela (`kdotool windowsize <id> 1920 1900`) e capturar com `spectacle -b -n -a`.
- `test_emulation_ui_has_no_switch_specific_routing_or_copy` proíbe a palavra
  "switch" em `Emulation.qml` e `Main.qml`, inclusive em comentários e nomes.
- Migração nova exige atualizar todos os asserts de versão final
  (`test_state.py`, `test_multidisc_artifacts.py`).
- Pouca memória livre no host fez o Claude Code encerrar jobs em background; com
  menos de ~2 GiB livres, a suíte integral local não completa.

# 2026-11-05 — Saída RetroFE, entrada decimal por locale e piso do Pillow

Branch `codex/product-recovery-2026-10-16`, PR #268. Executor serial (Claude Code).
Nível de prova: **fonte + Qt offscreen** com dados sintéticos. Sem instalação,
sem compositor real, sem hardware, sem alteração do host.

## Commits

| Commit | Conteúdo |
|---|---|
| `a9bd7edc` | Gate visual QML: verificação de visibilidade da prévia aceita prévia mais alta que a viewport (falha do run 42012024471 em `08306596`). |
| `38ff2be9` | Studio: entrada decimal independente da locale do sistema. |
| `1659e72d` | Temas: transição de saída RetroFE (`onExit`) no renderizador comum e no Launcher. |
| `b46eb04d` | Build: `Pillow>=13.0.0`. |

## 1. Gate visual QML do checkpoint anterior

- Reprodução: `test_04_jornada_salva_e_previsualiza_cena_retrofe` reprovava somente
  no CI ("prévia não está visível na área do inspetor"); local passava.
- Causa provável (geometria do CI não observada): prévia mais alta que a viewport
  do inspetor torna "inteiramente visível" insatisfazível. Com `QT_SCALE_FACTOR=1.5`
  o caso passa após a correção; a mensagem agora registra as alturas.

## 2. Saída RetroFE

- Antes: `SceneEsdeView.unsupportedTimelines` listava `exit` do fixture RetroFE.
- Agora: `timeline(element, event)` valida `enter` e `exit` com os mesmos limites
  (32 blocos, 16 clipes, 60 s por bloco, `alpha/x/y/nop`, curvas allowlisted).
  `playExit()` parte do estado atual, teto `exitBudgetMs` = 1500 ms e sinal
  `exitFinished(completed)`; `cancelExit()` restaura o estado final de entrada;
  movimento reduzido assenta sem animação. Endpoints x/y de saída são
  normalizados como os de entrada; a cena armazenada fica intacta.
- Launcher: `activated` é emitido antes; a saída só acompanha e nunca atrasa a
  operação de sessão. Navegação ou retorno à tela restauram a cena.
- Eventos sem suporte continuam identificáveis: o fixture ganhou
  `onHighlightEnter`, mantendo o banner de perda do Launcher e a linha da prévia.
- Provas: `tests/qml/check_theme_scene_runtime_e2e.qml` (saída, interrupção,
  movimento reduzido, teto, Launcher), `tests/qml/check_scene_esde_view.qml`,
  `tests/unit/test_theme_scene.py` (normalização e entradas malformadas).
- Fora do aceite: execução RetroFE `exit` ao trocar de coleção/menu (o Launcher só
  dispara na ativação), eventos `highlight*`, `menu*`, `game*`, `playlist*`.

## 3. Entrada decimal em pt-BR (achado pelo gate integral)

- Reprodução: `test_native_wheel.py::test_wheel_authoring_controls_use_real_bridge_and_persist`
  reprovava com `LANG=pt_BR.UTF-8` (valor 1 em vez de 0.5) e passava em `C.UTF-8`;
  falhava também com as mudanças deste lote guardadas (pré-existente).
- Causa: `DoubleValidator` segue a locale; em pt-BR bloqueava "." sem aviso.
- Correção: campo de receita aceita "." e ","; fora do intervalo mantém o valor e
  mostra aviso. `AuthRangeSpinBox` mantém exibição e leitura pela locale
  (agrupamento incluído) e usa "." como decimal quando a locale não lê o texto.
- Regressão: caso `wide-pt-BR` no teste da wheel; vermelho sem a correção.

## 4. Alertas de dependência

- Os 41 alertas abertos (5 críticos, 23 altos, 13 moderados) são todos Pillow
  `< 13.0.0`, apontando o pin `Pillow==12.3.0` de `requirements-runtime.in` na
  `main`. A branch já fixa `13.0.0` em `.in` e locks; os alertas fecham com o merge
  do PR #268 (merge exige autorização própria).
- Release ativa `2.0.0rc1-59ecc2d8f0f6`: venv isolada
  (`include-system-site-packages = false`) com `pillow-13.0.0` — sem exposição.
- Pillow 12.3.0 do sistema pertence ao gerenciador de pacotes da distribuição;
  não é tocado.

## Gates

Logs locais (não versionados) em `build/agent-runs/exit-motion-gates-0824/` e
`build/agent-runs/exit-motion-gates-r2/`. Recursos antes: MemAvailable ≈ 6,4 GiB,
125 GiB livres, carga ≈ 2,3; `nice -n 10`.

| Gate | Resultado |
|---|---|
| Integral r2 (`tools/run_tests_isolated.py tests -q --cov --cov-branch`) | 7349 passed, 48 skipped, 4 failed, 51m52s |
| Falhas r2 | 3 por tempo sob carga (2× `TimeoutExpired`, 1 refresh do dashboard), passam isoladas (90 passed); 1 `test_project_status` (digests, resolvida neste commit documental) |
| Cobertura com branches | 85,8682% no integral; 85,8765% após anexar reexecuções focadas e 2 testes novos de `theme_scene` (`--cov-append`); referência 85,8721% |
| pt-BR (wheel + autoria) | rc=0 |
| `ruff check`, `ruff format --check`, `mypy src`, `make independence boundaries` | rc=0 |
| `make status-check` | verde após renovação dos digests |

O integral r1 (antes da correção de locale) teve 7349 passed / 3 failed, cobertura
85,85%. Nenhum teste foi removido ou enfraquecido; contratos alterados: `exit`
deixou de ser "sem suporte" e o fixture ganhou `onHighlightEnter`.

## Pendências externas

Instalação, compositor real, controle físico e captura PNG da release instalada
continuam fora deste lote; merge do PR #268 exige autorização.

## Lote 2 (após o merge do PR #268 em `c5819591`)

| Commit | Conteúdo |
|---|---|
| `92c79da5` | Tetos limitados de espera em três testes que estouraram sob carga (12→30 s, 30→60 s, 10→20 s); isolados levam 1–20 s; porta livre conferida. |
| `8331fa87` | Saída do tema ao trocar coleção: coleção nova ativa na hora; cópia não interativa da anterior toca a saída por cima, teto 1,5 s; movimento reduzido sem cópia. |
| `a0d5f422` | `onHighlightEnter` na mudança de seleção; eventos partem do valor exibido; cópia de saída assenta ao ficar visível (8331fa87 passava por tempo). Fixture usa `onMenuEnter` como exemplo sem suporte. |

- Merge do PR #268: CI do `f4617285` verde nos 8 jobs; merge commit `c5819591`
  com `--match-head-commit`; CI push da `main` (run 42040231859) verde nos 8 jobs.
- Integral do lote 2: 7354 passed, 48 skipped, 1 falha (`test_project_status`,
  digests, resolvida neste commit), 41m13s; cobertura com branches **85,8737%**
  no integral puro (referência 85,8721%); pt-BR, ruff, format, mypy, independence
  verdes. Fonte + Qt offscreen.
- Ainda sem suporte e sinalizados como perda: `menu*`, `game*`, `playlist*`,
  `highlightExit`.

## Release do `c5819591` — bloqueada por autenticação

- `release_host.py prepare --commit c58195919b07a799c67ac716ceb9e3ca99ba3f12
  --run-id 42040231859 --output build/release/c5819591`, com o checkout no commit
  exato (árvore limpa) e `GIT_TERMINAL_PROMPT=0`: recusado com
  "autenticação do GitHub falhou … gh auth login". O `gh` do host não tem login
  armazenado; o agente não inicia autenticação.
- Primeira tentativa travou no `git fetch` interno (prompt de credencial, 120 s);
  repetível e evitável com `GIT_TERMINAL_PROMPT=0`.
- Ação do proprietário: `gh auth login` neste host. Depois, o agente repete o
  `prepare` acima e segue para `install` com token; o `pkexec` abre a janela de
  senha, digitada pelo proprietário. Release ativa permanece
  `2.0.0rc1-59ecc2d8f0f6`; rollback é a própria release ativa.

### Atualização: bundle pronto, instalação pendente de autenticação do operador

- Causa do "gh sem login": `.steamzero-dev/env.sh` isola `XDG_CONFIG_HOME`; o
  `prepare` passa com `GH_CONFIG_DIR=$HOME/.config/gh`. Bundle preparado e
  verificado: `2.0.0rc1-c58195919b07`, wheel sha256
  `24f1fd359eabf59de6b037158bb354e7fb3731729427b0c012ac7227fbdae4ce`, run 42040231859
  (`build/release/c5819591`, não versionado).
- `install` exige o checkout no commit do artifact (recusa sem mutação em outra
  HEAD). Três tentativas expiraram no teto de 90 s da autorização `pkexec`: duas a
  partir do shell isolado do agente (janela não chega à sessão) e uma do terminal
  do operador às 13:12:45, em que o journal registra o diálogo polkit sem senha
  ("conversation failed"). Host inalterado: `2.0.0rc1-59ecc2d8f0f6`.
- Retomada (terminal do operador, em `~/Projects/SteamZero`):
  1. `git status --porcelain && git -c advice.detachedHead=false checkout c58195919b07a799c67ac716ceb9e3ca99ba3f12`
  2. `source .steamzero-dev/env.sh && GH_CONFIG_DIR=$HOME/.config/gh GIT_TERMINAL_PROMPT=0 PYTHONPATH=src .venv/bin/python tools/release_host.py install --bundle build/release/c5819591 --rollback-release 2.0.0rc1-59ecc2d8f0f6 --confirm-install INSTALAR-2.0.0rc1-c58195919b07`
     (senha na janela polkit em até 90 s)
  3. `git checkout codex/product-recovery-2026-10-16`
  Depois: validação read-only (versão, doctor, units, sessões), reboot e prova
  física com PNG pelo operador.

## Instalação de `2.0.0rc1-c58195919b07` (05/11/2026 14:55–15:05)

- Autorização expressa do proprietário na thread; senha polkit digitada por ele.
  `release_host.py install --bundle build/release/c5819591 --rollback-release
  2.0.0rc1-59ecc2d8f0f6 --confirm-install INSTALAR-2.0.0rc1-c58195919b07` com o
  checkout no commit do artifact; journal: duas sessões `pkexec` às 14:55:38/44.
- Resultado da ferramenta: `E-HOST-RESTART-FAILED: daemon-reload falhou` — o
  processo herdou `XDG_RUNTIME_DIR` do perfil de desenvolvimento (env.sh) e não
  alcançava o barramento de usuário. A ativação já tinha ocorrido:
  `/opt/steamzero/current` → `releases/2.0.0rc1-c58195919b07`; o socket ativou o
  daemon da release nova às 14:56; sem quarentena; units com `NeedDaemonReload=yes`.
- Recuperação pelo caminho oficial do produto (não manual):
  `steamzero service refresh` com `XDG_RUNTIME_DIR=/run/user/1000` →
  `state: ready`, identidade `2.0.0rc1-c58195919b07` / `c58195919b07a799…` /
  `sourceDirty: false`; `NeedDaemonReload=no` e `active` em `steamzero-core.service`
  e `.socket`.
- Validação read-only: `steamzero --version` 2.0.0rc1; `steamzero service status`
  `converged`, daemon na release ativada, quarentena nula; `steamzero doctor`
  `degraded` com 9 pass, 0 fail e 3 warn (13 backups e 9 journals órfãos
  pré-existentes; `boot.direct` sem permissão para leitura); sessão
  `/usr/share/wayland-sessions/steamzero-gamemode.desktop` com marcador de ownership.
- Correção da causa: `75ab8ac8` — `install/rollback/cycle/update` recusam, antes de
  qualquer passo de host, um `XDG_RUNTIME_DIR` diferente de `/run/user/<uid>` ou sem
  barramento.
- Rollback disponível: `release_host.py rollback 2.0.0rc1-59ecc2d8f0f6
  --confirm-rollback REVERTER-2.0.0rc1-59ecc2d8f0f6` (fora do env.sh).
- Não certificado: reboot, boot direto, captura PNG da release instalada, jornada
  launch/return, controle físico e receptor — ações do operador.

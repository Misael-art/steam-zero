# P0-A/P0-B e bezel — checkpoint 04/10/2026

- Checkout canônico: `Canonical/2026-09-21`
- Branch: `codex/session-exit-wayland-bezel-2026-10-04`
- Base: `5e94e50810deac5bde22645fb3e015d62426baf2`
- Workstream: `WS-2026-10-JOURNEY-LAUNCHER-SESSION`

Este registro mantém os defeitos originais visíveis, descreve os testes de
correção e separa a evidência de código da prova física que ainda exige uma
release instalada e autorização própria.

## Baselines preservados

A revisão do PR #250 reproduziu ambos os defeitos no main `5e94e50810de`:

- **Saída pausada — failed:** `136-exit-paused-repro.json` registra o filho
  descartável em estado Linux `T` antes/depois da saída confirmada e também após
  a repetição; ele só terminou com `SIGCONT` de limpeza no próprio grupo de
  teste. O filho foi coletado e não houve jogo, save ou serviço do host. Relato:
  `/home/misael/steamzero-evidencia-integracao-2026-09-30/integracao-2026-09-30/136-revisao-pr250.md`.
- **Wayland isolado — failed:** `136-wayland-isolation-repro.json` registra
  `WAYLAND_DISPLAY=wayland-0` relativo com `XDG_RUNTIME_DIR` privado, socket
  resultante ausente e `wl_display_connect(NULL)` falhando com `errno=2`;
  informar o socket original absoluto conectou. As conexões foram encerradas
  imediatamente. Nenhuma janela, captura, tecla ou gamepad foi usado. O probe
  não testou startup Qt nem fallback X11.

## Correções no checkout

### P0-A — pedido de saída a partir de suspensão

`SessionControlOwner` revalida ID da sessão/jogo, owner, PID, start ticks e grupo
e sessão Linux próprios antes de sinalizar. Para sessão `suspended`, envia TERM
e, se o processo ainda existe e a identidade continua válida, CONT apenas para
permitir o tratamento do TERM pendente. Não publica `running` ou `closed`, não
envia SIGKILL e deixa `closing` para o observer confirmar. A repetição após
sucesso não duplica sinais; a etapa parcial fica recuperável se TERM foi enviado
mas CONT falhou. A resposta remota usa o estado reconhecido pelo dono para não
confundir o encerramento rápido com sessão perdida.

A regressão usa processo Python descartável real com grupo próprio e confirma
pausa real, exit confirmado, término coletado, identidade e deduplicação. Casos
de confirmação/identidade antiga e comportamento da bridge/overlay também são
cobertos. O ciclo de jogo na release, retorno visual e preservação de saves
reais ainda não foram executados.

### P0-B — XDG isolado preserva o endpoint Wayland

Os homes de config/data/state/cache/runtime continuam sob raiz privada da
fixture. Antes de os alterar, o Launcher resolve e valida `WAYLAND_DISPLAY`:
nome relativo usa o runtime original privado do usuário; endereço absoluto é
aceito somente como socket Unix regular pertencente ao usuário. O filho QML
recebe o caminho absoluto do socket, independente do `XDG_RUNTIME_DIR` novo.
Ausência de Wayland e X11 produz diagnóstico antes de consultar catálogo ou
capacidades do host; X11 sem Wayland preserva seu display.

Testes de integração usam listener Unix descartável, verificam o endpoint no
ambiente entregue à bridge e conectam o socket. Isso valida resolução e
transporte local, não uma janela Qt no compositor real. O probe com
`libwayland-client.so.0` após a alteração, teclado/gamepad, screenshot e fallback
X11 não foram executados.

### Bezel personalizado — próximo lançamento RetroArch Flatpak

O Theme Studio aceita um PNG-fonte validado no slot `bezel` do manifesto v1; o
asset permanece na raiz declarativa do tema e suporta undo/redo, salvar,
reabrir, exportar e importar pelo `ThemeInstaller`. A Jornada persiste apenas
`aura-default` ou URI lógica versionada contendo namespace, versão semver e
SHA-256; paths, URLs e scripts não são aceitos. Catálogo/resolver revalidam
manifesto, licença, compatibilidade, formato, tamanho e conteúdo imediatamente
antes de preparar a sessão.

O caminho de launch cria somente arquivos SteamZero conhecidos em
`XDG_CONFIG_HOME/retroarch/sessions/{sessionId}`, com `config_save_on_exit=false`,
e os remove após observar a saída. O `--appendconfig` próprio é combinado com a
configuração gerenciada de controles em um único argumento ordenado; paths com
o separador `|` são recusados. `retroarch.cfg` de terceiros não é aberto nem
alterado. A escolha é de próximo lançamento; o read model diz
`launch-configured-unconfirmed` e não afirma que o overlay foi carregado nem que
pixels foram exibidos.

No código oficial do RetroArch, o argumento `--appendconfig` escreve num único
campo de caminho e `configuration.c` separa a lista por `|`; o parser de
consultas de configuração é allowlisted e não oferece consulta genérica a
`input_overlay`. Fontes upstream usadas para orientar o adapter:
[retroarch.c](https://github.com/libretro/RetroArch/blob/master/retroarch.c),
[configuration.c](https://github.com/libretro/RetroArch/blob/master/configuration.c)
e [command.c](https://github.com/libretro/RetroArch/blob/master/command.c).

O catálogo e os adapters testados não provam o RetroArch aberto, a aplicação
visual do bezel ou gameplay. SVG/WebP são mostrados indisponíveis para esse
adapter; seleção ausente/obsoleta recupera pela herança AURA.

## Testes de checkout observados

- **Bateria focada ampla:**
  `rtk .venv/bin/python -m pytest tests/unit/test_session_control.py tests/unit/test_emulation_controller.py tests/unit/test_experience_journey.py tests/unit/test_journey_studio.py tests/unit/test_launcher_journey_runtime.py tests/unit/test_session_peripherals.py tests/unit/test_theme_editor.py tests/unit/test_themes.py tests/integration/test_desktop_ui_bridge.py tests/integration/test_experience_journey_bridge_e2e.py tests/integration/test_launcher_app.py tests/integration/test_launcher_journey_e2e.py tests/integration/test_experience_journey_e2e.py tests/integration/test_launcher_session_overlay_trigger.py -q`
  — **399 passed em 141,61 s**. Incluiu o harness QML real de Jornada e overlay
  no runtime Qt do job local; nenhum passe físico.
- **Follow-up focal:** três casos passaram: export/import do PNG no instalador,
  Jornada ativa → resolver → callback `LauncherBridge` com o mesmo URI, e recusa
  HTTP 400/E-API-SCHEMA de URI com caminho. `3 passed em 2,11 s`.
- Ruff check, `ruff format --check` e `git diff --check` passaram nos arquivos
  Python alterados depois das correções.
- O primeiro passe focado encontrou sete falhas em 390 testes; causas e
  correções estão registradas pelo histórico desta sessão. O resultado anterior
  não foi apagado nem chamado de flaky.

## Checkpoint integral desta branch

Antes da primeira suíte integral, os gates estáticos passaram:

- `rtk .venv/bin/ruff check src tools tests` — passou.
- `rtk .venv/bin/ruff format --check src tools tests` — passou, 699 arquivos.
- `rtk .venv/bin/mypy src` — passou, 303 arquivos. A primeira tentativa apontou
  uma tupla de argv estreita e invariância de `list`; as anotações foram
  corrigidas e a execução final passou.
- `rtk make independence boundaries` — passou, 0 violações.
- `rtk git diff --check` — limpo.

### Integral inicial — falha preservada

`rtk .venv/bin/python tools/run_tests_isolated.py tests -q` concluiu em
**2353,67 s**: **6661 passed, 47 skipped, 4 failed**. A saída integral
byte-a-byte está em
[`01-integral-initial-failed.log.gz`](01-integral-initial-failed.log.gz); o SHA-256
após descompressão é
`1ac8f6533d4ba77db84bb321058c695326884b50a1f5736bc644830eb8f9e402`.

- `test_emulation_launch_cli_uses_local_controller` e
  `test_emulation_launch_spawn_failure_stays_unconfirmed`: o CLI enviava o
  argumento opcional `bezel_resource` até no caminho padrão, quebrando
  controllers que implementam o contrato anterior `launch_game(game_id)`.
  Corrigido para enviar o argumento apenas quando o operador informa um URI;
  adicionado teste de regressão para o URI explícito.
- `test_committed_matrix_matches_the_code`: a matriz gerada tinha uma
  capacidade a menos. Regenerada com `make update-capability-matrix`; o gate
  `tools/capability_matrix.py --check` passou.
- `test_additive_bezel_slot_inherits_aura_and_filters_untrusted_assets`: o
  contrato do slot agora carrega também o estado operacional aditivo. A
  expectativa passou a verificar defaults honestos (`applied=false`, origem e
  versão vazias/unknown e `applyMode`/`executionState=unavailable`), mantendo a
  recusa de `file://`.

Depois dessas correções, os quatro casos originais mais o caso novo do URI
explícito passaram juntos (**5 passed em 1,05 s**); Ruff check/format e a
verificação da matriz também passaram nos arquivos/artefatos alterados. A
integral corrigida abaixo concluiu depois, no mesmo checkout congelado.

Na integral inicial, o runner viu alteração no state home real durante a janela
(`logs`, `logs/core.jsonl`, `state.db`), mas atribuiu a escrita ao daemon
`steamzero-core --systemd`, que já existia antes; a atribuição daquele lote
fica **degradada** conforme o aviso do runner. O serviço permaneceu ativo. O
runner não atribuiu a mudança à suíte isolada.

### Integral corrigida — concluída

`rtk .venv/bin/python tools/run_tests_isolated.py tests -q` concluiu com saída
**0** em **2708,15 s**: **6666 passed, 47 skipped, 0 failed**. O log integral
está em [`02-integral-final.log`](02-integral-final.log), SHA-256
`59f74a4aed4bef03b16d37f23a5e2effc633c2b8e724fb70b1b0604970ad53b9`.
O snapshot do state home real permaneceu idêntico antes/depois: 12818 arquivos,
2068 diretórios, 1372880520 bytes e mesmo `max_mtime_ns`. Após 100%, o wrapper
imprimiu `ipc connect failed: [Errno 2] No such file or directory`; o processo
terminou com código 0 e o pytest publicou o resumo integral acima.

O código permaneceu congelado durante a rodada. Os gaps físicos do Launcher,
da saída pausada, da janela Wayland e da execução visual do bezel continuam
fora do alcance dessa evidência.

### Revalidação de escopo

Após a integração do PR #250 e as alterações desta continuidade, **34 cartões
preexistentes** tinham `scopeDigest` desatualizado porque seus `scopePaths`
incluem arquivos que mudaram neste lote. Cada digest foi recalculado pela
ferramenta de catálogo e registrado como diagnóstico de escopo somente. Nenhum
critério de aceite foi reexecutado por essa renovação e nenhum eixo de
implementação, integração, verificação, operação ou distribuição foi promovido.
Após as quatro correções da integral inicial, mais **11 renovações scope-only**
atualizaram os cartões afetados pelos arquivos adicionais; também não
promoveram eixos.
Os gaps físicos do Launcher, da saída pausada, da janela Wayland e da execução
visual do bezel seguem abertos.

## Estado externo e próximos limites

Nenhuma instalação, rollback, publicação, restart, janela física ou captura foi
executada nesta branch. A observação da revisão anterior era release
`2.0.0rc1-5715d7962691`; deve ser revalidada por leitura antes de preparar uma
candidata. A autorização de código/PR/merge desta tarefa não é autorização de
instalação ou B_VISUAL. Permanecem gaps físicos para exit durante pausa, janela
Qt Wayland, gameplay com bezel e retorno contextual/input na release instalada.

## Continuidade de central-loading — 05/10/2026

O handoff serial autorizado cedeu temporariamente
`tests/integration/test_qml_handheld_offscreen.py` à WS-2026-10-JOURNEY-LAUNCHER-SESSION;
`tests/qml/check_central_loading.qml` foi declarado no claim Jornada antes de
ser alterado. A Biblioteca permaneceu ativa, preservando G58/G59 e os demais
caminhos exclusivos. O probe original 137 foi copiado sem alteração para
[`05-central-loading-counter-probe.json`](05-central-loading-counter-probe.json),
SHA-256 `2f9d42cb724486feb0f2b963a6592fa055cce55f37854936cf6ef8d24930bc7c`.
Ele prova interferência da contagem global entre instâncias, mas declara
explicitamente que não reproduz nem explica a sexta leitura histórica.

O bridge agora mantém sequência, lock, porta, trace e barreira por instância;
usa socket efêmero, threads próprias não daemon, deadlines por evento e fecha
barreira, servidor, handlers e socket por context manager. A cena registra
origem de refresh/retry, fase, `statusAttempt`, `statusInFlight`, fila e pedidos
pendentes. O resultado de `qml6` (código, stdout, stderr e timeout) é validado
antes da contagem, e qualquer divergência imprime a sequência HTTP completa.
Regressões cobrem isolamento A/B e cleanup em sucesso, falha e timeout. Os
quadros loading, stale e ready são capturados em execuções independentes.

O checkpoint focal executou dez casos: **10 passed em 32,12 s**. O snapshot do
state home real permaneceu idêntico (12818 arquivos, 2068 diretórios,
1372896963 bytes e mesmo `max_mtime_ns`). O trace sintético completo está em
[`06-central-loading-trace.json`](06-central-loading-trace.json): `qml6` saiu
com código 0, registrou cinco GET `/status` em sequência, nenhum erro de
transporte e cleanup confirmado (serve thread parada, zero handlers, fd -1).
Hash do teste Python `193b0446cd2e19f7d1701c60891ba1177675c81e24eb525bf07c376fb71d5b66`;
hash do harness QML `749f12c7ad8345cb6188a289f474d17cac70c132ef444df6dc2894c6774341fa`.

Em seguida, o módulo inteiro `tests/integration/test_qml_handheld_offscreen.py`
passou: **62 passed em 121,49 s**, também com snapshot real idêntico antes e
depois. Isso cobre a ordem completa entre seus testes na versão instrumentada;
como não reproduziu seis pedidos, não estabelece a causa que ocorreu na
integral anterior.

Após acrescentar o parser estruturado dos eventos QML ao diagnóstico, os dez
casos focais passaram novamente em **29,51 s**. O trace atual está em
[`07-central-loading-structured-trace.json`](07-central-loading-structured-trace.json),
SHA-256 `d8933683d422cc922d016fb0cf147e6ef03c886327f0170af3b24fb1fe84a676`.
Ele compara `qmlLogicalAttemptMax=5` com cinco recebimentos `/status`, contém 44
eventos QML sem erro de parse, returncode 0, nenhum erro HTTP e cleanup completo.
Hashes da fonte executada ao gerar o trace 07: teste Python
`85e479a905eb7d2ab39e28e4222dda3a3f70e89ce80df7cefafee05129c7971b`; harness
QML `749f12c7ad8345cb6188a289f474d17cac70c132ef444df6dc2894c6774341fa`.

Com o caso de timeout atualizado para provar a extração do trace parcial, o
módulo QML completo passou novamente: **62 passed em 96,33 s**. O state home
real permaneceu idêntico. Hash atual do teste Python:
`201ce5d42d4a5f10f1610c9e873c5112e9d95d6e96cf54e76358eff24777a707`.

Esta execução verde não explica o seis-vs-cinco histórico. O log integral
vermelho continua preservado em
[`04-integral-preflight-failed.log`](04-integral-preflight-failed.log), SHA-256
`63dac04da8fa5f392e2cc4e0f5b853af7bb4d102602f405436f720615209fd2e`; sem
stdout/stderr QML naquela falha, ainda não há causa medida. A integral do novo
checkpoint não foi iniciada enquanto essa causa permanece desconhecida.

Na próxima reprodução, o diagnóstico estruturado permite comparar
`qmlLogicalAttemptMax` com `actualStatusReads`: ambos em seis apontariam para
pedido lógico extra; cinco tentativas e seis recebimentos apontariam para
repetição/transporte ou contabilização fora da instância; código/timeout e o
último evento `scene-finish` delimitam encerramento do harness. Esses critérios
são discriminantes para uma observação futura, não uma conclusão sobre os logs
antigos.

Gates estáticos deste checkpoint passaram: `ruff check src tools tests`,
`ruff format --check src tools tests` (699 arquivos), `mypy src` (303 arquivos),
`make independence boundaries`, `make status-check` e `git diff --check`. A
integral local não foi iniciada porque a causa do seis-vs-cinco ainda não foi
medida; o resultado vermelho anterior permanece aberto.


## Instrução operacional atualizada — 05/10/2026

A instrução atual do operador autoriza uma única integral da árvore corrigida. Ela substitui a decisão anterior, registrada acima, de aguardar uma reprodução discriminante da causa histórica antes de iniciar a integral. Essa alteração de sequência não fecha nem reclassifica o incidente antigo: `04-integral-preflight-failed.log` continua sendo a evidência vermelha, com SHA-256 `63dac04da8fa5f392e2cc4e0f5b853af7bb4d102602f405436f720615209fd2e`, e `GAP-AURA-UI-CENTRAL-LOADING-6-VS-5` permanece aberto sem causa estabelecida.

A próxima ação é congelar `src/`, `tests/` e `tools/`, registrar HEAD e hashes dos arquivos modificados antes/depois, manter ativo o guard de estado real do runner e gravar o log vivo fora do checkout. Preservar cinco GET `/status`, o `Main.qml` real, os contratos de fases e o cleanup; não parar o daemon nem disputar CPU com validação visual. Se a nova integral passar, o resultado vale somente para a nova árvore. Se falhar, usar os diagnósticos completos para investigação focal e não repetir a suíte sem mudança causal. A autorização inclui commits, push, PR e merge commit somente depois de gates verdes; não autoriza instalação, rollback, publicação certificada ou B_VISUAL.


## Integral do checkpoint corrigido — 05/10/2026

Com a instrução operacional atualizada do operador, foi executado uma única vez `.venv/bin/python tools/run_tests_isolated.py tests -q`. O comando terminou com exit **0** em **2669,43 s (44:29)**: **6675 passed, 47 skipped, 0 failed**. O log completo está em [`08-integral-corrected-tree-2026-10-05.log`](08-integral-corrected-tree-2026-10-05.log), SHA-256 `328cc74330ebb90e6c01a2677a5325cc75c155b1eb7406630b02f8c2b20f2bca`. O log foi escrito em `/tmp` enquanto o checkpoint rodava e copiado ao acervo somente após a saída terminal.

O HEAD-base permaneceu `31564383ac90b53e0ae8ed6696eaa7ca32f8d5ef`. Hashes antes/depois também coincidiram: `tests/integration/test_qml_handheld_offscreen.py` `201ce5d42d4a5f10f1610c9e873c5112e9d95d6e96cf54e76358eff24777a707`; `tests/qml/check_central_loading.qml` `749f12c7ad8345cb6188a289f474d17cac70c132ef444df6dc2894c6774341fa`; `tests/unit/test_release_host.py` `61681010e7585d5697f41954ee3e7a4eaea6ac5148cbb752af1c5cac21ea3cc6`; `tools/release_host.py` `cc6ff13ff1080c90796755d737cf622352289d8e1baed4095b9e8ab4ddeabf66`.

O guard real detectou alteração durante a janela (`logs/core.jsonl` e `state.db`; 12818 arquivos e 2068 diretórios antes/depois; bytes 1372896963 → 1372897989). O runner atribuiu as escritas ao `steamzero-core --systemd`, PID 695227, já ativo antes do teste, e terminou sem reprovar, mas marcou a atribuição como degradada enquanto esse dono externo escreve. O daemon não foi parado, conforme instrução. Isso limita a prova de ausência de escrita concorrente da suíte; não altera o exit 0 do pytest nem é prova de que o host ficou imutável.

Este é um passe da nova árvore corrigida. O histórico não foi reescrito: `04-integral-preflight-failed.log` continua vermelho (6670 passed, 47 skipped, 1 failed; SHA-256 `63dac04da8fa5f392e2cc4e0f5b853af7bb4d102602f405436f720615209fd2e`) e `GAP-AURA-UI-CENTRAL-LOADING-6-VS-5` segue sem causa. A integral nova não reproduziu nem explica o sexto pedido antigo. Não promove maturidade física, instalação, Theme Studio/Engine ou B_VISUAL.


## Estado consultivo do host e gates estáticos — 05/10/2026

Antes da integral, `release_host.py --json inspect` confirmou somente por leitura a release ativa `2.0.0rc1-5715d7962691`, source commit `5715d7962691efedef0f1b63e71adff1ad5ba801`, service/socket ativos, Doctor schema 22 e `pendingOperations=0`. O Doctor permaneceu degraded: 9 backups órfãos, 9 journals órfãos, `bootDirect=unknown` e botões Deck sem teclas. O inspect também marcou o worktree sujo e o host diferente da última tag. Nenhum cleanup, restart, instalação ou outra mutação foi feita.

Após a integral, os gates estáticos passaram sobre a mesma fonte: `ruff check src tools tests`; `ruff format --check src tools tests` (699 arquivos); `mypy src` (303 arquivos); `make independence boundaries`; `make status-check` (`STATUS-CHECK: OK`); `git diff --check`. Os hashes de `src/tests/tools` confirmam que o código permaneceu idêntico durante a integral.

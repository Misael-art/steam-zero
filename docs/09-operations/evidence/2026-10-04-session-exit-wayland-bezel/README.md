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

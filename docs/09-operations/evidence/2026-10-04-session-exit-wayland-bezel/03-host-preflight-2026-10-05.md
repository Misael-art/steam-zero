# Pós-merge, identidade de runtime e preflight do host — 05/10/2026

## Integração e candidata anterior

- PR #251 foi integrado por merge commit
  `31564383ac90b53e0ae8ed6696eaa7ca32f8d5ef`; a árvore testada foi
  `7f5f323c114dab661e82d36c973ce34b9028198f`, igual à árvore do merge.
- O push de `main` no run `37258141399` terminou com sucesso em 8/8 jobs.
- A candidata daquele tip foi preparada do run exato e passou `verify-bundle`:
  release `2.0.0rc1-31564383ac90`, source commit completo
  `31564383ac90b53e0ae8ed6696eaa7ca32f8d5ef`, wheel SHA-256
  `cfc10b981835fff53b8fcc2c1579766428d5c91c3078e51ecfcd025df97c606b`.
  Seu `_build_info.py` embute esse commit com `SOURCE_DIRTY=False`.
- Essa candidata não foi instalada. O follow-up de preflight abaixo altera a
  ferramenta de promoção; uma candidata nova deve vir do próximo run push verde
  do `main` exato.

## Causa da leitura falsa e proteção

Ao carregar a ferramenta do checkout com `PYTHONPATH=src`, o subprocesso da CLI
instalada herdava esse caminho. O Python podia então importar o pacote local,
sem `_build_info.py`, e reportar proveniência `unknown`. A leitura direta do
binário instalado, sem o caminho do checkout, mostrou `runtime.provenance=pass`
com `2.0.0rc1-5715d7962691`; `PATH` e `/opt/steamzero/current` resolvem para a
mesma release.

`tools/release_host.py` agora remove `PYTHONPATH` somente ao iniciar a CLI
`steamzero` do host. O preflight também exige manifesto completo, versão e
release do Doctor iguais ao manifesto, `runtime.provenance=pass`, e commit
declarado pelo daemon igual ao commit completo do manifesto. Identidade ausente,
desconhecida ou divergente interrompe o fluxo antes de qualquer ativação.

## Host observado, somente leitura

- Release ativa e rollback previsto para a atualização:
  `2.0.0rc1-5715d7962691`, source commit
  `5715d7962691efedef0f1b63e71adff1ad5ba801`. O manifesto, hashes, ownership
  root e smoke isolado da release foram verificados; os destinos gerenciados de
  ativação passaram o teste read-only de ownership.
- Doctor ativo: `ok=true`, schema 22, `pendingOperations=0`, runtime identity
  correspondente ao manifesto. Daemon convergido com release e commit iguais;
  socket e service ativos.
- O Doctor continua `degraded`: 9 backups órfãos, 9 journals órfãos, nenhum
  staging órfão ou job stale, `bootDirect=unknown` por falta de permissão de
  inspeção, e botões do Deck não chegam como teclas. Nenhum backup/journal foi
  removido ou reconciliado.
- `release_host.inspect` registra que o host ainda difere do último commit
  tagueado (`v2.0.0rc1` → `085169f471866fbb61530c777d368729002b6868`). Isso é a
  release instalada anterior ao candidato; o preflight de atualização
  read-only passou. O worktree estava sujo durante o follow-up, como esperado
  enquanto a correção estava em desenvolvimento.
- Nenhuma instalação, rollback, restart, publicação, captura, janela Qt ou
  input foi executado.

## Provas locais da proteção

`tests/unit/test_release_host.py`: **75 passed**. Inclui recusa de proveniência
ausente/desconhecida e de identidade divergente, aceitação quando manifest,
Doctor e daemon concordam, e regressão que garante que `PYTHONPATH=src` não
contamine subprocessos `steamzero` do host. Ruff check/format e `git diff
--check` passaram nos arquivos alterados.

## Integral deste checkpoint

`04-integral-preflight-failed.log` preserva a saída terminal completa. SHA-256:
`63dac04da8fa5f392e2cc4e0f5b853af7bb4d102602f405436f720615209fd2e`.
`tools/run_tests_isolated.py tests -q` terminou com exit 1 em 2454,86 s:
**6670 passed, 47 skipped, 1 failed**. O state home real permaneceu idêntico:
12818 arquivos, 2068 diretórios, 1372896271 bytes e mesmo `max_mtime_ns`.

A única falha foi `test_central_loading_phases_are_observable_offscreen`:
esperava cinco GET `/status`, observou seis, com `BrokenPipeError` no handler.
O teste isolado passou uma vez (**1 passed em 3,46 s**) após a integral; isso
não determina a causa e não transforma o resultado integral em verde. A mesma
diferença 6-vs-5 aparece em uma anotação histórica de 2026-10-03. Não alterei o
teste: `tests/integration/test_qml_handheld_offscreen.py` está reservado pelo
workstream ativo de Biblioteca e requer handoff serial para qualquer correção.
Não há commit funcional nem PR até este gate ficar terminalmente verde.

## Limites de produto e próximo passo

P0-A e P0-B continuam comprovados no checkout: o caso paused-exit usa processo
descartável próprio, e Wayland preserva o socket validado. Theme Studio e
Jornada round-trip do PNG-fonte/URI versionada; no RetroArch Flatpak, o adapter
prepara config privada para o próximo launch, com estado
`launch-configured-unconfirmed`. Nada prova pixels do bezel, gameplay, janela
Qt Wayland real, input físico ou ciclo de retorno na release instalada.

Os gates, PR/CI e uma candidata nova precisam ser fechados para o tip resultante
do follow-up. A integral atual está bloqueada pela falha acima e pelo handoff
serial do path reservado. Instalação ainda exige autorização própria e token
exato no fluxo governado. B_VISUAL requer essa release autorizada e captura/input
disponíveis; nenhum eixo de maturidade dos quatro produtos foi promovido por
estas leituras.

## Sondagem instrumentada sem edição do teste

Uma execução diagnóstica em memória envolveu `_CentralLoadingHandler.do_GET`
para registrar os pedidos enquanto chamava o corpo do teste, sem alterar os
arquivos do repositório. Ela passou com cinco GET `/status`; houve também um
GET `/theme/list`, que não participa da contagem. Isso confirma uma execução
normal, mas não reproduz a sexta leitura.

O teste primeiro afirma `served == 5` e só depois chama
`_assert_qml_clean(completed, ...)`. Quando a contagem é seis, a asserção
interrompe a função antes de validar `completed.returncode`, stdout e stderr do
`qml6`. Portanto o log integral não revela se o harness QML em si saiu com
sucesso, e a origem da sexta leitura segue desconhecida. A próxima investigação
precisa observar esse resultado antes da contagem; o path continua reservado e
aguarda handoff serial.

## Atualização após handoff serial — 05/10/2026

O handoff autorizado ocorreu antes da edição: o teste foi removido do claim
exclusivo da Biblioteca e adicionado ao da Jornada; o harness
`tests/qml/check_central_loading.qml`, sem claim anterior, também foi declarado
na Jornada antes da alteração. Os dois workstreams continuam ativos e G58/G59,
`emulation.py` e os demais caminhos da Biblioteca permaneceram preservados.

O probe 137 está arquivado como
[`05-central-loading-counter-probe.json`](05-central-loading-counter-probe.json),
com o SHA-256 original
`2f9d42cb724486feb0f2b963a6592fa055cce55f37854936cf6ef8d24930bc7c`; o arquivo
confere byte a byte com o acervo externo. Ele prova só a interferência entre
contadores globais de instâncias e não a causa histórica.

O novo trace completo está em
[`06-central-loading-trace.json`](06-central-loading-trace.json). A execução
sintética terminou com QML returncode 0, cinco GET `/status` numerados 1–5,
nenhum erro de transporte e recursos próprios fechados. O log traz a saída QML,
ordem de mudanças de `statusAttempt`, fase, fila e requests, além dos tempos
monotônicos de recebimento/liberação/resposta. `qml6` é validado antes da
contagem; divergências preservam subprocesso e sequência HTTP.

Comando focal:
`rtk .venv/bin/python tools/run_tests_isolated.py tests/integration/test_qml_handheld_offscreen.py::test_central_loading_bridges_isolate_sequences_and_close_owned_resources tests/integration/test_qml_handheld_offscreen.py::test_central_loading_bridge_closes_held_request_after_failure_or_timeout tests/integration/test_qml_handheld_offscreen.py::test_central_loading_phases_are_observable_offscreen tests/integration/test_qml_handheld_offscreen.py::test_central_loading_frames_are_capturable tests/integration/test_qml_handheld_offscreen.py::test_a_mutation_refresh_is_not_discarded_by_an_in_flight_read -q --tb=short`
— **10 passed em 32,12 s**; state home real idêntico antes/depois. Os testes
cobrem captura loading/stale/ready, sequência por instância e cleanup após
sucesso, falha e timeout. Ruff check, format e `git diff --check` passaram nos
arquivos alterados neste slice.

Depois do foco, a sequência completa do módulo QML passou: **62 passed em
121,49 s**. O snapshot do state home real permaneceu idêntico. A execução
abrange os testes anteriores/posteriores do módulo com pontes agora isoladas e
fechadas; ela não reproduziu o sexto pedido observado no gate integral.

O seis-vs-cinco histórico segue sem causa medida. A nova execução normal não o
reproduziu e não altera o veredito do log integral vermelho acima. Por isso não
se iniciou outra integral nem se registrou correção de produto: o resultado
focal demonstra a execução normal e as correções de isolamento/diagnóstico,
mas não fecha a falha histórica.

Na próxima reprodução, `qmlLogicalAttemptMax` é comparado com a quantidade
recebida pela instância: seis em ambos aponta para chamada lógica adicional;
cinco tentativas com seis HTTP aponta para repetição de transporte ou origem
que não incrementa `statusAttempt`. A trilha de porta/instância separa isso de
contabilidade alheia. Returncode, timeout e `scene-finish` delimitam o caminho
de encerramento. Esses critérios ainda não explicam a execução vermelha
anterior.

Após a última alteração de diagnóstico, os dez casos focais passaram novamente
em **29,51 s**. O trace atual
[`07-central-loading-structured-trace.json`](07-central-loading-structured-trace.json),
SHA-256 `d8933683d422cc922d016fb0cf147e6ef03c886327f0170af3b24fb1fe84a676`,
registra `qmlLogicalAttemptMax=5`, cinco recebimentos HTTP `/status`, 44 eventos
QML parseados sem erro, QML returncode 0, nenhum erro de transporte e cleanup
completo. Esse resultado continua sendo uma execução normal, não a causa do
sexto pedido antigo.

Com o caso de timeout atualizado para provar o parse da saída parcial, o
módulo QML inteiro passou outra vez: **62 passed em 96,33 s**, com state home
real idêntico. Hash do teste Python deste fechamento focal:
`201ce5d42d4a5f10f1610c9e873c5112e9d95d6e96cf54e76358eff24777a707`.

Gates estáticos globais passaram: Ruff check, formatação (699 arquivos), mypy
(303 arquivos), independência, fronteiras, `make status-check` e `git diff
--check`. A integral do novo checkpoint segue sem execução até existir uma
reprodução que discrimine a causa da falha histórica.


## Atualização operacional do checkpoint — 05/10/2026

A orientação registrada na seção anterior dizia para não iniciar nova integral enquanto a causa histórica não fosse medida. A instrução do operador atualizada em 05/10/2026 substitui essa condição: autoriza uma única integral da árvore corrigida com instrumentação completa, hashes antes/depois e state guard real. A mudança autoriza avaliar o novo código; ela não explica o 6-vs-5 antigo. Preserve o log e SHA acima e mantenha `GAP-AURA-UI-CENTRAL-LOADING-6-VS-5` aberto. O resultado novo deve ser registrado como checkpoint independente da árvore atual.


## Resultado da integral corrigida — 05/10/2026

A integral única autorizada terminou exit 0 em 2669,43 s: 6675 passed, 47 skipped, 0 failed. Log 08: SHA-256 `328cc74330ebb90e6c01a2677a5325cc75c155b1eb7406630b02f8c2b20f2bca`. O HEAD-base e os quatro hashes de src/tests/tools permaneceram idênticos antes/depois. O state guard registrou alteração em logs/core.jsonl e state.db atribuída pelo runner ao daemon já ativo, com autoria degradada; ele permaneceu ativo. Este passe vale somente para a nova árvore, sem atribuição causal ao 6-vs-5 histórico; log 04 e gap continuam abertos.


A inspeção somente leitura anterior à integral reconfirmou a release ativa `2.0.0rc1-5715d7962691`, daemon/socket ativos, schema 22 e zero operações pendentes. Doctor degraded e alertas (9 backups, 9 journals, `bootDirect=unknown`, Deck keys false) foram preservados; nenhum artefato foi reconciliado ou alterado. Após a integral, os gates estáticos passaram sobre a mesma fonte: `ruff check src tools tests`; `ruff format --check src tools tests` (699 arquivos); `mypy src` (303 arquivos); `make independence boundaries`; `make status-check` (`STATUS-CHECK: OK`); `git diff --check`. Os hashes de src/tests/tools coincidiram antes e depois da integral.

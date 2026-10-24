# R2 — metadados canônicos no Launcher

Assunção serial em 2026-10-23: branch `codex/product-recovery-2026-10-16`, HEAD inicial `c2929ff0a6c3f175f393c36e62707b06ac565480`, origin/main `0979765171a32e7532f1f650a889962ba375d58d`, fetch sem mudança, árvore inicialmente limpa e um worktree. Nenhum escritor SteamZero encontrado em /proc; processos de outras tarefas não foram alterados.

A instrução do proprietário nesta tarefa atualiza o regime histórico: após implementação, testes e checkpoint, trabalhos tecnicamente independentes podem continuar durante a ausência. Instalação/prova física pendentes não bloqueiam todo o desenvolvimento. Não iniciar bigsudo nem preflight interativo, não repetir a tentativa expirada e não solicitar senha. Push e integração governada continuam autorizados, sujeitos aos checks; sem force push ou bypass. Histórico preservado.

Baseline: Central anexa `public_view` de `game_metadata`; Launcher usa somente `cinema_metadata(record)` do cache e o registro de mídia. Ano/gênero/desenvolvedor/descrição persistidos não chegam ao modelo. O consumidor deve ler sem criar/migrar o banco, preservar campos e procedência, degradar por jogo e manter a biblioteca navegável.

## Fila única de instalação e aceite

| Entrega | Implementação/integração | Pacote | Instalação/aceite | Dependências |
|---|---|---|---|---|
| R2 Central, migração v23, conteúdo NES | Integrada em main 09797651 | 2.0.0rc1-0979765171a3, bundle privado histórico bundle-09797651 | PENDENTE_CREDENCIAL; tentativa anterior expirou; não repetir | Presença do operador; revalidar bundle/CI/SHA/rollback com controlador antes da retomada |
| R2 Launcher | Integrado pelo PR #265, main 927dee4a; oito jobs verdes no PR e push | Não preparado | Pendente; consolidar candidata coerente após checks/integração | Instalação governada; aceite Central/Launcher do mesmo jogo |
| R3/D-08 recuperação do refresh | D-08 corrigido em 02248b0d; integral 6848 passed, 47 skipped, exit 0; integração pendente | Não preparado | Pendente; mesmo fluxo de consolidação, sem instalação por microalteração | Gates/CI/integração e aceite instalado de erro/recuperação; jornada completa conserva provas próprias |

Release ativa conferida por symlink: `2.0.0rc1-3f87657c0a6c`. Nenhuma instalação, rollback ou prova física nesta sessão. R0/R1 conserva a prova de interface, NES/Amiga e reabertura em perfil sem daemon; não comprova gameplay, Deck ou jornada completa.

Banco real, ROMs, BIOS, saves, mídias e preferências não são corpus de teste. Migração v23 e recuperação exigem prova própria: rollback do executável não demonstra recuperação dos dados.

Próxima ação: regressão isolada do entrypoint Launcher com GameRecord persistido, seguida da correção mínima e gates integrais.

## Verificação em andamento

Baseline negativo: `01-baseline.log`, falha na descrição antiga do cache (1 failed). Correção: leitura SQLite `mode=ro` pela projeção `public_view` da Central; campos canônicos prevalecem no read model usado por Home/Cinema/busca/Jornada. Fontes e desenvolvedor chegam à página sem expor caminhos ou credenciais.

Focada (`02-focused.log`): 47 passed, incluindo metadados, jobs (autenticação/quota/offline), store, projeção e migração. `03-qml.log`: 1 passed, 62 deselected, contrato offscreen de página; não é prova instalada. Teste amplo do Launcher: 60 passed e uma falha de fixture (WAL permite leitura durante writer exclusivo); fixture corrigida para journal DELETE para exercitar indisponibilidade real, sem mudar produção. A primeira coleta conjunta falhou por nomes iguais de módulos; teste de integração renomeado antes de repetir.

Migração: v22→v23 preserva job preexistente e registro após reabertura; segunda migrate não cria backup novo; backup v22 tem integridade verificada e dado lido. Falha injetada em v23 percorre a restauração do core, recupera v22 e permite retry. Tudo em corpus temporário, sem downgrade/restauração do banco real e sem alegação de recuperação física da release.

Gates integrais serão executados na árvore estável antes dos commits. Comparação de cobertura equivalente: baseline remoto Python 3.14 run 39636317805, SHA 09797651, `not visual`, artefato coverage-python-3.14 (85,32805755395684%); cotejar com o mesmo job da nova candidata, não com a suíte local que inclui visual.

Integral local inicial interrompida deliberadamente durante a revisão: timeout SQLite repetia por jogo. Saída terminal do runner 247 (filho encerrado), sem delta do state home; não é gate aprovado. SIGINT/SIGTERM não encerraram o pytest (handlers instalados); somente o subprocesso próprio de pytest e seu filho QML foram encerrados, sem atingir outras tarefas. Log preservado em `04-full-interrupted.log`. Controle negativo `05-lock-negative-control.log`: 32 IDs, banco bloqueado, 6,755 s > orçamento 2 s. Correção aborta a leitura de storage após o primeiro erro SQLite, mantendo corrupção de GameRecord tratada por linha pela projeção existente. Reexecutar a integral sobre os bytes corrigidos.

Regressão ampliada final: `06-final-focused.log`, **152 passed** em 220,20 s, runner exit 0, sem delta do estado real. Inclui todos os 63 casos de `test_qml_handheld_offscreen.py`, Launcher entrypoint/bridge, store/jobs, migração/recuperação e limite de timeout com banco bloqueado. Ruff integral, format integral e mypy (306 fontes) novamente verdes após o reparo. Nenhuma mudança de schema ou migração de produção neste lote.

Integral corrigida: executar `rtk proxy env -u PYTEST_DEBUG_TEMPROOT .venv/bin/python tools/run_tests_isolated.py tests -q --cov=steamzero --cov-report=term --cov-report=json:/tmp/steamzero-r2-local-coverage.json`, log privado `/tmp/steamzero-r2-full-final.log`; aguardar código terminal antes de commit funcional.

## Checkpoint funcional local

Integral corrigida terminou com exit **1**: **6845 passed, 3 failed, 47 skipped**, 3021,73 s (`07-full-local.log`). As três falhas são o guard do mesmo arquivo temporário criado pela interrupção anterior, não falhas de metadados. O resíduo próprio foi identificado por hash/mtime/UID, saneado sem registrar token e removido (`11-residue-sanitized.json`). Guard intacto. Os três casos foram reexecutados sem mudança de produção, QML ou harness: **3 passed**, exit 0, 16,75 s (`08-facets-retest.log`). Portanto, cobertura de execução complementar: **6848 aprovações / 47 skips**, sem apresentar o log bruto como verde.

Cobertura local combinada: **85,52504782314784%**, gate >=85 atingido. Não é comparação equivalente com o job não visual anterior; comparação equivalente será pelo CI Python 3.14.

Depois da integral, só dois arquivos de testes mudaram para fechar conexões SQLite explicitamente via `contextlib.closing`, sem alterar assertions. **9 passed** com `ResourceWarning` tratado como erro (`10-resource-cleanup.log`). Nenhum byte de produção mudou. Hashes antes/depois e composição da prova em `12-local-checkpoint.json`. Ruff check e format integrais novamente verdes (721 arquivos); mypy 306 fontes, independence, boundaries, component-lock, capability-matrix e status verdes na fonte estável.

As provas são isoladas e offscreen. Não há gameplay, daemon instalado, controle, toque, Deck, PNG físico ou consulta remota real novos. Não há instalação, autenticação ou pacote local novo. CI poderá produzir artefatos; preparar uma candidata consolidada pelo controlador depois de integração/CI terminal, sem iniciar install/preflight interativo durante a ausência.

Dívidas de R2: aceite instalado de Central/Launcher e mídias do mesmo jogo; consulta remota com credencial; conteúdo por adapters demonstráveis. A projeção deste lote é carregada ao abrir/reabrir o Launcher; atualização ao vivo dentro de um processo já aberto não foi implementada nem promovida. R3 segue dependente dos aceites aplicáveis e da definição/prova de navegação e sessão; não se removeu caminho existente.

## Commits e retomada remota

Branch mantida: `codex/product-recovery-2026-10-16`. Commits funcionais: `1d83e5b80423c1cdaa85a423f1598d9ac0982a88` (leitor, página e regressões) e `2097fcc063c7c11910f0f08470ebab776e0e5fd0` (integração de `app.py` por último e teste do entrypoint). A produção testada está em **2097fcc0**; o commit documental seguinte não muda produção/testes. Último fetch manteve origin/main em `0979765171a32e7532f1f650a889962ba375d58d`.

Próximos passos autorizados no mesmo checkout: push da branch atual; PR para main; conferir os oito jobs terminais e a cobertura Python 3.14 contra o run 39636317805; integrar somente com checks verdes. Não usar force push, bypass ou publicação pública. No fechamento remoto, registrar o run/SHA/PR no checkpoint antes de qualquer release.

A candidata histórica **09797651 não inclui estes commits** e não pode comprovar a projeção nova. Seu bundle privado histórico permanece preservado, sem nova tentativa. Uma candidata consolidada deve ser preparada de tip exato de main e CI push verde do SHA exato, com checkout limpo e alinhado. A instalação continua PENDENTE_CREDENCIAL e requer o operador; nenhum install/preflight interativo será iniciado nesta ausência. Rollback histórico instalado 3f87657c não foi ativado nem revalidado para dados reais v23 nesta sessão.

Para acompanhar a próxima operação, usar `rtk proxy gh run list --branch codex/product-recovery-2026-10-16 --event push --limit 3` e consultar o run do SHA corrente no estado terminal. Logs locais completos já terminaram; não há teste/GUI ou operação de host em andamento neste checkpoint.

## Integração R2 confirmada em 2026-10-24

PR [#265](https://github.com/Misael-art/steam-zero/pull/265), head `63434b1f78b79ca69ed21ec6b3fc3cd55e9e2b99`, merge normal `927dee4a1b3492c1509451683586a18c1c66a74b` em 2026-10-24T02:35:57Z. CI PR [40053026587](https://github.com/Misael-art/steam-zero/actions/runs/40053026587) e CI push exato [40054839735](https://github.com/Misael-art/steam-zero/actions/runs/40054839735): oito jobs success. Cobertura equivalente Python 3.14 passou de 85,32805755395684% (09797651) a 85,33807010226244% (PR R2), +0,01001254830560 ponto; recibos 14/15. Nenhum bypass ou force push.

Retomada atual: consolidar R3/D-08 após CI/integração e só então preparar candidata útil pelo controlador. As instruções anteriores de push/PR R2 são histórico concluído. Release instalada continua 3f87657c, sem alteração ou nova tentativa do bundle 09797651. Fila acima permanece única.

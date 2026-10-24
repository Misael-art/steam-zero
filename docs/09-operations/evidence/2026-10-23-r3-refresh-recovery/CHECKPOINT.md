# R3 — resíduo D-08 de refresh e recuperação

Base `63434b1f78b79ca69ed21ec6b3fc3cd55e9e2b99`, mesma branch e checkout canônicos. Assunção serial após código, testes e checkpoint R2. R2 integrado pelo PR #265 em main `927dee4a1b3492c1509451683586a18c1c66a74b`; CI PR `40053026587` e push `40054839735` concluíram os oito jobs com sucesso. Credencial/instalação e prova física continuam pendentes. Sua pendência não bloqueia esta correção independente, conforme orientação atual do proprietário.

Handoffs prospectivos dos paths QML/teste pela WS-2026-10-JOURNEY-PLATFORM-PROJECTION e do README de recuperação pela WS-2026-10-RECOVERY-R2-GAME-DATA, registrados antes de editar. Nenhum escritor concorrente observado.

Baseline a reproduzir: `showLaunchError` deixa erro pendente para o próximo refresh válido. HTTP não-200 e view inativa consomem o erro pendente ao mostrar outra causa, mas o catch de JSON ilegível não consome. Recuperar a bridge pode ressuscitar a recusa anterior.

Próxima ação: controle negativo QML; corrigir catch; testar falha, recuperação, seleção, resposta atrasada e preservação do erro válido uma única vez. Depois gates e checkpoint remoto. Não iniciar instalação/preflight interativo durante ausência.

[Fila única de instalação e limites R0/R1/R2](../2026-10-23-r2-launcher-data/CHECKPOINT.md). Esta etapa não comprova gameplay, daemon instalado, Deck, controle/toque nem jornada completa R3.

## Resultado focal

Controle negativo (`01-negative-control.log`): o teste Python sai 1; QtTest tem 2 falhas (JSON malformado e `null`) exatamente em `pendingLaunchError`, que ainda continha `OLD-LAUNCH-REFUSED`. Ramos HTTP 503 e view inativa já passavam.

Correção: o catch de leitura passa a consumir `pendingLaunchError` quando publica a causa de resposta ilegível, assim como os outros ramos de falha. Não remove a recusa válida: teste próprio confirma que o primeiro refresh válido a exibe uma vez e o seguinte limpa. Recuperação restaura seleção e contexto publicados; respostas atrasadas continuam rejeitadas pela sequência existente.

Runner isolado de `test_launcher_journey_e2e.py`, `test_journey_complete_facets.py` e `test_launcher_return_cycle.py`: **14 passed**, 10,26 s, exit 0, estado real sem delta (`02-focused.log`). QtTest usa o componente real offscreen com resposta de fixture. Ruff check/format integrais e mypy 306 fontes passaram; produção Python não mudou. Há QWARN anterior de `SceneEsdeView.qml:642` no caso legado de facetas; teste passou, sem inferir fidelidade visual.

Integral deste novo lote será executada na árvore congelada, removendo PYTEST_DEBUG_TEMPROOT pelo runner existente. Não interromper nem repetir antes de resultado terminal. Log privado `/tmp/steamzero-r3-full.log`; cobertura `/tmp/steamzero-r3-local-coverage.json`. Sem instalação e sem teste físico.

## Checkpoint funcional de 2026-10-24

Integral **exit 0, 6848 passed, 47 skipped**, 2676,52 s (`03-full-local.log`), sem delta de estado real. Fonte congelada: 1262 hashes conferidos, nenhum alterado durante a execução; commit funcional `02248b0d3d666124bafe253b708a2d36a29f0bf0` (`05-local-checkpoint.json`). Ruff check/format, mypy, independence, boundaries, component-lock, capability-matrix e status aprovados em `04-static-gates.log`; visões serão reconciliadas após documentos.

Cobertura local **85,50778834121996%**, acima do gate 85, mas -0,01725948192788 ponto percentual contra R2 combinado. Os únicos deltas são em Python inalterado: corrida de leitura /proc, espera do teclado virtual, sondagem de arquivo, retry SQLite WAL e ramo SSE. Não apresentar como ausência de regressão equivalente. A comparação decisória será CI Python 3.14 `not visual`, igual ao perfil R2; fonte Python e testes Python iguais.

Próxima ação: fechar docs/claims e status, alinhar main sem perder commits no mesmo checkout e publicar a branch existente. Integrar somente com oito jobs terminais verdes e comparação equivalente registrada. Nenhum pacote, instalação, autenticação ou prova física novos.

## Integração remota de 2026-10-24

PR [#266](https://github.com/Misael-art/steam-zero/pull/266), head `b59651dbc92152d6cf06a4918a4662c8a5835066`, CI [40082089157](https://github.com/Misael-art/steam-zero/actions/runs/40082089157): **oito jobs terminais success**. Merge normal `59ecc2d8f0f66e27ce9aefa1dd7656451a610997` em 2026-10-24T09:51:08Z, sem bypass/force push.

Comparação equivalente CI Python 3.14 `not visual`: base main `927dee4a`, run 40054839735, **85,33231694161981%**; R3 PR **85,33519352194112%**, +0,00287658032131 ponto. Sem regressão contra a base integrada. PR R2 marcou 85,33807010226244%, preservado no recibo; não confundir PR e push da mesma fonte Python, sujeitos a ramos de ambiente. Somente os dois arquivos QML mudaram funcionalmente entre base e PR (recibos 06–09).

R3 não recebeu nova prova instalada, de gameplay ou hardware. Os 19 warnings da integral local foram preservados (incluem ResourceWarning SQLite em testes preexistentes), sem apresentar a suite como livre de avisos. Este slice não fecha a recusa D-08 observada na overlay real nem D-12/D-22/D-23.

Próximo trabalho serial já assumido: R2/year-alias, integral ativa em /tmp/steamzero-r2-year-full.log. A árvore local só será alinhada ao merge após resultado e commit limpo; não misturar Git local com os bytes congelados. Preparação consolidada aguarda também esse lote.

CI push [40083592868](https://github.com/Misael-art/steam-zero/actions/runs/40083592868) concluiu **oito jobs success** no merge exato `59ecc2d8f0f66e27ce9aefa1dd7656451a610997` (recibo 10). Operador presente em 24/10 solicita instalação agora dessa main aprovada; ajuste R2/year-alias 7d89ab0f preservado separadamente, ainda sem CI remoto.

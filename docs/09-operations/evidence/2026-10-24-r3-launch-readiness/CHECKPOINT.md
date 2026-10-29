# R3 — prontidão e preparação visíveis nos detalhes

Assunção serial prospectiva em 2026-10-24 na base744d300bf1672275ce15c08cf2fe44d31d067ab1, mesma branch/checkout e executor. R2/year-alias local fechado, PR#267 CI40087147293 em curso. Nenhum outro executor observado nos paths. Main/host ativo59ecc2d8. Direção atual: desenvolvimento contínuo sem senha/autenticação até nova direção expressa; nenhuma instalação/preflight neste lote.

Baseline de código: LauncherGamePage recebe ações/descritivos, mas não publica prontidão. LauncherBridge só consulta readiness após Jogar; _auto_prepare mantém threads/erros reais, sem observação pública. Router faz fail-open quando a consulta falha, útil para launch, mas isso não pode ser exibido como prontidão comprovada.

Primeiro slice: endpoint autenticado somente leitura para prontidão e estado da preparação existente; ação explícita de preparar reaproveita _auto_prepare sem launch e sem novo job/supervisor. Observação de consulta falha é unknown, mantendo o preflight de launch como autoridade. Componente de detalhes consome estado público, exibe atividade indeterminada real (sem percentual inventado), erro/recuperação e ignora callbacks de jogo/página anteriores. Primeira composição: detalhes do shell Home; Jornada autorada e hardware conservam aceites próprios.

Handoffs antes de editar: JLS cede launcher_ui.py, LauncherMain.qml, LauncherShell.qml e teste de integração existente. R2 cede página/teste QML (este último não será editado salvo necessidade), app.py shared e README de continuidade. Novos componente/testes sem claim anterior. Reconciliar e devolver paths cedidos após checkpoint integrado. Contratos de sessão/launch existentes e cache/identidades preservados.

Próxima ação: controles negativos no endpoint e UI, implementação mínima, regressões HTTP/QML e gates integrais na árvore congelada. Sem mutação de dados reais no teste; runner isolado com PYTEST_DEBUG_TEMPROOT removido.

## Focadas e controles

Baseline HTTP: endpoint readiness/prepare inexistente (404) e observador separado ausente. Log01 tem12 falhas, das quais9 eram erro da factory do teste sem on_launch obrigatório; factory corrigida antes da prova positiva, sem mudar produção para acomodar fixture. Não contar essas9 como reprodução funcional. Resto confirma ausência de contrato.

Backend positivo:54 passed incluindo regressões antigas de launch. Broad final:64 passed em25,08s (04). Depois acrescida exceção da porta de preparar à regressão de falha/retry; rodada final dedicada passa em05, sem mudança de produção. QML negativo02:13 casos pass e2 fail (callback duplicado alterava estado, Enter não acionava). Corrigidos callback de uma só conclusão e Enter, com foco da janela de harness restaurado e conflito visible/visibility removido. QML final03 exit0, teste usa raiz LauncherMain real e ponte HTTP autenticada: detalhe→preparar→preparing→ready, sem spawn. Canal temporário em fixture privada; nenhuma credencial em argv/evidência nova. A sonda inicial tentou argumentos extras não aceitos pelo qmltestrunner e foi corrigida, sem mudar produção por esse erro.

Observação bounded2s do produto separada do fail-open legado de launch20s. GET não inicia nem consome preparação/erro; POST explícito reutiliza worker e lock existentes. Falha da consulta é unknown. Atividade publicada depende de thread real e não é percentual. Polling enquanto preparing e leitura única após resposta perdida de POST; sem repetir mutação automaticamente. Troca de jogo/página e callbacks duplicados descartados. Home/detalhes é a primeira composição; cartões/Jornada autorada/hardware permanecem em aceite próprio.

Ruff/format integrais723arquivos e mypy306fontes verdes (06). Digests de escopos compartilhados são reconciliação de fonte/documentos, sem novo aceite físico dos itens antigos. Próxima operação: gates de arquitetura/status e integral isolada em fonte congelada. Log /tmp/steamzero-r3-readiness-full.log, cobertura /tmp/steamzero-r3-readiness-coverage.json. Aguardar saída terminal; não interromper nem editar src/tools/tests. Sem senha ou preflight de instalação.

Integral iniciada em2026-10-24T11:05:54Z, operação ativa no runner isolado, log e snapshot1266 em/tmp conforme acima; não repetir antes de saída terminal. Memória disponível4,6GB e disco113GB no início, nenhum teste/QML próprio concorrente. Estados before/after das focadas:12984files/2124dirs/1437433483bytes/mtime1792839271376207207, sem delta em cada execução.

Enquanto a integral corre, R2/year-alias foi integrado pelo PR267/mainad742ca3 após oito jobsCI40087147293 e comparação equivalente sem regressão. Nenhuma mudança de fonte local para acompanhar o merge remoto. Nova baseCIpush40088910465 em andamento; árvore local será alinhada somente limpa, depois dos commits.

Limite operacional já conhecido: prepare_game materializa e revarre, mas _launch_preflight ainda pode rejeitar a origem archive. Não afirmar que fixture de prontidão depois de preparar prova essa jornada real. Próximo slice deve reproduzir com archive temporário e preservar ID/preferências ao resolver a projeção gerenciada, usando o materializador existente. Nenhuma alteração desse slice durante a integral atual.

Retomada13:10UTC: integral anterior sem sessão/processo nem logs/cobertura temporários; saída desconhecida, não aprovada. Não há teste em andamento. Novo pedido de migração priorizado, fonte e focadas preservadas. Retry explícito agora revalida requisitos depois de falha antes de começar trabalho novo; teste de mudança externa acrescentado. Gates finais e logs persistentes serão no handoff de24/10.

26/10: os logs públicos de baseline e callback negativo receberam somente
normalização de espaços finais para o check de whitespace do Git. Resultados
negativos e tracebacks foram mantidos; os bytes brutos e hashes originais foram
preservados no recibo privado de recuperação. Isso não é nova execução.


## Continuidade de 28/10 — archive preparado com identidade preservada

Base `3f010cec`, branch de continuidade e PR #268 conferidos, remoto sem
 divergência e oito jobs CI anteriores verdes (run 40753525934).
Pedido atual autoriza código, testes, commit/push/PR; sem instalação ou autenticação.

Baseline controlado: a varredura publicava um archive PS5, mas `_load_library_cache`
o descartava ao reclassificar `archive-needs-extraction`. Além disso, o preflight
recusava qualquer archive e `inspect` nunca retornava `current`. Não houve prova
de troca de ID; a identidade canônica é a origem compactada.

Correção: reidratar archives recuperáveis apenas sob a política `extract` declarada;
resolver no preflight compartilhado um único alvo base pelo classificador existente.
O manifesto gerenciado v2 guarda hash da origem e hashes de todas as entradas.
Markers antigos precisam de nova preparação, sem promoção implícita. Bytes ausentes
ou alterados podem ser preparados novamente; symlinks, ownership/identidade inválida
e manifesto divergente bloqueiam. Seleção ambígua não escolhe primeiro arquivo e
multidisco mantém seu contrato independente. Nenhuma nova fonte de catálogo ou executor.

Evidência: `tests/integration/test_launcher_archive_preparation.py` usa scan real,
ZIP sintético, transação e releitura do catálogo, mantendo ID e preferências em disco;
regressões do materializador cobrem corrupção, origem alterada, legado, symlink,
manifesto inválido, ausência e ambiguidade. A parametrização real em
`test_launcher_readiness_qml.py` percorre LauncherMain → detalhes → Preparar via
Enter → bridge autenticada → materializador → rescan → pronto, sem spawn.
Fonte e Qt/offscreen apenas; não prova gameplay, release instalada ou hardware.
Logs locais regeneráveis em `build/agent-runs/r3-archive/`; nenhum payload privado
foi usado. Resultados integrais registrados no fechamento abaixo.


### Fechamento em fonte — 28/10/2026

| Item | Commit | Prova |
|---|---|---|
| Projeção verificada e alvo único | `d41923f48bd2c9a1bca32ab2dc33f5c517ac967e` | hashes, ownership, symlinks, legado, ausência, corrupção, recuperação e ambiguidade |
| Identidade e continuidade do preparo | `eb39b4b6f2d0b6ec4c51ffd1361ed64b08ce56c5` | scan/preparo/rescan/reabertura e LauncherMain/HTTP/Qt offscreen |

Integral com cobertura: **6.893 passed, 48 skipped, 1 failed**, 20 warnings,
2075,98 s. Cobertura **85,573587%** (gate de 85% atendido). O resultado bruto
não é uma integral verde. A única falha foi
`test_archive_without_materialization_is_refused_before_emulator`: o teste
substituía `_current_game` por um registro fora das bibliotecas permitidas e
esperava o texto do veto incondicional antigo. O preflight agora resolve uma
projeção validada; a fixture foi ajustada para ZIP real numa raiz controlada,
com o mesmo código E-CONTENT-INCOMPLETE, motivo exato do archive não preparado
e uma nova asserção que reprova qualquer consulta ao runtime. Nenhum teste foi
removido, pulado ou afrouxado. Essa mudança de contrato está no commit eb39b4b6.

Reteste final da área: **53 passed em 14,59 s**, incluindo o módulo inteiro de
runtime remediation, materializador, BIOS/preflight, HTTP e QML do Launcher.
Os seis arquivos de produto/testes anteriores conservaram seus SHA-256 durante
a integral e o reteste; somente a fixture de remediation mudou após a integral.
O código de produto não mudou após a execução ampla. A tentativa ampla anterior
foi interrompida para trocar a releitura do manifesto por entradas já verificadas;
ela não constitui aprovação. Logs brutos preservados em build/agent-runs/r3-archive.

Ruff check/format, mypy (306 fontes), independence e boundaries passaram.
Catálogo/digests/visões regenerados sem promover outros itens; validação específica
de status acompanha o commit documental. A referência a py.typed de um agregador
sem digest não exigiu criar artefato nem alterar o catálogo por conveniência.
A comparação de cobertura com CI canônico fica para o SHA publicado: o baseline
local de núcleo era 85,398001%, mas tem seleção diferente da integral com QML.
Os 48 skips mantêm seus motivos originais; não contam como aprovação.

Estado pessoal antes/depois sem delta nos runners. Nenhuma instalação, release,
merge, deploy ou mudança de boot. Somente readlink de /opt/steamzero/current:
`releases/2.0.0rc1-59ecc2d8f0f6`; runtime ativo e rollback não foram revalidados.
Aceite instalado/físico e capturas da release ficam pendentes de autorização
própria. CI novo permanece pendente até publicação, sem herdar o run anterior.
Próximo lote seguro: prontidão/progresso no cartão, reutilizando as portas existentes.

Reprodução: carregar .steamzero-dev/env.sh e executar pelo runner isolado
`tests/integration/test_launcher_archive_preparation.py` e
`tests/integration/test_launcher_readiness_qml.py -q`. Na interface, abrir os detalhes
do archive e acionar Preparar; o preflight usa o alvo extraído verificado quando
os demais requisitos de runtime estiverem satisfeitos.

Validação documental: a primeira tentativa encontrou disputa de claim no teste
de remediation (12passed/1failed); cessão serial reconciliada e visões regeneradas.
Reteste final do módulo de status: **13 passed**, sem delta no estado pessoal;
status-check aprovado. O fechamento preserva resultados brutos e separa o reteste.


## Continuidade — cartão e andamento observado, 28/10/2026

Base52b9ebf8 e PR268 conferidos: oito jobs do run40780398054 terminaram verdes,
incluindo QML canônico. Essa evidência fecha o CI anterior, não prova instalação.
Baseline da fatia nova: LauncherHome não tinha observador nem estado/progresso
no cartão; o teste raiz procurava selectedGameReadiness e falhou nas duas variantes.

Um único LauncherReadiness segue o foco semântico, com debounce200ms, e publica
badge do cartão nativo e faixa operacional da Home/Cinema. A faixa reserva área
da cena para manter título e atalhos visíveis. Nenhum passeio pela biblioteca
inicia preparo. Header/ausência de seleção/Home oculta não consultam a porta.
Preparar continua explícito nos detalhes. Ao voltar durante extração, o mesmo
GET autenticado observa preparando/erro/pronto e conserva seleção. A porta atual
não publica totais: a barra é indeterminada, sem porcentagem estimada. ReducedMotion
usa texto estático, sem animar a barra ou spinner. Consulta sem callback expira
em8s, admite retry e invalida resposta atrasada; POST incerto mantém a observação
sem repetir a mutação. Nenhum catálogo/executor/cache paralelo foi criado.

Focadas finais:31passed, incluindo gesto/foco/timeout/retorno/busca, HTTP,
ZIP real e transação. QML adiciona regressões de seleção rápida, resposta antiga,
header/Home oculta, timeout/retry, Cinema e reducedMotion. Captura PNG de fixture
real em Qt/offscreen inspecionada: build/agent-runs/r3-cards/02-preparing.png;
é artefato local regenerável, não captura de release instalada nem prova GPU/FPS.
Sem delta no estado pessoal nos runners. Logs em build/agent-runs/r3-cards/.
Fonte de produto, CI visual canônico, instalação e hardware mantêm aceites separados.
Resultados integrais são registrados no fechamento desta fatia.

Regressão ampla antes do checkpoint: **128 passed em72,90s**, cobrindo todas as
integrações test_launcher_*.py. Arquivos de produto/teste congelados por SHA-256
antes da integral; nenhum gate físico promovido.


### Fechamento do cartão em fonte — 28/10/2026

| Item | Commit | Prova |
|---|---|---|
| Observação limitada e apresentação somente leitura | `d9d8f42ba05f09851cf81430a00866ba3d96b289` | timeout, resposta antiga, leitura sem preparar, andamento sem porcentagem |
| Cartão selecionado e retorno Home/Cinema | `d93bae2e09e9cf1d6fad6b4494473365807ef57f` | 128 integrações do Launcher; ZIP/transação reais e Qt/offscreen |

Integral oficial: **6.894 passed, 48 skipped, zero failed**, 19 warnings,
2270,17s (37m50s), runner exit0. Cobertura da integral: **85,559251%**.
Os cinco arquivos de produto/teste congelados conservaram SHA-256 durante a
execução. Nenhum produto mudou após a integral. Os48skips mantêm seus motivos.

A comparação exploratória com a integral anterior (que terminou com uma falha
de fixture) mostrou delta de−0,014pp em caminhos Python não alterados. Reteste
dirigido: **111 passed em15,52s**; a execução agregada ficou85,562118%.
Foi acrescentado somente um teste após a integral: uma biblioteca é retirada
depois do scan real, e o preflight deve recusar seu archive antes do runtime.
Esse teste protege custódia, sem afrouxar o contrato nem mudar produção.

A comparação de não regressão usa o **baseline verde de núcleo do CI**, mesma
seleção `-m "not visual"`, mesmos52.128statements e17.626branches. Artefato
coverage-python-3.14 do run40780398054, head52b9ebf8, artifact12856673513:
663.174bytes comprimidos, somente dados baixados para build/agent-runs/r3-cards/
baseline-ci-coverage, recibo/hash local em baseline-receipt.json. Baseline:
**85,395819%**. Núcleo atual: **6.498 passed, 48 skipped, 397 deselected**,19warnings,
680,68s, runner exit0; **85,435961% >= 85,395819%**. Não houve regressão nesse
comparativo. Cobertura da integral e do núcleo são reportadas separadamente.
Não se repetiu a bateria QML depois de acrescentar o teste de custódia.

Ruff check/format (728arquivos), mypy306, independence, boundaries e status-check
aprovados. A documentação final regenera apenas os digests afetados e as visões;
validação específica do catálogo acompanha o commit documental. WORKLOG é append-only.

Nenhuma instalação, release, merge, deploy, boot ou autenticação privilegiada.
Readlink somente: releases/2.0.0rc1-59ecc2d8f0f6; runtime efetivo e rollback não
revalidados. A captura funcional é de fonte com fixtures e Qt/offscreen, sem
aceite instalado/físico, controle real, desempenho ou promoção da Theme Engine.

Reprodução da captura: carregar .steamzero-dev/env.sh e executar
`STEAMZERO_CAPTURE_READINESS=1 rtk proxy .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_readiness_qml.py -q`.
Próximo lote seguro: conferir se o gap existente
GAP-AURA-LAUNCHER-BRIDGE-DISCONNECT-RECOVERY ainda é reproduzível e fechar a
jornada de reconexão se necessário, usando os serviços e workstreams existentes.
Começar por tests/integration/test_launcher_request_timeout.py e
 tests/integration/test_launcher_return_cycle.py. Instalação e provas físicas
permanecem pendentes de autorização/aceite próprios; não iniciar autenticação.


## Recuperação de consulta da bridge — 28/10/2026

Base2a3129b0. CI40793431084 terminou com oito jobs verdes, incluindo visual canônico.
A definição histórica de GAP-AURA-LAUNCHER-BRIDGE-DISCONNECT-RECOVERY documenta
watchdog já corrigido em fonte e recaptura instalada ainda pendente. Esse gap
permanece aberto; esta fatia fecha defeitos de consulta/retry demonstrados em fonte.

Baseline HTTP controlado com a fonte anterior: três regressões QML. O retry
zerava model e destruía LauncherShell, seleção, página e trava de sessão; JSON null
virava ready sem catálogo; resposta antiga podia substituir um retry mais recente.
Log válido: build/agent-runs/r3-bridge/baseline-http.log. Tentativa inicial de fixture
com método QML read-only não foi usada como prova do produto.

Correção mínima: manter o último modelo válido, aplicar resposta validada por
geração e identidade do canal, cancelar consulta de modelo substituída e XHR
expirado pelo watchdog existente. O handle é o XMLHttpRequest já criado, sem
catálogo, executor ou supervisor adicional. O estado UNSENT prova o cancelamento
lógico conforme o [contrato Qt](https://doc.qt.io/qt-6/qml-qtqml-xmlhttprequest.html).
Não se assume EOF TCP imediato nem cancelamento de operação já recebida pelo serviço.
O texto de timeout de launch agora informa ausência de confirmação, em vez de
alegar que o jogo não iniciou. Correlação/ACK perdido permanece no gap próprio.

A recuperação apresenta erro legível com foco e alvo de48px, Enter para retry e
Escape para voltar ao cache/sair quando não há catálogo. Foco retorna à superfície
visível. HTTP real da fixture controla resposta antiga, erro503, JSON inválido e
peer retido; 128 integrações Launcher passaram em80,95s. Capturas Qt/offscreen
inspecionadas: build/agent-runs/r3-bridge/02-query-unavailable.png e
03-query-recovered.png. Sessão ativa é estado controlado da fixture; não houve
spawn nem prova de jogo físico. Fonte e testes são congelados antes dos gates.

Os limites permanecem: sem instalação, release, merge, deploy, boot ou autenticação
privilegiada. Não promover Central, Theme Engine, Studio, Aura, hardware ou desempenho.
Gates integrais e comparação de cobertura serão registrados no fechamento.


### Falha do gate e sincronismo da fixture

A primeira integral terminou com **6.894 passed, 48 skipped e uma falha**, em
2.247,76 s: `test_ui_credential_journey_e2e.py`. A localização exata corrigiu a
suspeita inicial de falha na matriz de controles. O teste envia POST de mudança
de modo à sua fixture e clica em Testar sem aguardar esse ACK; as duas conexões
podiam ser processadas na ordem inversa. O produto não participa dessa corrida.
O caso passou sozinho sem alteração. Um injetor local de 250 ms na resposta de
modo reproduziu as mesmas três reprovações QML do gate (baseline de 13,11 s).

O harness agora aguarda a resposta HTTP 200 antes da próxima ação. Todas as
asserções de sucesso, rejeição, segredo preservado e revogação permanecem.
Com o mesmo atraso controlado, a jornada passou em 6,60 s. Não há autenticação
real, alteração de credenciais do operador, espera fixa na UI ou mudança de
produto. O harness sem claim ativo foi reservado serialmente na frente existente;
o item SZ-UI-DESKTOP-AUDIT registra a manutenção de sua prova.

Logs: build/agent-runs/r3-bridge/full.log, credential-focused.log,
credential-delayed-baseline.log e credential-delayed-fixed.log. O núcleo passou
com 6.498 passed/48 skipped/397 deselected em 668,57 s; cobertura 85,435961%
>= 85,395819% do CI verde 40793431084, mesmos denominadores. Estado pessoal
monitorado permaneceu inalterado. Uma nova integral é justificada pela falha e
pela correção do harness; seu resultado será acrescentado no fechamento.


### Fechamento verificável — 29/10/2026

| Item | Commit | Prova |
|---|---|---|
| SZ-AURA-LAUNCHER: recuperação de consulta | `b4b7196d4b4f368d2074b92706a8389853f22ea9` | 128 integrações Launcher em 80,95 s; baseline HTTP com três regressões na base; seis casos Qt de retry/erro/retorno/cancelamento, incluindo dados inválidos |
| SZ-UI-DESKTOP-AUDIT: sincronismo da fixture | `9e23c1f3e8c3f3fc0be1495dd46b2b636da1c5d7` | atraso controlado de 250 ms reproduz a corrida antes da correção e passa após aguardar o ACK; asserções preservadas |

**Segunda integral: 6.895 passed, 48 skipped, zero failed**, 26 warnings,
2.350,47 s (runner exit 0). Log `build/agent-runs/r3-bridge/full-final.log` e
recibo `full-final-result.json`. Cobertura integral: **85,567853%**, reportada
separadamente do núcleo. A comparação equivalente de núcleo permaneceu em
**85,435961% >= 85,395819%**, sem regressão. Os seis hashes congelados coincidem
com o conteúdo commitado; o primeiro resultado reprovado foi preservado, sem
alterar goldens, skips, limites de cobertura ou asserções para obter aprovação.

Ruff check, Ruff format --check (728 arquivos), mypy (306 fontes), independence,
boundaries e status-check aprovados. Recibos em static-final-results.json.
O catálogo e as visões recebem somente a validação documental específica após
estes registros; não se repete a integral por mudança de digest/documentação.
O estado pessoal monitorado ficou idêntico antes/depois em ambas as integrais.

Autorização vigente: commit/push/atualização do PR #268 na branch de continuidade,
sem force push, merge, release, instalação, boot ou autenticação privilegiada.
Em 29/10, somente readlink confirmou `releases/2.0.0rc1-59ecc2d8f0f6`;
runtime efetivamente ativo e rollback não foram revalidados. Nenhuma ação
privilegiada foi executada. As capturas locais são de fonte Qt/offscreen com
HTTP e sessão sintéticos, sem spawn, controle físico ou medida de desempenho.

A recaptura instalada de GAP-AURA-LAUNCHER-BRIDGE-DISCONNECT-RECOVERY e o aceite
físico de prontidão permanecem abertos. Próxima investigação segura:
GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME. O requestId chega ao QML no retorno do
POST /launch; perder esse ACK ainda não permite correlacionar a tentativa de
modo seguro. Não adotar recibo antigo por gameId/nome. Reproduzir primeiro com
resposta do POST retida/perdida e efeito controlado, usando LauncherBridge,
LaunchRouter, recibo e observador de sessão existentes. Não há novo catálogo ou
supervisor neste lote.

Próximo comando de baseline: carregar .steamzero-dev/env.sh e executar
`rtk proxy .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_receipt.py tests/integration/test_launcher_session_observation.py -q`;
depois acrescentar a reprodução do ACK perdido antes de escolher o contrato.
Conferir CI do SHA publicado no PR antes de qualquer integração/release autorizada.


## ACK perdido de lançamento — 29/10/2026

Base 4c829a8744118a1a0ccdfc86252fe67489f63976, CI 40831063419 com oito jobs
verdes, incluindo visual canônico. Continuidade serial autorizada para fonte,
commit/push/PR #268; sem autenticação, instalação, release, merge ou boot.

Baseline HTTP/QML: três casos reprovados em 10,53 s. Após POST aceito com ACK
perdido, a UI entrava em failed e liberava nova tentativa; uma recusa pré-spawn
não podia ser correlacionada; pedido que nem chegara ao serviço era tratado
como falha conclusiva. Log: build/agent-runs/r3-launch-ack/baseline-qml.log.
O gate de foco existente distinguiu corretamente canal ausente antes do envio:
esse caso continua sendo falha comprovadamente anterior a qualquer efeito.

Contrato aditivo: /model anuncia launchCorrelation.clientRequestId; somente
quando anunciado, QML envia um identificador por tentativa no POST /launch e
consulta /session com o mesmo clientRequestId. O requestId de recibo do servidor
continua distinto. A bridge associa as duas identidades sob o lock existente;
retém apenas o último pedido aceito, até a próxima aceitação ou o fim da bridge.
Repetição exata desse pedido retido devolve o mesmo recibo sem novo efeito;
reuso com argumentos diferentes é recusado. IDs são ASCII allowlisted, 1–128
caracteres, validados antes do efeito. Clientes/modelos antigos conservam as
rotas legadas, sem inventar correlação por nome ou gameId.

O recibo retido alimenta a mesma _session_locked, sem segundo observador,
catálogo ou supervisor. Uma leitura perdida ou consumo por observação legada
não apaga o único notStarted correlacionado. Confirmação exige o sessionId exato
do recibo; tentativa pendente, delayed, unconfirmed ou sessão externa não viram
running. GET com identidade divergente não consulta/adota a tentativa atual.
Uma resposta de POST antiga é descartada pela geração/identidade da UI.

Timeout após envio mantém launching e a trava, informa incerteza e continua
somente leituras; não há repetição automática de POST. A leitura correlacionada
pode confirmar running, confirmar notStarted ou conduzir ao retorno canônico.
ACK que expira depois da confirmação não rebaixa a sessão para erro. Se o pedido
não foi recebido, permanece não confirmado, com orientação para a Central.

O percurso por teclado reproduziu também foco roubado para launcherHome escondida:
closeSessionOverlay restaurava Home após a recusa mesmo com detalhes visíveis.
A recuperação agora foca o botão da falha e depois a superfície visível. Enter
real confirma a dispensa e a nova tentativa; o harness não força foco.
Logs de reprodução e correção: keyboard-flow.log, focus-diagnostic.log,
keyboard-final.log. Nenhum teste existente foi enfraquecido.

Regressão final: 145 integrações Launcher passaram em 87,10 s, inclusive os
17 novos casos (quatro Qt/HTTP e treze de contrato). Cobrem ACK perdido, primeira
observação perdida, ACK expirado depois de running, pedido não recebido,
notStarted/recuperação, IDs inválidos, sessão externa, identidade substituída e
replay concorrente com efeito único. Recibos e sessão são controlados, sem spawn.
Estado pessoal monitorado inalterado. Capturas 01–04 no diretório local do lote,
fonte Qt/offscreen fullscreen 800x800, sem alegação de Deck/hardware/desempenho.

Limites: a retenção não é persistida entre processos/reboots e não é histórico
ilimitado de idempotência. Não prova confirmação de jogo Steam sem recibo.
GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME permanece aberto para esses limites e a
prova instalada/física; o lote fecha o ACK perdido com a bridge viva. Os demais
aceites de prontidão, desconexão física e instalação permanecem independentes.
Gates integrais e cobertura equivalente serão acrescentados no fechamento.


### Fechamento do ACK perdido — 29/10/2026

| Item | Commit | Prova |
|---|---|---|
| SZ-AURA-LAUNCHER: correlação, retenção e foco | `36e01f701eba1185f1957e2b30105bd754da0284` | 145 integrações Launcher; 17 casos novos, quatro Qt/HTTP com teclado real e treze de contrato |

**Integral concluída: 6.912 passed, 48 skipped, zero failed**, 19 warnings,
2.857,35 s, runner exit 0. Recibo full-result.json e log full.log em
build/agent-runs/r3-launch-ack. Cobertura integral: **85,576152%**.
Núcleo: **6.511 passed, 48 skipped, 401 deselected**, 19 warnings, 848,76 s,
runner exit 0. Comparação equivalente de seleção not visual:
**85,447227% >= 85,398687%** do CI verde 40831063419, head 4c829a87.
O código Python novo muda os denominadores: atuais 52.164 statements/17.644
branches; baseline 52.128/17.626. Não se alegam denominadores idênticos.
Artefato 12879485133, coverage-python-3.14, 663.143 bytes comprimidos; origem,
hash e totais preservados em baseline-receipt.json. Sem regressão de cobertura.

Ruff check/format (729 arquivos), mypy (306 fontes), independence, boundaries e
status-check verdes. Cinco hashes de fonte/teste permaneceram intactos durante
os gates e coincidem com o commit funcional. Nenhum golden, skip, limite de
cobertura ou teste existente foi alterado para acomodar o resultado.
Estado pessoal monitorado idêntico antes/depois nos gates concluídos; nenhum
warning de escritor externo. Validação documental específica acompanha o commit.

A primeira tentativa de integral foi interrompida por SIGTERM, saída 143, sem
resumo de pytest nem recibo terminal; **resultado desconhecido, não aprovado**.
Não havia pytest ativo após a interrupção. Remetente do sinal não determinado.
Log full-interrupted.log e full-interrupted-result.json preservados. Repetiu-se
somente a integral, em sessão separada; núcleo/cobertura não foram repetidos.
A passagem concluída acima é a prova integral válida, com o mesmo fonte.

Sem instalação, release, merge, deploy, boot ou autenticação privilegiada.
Readlink somente: releases/2.0.0rc1-59ecc2d8f0f6; runtime ativo e rollback não
revalidados. Capturas 01–04 inspecionadas de fonte Qt/offscreen, sem spawn nos
17 casos novos. O botão de recuperação tem foco visível e Enter executa o retry;
o retorno preserva library:second. Nenhuma prova física ou de desempenho.

Próxima reprodução segura: encerrar/recriar somente uma bridge de fixture com
sessão controlada já aceita e verificar a continuidade entre processos. O
LaunchPlan.context_payload existente guarda apenas gameId/focusId e
consume_context remove esse contexto; não há clientRequestId persistido neste
lote. Começar por src/steamzero/launcher/launch.py, launcher/app.py e
adapters/launcher_session.py, usando o estado canônico existente. Não migrar
schema, adotar sessão por nome/PID/gameId ou promover Steam sem recibo por
inferência. Provas instaladas/físicas e autorização de host continuam pendentes.

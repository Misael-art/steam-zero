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

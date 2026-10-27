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

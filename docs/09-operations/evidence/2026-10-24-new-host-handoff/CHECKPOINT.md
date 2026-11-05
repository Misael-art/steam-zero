# Migração para host novo e bootstrap de desenvolvimento

Pedido expresso do proprietário em24/10: diagnosticar e preservar o trabalho, preparar wrapper para host sem instalação, commit/PR e retomada por novo agente, sem depender deste disco. Novo pedido prioriza a migração; permanece sem autorização para pedir senha ou instalar neste host. Código e diagnósticos públicos pelo GitHub; dados privados só em arquivo privado/destino externo confirmado.

Assunção serial na branch existente, base744d300b; fonte de prontidão R3 implementada com focadas64+14 e estáticos verdes. Integral iniciada11:05:54UTC perdeu a sessão e os logs temporários antes da retomada13:10UTC: processo não existe, /tmp limpo, .coverage ausente. **Resultado desconhecido, não aprovado**. Logs focados preservados no diretório R3. Revisão adicional revalida requisitos no retry explícito, para impedir preparação já desnecessária ou inaplicável após mudança externa; regressão adicionada. Nova integral usará build/agent-runs, não /tmp para resultados.

Handoffs prospectivos: README de recuperação vem da WS-R3-LAUNCH-READINESS; demais arquivos novos/AGENTS/RTK/gitignore sem outro claim exclusivo observado. Nenhuma branch/worktree nova neste host. Bootstrap será testado em fixtures/plan, sem instalar dependências atuais nem tocar /opt/etc/boot. Um executor, código R3 concluído antes do bootstrap; gates finais cobrirão o conjunto.

Inventário inicial: release antiga ativa59ecc2d8; main remotaad742ca3 (PR267), confirmar antes de integrar. Dados fora do Git: data≈1980MiB, state≈1371MiB, config pequeno, cache≈1657MiB reconstruível. Pacote privado de21/10 ainda existe; cópia externa dele não foi comprovada. Acervo ~/emulation era≈341GB na fotografia anterior, nunca publicar no repo. Nenhuma cópia em armazenamento persistente Codex foi confirmada pelas ferramentas; conexões Dropbox/Drive sugeridas e destino pendente do proprietário. Não declarar backup externo só por existir arquivo/hash local.

## Recuperação e raiz única — 26/10/2026

Checkout transferido por rename para `$HOME/Projects/SteamZero`; 3.641 entradas
de fonte conferidas por identidade/hash, com WIP preservado. A base avançou por
fast-forward de744d300b para mainad742ca3, com árvores idênticas. Foram recuperadas
19 referências de fontes antigas e protegidos63commits dangling em namespace
local de recuperação; nenhum desses ramos foi automaticamente integrado/publicado.

Doze diretórios históricos dispersos foram reunidos em um arquivo privado,
com85.810entradas verificadas por conteúdo, modo e links. Um endpoint de socket
inativo, sem owner informado por fuser, foi preservado separadamente. Os recibos
privados ficam no armazenamento de recuperação da coleção. O backup de dados
existente passou pelo verificador oficial,19.613arquivos; backup e ensaio de
restauração foram retirados de build para sobreviver à limpeza de gerados.
Não há confirmação de proteção remota privada nem novo aceite instalado/físico.

Ambiente existente preservado,24launchers reposicionados; perfil isolado gerado
pelos helpers oficiais, sem ownership fictício. O isolamento in-place removeu
dependências globais e acrescentou13pacotes do lock com hashes, sem instalar
globalmente nem recriar a venv. `pip check` passou. O bootstrap standalone agora
seleciona `Projects/SteamZero` por padrão, com override explícito testável.

Primeira seleção:29passed em17,68s, sem delta no state pessoal. A integral
inicial foi interrompida após falhas e travamento; resultado não aprovado.
A reprodução da primeira falha mostrou `PYTEST_DEBUG_TEMPROOT` herdado desviando
fixtures para outro filesystem. O runner remove esse override; uma regressão
com pytest filho real e130testes focados passaram em15,21s, sem delta pessoal.
Lint, formato, mypy, independence, boundaries, component-lock e capability-matrix
passaram antes do último ajuste do runner; o fechamento registra a revalidação.
Evidência física anterior de arquivos compartilhados fica histórica; a fonte
resgatada conserva verificação dev e não herda promoção de hardware.

O traceback da tentativa seguinte localizou o custo no benchmark de10mil:
`core.fs._renameat2` repetia a descoberta de libc/ldconfig a cada renomeação.
Foi mantida em cache somente a resolução do nome da biblioteca no processo;
flags, syscall, errno e recusas de custódia permanecem no caminho existente.
Regressão real de custódia/readback/no-clobber e consulta única adicionada.
A seleção de filesystem/failure injection/organização/isolamento passou147testes
em33,47s, incluindo o benchmark de10mil, sem delta pessoal. Smoke controlado
no Btrfs do checkout confirmou custódia, restauração, inode e recusa de sobrescrita.
Nenhum arquivo privado ou processo de trabalho foi usado como fixture.

O teste de assinatura do daemon reproduziu um conflito com o perfil offline:
com `STEAMZERO_NO_DAEMON=1`, o CLI segue corretamente o fallback local, mas a
fixture esperava seu próprio servidor. A fixture in-process agora limpa a flag
somente no seu escopo privado; a regressão passou com a flag herdada ativada.
O modo offline do produto não foi removido ou alterado.

As tentativas nativas amplas foram interrompidas e continuam não aprovadas.
O fechamento usa a divisão documentada deste handoff: núcleo local com
`-m 'not visual'` e gate visual completo na imagem fixada do CI. Os recortes
QML afetados foram exercitados neste host; isso não equivale ao gate canônico,
instalação, compositor físico, input de Deck ou gameplay. O estado do CI do
SHA publicado deve ser registrado separadamente, sem herdar o verde de main.

A primeira execução de núcleo terminou com 6.484 passed, 48 skipped,
396 deselected e uma falha: a fixture de timeout de `component.apply` também
herdava o perfil offline. A reprodução isolada confirmou a causa; o teste agora
limpa a flag somente em seu monkeypatch, como os vizinhos do mesmo módulo.
Os 43 testes de `test_service_core.py` passaram com a flag herdada em 12,79 s,
sem delta pessoal. A execução inicial permanece registrada como reprovada;
o fechamento registra separadamente a reexecução de núcleo.

## Fechamento local da recuperação — 26/10/2026

A reexecução de núcleo terminou em 595,15 s: **6.484 passed, 1 failed,
48 skipped, 396 deselected**, cobertura **85,40%**, acima do gate de 85%.
A única falha foi `test_committed_catalog_and_generated_views_are_consistent`: as
atualizações documentais feitas durante a execução deixaram digests e visões
desatualizados. O resultado bruto é exit 1 e não constitui integral aprovada.
Os 1.271 arquivos de src/tools/tests conservaram os hashes congelados antes da
execução. O fechamento regenera o catálogo e registra seu reteste separado,
sem repetir a suíte pesada por uma mudança apenas documental.

Gates finais de código aprovados: Ruff check e format (727 arquivos), mypy
(306 fontes), independence, boundaries, component-lock e capability-matrix.
Não houve nova instalação, release, merge, deploy ou mudança de boot.
O gate visual canônico do SHA publicado e a prova instalada/física permanecem
independentes; CI ainda não consultado para a candidata que será publicada.

Catálogo e visões regenerados pela ferramenta oficial: `make status-render
status-check` passou. O reteste específico do catálogo é registrado no fechamento
append-only do WORKLOG. Não houve redução de guardas, mudança de testes do
catálogo ou promoção de hardware; os seis aceites físicos afetados ficam como
evidência histórica e a fonte recuperada conserva verificação de desenvolvimento.

Reteste do módulo de catálogo: **13 passed em 6,55 s**, com state pessoal
inalterado; `make status-check` aprovado. A falha documental da execução ampla
foi corrigida por regeneração, sem alterações nas validações nem nos testes.

Commit funcional recuperável: `c38e74f53c1cd6bc63ae4acba377447a0932bc3c`, na branch de continuidade.
O commit documental separado fecha regras, evidências e estado; o SHA final e
o PR devem ser conferidos no remoto antes de integrar.


## Incidente da unit privada de cotas — 05/11/2026

Prioridade expressa do operador: conter `codex-quota-panel.service` antes de
retomar o desenvolvimento. Checkout canônico confirmado, branch de continuidade
`codex/product-recovery-2026-10-16`, HEAD `fedee5cb`, três commits locais além de
`cb1d6f87` no remoto. PR #268 aberto em rascunho; os oito jobs verdes observados
pertencem a `cb1d6f87`, não às mudanças locais. As 16 modificações existentes
foram preservadas. Esta intervenção acrescenta testes de ownership, sem mudar
comportamento do instalador ou acrescentar serviço ao produto.

**Causa comprovada do ciclo:** o Python sai com código 2 porque o script
`panel_server.py` referido em `Projects/Steam Zero/plugins/codex-quota-resume`
não existe. `Restart=on-failure` e `RestartSec=5` repetem a falha. A unit está
habilitada por `default.target`, sem timer/socket, drop-in, consumidor reverso
específico ou propagação de parada observados. Sua linha de execução também
aponta para dados e pacote internos de uma aplicação legada; nenhum desses
arquivos foi aberto. Não foi lido nem copiado o plugin privado.

**Responsabilidade:** a unit pessoal tem 640 bytes, modo 0644, pertence ao
usuário e não tem marcador SteamZero. O registro de reinstalação de 21/10,
seção 2, classifica o plugin como arquivo privado externo ao Git. O código
atual não publica painel/API de cotas Codex. `tools/install_host.py` limita
as units a `steamzero-core.service` e `steamzero-core.socket`, com recusa de
alvos não gerenciados. O nome da pasta antiga não comprova propriedade pelo
instalador. A decisão para este lote é aposentar a ligação privada órfã, sem
incorporá-la ao produto, restaurar o plugin ou criar monitor substituto.
Não há valor confiável de cota disponível: estado desconhecido; nenhuma ação
de recuperação de aplicativos é autorizada por esse estado.

**Baseline real, 08:08–08:11 UTC:** contador 295, depois 320 e 331 reinícios;
`activating/auto-restart`, `MainPID=0` entre tentativas. Amostras de CPU do
cgroup por ativação: 34.812.000 e 26.934.000 ns; picos de memória 4.390.912 e
3.682.304 bytes. Esses contadores não são consumo acumulado desde o boot.
Janela de journal de 60 s: 60 registros, 5.040 bytes de mensagens;
86.903 bytes na representação JSON exportada (não mede ocupação física do
journal). Recursos antes dos testes: 126 GiB livres, RAM disponível 7,2 GiB,
swap usada 2,6 GiB, carga 2,78/3,34/2,98.

**Custódia e ação preparada:** cópia byte a byte em armazenamento privado
`$HOME/.local/share/project-recovery/SteamZero/codex-quota-panel-20261105/`,
diretório 0700, arquivos 0600, metadados e estado anterior em `before.json`.
SHA-256 da unit:
`875c818e563518ac1810f94598cf9410063307e88b9acdb465b26241d18a5a61`.
O original não foi editado, removido, remarcado nem adotado pelo instalador.
A autorização inicial condiciona a parada à propriedade SteamZero confirmada;
essa condição não foi comprovada. Ação preparada antes da autorização específica para a
unit privada: `systemctl --user stop codex-quota-panel.service`, seguido por
`systemctl --user disable codex-quota-panel.service`. Nenhum comando de
instalação, root, daemon-reload global, mask ou reset-failed é necessário.
O procedimento exigiu reconferir hash, dependências e estado, executar somente
essas duas ações e comparar observações separadas por pelo menos 60 s.
Aceite: inactive, disabled, PID zero, contador estável e nenhum novo erro
após a parada. O arquivo original deve conservar o mesmo hash.

**Rollback:** como o arquivo será preservado, `systemctl --user enable
codex-quota-panel.service` restaura o vínculo de habilitação; `start` restauraria
a execução, inclusive o defeito atual. Não executar esse rollback automaticamente.
A cópia privada permite comparar/restaurar conteúdo somente mediante revisão;
não sobrescrever uma unit que outro owner tenha mudado. A cópia é local e não
comprova backup externo.

**Reinício abrupto do host, investigação separada:** o journal do boot anterior
termina às 01:41:50 locais; o novo boot começa às 04:42:18. A consulta limitada
a eventos de OOM, watchdog, panic, thermal e hardware retornou inicializações,
sem diagnóstico causal de falha. Isso não exclui travamento, energia, pressão
de recursos, GPU ou perda do journal. Não atribuir o reboot à unit de cotas.
A integral R3 anterior parou em aproximadamente 28%, sem recibo final: resultado
interrompido/desconhecido, nunca aprovado. R2 permanece evidência histórica,
não valida o WIP posterior. Não repetir carga pesada para provocar o incidente.

**Alcance dos testes:** fixtures em HOME isolado exercitam recusa de units
sem marcador e symlinks antes da publicação; ativação repetida e retorno entre
releases preservam unit privada e seu vínculo de habilitação. Somente binários
sintéticos da fixture podem ser executados; chamadas a serviços reais falham
o teste. Script ausente é representado, nunca executado. Não existe coletor
novo: dados de cota inválidos, timeout de coleta, backoff e disjuntor não são
contratos de runtime introduzidos por este lote. Nenhuma migração de propriedade
ou substituição simultânea de serviço é feita. Os gates integrais do produto
continuam pendentes; este checkpoint não declara release pronta.


### Contenção autorizada e verificada — 05/11, 08:24 UTC

Após a explicação de que a unit não tem propriedade SteamZero comprovada,
o operador autorizou prosseguir com a correção desse legado e depois retomar
o desenvolvimento. Hash do arquivo e cópia novamente conferidos, sem drop-ins,
consumidores específicos ou propagação de parada. Somente `systemctl --user stop
codex-quota-panel.service` e `systemctl --user disable codex-quota-panel.service`
foram executados, ambos com saída 0. A habilitação em `default.target.wants`
foi removida; o arquivo original permanece intacto. Nenhum serviço substituto,
instalação, alteração privilegiada, reboot ou recuperação de aplicativo.

Imediatamente antes: 473 reinícios, CPU da última ativação 23.224.000 ns,
pico 3.686.400 bytes. Depois: `inactive/dead`, `disabled`, PID 0; systemd zerou
`NRestarts` na parada e deixou CPU/memória sem cgroup ativo. Segunda observação
69,66 s após a conclusão: mesmos estados, zero novas mensagens e zero bytes
de mensagens no journal. Hash original e backup permanecem iguais ao registrado.
Isso comprova contenção do ciclo, não correção da causa dos reboots do host.

44 testes focados do instalador passaram em 3,14 s, com perfil preservado;
Ruff check/format (742 arquivos), mypy (308 fontes), independence, boundaries e
status-check passaram. O primeiro ensaio teve 43 aprovações e uma falha do
harness por bloquear o próprio executável sintético; a allowlist da fixture
foi corrigida, sem modificar código de produção. Uma sobreposição documental
de claims foi reconciliada antes do status-check verde. A suíte integral não
foi repetida para esta contenção: não há mudança de runtime do produto. Ela
continua exigida para o lote funcional do Launcher retomado separadamente.

Durante a consulta solicitada sobre a ventoinha, uma compilação Rust iniciada
cerca de três minutos antes consumia 87,3% de um núcleo e 2,89 GiB RSS; terminou
antes da identificação de sua origem. As verificações desta tarefa também
ocorreram nesse intervalo e podem ter contribuído. A carga chegou a 6,28;
ACPI marcou 92 °C e GPU 77 °C, depois 72 °C. São amostras, não diagnóstico de
thermal shutdown. Antes da retomada, carga 2,34 e RAM disponível 7,9 GiB.
Nenhum processo alheio foi interrompido. A suíte seguinte usa runner oficial,
prioridade reduzida e afinidade de dois núcleos; nenhuma unit extra é criada.


A observação prolongada às09:43:43UTC confirmou **4.763,34 s (79,4 min)** desde
a contenção, zero novos registros, inactive/dead/disabled/PID0 e SHA original
inalterado. O teste de proteção das units foi commitado em `dd026fec`.
Desenvolvimento retomado: integral R6 passou7351/48 em2494,49s, sem delta no
perfil ou erro de cleanup, com cobertura85,8776727996022% contra85,87214763246588%.
A guarda temporária terminou sem intervenção; nenhuma unit foi criada para ela.
R4 e R5 permaneceram registradas como reprovada/interrompida, com as limitações
no recibo studio-native-context.json. R4 deixou runtime/pulse vazio; não havia
consumidor com HOME/XDG/PULSE apontando para a raiz e somente os três diretórios
vazios foram removidos. O autor da recriação não foi demonstrado.

O build anterior deixou `_build_info.py` ignorado no fonte, causando a falha de
custódia. Seus bytes correspondiam exatamente ao wheel fedee5cb; o arquivo foi
preservado no diretório ignorado de evidências do build. Não se alterou o teste
para ignorar arquivos sem dono. Depois do render, os13 testes do catálogo
passaram. Builds seguintes devem preservar esse metadado junto ao próprio wheel,
com hash/bytes conferidos e sem sobrescrever material preexistente, antes de
retomar gates do fonte. As etapas de CI de fonte e pacote já são separadas.

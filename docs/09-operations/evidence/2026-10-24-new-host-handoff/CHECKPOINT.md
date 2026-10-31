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

# Retomada em host novo — 24/10/2026

## Localização e identidade — 28/10/2026

A procura pelo nome Port Steam confirmou o mesmo projeto SteamZero: os commits
preservados de Port_Steam declaram `name = "steamzero"` no pyproject.toml.
A raiz oficial continua `$HOME/Projects/SteamZero`, branch
`codex/product-recovery-2026-10-16`, repositório `Misael-art/steam-zero`, PR #268.
O nome informado “Steam 1.0 Steam” não estabelece uma versão ou outro repositório;
use a identidade Port Steam/SteamZero confirmada pelo histórico.

Port_Steam e Port_Steam-claude já foram reconciliados na recuperação de 26/10;
não recriar essas pastas. As referências privadas `refs/recovery/20261026/port-steam/`
e os arquivos privados de recuperação preservam as fontes históricas. O bundle
antigo no SD corresponde ao main histórico `2d78366f`, já preservado nessas
referências; não é uma segunda raiz de desenvolvimento. Regras de organização,
espaço e fechamento com commit/push permanecem no AGENTS.md local e na coleção.
Este esclarecimento documental não muda o estado de aceites físicos ou a próxima
entrega de produto indicada abaixo.

## Atualização de continuidade — 26/10/2026

O checkout existente foi transferido por rename, sem clone, para
`$HOME/Projects/SteamZero`. A branch continua `codex/product-recovery-2026-10-16`.
Após fetch, a base avançou de `744d300b` para `ad742ca3` por fast-forward:
as árvores de fonte eram idênticas, e as alterações locais foram preservadas.
Confira o HEAD e o PR atuais; os SHAs abaixo continuam sendo referências históricas.

As fontes antigas Port_Steam/Port_Steam-claude, o contexto do diretório pai e
os pacotes/evidências dispersos foram recolhidos ao armazenamento privado de
recuperação `$HOME/.local/share/project-recovery/SteamZero`. Seus históricos foram
importados em `refs/recovery/20261026/`, sem merge de pesquisas nem publicação
dessas referências. O registro da coleção em `../.workspace`, relativo à raiz
do projeto, identifica a única raiz e os recibos privados de preservação.
Dados XDG, acervo, configurações pessoais, sessões de agentes e releases em
`/opt` permanecem nos destinos de seus respectivos owners; não são cópias fonte.

O ambiente `.venv` herdado foi preservado. Seus launchers foram ajustados à
nova raiz, sem recriação nem marcador fictício de ownership. O perfil foi
gerado pelos helpers existentes do bootstrap e mantém XDG separado e
`STEAMZERO_NO_DAEMON=1`. Para desenvolver neste host:

```sh
cd "$HOME/Projects/SteamZero"
. .steamzero-dev/env.sh
rtk proxy .venv/bin/python tools/run_tests_isolated.py tests/unit/test_bootstrap_dev.py -q
rtk proxy steamzero --help
```

`bootstrap-dev.sh --apply` preserva e recusa essa `.venv` não gerenciada;
não a apague, recrie ou marque como gerenciada para contornar a guarda.
Uma migração futura do ownership exige comprovação própria. Os comandos
de fonte acima não dependem dessa migração nem de autenticação administrativa.

A verificação posterior encontrou dependências globais misturadas à `.venv`.
O ambiente foi isolado in-place, desativando `include-system-site-packages`;
13 dependências ausentes foram acrescentadas pelo lock com hashes, sem recriar
o ambiente nem alterar pacotes globais. `pip check` passou. O runner também
passou a remover `PYTEST_DEBUG_TEMPROOT` herdado: essa variável desviava fixtures
para fora da árvore isolada e provocava erros de custódia entre filesystems.
Uma regressão com pytest filho real e 130 testes focados passaram após a correção.

O verificador oficial confirmou o backup privado já existente: 19.613 arquivos,
SHA-256 `270b21f2b95a36066d988ca1f9810c2c35814ca5b09429f14ae7adb53d98e374`.
O diretório privado de handoff e seu ensaio de restauração foram movidos de
`build/agent-runs/host-handoff-2026-10-24` para
`$HOME/.local/share/project-recovery/SteamZero/host-handoff-20261024`,
fora do alcance da limpeza normal de build. O arquivo e manifesto estão em
`private-backup/` nesse destino. A movimentação preservou o inode, sem recópia.
A proteção externa continua sem confirmação. Não restaurar por cima do perfil
pessoal nem publicar payloads, manifestos privados ou sessões no GitHub público.
Pacotes acima de 70.000.000 bytes permanecem manuais, inclusive quando divididos.

A retomada registrou 29 testes focados aprovados antes do ajuste de destino do
bootstrap, sem delta no state home pessoal. Os resultados do fechamento estão no
checkpoint existente de `docs/09-operations/evidence/2026-10-24-new-host-handoff/`.
Fonte, fixtures/offscreen, release instalada e hardware mantêm aceites distintos.
A release apontada por `/opt/steamzero/current` foi somente consultada, não alterada.
A próxima entrega de produto continua sendo reproduzir o gap R3 descrito ao fim
deste documento; esta organização não fecha gameplay ou prontidão instalada.

Este é o ponto de entrada atual. O host e o disco antigos deixarão de estar
disponíveis. O código e este diagnóstico devem ser recuperados do
[GitHub](https://github.com/Misael-art/steam-zero/tree/codex/product-recovery-2026-10-16),
branch `codex/product-recovery-2026-10-16`. Não dependa de caminhos locais de
uma conversa Codex para recuperar arquivos. Dados pessoais têm uma pendência
de cópia externa separada, descrita abaixo.

## Preparar o novo host

O bootstrap atual cobre **Linux x86_64**, com pré-requisito de Python de sistema
3.11 ou superior. Há planos mínimos para Ubuntu/Debian e Arch/Manjaro/BigLinux;
outros sistemas/arquiteturas precisam de adaptação, sem executar assets x86_64.
Ubuntu 24.04 atende ao Python inicial; versões anteriores não são presumidas.
São necessários internet, Git, make, certificados, curl, 4 GiB livres para o
ambiente e, para testes, pelo menos 3 GiB de RAM disponíveis e 8 GiB livres.

Baixe [`bootstrap-dev.sh`](https://github.com/Misael-art/steam-zero/blob/codex/product-recovery-2026-10-16/bootstrap-dev.sh)
no novo host, examine o arquivo e execute como usuário comum. Exemplo, se curl
já estiver disponível:

```sh
curl --fail --location --proto '=https' --tlsv1.2 \
  https://raw.githubusercontent.com/Misael-art/steam-zero/codex/product-recovery-2026-10-16/bootstrap-dev.sh \
  --output bootstrap-dev.sh
sh bootstrap-dev.sh --system-plan --ui
```

**Apenas o operador, no host novo vazio**, pode executar a preparação inicial
dos pacotes de sistema. Isso pode abrir autenticação da distribuição; o agente
não deve executar essa etapa nem pedir senha sem nova direção. O comando abaixo
inclui Qt nativo no Arch/Manjaro; no Ubuntu/Debian prepara o núcleo de
desenvolvimento, com o limite visual descrito adiante:

```sh
sh bootstrap-dev.sh --apply --system-packages --ui
```

Se os pré-requisitos já existem, use `sh bootstrap-dev.sh --apply`, sem a opção
de pacotes. O wrapper baixado fora do repo cria **um único checkout**, preserva
o histórico e busca main. Recusa destino existente; nesse caso continue pelo
wrapper dentro do checkout, sem apagar ou clonar outra árvore. Diretório padrão:

```sh
cd "$HOME/Projects/SteamZero"
. .steamzero-dev/env.sh
rtk proxy sh bootstrap-dev.sh --plan
rtk proxy sh bootstrap-dev.sh --apply --check
rtk proxy sh bootstrap-dev.sh --apply --test core
```

`--apply` baixa apenas ferramentas ausentes, verificadas por SHA-256/tamanho em
`tools/dev-bootstrap.lock.json`: uv, RTK e GitHub CLI. Usa Python gerenciado
3.14.7 e `requirements-dev.lock` com hashes; ferramentas existentes são
reutilizadas e não atualizadas globalmente. A reexecução verifica dependências
e não reinstala o lock inalterado. `.venv` sem ownership é preservada/recusada;
não a recrie para passar o bootstrap. Leia o erro e registre a situação.

Tudo fica no checkout: `.steamzero-dev/` para ferramentas, Python, cache e
perfil XDG; `.venv/` para dependências; `build/agent-runs/` para logs e cobertura.
Não há alteração do shell global, serviço em background, emulador, boot ou
release em `/opt`. Entry points do fonte são wrappers locais, sem build de
wheel. Carregue `env.sh` em cada terminal de desenvolvimento; o perfil é vazio,
isolado dos dados pessoais, e `STEAMZERO_NO_DAEMON=1` é explícito.

### UI e gate visual

Qt nativo exige `qt6-declarative`, `qt6-base`, `qt6-svg`, fontconfig, FreeType e
HarfBuzz no Arch/Manjaro. O wrapper não sincroniza bases nem faz upgrade parcial
de pacotes: se o repositório da distribuição estiver obsoleto, o operador deve
resolver sua atualização conforme a política da distribuição. Não instale todas
as plataformas/emuladores para desenvolver uma capacidade.

Ubuntu/Debian não recebem promessa de equivalência visual pelo Qt nativo. O gate
de pixels usa **Qt 6.11.2** e a imagem por digest definida em
`.github/workflows/ci.yml`, com contrato em
`ci/qml-visual/environment.lock.json`. Use o CI canônico para essa prova; não
atualize goldens para acomodar outra distro. `--test core` exclui os testes
marcados visual; skips de harness por Qt ausente continuam sendo skips. Para
testes completos num ambiente Qt apropriado use `--test full`; isso não
transforma um ambiente nativo diferente na imagem canônica. Veja
`ci/qml-visual/README.md` para execução em container, se o host já tiver esse
recurso autorizado. O bootstrap não instala/configura Docker ou grupos.

## Estado preservado e alcance das provas

| Camada | Checkpoint |
|---|---|
| Linha de continuidade | `codex/product-recovery-2026-10-16`; base de assunção `744d300bf1672275ce15c08cf2fe44d31d067ab1` |
| Main anterior ao handoff | `ad742ca3515f794fe285d42060708835cb09fb91`, PR [267](https://github.com/Misael-art/steam-zero/pull/267), oito jobs verdes no run [40088910465](https://github.com/Misael-art/steam-zero/actions/runs/40088910465) |
| Host antigo instalado | `2.0.0rc1-59ecc2d8f0f6`, fonte `59ecc2d8f0f66e27ce9aefa1dd7656451a610997`; CLI/daemon convergentes, schema 23 e idempotência verificados |
| Rollback antigo | `2.0.0rc1-3f87657c0a6c`, não ativado; não existe implicitamente no host novo |
| R2 posterior à instalação | Correção de alias `year` não sobrescrever `releaseDate`, integrada no PR 267; não instalada |
| R3 neste lote | Prontidão autenticada e preparação explícita nos detalhes do Launcher, estado indeterminado real, erro/retry, sem spawn; fixtures HTTP/QML, sem prova instalada |
| Bootstrap neste lote | Planos e testes de preservação/hash; criação e reexecução de ambiente descartável com dependências reais, sem pacotes de sistema; não equivale a ensaio de SO vazio |

O host antigo apresentou doctor degradado: nove backups e nove journals órfãos
preservados, input Deck sem prova e inspeção do boot direto sem permissão. A
evidência anterior de R0/R1 cobre interface, NES/Amiga e reabertura com perfil
sem daemon; não prova gameplay, controle, toque, Deck ou a jornada completa.
Veja `docs/09-operations/evidence/2026-10-23-r2-launcher-data/` para recibos.

A integral R3 iniciada às 11:05:54 UTC perdeu sessão, log e cobertura em `/tmp`;
seu resultado é **desconhecido, não aprovado**. As focadas anteriores 64+14 e as
posteriores 16+29 estão preservadas com seus alcances. Os resultados finais
deste handoff ficam em `docs/09-operations/evidence/2026-10-24-new-host-handoff/`;
essa evidência e o PR prevalecem sobre anotações antigas de processo ativo.

## Dados privados: recuperar exige cópia externa

Foi criado um arquivo local privado de **3.351.864.629 bytes**, 19.613 arquivos
e 15 snapshots SQLite pela API de backup (inclui WAL commitado), com SHA-256:

```text
270b21f2b95a36066d988ca1f9810c2c35814ca5b09429f14ae7adb53d98e374
```

Origem no host antigo:
`build/agent-runs/host-handoff-2026-10-24/private-backup/`.
Inclui dados, estado, configuração do SteamZero e o pacote de continuidade de
21/10. Inclui manifesto privado por arquivo, permissões restritas e um resumo
público sem caminhos de jogos. A restauração foi executada em staging novo,
separado dos dados reais; o recibo fica na evidência do handoff.

**Cópia externa ainda não comprovada.** As ferramentas desta sessão não oferecem
upload confirmado para armazenamento persistente do Codex. Dropbox/Drive foram
sugeridos, mas nenhuma conexão/upload foi comprovada. Links para arquivos locais
no Codex não salvam o disco. Antes de abandonar o host, copie **o diretório
private-backup inteiro** para armazenamento privado externo, baixe novamente e
execute `verify`/`restore`; registre destino e hash lido de volta. Nunca coloque
esse arquivo, manifesto privado ou credenciais no GitHub público.

ROMs do acervo, BIOS e saves externos aos diretórios do SteamZero **não estão
nesse arquivo**. `~/emulation/bios` tinha aproximadamente 681 MiB e o acervo
histórico era de aproximadamente 341 GB. Não foram encontrados diretórios de
saves conhecidos em `~/emulation/frontend`; isso não prova ausência de saves em
outros emuladores. Inventarie/copiei esses dados separadamente para destino
privado se precisar deles. Cache, `.venv`, `/opt`, chaves SSH/GPG e login Codex
não são migrados. O desenvolvimento do código pode continuar sem esses dados;
a biblioteca pessoal não será recuperada apenas pelo Git.

Depois de obter a cópia no host novo, sem restaurar sobre dados existentes:

```sh
rtk proxy .venv/bin/python tools/export_host_handoff.py verify --directory /caminho/privado/private-backup
rtk proxy .venv/bin/python tools/export_host_handoff.py restore \
  --directory /caminho/privado/private-backup --destination /caminho/novo/staging
```

O staging contém `data/`, `state/`, `config/` e `continuity/`. Inspecione antes de
qualquer adoção: caminhos absolutos do acervo antigo precisam de mapeamento
controlado, preservando IDs, preferências e mídia. Não faça substituição global
de caminhos, downgrade do schema 23 ou cópia cega sobre o perfil novo.

## Próxima entrega concreta

**Seguimento de cobertura do retorno — 30/10/2026:** teste
`0749d8e80ad8c97e422e81883181f735ca1fdd2b`. A fonte de produção continua idêntica ao checkpointf3139596,
árvore src c987db69ad965f9ef344e47500337b4709d0d9e9; produto Launcher integrado em `f6738ec4`.
CI40997943230 teve oito jobs aprovados, mas o comparador adicional coreCI caiu
85,485453%<85,486462% da baseac41c04c. Artefato original preservado; não reexecutar
para tentar obter um número favorável nem usar a base menor.

Testes agora usam volumes SATA/NVMe/MMC sintéticos e mantêm provider até fim
observado do handler HTTP. Um heartbeat real antecede desconexão na escrita;
relógio da fixture só virtualiza a espera, sem alterar produção ou prazos5s.
76 focados/37,34s;9casos5x/45 aprovações;4 casos novos. Integral do seguimento7.073 passed/48 skipped/0 failed/19 warnings/2.762,51s; runner/observador0, signals vazio,2.774,28s monotônicos. Cobertura integral85,658854% >=85,650326% da integral anterior, delta+0,008528pp.
Arcos críticos presentes,9 hashes, estado pessoal preservado, Ruff736/mypy307/
independence/boundaries/status verdes. Sem promoção de eixos ou aceite físico.

Fechar documentação e publicar checkpoint do seguimento/PR268; conferir remoto,
novo CI terminal e artefato coreCI contra a mesma base aprovada, com arcos críticos.
O resultado remoto será registrado no PR, sem commit circular. Sem instalação/
auth/release/merge/deploy/boot; host somente readlink59ecc2d8f0f6, runtime/rollback
não revalidados. Causas do SIGTERM anterior e episódio Saves seguem abertas.

Próximo baseline seguro: seção de origem inteira removida ou catálogo vazio antes da reabertura após closed com GET perdido. A projeção HTTP já cobre esses destinos; falta percorrer o Qt com resposta ausente e comprovar foco utilizável. Na Home vazia, Enter deve acionar a recarga existente library.add/library.retry pelo _retry, mantendo zero launches/recoveries automáticos e a referência canônica exata. Registrar comportamento antes de presumir defeito; reutilizar mapa/domínio e canais existentes, sem novo catálogo ou writer. Após carregar .steamzero-dev/env.sh: rtk proxy env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_app.py tests/integration/test_launcher_owner_loss_qml.py tests/integration/test_launcher_focus_bootstrap.py -q. Manter claims e integração compartilhada por último; não editar domínio reservado sem handoff prospectivo. V1, Steam sem recibo, provas/contextos ausentes, outro boot/namespace e instalação/hardware continuam independentes; GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME aberto. Sem instalação/auth/release/merge/deploy/boot.

Blocos seguintes são históricos.

**Fechamento do retorno com jogo removido — 30/10/2026:** produto
`edcfc20256d574e068406c8ac8a15d729327e559` e integração compartilhada final
`f6738ec498ab0ccfbf6c5bccc6b4220695d8a5b2`. O modelo reutiliza restore_context para publicar
returnFocus/returnDiagnostics, sem alterar returnContext/launchRecovery, arquivo
owned ou linha canônica. Duas respostas closed perdidas e remoção do jogo antes
de reabrir retornam ao vizinho da seção de origem; gestos iniciam uma única
sessão nova desse jogo e seu término retorna ao cartão. Nenhuma adoção de latest,
outro catálogo/supervisor/schema ou edição do domínio reservado.

Baseline1falha/6,88s;93 focados +9 shell,10 novos. Integral7.069 passed/48 skipped/0 failed/19 warnings em3.096,25s. Runner e observador0, signals vazio; observador3.106,75s. Cobertura integral85,650326% >=integral85,647076% da baseac41c04c, delta+0,003251 ponto percentual.
Ruff736/mypy307/independence/boundaries/status verdes; sete hashes e estado
pessoal preservados. Primeira integral interrompida143/Qt-15 não conta como
aprovação; ES-DE original1passed/34,38s e retomada integral0, sem fonte/teste/
timeout alterados. A causa do sinal continua não confirmada. Seis PNGs fonte
Qt/offscreen no CHECKPOINT R3; sem prova instalada/hardware ou promoção de eixos.

Próximo baseline seguro: seção de origem inteira removida ou catálogo vazio antes da reabertura após closed com GET perdido. A projeção HTTP já cobre esses destinos; falta percorrer o Qt com resposta ausente e comprovar foco utilizável. Na Home vazia, Enter deve acionar a recarga existente library.add/library.retry pelo _retry, mantendo zero launches/recoveries automáticos e a referência canônica exata. Registrar comportamento antes de presumir defeito; reutilizar mapa/domínio e canais existentes, sem novo catálogo ou writer. Após carregar .steamzero-dev/env.sh: rtk proxy env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_app.py tests/integration/test_launcher_owner_loss_qml.py tests/integration/test_launcher_focus_bootstrap.py -q. Manter claims e integração compartilhada por último; não editar domínio reservado sem handoff prospectivo. V1, Steam sem recibo, provas/contextos ausentes, outro boot/namespace e instalação/hardware continuam independentes; GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME aberto. Sem instalação/auth/release/merge/deploy/boot.

Fechar documentação e publicar um checkpoint/PR268, conferir remoto/CI terminal
no PR. Baseac41c04c teve CI40981206167 com oito jobs aprovados na primeira
tentativa, core85,486462%; comparar CI↔CI separado da integral local. Host só
readlink59ecc2d8f0f6, runtime/rollback não revalidados. Sem instalação/auth/release/
merge/deploy/boot. Blocos seguintes são históricos.

**Fechamento de sucesso closed após GET perdido e reinício — 29/10/2026:**
`a9a2e8edbf85b912a8a346bd2ca19949cfbe52e1`. O GET terminal conserva a referência v2 owned/recibo
confirmado até o próximo launch explícito validado. Duas bridges perdem as
respostas; a terceira restaura o mesmo cartão sem erro ou launch automático.
O owner de fixture permanece até o término natural. Não converte sucesso em
ORPHANED nem fabrica saída/tempo; registro canônico e contextos alheios intactos.
Migração explícita das assertivas de consumo v2; v1 one-shot independente.

Baseline1falha/1,50s;122 focados,17 novos. Integral7.059 passed/48 skipped/0 failed/19 warnings/2.490,81s; núcleo6.652 passed/48 skipped/407 deselected/19 warnings/746,04s. Runner e observador0, signals vazio. Core85,519153% >=CIverde85,478942% (base24b3dcb9/run40966373727/artifact12939315169) e >=core local85,514477%; integral85,647076% separada.
Ruff736/mypy307/independence/boundaries/status verdes, sete hashes e estado
pessoal preservados. Seis PNGs fonte Qt/offscreen no CHECKPOINT R3; sem prova
instalada/hardware ou promoção de eixos. Host só readlink59ecc2d8f0f6;
runtime/rollback não revalidados. Fonte/testes/commits/push/PR268 autorizados;
sem instalação/auth/release/merge/deploy/boot.

Próximo baseline seguro: catálogo alterado/jogo removido antes da reabertura após closed com GET perdido. Observar prova canônica exata, retorno a foco válido e zero launches automáticos; preferir vizinho da mesma seção conforme o contrato existente. Registrar primeiro o comportamento, sem presumir novo defeito, adotar a sessão latest ou criar outro catálogo. Após carregar .steamzero-dev/env.sh: env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_restart.py tests/integration/test_launcher_return_cycle.py tests/unit/test_launcher_session.py -q. Reservar prospectivamente qualquer path adicional antes de editar. V1, Steam sem recibo, provas/contextos ausentes, outro boot/namespace e prova física seguem independentes; GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME aberto. Sem instalação/auth/release/merge/deploy/boot.

Publicar um checkpoint e conferir SHA remoto/CI terminal no PR268. A base24b3dcb9
teve CI40966373727 aprovado após única reexecução visual; primeira falha Saves
não reproduzida e causa não confirmada. Não tratar como corrigida, nem repetir
cegamente se recorrer. Blocos seguintes são históricos.

**Fechamento de GET terminal perdido e retomada do erro órfão — 29/10/2026:**
`997c3cd9391ae88960c7ba5797413140fc5acbe8`. A bridge retém contexto v2 owned e recibo exato
após failed/E-SESSION-ORPHANED, mesmo se o GET terminal se perder e houver novo
reinício. Leitura do contexto não consome/repara arquivos. O retry revalida
estado e identidade e só então consome o registro próprio; preserva contexto
alheio/substituído/ilegível, não fabrica notStarted nem dispara launch automático.
Mantém ausência de arquivo compatível com um novo pedido explicitamente validado.
Sucesso closed e outros erros não ganham esse aceite por inferência.

Prova:baseline1falha/1,04s;84 focados,18 novos. Qt/HTTP com duas perdas de GET,
terceira bridge restaura erro/foco, um retry por Enter e retorno. Integral7.042
passed/48 skipped/0 failed em2.297,92s; núcleo6.636/48/406 em613,21s. Core85,514477%
>=CIverde85,477196% (base490b4722,run40952684734,Python3.14). Ruff736/mypy307,
independence/boundaries/status verdes;5 hashes e estado pessoal preservados.
Cinco PNGs de fixture Qt/offscreen persistidos no CHECKPOINT R3; sem prova instalada
ou hardware. Nenhuma promoção dos cinco eixos; WORKLOG só recebe fechamento.

Próximo baseline seguro: término normal closed com GET terminal perdido e novo reinício, observando foco/contexto e zero lançamentos automáticos. Manter o owner de fixture até o término canônico; não converter sucesso em erro órfão nem fabricar exit/tempo. Reutilizar contexto, recibos e serviço existentes. Após carregar .steamzero-dev/env.sh: env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_restart.py tests/integration/test_launcher_return_cycle.py tests/integration/test_emulation_session_lifetime.py -q. V1, provas/contextos ausentes, Steam sem recibo, outro boot/namespace e prova instalada/física permanecem independentes; GAP lifetime aberto. Sem instalação/auth/release/merge/deploy/boot.

Fechar documentação e publicar uma vez a continuidade/PR268; conferir remoto e
CI novo em estado terminal. O resultado remoto será registrado no PR. Host só
readlink59ecc2d8f0f6; runtime/rollback não revalidados. Blocos seguintes históricos.

**Fechamento da recuperação após perda do owner — 29/10/2026:** produto
`116815d118dc6f26dcf7d2f0960ba9761eaae8ae`; integração compartilhada por último
`7c63f4f079af0106e3d3fcb74e298a170637832d`. Depois de running confirmado, perda do owner
preserva jogo/descendentes. A sondagem exige identidades tipadas do mesmo
boot/namespace e grupo/sessão vazios; prova insuficiente permanece unknown.
Verificar sessão é explícito e usa o controlador/CLI/RPC existentes, guardando
identidade na transação. Marca failed/E-SESSION-ORPHANED sem inventar exit/tempo;
GET não reconcilia lifecycle. POST perdido é recuperado pelo GET canônico;
outro Enter cria uma única sessão nova e retorna ao mesmo cartão.

Prova:53 novos,116 focados/handheld; integral7.024 passed/48 skipped/0 failed
em2.247,58s, núcleo6.619/48/405 em617,84s. Core85,509905% >=85,431457% do
CIverde40906842436/base969933a1. Ruff736/mypy307/independence/boundaries/status
verdes,17 hashes/estado pessoal preservados. Um harness antigo indexava o retry
por posição; reprodução1falha, busca por nome mantendo assertivas e integral
final aprovadas. A passagem interrompida e a regressão parcial não são aprovação.
Cinco PNGs de fixture Qt/offscreen persistidos no CHECKPOINT R3, sem prova física.
Claim antigo do harness cedido à R3 após conflito de status, sem concorrência;
sequência registrada nos workstreams. Nenhuma promoção dos cinco eixos.

Próximo baseline seguro: recuperação canônica concluída, GET terminal perdido e outro reinício do Launcher. Observar mensagem/foco/contexto e zero lançamentos automáticos antes de alterar contrato; não inferir notStarted para jogo que já executou. Reutilizar contexto e serviço canônicos, sem outro supervisor/banco. Após carregar .steamzero-dev/env.sh: env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_owner_loss.py tests/integration/test_launcher_owner_loss_qml.py tests/integration/test_launcher_restart.py -q. Registros sem prova tipada, outro boot/namespace, perda antes de running persistido, V1, Steam sem recibo e prova física continuam independentes; GAP lifetime aberto. Sem instalação/auth/release/merge/deploy/boot.

Publicar o fechamento documental na continuidade/PR268, conferir SHA remoto e
CI novo em estado terminal. Host apenas readlink59ecc2d8f0f6; runtime/rollback
não revalidados. Os blocos seguintes são procedência histórica.

**Fechamento da recusa recuperável — 29/10/2026:** produto em
`e30bd4f98468e2077b077e97fdb9809deaab6dc5`; fixture CI em
`aed4856afd0c69922872d635b3ab1c33359dd038`. O owner que recusa uma tentativa
pré-alocada antes do spawn persiste failed com prova tipada e código registrado,
sem detalhe privado, tabela nova ou mudança do SQLite 23. A bridge reaberta
recupera a recusa exata, mantém contexto entre GET perdido e outro reinício e
consome somente seu contexto ao receber um novo pedido explícito validado.
Falta de prova permanece não confirmada; não há POST automático ou adoção por jogo.

Prova: 59 focados sem PYTHONPATH inicial, 26 casos novos; integral 6.971 passed,
48 skipped, zero failed em 2.067,19 s; núcleo 6.567/48/404, cobertura 85,464311%
>= 85,423695% do job Python 3.14 aprovado da base c9345cf1. Esse workflow
anterior teve sete jobs verdes e falhou nos dois testes visuais cujo subprocesso
dependia do perfil local. A reprodução sem PYTHONPATH e a fixture corrigida estão
no CHECKPOINT R3. Ruff check/format731, mypy306, independence/boundaries/status
passaram. Um núcleo interrompido por SIGTERM143 sem resumo ficou desconhecido;
a repetição supervisionada e a integral concluíram com o mesmo fonte. Sem
atribuir a causa do sinal ou promover runtime/hardware.

Próximo baseline seguro: encerrar apenas o owner de uma fixture depois de
confirmar running, preservar o jogo sintético e reabrir a observação antes/depois
do seu término. Não inferir closed/notStarted pela ausência de PID, criar outro
supervisor ou tocar o desktop/perfil do operador. Ler contratos/reconciliadores
existentes. Primeiro comando, após carregar .steamzero-dev/env.sh:
`env -u PYTHONPATH .venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_restart.py tests/integration/test_launcher_refusal_restart.py tests/integration/test_emulation_session_lifetime.py -q`.
GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME, Steam sem recibo e instalação/prova física
seguem independentes e abertos. Sem instalação/auth/release/merge/deploy/boot.
Conferir CI do novo checkpoint publicado. Os blocos abaixo são procedência.

**Fechamento da retomada entre processos — 29/10/2026:** implementação em
`b9f190f7026bc0e064096f25adc6a3ac5e74558f`. Novos lançamentos de emulação
publicam contexto v2 owned com ULID pré-alocado, passado à CLI e ao lifecycle
existente. A bridge reaberta consulta somente a sessão exata por ID/jogo/owner,
com guarda de PID/start_ticks, preserva o foco e não faz outro lançamento.
Ausência/divergência continua não confirmada. V1 mantém consumo único; banco
permanece no schema 23. O término canônico consome somente o contexto próprio.

Prova fonte: 33 focados de retomada/lifetime, dois Qt/HTTP com processos distintos
e dois reinícios. Integral: 6.945 passed/48 skipped/0 failed em 2.197,55 s;
núcleo: 6.542/48/403 e cobertura 85,466579% >= CI verde 85,412847% da base
b55890b0, run 40845684020. Ruff check/format (730), mypy (306), independence,
boundaries e status-check passaram. Uma integral terminou com SIGTERM 143 sem
resumo e permanece desconhecida; a repetição supervisionada concluiu com saída
0 e mesmo fonte. Não se afirma a causa do sinal. Evidência no CHECKPOINT R3.

Próximo baseline seguro: recusa pré-spawn com resposta perdida após encerrar o
Launcher originador, sem linha canônica. Preservar a incerteza; não fabricar
notStarted ou permitir retry pela mera ausência de registro. Reutilizar fontes
existentes; não criar outro supervisor/banco. Primeiro comando, após carregar
.steamzero-dev/env.sh:
`.venv/bin/python tools/run_tests_isolated.py tests/integration/test_launcher_restart.py tests/integration/test_emulation_session_lifetime.py -q`.
GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME segue aberto nesses limites, para Steam
sem recibo e provas instaladas/físicas. Sem instalação, autenticação, merge,
release, deploy ou boot. Conferir CI do novo checkpoint publicado. Os blocos
seguintes preservam a procedência dos lotes anteriores.

**Atualização de 28/10/2026:** o gap abaixo foi reproduzido e corrigido em fonte
na continuação do PR #268, commits `d41923f4` e `eb39b4b6`. O loader descartava o archive recuperável; não foi
observada troca de ID. A projeção agora exige manifesto com hashes por entrada e
resolve um alvo base único no preflight compartilhado. Scan, preparo, rescan,
reabertura, erro e recuperação usam fixtures isoladas; LauncherMain também foi
exercitado em Qt/offscreen com o materializador real. Resultados e limites em
[CHECKPOINT R3](../../09-operations/evidence/2026-10-24-r3-launch-readiness/CHECKPOINT.md).
Prontidão/progresso do cartão foram entregues em fonte em `d9d8f42b`/`d93bae2e`;
consulta da bridge em `b4b7196d`, com retry preservando shell/contexto.

**Atualização de 29/10/2026:** ACK perdido com a bridge viva entregue em
`36e01f70`. A identidade criada antes do POST se vincula ao recibo do servidor;
leitura posterior recupera running/notStarted sem repetir POST automaticamente.
Apenas o último pedido aceito é retido nesta execução. Foco de erro/retry e
retorno foram verificados com Enter real. 145 integrações Launcher; integral
6.912 passed/48 skipped/0 failed em 2.857,35 s; núcleo 6.511/48/401 e cobertura
85,447227% >= CI verde 85,398687%. Gates estáticos/status aprovados. Uma integral
interrompida por SIGTERM ficou desconhecida; somente a passagem concluída conta.

CI da base `4c829a87`: oito jobs verdes no run 40831063419. Conferir o CI do
novo SHA publicado. Fonte Qt/offscreen com dados controlados; sem instalação.
Próximo lote seguro: reproduzir continuidade após recriar a bridge de fixture.
LaunchPlan.context_payload guarda só jogo/foco; não há clientRequestId persistido.
Usar contexto e estado canônico existentes antes de escolher migração; não adotar
sessão por nome/PID/gameId. GAP-AURA-LAUNCHER-SESSION-ACK-LIFETIME, Steam sem
recibo e provas instaladas/físicas permanecem abertos. O roteiro abaixo
permanece como diagnóstico histórico.


Feche primeiro o PR/checkpoint deste handoff conforme os recibos atuais. Depois
retome R3 com reprodução de `GAP-LAUNCH-PREPARE-GAME-ID-AFTER-RESCAN` em um archive
temporário. A leitura do código sugere que o problema pode estar na projeção do
alvo de execução, e não numa troca de ID: `EmulationController.prepare_game`
materializa e revarre, mas `_launch_preflight` ainda recusa a origem compactada;
`ArchiveMaterializer.inspect` pode continuar retornando `needs-extraction` mesmo
com marker. Isso é hipótese de diagnóstico, não reprodução concluída.

Pontos de entrada: `src/steamzero/controllers/emulation.py` (`prepare_game`,
`_launch_preflight`, `current_game`),
`src/steamzero/adapters/multidisc_materializer.py` (`inspect`, `prepare`) e
`tests/unit/test_multidisc_materializer.py`. Confira os paths no fonte atual.
Preserve o ID canônico do archive e seus metadados; resolva somente o alvo
efetivo no preflight compartilhado, usando ownership, fingerprint da origem,
manifesto e hashes das entradas. O marker atual não prova hash individual.
Recuse symlinks, divergências e seleção ambígua; multidisco exige o contrato C2,
nunca escolher arbitrariamente o primeiro arquivo. Reutilize materializador e
serviços existentes, sem novo catálogo/supervisor/jobs.

Instalação de produto em host vazio é outra pendência: o controlador conhecido
exige rollback instalado. **Não invente uma release anterior** nem copie `/opt`
para satisfazer preflight. Desenvolva no fonte isolado; trate suporte à primeira
instalação como entrega própria antes de uma ativação autorizada.

## Prompt para o novo agente

```text
Continue SteamZero no único checkout criado pelo bootstrap, na branch
codex/product-recovery-2026-10-16. Leia AGENTS.md, RTK.md e
docs/recovery/2026-10-16/RETOMADA-HOST-NOVO-2026-10-24.md; depois DIRECAO.md,
PLANO.md, catálogo de status e workstreams. Confira HEAD, PR e CI remotos.
Preserve mudanças e claims; um executor e um lote por vez, sem worktrees ou
branches por lote. Não peça senha nem inicie autenticação, sudo, release,
serviço ou boot até nova direção. Não recrie ambiente não gerenciado.
Carregue .steamzero-dev/env.sh; use rtk e o runner isolado, nunca pytest contra
dados reais. Diferencie fonte, CI, instalação, fixture e hardware. Resolva o
checkpoint de handoff que ainda estiver aberto; depois reproduza o gap da
preparação de archive indicado no documento, sem mudar a identidade do jogo.
Documente baseline, correção mínima, sucesso/erro/recuperação e leitura de volta.
No fechamento estável, gates integrais e cobertura equivalente, status coerente,
commits funcionais/documentais separados, push e PR governado, sem bypass.
Logs duráveis em build/agent-runs; WORKLOG append-only no fechamento. Backup
privado só é externo após upload e leitura de volta comprovados. Não promova
instalação ou gameplay a partir de fixtures. Prossiga no trabalho seguro elegível.
```

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

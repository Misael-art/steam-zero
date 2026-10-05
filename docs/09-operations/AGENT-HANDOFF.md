# Handoff do agente — atualização de 04/10/2026

## Continuidade vigente

Checkout único: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`.
Branch ativa: `codex/session-exit-wayland-bezel-2026-10-04`, baseada no `main`
`5e94e50810deac5bde22645fb3e015d62426baf2`. PR #250 está integrado; não retome
nem commite em sua branch antiga. Workstream ativo:
`WS-2026-10-JOURNEY-LAUNCHER-SESSION`.

Esta continuação implementa P0-A (saída confirmada de processo suspenso, com
identidade PID/start ticks/grupo e confirmação do watcher), P0-B (homes XDG
privados mantendo o socket Wayland absoluto validado no ambiente do QML) e o
recorte de bezel personalizado: PNG-fonte pelo Theme Studio, URI versionada na
Jornada, catálogo/resolver e configuração privada para o próximo launch do
RetroArch Flatpak. O read model informa `launch-configured-unconfirmed`; não há
prova de que o RetroArch compôs os pixels. O AURA gerenciado continua fallback e
outros adapters continuam indisponíveis com motivo.

Os módulos focados mais recentes passaram: 399 testes em 141,61 s, incluindo os
harnesses QML de Jornada e overlay; três regressões de persistência/importação,
propagação do URI até o callback de launch e erro HTTP de schema passaram em
follow-up. Ruff check, ruff format --check e git diff --check dos arquivos
alterados passaram. Ainda falta o checkpoint dos seis gates integrais da árvore
congelada e a documentação final de seus resultados. O relatório e a prova
histórica preservada estão em
`docs/09-operations/evidence/2026-10-04-session-exit-wayland-bezel/README.md`.

PR/CI/merge por merge commit estão autorizados para esta branch conforme o
prompt desta tarefa; nenhuma instalação, rollback, publicação ou interação
física está autorizada por essa permissão geral. A release observada na revisão
anterior era `2.0.0rc1-5715d7962691`; revalidar somente por leitura antes de
preparar qualquer candidata. B_VISUAL exige autorização específica, token novo,
janela/captura/input seguros e a release efetivamente instalada.

Não declarar Qt no compositor real, gameplay, bezel visualmente aplicado, input
físico ou capacidades `installed/certified` com base nos testes de checkout.
Manter abertos os gaps de exit físico durante pausa, janela Wayland Qt física,
aplicação visual do bezel e GAP-AURA-LAUNCHER-EXIT-PHYSICAL.

Próximo checkpoint: terminar os documentos/status e seus digests; executar uma
vez os gates integrais exigidos; promover o log capturado fora de `scopePaths`;
separar commits funcionais, documentais e de integração compartilhada; fazer um
push, abrir PR e aguardar CI terminal verde no SHA exato antes do merge
autorizado. Nenhuma autorização antiga de release ou B_VISUAL se transfere.

## Registro de 01/10/2026 (histórico)

## Onde continuar

Checkout único: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`.
Antes desta revisão, a conferência local encontrou main em
`5715d7962691efedef0f1b63e71adff1ad5ba801`, árvore limpa, um worktree e nenhum
processo de suíte integral identificado. A revisão documental está na branch
`codex/visual-diagnostic-roadmap-2026-10-01`; preserve suas alterações pendentes.
Reconfira `git status`, base e claims antes de editar. Não criar diretório paralelo.

A fila de execução está somente no
[roadmap](../12-roadmap/IMPLEMENTATION-ROADMAP.md), prioridade V1–V4.
O [prompt raiz](../../IMPLEMENTATION-PROMPT.md) é a instrução de continuidade
para A_CODIGO. O catálogo continua sendo a fonte do estágio, embora alguns
nextAction antigos precisem ser reconciliados com as evidências atuais.

## Base já integrada e instalada

A cadeia #239–#248 foi integrada no main acima conforme os logs do fechamento
canônico em `evidence/2026-09-30-rc01-fileira-integracao`. Não continua aguardando
merge como dizia o handoff anterior.

A instalação governada da release `2.0.0rc1-5715d7962691` está registrada nos
logs 131/132 do acervo durável. B_VISUAL 133/134 exercitou essa release.
Rollback relatado: `2.0.0rc1-e2af2562ebba`; este handoff não o executou nem
reverificou. Autorizações antigas não autorizam a próxima instalação.

Acervo físico:
`/home/misael/steamzero-evidencia-integracao-2026-09-30/integracao-2026-09-30/`

Leia `134-b_visual-rc01-fisico-2/` (README, MATRIZ, ACHADOS, RC01,
TAREFAS-A-CODIGO e adendos), comparando com `133-b_visual-rc01-fisico/`.
Importação ES-DE/RetroFE, prontidão e unidades foram exercitadas com ressalvas;
modais/componentes com contraste insuficiente e conflito de ID com mensagem
errada estão documentados. Teclado/gamepad, round-trip do Studio e Launcher
continuam sem prova física completa. Limitação de AT-SPI/input não prova defeito
do produto; abertura incompleta do seletor permanece inconclusiva.

Foram criados por importação autorizada um tema “Diagnostico BV134 ESDE” e uma
cena “bv134-cena-01”, sem ativação automática. Preserve os itens; remoção não faz
parte da continuidade. Preferências e acervo original não foram alterados pelo
relato. Não publique capturas privadas sem revisão de privacidade/licença.

## Próxima entrega

V1: corrigir apresentação/interação por componentes e contratos compartilhados.
Prosseguir V2/V3 até tema importado/produzido pelo Studio renderizar no runtime,
com autoria, undo/redo, persistência e round-trip demonstráveis. Leia AURA-SURFACES
e THEME-ENGINE-AND-STUDIO antes da implementação. O roadmap define aceite e
limites; este handoff não mantém backlog separado.

A_CODIGO produz entrega e testes; B_VISUAL revisa jornada identificada por
release/artefato. Um dono de código, passes seriais, checkout único. As provas
históricas e a integral histórica não verde permanecem preservadas. Nenhuma
capacidade recebeu promoção por esta revisão documental.

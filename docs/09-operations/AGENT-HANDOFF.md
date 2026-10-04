# Handoff do agente — atualização de 04/10/2026

## Continuidade vigente

Checkout único: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`.
Branch de trabalho: `codex/journey-launcher-session-2026-10-04`, baseada no
`main` `b12e5f799498b92995a581c941735a21f27ef546`. A árvore está em andamento e
contém a implementação da Jornada no Launcher/Cinema, contratos de sessão,
provas focadas e atualização documental; preserve-a e não troque de branch.

Workstream ativo: `WS-2026-10-JOURNEY-LAUNCHER-SESSION`. A prova de integração
mais recente passou com 207 testes focados; a prova inclui a cópia ativa da
Jornada, facetas tipadas, retorno, ação de sessão e cena XML compilada no
Cinema/`SceneEsdeView`. O contrato de bezel publica o slot e o perfil RetroArch
aplica apenas o AURA gerenciado; bezel personalizado ainda não é executável.
Após tornar repetição da saída idempotente enquanto `closing`, os 16 testes de
controle/adapter de sessão também passaram.
Consulte `docs/09-operations/evidence/2026-10-04-journey-launcher-session`
quando os resultados integrais e o SHA candidato forem registrados.

Próximo checkpoint: estabilizar implementação e documentos, executar uma vez os
seis gates integrais de `AGENTS.md`, promover os logs necessários, separar
commits funcionais/documentais e o commit de integração compartilhada, fazer
push/PR e aguardar CI terminal verde no SHA final. A autorização da tarefa cobre
essas operações no branch próprio e o merge autorizado. Não instalar, publicar,
reverter ou capturar a release no host nesta etapa: isso exige autorização e
token próprios. B_VISUAL ainda precisa de janela/captura/input seguros e do ciclo
na candidata instalada.

O perfil RetroArch Flatpak é o único ciclo de sessão apoiado por esta fatia.
Pause/resume, save-state, disco e saída são publicados pelo adapter; saída pede
confirmação e espera `closed` real. Outros perfis deixam a capability ausente
com razão legível. Nenhuma fixture sintética promove operação ou consumo físico.

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

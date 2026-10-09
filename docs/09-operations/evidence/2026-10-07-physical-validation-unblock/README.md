# Desbloqueio da validação física e das jornadas reais

## Origem e limite

Síntese das rodadas R01–R17 reportadas em 06–07/10/2026 no acervo privado `139-correcao-jornadas-reais-213124ed513b`. Foram lidos a matriz CSV e o parecer `cases/2026-10-07-launch-cinema-theme-events.md`. Esta revisão não executou input, captura, download, jogo, instalação ou benchmark; resultados físicos abaixo são os registrados pelo executor anterior.

A leitura local desta revisão confirmou HEAD e o ref local origin/main em `213124ed513b404c78bb0a83c0e2514648a429d4`, branch `codex/r05-component-operation-trace-2026-10-05` com trabalho não commitado e `/opt/steamzero/current` apontando à release `2.0.0rc1-213124ed513b`. Não foi feito fetch nem consulta remota; ref local não confirma o tip atual no servidor.

## Resultado disponível

- Rotas semânticas foram acionadas por AT-SPI; falta evidência de pixels e input direto.
- Engine CLI resolveu seis temas compatíveis; cinco apply/readback/rollback e importação de amostra em perfil temporário foram registrados. Quatro entradas legadas foram recusadas. Não houve certificação do Studio, renderer, Launcher ou Cinema.
- Catálogo foi reportado com 64 plataformas/1.145 jogos; somente Switch tinha 15 ações publicadas. Nenhum jogo foi iniciado, nem pause/save/exit/return testados.
- Providers produziram candidatos; não houve download novo. ScreenScraper reportou credencial rejeitada. Contas e receptores não foram autenticados para sync/casting.
- R05/R06 estão implementados localmente, não commitados e não contidos na release ativa. O checkpoint reportado de 6.676/47/1 continua reprovado; governança precisa de reconciliação dos digests.

## Correções de enquadramento do diagnóstico

1. O `pyproject.toml` do SHA de referência declara `steamzero-launcher = steamzero.launcher.app:main`. Não encontrar um grupo na CLI central não demonstra ausência do entry point separado. Conferir pacote publicado, executable e runtime antes de implementar uma entrada ou declarar Cinema inexistente.
2. Ausência de `showing` e bounds no AT-SPI não demonstra ausência de pixels. Exposição acessível, desenho e ação efetiva são critérios distintos.
3. Falha de resize por extensão GNOME na sessão KDE/KWin requer diagnóstico da ferramenta/backend. Não autoriza configurar um desktop diferente ou contornar portais.
4. Outras janelas abertas não bloqueiam automaticamente funcionalidade. Elas requerem foco verificável e privacidade; concorrência limita atribuição de desempenho.
5. Um jogo próprio pode servir como input real sem marcação demo. Antes de executar, confirmar input permitido e destinos de writes; teclado pode ser válido quando suportado, sem alegar gamepad certificado.
6. Cálculos de tokens não são contraste dos pixels. Não aplicar uma regra de texto ativo automaticamente a disabled; conferir a política normativa e o uso operacional do texto.
7. Entrada legada inválida deve ser classificada/migrada ou segregada no catálogo com razão; não apagar pacote pessoal.
8. Atualizar scopeDigest registra integridade de escopo. É necessário atribuir o delta e distinguir revalidação do escopo de reteste dos aceites; nenhum eixo físico sobe pelo recálculo.

## Encaminhamento

O [roadmap](../../../12-roadmap/IMPLEMENTATION-ROADMAP.md) contém D0–D8, vinculados a RC-00–08 e aos R01–R17 existentes. Ordem operacional: preservar/conciliar lote atual, restabelecer ferramentas, auditar entry points, tornar catálogo/input/saves aptos a sessão, comprovar mídia/gameplay e autoria/render; consolidar candidato e retestes físicos com autorização específica.

Esta evidência é documental e tem resultado `recorded`. Não é uma nova aprovação dos testes históricos nem dos produtos. O item de governança associado é parcial, em feature branch, sem verificação operacional. Os itens de capacidade mantêm seus eixos e ownership.

## Validação documental e integração pendente

O catálogo e os novos registros passaram pelo loader/schema do project_status.py. As views foram regeneradas pela ferramenta; links críticos e D0–D8 foram conferidos. Os 17 arquivos previamente pendentes mantiveram seus hashes antes da regeneração das três views; código, testes e itens R05/R06 não foram editados por esta revisão.

A comparação por conteúdo, sem reescrever o checkout, atribuiu **10 digests já obsoletos antes da revisão** e **5 novos pela inclusão documental**: SZ-AURA-LAUNCHER, SZ-MAIN-WORKTREE-RECONCILIATION, SZ-PLATFORM-PS5-CATALOG, SZ-ROADMAP-CONTINUATION e SZ-THEME-STUDIO. O gate global permanece reprovado em 15 itens. Os cinco itens incluem roadmap/escopos documentais compartilhados; nenhum foi recertificado ou alterado para ocultar o envelhecimento. D0 deve integrar esta revisão e renovar o escopo documental com o owner, preservando eixos e evidências funcionais; os dez anteriores exigem atribuição própria de delta. O mapa detalhado está no acervo privado `140-roadmap-desbloqueio-2026-10-07/atribuicao-digests.json`.

Não houve commit, troca de branch, push, merge ou instalação. Os arquivos desta revisão são uma entrega documental local, a integrar serialmente sem incluir alterações funcionais alheias. A suíte integral não foi executada para esta mudança documental; seu resultado histórico continua o reportado pelo executor.

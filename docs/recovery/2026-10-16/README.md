# Recuperação da proposta SteamZero

> **Continuidade vigente em 2026-10-24:** ambiente existente; seguir o [checkpoint R2 e fila única](../../09-operations/evidence/2026-10-23-r2-launcher-data/CHECKPOINT.md). Trabalho serial atual: [R3, recuperação D-08](../../09-operations/evidence/2026-10-23-r3-refresh-recovery/CHECKPOINT.md), com integral isolada aprovada; R2 já integrado pelo PR #265 com CI verde. Durante a ausência do operador, desenvolvimento e testes independentes continuam, sem iniciar autenticação de instalação. O guia abaixo é para eventual reinstalação futura.

> **2026-10-21 — host será reformatado.** Retomada a partir do GitHub: leia primeiro [`REINSTALACAO-HOST-2026-10-21.md`](REINSTALACAO-HOST-2026-10-21.md).

Direção estabelecida pelo proprietário em 16 de outubro de 2026. O SteamZero deve oferecer experiências de jogo prontas para computadores, emulação e plataformas web, com configuração avançada acessível e uma experiência de sala/handheld completa.

**Conclusão:** há uma base técnica substancial que merece ser preservada, mas a integração das jornadas e a definição de produto estão fragmentadas. A recuperação deve fechar jornadas completas sobre essa base. Aura passa a designar o tema demonstrativo do Launcher; Central Desktop, Launcher e Theme Engine têm responsabilidades e critérios de aceite próprios.

## Ordem de leitura

1. [Direção de produto e arquitetura](DIRECAO.md): vocabulário normativo, responsabilidades, compatibilidade e experiências.
2. [Diagnóstico e reconstrução histórica](DIAGNOSTICO.md): evidência do código, histórico, status e limites da avaliação.
3. [Plano de execução](PLANO.md): ordem, dependências, arquivos de partida e critérios verificáveis.
4. [Instrução para o próximo agente](PROXIMO-AGENTE.md): tarefa inicial concreta e regras para continuidade.
5. [Baseline estruturado](baseline.json): fotografia dos 97 itens preexistentes e dos 64 manifestos de plataforma, vinculada ao commit de origem.
6. [Validação desta entrega](VALIDACAO.md): verificações executadas e seus limites.

## Precedência e preservação

A orientação do proprietário nesta sessão corrige a nomenclatura anterior. `AGENTS.md` remete a esta direção antes dos documentos antigos. Em conflito de significado ou prioridade, prevalece [DIRECAO.md](DIRECAO.md); contratos técnicos existentes, segurança, preservação de dados e governança de release continuam aplicáveis.

Os arquivos `AURA-SURFACES.md`, `THEME-ENGINE-AND-STUDIO.md`, o framework de julho e roadmaps anteriores permanecem como referências técnicas e históricas. Suas definições incompatíveis estão explicitamente superadas na direção. A migração integral da redação é uma tarefa enumerada no plano, respeitando os workstreams que ainda reivindicam esses arquivos.

`docs/status/items/` continua sendo a fonte de estado atual. Este pacote define direção e registra um diagnóstico datado; não é um segundo painel de status. Sua conclusão documental não promove nenhuma capacidade funcional.

## Resultado esperado

O usuário prepara um jogo na Central, obtém seus dados e mídias, escolhe uma experiência compatível, abre o Launcher com o tema desejado, joga e retorna ao mesmo contexto. Usuários avançados ajustam emulador, jogo e dispositivo com herança explícita. A personalização visual acontece no motor; a operação de jogos acontece nos serviços compartilhados.

## Ampliação com capacidades e experiências

A segunda orientação do proprietário, na mesma data, acrescenta recursos componíveis e jornadas por plataforma. Leia:

- [Capacidades componíveis](CAPACIDADES-COMPONIVEIS.md): ações, fontes e instâncias visuais livres no Studio; saves/replay, HD packs e periféricos.
- [Compartilhamento](COMPARTILHAMENTO.md): descoberta amigável e conexão conforme o método exigido pelo receptor.
- [Multidisco](MULTIDISCO.md): automação do procedimento, unidades de disquete e escolha pelo controle.
- [Experiências por plataforma](EXPERIENCIAS-POR-PLATAFORMA.md): 64 manifestos, PC nativo e web genérica, com propostas condicionadas à prova.
- [Estado e execução](ESTADO-E-EXECUCAO.md): capacidades existentes, lacunas, lotes C0–C6 e ligação com R0–R10.

O catálogo editorial em JSON tem [schema próprio](catalogo-experiencias.schema.json). Ele não habilita recursos de runtime. Os estados existentes foram preservados no [baseline complementar](baseline-capacidades.json).

As [fontes primárias e seus limites](FONTES-EXPERIENCIAS.md) sustentam a pesquisa por runtime; possibilidades upstream não são provas de integração no SteamZero.

## Continuidade em checkout único

Use o [prompt de execução centralizada](PROMPT-EXECUCAO-CENTRALIZADA.md) para iniciar a implementação. A terceira orientação do proprietário estabelece um executor e um lote funcional por vez no diretório canônico, com instalação e prova real na máquina, pendência explícita de credencial e checkpoint de retomada. A conferência encontrou um único worktree registrado e 16 registros de frentes ativas, não 16 executores comprovados.

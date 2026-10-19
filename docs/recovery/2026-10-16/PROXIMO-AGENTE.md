# Instrução para continuidade da recuperação

Você está continuando a recuperação da proposta SteamZero definida pelo proprietário em 2026-10-16. Execute a próxima entrega concreta de `PLANO.md`, começando por R0/R1. Esta é uma tarefa de implementação com baseline e validação, não uma nova rodada de planejamento geral.

O prompt operacional vigente é [Execução centralizada](PROMPT-EXECUCAO-CENTRALIZADA.md): um único checkout, assunção serial da linha existente e instalação/prova física autorizadas para o programa. Este documento detalha o primeiro lote técnico.

## Leitura e autoridade

Leia `AGENTS.md`, `docs/recovery/2026-10-16/DIRECAO.md`, `DIAGNOSTICO.md`, `PLANO.md`, `docs/ACTIVE-WORK.md` e os itens de status envolvidos. Leia também `CAPACIDADES-COMPONIVEIS.md` e `ESTADO-E-EXECUCAO.md` no diretório de recuperação: C0–C6 ampliam este trabalho sem substituir R0/R1. A direção de 16/10 corrige a nomenclatura antiga: Central Desktop e Launcher são as superfícies; Aura é tema fullscreen; Theme Engine é runtime; Theme Studio é autoria. IDs antigos continuam compatíveis até migração explícita.

O baseline documental foi feito sobre `6475947c189f2d903b83f7f242a2c5ca535fb14c`. Não assuma que esse commit continua sendo a base atual de implementação. Confira integração, alterações locais, claims e release efetiva. A branch `codex/product-recovery-2026-10-16` contém a recuperação documental; ela não é uma release instalada.

## Objetivo do primeiro lote

Corrigir a jornada Central → plataforma → emulador → requisitos → jogo, começando pelo problema de cartões Keys/Firmware genéricos em sistemas onde não se aplicam, e mapear a configuração efetivamente suportada pelo adapter.

1. Assuma a linha existente no checkout oficial e registre item/workstream sobre a base conferida. Reconcilie os claims do lote com handoff antes de editar; não crie outro worktree ou branch por lote.
2. Reaproveite `baseline.json` e a matriz da Tarefa 15 como histórico. Faça um baseline atual isolado, incluindo duas plataformas de requisitos diferentes, selecionadas pelos manifestos.
3. Trace cada controle até a porta de serviço, efeito e leitura de volta. Inclua no inventário de C0 ação, fonte pública, argumentos, contexto, disponibilidade e modo de aplicação; a mesma função deverá poder alimentar duas instâncias visuais do tema. Comece por `Emulation.qml::overviewCards`, `emulation_workspace.py`, `platform_composer.py`, manifestos e contratos desktop.
4. Diferencie requisito inaplicável, ausente, desconhecido e válido. Não converta desconhecido em instalado e não mostre importação de firmware como ação universal.
5. Implemente a correção vertical mínima, com navegação de ida/volta e preservação da seleção. Se o ajuste exigir editar o formulário, publique apenas settings que tenham writer e readback verdadeiros.
6. Teste comportamento e falhas, não apenas strings do QML. Use fixtures isoladas e o runner do projeto. Rode gates integrais no checkpoint funcional previsto pelo `AGENTS.md`, sem repeti-los a cada edição.
7. Execute o roteiro físico com Central desktop e viewport Deck após instalação governada da candidata. A autorização do programa cobre instalação e interação de teste; viewport não comprova input de Deck real. Respeite o checkpoint main/CI, o desktop ocupado e as pendências de credencial descritos no prompt centralizado.
8. Atualize status com evidência de escopo real. Se faltar prova física, mantenha o lote aberto, registre a pendência e conclua somente trabalho independente desse lote. Comece R2 após o fechamento aplicável, no mesmo checkout.

## Critérios que não podem ser diluídos

- Não restaurar a definição de Aura como a central administrativa.
- Não reescrever o projeto inteiro nem renomear IDs persistidos em massa.
- Não trocar a engine por um launcher especial para cada tema.
- Não considerar download de capa como obtenção completa de metadados.
- Não considerar importação ou preview sintético como suporte fullscreen concluído.
- Não considerar botões/eixos como GamePad Wii U completo, dois processos como GBA link, nem cast de desktop como duas saídas independentes.
- Não criar novos temas para contornar componentes incompletos.
- Não inventar resultados de release, hardware, FPS ou credenciais.

## Entrega do lote

Relate problema reproduzido, causa, arquivos/commit, fluxo utilizável, testes, resultado físico quando houver, limitações e próxima ação R2 no mesmo conjunto de jogos. Uma pergunta opcional de preferência visual não deve interromper a correção de contratos e jornadas já autorizada.

## Restrições específicas da ampliação

Não tratar PNG de bezel como overlay interativo, broadcast próprio como descoberta universal, envio de `DISK_*` como confirmação de mídia, link GB como link GBA ou o catálogo editorial como manifestos habilitados. Diferenciar unidade e disco, save normal e save-state, vídeo e replay de inputs. Fade de cartão não apaga save. PIN/senha só são exigidos quando a rota escolhida pedir. Referências de ecossistema são candidatas, não prova de suporte no Linux/SteamZero.

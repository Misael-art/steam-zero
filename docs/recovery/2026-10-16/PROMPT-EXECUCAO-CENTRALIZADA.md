# Prompt para implementação sequencial e validação no host

Continue a implementação do SteamZero conforme a direção do proprietário de 2026-10-16. Execute o plano progressivamente, feche jornadas utilizáveis e valide cada lote funcional na própria máquina. Esta tarefa é de implementação; comece pelo próximo lote elegível, sem produzir outra rodada de planejamento geral.

## Diretório oficial e continuidade

Use exclusivamente este checkout de desenvolvimento:

```text
/home/misael/Projects/SteamZero
```

Na conferência de 2026-10-16, `git worktree list --porcelain` mostrou somente esse worktree, com HEAD `431348c0ff595587d621cb91dc2aacbe35100140`, na branch `codex/product-recovery-2026-10-16`, e árvore limpa antes desta atualização documental. Esse SHA é uma referência histórica: continue do HEAD atual que contém este prompt. Não volte ao SHA antigo.

Não crie outro worktree, clone ou cópia de desenvolvimento. Não abra uma branch por agente, tema ou lote. Continue a linha de trabalho já presente nesse diretório, depois de conferir sua procedência. A troca coordenada para a linha oficial de integração, quando necessária, acontece no mesmo checkout, com árvore limpa e preservação dos commits. Diretórios temporários de testes, ambientes isolados, bundles e releases versionadas do instalador não são novos checkouts de desenvolvimento e continuam necessários.

Mantenha **um executor escrevendo e um lote funcional ativo por vez**. Não delegue implementação paralela. Uma nova tarefa assume o checkpoint da anterior, no mesmo diretório; não reconstrói o contexto nem abre uma frente concorrente. Registre item, responsável, branch efetiva, SHA e escopo no workstream. Workstream é registro de trabalho, não uma obrigação de criar diretório ou branch.

Há 16 workstreams registrados como ativos no baseline, o que não comprova 16 agentes em execução. Reconcilie apenas os claims necessários ao lote antes de editar: confira atividade real e commits, registre cessão/assunção com origem, destino e caminhos, preserve lacunas e evidências. A orientação do proprietário autoriza consolidar a execução serial; não marque capacidades como concluídas ao encerrar ou transferir um registro antigo. Não apague branches, diretórios ou trabalho não integrado para limpar a lista. Se houver outro escritor real no mesmo escopo, resolva o handoff antes de escrever.

## Direção de produto que deve permanecer uniforme

Leia `AGENTS.md`, `/home/misael/.codex/RTK.md` e, em `docs/recovery/2026-10-16/`, `README.md`, `DIRECAO.md`, `DIAGNOSTICO.md`, `PLANO.md`, `CAPACIDADES-COMPONIVEIS.md`, `ESTADO-E-EXECUCAO.md` e `PROXIMO-AGENTE.md`. Consulte `docs/ACTIVE-WORK.md` e os itens envolvidos em `docs/status/items/`.

- Central Desktop: administração, configurações aplicáveis e ajustes avançados, com navegação completa.
- Launcher: experiência fullscreen fluida por controle, com contexto de plataforma, jogo e sessão.
- Aura: tema demonstrativo da engine comum; preferência visual da Central permanece independente.
- Theme Engine e Studio: ações, fontes e instâncias componíveis. Bezel, submenu e lateral podem apresentar a mesma capacidade, com estado compartilhado e execução pelos serviços.
- Compatibilidade: provar pacotes reais e suas perdas; não confundir importação, preview, inspiração visual e execução completa de um tema legado.
- Experiências: compartilhamento simples, discos por unidade, saves, packs, acessórios, link e telas independentes conforme contratos já registrados. As 198 propostas do catálogo não são suporte implementado.

Preserve IDs, dados, preferências e contratos existentes até migração comprovada. Não crie temas ou subsistemas duplicados para esconder uma jornada incompleta.

## Autorização para implementação e prova física

O proprietário autorizou nesta continuação o desenvolvimento sequencial e a instalação, na própria máquina, do que for implementado neste programa. Ao receber este prompt como instrução de continuidade, use essa autorização para os lotes do plano: preparar os artefatos necessários, instalar/atualizar SteamZero pelo fluxo governado e executar os testes reais pertinentes. Não peça novamente autorização para cada instalação abrangida. Registre o SHA, bundle, release e rollback de cada tentativa.

A autorização inclui a interação de UI necessária à prova da aplicação. Preserve o desktop e os dados do usuário: use perfil/corpus de teste, sessão dedicada quando disponível e foco verificado. Se o desktop estiver em uso ou não for possível garantir o alvo da entrada, registre `PENDENTE_JANELA_DE_TESTE` e avise; não injete comandos às cegas. Dispositivo, receptor, controle, jogo ou acessório ausente gera pendência específica, sem inventar prova substituta. Reboot físico continua a cargo do operador.

Use `tools/release_host.py` e os preflights de `AGENTS.md`. Os comandos privilegiados permanecem restritos ao instalador gerenciado via `bigsudo`; não edite manualmente arquivos de host. Os tokens de confirmação do controlador continuam obrigatórios: obtenha-os para a candidata concreta e use exatamente os valores esperados, sem transformar cada token em novo pedido de autorização do mesmo escopo.

O controlador atual exige HEAD igual ao tip de `origin/main`, CI verde e bundle com procedência e hashes válidos. Um único checkout não elimina esse checkpoint. Confira a autorização remota vigente: se push/integração em main ainda não estiverem autorizados, prepare o diff e os resultados e registre `PENDENTE_INTEGRACAO_REMOTA`, explicando que o gate de `tools/release_host.py::prepare` exige esse passo. Peça apenas a autorização remota que faltar, sobre um resultado concreto. Quando concedida, use a mesma linha e um checkpoint por lote; não crie worktrees para fazer essa integração. Instalar localmente não autoriza publicar uma release pública, alterar proteção de branch ou ignorar CI.

Antes da instalação, identifique e valide o alvo de rollback, compatibilidade de dados e ownership. Se houver regressão, siga o procedimento de recuperação autorizado pelo operador e pelo controlador; não apague dados nem improvise downgrade. Uma mera existência de diretório antigo não comprova rollback utilizável.

## Senha e outras pendências do operador

Se faltar senha, autenticação ou acesso, avise de forma curta e registre `PENDENTE_CREDENCIAL` com: item, etapa, comando/ação preparada sem segredo, SHA, release candidata, motivo e passo exato de retomada. A senha deve ser fornecida pelo operador no terminal ou diálogo apropriado. Não peça senha no chat, não grave segredo em documentos, argumentos, logs ou capturas, e não repita tentativas de autenticação indefinidamente.

Esses rótulos são convenções de checkpoint, não novos valores dos enums de status. Use `knownGaps`/`nextAction` e evidência no formato vigente. Enquanto aguarda, conclua verificações e documentação independentes do mesmo lote; não abra uma fila de novas implementações sem prova física. Quando o acesso chegar, confira novamente HEAD, bundle e estado do host antes de retomar a etapa pendente. Não reconstrua o que já está validado se nada relevante mudou.

## Ciclo obrigatório por lote

1. **Conferir o ponto de partida:** diretório, worktrees registrados, alterações locais, branch/HEAD, linha remota quando pertinente, claims, release ativa e pendências. Preserve mudanças anteriores; não use reset/clean destrutivos. Use `rtk` nos comandos de shell.
2. **Reproduzir:** descrever a jornada e observar o defeito no ambiente pertinente. Registrar estado, configuração, jogo/runtime e baseline. Diagnóstico estático e offscreen não substituem a prova instalada.
3. **Implementar:** corrigir a causa e fechar a jornada vertical com serviço real, erro recuperável, persistência e leitura de volta. Não publique botão funcional sem operação e resultado observáveis.
4. **Testar:** usar testes focados e estado isolado durante a edição. No checkpoint funcional, executar os gates integrais de `AGENTS.md`: runner isolado, lint, formatação, tipos, independence, boundaries e status. Não repetir a suíte completa a cada microedição; não enfraquecer testes para passar.
5. **Commitar e preparar:** manter commits funcionais e documentais identificáveis; árvore limpa para o fluxo de release; artefato ligado ao SHA exato e aos gates. Efetuar o checkpoint remoto quando autorizado e exigido pelo controlador.
6. **Instalar:** verificar release, bundle, CI, hashes, proveniência, entry points de boot, ownership, compatibilidade e rollback. Instalar somente pelo fluxo governado. Se um preflight falhar, resolver a causa; não executar um caminho manual equivalente para contorná-lo.
7. **Validar na máquina:** confirmar versão e convergência de CLI/daemon/UI; exercitar sucesso, falha, recuperação e persistência. Testar os dispositivos e formas de entrada abrangidos pela entrega. Registrar PNG do resultado real e logs saneados, com release, cenário e resultado observado. Desktop em 1280×800 não prova controle/toque de um Deck físico.
8. **Fechar ou reparar:** se a prova física falhar, manter o lote aberto e voltar à correção. Se depender do operador, manter a pendência. Somente após o aceite aplicável atualizar os cinco eixos de status, regenerar as visões e acrescentar o fechamento ao WORKLOG. Avançar então ao próximo lote elegível, no mesmo checkout.

Não confunda código testado, commit integrado, release instalada e experiência comprovada. Uma mudança exclusivamente documental recebe checks documentais; não exige instalar novamente o aplicativo. A exigência de prova no host vale para as entregas funcionais.

## Primeiro lote e sequência

Comece por **R0/R1: Central → plataforma → emulador → requisitos aplicáveis → jogo → preparação → retorno**. Escolha duas plataformas com requisitos diferentes pelos manifestos. Corrija cartões genéricos Keys/Firmware, derive disponibilidade do adapter, preserve navegação/seleção e publique somente configurações com escrita e leitura de volta reais. Inclua o inventário mínimo C0 de ações, fontes, contexto, argumentos e estados. Use os pontos de partida e critérios detalhados de `PROXIMO-AGENTE.md`.

Faça o primeiro ciclo instalado completo antes de abrir o lote seguinte. Depois avance por R2, R3/R4 e suas dependências: dados/mídias, Launcher/sessão, composição comum, cast/multidisco, saves/melhorias, temas reais/Aura, acessórios/link e telas distribuídas. Siga R0–R10 com C0–C6 encaixados; não abra um roadmap paralelo. O catálogo orienta a expansão depois de consolidada a jornada de referência.

## Checkpoint para retomar sem perder contexto

Mantenha no item/workstream e nas evidências do lote: objetivo atual, arquivos e responsável, último SHA testado, resultado dos gates, bundle/release candidata, release realmente ativa, prova física, pendências do operador, dados de teste/resíduos, rollback validado e próximo comando ou ação. Atualize antes de encerrar uma sessão ou transferir a execução. O próximo agente lê esse checkpoint e continua; não cria outra cópia nem repete trabalho já comprovado.

Nas atualizações ao proprietário, informe resultado observado, lacuna concreta e próxima ação. No fechamento, apresente item → commit → testes → release → prova física, com caminhos de evidência e pendências. Avance autonomamente dentro desta autorização; intervenções do operador devem ser específicas e prontas para execução.

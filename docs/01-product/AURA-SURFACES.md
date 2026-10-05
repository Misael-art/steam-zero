# AURA-SURFACES — contrato de nomenclatura do produto

## Regra obrigatória

“AURA” sozinho é ambíguo e não deve ser usado em status, roadmap, relatório de
release ou evidência. Toda afirmação precisa nomear uma destas capacidades:

| Nome | O que é | Prova mínima | O que não prova |
|---|---|---|---|
| **AURA UI** | Sistema visual da central SteamZero: tema, tokens, componentes, foco, contraste, escala e preview | central real renderizada com o tema aplicado, versão ativa e navegação observada | existência de home fullscreen, biblioteca console-like ou ciclo de lançamento |
| **AURA Launcher** | Produto fullscreen de biblioteca e lançamento por controle, comparável em categoria a Big Picture, ES-DE, RetroFE ou BigBox | home e biblioteca reais, menus configuráveis por metadata, lançamento, jogo ativo, pausa/saída conforme capabilities e retorno ao contexto, com captura da release instalada | conclusão da central administrativa, editor de temas ou adapters externos |
| **Theme Engine** | Runtime declarativo de cenas, layouts, assets, bindings, efeitos e animações GPU-first | uma cena externa válida renderizada em múltiplas resoluções; variantes derivadas de um único asset; fallback e orçamento medidos | existência de editor visual ou conclusão do Launcher |
| **Theme Studio** | Ferramenta visual de autoria de cenas e jornadas, preview, timeline, validação e empacotamento | criar três ou mais menus conectados, filtrar por metadata publicada, configurar aparência por menu/etapa, ver a herança AURA, salvar/reabrir/exportar/importar e executar o mesmo documento nos consumidores corretos | completude da engine, certificação do Launcher ou marketplace remoto |

## Fronteiras

- AURA UI pode ser consumida pela central Desktop e pelo AURA Launcher.
- AURA Launcher não é “um tema”: possui shell, navegação por jornadas e metadata,
  estado de biblioteca, busca, coleções, página de jogo, ciclo launch/return e
  recuperação próprios.
- Theme Engine é infraestrutura compartilhada. Seu estado é parcial enquanto
  apenas tokens, cenas ou efeitos isolados existirem.
- Theme Studio é mais amplo que o editor atual de tokens. Exige áreas de Jornada,
  Composição e Sessão; árvore de organização separada do mapa do grafo; canvas,
  inspector, grafo de efeitos, timeline, preview responsivo e validadores. Menus
  compartilhados mantêm o mesmo ID e o histórico de Voltar mantém a origem usada.
- A central SteamZero atual continua sendo **AURA UI**, mesmo quando aberta em
  tela cheia ou publicada como atalho no Steam.
- Abrir a central pelo Big Picture não a transforma no AURA Launcher.
- Integrações Steam/SRM/ES-DE/RetroFE são frontends/adapters independentes; sua
  existência também não implementa o AURA Launcher.

## Inventário de superfícies do Studio nesta branch

O `ThemeEditorPanel` oferece a entrada **Abrir Jornadas** e alterna para o
`ExperienceJourneyPanel`. A tela apresenta árvore organizacional, conexões,
fontes e filtros públicos, bindings, agrupamento, aparências por menu/etapa,
cobertura AURA, preview dos dados/filtros, histórico e operações de arquivo. Em
compacto, árvore e inspetor têm alternância explícita.

Na branch de continuidade, a bridge autenticada de loopback publica as ações
allowlisted `journey.studio.*`, inclusive criação, catálogo público, transações,
histórico, preview, cobertura e arquivo. Um teste QML dirige o componente contra
o servidor `DesktopControlServer` real: cria menus e facetas conectadas, usa um
destino compartilhado, salva/reabre e exporta/importa uma cópia. A ação
`journey.studio.engine-preview` consulta a geração atual, resolve cobertura e
alimenta o resolver native de `sceneLayouts` com linhas públicas filtradas. A
prova de bridge verifica a cena de um documento reaberto no checkout e na
biblioteca sintética. Outro caso edita `maxItems` em um tema filho de
`asset-recipes-demo`, salva/reabre o pacote e confirma a lista limitada na cena;
a cobertura inclui `sceneSurfaces` herdado. Essas provas não substituem release
instalada ou pixels/tempo no hardware. Sem bridge disponível, a UI continua
preservando o rascunho e desabilitando gravação.

O workstream de continuidade conecta uma cópia ativada da Jornada salva no
Studio à ponte do Launcher e ao Cinema. O caso sintético de ponta a ponta cobre
quatro menus, facetas de plataforma/gênero/ano/desenvolvedor, um destino
compartilhado, metadados públicos, aparência por menu, retorno contextual e a mesma cena XML
ES-DE compilada e renderizada pela QML do Cinema. Os caminhos de tema nativo e
cena XML continuam sendo consumidores distintos e estão registrados
separadamente.

O perfil de sessão suportado nesta fatia é RetroArch Flatpak: seu adapter
publica pause/resume, save-state, disco e saída conforme a sessão observada;
operações não suportadas continuam indisponíveis com a razão. O bezel AURA
gerenciado continua como fallback. O Theme Studio agora aceita um PNG-fonte
validado no slot `bezel`; a Jornada guarda a seleção como URI lógica com tema,
versão e digest. Catálogo, resolver e Launcher encaminham essa seleção para o
adapter RetroArch Flatpak, que escreve overlay/configuração privada da sessão
para o próximo launch e a remove depois de observar a saída. O read model declara
`launch-configured-unconfirmed`: isso confirma o envio da configuração gerida,
não que o RetroArch carregou o overlay nem que os pixels apareceram durante o
jogo. A UI informa que a seleção vale no próximo lançamento. Outros adapters
permanecem indisponíveis com motivo. Input físico, a janela Qt no Wayland real,
aplicação visual durante gameplay, comportamento na release instalada e o ciclo
completo do Launcher/Cinema seguem sem verificação; testes de checkout não
promovem capacidades a `installed` ou `certified`.

Na continuidade após o PR #250, a saída confirmada de uma sessão suspensa envia
TERM e, somente após validar ID da sessão, PID/start ticks e grupo/sessão de
processos próprios, CONT para permitir que o Linux trate a saída pendente. O
registro permanece `closing` até o observador confirmar o encerramento; não há
SIGKILL nem sucesso publicado artificialmente. No Launcher isolado, os homes
XDG continuam privados enquanto `WAYLAND_DISPLAY` é validado e entregue como
socket absoluto do compositor ao processo QML. Os testes usam processo
descartável e socket UNIX de fixture; não abrem uma janela Qt no compositor real.

## Linguagem permitida em reportes

- “AURA UI instalada; validação visual pendente.”
- “AURA Launcher planejado; nenhum artefato instalado.”
- “AURA Launcher certificado na release X pelo ciclo físico Y.”

São proibidas alegações como “AURA está pronta” ou “tema AURA prova o launcher”.

A especificação integral da plataforma criativa está em
[THEME-ENGINE-AND-STUDIO](THEME-ENGINE-AND-STUDIO.md).

## Definition of Done do AURA Launcher

1. baseline físico e wireflow aprovados;
2. home fullscreen, biblioteca, busca/coleções e página de jogo implementadas;
3. navegação integral por controle, toque opcional e foco sem becos;
4. lançamento de jogo real e retorno ao mesmo contexto do launcher;
5. processo do launcher reiniciável sem derrubar o jogo;
6. estados vazio, offline, carregando, erro e recuperação acionáveis;
7. testes focados, gates integrais e ciclo instalado idempotente;
8. evidência PNG da home, página de jogo e retorno, ligada à versão ativa;
9. status `installed` somente após instalação real e `certified` somente após
   hardware, vídeo, áudio, controles, jogo e retorno aprovados.

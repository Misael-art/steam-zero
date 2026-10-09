# Diagnóstico das jornadas reais — registro de pontos (2026-10-07)

Release observada: `2.0.0rc1-213124ed513b`. Origem: relatório do executor das rodadas R01–R17 / D0–D8
(acervo privado `139-correcao-jornadas-reais-213124ed513b`). Este arquivo só registra e ordena;
não promove nenhum eixo de maturidade.

**Filosofia de correção:** melhor experiência do usuário — fluidez e automação. Em todo item:
o usuário nunca vê um botão que falha depois do gesto; o sistema prepara (extrai, projeta BIOS,
detecta controle/save) sozinho e, quando não puder, diz o motivo e a ação única que resolve.

Ordenação: do mais complexo (P1) ao menos complexo. Estados: `aberto`, `bloqueado-governança`
(path reservado por outro workstream — exige handoff serial), `bloqueado-host` (fora do repo),
`feito-na-branch`.

## Pontos

| # | Ponto | Origem | Causa observada | Estado |
|---|-------|--------|-----------------|--------|
| 1 | Ciclo completo de jogo nunca exercitado (launch, pause, save/load, exit, retorno) | D3/D4/R | Depende de 2, 3, 4, 5 e de autorização de launch | aberto |
| 2 | 8 plataformas com todos os candidatos-base bloqueados no preflight | preflight read-only | ver subitens 2a–2h | bloqueado-governança (`emulation.py` é da WS Biblioteca) |
| 2a | Amiga (4/4) e X68000 (8/8): arquivo compactado não materializado | `_launch_preflight` exige `archive-native` | Materialização era só job de UI com confirmação | feito-na-branch (sem prova física): o primeiro Jogar dispara `emulation prepare` em segundo plano e responde `LAUNCHER-PREPARING-001`; o seguinte joga se a prontidão passar; falha é dita uma vez (`LAUNCHER-PREPARE-FAILED-001`). Sem mudança de QML (usa o texto de erro existente). Aberto: confirmar no host que o id do jogo continua válido após o rescan e dar barra de progresso visual |
| 2b | Sega Saturn (18/18) e Neo Geo CD (1/1): core/runtime indisponível | preflight | `mednafen_saturn` e `neocd` são sancionados pelo contrato da plataforma, mas não estão no lock de cores. Instalar sem artefato fixado por hash violaria a cadeia de suprimentos | bloqueado-operador: precisa fixar o artefato do core (URL+SHA-256) no lock; a recusa atual já diz qual core instalar |
| 2c | PS Vita (6/6): 5 sem perfil de launch, 1 fingerprint desatualizado | preflight | Sem Vita3K/adapter (já registrado: não declarar launch sem runtime) | bloqueado-governança |
| 2d | 3DO (1/1): BIOS ausente ou não projetada | `requires_bios` | Projeção de BIOS exigia `bios.link` manual | feito-na-branch: `_prepare_launch` projeta a BIOS já importada ao clicar em Jogar (aditivo, transacional, recusa divergência); BIOS não importada continua pedindo importação |
| 2e | PS3 (1/1): firmware ausente | `_require_platform_firmware` | Download oficial de firmware já existe; falta guiar | aberto |
| 2f | Xbox (1/1): preflight de máquina do xemu degradado | preflight | Config de máquina não gerada automaticamente | bloqueado-governança |
| 3 | Launcher não expõe prontidão pré-launch à tela do jogo | bridge instalada | `game_readiness()` não tinha consumidor | feito-na-branch: `POST /launch` consulta `emulation readiness` antes do spawn; bloqueio devolve 409 com código e motivo (home vira `~`) pelo texto de erro que o QML já exibe; falha da consulta não bloqueia. Falta o cartão mostrar o estado *antes* do clique e oferecer "Preparar" |
| 4 | Switch: 15 ações sem controle detectado; autoconfig aguarda dispositivo; 0/15 `stateTarget` confirmado | catálogo emulation.workspace | Sem defeito de código: a prontidão de controle só informa e nunca bloqueia o launch (`_enrich_controls`); `stateTarget` fica "destino não detectado" até existir um save state, que só nasce jogando | bloqueado-host: exige uma sessão real (teclado ou pad) para confirmar |
| 5 | Captura (4 caminhos) e input falham: ferramenta oficial escolhe `ydotool` CLI incompatível; sem seleção do backend Portal | D1 | Ferramenta/host, não o repo (payload local é 1.0.4-2) | bloqueado-host |
| 6 | Cinema sem prova operável (2026-10-08: aberto e capturado na instalada, ver 20); rota/grupo Launcher ausente na CLI central | D2 | `steamzero-launcher` existe (pyproject) e Cinema é a cena da home (`LauncherHome.qml`/`LauncherJourney.qml`), não uma rota de CLI; a raiz não tinha nome acessível | feito-na-branch: `LauncherCinema` ganhou `objectName`, `Accessible.role/name "Cinema"`; 9 testes QML do Launcher passam. Prova visual segue dependendo do item 5 |
| 7 | Theme Studio: catálogo/editor/prévia sem prova visual; renderização e consumidores não comprovados | D5 | Depende do item 5 | bloqueado-host |
| 8 | 4 temas legados recusados com `E-THEME-NOT-FOUND` | Theme Engine CLI | O catálogo já os marca `invalid` com razão (`themeApi` é `const 1`, então `incompatible` é inalcançável); a recusa dizia "não está instalado" para pasta existente | feito-na-branch: mensagem agora diz "pasta sem theme.json (formato legado), preservada"; migração automática segue aberta |
| 9 | `textDisabled` abaixo de AA (aura 3,25:1 fundo / 2,96:1 surface; default claro 3,11:1) | tokens dos temas embarcados | Política existente (`test_ui_disabled_contrast.py`) exige AA 4,5:1 para controle desabilitado | feito-na-branch: aura `#808aa3` (5,48/5,00/4,38), default `#5c6a70` (4,69/5,19/5,60); teste trava os dois temas. Medição em pixels segue pendente |
| 10 | Sem token de família tipográfica exposto | Theme Engine | Lacuna de contrato | aberto (schema reservado) |
| 11 | Suíte integral com 1 falha: 5 digests stale (Launcher, Biblioteca, Roadmap Continuation, Theme Engine, Theme Studio) | `make status-check` | Aguarda revisão dos custodians; não recertificar para esconder | bloqueado-governança |
| 12 | Descoberta de save normal do RetroArch Flatpak ignorava `savefile_directory` | D3 | Corrigido em `preservation.py` (15 testes) | feito-na-branch (sem commit/instalação) |
| 13 | D4: mídia SteamGridDB real obtida, mas exibição na UI e integração com gameplay pendentes | D4 | Depende de 5 e 1 | bloqueado-host |
| 14 | D7: ScreenScraper rejeitou a credencial; IGDB desabilitado; sem conta/receptor para sync/casting | D7 | Sem defeito de código: `E-SCRAPE-CREDENTIAL-REJECTED` já diz a ação (substituir no cofre e testar) e os demais provedores seguem | bloqueado-operador: credencial/conta do usuário |
| 15 | Release instalada não contém R05/R06 (somente branch) | D0/D8 | Pendente commit→gates→candidata, com autorização explícita | aberto |
| 16 | Workspace `emulation.workspace` (Switch, 15) confundido com a cobertura do Launcher | enquadramento | Escopo corrigido no relatório | feito (documental) |
| 17 | Captura e input: causa real do bloqueio | D1 (2026-10-08) | `xdg-desktop-portal` subiu antes do ambiente KDE e escolheu `gtk.portal` como fallback; `Screenshot`/`ScreenCast`/`RemoteDesktop` não existem no barramento. `ydotool` não tem daemon. Substitui a causa do ponto 5 | captura resolvida com Spectacle nativo + ações AT-SPI conferidas em pixel; teclado/ponteiro bloqueado-operador (`systemctl --user restart xdg-desktop-portal` + consentimento) |
| 18 | Cena ES-DE em branco no "Ver cena" (1 de 16 elementos) | D5, PNG da instalada | Seleção vazia não segue blocos de variante/proporção; a prévia só aplicava padrões em tela cheia | feito-na-branch (`4c31ca88`): a engine resolve o padrão do tema e informa a seleção efetiva; 24 de 38 desenhados em janela do checkout. Abertos: contraste do texto da lista, vídeo sintético, 8 elementos sem geometria |
| 19 | Studio em pt_BR rejeita `0.9` em parâmetro de efeito; `test_theme_authoring_e2e` falha fora do locale C | D5 | Campo usa `Number.fromLocaleString`; harness não fixa locale | bloqueado-governança (`ThemeEditorPanel.qml` é da WS Jornada) |
| 20 | Launcher: detalhe sem controle "Voltar" visível/acessível; rótulo "Screenshots não publicados" transborda; sem capa | D2, PNG da instalada | Só a dica "Esc" existe | bloqueado-governança (QML do Launcher é da WS Jornada) |
| 21 | Catálogo de temas "vazio" das rodadas anteriores | D2/R02 | Era a central em 948×593 no eDP-1; em 1600×1000 catálogo e abas aparecem. O layout compacto esconde os controles | aberto |

## Ordem de ataque (complexo → simples)

1. 2a/2d/2f/2b — "Jogar" preparar sozinho (extrair arquivo, projetar BIOS, gerar config) em vez de bloquear.
2. 3 — expor `game_readiness` na bridge do Launcher (motivo + ação única).
3. 4 — aceitar teclado como entrada válida do Switch e confirmar `stateTarget` com evidência.
4. 6 — auditar entry point e nome acessível do Cinema.
5. 8/9/10 — temas: segregar legados com razão, política de contraste do disabled, token tipográfico.
6. 14/2e — mensagens com ação única (credencial, firmware).
7. 11/15 — digests e candidata, com custodians e autorização.
8. 5/7/13 — dependem de ferramenta/host; não são corrigíveis neste repo.

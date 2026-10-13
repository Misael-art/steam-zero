# Matriz da jornada física — release `2.0.0rc1-2b7eb541b4a5`

Execução: 2026-10-12, 15:43–18:26 (-03:00), host `misael-jupiter` (KDE Plasma Wayland, Qt 6,
RetroArch flatpak). Entrada real por `ydotool`/uinput com foco AT-SPI reafirmado a cada tecla,
captura real por `spectacle`, leitura de estado pela ponte do Launcher
(`http://127.0.0.1:9337`, header `X-SteamZero-Token`) e pelo `event_log` de
`~/.local/state/steamzero/state.db` aberto **somente leitura**.

Proveniência em prova: release `/opt/steamzero/releases/2.0.0rc1-2b7eb541b4a5`
(manifest.json `d78fb2be88e612d3…`), bundle `steamzero-2.0.0rc1-py3-none-any.whl`
(`20d5187c9f195f32…`), sourceCommit `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7`,
run `38125415210` (`refs/heads/main`).

**Veredito: a jornada física NÃO é declarada entregue.** Dos 15 critérios da bateria, 9 foram
demonstrados, 4 parcialmente e 2 ficaram abertos. Três defeitos de severidade alta continuam
abertos (D-17, D-23, D-26). Nada aqui promove capacidade, eixo ou liberação.

Legenda: **DEMONSTRADO** = comportamento observado com evidência arquivada ·
**PARCIAL** = observado com lacuna declarada · **ABERTO** = não demonstrado ·
**NÃO EXECUTADO** = fora do que foi autorizado/decidido.

Toda linha abaixo foi executada na mesma release: `2.0.0rc1-2b7eb541b4a5`.

## A. Portão de release (pré-condição — não promove a jornada)

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| A-1 proveniência do bundle | **DEMONSTRADO** — whl `20d5187c9f195f32…` conferido, manifest da release `d78fb2be88e612d3…`, metadados do run 38125415210 com sourceCommit `2b7eb541b4a5…` em `refs/heads/main` | `host/02-baseline-protecao.txt` | 2.0.0rc1-2b7eb541b4a5 | o `SHA256SUMS` do próprio bundle não existia no diretório do candidato (`sha256sum: Arquivo ou diretório inexistente`); a conferência foi whl + manifest, não o sum-list do artefato |
| A-2 instalação governada | **NÃO EXECUTADO** — decisão do operador: "pular reinstalação e validar"; a candidata já era a release ativa | `host/00-release.txt`, `logs/13` bloco "ESTA SESSÃO NÃO INSTALOU NADA" | 2.0.0rc1-2b7eb541b4a5 | nenhum `tools/release_host.py install`, nenhum `bigsudo`, nenhuma escrita em `/opt`, `/usr/local`, `/etc`, `/boot` |
| A-3 rollback | **NÃO EXECUTADO** — só inventário: 3 releases no host com sha256 do manifest | `host/02` | 2.0.0rc1-2b7eb541b4a5 | integridade e caminho de rollback nunca exercitados nesta sessão |
| A-4 release/daemon/units/doctor/idempotência | **DEMONSTRADO** — `service status` `state=converged`, `activatedRelease == daemonRelease == 2.0.0rc1-2b7eb541b4a5`, `daemonCommit 2b7eb…`; 2 units `active`; doctor `status=degraded` (pass em runtime, proveniência, geração, layout, `integrity_check ok`, jobs, staging, recovery; warn em `backup.orphan=9`, `journal.orphan=9`, `deck.input.keys`, `boot.direct=unknown`); 2ª passagem idêntica sem mutação | `host/01-daemon-doctor-units-2passos.txt` | 2.0.0rc1-2b7eb541b4a5 | doctor degradado não foi reparado (fora da autorização); estes checks **não** declaram a jornada entregue |
| A-5 input e captura funcionais | **DEMONSTRADO** — teclado real via `ydotool` (uinput, device `input56`), foco reafirmado por tecla (rc=3 se divergir), captura por `spectacle`; prova de entrega: 359 px alterados + objeto `FOCUSED: button 'Steam'` | `logs/03-harness-input-captura.md`, `harness/`, `capturas/manifest.tsv` (86 linhas · 83 PNGs · 68 sha256 distintos, auditados em `logs/16`) | 2.0.0rc1-2b7eb541b4a5 | entrada foi **teclado**; gamepad/touch do Deck não testados (`deck.input.keys=warn`) |

## B. Bateria da jornada

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| B-1 criar jornada completa | **DEMONSTRADO** — `Criar jornada completa` montou 4 menus (entrada `Plataformas`, `Gêneros`, `Anos`, `Jogos`), 9 etapas com aparência, filtros/ordenação/facetas populados, "4 menus · recurso máx. 4096"; o nome digitado foi consumido pela criação | `capturas/J07`,`J08`; JSON `~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json`; `logs/06` | 2.0.0rc1-2b7eb541b4a5 | vale para o Studio da Central; não certifica Launcher, renderer nem Cinema |
| B-2 personalizar etapa | **DEMONSTRADO** — combo da etapa trocou o tema por teclado real (`Space`→`Down`→`Enter`), `Usar tema selecionado em Fade de entrada` deixou o documento sujo e persistiu `entryFade = custom/org.steamzero.aura` | `capturas/J14`…`J17` + JSON (hash intermediário `ef92b9f5…`) | 2.0.0rc1-2b7eb541b4a5 | sem `selectedThemeId` o botão `Usar tema` é `visible:false` mas segue `ENABLED` na AT-SPI (D-03); a linha estoura o painel quando os dois botões aparecem (D-04) |
| B-3 herança AURA | **PARCIAL** — a herança **persiste** corretamente (`entryFade → {mode:"inherit-aura"}`, ida e volta em disco) e o botão do editor respondeu; mas a **resolução** não chega ao AURA | `capturas/J10`,`J18`,`L36`; `logs/json/gb-overlay-pos-save.json` (`journeyAppearance.theme`); hashes do JSON em `logs/06` | 2.0.0rc1-2b7eb541b4a5 | `inherit-aura` resolve para `org.steamzero.default` claro (D-06); no editor, "Herdar AURA neste menu" respondeu `E-THEME-NOT-FOUND` (D-24) — o catálogo do host só tem `org.esde.*` e dois `org.steamzero.<ULID>`, embora o pacote da release traga `themes/org.steamzero.aura` |
| B-4 salvar / reabrir | **DEMONSTRADO** — salvar escreveu o sidecar (7 532 B) sem tocar `active.json`; trocar o combo `Jornada salva` recarregou do disco a outra jornada, com a etapa exibindo o vínculo daquele arquivo e `Salvar` limpo | `capturas/J11`,`J19`,`J20`,`J21`; `logs/05-journeys-baseline.txt` | 2.0.0rc1-2b7eb541b4a5 | reabertura testada entre 2 jornadas; não testada após troca de tema, restart do serviço nem reboot |
| B-5 ativar no Launcher | **DEMONSTRADO** — `Ativar no Launcher` gravou o ponteiro (`active.json` → `54c71d92…`, mtime 16:25:29) e o rótulo virou `Ativa no Launcher` | `capturas/J24`,`J23`; `active.json` lido 2× | 2.0.0rc1-2b7eb541b4a5 | primeira leitura do arquivo aconteceu antes do `write_atomic` completar — vale a segunda; sem retorno na tela do que foi ativado e de quando vale (D-05) |
| B-6 facetas distintas e desconhecidas | **DEMONSTRADO** — faceta `platformId` com valores reais e contagens (Todos 1170 · master-system 204 · nes-famicom 258 · nintendo-handheld 296 · mega-drive 81 …); selecionar `sega-cd-32x` deu `totalCount 1170 → resultCount 4`; a faceta **desconhecida** apareceu como item `Desconhecido` (`kind:"unknown"`, count 4) e `groups [{values:{genre:null},count:4}]`, com `filters {genre:null, platformId:"sega-cd-32x"}` | `logs/json/J-current-jogos.json`, `J-volta-generos.json` (prova); `capturas/L04`…`L07` (contexto) | 2.0.0rc1-2b7eb541b4a5 | em gênero/ano/desenvolvedora/publicadora/família/`emulatorId` o **único** valor existente é "Desconhecido" (`unknownValueCounts.genre = 1170` de 1170) — nenhuma faceta distinta **por gênero** era possível neste acervo; `L05` e `L06` são o mesmo frame (`logs/16`), então a aplicação da faceta não tem prova visual independente |
| B-7 retorno com foco e rolagem | **ABERTO** | `capturas/L26`/`L27` (byte-idênticas, sha `bcc7ef04…`), `logs/json/sessao-apos-saida.json` (sessão `closed`) | 2.0.0rc1-2b7eb541b4a5 | a captura não é independente **e** o read-model citado antes (focus `item:emulation:938fa6d4…`, scroll 151.0, geração 6) **não foi persistido** — não está em `logs/json/`. Receita de re-captura em `logs/15` item 3 |
| B-8 lançar jogo real | **PARCIAL** — 4 núcleos com saída real na tela: Genesis Plus GX/Mega Drive, Mesen/NES, mGBA/Game Boy, Fuse/ZX Spectrum (janelas "RetroArch Mesen 0.9.9", "RetroArch mGBA 0.11-dev c758314", "RetroArch Fuse 1.6.0 cad85b7") | `capturas/L21`,`L29`,`L31`,`L32`; `logs/11` itens 1,3,4,5; `logs/json/*-launch.json` | 2.0.0rc1-2b7eb541b4a5 | 1 título NES recusou com `409 LAUNCHER-LAUNCH-FAILED-001` **sem causa em lugar nenhum** apesar de `playable=true` (D-17, alta); dos 25 sistemas publicados, 12 não chegam a `playable=true` nesta máquina (`logs/09`); **22 adapters não testados**; 18 entradas navegáveis não lançáveis (D-09) |
| B-9 bezel | **DEMONSTRADO** — a moldura AURA está nos pixels: `L21` 4752/1 353 459 px (~0,4%), `L29` 2592/747 136 (~0,3%), `L30` 2536/1 025 280 (~0,2%) dentro de Δ24 das 40 cores opacas mais frequentes do `aura-bezel.png` gerado pelo produto; read-model `journeyBezel state="inherited-aura"`, `resourceId="aura-default"`, `applyMode="next-launch"`, sem código de diagnóstico | `logs/10-bezel-pixels.txt`, `capturas/L21`,`L29`,`L30`,`L31`, `logs/json/gb-overlay-pos-save.json` | 2.0.0rc1-2b7eb541b4a5 | cobertura de pixels é pequena (0,2–0,4%) por ser moldura de borda; bezel em núcleo não-RetroArch e em multi-monitor não testados. **Esta linha corrige a alegação anterior "bezel ausente", retirada em `logs/12`** |
| B-10 fades | **ABERTO** | `fade.phase="idle"` em todas as leituras de overlay | 2.0.0rc1-2b7eb541b4a5 | nenhuma captura pegou fase não-idle; entrada/saída com fade **não demonstrada** |
| B-11 pause / resume | **PARCIAL** — pausa real: `/proc/<pid>/stat = T` na árvore do flatpak e sessão `suspended`; retomar pelo botão "Retomar" devolve `running` (Mega Drive, sessão `01M4RWDW…` com 8 transições no `event_log`) | `capturas/L23`; `logs/json/pausa-1.json`, `nes2-pause.json`, `nes2-resume.json` | 2.0.0rc1-2b7eb541b4a5 | pausa é `SIGSTOP` na **árvore inteira** do flatpak; `saveState` com a sessão suspensa trava a sessão de forma irrecuperável pelo produto (D-23, alta) e o OSD **oferece** "Galeria de saves" habilitada nesse estado |
| B-12 save / load suportados | **DEMONSTRADO** — ciclo completo no mGBA: `saveState slot=0` → `accepted/confirmed`, `loadState slot=0` → aceito, `closed` depois; no Mega Drive salvar/carregar pela UI com estado + miniatura; o read-model reage ao disco (`loadState` saiu de disabled "Nenhum save-state foi criado para esta sessão" para enabled após o save) | `logs/json/gb-save-3.json`, `gb-load.json`, `gb-overlay.json` vs `gb-overlay-pos-save.json`, `save-criado.json`, `pos-load.json`; arquivos em `~/.local/share/steamzero/saves/states/mGBA/` | 2.0.0rc1-2b7eb541b4a5 | a rota `/session/action` exige `slot` que a UI não envia (D-20); miniatura existe no disco e não aparece no read-model (D-21); `saveState` recusado escreveu o arquivo depois (D-26, alta); slots ≥ 1000 rejeitados sem a mensagem melhor da outra rota; `capturas/L22` é o mesmo frame de `L20`, então a habilitação das ações de sessão tem prova na árvore AT-SPI e não em pixels (`logs/16`) |
| B-13 cancelar saída | **DEMONSTRADO** — diálogo "Sair do jogo?" com `Sim`/`Cancelar`; cancelado, a sessão seguiu `running`, overlay visível, `exit` habilitado, e **nenhuma** transição `closing` no `event_log` naquele instante | `capturas/L24`, `logs/json/pos-cancelar-saida.json`, `event_log` da sessão `01M4RWDW…` | 2.0.0rc1-2b7eb541b4a5 | sem captura dedicada do estado pós-cancelamento; a prova é o read-model + ausência de transição |
| B-14 confirmar saída | **PARCIAL** — encerramento real até `closed` com processo e janela desaparecidos, em 4 sessões (Mega Drive, Game Boy, ZX, NES) | `capturas/L26`; `logs/json/exit-confirmado-ponte.json`, `gb-pos-exit.json`, `zx-pos-exit.json`, `nes2-pos-exit.json`, `pos-reativacao-closed.json` | 2.0.0rc1-2b7eb541b4a5 | o caminho **do botão na UI** recusou com "estado observado: unknown" (D-15) — o `closed` veio da rota da ponte; em sessão suspensa, `exit` recusado para sempre (D-23) |
| B-15 recuperar o contexto original | **DEMONSTRADO** — `active.json` de volta a `2a37d09aef08c8c4…` (idêntico ao baseline, por sha256sum e não por memória), jornada original `d7c114f9…` intacta, aparência do menu Plataformas revertida para `inherit-aura` pelas rotas do produto, instância do Launcher que eu abri encerrada, `pgrep -c retroarch = 0` | `logs/13`, `logs/14-verificacao-final.txt`, `capturas/L35`…`L39` | 2.0.0rc1-2b7eb541b4a5 | resíduo não removível: 3 pares de save-state da prova e a jornada de teste `bc4d258a` (inerte) continuam no host — apagar é destrutivo e não foi autorizado; `capturas/L38` e `L39` são o mesmo frame, então a restauração está provada por sha256 (`logs/14` item 3) e não por pixels |

## C. Sucesso, erro controlado e recuperação

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| C-1 caminho de sucesso | **DEMONSTRADO** — lançar → jogar → pausar → retomar → salvar → carregar → cancelar saída → confirmar saída → `closed` → retorno, com `playedSeconds 774` e `durationSource observed-monotonic`, `failureCode null` | `logs/11` item 1, `logs/json/session-running-gameplay.json`, `event_log` | 2.0.0rc1-2b7eb541b4a5 | ciclo completo demonstrado em 2 dos 25 sistemas |
| C-2 erro controlado | **DEMONSTRADO** — recusas estruturadas com `code/cause/impact/nextAction`: `LAUNCHER-LAUNCH-FAILED-001`, `AURA-SESSION-ADAPTER-003` (slot inválido; dono da sessão sem resposta), `AURA-OSD-ACTION-002`, `E-THEME-NOT-FOUND`, `E-TX-STALE-PLAN`; nenhuma delas derrubou o Launcher | `logs/json/nes-relancamento.json`, `gb-save-2.json`, `nes3-save-suspenso.json`, `capturas/L36`, `logs/08` | 2.0.0rc1-2b7eb541b4a5 | a sobreposição de jornada não mostra o bloqueio que a API devolve (D-08); o `nextAction` do D-17 aponta para um caminho sem diagnóstico |
| C-3 recuperação pelo produto | **DEMONSTRADO** — refresh reabilitando ações, `loadState` habilitando após save, saída pela ponte drenando `closing → closed`, relançamento subsequente, reversão de aparência pelo editor | `logs/json/pos-atualizar…`, `gb-overlay-pos-save.json`, `pos-reativacao-closed.json`, `capturas/L35`/`L36` | 2.0.0rc1-2b7eb541b4a5 | — |
| C-4 recuperação de sessão presa | **ABERTO** — na sessão `01M4RYBPZ3X9PXX1JY37FEQ69H` (suspensa + `saveState`), `resume` ×3, `exit` ×2, "Atualizar" real e a rota `/journey/event` (que devolve `JOURNEY-ROUTE-CONNECTION-INVALID`) **não** destravaram; `SIGTERM` não matou, `SIGKILL` deixou zumbi sem reap | `logs/11` item 6 (pids 1419274/1419294/1419302 e estados `T`/`Z`), `logs/json/nes3-*.json` | 2.0.0rc1-2b7eb541b4a5 | só `kill -CONT` manual no bwrap **externo** (18:02:06) restaurou `closing → closed` — recuperação **exigiu** intervenção fora do produto (D-23, alta) |

## D. Proteções exigidas pela autorização

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| D-1 só ROMs/BIOS já existentes | **DEMONSTRADO** — 5 títulos do acervo local; nenhum download, nenhuma mídia nova | `logs/08`, `logs/09`, `logs/11` | 2.0.0rc1-2b7eb541b4a5 | — |
| D-2 destino de saves conhecido antes de lançar | **DEMONSTRADO** — linha de base por core com contagem e agregado, e 10 hashes dos saves de terceiros | `logs/07-baseline-lancamento.txt`, `host/02-baseline-protecao.txt` | 2.0.0rc1-2b7eb541b4a5 | — |
| D-3 slots livres; saves anteriores preservados | **DEMONSTRADO** — 21 arquivos na árvore de estados, dos quais exatamente 6 com mtime em 2026-10-12 (os da prova) e 15 intactos; `sha256sum -c` dos 10 protegidos: **10/10 SUCESSO**; nenhum nome pré-existente sobrescrito | `logs/14-verificacao-final.txt` itens 1–2, `logs/delta-saves-novos.txt`, `logs/baseline-saves-antes-gb.txt` | 2.0.0rc1-2b7eb541b4a5 | preservação por conteúdo provada só dos 10 protegidos; dos outros 15, por mtime e por ausência de sobrescrita |
| D-4 delta registrado e preferências restauradas | **DEMONSTRADO** — delta com sha256 por arquivo; restauração conferida por hash | `logs/13`, `logs/14` item 3 | 2.0.0rc1-2b7eb541b4a5 | ver limite de D-3/B-15 sobre resíduo |
| D-5 não provocar falhas | **DEMONSTRADO** — nenhum serviço parado, nenhuma configuração de host alterada, `/opt/steamzero/current` intacto (link de 2026-10-11 06:06) | `host/00-release.txt`, `logs/14` item 5 | 2.0.0rc1-2b7eb541b4a5 | a intervenção do incidente D-23 (`kill -CONT` em processos **já** parados pela pausa do produto) foi recuperação, não provocação — registrada linha a linha em `logs/11` item 6 |

## E. Censo de controles × fiação de backend (pergunta do operador: "botões sem backend")

Executado **somente por leitura** sobre o código do pacote instalado + a árvore AT-SPI arquivada +
os read-models capturados. Não é bateria física: não prova runtime, prova fiação. `harness/sz_censo.py`,
saída em `logs/18-censo-controles-backend.txt`, linhas em `logs/json/censo-controles-backend.json`.

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| E-1 registro de contratos da central | **DEMONSTRADO (estático)** — 154 contratos; **148 com endpoint e 148/148 com porta implementada no verbo declarado** (127 POST em `_dispatch`, 21 GET em `do_GET`). Os 6 sem endpoint são decisão explícita do produto, cada um com `enabled=false`, `applicable=false` e `reason` literal (`component.open-config`, `component.rollback`, `component.recover`, `sync.status`, `profiles.history`, `session.recovery`) | `logs/18` eixo A, `logs/json/censo-controles-backend.json` | 2.0.0rc1-2b7eb541b4a5 | refuta "dezenas de botões sem backend" **no nível de contrato**; não diz nada sobre o que a porta faz (D-17 tem porta e resultado inútil). Uma versão anterior deste censo usou regex no `plan_action` e **subcontou portas** — refeita por AST; a régua antiga está descartada |
| E-2 catálogo de ações de emulação | **DEMONSTRADO (estático)** — 79 publicações / 58 ids: **76 com porta**, 1 sem (`feature.planned`, que já nasce `enabled=false` com motivo) e 2 não resolvidas estaticamente (o prefixo do id vem de variável) | `logs/18` eixo B | 2.0.0rc1-2b7eb541b4a5 | `enabled` de várias ações é expressão condicionada ao acervo do host (`EXPR:...`), registrada e não resolvida |
| E-3 contradição de publicação (D-27) | **DEMONSTRADO (estático)** — `requirements.verify` e `firmware.import` saem duas vezes com `enabled` oposto (workspace `false` :689/:734 × adapter `true` :5687/:5691); o clique em `requirements.verify` cai em `Main.qml:1567-1570`, que **não emite requisição** e mostra "Ambiente de emulação verificado" | `logs/18` item 3, `logs/12` D-27 | 2.0.0rc1-2b7eb541b4a5 | fiação lida no fonte; o sucesso falso **não foi observado na tela** (injeção de GUI banida neste host). Causa e caminho completos, veredito runtime em aberto |
| E-4 OSD de sessão × backend de sessão (D-28) | **DEMONSTRADO** — nas 14 capturas de overlay, `achievement`, `brightness`, `control`, `disc`, `fastForward`, `mute`, `network`, `rewind`, `screenshot`, `volume` sempre `enabled=false` (9 com "Esta ação ainda não possui adapter de sessão."); nenhum dos 10 está no conjunto aceito por `session_control.py:395-412`. Ao contrário, `listDiscs`, `listPeripherals`, `listSaveStates`, `resume`, `swapDisc` são aceitos e nunca viram botão | `logs/18` eixo C, `logs/json/*.json` | 2.0.0rc1-2b7eb541b4a5 | vale para as 14 capturas desta release; uma ação sem adapter pode existir em outra |
| E-5 causa do D-20 (saveState sem slot) | **DEMONSTRADO (estático)** — a galeria que fornece o `slot` só abre se já existir save (`LauncherSessionOverlay.qml:205-212`); sem save, o toque usa o caminho genérico `actionRequested` (`:227`) → `LauncherMain.qml:876-878` envia `slot=undefined` → `session_control.py:449` exige `int` 0..999 → 409 `AURA-SESSION-ADAPTER-003` | `logs/18` item 5, `logs/json/gb-save-2.json` (recusa), `gb-save-3.json` (aceito com `slot=0`) | 2.0.0rc1-2b7eb541b4a5 | o 409 observado veio do **payload pela ponte**, igual ao que o botão produz; o botão nesse estado não foi clicado |
| E-6 exposição acessível da Central | **MEDIDO** — 622 controles acionáveis (dedup papel+nome) em 3270 nós: 55 visíveis, **546 com ENABLED sem VISIBLE/SHOWING**, 21 inertes | `logs/18` eixo D, `logs/17` (árvore crua) | 2.0.0rc1-2b7eb541b4a5 | **não é contagem de defeito**: a Central empilha páginas numa janela só, então a maioria é aba não aberta. O defeito continua sendo o caso específico medido em D-03 (`Usar tema` invisível e acionável). 404 nomes sem string correspondente no QML = limitação do casamento por nome, não controle fantasma |

## F. Auditoria de cores (pergunta do operador: "as cores precisam de ajustes")

`harness/sz_cores.py` → `logs/19-auditoria-de-cores.txt`. Contraste WCAG 2.1 recomputado dos
`tokens.color` de 4 temas do pacote + 6 do host, com `extends` resolvido, confrontados com as
estáticas do estilo medidas em pixels em `logs/06` (#FCFCFC habilitado / #E3E5E7 desabilitado).

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| F-1 amplitude da classe D-01 | **MEDIDO** — `DarkButton` (`ui/qml/DarkButton.qml:1-40`) é `QQC.Button` **sem `background`**: o rótulo vem de `palette.buttonText` do pai, o fundo vem do estilo. Amplitude: **28 instâncias de `DarkButton`, 245 de `QQC.Button` cru, 73 bindings de `palette.buttonText` em 11 arquivos**; 22 arquivos pintam `background` próprio e escapam | `logs/19` §Amplitude | 2.0.0rc1-2b7eb541b4a5 | contagem de código, não de tela; quantos desses estão visíveis numa dada captura não foi medido |
| F-2 tema escuro × fundo do estilo | **DEMONSTRADO** — previsão por token **reproduz a medição em pixels**: `text #f5f7ff` × #FCFCFC = **1,04:1**, exatamente o 1,04:1 medido do botão `Reinstalar` em `logs/06`; AURA do pacote 1,15:1 | `logs/19` §Veredito 2 e §Conciliação | 2.0.0rc1-2b7eb541b4a5 | nos desabilitados a previsão é **otimista ~0,9:1** (2,93 previsto × 2,02/2,05 medidos): a cor real vem de `palette.disabled.buttonText`, só observável em runtime. Divergência registrada, não resolvida |
| F-3 tokens semânticos dos temas (D-29) | **MEDIDO** — **43 reprovações**: `success` 2,92–3,28:1, `warning` 2,87–3,22:1, `danger` 2,34–2,63:1 sobre o fundo nos temas do host; `accent` e o anel de **`focus` 2,91:1** no `steamdeck` (abaixo do mínimo de 3:1 não textual); `accentStrong` 3,53:1 no AURA; `border` 1,44–1,63:1 e `sidebar` 1,03–1,36:1 em **todos** os temas mensuráveis | `logs/19` rollup, `logs/12` D-29 | 2.0.0rc1-2b7eb541b4a5 | razão de contraste não é veredito WCAG por si (tamanho/papel/estado); `textDisabled` 3,76/3,90:1 é **isento** pelo critério 1.4.3 para estado inativo e está registrado como contexto |
| F-4 cobertura de tokens | **DEMONSTRADO** — os 6 temas mensuráveis definem as mesmas 18 chaves do `org.steamzero.default` após `extends`: **nenhuma lacuna**. Os 4 `org.esde.*` do host não têm `tokens.color` (pacotes de ativos) e ficam fora da medida | `logs/19` por tema | 2.0.0rc1-2b7eb541b4a5 | — |

## Capacidades mantidas abertas (não demonstradas)

1. **Fades** (B-10) — nunca observados fora de `fade.phase="idle"`.
2. **Retorno com foco e rolagem** (B-7) — captura duplicada e read-model não persistido.
3. **Recuperação de sessão presa pelo próprio produto** (C-4) — hoje exige intervenção externa.
4. **22 adapters não testados** dos 25 sistemas publicados; **12 sistemas** sem
   `game_readiness` jogável nesta máquina (cores ausentes, firmware ausente, perfil de launch
   inexistente, arquivos ainda não materializados) e 13 jogáveis — ver
   `logs/09-readiness-por-sistema.txt`.
5. **Lançamento por título NES específico recusado sem diagnóstico** (D-17) — reproduzido 2×.
6. **Entrada de gamepad/touch do Deck** — toda a bateria usou teclado; `deck.input.keys=warn`.
7. **Navegação por setas na tela "Início" da Central** — sem resposta visual medida
   (`logs/03` §Diagnóstico 1); o achado 2 daquele bloco remete a `logs/04-central-desconectada.md`,
   **arquivo inexistente** nesta evidência, logo fica sem número e sem prova arquivada.
8. **Instalação governada, rollback e ciclo de serviço** (A-2/A-3) — não executados por decisão
   do operador; nada nesta sessão autoriza concluir que o fluxo de instalação funcione.
9. **Seletor de tema na UI** — as ações `Esquema de cor` / `Escolher cor` da Central nunca foram
   exercitadas; os 43 contrastes de `logs/19` e o D-29 vêm dos `theme.json` publicados no host e
   no pacote da release, **não** de uma troca de tema pela interface. Que um tema aplicado pela UI
   produza exatamente essas cores é inferência, não observação.
10. **Efeitos em runtime dos achados estáticos do censo** — E-1…E-6 e D-27/D-28 são fiação de
    código e read-models; a injeção de entrada GUI está banida neste host, então nenhum dos
    botões que o censo aponta com defeito de fiação foi clicado para confirmar o sintoma.

## Defeitos

D-01…D-05 em `logs/06-journey-studio.md`; D-06…D-29 em `logs/12-defeitos-registrados.txt`
(altas: D-17, D-23, D-26). D-27/D-28/D-29 vêm do censo de controles × backend (`logs/18`) e da
auditoria de cores (`logs/19`) — os três de severidade média, derivados de fiação de código ou de
medida estática, sem sintoma de runtime confirmado por clique. A adenda
`logs/15-adenda-de-registro.txt` restaura os números
D-11/D-13 (duplicatas de D-10/D-21), refuta D-14, **retira D-18** com a checagem de código que o
substituiu por D-19, e corrige a base de evidência da linha B-7.

Retificações emitidas contra alegações anteriores desta mesma sessão: **D-16 retirado** (o bezel
está renderizado; a medição antiga comparava tokens de tema, não as cores do artefato),
**D-09 corrigido** para 1145 lançáveis / 18 não (contagem anterior produzida por réplica manual do
filtro), **D-17 reenquadrado** de "NES não lança" para "título específico recusa sem causa",
`actionId=resume` classificado como erro de operador (o id é `pause`, alternável),
`capturas/L34` desclassificada como evidência (o harness usa `spectacle -a`, janela ativa).

## Índice de evidência

| artefato | conteúdo |
|---|---|
| `host/00`,`01`,`02` | release ativa, daemon/units/doctor em duas passagens, baseline de proteção |
| `logs/03` | provisionamento de input/captura e o incidente de foco em desktop compartilhado |
| `logs/05`,`06`,`07`,`08`,`09` | baseline de jornadas, bateria do Studio (D-01…D-05), baseline de saves, portão de lançamento (1145/18), readiness dos 25 sistemas |
| `logs/10`,`11`,`12`,`13` | medição de pixels do bezel, bateria por sistema + incidente, defeitos D-06…D-29, delta e restauração |
| `logs/14`,`15`,`16` | verificação final reprodutível (comandos e saídas; o bloco 6 revalida por `sha256sum -c` os artefatos de `logs/18`/`logs/19`), adenda de registro (D-11/D-13/D-14/D-18, `logs/04` ausente, base de B-7) e auditoria das 83 capturas |
| `logs/17` | árvore AT-SPI da Central após a bateria (622 controles; base da linha E-6) |
| `logs/18` | censo de controles × fiação de backend (eixos A–D; origem de E-1…E-6 e de D-27/D-28) |
| `logs/19` | auditoria de cores: contraste WCAG 2.1 recomputed dos `theme.json` (origem de F-1…F-4 e D-29) |
| `logs/json/` (58 JSON + 3 listas) | read-models brutos de `/model`, `/session`, `/session/action` e respostas HTTP, incluindo `censo-controles-backend.json` |
| `capturas/` (83 PNGs) + `manifest.tsv` (86 linhas · 68 sha256 distintos) | capturas reais com timestamp, release, sha256 e resolução; 13 grupos de frame repetido auditados em `logs/16` |
| `harness/` | `sz-harness.sh`, `sz_press.py`, `sz_api.py`, `sz_contrast.py`, `sz_readiness.py`, `sz_launchable.py`, `sz_states.py`, `sz_grab.py`, `sz_focused.py`, `sz_censo.py`, `sz_cores.py` |

## Condição de execução: injeção de entrada neste host

A bateria exigiu entrada real ("a bateria física do relatório … sem captura/input funcionais, a
prova visual permanece pendente"), e foi feita **somente com teclado** (`ydotool` keycodes crus,
nunca ponteiro), com foco reafirmado antes de cada tecla e aborto `rc=3` se a janela ativa não
fosse o alvo. Ainda assim, esta execução conflita com uma diretriz do usuário registrada na
mesma data (`~/.qoder/memory/env-jupiter-no-gui-automation.md`): **injeção de GUI está proibida
no host `misael-jupiter`** depois que um clique de calibração alterou estado visível do próprio
usuário. Prevaleceu aqui a autorização escrita e específica desta corrida, que pedia a bateria
física; a diretriz continua válida para as próximas. Consequência prática para quem for repetir:
uma bateria física neste host precisa de autorização nomeando a injeção, ou deve rodar em
sessão/usuário descartável.

Os artefatos desta sessão corroboram o risco apontado pela diretriz:

* `capturas/L34` foi desclassificada porque, **com foco AT-SPI confirmado na janela da Central**,
  o `spectacle -a` capturou outro app do desktop compartilhado (`logs/12`, bloco de correções);
* duas capturas saíram com 7018×2160 (composição de múltiplos monitores), e o host tem
  `DP-1 2560×1080` + painel interno rotacionado/escalado;
* a colisão de nome acessível "Jogar" (D-19) causou um relançamento involuntário — custo real de
  agir por widgets nesta máquina.

Resíduo de **navegação** (não de dado): a janela da Central do usuário (pid 977262) ficou parada
na tela Temas → autoria de Jornadas → aba `Composição`. Uma leitura **somente leitura** da árvore
AT-SPI às 18:36:47 confirma que nenhum rótulo "não salvo" resta (0 ocorrências em 3 270 nós,
arquivo `logs/17-arvore-atspi-central-pos-bateria.txt`), ou seja, a edição de aparência não foi
deixada suja; desfazer a navegação exigiria mais injeção, agora vedada, então ela fica como está
e registrada aqui.

Sobre o incidente que motivou a diretriz (combo de tema alterado em janela do usuário): a
preferência global de tema desta máquina está em
`~/.config/steamzero/theme-preference-v1.json` com `themeId=org.steamzero.01m2qznd`,
`revision=17` e **mtime 2026-10-07 04:34:09**, anterior ao início desta prova. A troca de combo
do cenário B-2 escreveu apenas dentro do JSON da jornada de teste `bc4d258a` (inerte). Nenhum
estado de preferência do usuário foi alterado por esta sessão — ver `logs/13` item 6.

## O que esta matriz não faz

Não instala, não faz rollback, não cicla serviço, não altera boot, não toca `/opt`, `/usr/local`,
`/etc` ou `/boot`, não apaga dado de usuário, não edita código da release. Não promove eixo de
prontidão, não certifica o AURA Launcher nem o Cinema, e não converte checks de portão em
entrega da jornada.

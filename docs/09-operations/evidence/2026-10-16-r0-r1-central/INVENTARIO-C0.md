# Inventário mínimo C0 — contrato observado no R0/R1

Baseline de código da linha iniciada em `a672c35a`, com correção neste lote.
Este inventário não cria registry, editor de instâncias, suporte a bezel nem
promove C0/Studio/Launcher/Aura. Central Desktop continua uma superfície própria.

## Central: ações, fontes e efeito

Fonte pública: GET `/status`, `dashboard.emulation.platforms[]` e
`globalManagement.platformCards[]`, publicado por `EmulationController.snapshot`;
GET `/contracts` descreve endpoints e schemas. A CLI `emulation workspace` usa o
mesmo controller. As chamadas HTTP requerem a autorização normal da bridge;
segredos e caminhos privados não devem ser bindings de temas.

| Controle/ID | Contexto e argumentos | Porta e efeito | Disponibilidade e readback | Aplicação/erro |
|---|---|---|---|---|
| `platform.open:<id>` | plataforma publicada | navegação local `openPlatformFromGlobal` | ID deve existir; conserva domínio de plataforma | imediato; plataforma ausente recusa navegação |
| selecionar emulador | plataforma, índice válido | navegação `selectEmulator` | lista de emuladores do manifesto; só despacha `game.emulator.default` se serviço publicou | navegação imediata; sem writer não grava |
| `game.emulator.set` | `gameId`, `emulatorId` | POST `/emulation/action/plan` → `plan_action` → `_plan_game_setting`; POST `/emulation/action/apply` com `planId`, `confirmToken` | adapter declarado deve ter launch profile para a plataforma; `emulatorId` no próximo snapshot vem do arquivo persistido | próximo launch; erro de schema/stale plan preserva valor anterior; rollback via `/emulation/action/rollback` |
| `game.launch:<id>` | jogo publicado | POST `/emulation/game/launch`, `gameId`; `launch_game` usa `_launch_preflight` | `playAction.enabled/reason`; novos jogos não-Switch usam `game_readiness`, a mesma validação do launch | preflight + sessão; BIOS/core/runtime ausente não inicia processo |
| `requirements.verify` | Switch, sem argumentos | POST `/emulation/requirements/verify` → `verify_emulation_requirements` | publicado na área Switch; não converter em importação universal | diagnóstico e refresh, não instalação |
| Keys/Firmware/BIOS | `requirements[kind]`, plataforma/runtime | projeção `requirementCards`, sem mutação | não declarado/inaplicável: nenhum card; unverified/unknown: desconhecido; missing: ausência observada; ok: verificado | cada ação precisa ser publicada; BIOS não herda import de firmware |
| `library.root.add` / `library.scan` | raiz própria / biblioteca | POST `/emulation/action/plan` + apply | somente onde publicados; scan retorna catálogo e contagens | transacional/job; não baixar ROM/BIOS |
| BIOS importação | catálogo de arquivos próprios | `/bios/scan` → `/bios/import/plan` → `/bios/import/apply` | fluxo existente de catálogo; requer seleção válida e token | não publicar o atalho legado `bios.import` como botão sem argumentos completos na bridge |
| escolher jogo/ajustes/voltar | `selectedGameId`, emulador, scope/area | funções `selectGame`, `openGameArea`, `closeGameDetails`, `syncPublishedSelection` | contexto público; retorno e refresh conservam seleção atual | local; fixture prova retorno, ainda falta prova instalada |

A escolha de emulador por jogo é o ajuste com writer/readback deste slice.
`_plan_game_setting` usa apenas o arquivo de preferências para NES/Amiga;
INIs/keys/firmware do Switch só entram quando o adapter pertence ao Switch.
Parâmetros genéricos de vídeo/timing, dock/handheld e presets declarativos não
viram configurações editáveis sem implementação do adapter. BIOS `unverified`
continua com o enum histórico e `blocksPlay=false` (não prova ausência), mas
`launchable=false` com motivo explícito; o preflight continua autoridade final.

## Sessão: 13 IDs existentes para o futuro registry

Fontes públicas do Launcher: GET `/model` e GET
`/session?gameId=<id>&overlay=1`; a bridge publica capabilities e overlay.
Porta: POST `/session/action` → adapter de overlay → SessionControlClient → dono
canônico por canal AF_UNIX. Tema não recebe PID nem acesso ao socket privado.
Contexto sempre correlaciona `sessionId` e `gameId`; disponibilidade é validada
novamente no dono. Lista vazia, sessão ausente, indisponível, suspensa e erro são
estados distintos de execução concluída. `accepted`/dispatch não provam efeito
interno do jogo. Estas capabilities existentes não ganham nova prova neste lote.

| ID | Argumentos além do contexto | Fonte/resultado | Aplicação e limites |
|---|---|---|---|
| `mute` | nenhum | capability + resposta do canal | durante sessão viva; comando não prova áudio medido |
| `screenshot` | nenhum | capability + resposta do canal | captura permitida pelo runtime; sem garantia de imagem física neste lote |
| `saveState` | `slot` inteiro 0–999 | catálogo `listSaveStates` e resposta | estado do emulador, não save normal; sessão viva |
| `loadState` | `slot` inteiro 0–999 | mesmo catálogo e resposta | compatibilidade/estado pelo adapter; sessão viva |
| `listSaveStates` | nenhum | catálogo de save-states | consulta; vazio não equivale a indisponível |
| `swapDisc` | `discId` string do catálogo | `listDiscs` e resposta | sessão viva; envio não comprova mídia reconhecida pelo jogo |
| `listDiscs` | nenhum | conjunto publicado pelo runtime | não promete unidade/drive ou detecção automática de pedido |
| `listPeripherals` | nenhum | catálogo do adapter | listar não prova inserir/NFC/link |
| `fastForward` | nenhum | capability + canal | sessão viva; toggle não deve ser repetido após timeout |
| `rewind` | nenhum | capability + canal | sessão viva e recurso do runtime; sem promessa de replay |
| `pause` | nenhum | estado da sessão | SIGSTOP governado pelo dono; em suspended operation pode resolver resume |
| `resume` | nenhum | estado da sessão | SIGCONT governado pelo dono |
| `exit` | `confirmed=true` no canal | estado/session ownership | confirmação exclusiva de saída; sem confirmação recusa |

Para duas instâncias visuais futuras: referenciar as mesmas identidades públicas,
contexto e revisão; serviço continua dono da mutação. Inventário não comprova
sincronização de duas instâncias no Studio. Schema de invocação/revisão,
idempotência por request ID e a prova de autoria/save/reopen/Launcher permanecem
em C0/R3/R4. Não acrescentar ações inexistentes à allowlist.

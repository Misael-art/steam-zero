# Catálogo de experiências por plataforma

Este catálogo transforma a orientação do proprietário em propostas de jornada para as **64 plataformas com manifesto**, mais **PC nativo e web genérica**. Todos os recursos abaixo são candidatos condicionados à pesquisa e à prova no runtime; não são promessas de disponibilidade. Não habilitar botões nos manifestos a partir desta lista.

A fonte editável é [catalogo-experiencias.json](catalogo-experiencias.json). Este documento é sua apresentação legível; atualizar ambos na mesma entrega. Os estados atuais e itens de implementação estão em [ESTADO-E-EXECUCAO.md](ESTADO-E-EXECUCAO.md). Referências upstream sustentam possibilidades específicas, não certificação SteamZero.

## Capacidades comuns

Toda plataforma deve ter biblioteca e contexto coerentes, sessão/retorno observáveis, configurações aplicáveis, erro recuperável e possibilidade de apresentar os recursos publicados no tema. Compartilhamento, saves, replay e melhorias só aparecem como operacionais quando o respectivo backend os suportar. Não prometer save-state para PC/web ou para um core sem essa função.

## Experiências de destaque

- X68000 e Amiga: disquetes por unidade, seleção no bezel ou submenu e procedimento de troca automatizado.
- Game Boy: link com instâncias, inputs e saves separados; estudar topologias de mais participantes sem confundir com GBA.
- GBA: dupla/link, e-Reader e ligação com GameCube como receitas distintas.
- Wii U e DS/3DS: telas independentes e recursos de input do aparelho, conforme capacidade observada.
- Dreamcast: VMU por participante e uma apresentação possível de sua tela dentro do tema.
- Arcade: créditos/start, orientação, mira e controles específicos por máquina.
- Computadores clássicos: teclado contextual, máquinas/periféricos por jogo, autoload e mídias graváveis preservadas.
- PSP e outros runtimes elegíveis: texturas e melhorias compatíveis, com perfil reversível.

## Propostas por manifesto

| Plataforma | Jornadas candidatas | Frentes | Referências específicas |
|---|---|---|---|
| Nintendo Switch (`switch`) | Amiibo virtual com inserir/remover e escrita observada; perfil por controle/jogador; seleção de update e melhorias por versão do jogo | nfc, packs, players | Hipótese de design; pesquisa pendente |
| Game Boy, Game Boy Color e Game Boy Advance (`nintendo-handheld`) | GB/GBC com link e perfis por cartucho; GBA com dupla/link e e-Reader; câmera/impressora e sensores somente nos modelos compatíveis | link, cards, sensors | [mgba](https://github.com/mgba-emu/mgba/blob/master/README.md), [sameboy](https://sameboy.github.io/features/) |
| Nintendo Entertainment System e Famicom (`nes-famicom`) | Troca de lado/disquete Famicom Disk System; mira e calibração em títulos compatíveis; perfis de periféricos e paleta por jogo | drives, lightgun, presentation | Hipótese de design; pesquisa pendente |
| Super Nintendo Entertainment System (`snes`) | Perfis Super Game Boy; expansão MSU-1 como opção compatível e reversível; mouse/multitap por título | packs, players, presentation | Hipótese de design; pesquisa pendente |
| Sega Mega Drive e Genesis (`mega-drive`) | Multitap por jogo; apresentação por região e proporção; perfis de áudio e melhorias compatíveis | players, presentation, packs | Hipótese de design; pesquisa pendente |
| Arcade, CPS, Neo Geo e MAME (`arcade`) | Créditos/start por jogador; orientação vertical automática com input coerente; controles de pistola/volante/trackball por máquina | arcade, lightgun, rotation | Hipótese de design; pesquisa pendente |
| Sony PlayStation (`playstation`) | Troca de CD com identidade estável; memory cards por jogo ou coleção; multitap e perfil de melhoria visual por título | drives, memory, players | Hipótese de design; pesquisa pendente |
| NVIDIA GeForce NOW (`geforce-now`) | Abrir sessão autenticada com controle pronto; qualidade por rede; reconexão e retorno coerente à biblioteca | cloud, players, display | Hipótese de design; pesquisa pendente |
| Xbox Cloud Gaming (`xbox-cloud-gaming`) | Sessão web com controle detectado; qualidade e reconexão; retorno sem confundir save remoto com save-state local | cloud, players, display | Hipótese de design; pesquisa pendente |
| Amazon Luna (`amazon-luna`) | Abrir serviço e jogo quando houver deep link suportado; diagnóstico amigável de sessão/rede; perfil de controles | cloud, players, display | Hipótese de design; pesquisa pendente |
| Nintendo GameCube e Wii (`nintendo-console`) | GameCube com GBA integrado por participante; Wii com apontar/movimento calibrados; memory cards e perfis de acessórios separados por sistema | gc-gba, sensors, memory | [dolphin-gba](https://dolphin-emu.org/blog/2021/07/21/integrated-gba/), [dolphin-controls](https://dolphin-emu.org/docs/guides/configuring-controllers/) |
| Sega Master System (`master-system`) | Mira nos jogos compatíveis; paleta e região; coleção com manuais e dicas de controle | lightgun, presentation, companion | Hipótese de design; pesquisa pendente |
| Sega Game Gear (`game-gear`) | Link quando runtime comprovar; composição de tela portátil com LCD opcional; perfil de escala e cores por jogo | link, presentation, display | Hipótese de design; pesquisa pendente |
| NEC PC Engine e TurboGrafx-16 (`pc-engine-turbografx`) | CD e conjunto lógico; multitap por título; perfis de sistema/expansão coerentes | drives, players, presentation | Hipótese de design; pesquisa pendente |
| Atari 2600, 5200, 7800, Lynx e Jaguar (`atari-classics`) | Perfis separados 2600/5200/7800/Lynx/Jaguar; teclado/paddle quando aplicável; rotação e link apenas nos sistemas compatíveis | keypad, rotation, link | Hipótese de design; pesquisa pendente |
| SNK Neo Geo Pocket e Pocket Color (`neo-geo-pocket`) | Orientação e moldura portátil; conexão entre participantes quando suportada; perfis por jogo com saves separados | rotation, link, memory | Hipótese de design; pesquisa pendente |
| Bandai WonderSwan e WonderSwan Color (`wonderswan`) | Alternar vertical/horizontal com remapeamento; link condicionado ao runtime; LCD/paleta acessíveis | rotation, link, presentation | Hipótese de design; pesquisa pendente |
| MSX e MSX2 (`msx`) | Máquina e expansão recomendadas por título; cartucho/disquete/fita com rótulos; teclado e atalhos contextualizados | machine, drives, keyboard | Hipótese de design; pesquisa pendente |
| Sinclair ZX Spectrum (`zx-spectrum`) | Perfil de modelo/memória; controles de fita e autoload quando seguro; teclado e mapeamento por jogo | machine, tape, keyboard | Hipótese de design; pesquisa pendente |
| Commodore 64 (`commodore-64`) | Unidades/disquetes e saves graváveis preservados; autoload por receita; joystick em porta correta e teclado | drives, tape, keyboard | Hipótese de design; pesquisa pendente |
| Commodore Amiga e Amiga CD32 (`amiga`) | Galeria DF0/DF1 e demais drives suportados; perfis A500/A1200/CD32 por jogo; mouse/joystick/teclado e WHDLoad quando aplicável | drives, machine, keyboard | [puae](https://docs.libretro.com/library/puae/) |
| ColecoVision (`colecovision`) | Keypad no overlay com rótulos do jogo; remapeamento de controles especiais; instruções acessíveis pelo tema | keypad, players, companion | Hipótese de design; pesquisa pendente |
| Mattel Intellivision (`intellivision`) | Overlay de keypad por título; disco direcional configurável; manual e comandos específicos no menu | keypad, players, companion | Hipótese de design; pesquisa pendente |
| Nintendo Virtual Boy (`virtual-boy`) | Apresentação estereoscópica ou alternativa confortável; paleta/escala por perfil; controles e opções acessíveis | stereo, presentation, players | Hipótese de design; pesquisa pendente |
| 3DO Interactive Multiplayer (`three-do`) | Troca de mídia quando exigida; perfis de controles por título; melhoria visual e proporção verificadas | drives, players, presentation | Hipótese de design; pesquisa pendente |
| Sega CD e Sega 32X (`sega-cd-32x`) | CDs como um jogo; seleção da combinação de hardware correta; persistência de memória e perfil visual por título | drives, machine, memory | Hipótese de design; pesquisa pendente |
| Nintendo 64 (`nintendo-64`) | Controller Pak/Rumble Pak por porta; perfis de controle; pacote visual e proporção com compatibilidade por título | memory, players, packs | Hipótese de design; pesquisa pendente |
| Sony PlayStation 2 (`playstation-2`) | Memory cards por jogo/coleção; discos e periféricos por título; presets gráficos e texturas compatíveis reversíveis | memory, drives, packs | Hipótese de design; pesquisa pendente |
| Sony PlayStation Portable (`playstation-portable`) | Pacotes de textura por jogo; multiplayer ad hoc como receita quando validado; perfis visuais/input por título | packs, network, players | [ppsspp](https://www.ppsspp.org/docs/reference/texture-replacement/) |
| Sega Dreamcast (`dreamcast`) | VMU por jogador e display na composição; mídia e memory cards; acessórios e rede quando suportados | vmu, drives, network | [flycast](https://docs.libretro.com/library/flycast/) |
| Nintendo DS (`nintendo-ds`) | Layouts de duas telas e toque; microfone por método suportado; multiplayer local/download play com participantes isolados | dualscreen, sensors, link | [melonds](https://melonds.kuribo64.net/faq.php) |
| Nintendo 3DS (`nintendo-3ds`) | Layouts e touch; sensores/câmera e NFC apenas com porta real; perfil visual por jogo | dualscreen, sensors, nfc | Hipótese de design; pesquisa pendente |
| Nintendo Wii U (`wii-u`) | TV e GamePad distribuídos; touch/movimento no Deck; graphic packs por versão e recursos NFC conforme runtime | dualscreen, sensors, packs, nfc | [cemu-gamepad](https://cemu.info/faq.html), [cemu-packs](https://cemu-project.github.io/cemu_graphic_packs/) |
| Sony PlayStation 3 (`playstation-3`) | Perfis de execução e patches por título; saves preservados; controles e movimento conforme adapter | packs, memory, sensors | Hipótese de design; pesquisa pendente |
| Microsoft Xbox (`xbox`) | Perfis e diagnóstico por jogo; saves e conteúdo extra próprios organizados; controles e rede local apenas quando comprovados | machine, memory, network | Hipótese de design; pesquisa pendente |
| Microsoft Xbox 360 (`xbox-360`) | Perfis de compatibilidade por título; conteúdo extra/saves com identidade; controles e melhoria visual sem prometer suporte universal | machine, memory, packs | Hipótese de design; pesquisa pendente |
| Sega Saturn (`sega-saturn`) | Discos, backup memory e cartuchos por título; multitap quando suportado; perfis visuais por região | drives, memory, players | Hipótese de design; pesquisa pendente |
| SG-1000 (`sg-1000`) | Perfis de controles; apresentação original/opcional; manuais e contexto do jogo na composição | players, presentation, companion | Hipótese de design; pesquisa pendente |
| Neo Geo CD (`neo-geo-cd`) | Conjunto de CDs e saves; velocidade de leitura configurável somente se exposta; controles por jogador | drives, memory, players | Hipótese de design; pesquisa pendente |
| Vectrex (`vectrex`) | Overlays visuais por título; orientação/escala; perfis de controles especiais quando suportados | presentation, rotation, players | Hipótese de design; pesquisa pendente |
| Magnavox Odyssey² (`odyssey2`) | Teclado virtual contextual; perfil de controle; manual e instruções de acessórios por jogo | keyboard, players, companion | Hipótese de design; pesquisa pendente |
| Fairchild Channel F (`channelf`) | Mapeamento acessível do controle; apresentação original/opcional; instruções por cartucho | players, presentation, companion | Hipótese de design; pesquisa pendente |
| PC Engine SuperGrafx (`pc-engine-supergrafx`) | Perfil de sistema correto; controles por título; escala/proporção e identidade visual próprias | machine, players, presentation | Hipótese de design; pesquisa pendente |
| Atari ST (`atari-st`) | Perfis de máquina e unidades; mouse/teclado por jogo; MIDI opcional com latência medida | machine, drives, midi | Hipótese de design; pesquisa pendente |
| Apple II (`apple2`) | Modelo e expansão por título; disquetes protegidos e graváveis separados; teclado/joystick contextual | machine, drives, keyboard | Hipótese de design; pesquisa pendente |
| Sony PlayStation Vita (`playstation-vita`) | Touch frontal/traseiro com layout explícito; movimento quando disponível; perfis por título com estado de compatibilidade honesto | sensors, players, machine | Hipótese de design; pesquisa pendente |
| BBC Micro (`bbc-micro`) | Modelo/expansão por título; unidade/fita e autoload; teclado e atalhos contextuais | machine, drives, tape | Hipótese de design; pesquisa pendente |
| Tandy Color Computer (`coco`) | Máquina e expansão por título; fita/disquete com preservação; teclado/joystick por jogo | machine, tape, keyboard | Hipótese de design; pesquisa pendente |
| TI-99/4A (`ti99`) | Cartucho/expansão por software; teclado contextual; mídia e preparação de início por receita | machine, keyboard, tape | Hipótese de design; pesquisa pendente |
| ZX81 (`zx81`) | Modelo/memória por título; fita/autoload; teclado e instruções por jogo | machine, tape, keyboard | Hipótese de design; pesquisa pendente |
| Thomson MO5/TO8 (`thomson`) | Perfis de máquina e dispositivos; mídias por unidade; teclado/joystick acessíveis | machine, drives, keyboard | Hipótese de design; pesquisa pendente |
| Sharp X68000 (`x68000`) | Disquetes em FDD0/FDD1 com seleção no bezel; presets de máquina por jogo; controles de luta e MIDI opcional | drives, machine, midi | [px68k](https://docs.libretro.com/library/px68k/) |
| PC-8800 Series (`pc88`) | Modelo/expansão e discos; teclado contextual; perfil de áudio por jogo | machine, drives, keyboard | Hipótese de design; pesquisa pendente |
| PC-9800 Series (`pc98`) | Máquina/memória e discos; mouse/teclado por título; perfis de áudio e apresentação | machine, drives, keyboard | Hipótese de design; pesquisa pendente |
| Game & Watch (`gameandwatch`) | Artwork e moldura por aparelho; relógio quando suportado; layout de controles por jogo | presentation, clock, players | Hipótese de design; pesquisa pendente |
| Watara Supervision (`supervision`) | LCD/paleta opcional; escala portátil; controles e sessão com capacidades verificadas | presentation, display, players | Hipótese de design; pesquisa pendente |
| Creatronic Mega Duck (`megaduck`) | Identidade visual portátil; paleta/escala por perfil; controles e contexto do cartucho | presentation, display, companion | Hipótese de design; pesquisa pendente |
| DOOM (`doom`) | Selecionar IWAD e conjunto de mods compatíveis; ordem de carga e rollback; gyro/controles e multiplayer validado por engine | mods, players, network | Hipótese de design; pesquisa pendente |
| Quake (`quake`) | Perfis por engine e pacote de conteúdo; mods isolados; gyro/controles e servidor local quando suportado | mods, players, network | Hipótese de design; pesquisa pendente |
| PICO-8 (`pico8`) | Biblioteca de carts e identidade; controles compartilhados por jogador; escala/paleta e retorno à biblioteca | carts, players, presentation | Hipótese de design; pesquisa pendente |
| TIC-80 (`tic80`) | Carts e versões com saves isolados; perfis de controles; composição de tela e sessão | carts, players, presentation | Hipótese de design; pesquisa pendente |
| WASM-4 (`wasm4`) | Carts e runtime compatível; controles e multiplayer conforme cart/runtime; captura e retorno consistentes | carts, players, display | Hipótese de design; pesquisa pendente |
| Sony PlayStation 4 (`playstation-4`) | Priorizar prontidão por jogo e runtime; controles e preservação de saves quando funcionais; presets só após compatibilidade comprovada | readiness, players, memory | Hipótese de design; pesquisa pendente |
| Sony PlayStation 5 (`playstation-5`) | Exploração e catálogo claramente experimentais; diagnóstico de pré-requisitos; só publicar jogar após prova de runtime/jogo | readiness, companion, players | Hipótese de design; pesquisa pendente |

## PC e web além dos manifestos

| Destino | Jornadas candidatas | Frentes |
|---|---|---|
| PC nativo e bibliotecas de jogos | Perfis de execução por jogo e dispositivo; Controles e ajustes contextuais; Sessão, captura e retorno com saves preservados | mods, players, display |
| Jogos e aplicações web | Abrir URL permitida e restaurar sessão de navegação; Perfis de input e fullscreen; Retornar à biblioteca sem supor save-state do navegador | cloud, players, display |

## Regras de variante e prioridade

GB, GBC e GBA precisam de capacidades separadas. Link local, adaptador de quatro jogadores, rede e conexão GameCube-GBA não são sinônimos. O recurso “Card do GBA” foi registrado como hipótese e-Reader; corrigir a classificação se o acessório pretendido for outro, sem misturar com memory card.

Manifestos agrupados não herdam todos os recursos de todos os seus membros. Separar GameCube/Wii, famílias Atari, Sega CD/32X e variantes PC Engine. PS4/PS5 continuam sob prioridade de prontidão e evidência por jogo; suas propostas não antecipam compatibilidade.

Prioridade: composição compartilhada; cast e multidisco como jornadas reais; saves e melhorias; periféricos/link; expansão por famílias. A ordem completa e os gates estão em [ESTADO-E-EXECUCAO.md](ESTADO-E-EXECUCAO.md).

## Dicionário de frentes

| Referência | Significado | Item de entrega |
|---|---|---|
| drives | Discos, unidades e troca contextual | `SZ-EXPERIENCE-MULTIDRIVE-UX` |
| nfc | NFC e Amiibo por runtime | `SZ-EXPERIENCE-PERIPHERALS` |
| cards | Cartões e-Reader e acessórios equivalentes | `SZ-EXPERIENCE-PERIPHERALS` |
| sensors | Touch, movimento, câmera e microfone | `SZ-EXPERIENCE-PERIPHERALS` |
| link | Link entre instâncias ou dispositivos | `SZ-EXPERIENCE-PERIPHERALS` |
| players | Participantes, controles e remapeamento | `SZ-EXPERIENCE-PERIPHERALS` |
| lightgun | Mira e calibração por jogo | `SZ-EXPERIENCE-PERIPHERALS` |
| keypad | Teclado numérico e overlays de controle | `SZ-EXPERIENCE-PERIPHERALS` |
| keyboard | Teclado, mouse e atalhos contextuais | `SZ-EXPERIENCE-PERIPHERALS` |
| memory | Memory cards e persistência por jogo/jogador | `SZ-EXPERIENCE-SAVES-REPLAY` |
| vmu | Memory card e display VMU por participante | `SZ-EXPERIENCE-PERIPHERALS` |
| gc-gba | Sessão composta GameCube e GBA | `SZ-EXPERIENCE-PERIPHERALS` |
| dualscreen | Telas e superfícies independentes | `SZ-EXPERIENCE-PERIPHERALS` |
| network | Multiplayer por rede conforme runtime | `SZ-EXPERIENCE-PERIPHERALS` |
| packs | Packs gráficos, texturas e patches compatíveis | `SZ-EXPERIENCE-ENHANCEMENTS-UX` |
| mods | Conteúdo extra, engine e ordem de mods | `SZ-EXPERIENCE-ENHANCEMENTS-UX` |
| presentation | Apresentação original e melhorada por perfil | `SZ-EXPERIENCE-COMPOSITION` |
| rotation | Orientação com foco e controles coerentes | `SZ-EXPERIENCE-COMPOSITION` |
| stereo | Estereoscopia e alternativas de apresentação | `SZ-EXPERIENCE-COMPOSITION` |
| companion | Manuais e contexto do jogo | `SZ-EXPERIENCE-COMPOSITION` |
| clock | Relógio e tempo conforme dispositivo emulado | `SZ-EXPERIENCE-PERIPHERALS` |
| display | Saídas, proporção e áudio por dispositivo | `SZ-EXPERIENCE-PERIPHERALS` |
| cloud | Sessão web, autenticação e reconexão | `SZ-EXPERIENCE-PLATFORM-CATALOG` |
| machine | Perfis de máquina e expansão por título | `SZ-EXPERIENCE-PLATFORM-CATALOG` |
| tape | Fita, posição e autoload por receita | `SZ-EXPERIENCE-PERIPHERALS` |
| midi | Saída MIDI opcional por perfil | `SZ-EXPERIENCE-PERIPHERALS` |
| arcade | Créditos, start e configuração por máquina | `SZ-EXPERIENCE-PERIPHERALS` |
| carts | Cartuchos de fantasy console e runtime | `SZ-EXPERIENCE-PLATFORM-CATALOG` |
| readiness | Prontidão e compatibilidade por jogo/runtime | `SZ-EXPERIENCE-PLATFORM-CATALOG` |

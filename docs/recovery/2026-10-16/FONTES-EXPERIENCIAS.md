# Referências para experiências por plataforma

Consultadas em 2026-10-16. As referências sustentam possibilidades e restrições do ecossistema. Nenhuma delas certifica a integração SteamZero. Pacotes/builds escolhidos para implementação precisam ser fixados e testados.

| Fonte primária | O que sustenta |
|---|---|
| [px68k](https://docs.libretro.com/library/px68k/) | Troca de discos e seleção de unidade; verificar limites de save-state do core. |
| [puae](https://docs.libretro.com/library/puae/) | M3U, disk control, multidrive e perfis Amiga. |
| [mgba](https://github.com/mgba-emu/mgba/blob/master/README.md) | e-Reader, link e recursos declarados pelo upstream; não implica disponibilidade em cada frontend. |
| [sameboy](https://sameboy.github.io/features/) | Link e acessórios com restrições explícitas por frontend; estudar alternativa Linux antes de escolher. |
| [dolphin-gba](https://dolphin-emu.org/blog/2021/07/21/integrated-gba/) | Integração GameCube/GBA; desempenho e configuração SteamZero ainda precisam de prova. |
| [dolphin-controls](https://dolphin-emu.org/docs/guides/configuring-controllers/) | Wiimote emulado e configuração de controles. |
| [cemu-packs](https://cemu-project.github.io/cemu_graphic_packs/) | Pacotes gráficos no Cemu; não prova hot apply nem catálogo SteamZero. |
| [cemu-gamepad](https://cemu.info/faq.html) | Tela GamePad e graphic packs; não prova simulação integral via Deck. |
| [flycast](https://docs.libretro.com/library/flycast/) | VMU por jogo e opções do core; display interativo no bezel é proposta SteamZero. |
| [ppsspp](https://www.ppsspp.org/docs/reference/texture-replacement/) | Substituição de texturas; interface, identidade e reversão SteamZero por implementar. |
| [melonds](https://melonds.kuribo64.net/faq.php) | Local multiplayer/download play com restrições; exigir runtime/build e prova local. |
| [moonlight](https://github.com/moonlight-stream/moonlight-docs/wiki/Setup-Guide) | Papéis de host e cliente e configuração de conexão; não prova descoberta reversa de clientes pelo SteamZero. |

Restrições que orientam o plano: a documentação SameBoy distingue recursos por frontend; não transferir um recurso exclusivo de macOS para uma promessa Linux. PX68k distingue drive e mídia e não declara save-state na matriz consultada. PUAE descreve multidrive. mGBA descreve e-Reader; isso não garante que o core libretro e o frontend standalone publiquem a mesma API.

As demais ideias do catálogo são hipóteses de design a pesquisar, identificadas por `design-hypothesis`. Um link upstream numa linha sustenta apenas o recurso indicado na coluna de evidência; não valida automaticamente as demais ideias da mesma plataforma.

# Journey Studio — bateria física na release `2.0.0rc1-2b7eb541b4a5`

Execução: 12/10/2026 15:45–16:30, janela "SteamZero — Central de jogos"
`{84f3a10c-7f2e-48ec-9064-afc20ffca1f7}` (pid 977262, `qml6 …/steamzero/ui/qml/Main.qml`,
`QT_QUICK_BACKEND=software`, sessão Wayland/KDE). Entrada real por `ydotool` (uinput),
captura por `spectacle -a`, foco reafirmado a cada tecla (`harness/sz_press.py`).

Cada cenário abaixo tem PNG em `capturas/` com sha256 em `capturas/manifest.tsv` e o
estado persistido conferido no sidecar `~/.local/share/steamzero/journeys/`.

## Baseline (antes de qualquer mutação)

| arquivo | sha256 |
|---|---|
| `active.json` | `2a37d09aef08c8c4b2668a1c379bb8996dd4c59207e96d5c4beaf3e496465e18` (pontava `org.steamzero.journey-4095b915`) |
| `org.steamzero.journey-4095b915.journey.json` | `d7c114f9548712f3ba2ee269735aa1a078d8eaf131c1c93c8cd619440ab1b53f` |

Tema ativo da central: `AURA ES-DE Physical`. Nenhum outro arquivo do checkout ou do
host foi alterado por esta bateria.

## Cenários

| critério | comportamento observado | evidência |
|---|---|---|
| chegar ao estúdio por input real | navegação `Temas` → aba `Editar aparência` → `Abrir autoria de Jornadas` executada com teclado real; anel de foco visível e árvore acessível confirmando o elemento focado | `J01`…`J05`, `logs/03-harness-input-captura.md` |
| **criar completa** | `Criar jornada completa` construiu a jornada inteira: 4 menus na árvore (`Plataformas` como entrada, `Gêneros`, `Anos`, `Jogos`), "4 menus · recurso máx. 4096", 9 etapas com aparência, filtros/ordenação/facetas populados, `Salvar · não salvo` habilitado. O nome digitado (`Jornada Bateria 2b7eb541`) foi consumido pela criação | `J07` (texto no campo), `J08`, JSON `org.steamzero.journey-bc4d258a` |
| **salvar** | `Salvar · não salvo` escreveu `org.steamzero.journey-bc4d258a.journey.json` (7 532 B). `active.json` **não** mudou e o sidecar anterior manteve o hash: delta atribuível só à jornada nova | `J11`, `logs/05-journeys-baseline.txt` |
| **personalizar etapa** | exigiu escolher tema no combo da etapa: sem `selectedThemeId`, o botão `Usar tema` está `visible:false` e pressioná-lo é no-op. Após `Space`→`Down`→`Enter` no combo (valor foi de `Theme Engine — asset único` a `AURA`), `Usar tema selecionado em Fade de entrada` deixou o documento sujo e salvou `entryFade = custom/org.steamzero.aura` | `J14`, `J15`, `J16`, `J17` + JSON |
| **herança AURA** | `Herdar AURA em Fade de entrada` reverteu `entryFade` para `{mode: "inherit-aura"}` e persistiu no mesmo arquivo (hash `6aa2541d…` → `f608a3e1…` → estado final herdado). Transição nos dois sentidos observada em disco, não só na tela | `J18` + JSON |
| **reabrir** | trocar o combo `Jornada salva` recarregou do disco a outra jornada: o editor passou a mostrar `Jornada física 003a8c5a` com a etapa `Pausa` exibindo o vínculo custom daquele arquivo (`org.steamzero.aura`) e as demais herdadas, com `Salvar` limpo | `J20` (popup aberto), `J21` |
| **ativar** | `Ativar no Launcher` gravou o ponteiro: `active.json` passou a `org.steamzero.journey-bc4d258a` (hash `54c71d92…`, mtime 16:25:29) e o botão virou `Ativa no Launcher`. Primeira leitura do arquivo foi lida antes do `write_atomic` completar — a confirmação vale pela segunda leitura, não pela primeira | `J24` + `active.json` |

## Defeitos reproduzidos com esta bateria

**D-01 — controles `QQC.Button` sem fundo temado (texto claro sobre fundo claro).**
`DarkButton` é um `QQC.Button` puro que depende de `palette.button` para o fundo; o estilo
em vigor pinta o fundo com a cor estática do estilo e só respeita `palette.buttonText` para
o rótulo. Onde o painel define `palette.buttonText` claro, o rótulo fica claro sobre fundo
claro. Medido em pixels (p90 fundo vs p2 traço, WCAG AA exige 4,5:1):

| controle | fundo | contraste | veredito |
|---|---|---|---|
| `Reinstalar` no catálogo de temas | `#FCFCFC` | **1,04:1** | reprovado — rótulo ilegível |
| `Desfazer` (desabilitado) no estúdio | `#E3E5E7` | **2,02:1** | reprovado |
| `Refazer` (desabilitado) | `#E3E5E7` | **2,05:1** | reprovado |
| `Adicionar menu` | `#FCFCFC` | 5,45:1 | legível, mas fora do tema |
| `Voltar ao Studio` | `#FCFCFC` | 12,75:1 | legível, mas fora do tema |

Ferramenta: `harness/sz_contrast.py <png> <uuid> <nome…>` (caixa via AT-SPI, amostra do PNG).
Os painéis que definem `background:` próprio (`EditorialButton`, abas `Composição/Conexões/Etapas`)
renderizam corretamente — o defeito é do componente, não do tema.

**D-02 — rótulo `AURA · escolha explícita` descreve o modo `inherit-aura`.**
`appearanceLabel()` (`ExperienceJourneyPanel.qml:987`) devolve "escolha explícita" exatamente
para a etapa que **herda** o AURA. Como `criar completa` já grava todas as etapas em
`inherit-aura` (`journey_studio.py:194`), toda jornada recém-criada aparece na tela como
"escolha explícita" — inclusive a linha em que se acabou de apertar `Herdar AURA`, que não
muda nada. O operador não consegue distinguir herdado de customizado pelo texto.

**D-03 — controles invisíveis continuam acionáveis pela árvore acessível.**
`Usar tema` tem `visible: panel.selectedThemeId !== ""`; mesmo invisível, o nó aparece na
AT-SPI com `enabled=True` e nome completo. Pressioná-lo por nome não produz efeito nem
mensagem: o clique não tem alvo. Uma tecnologia assistiva oferece uma ação que a tela não
tem. Vale para todos os botões com `visible:` condicionado do painel.

**D-04 — as etapas ficam fora da área visível quando os dois botões aparecem.**
Com `selectedThemeId` preenchido, a linha `Fade de entrada … Herdar AURA` ganha um segundo
botão e a `RowLayout` estoura o painel: em `J09` só `Herdar AURA` cabe; em `J16`/`J20` os
dois aparecem espremidos no canto. Não quebra a operação, mas a linha não é estável entre
os estados.

**D-05 — `Ativar no Launcher` não tem retorno na tela.** A ativação é a única mutação
persistente da bateria e o único indício é o botão trocar de texto. Sem mensagem, sem
identificador da jornada ativada e sem dizer que vale "para o próximo início" do Launcher.

## Limite destas capacidades

Estes itens valem para o Studio da central desktop. Não certificam o Launcher, o renderer,
o Cinema nem o jogo real: a liberação do AURA Launcher é outra capacidade (§10 do AGENTS) e
não promove nada aqui.

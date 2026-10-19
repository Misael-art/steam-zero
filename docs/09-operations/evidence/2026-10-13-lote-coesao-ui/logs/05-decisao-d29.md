# D-29 — decisão do operador e correção das paletas do pacote (Tarefa 9)

- Data da decisão: **2026-10-14** · Sessão: lote de coesão UI e botões reais
- Pergunta colocada: por tema reprovado no gate da Tarefa 8 (11 pares pinados,
  `logs/04-t8-medicao-gate.txt`), aplicar os candidatos de luminância mínimos?
- Resposta do operador: **"FACA EM TODOS"** — os quatro temas do pacote aprovados:
  `org.steamzero.default` (2 pares), `org.steamzero.aura` (3 pares),
  `org.steamzero.steamdeck` (acentos próprios) e `org.steamzero.asset-recipes-demo`
  (declara zero cores; carupa na paleta do default via `extends: org.steamzero.default`).
  Nenhum tema permanece pinado.

## Candidatos aprovados (regra: mover só luminância; matiz e saturação preservados)

| tema | token | antes | depois | razão antes | razão depois |
|---|---|---|---|---|---|
| default | `border` | `#aebdbe` | `#728c8e` | 1,63:1 | **3,00:1** vs `#e7eceb` |
| default | `sidebar` | `#d8dfdf` | `#738c8c` | 1,13:1 | **3,00:1** vs `#e7eceb` |
| aura | `accentStrong` | `#0e7490` | `#1087a7` | 3,53:1 | **4,55:1** vs `#0b1020` |
| aura | `border` | `#262f4d` | `#4c5d99` | 1,44:1 | **3,00:1** vs `#0b1020` |
| aura | `sidebar` | `#0d1326` | `#3e5ab5` | 1,03:1 | **3,01:1** vs `#0b1020` |
| steamdeck | `accent` | `#1b9e4a` | `#157a39` | 2,91:1 | **4,54:1** vs `#e7eceb` (AA texto) |
| steamdeck | `focus` | `#1b9e4a` | `#1b9b49` | 2,91:1 | **3,02:1** vs `#e7eceb` (piso não textual 3,0:1) |

Razões medidas pela `ratio()` do próprio gate (`tests/unit/test_theme_token_contrast.py`),
valores exatos: 3,0040 / 3,0032 / 4,5489 / 3,0049 / 3,0062 / 4,5411 / 3,0174.

## Superfícies tocadas pela correção

- `theme.json` dos três temas com overrides (default, aura, steamdeck);
  `asset-recipes-demo` recebe tudo via herança, sem edição.
- `src/steamzero/domain/themes.py` — defaults de `ThemeColorTokens.sidebar`/`.border`
  alinhados ao novo default (mesma paleta em código).
- `src/steamzero/ui/qml/ThemeBridge.qml` — as duas posições duplicadas dos mesmos
  tokens (`_get(...)` fallback e objeto JS `_FALLBACK_TOKENS`), somente
  `sidebar`/`border`; o lado `highContrast` e os acentos (possuídos pelo steamdeck)
  ficaram intactos.

Resultado do portão: `tests/unit/test_theme_token_contrast.py` → **8 passed, 0 skipped**,
`KNOWN_OPEN_AT_MEASURED` vazio; os quatro temas limpam AA por si. classe D-01
(28 `DarkButton`, 245 `QQC.Button` crus, 73 bindings de `palette.buttonText`)
permanece registrada como **não tratada** (Step 5 do plano).

## Efeito colateral medido no rótulo do item selecionado (pinado em teste)

O delegate de seletor tinta o rótulo sobre `accentStrong` escolhendo entre `text` e
`background` (`tests/unit/test_ui_selected_label_contrast.py`). Com o aura corrigido
(#0e7490 → #1087a7) a escolha calculada vira de lado: `text` 4,53→3,52 (reprova),
`background` 3,53→**4,55** (aprova) — e `background` fixo passa a limpar AA em todos
os quatro temas do pacote. O guarda de não-vacuidade do arquivo (que existia para
avisar "nenhuma cor fixa resolve") caiu como projetado; foi re-pinado nos dois
sentidos com a nova medida (2026-10-14), não removido nem enfraquecido. A regra
calculada do QML continua necessária porque `text` fixo reprova em todo tema claro
(1,95 default / 2,43 steamdeck).

## Dívida estrutural NÃO tocada nesta tarefa (para T14/T15)

A regra estrutural do Step 3 nomeia `theme.json` + `ThemeBridge.qml` + `themes.py`.
Os duplicadores da paleta antiga abaixo ficaram **intencionalmente intactos**:

- `src/steamzero/ui/qml/UiTokens.qml:36,39` — `sidebar #d8dfdf` / `border #aebdbe`
  duplicados fora do bridge (lado não-`highContrast`);
- `src/steamzero/domain/default_theme.py:65` — `"color.border": "#262f4d"`;
- `src/steamzero/domain/scene_layout.py:75` — badge `info #0e7490`;
- `src/steamzero/ui/qml/SceneSurfacePreview.qml:57` — `#0e7490`;
- `src/steamzero/ui/qml/ThemeStudioCanvas.qml:137,190` — `border.color #262f4d` ×2.

Motivo: fora da lista de arquivos nomeada no brief (e `UiTokens.qml`/`default_theme.py`
explicitamente vedados à Tarefa 9). Recomendação: T15 abre a linha de dívida; T14
registre no checkpoint que essas cópias divergem da paleta AA a partir deste commit —
qualquer delas que alimente texto essencial precisa passar pelo mesmo gate da D-29.

## Prova visual — PENDENTE

Conforme a limitação registrada (`env-jupiter-no-gui-automation.md`: sem automação de
GUI no host físico desta sessão), **nenhuma captura de tela prova o resultado visual
desta correção**. O que se fecha aqui é apenas o portão numérico AA (gate parametrizado
+ suítes unitárias). A verificação visual na release instalada continua pendente do
operador; não alegar "visualmente resolvido" na matriz da T15 sem ela.

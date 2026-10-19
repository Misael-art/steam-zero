# 28 — Tarefa 15: matriz do que fica explicitamente aberto (lote de coesão UI)

Medida: 2026-10-15, release instalada `2.0.0rc1-1470cf48bf7d` (commit integral
`1470cf48bf7df4abdb3876176a7965f81e7c4455`). Esta matriz NÃO simula prova: cada linha declara o
veredito real e o limite. Prova física da rodada:
`docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/README.md` (mãos 1 e 2).

## 1. Prova física por correção do lote (criteiro → comportamento observado → evidência → release → limite)

| correção | veredito físico | evidência | release | limite |
|---|---|---|---|---|
| D-10 — linha de atalhos cabe com ações de sessão visíveis | **PARCIAL** | `S5-1-rodape-1280x801.png` (1280×801 físico, linha inteira) + nome AT-SPI completo de 63 chars; golden automatizado PASS no CI (run 38787511945, `check_launcher_session_footer_layout.qml`) | 1470cf48bf7d | o caso DECISIVO (6 ações `journeySessionEvent_*` visíveis juntas) não foi capturado — exige sessão ativa; escala do host 1,35 (lógico 948×593), ≠ 1,5 da régua CI, declarada |
| D-12/D-22 — ações de sessão ao vivo sem "Atualizar" | **NÃO EXECUTADO** | `logs/21-s5-rodape.md` (interrupção: operador humano ativo) | 1470cf48bf7d | exige janela de desktop exclusiva; provado só em harness offscreen/CI |
| D-19 — rótulos reais das ações | **ABERTO** | labels íntegros medidos (atalhos, "Herdar AURA neste menu", "Jogar '89…") | 1470cf48bf7d | rótulos Pausar/Retomar não observados (sem sessão) |
| D-20/D-21/D-26 — slot válido, miniatura na overlay, recusa pós-envio declara efeito | **NÃO EXECUTADO** | — | 1470cf48bf7d | exige sessão ativa |
| D-23/D-15 — salvar suspenso limpo; sair pelo botão até `closed` | **NÃO EXECUTADO** | — | 1470cf48bf7d | exige sessão ativa; D-23 continua o de maior risco residual do lote |
| D-08 — bloqueio estruturado na sobreposição | **ABERTO** | lado API medido: 409 com `code/impact/nextAction/diagnosticId` (`logs/json/S5-launch*.json`) | 1470cf48bf7d | overlay nunca observada com recusa (sem sessão) |
| D-17 — recusa de lançamento com causa resolúvel | **PARCIAL** | 409 com `diagnosticId` + `nextAction` resolvendo via `core.jsonl` ("launch requires a current game focus") — formato provado numa recusa real da ponte | 1470cf48bf7d | o título NES específico (`c51dbc23e9b3258b761df058`, '89 Dennou Kyuusei Uranai) e a visibilidade na UI não foram executados |
| D-06/D-24 — Herdar AURA sem `E-THEME-NOT-FOUND` | **PARCIAL** | `logs/08`: press rc=0, 0 ocorrências de recusa na árvore pós-clique | 1470cf48bf7d | resolução herdar→AURA não provada por diff de documento (arquivo == baseline `81d313df…`) |
| D-07/D-25 — tema por menu único; recusa não suja | **ABERTO** | `logs/10..15`: combo aberto e AURA destacado; apply falhou `não focado` ×5; um apply/save rc=0 sem persistência | 1470cf48bf7d | nada fechou por documento; R1: herança de aparência ausente é decisão material do operador, não implementada; R2: lock de invariante D-25 pendente |
| D-27/D-28 — runtime spot-check | **NÃO EXECUTADO** | estático provado (censo + gates T6/T7/7b) | 1470cf48bf7d | S-9 opcional não executado |
| D-29 — paletas sustentam texto | **DEMONSTRADO (gate) + fotografia** | gate T8/T9 verde (11 pins, `KNOWN_OPEN_AT_MEASURED={}`); censo pós-instalação `logs/27`: reprovas 43→30 | 1470cf48bf7d | os 30 restantes pertencem aos 2 temas derivados do editor (26) e à classe D-01/aura (4) — fora do contrato do lote; troca de tema pela UI nunca exercitada (ver §3) |

## 2. Incidente registrado desta rodada (não ocultar)

A mão 1 gravou edições de editor na jornada do usuário `4095b915` (documento carregado era o errado).
Restaurada ao baseline `d7c114f9…` via Desfazer+Salvar do produto; verificação por sha256 no takeover
do controlador e re-verificada na mão 2 (`logs/21-delta-final.txt`). Saves 21 == baseline, novos=0;
`active.json` e prefs intactos; resíduo da mão 2: zero. A mão 2 também registrou 1 `Tab` enviado sem
reafirmação de foco (janela ativa era app do operador) e 1 captura `S5-6` removida por conter app de
terceiros (linha órfã no manifest com motivo em `logs/21-s5-rodape.md`).

## 3. Abertos que o lote não alcança (herdados e novos)

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| B-7 retorno com foco/rolagem; B-10 fades; C-4 destravamento pelo produto | ABERTO (não re-executados) | rodada `2026-10-12` README B-7/B-10/C-4; esta rodada não chegou a sessão | 1470cf48bf7d | re-execução física em janela exclusiva com o operador cobriria C-4 via D-23 |
| 22/25 adapters não testados; 12 sistemas sem `game_readiness` jogável | ABERTO | `2026-10-12-.../logs/09` | 1470cf48bf7d | acervo/cores/firmware do host |
| Gamepad/touch do Deck | ABERTO | doctor `deck.input.keys=warn` | 1470cf48bf7d | toda prova é teclado |
| `Esquema de cor`/`Escolher cor` pela UI | ABERTO | capacidades 9 da rodada 2026-10-12 | 1470cf48bf7d | o editor pode produzir combinações piores que as 30 medidas |
| Classe D-01: 28 `DarkButton`, 245 `QQC.Button` crus, 22 arquivos com `background` próprio | ABERTO (fora do escopo) | `2026-10-12-.../logs/19` §Amplitude; censo `27` | 1470cf48bf7d | D-29 trata tokens, não o componente |
| `nsz.install=1` literal; `keys.import` divergente | ABERTO | censo `2026-10-13-lote-coesao-ui/logs` e `2026-10-12-.../logs/08` | 1470cf48bf7d | acervo sem mídia NSZ; item sem clique runtime |
| Ramo `pendingLaunchError` em `LauncherJourney.qml:227-230` | ABERTO | revisão da T12; não exercitado | 1470cf48bf7d | exige lançamento com overlay de erro ativa |
| D-01…D-05 (Studio de Jornadas) e D-09 (18 entradas não lançáveis) | FORA DO ESCOPO | plano §Autorevisão 1 | 1470cf48bf7d | pertencem às frentes Studio/acervo; registrados, não arrastados |
| journal/backup orphans (9+9); `boot.direct` permission warn | ABERTO | doctor em `2026-10-13-lote-coesao-ui/logs/25` | 1470cf48bf7d | resíduo certificado; reparo é decisão do operador |
| semente `dynamicPalette.fallback.darkVibrant:#0e7490` em `org.steamzero.asset-recipes-demo/theme.json:170` fora dos 11 pins e do portão WCAG | DÍVIDA ESTRUTURAL (registrada para o próximo censo não a "redescobrir"; M-17 da revisão final) | `logs/29-revisao-final-do-branch.md` §M-17; ledger T9 | 1470cf48bf7d | o portão valida `tokens.color`, não a semente; validar semente é frente própria |

**Revisão final do branch inteiro (2026-10-15)** — texto integral commitado como
`logs/29-revisao-final-do-branch.md` (veredito APPROVE_WITH_FINDINGS: 0 críticas, 1 importante,
18 menores). Corrigidas neste checkpoint: **I-1** (linhas de cessão (9)–(11) na carta do lote e
contrapartes lavradas nos cartões JLS, JCT e SDH, nomeando os 8 paths com origem, destino, base,
escopo e devolução; frase de completude da carta corrigida para o conjunto registrado);
**M-5** (escrita do teste `test_refused_save_state_declares_exists_when_the_file_landed`
confinada a `tmp_path` por monkeypatch de `paths.saves_dir`); **M-7** (renomeado para
`test_fixed_text_choice_fails_a_theme_while_background_holds` — o nome antigo era literalmente
falso após a D-29); **M-14** (convenção da colisão de índice 21 registrada no README da rodada
2026-10-15); **M-16** (ponteiro inline na linha superada de `logs/03-decisao-d23.md`);
**M-17** (linha acima). Ficam estacionados sem código neste checkpoint: M-1…M-4, M-6,
M-8…M-13, M-15 e M-18 — cada um com adjudicação ou diferimento do ledger citados no próprio
`logs/29`.

**Re-revisão escopada da remediação (2026-10-15)** — um revisor read-only verificou o batch acima
contra os findings: I-1, M-5, M-7, M-14, M-16 e M-17 **ADDRESSED**, sem quebra crítica, sem
asserção enfraquecida e sem colisão de posse no novo `scopePaths`. Quatro residuais de prosa foram
abertos e corrigidos no mesmo checkpoint: a frase de completude contava «as dez» quando a própria
enumeração dá **onze** linhas que nomeiam origem — (1), (2), (3), (4), a série (5) nas suas três
linhas (5a)/(5b)/(5c), (6) e as retrospectivas (9), (10), (11), com (5) como cabeçalho de série e
(7)/(8) sem origem ativa; o handoff novo do cartão JCT estava inserido no meio do bloco (5a) e
duplicava a frase de devolução; M-15 faltava na lista de estacionados acima; e o cartão cedente JLS
citava as unidades endossadas sem a cláusula da ratificação da Tarefa 3, que é o que cobre a
unidade 5 no ledger. Renovaram-se dois `scopeDigest` tornados obsoletos pelas próprias edições de
prosa mais o `render --write`, na árvore congelada e como última edição de conteúdo; nenhum estágio
promovido.

## 4. Estado do host e da entrega

| critério | comportamento observado | evidência | release | limite |
|---|---|---|---|---|
| Instalação governada da candidata do lote | **DEMONSTRADO** | `logs/24` transação completa (token exato, wheelSha256 `155158b4…`, run 38787511945), `logs/25` pós-instalação | 1470cf48bf7d | reboot é do operador |
| `/opt/steamzero/current` | `2.0.0rc1-1470cf48bf7d` — retifica a linha "permanece 2b7eb" do plano (escrita antes da Fase 2; marcar sem apagar) | `host/01-release.txt` desta rodada; `logs/25` | 1470cf48bf7d | — |
| Idempotência | **DEMONSTRADO** | `logs/25` (converge attempts=0, restarted=false) | 1470cf48bf7d | — |
| Rollback | **CERTIFICADO** | `logs/24` (previousRelease `2.0.0rc1-2b7eb541b4a5` disponível) | 1470cf48bf7d | não executado de fato |

## 5. Próxima ação por linha aberta

1. S-5…S-8 restantes (D-12/D-22/D-20/D-21/D-23/D-15/D-08/D-17-específico/D-19): **re-execução física em
   janela de desktop exclusiva**, combinada com o operador (a mão 2 parou por atividade humana —
   proteção, não falha). Harness pronto na rodada; vereditos saem direto para a tabela §1.
2. Revisão final do branch (base `2b7eb541b4a5`) → PR ao repositório `Misael-art/steam-zero`; merge e
   devolução de cessões são do operador.
3. Decisões materiais pendentes do operador: R1 (herança absent-appearance do D-07), R2 (lock D-25),
   reparo dos orphans, unidade de cor dos temas do editor (§1 D-29 linha limite).

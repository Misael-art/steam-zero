# Rodada de prova física — 2026-10-15 — release `2.0.0rc1-1470cf48bf7d`

Bateria §6 do lote de coesão da UI (Tarefas 10–14), executada em duas mãos no desktop real do host.
Mão 1: S-PRE, S-BASE, S-1, S-2, S-3 + incidente de gravação indevida na jornada do usuário (restaurado).
Mão 2 (este relatório): tentativa de S-5…S-9, interrompida na borda por **operador humano ativo no
desktop**, e S-10 completo. Convenções, proteções e matriz no estilo da rodada
`2026-10-12-jornada-fisica-2b7eb541b4a5`.

- Release em toda linha: `2.0.0rc1-1470cf48bf7d` (commit integral `1470cf48bf7df4abdb3876176a7965f81e7c4455`);
  instalação/doctor/idempotência provadas em `../2026-10-13-lote-coesao-ui/logs/24,25` (referenciadas, não repetidas).
- Integralidade: `capturas/manifest.tsv` (data, release, label, sha256, dimensões). Exceção documentada:
  `S5-6-tab-windowfocus.png` removido por conter tela cheia com app de terceiros do operador (dados pessoais);
  a linha do manifest ficou órfã e o motivo está registrado em `logs/21-s5-rodape.md`.
- Vereditos: DEMONSTRADO / PARCIAL / ABERTO / REPROVADO / NÃO EXECUTADO. Aparência nunca prova operação:
  cada linha cita PNG **e** read-model/AT-SPI/event_log quando alega comportamento.

## A — Preparação, host e proteções

| critério | veredito | evidência | limite honesto |
|---|---|---|---|
| Entrega de input focado (harness, rc=3 sem foco) | DEMONSTRADO | `host/00-input.txt`, `capturas/S-PRE-0..3` (147 px + AT-SPI `Cinema` após Tab×2), `scripts/01-prova-input.sh` | provado na janela da mão 1; na mão 2 a entrega ficou contaminada por corrida de foco com o operador humano (ver B-S5) |
| Núcleo convergido na release alvo | DEMONSTRADO | `host/01-release.txt` (state=converged, activatedRelease==daemonRelease==2.0.0rc1-1470cf48bf7d) | instalação governada referenciada de `2026-10-13-lote-coesao-ui/logs/24,25` |
| Baseline de proteção (saves=21, active.json `2a37d09a…`, jornadas `d7c114f9…`/`81d313df…`, prefs `9491ce13…`) | DEMONSTRADO | `logs/00-baseline.txt`, `host/02-baseline-protecao.txt`, cópias em `/tmp/bateria-1470/config-baseline/` | — |

## B — Cenários

| cenário | veredito | evidência | limite honesto |
|---|---|---|---|
| S-1 Central declara conexão com o núcleo | **DEMONSTRADO** | `logs/03-s1-central.md`, `S1-1-central-inicio.png`, `S1-arvore-central.txt` (label "Central desconectada" presente mas SEM VISIBLE/SHOWING; ponte HTTP 200; árvore "Estado da ponte: ● ONLINE" reconfirmado na mão 2) | a tela informa conexão só por omissão (sem rótulo afirmativo) |
| S-2 Studio: "Herdar AURA neste menu" (D-24/D-06) | **PARCIAL** | `logs/08-s2-resultado.md` (press rc=0; **0** ocorrências de E-THEME-NOT-FOUND/"Tema não encontrado" na árvore pós-clique; labels "AURA · escolha explícita"), `logs/09-s2-salvar.md`, capturas S2e-*/S2f-1 | o documento em disco não mudou (`81d313df…` == baseline; appearance `inherit-aura` antes==depois): a resolução herdar→AURA não foi provada por diff de documento; log da mão 1 não fecha veredito |
| S-3 Studio: tema por menu + recusa sem sujeira (D-07/D-25) | **ABERTO** | `logs/10..15` (combo aberto e AURA destacado S3-2/S3-3; "Aplicar ao menu" falha `fail\|nao focado` ×5 em duas tentativas; um apply rc=0 + save rc=0 em `14/15`) | documento final inalterado em disco (`81d313df…` == baseline; genres null) — nada persistiu, nada fechou; linha ABERTO por regra ("log não fecha ⇒ ABERTO") |
| Incidente mão 1: gravação indevida na jornada do usuário `4095b915` + restauração | REGISTRADO+RESTAURADO (verificado) | `logs/16-s3-restauracao.md`, `logs/17-s3-undo-exato.md`, `logs/18-restauracao-4095b915.md`; sha final `d7c114f9…` == baseline, conferido de novo em `logs/21-delta-final.txt` (mão 2) | os logs de undo terminam em `7eddd0aa…` (16:58); o retorno a `d7c114f9…`==baseline foi medido pelo controlador no takeover (~17:05) — o último traço de restauração ficou sem log próprio da mão 1, que morreu no limite de turnos entre esses dois instantes; o controlador não escreveu o arquivo, apenas mediu o hash e fechou as janelas |
| S-5 D-10 rodapé em 1280×801 físico | **PARCIAL** | `logs/21-s5-rodape.md`; `S5-1-rodape-1280x801.png` (1280×801 px; linha de atalhos inteira no rodapé); AT-SPI: nome acessível completo `↑ ↓ navegar · Enter abrir · Esc voltar · Ações de sessão abaixo` (63 chars, sem corte — o "aba" visto antes era o print `name[:60]` do harness); janela lógica 948,15×593,33 @ escala 1,35 (declarado: ≠ 853×534 da rodada anterior) | provado **sem sessão ativa**; o caso decisivo do D-10 (linha completa com as 6 ações de sessão visíveis) nunca foi capturado — exige sessão |
| S-5 D-12/D-22 ações de sessão ao vivo sem "Atualizar" (6 botões `journeySessionEvent_*`) | **NÃO EXECUTADO** | `logs/21-s5-rodape.md` (registro da interrupção) | nenhuma sessão obtida: POST /launch recusa sem foco de jogo na UI; navegação por teclado não completou (operador humano ativo; ver limite abaixo) |
| S-6 D-20/D-21/D-26/D-08 (salvar estado/miniatura/recusa na overlay) | **NÃO EXECUTADO** | — | exige sessão mGBA ativa |
| S-7 D-23/D-15 (pausar/salvar-pausado/retomar/sair pelo botão) | **NÃO EXECUTADO** | — | exige sessão ativa |
| S-8 D-17 no título NES `c51dbc23e9b3258b761df058` | **NÃO EXECUTADO** | id lido de `../2026-10-12-.../logs/json/nes-relancamento.json` + `logs/12` (título '89 Dennou Kyuusei Uranai) | medição adjacente na coluna C (D-17) |
| S-9 D-27/D-28 spot-check | **NÃO EXECUTADO** | — | opcional; sem fôlego após a interrupção |
| S-10 retorno e restauração | **DEMONSTRADO** | `logs/21-delta-final.txt`, `logs/delta-saves-novos.txt` (novos=0, alterados=0, faltando=0), `pgrep qml6`=0, janela fechada por `kdotool windowclose` | resíduo zero certificado por sha256; nenhuma jornada tocada por esta mão |

### Registro operacional da interrupção (mão 2)

Às ~17:14–17:17 a janela ativa do KWin tornou-se `{92786164-…}` = app **ChatGPT** do operador
(2560×1080), roubando a ativação logo após `sz_focus` rc=0; as capturas S5-1..S5-5 saíram
byte-idênticas (janela oculta não re-renderizava; relógio AT-SPI congelado em "17:11"). Teclas
verificadas por `sz_press` (FOCUSED==alvo no envio) produziram 0 px de mudança — a medição de
teclado está **contaminada pela corrida de foco** e não sustenta veredito de produto. A bateria foi
parada na borda seguinte, conforme regra do brief.

## C — Defeitos: resultado físico por correção do lote

| defeito | veredito físico nesta release | evidência | limite |
|---|---|---|---|
| D-06 editor enxerga o pacote AURA | PARCIAL | `logs/08` (0 recusas E-THEME-NOT-FOUND pós-"Herdar AURA") | direção da resolução não provada por documento |
| D-07 tema por menu único | ABERTO | `logs/10..15` (apply/save sem efeito persistido) | cenário não fechou |
| D-08 bloqueio estruturado na sobreposição | ABERTO | lado API medido (409 com code/impact/nextAction/diagnosticId: `logs/json/S5-launch*.json`) | overlay nunca observado com recusa (sem sessão) |
| D-10 linha de atalhos cortada | PARCIAL | `S5-1` + nome AT-SPI completo (63 chars) em 1280×801 físico | sem sessão ativa; as 6 ações não visíveis nesta condição |
| D-12 ações de sessão sem Atualizar | NÃO EXECUTADO | — | sem sessão |
| D-15 sair pelo botão até closed | NÃO EXECUTADO | — | sem sessão |
| D-17 recusa de lançamento com causa | PARCIAL | `logs/json/S5-launch.json`/`S5-launch2.json`: 409 com `diagnosticId` e `nextAction` apontando `core.jsonl`; correlação lida no `core.jsonl` (`launcher.launch.failed`, errorDetail "launch requires a current game focus") | formato provado em recusa da ponte; o caso NES específico e a visibilidade na UI/overlay não foram executados |
| D-19 rótulos reais | ABERTO | labels íntegros na árvore (atalhos 63 chars; "Herdar AURA neste menu"; "Jogar '89…") | rótulos de ações de sessão (Pausar/Retomar) não observados |
| D-20 slot de save-state válido | NÃO EXECUTADO | — | sem sessão |
| D-21 miniatura real do save-state | NÃO EXECUTADO | — | sem sessão |
| D-22 estado vira sem "Atualizar" | NÃO EXECUTADO | — | sem sessão |
| D-23 salvar com sessão suspensa | NÃO EXECUTADO | — | sem sessão |
| D-24 E-THEME-NOT-FOUND no Herdar AURA | PARCIAL | `logs/08` (0 ocorrências) | idem D-06 |
| D-25 recusa não suja documento | ABERTO | `logs/11..15` | caminho de recusa não exercitado até fim |
| D-26 recusa pós-envio declara efeito | NÃO EXECUTADO | — | sem sessão |
| D-27 Verificar ambiente emite requisição | NÃO EXECUTADO | — | S-9 opcional não executado |
| D-28 vocabulário do OSD (só ações com porta) | NÃO EXECUTADO | — | sem sessão |

## D — Capacidades não demonstradas nesta rodada

Ações de sessão ao vivo (D-12/D-19/D-22), salvar/carregar estado com miniatura (D-20/D-21),
recusa estruturada na overlay (D-08), suspensão+salvo limpo e saída pelo botão (D-23/D-15),
diagnóstico D-17 no título NES específico, D-26/D-27/D-28, e o fechamento de S-2/S-3 por documento.

## E — Índice de evidência da mão 2

`scripts/20-lancamento2.sh`, `scripts/21-s5a-rodape.sh`, `scripts/21-s5b-navega-lanca.sh`;
`logs/20-janela2.txt`, `logs/21-s5-rodape.md`, `logs/21-delta-final.txt`, `logs/delta-saves-novos.txt`,
`logs/S5-arvore-botones.txt`, `logs/S5-arvore-sessao.txt`, `logs/19-consolidacao.md`;
`logs/json/S20-modelo-inicial.json`, `logs/json/S5-launch.json`, `logs/json/S5-launch2.json`,
`logs/json/S5-session-running.json`; capturas `S5-1..S5-5` (manifest completo em `capturas/manifest.tsv`).

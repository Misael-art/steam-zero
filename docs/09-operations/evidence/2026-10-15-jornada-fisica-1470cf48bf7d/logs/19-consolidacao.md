# 19-consolidacao — totais e lacunas da rodada (2026-10-15, mão do executor 2)

## Capturas

- `capturas/manifest.tsv`: 53 linhas registradas (S-PRE, S-1, S-2*, S-3*, REST-19 pela mão 1; S5-1..S5-6 pela mão 2).
- Válidas em disco: 52 PNG. **S5-6-tab-windowfocus.png foi REMOVIDO da rodada**: o spectacle capturou a tela
  cheia com o app de terceiros do operador (dados pessoais) em vez da janela SteamZero; a linha do manifest
  ficou órfã por decisão de privacidade (explicado em `logs/21-s5-rodape.md`).
- Novas desta mão: S5-1..S5-5 (5 válidas; S5-1..S5-5 byte-idênticas — janela oculta não re-renderizava, ver
  registro de interrupção) + REST/JSONs abaixo.

## Artefatos desta mão

- `scripts/20-lancamento2.sh`, `scripts/21-s5a-rodape.sh`, `scripts/21-s5b-navega-lanca.sh` (reprodutibilidade).
- `logs/20-janela2.txt` (janela/ponte), `logs/21-s5-rodape.md` (S-5 completo + interrupção),
  `logs/21-delta-final.txt` (S-10), `logs/delta-saves-novos.txt` (zero resíduo),
  `logs/S5-arvore-botones.txt`, `logs/S5-arvore-sessao.txt` (AT-SPI),
  `logs/json/S20-modelo-inicial.json`, `logs/json/S5-launch.json`, `logs/json/S5-launch2.json`,
  `logs/json/S5-session-running.json`.

## O que ficou NÃO EXECUTADO e por quê

| item | motivo |
|---|---|
| S-5 passo 3–4 (6 botões `journeySessionEvent_*`, Pausar/Retomar sem Atualizar — D-12/D-22) | Nenhuma sessão ativa obtida: o lançamento exige foco de jogo na UI e a navegação por teclado não completou antes da interrupção — operador humano ativo no desktop (janela ChatGPT 2560×1080 roubando a ativação; capturas obsoletas). Bateria parada na borda, conforme regra. |
| S-6 (D-20/D-21/D-26/D-08 overlay) | exige sessão mGBA ativa — não obtida. |
| S-7 (D-23/D-15) | exige sessão ativa — não obtida. |
| S-8 (D-17 no título NES `c51dbc23e9b3258b761df058`) | exige navegação+lançamento físicos — interrompido. Medição adjacente: recusas de launch desta mão já trazem `diagnosticId` + `nextAction` resolvendo a causa via `core.jsonl` (ver D-17 no README). |
| S-9 (D-27/D-28) | opcional; sem fôlego após a interrupção. |
| S-2/S-3 fechamento | logs da mão 1 não fecham veredito (regra: linha ABERTO); não refeitos — editor de jornada é a fonte do incidente e está fora do meu escopo. |

## Encerramento

- Launcher desta mão fechado por `kdotool windowclose` (caminho normal). `pgrep -a qml6` = 0; launcher = 0; retroarch = 0.
- Jornadas: 3 hashes == baselines (`2a37d09a…`, `d7c114f9…`, `81d313df…`) — ver `21-delta-final.txt`.
- Saves: 21/21, novos=0, alterados=0, faltando=0 — ver `delta-saves-novos.txt`.
- Preferências: `theme-preference-v1.json` `9491ce13…` == baseline; nada a restaurar.

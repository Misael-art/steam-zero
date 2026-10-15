# S-5 parte A — D-10 rodapé + sessão ativa (2026-10-15T17:11:40-03:00)
## 1. geometria antes
Window {05f2e28a-60a3-4049-a192-1728a036e3a8}
  Position: 0,0
  Geometry: 948.148148148148x593.3333333333333
## resize 1280x801 físico (kdotool windowresize)
Error: in command 'windowresize'

Caused by:
    Unknown command: windowresize
## geometria depois
Window {05f2e28a-60a3-4049-a192-1728a036e3a8}
  Position: 0,0
  Geometry: 948.148148148148x593.3333333333333
## escala do host (plasmactl/kinfo6 se disponível)
## 2. readiness do título (EmulationController.game_readiness, spawn bloqueado)
readiness: {'playable': True, 'code': '', 'reason': ''}
## 3. slots de save mGBA do título (livres: state1..)
total 16
drwxr-x--- 1 misael misael  236 out 12 17:51 .
drwx------ 1 misael misael  102 set 22 08:19 ..
-rw-r--r-- 1 misael misael 6599 out 12 17:51 Castlevania Legends (USA, Europe) (Translated PtBr).state
-rw-r--r-- 1 misael misael 6418 out 12 17:51 Castlevania Legends (USA, Europe) (Translated PtBr).state.png
## 4. lançamento via ponte POST /launch
HTTP 409
json: /home/misael/Projects/Steam Zero/Canonical/2026-09-21/docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/logs/json/S5-launch.json
{
 "error": {
  "code": "LAUNCHER-LAUNCH-FAILED-001",
  "cause": "Não foi possível preparar o lançamento.",
  "impact": "O Launcher não confirmou o início do jogo.",
  "diagnosticId": "01M50K2B2BAVPZ8DZXASDG880B",
  "nextAction": "Consulte o diagnóstico 01M50K2B2BAVPZ8DZXASDG880B em /home/misael/.local/state/steamzero/logs/core.jsonl e tente novamente."
 }
}
## 5. sessão (GET /session stage=running)
HTTP 400
json: /home/misael/Projects/Steam Zero/Canonical/2026-09-21/docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/logs/json/S5-session-running.json
{
 "error": "JOURNEY-STAGE-REFERENCE-MISSING"
}
## 6. processos retroarch/flatpak da sessão
## 7. foco + captura do rodapé
sz_focus rc=0
/home/misael/Projects/Steam Zero/Canonical/2026-09-21/docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/capturas/S5-1-rodape-1280x801.png
## 8. dump AT-SPI (botões + labels da janela do Launcher)
    button|Atualizar|ENABLED,SENSITIVE,VISIBLE,SHOWING,FOCUSABLE
    label|↑ ↓ navegar · Enter abrir · Esc voltar · Ações de sessão aba|ENABLED,SENSITIVE,VISIBLE,SHOWING,FOCUSABLE
fim parte A 2026-10-15T17:11:57-03:00

# S-5 parte B — navegação + lançamento (2026-10-15T17:14:19-03:00)
## B1. entra na plataforma GB via grab+Enter (teclado seta testado depois)

(process:3668473): dbind-WARNING **: 17:14:20.459: AT-SPI: Unable to open bus connection: Failed to connect to socket /run/user/1000/at-spi2-ZKEHX3/socket: No such file or directory
ok|button|Game Boy, Game Boy Color e Game Boy Advance
grab+Enter ok
HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.steamzero.default/None active=True journeyId=org.steamzero.journey-4095b915 events=[{'event': 'select', 'connectionId': 'platforms-genres', 'action': 'navigate', 'label': 'Explorar por gênero'}, {'event': 'route', 'connectionId': 'platforms-years', 'action': 'navigate', 'label': 'Explorar por ano'}] caps={}
  item: {"id": "nes-famicom"}
## B2. teste de setas (evidência D-11/D-19): foco antes/depois de Down×2

(process:3668582): dbind-WARNING **: 17:14:23.466: AT-SPI: Unable to open bus connection: Failed to connect to socket /run/user/1000/at-spi2-ZKEHX3/socket: No such file or directory
foco antes: Jogar '89 Dennou Kyuusei Uranai (Japan)

(process:3668631): dbind-WARNING **: 17:14:24.444: AT-SPI: Unable to open bus connection: Failed to connect to socket /run/user/1000/at-spi2-ZKEHX3/socket: No such file or directory
foco depois de Down×2: Jogar '89 Dennou Kyuusei Uranai (Japan)
HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.steamzero.default/None active=True journeyId=org.steamzero.journey-4095b915 events=[{'event': 'select', 'connectionId': 'platforms-genres', 'action': 'navigate', 'label': 'Explorar por gênero'}, {'event': 'route', 'connectionId': 'platforms-years', 'action': 'navigate', 'label': 'Explorar por ano'}] caps={}
## B3. busca por nome (atalho de navegação) até Castlevania Legends

(process:3668646): dbind-WARNING **: 17:14:24.761: AT-SPI: Unable to open bus connection: Failed to connect to socket /run/user/1000/at-spi2-ZKEHX3/socket: No such file or directory
ok|text|
grab search ok
digitou rc=0
HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.steamzero.default/None active=True journeyId=org.steamzero.journey-4095b915 events=[{'event': 'select', 'connectionId': 'platforms-genres', 'action': 'navigate', 'label': 'Explorar por gênero'}, {'event': 'route', 'connectionId': 'platforms-years', 'action': 'navigate', 'label': 'Explorar por ano'}] caps={}
  item: {"id": "nes-famicom"}
  item: {"id": "nintendo-3ds"}
  item: {"id": "master-system"}
## B4. setas até o item do jogo; registra foco a cada passo
iter 1 focus=None
iter 2 focus=None
iter 3 focus=None
iter 4 focus=None
iter 5 focus=None
iter 6 focus=None
iter 7 focus=None
iter 8 focus=None
focus final=None
HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.steamzero.default/None active=True journeyId=org.steamzero.journey-4095b915 events=[{'event': 'select', 'connectionId': 'platforms-genres', 'action': 'navigate', 'label': 'Explorar por gênero'}, {'event': 'route', 'connectionId': 'platforms-years', 'action': 'navigate', 'label': 'Explorar por ano'}] caps={}
  item: {"id": "nes-famicom"}
  item: {"id": "nintendo-3ds"}
## B5. POST /launch
HTTP 409
json: /home/misael/Projects/Steam Zero/Canonical/2026-09-21/docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/logs/json/S5-launch2.json
{
 "error": {
  "code": "LAUNCHER-LAUNCH-FAILED-001",
  "cause": "Não foi possível preparar o lançamento.",
  "impact": "O Launcher não confirmou o início do jogo.",
  "diagnosticId": "01M50K7JKTPR1Y8Q24VZTTQ156",
  "nextAction": "Consulte o diagnóstico 01M50K7JKTPR1Y8Q24VZTTQ156 em /home/misael/.local/state/steamzero/logs/core.jsonl e tente novamente."
 }
}
## B6. modelo pós-lançamento (estado da sessão + eventos)
HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.steamzero.default/None active=True journeyId=org.steamzero.journey-4095b915 events=[{'event': 'select', 'connectionId': 'platforms-genres', 'action': 'navigate', 'label': 'Explorar por gênero'}, {'event': 'route', 'connectionId': 'platforms-years', 'action': 'navigate', 'label': 'Explorar por ano'}] caps={}
  item: {"id": "nes-famicom"}
  item: {"id": "nintendo-3ds"}
{
 "http": 400,
 "body": {
  "error": "JOURNEY-STAGE-REFERENCE-MISSING"
 }
}
## B7. processos da sessão
## B8. foco launcher + captura rodapé + dump AT-SPI
sz_focus rc=0
/home/misael/Projects/Steam Zero/Canonical/2026-09-21/docs/09-operations/evidence/2026-10-15-jornada-fisica-1470cf48bf7d/capturas/S5-2-rodape-sessao-ativa.png
0
    label|↑ ↓ navegar · Enter abrir · Esc voltar · Ações de sessão aba|ENABLED,SENSITIVE,VISIBLE,SHOWING,FOCUSABLE
fim parte B 2026-10-15T17:14:51-03:00

## INTERROMPIDA — operador humano ativo (2026-10-15T17:19:46-03:00)
- Evidência de uso humano: janela ativa {92786164-2546-4d6b-a37c-af86e2182d51} = 'ChatGPT' (app de terceiros, 2560x1080 em 949,0) roubando a ativação
  logo após sz_focus rc=0; capturas S5-1..S5-5 byte-idênticas (relógio AT-SPI congelado em 'Hora atual 17:11') — janela oculta não re-renderizava.
- Teclas verificadas por sz_press (FOCUSED==alvo, janela ativa conferida no envio): Enter/Espaço no botão 'Game Boy, Game Boy Color e Game Boy Advance' e Tab → 0 px de mudança; navegação de menu NÃO demonstrada nesta mão (medição contaminada pela corrida de foco com o operador; não é veredito D-11/D-19).
- Texto completo da linha de atalhos na árvore AT-SPI (nome acessível, 63 chars, sem corte): '↑ ↓ navegar · Enter abrir · Esc voltar · Ações de sessão abaixo' — corte 'aba' visto antes era o print name[:60] do próprio harness sz_states.py, não do app.
- PNG S5-1 (janela física 1280×801 = lógica 948,15×593,33 @ escala 1,35; declarar: lógico ≠ 853×534 desta vez): linha de atalhos inteira visível no rodapé, sem sessão ativa.
- POST /launch sem foco de jogo na UI → 409 LAUNCHER-LAUNCH-FAILED-001 COM diagnosticId 01M50K2B2BAVPZ8DZXASDG880B/01M50K7JKTPR1Y8Q24VZTTQ156 e nextAction apontando core.jsonl; correlação resolvida no log do núcleo: errorDetail 'launch requires a current game focus' (ValueError, launcher.launch.failed). Formato de diagnóstico D-17 presente na recusa.
- Sessão ativa nunca obtida ⇒ 6 botões journeySessionEvent_*, Pausar/Retomar sem Atualizar (D-12/D-22), S-6, S-7, S-8 (título NES c51dbc23e9b3258b761df058), S-9: NÃO EXECUTADOS. Launcher fechado por kdotool windowclose; S-10 em logs/21-delta-final.txt: zero resíduo, hashes == baseline.
- CORREÇÃO de privacidade: a captura S5-6-tab-windowfocus.png (2560x1080) registrou a tela cheia com o app de terceiros do operador (ChatGPT) em vez da janela alvo; arquivo REMOVIDO da rodada por política (dados pessoais não pertencem à evidência). A linha correspondente em capturas/manifest.tsv foi mantida como auditoria e o sha ali registrado não casa mais com disco — este log explica o motivo.
- Contagem de capturas da rodada após remoção: 53 linhas de manifest (inclui a linha órfã de S5-6).

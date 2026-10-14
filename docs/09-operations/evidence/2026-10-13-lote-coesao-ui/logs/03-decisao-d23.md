D-23/C-4 — decisão de unidade: destravar a árvore que o produto parou
============================================================================
Data: 2026-10-14 · Lote: coesão UI e botões reais (2026-10-13) · Tarefa 3
Rúbrica de defeito: docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/
logs/12-defeitos-registrados.txt:97-107 (D-23)
Linha da matriz: docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/
README.md:61 (C-4 recuperação de sessão presa)
Gate: este lote exige aprovação por unidade de design (AGENTS.md §6 / plano, seção
"Aprovação por unidade de design"). O registro abaixo é a resposta escrita do operador.

A pergunta apresentada
---------------------
A pausa de uma sessão de emulação sinaliza **um** pid (`SessionControlOwner.pid`, líder
do grupo criado com `start_new_session`) e a retomada refaz exatamente o mesmo caminho.
Quando a pausa alcança mais de um grupo — ou quando o líder gravado deixa de verificar —
o `resume` não alcança o que ficou parado. Duas unidades foram apresentadas:

- **3a — retomar o que se parou:** registrar os pids dos grupos supervisionados no
  `suspend` e continuar exatamente esse conjunto no `resume`/`request_exit`, com
  verificação de identidade (`_verify_process_identity`) antes de cada sinal. Escopo: o
  mesmo padrão que `request_exit` já usa neste arquivo (`session_control.py:172-186`).
- **3b — nunca parar o supervisor:** pausar somente a árvore do emulador, deixando o
  supervisor do canal responsivo; o `saveState` deixaria de pendurar.

A medição em que a pergunta se apoia
-----------------------------------
`docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/11-bateria-por-sistema.txt:84-94`:

    Cadeia de processos observada (ps): o SIGSTOP da pausa atingiu a ÁRVORE do flatpak —
    bwrap externo (1419274) em T<s, bwrap interno (1419294) em T< e retroarch (1419302) em T.
    Consequências medidas:
      · kill -TERM em retroarch (17:58:57) não encerrou nada: o processo ficou vivo;
      · kill -KILL (18:00:00) deixou [retroarch] <defunct> Z, pai bwrap parado, sem reap;
      · kill -CONT no bwrap interno (18:01:08): bwrap virou Z, sessão ainda suspended;
      · kill -CONT no bwrap externo (18:02:06): o launcher reaps, closing→closed em <4 s,
        nenhuma janela e nenhum processo retroarch restantes.
    Recuperação, portanto, EXIUG de intervenção manual fora do produto (D-23).
    (transcrição literal do arquivo; a palavra no original é "EXIGIU")

`logs/12-defeitos-registrados.txt:102-105` registra a causa provável do D-23: "a pausa
SIGSTOPa a árvore do flatpak inteira (bwrap externo T<s, bwrap interno T, retroarch T) e
o pedido de save fica pendurado no canal de controle; retomar exige continuar o supervisor
externo, o que o produto nunca faz." `resume` ×3, `exit` ×2 e o "Atualizar" real do
Launcher devolveram o mesmo 409 (logs/json/nes3-resume*.json, nes3-exit*.json).

A escolha do operador (vinculante)
---------------------------------
**3a — retomar o que se parou.** Aprovada pelo operador em 2026-10-14 e registrada no
ledger do lote (`.superpowers/sdd/2026-10-13-HANDOFF-lote-coesao-ui-e-botoes-reais/
progress.md`, ruling da Tarefa 3; Ruling P1 liberou o parâmetro `supervised_pids` do
helper de teste, que estava retido até aqui).

O que 3a aplica
---------------
- `suspend` grava o conjunto **efetivamente parado**: cada líder de grupo supervisionado
  que passa na verificação de identidade, com o `(pgid, sid)` e o start-time do momento da
  pausa (`_StoppedGroup`).
- `resume` e o estágio `SIGCONT` do `request_exit` continuam **exatamente** esse conjunto,
  re-verificando cada pid antes de cada sinal. Start-time ou `(pgid, sid)` diferentes do
  gravado significam outro processo no mesmo pid (reuso de PID) — não é sinalizado, e o
  motivo sai em `_log.warning`, não em silêncio.
- Um grupo que sumiu no meio do caminho não aborta a retomada dos demais. Antes, uma única
  falha de verificação no líder derrubava o sinal inteiro — que é como a árvore medida
  ficou parada depois do `kill -KILL` que deixou o pai zumbi sem reap.
- A semântica de "pausa" para o usuário **não muda**: continuar parado = retomar; nenhum
  estado novo é publicado; `request_exit` continua sem publicar `running`.

A alternativa rejeitada e por quê
--------------------------------
**3b — nunca parar o supervisor: REJEITADA nesta rodada.** Ela muda o que "pausa" significa
para o usuário (o supervisor continua correndo, e a promessa de "jogo congelado" deixa de
valer) e altera o contrato do canal de controle, que hoje vive dentro da árvore suspensa.
Mudança de semântica exige ADR próprio; este lote é rodada de correção dentro das
prioridades já declaradas em `IMPLEMENTATION-PROMPT.md`, não um foro de decisão de produto.
Nenhuma parte de 3b foi implementada.

Limite honesto do que foi entregue
---------------------------------
O conjunto registrado é o que o `suspend` **parou de fato**. A fonte dos pids supervisionados
é a lista que o launcher entrega ao dono da sessão (`SessionControlOwner(supervised_pids=...)`),
e hoje o launcher conhece um único grupo por sessão: o processo que ele cria com
`start_new_session` (`adapters/emulation.py:1854` `_spawn` → `_spawn_detached`, `emulation.py:469-478`),
gravado na linha `game_session(pid, start_ticks)` que `adapters/launcher_session.py:26-53`
observa e verifica. Os `bwrap interno/externo` medidos em `logs/11` não são processos criados
pelo produto — são da árvore do `flatpak run` — e por isso não há registro deles a consumir:
enumerá-los exigiria varrer `/proc` em busca da árvore, o que este lote proíbe. Nenhuma
descoberta nova foi implementada; o mecanismo `_managed_process_groups` (`emulation.py:8781`),
que varre `/proc` por argv exata de payload, continua restrito ao encerramento de fontes
portáteis e não foi usado aqui.

Condição de devolução (o que continua aberto)
---------------------------------------------
- **C-4 NÃO é declarada fechada.** O fechamento físico exige uma sessão presa real no host
  e a re-execução GUI/física não está autorizada nesta rodada (AGENTS.md §1/§9; plano, seção
  "Sem injeção de entrada GUI"). A linha C-4 da matriz permanece **parcial/aberto** com a
  causa corrigida apontada acima.
- A questão de ADR segue aberta: para fechar o caso medido, é preciso decidir **quem registra
  os grupos da árvore do flatpak** — (a) o produto passa a supervisionar cada grupo que cria
  e os registra no dono, (b) uma enumeração de árvore com prova de posse, ou (c) 3b, que muda
  a semântica de pausa. Cada opção é mudança de contrato/semântica e pede ADR + prova física.
- Reversão: reverter o commit `fix(session): retomar a arvore supervisionada que a pausa parou
  (D-23/C-4)` devolve o comportamento anterior; sem `supervised_pids` registrado, o caminho de
  produção é o mesmo de antes, e os três testes novos desaparecem com o commit.

# Studio · Autoria visual de experiências e Jornadas

Entrega iniciada em 2026-11-06 sobre `aff0f65c52ec4d311c7d5961ee125d5ed5a19bb3`
(branch `codex/product-recovery-2026-10-16`). Item de status:
`docs/status/items/studio-visual-authoring.json`. Workstream:
`docs/status/workstreams/studio-visual-authoring-2026-11-06.json`.

## Procedência do design

A referência aprovada pelo proprietário é um protótipo local de revisão
(`build/agent-runs/design-steamzero/studio-experiencia/`: `ESCOPO.md`,
`JORNADA.md`, `index.html` e sete capturas). Esse diretório é material
temporário não versionado; as decisões necessárias à retomada estão
consolidadas aqui. Nenhum asset do protótipo foi copiado para o repositório.
Os testes usam PNGs sintéticos gerados em tempo de execução.

## Decisões e contratos

| Decisão | Motivo | Contrato |
| --- | --- | --- |
| Nova versão `experience-journey-v3`, aditiva sobre v2. Documentos v2 continuam v2 e só migram quando o autor usa natureza, layout, `launchRequest` ou os eventos `complete`/`context-missing`. | v2 tem `additionalProperties: false`; gravar campos novos em v2 quebraria leitores. Migração sob demanda preserva todos os documentos e testes existentes. | `src/steamzero/schemas/experience-journey-v3.schema.json`, `migrate_journey_v2_to_v3`, `uses_v3_features` |
| Instância = menu com `nature` (`free`, `platforms`, `games`, `categories`, `direct-launch`, `transition`, `session`, `recovery`). `NATURE_EVENTS` publica as saídas de cada natureza. | O ID do menu já é a identidade estável; mover, renomear e trocar a natureza preservam o ID. | `NATURE_EVENTS`, operação `set-nature` |
| Troca de natureza não apaga ligações: a saída incompatível fica no documento com `JOURNEY-NATURE-OUTPUT-INCOMPATIBLE` até ser remapeada (`update-connection`) ou removida. | Pedido do aceite: manter a referência disponível. | `_nature_diagnostics` |
| Exclusão com impacto: `removal-impact` lista ligações de entrada/saída; `delete-instance` remove a instância e suas ligações; Desfazer restaura tudo pelo histórico transacional. A entrada não pode ser excluída sem nova entrada. | `remove-menu` existente exige substituto; a autoria visual precisa de excluir-e-desfazer. Ambas convivem. | `JourneyStudioService.removal_impact`, operação `delete-instance` |
| Lançamento pertence ao serviço. `JourneyExecutor.request_operation` registra a intenção (recusa duplicata com `operation-pending`); só `resolve_operation(token, resultado)` com o resultado observado avança para o destino de sucesso, falha ou tempo esgotado. Token antigo devolve `stale-response` e mantém o contexto atual. | Sessão confirmada somente após o resultado do serviço; prevenção de pedido duplicado e de resposta atrasada. | `request_operation`, `resolve_operation` |
| `direct-launch` lê `launchRequest` (`context` ou `fixed`). Sem jogo no contexto, segue a ligação `context-missing` (rota para escolher um jogo). | Entrada que pede lançamento. | `JOURNEY-LAUNCH-REQUEST-MISSING`, `JOURNEY-LAUNCH-CONTEXT-ROUTE`, `JOURNEY-LAUNCH-OUTCOME-MISSING` |
| Validação: ciclo exclusivamente automático continua bloqueado (`JOURNEY-AUTOMATIC-CYCLE`); ciclo com escolha da pessoa é aceito; instância alcançável sem saída gera `JOURNEY-DEAD-END` (aviso); transição sem término roteado gera erro. | Caminho sem saída segura deve aparecer ao autor sem invalidar rascunhos v2 antigos. | `validate_journey` |
| Cena: documento `steamzero-scene-authoring-v1` com mestres por SHA-256, camadas em coordenadas normalizadas do palco 16:9 e receita declarativa (brilho, saturação, preset, enquadramento, ponto focal). | "Renderize, não edite": o master nunca é reescrito; a mesma foto serve a várias camadas com tratamentos diferentes; a composição sobrevive ao redimensionamento da janela. | `src/steamzero/domain/scene_authoring.py` |
| Mídia: o serviço copia o arquivo escolhido uma vez para o armazenamento de mestres do projeto (`$XDG_DATA_HOME/steamzero/scenes/masters/<sha256>`), identifica o tipo pelo cabeçalho (PNG/JPEG/WebP) e reporta `available`, `missing` ou `changed` sem substituir a fonte. | Fonte movida ou removida não quebra o projeto; fonte alterada é detectada pelo hash. | `SceneStudioService`, `resolve_master` |
| Busca e filtro da biblioteca só localizam mestres; o tratamento visual é propriedade da camada. | Separação pedida no design. | `SceneAuthoringSession.library` |
| Bridge: rotas allowlisted `/studio/scene/{create,load,list,import-media,transact,save}` e `/journey/studio/{removal-impact,natures}`; novas operações de Jornada entram em `_JOURNEY_OPERATION_FIELDS`. | Mesmo regime das rotas existentes: chaves exatas, recusa estruturada "nenhuma mudança foi feita". | `desktop_ui.py`, `desktop_contracts.py` |

## Critérios de aceite

Níveis: **M** = modelo/serviço (pytest), **Q** = Qt offscreen pela bridge real,
**L** = Launcher instalado, **H** = hardware. Um nível não promove o outro.

| # | Cenário | Resultado observado | Prova | Pendente |
| --- | --- | --- | --- | --- |
| 1 | Autoria visual: importar foto, soltar, mover, redimensionar pela alça com proporção, Shift-selecionar, alinhar, tratar, redimensionar a janela (1440×900 → 1024×740), desfazer/refazer, salvar, reabrir. | Geometria normalizada idêntica após resize e reabertura; receita preservada; 2 mestres `available` após reabrir; fonte removida continua íntegra pelo armazenamento de mestres; arquivo inválido e falha de escrita preservam o projeto. | M: `tests/unit/test_scene_authoring.py`; Q: `tests/integration/test_studio_scene_authoring_e2e.py` (mouse pelo `qmltestrunner`) | L/H: arraste vindo do gerenciador de arquivos e pasta de rede; aparência em GPU real. Tratamento de cor (saturação/preset) é receita persistida; o canvas Qt atual aplica só enquadramento e escurecimento — o render completo é responsabilidade da Theme Engine. |
| 2 | Lançamento direto: entrada `direct-launch` com jogo do contexto ou fixado. | Sem contexto → rota para escolher jogo; falha e tempo esgotado → recuperação; resposta antiga descartada; segundo pedido durante o primeiro recusado; sessão só após `operation-success`. | M: `test_direct_launch_*` em `tests/unit/test_journey_authoring_v3.py` | L: o `LauncherJourneyRuntime` ainda emite `operationRequest` e não chama `resolve_operation`; ligar o resultado real do serviço de sessão a esse método é a próxima integração. H: lançamento real. |
| 3 | A plataformas → B jogos → C transição → D sessão com bezel. | Seleção leva filtro `platformId` a B; `play` gera pedido; após sucesso observado vai a C; `complete` encaminha a D; bezel `aura-default` publicado no estágio. | M: `test_platform_game_fade_session_and_shared_list_from_two_origins` | L/H: bezel no adapter real e fallback visual instalado. |
| 4 | Ramificação e retorno: A → categorias ou jogos; duas origens para a mesma lista com filtros próprios; retorno da sessão restaura menu, seleção, filtros, foco e rolagem; resposta atrasada preserva o contexto recente. | Restauração exata por histórico; `restore_return_context` com geração antiga recusado sem alterar a seleção atual. | M: `test_return_after_session_restores_selection_filters_focus_and_scroll`, bindings em `test_platform_game_fade_session_*` | L/H: foco e rolagem no Launcher instalado com controle. |
| 5 | Edição e recuperação: Jornada vazia, trocar natureza, remapear saída, excluir destino referenciado e desfazer, ciclo manual válido, ciclo automático bloqueado, salvar/reabrir em perfil isolado, regressão v2, arquivo inválido. | IDs preservados; saída incompatível sinalizada e remapeada; exclusão mostra impacto e Desfazer restaura instância e ligação; ciclo automático impede salvar; v2 permanece v2 até usar recurso v3. Mapa Qt: arrastar cartão emite `set-layout`; "Saída →" + cartão destino emite a ligação. | M: `tests/unit/test_journey_authoring_v3.py`; Q: `test_02_graph_drag_and_link`; regressão: suítes `test_experience_journey*`, `test_journey_studio*`, `test_launcher_journey*` | L/H: percurso no Launcher instalado. |

## Retomada

```bash
git clone https://github.com/<owner>/SteamZero.git "$HOME/Projects/SteamZero"
cd "$HOME/Projects/SteamZero"
git checkout codex/product-recovery-2026-10-16
./bootstrap-dev.sh --apply            # prepara .venv e .steamzero-dev gerenciadas
.venv/bin/python tools/run_tests_isolated.py tests/unit/test_scene_authoring.py tests/unit/test_journey_authoring_v3.py tests/integration/test_studio_scene_authoring_e2e.py -q
```

O teste Qt exige `qmltestrunner` do Qt 6 (`--ui` no bootstrap do Arch/Manjaro).
Próxima ação técnica: ligar o resultado observado pelo serviço de sessão ao
`resolve_operation` no `LauncherJourneyRuntime` e então executar a prova
instalada (critérios 2–4 em nível L).

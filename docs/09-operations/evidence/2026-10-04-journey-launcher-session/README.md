# Jornada, Launcher/Cinema e sessão — 04/10/2026

## Ambiente e alcance

- Checkout: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`.
- Branch: `codex/journey-launcher-session-2026-10-04`, baseada no `main`
  `b12e5f799498b92995a581c941735a21f27ef546`.
- Execução local com fixtures sintéticas/licenciadas; nenhum jogo, save ou
  configuração pessoal foi usado. Sem instalação, publicação ou alteração do
  host nesta etapa.
- Consumidores exercitados: `JourneyRuntime`, ponte loopback autenticada do
  Launcher, endpoint `/cinema`, QML `LauncherJourney`, `LauncherCinema` e
  `SceneEsdeView`.

## Comportamento verificado

- Jornada salva no Studio, exportada, importada como cópia e ativada pelo
  `JourneyStore`; o entry point isolado também carrega a cópia ativa real do
  XDG sintético.
- Quatro menus, navegação por plataforma/gênero/ano, faceta pública adicional
  `developer`, destino compartilhado e retorno contextual com filtros/seleção.
- Layout nomeado da Jornada e cena XML ES-DE compilada pelo compilador/blob
  store existentes. O entry point publica a mesma cena no Launcher e em
  `/cinema`; o harness QML confirma que `SceneEsdeView` desenha o elemento.
- `requestId` duplicado com ação diferente é recusado sem mutar a sessão. Saída
  exige confirmação; pedidos repetidos enquanto `closing` não reenviam sinal, e
  a sessão permanece pendente até `closed` ser observado.
- O modo `--isolated-library --isolated-root` usa catálogo sintético e desliga
  acesso ao catálogo Steam, acessibilidade do host, sessão e lançamento.

## Verificação focada

Comando:

```text
rtk .venv/bin/python -m pytest tests/integration/test_launcher_app.py tests/integration/test_launcher_journey_e2e.py tests/integration/test_launcher_session_overlay_trigger.py tests/integration/test_launcher_return_cycle.py tests/integration/test_launcher_session_composition.py tests/integration/test_scene_esde_view.py tests/integration/test_experience_journey_bridge_e2e.py tests/integration/test_theme_scene_runtime_e2e.py 'tests/integration/test_qml_handheld_offscreen.py::test_qml_handheld_harness_offscreen[launcher/check_launcher_session_osd.qml]' tests/unit/test_launcher_journey_runtime.py tests/unit/test_experience_journey.py tests/unit/test_journey_studio.py tests/unit/test_session_control.py tests/unit/test_session_overlay.py tests/unit/test_session_overlay_adapter.py tests/unit/test_session_peripherals.py tests/unit/test_scene_surfaces.py tests/unit/test_theme_editor_extends.py tests/unit/test_themes.py -q
```

Resultado: `207 passed in 24.59s`. A cena XML também passou isoladamente em
`5 passed`; essa repetição foi feita depois de acrescentar cobertura do entry
point isolado e da faceta `developer`.

Após tornar a saída idempotente durante `closing`, foi executado:

```text
rtk .venv/bin/python -m pytest tests/unit/test_session_control.py tests/unit/test_session_overlay_adapter.py -q
```

Resultado: `16 passed in 1.20s`; Ruff check e format passaram nos dois arquivos
alterados.

## Suíte integral e correções posteriores

Única execução integral desta árvore antes das correções abaixo:

```text
rtk proxy .venv/bin/python tools/run_tests_isolated.py tests -q
```

Resultado exato: `5 failed, 6634 passed, 47 skipped in 2494.35s (0:41:34)`.
O log completo está em [full-tests.log](full-tests.log). O guard do estado real
registrou o mesmo antes/depois: `files=12818`, `directories=2068`,
`bytes=1372874354`, `max_mtime_ns=1791129499230539182`,
`source=HOME-default`. Esse retrato vermelho não foi reescrito como aprovação.
O checkpoint histórico `6614 passed, 47 skipped` continua distinto.

As cinco causas observadas no integral foram: lista de capas QVariant tratada
como array JavaScript no Cinema; escrita direta fora de `core.fs`; matriz de
capabilities uma ação atrás; teste do catálogo/status com digests envelhecidos;
e teste do grafo Studio preso ao nome pré-herança de um componente. Depois do
integral, as quatro causas funcionais/matriz foram corrigidas e reproduzidas em
baterias focadas. Os digests e views foram renovados e `tests/unit/test_project_status.py`
passou com `13 passed em 6.47s`; o gate final `make status-check` ainda será
executado uma vez. Não houve segunda suíte integral.

Reproduções após as correções:

- `tests/integration/test_launcher_focus_bootstrap.py::test_the_first_key_after_opening_navigates_without_a_pointer` — `1 passed`; cobre as quatro dimensões de viewport e o bootstrap real sem ponteiro.
- `tests/integration/test_launcher_app.py` — `31 passed`; inclui o modo XDG isolado.
- `tests/unit/test_boundaries_lint.py::test_production_source_is_clean` — `1 passed`.
- `tests/unit/test_studio_graph.py` — `12 passed`; seleciona o binding pelo id de componente resolvido e confirma o valor `0.4`.
- `tests/unit/test_capability_matrix.py` — `7 passed`; a matriz gerada declara 153 ações publicadas.
- `tests/unit/test_project_status.py` — `13 passed` após atualizar digests e renderizar as views.
- O preflight `mypy src` apontou 15 erros de inferência/anotação em dois arquivos; a variável local que sombreava o resultado tipado foi renomeada e os clones JSON receberam casts explícitos. `mypy` focado nesses dois módulos passou e `tests/unit/test_launcher_journey_runtime.py tests/integration/test_launcher_app.py tests/unit/test_session_overlay_adapter.py` passou com `48 passed em 11.18s`.

Essas reproduções não substituem a execução integral que permaneceu vermelha,
nem demonstram pixels, input físico, gameplay, duração, FPS ou comportamento
numa release instalada.

## Limites preservados

- Isto não é prova de pixels, input físico, gameplay, duração, FPS ou
  comportamento numa release instalada.
- O perfil apoiado para periféricos é RetroArch Flatpak. Ele aplica o bezel AURA
  gerenciado. A fonte pública declarativa de bezel não oferece ainda uma
  operação de escolha/aplicação de bezel personalizado; adapters sem capability
  continuam indisponíveis.
- Requerem candidata instalada e janela/input/captura seguros: Studio e
  seletor nativo, navegação física, ciclo jogo/pausa/save/load/saída/retorno,
  viewports 949×593 e 1280×800, contraste medido e diagnóstico de desempenho.
- A única execução integral desta revisão está registrada vermelha e não será
  repetida localmente. Ruff check/format, mypy, `independence/boundaries`,
  `status-check`, PR/CI e integração ainda são etapas deste workstream; não
  inferir aprovação integral a partir dos testes focados.

# 06 — Tarefa 10 (Ruling P13): herda AURA resolve o AURA empacotado

Correção implementada conforme a Ruling P13: apenas o ramo `inherit-aura` de
`resolve_theme_coverage` (`src/steamzero/domain/experience_journey.py:1604`)
passa a definir `source_id = "org.steamzero.aura"` (mantendo
`source_version = aura_version`). `not-customized` e `missing-reference`
permanecem em `org.steamzero.default`. Nenhum arquivo QML foi tocado;
`themes.py` não foi tocado; `desktop_ui.py` não foi tocado (ver §3).

## 1. `summarize_theme_coverage` — NÃO alterado; semântica observou deslocamento

`summarize_theme_coverage` (:1665) continua filtrando
`sourceThemeId == "org.steamzero.default"` para compor
`auraEffectiveStages`/`auraEffectiveCount`. Após a correção, etapas com
escolha explícita de herdar AURA deixam de contar ali:

- No documento do teste unitário, `auraEffectiveCount` caiu de 5 para 4
  (re-pinned com comentário no teste — não silenciosamente);
  `requiresPreApplyConfirmation` permanece `True` porque ainda há etapas
  resolvidas para default (herança implícita e fallbacks).
- Caso extremo agora alterado: um documento cujas etapas usadas sejam TODAS
  `inherit-aura` explícitos passa a ter `auraEffectiveStages` vazio ⇒
  `requiresPreApplyConfirmation == False` e o rótulo
  "Tema personalizado em todas as etapas usadas", que é enganoso (nada ali é
  personalizado — tudo é AURA). Antes da correção esse caso produzia
  "Tema misto · AURA efetivo em N etapas". Nenhum teste cobre esse extremo
  hoje. Encaminho para discussão em T14/T15; não mudei o resumo.

## 2. Evidência D-06 (numérica)

- RED (antes do fix): `test_inherit_aura_coverage_resolves_to_the_packaged_aura_theme`
  falhou com `assert 'org.steamzero.default' == 'org.steamzero.aura'`;
  o `assert all(...)` antigo em `test_experience_journey.py:709` também
  falhou após ser reescrito por razão (`explicit-choice` ⇒ aura; demais ⇒
  default), confirmando que travava o comportamento bugado.
- GREEN após o fix: 27 passed em `tests/unit/test_experience_journey.py`,
  6 passed em `tests/integration/test_experience_journey_bridge_e2e.py`
  (linhas 351 e 557 mantidas, como exige a ruling).

## 3. `desktop_ui.py:1547` — não editado; gap latente registrado

A fix resolver-only não quebrou nenhum teste (e2e verde). Porém, por leitura
de código: se `engine-preview` for pedido para um MENU com
`appearance.mode == "inherit-aura"`, a cobertura agora reporta
`org.steamzero.aura`, e `loaded_by_theme` (:1609) só contém
`org.steamzero.default` + o tema custom declarado ⇒
`E-COMPONENT-DEGRADED: Theme Engine não abriu o tema resolvido`
(:1611-1614). Nenhum teste atual exercita esse caminho
(`check_experience_journey.qml:490` envia o payload, mas o harness QML stubba
a resposta). Conformemente à ruling ("prefer resolver-only; editar
desktop_ui apenas se um teste provar a necessidade"), deixei intacto e
registro aqui para o revisor/controller — provavelmente pertence à Tarefa 11
(tema por menu, D-07/D-25), que mexe nesse mesmo trecho de prévia.

## 4. D-24 — trava de catálogo já passava no BASE

`test_packaged_builtin_aura_is_visible_to_the_editor_without_a_host_copy`
passa contra `4f473136` sem nenhuma mudança de código (como a sonda read-only
da ruling previu). Mantida como regressão não-vácuoa: verifica diretório de
temas do usuário vazio, `origin == "builtin"`, `compatible is True`,
`state == "available"` via `theme_list()` e a paleta real `#0b1020` via
`editor_load` — provando visibilidade sem cópia em
`~/.local/share/steamzero/themes`.

## 5. Falha pré-existente fora de escopo

`tests/unit/test_project_status.py::test_committed_catalog_and_generated_views_are_consistent`
falha no BASE limpo (42 itens de status com digest obsoleto; verificado com
`git stash`). Regeneração de views pertence ao checkpoint da Tarefa 14.

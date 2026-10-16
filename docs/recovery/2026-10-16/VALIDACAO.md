# Validação da recuperação documental

Escopo: diagnóstico, direção normativa, plano e handoff de 2026-10-16. Nenhum arquivo de runtime foi alterado.

## Verificações

| Verificação | Resultado e limite |
|---|---|
| Base Git | `6475947c189f2d903b83f7f242a2c5ca535fb14c`, árvore inicialmente limpa; descende do `origin/main` local `2b7eb541`; sem fetch remoto |
| Histórico citado | 32 referências de commit do diagnóstico resolvidas com `git cat-file -e <sha>^{commit}` |
| Snapshot | 97 itens preexistentes e 64 manifestos; contagens declaradas, sem promoção ou recertificação |
| Importadores e projeções | 38 passed, 1 skipped em 2,88 s; runner isolado encerrou 0; state home sem diferença observada |
| Governança documental | 13 passed em 5,47 s após regeneração; log em `status-tests.log`; primeira execução capturou digests/views ainda não regenerados |
| Host | `readlink /opt/steamzero/current` apontou `releases/2.0.0rc1-1470cf48bf7d`; diretório da release anterior `2.0.0rc1-2b7eb541b4a5` existe |

Comando da bateria focal:

```bash
rtk proxy .venv/bin/python tools/run_tests_isolated.py tests/unit/test_theme_import_to_runtime_journey.py tests/unit/test_theme_import_retrofe.py tests/unit/test_theme_import_esde_layout.py tests/integration/test_metadata_to_catalog_pipeline.py tests/integration/test_emulation_platform_scope.py -q
```

O skip é de pesquisa `reference/` não versionada. O import de `steamzero` com `PYTHONPATH=src` foi conferido e resolve para este checkout; pytest configura `pythonpath` em `pyproject.toml`. Um caminho histórico exibido pelo skip não foi usado para inferir outra árvore testada.

## Integridade e limites

A primeira execução de `tests/unit/test_project_status.py` resultou em 1 failed e 12 passed por digests/views ainda obsoletos após editar `AGENTS.md`; preservada em `status-tests-initial.log`. O fechamento regenera somente os digests afetados pela documentação, mantendo os cinco eixos funcionais dos itens antigos. Isso não recertifica os contratos de runtime abrangidos pelos escopos antigos.

A suíte integral funcional não foi repetida: o lote muda documentação e governança, sem alteração de código, build ou release. A bateria focal informa o diagnóstico; os checks documentais validam a entrega. Nenhuma nova captura, medição de FPS, interação física com jogos, instalação ou rollback foi executada. Os limites físicos citados vêm da evidência histórica identificada no diagnóstico.

Fontes externas consultadas para não equiparar formatos incompatíveis: documentação primária de [BigBox](https://feedback.launchbox-app.com/en/help/articles/0780913-getting-started) e [CSS Loader](https://docs.deckthemes.com/CSSLoader/Features/). ES-DE e RetroFE foram avaliados principalmente pelos compiladores, testes e estudos já presentes no repositório; a página RetroFE retornou erro e não fundamenta alegação nova de compatibilidade.

Fechamento: links locais e os 32 commits citados conferidos; contagens do snapshot reconciliadas; cinco eixos dos itens preexistentes preservados. `make status-check` e `git diff --check` são os gates documentais finais, registrados no item.

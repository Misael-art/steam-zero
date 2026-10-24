# R2 — precedência do ano canônico sobre alias legado

Assunção serial prospectiva em 2026-10-24 sobre b59651dbc92152d6cf06a4918a4662c8a5835066, mesma branch/checkout/executor. R3 tem código, testes e checkpoint fechados e PR #266 em CI; nenhuma edição R3 em paralelo.

Escopo já reivindicado por R2: src/steamzero/launcher/app.py (shared de integração, cedido prospectivamente em 23/10), tests/integration/test_launcher_metadata_projection.py e este diretório, filho da evidência exclusiva R2. Nenhum handoff novo necessário; app.py não foi devolvido ao owner anterior.

Baseline de leitura: public_game_record prioriza record.year sobre releaseDate. app.py sobrepõe releaseDate canônico mas conserva year antigo. Reproduzir com ano legado conflitante no entrypoint real; preservar o fallback legado quando não há data persistida. Corrigir somente na projeção Launcher, sem alterar contratos globais/identidade/cache persistido. Depois focados e gates integrais da fonte congelada. Não instalar nem iniciar autenticação durante ausência.

Controle negativo corrigido: **1 failed, 1 passed**, assert 1999 != 1985 no read model real publicado pelo entrypoint; sem data canônica o fallback 1999 já passa. A primeira sonda tentou ler year no resultado de busca (campo não publicado ali) e falhou com KeyError nos dois casos; log 00 preservado como sonda inválida, não como reprodução do bug.

Correção de projeção: remove apenas o alias year na cópia em memória quando há releaseDate persistido, deixando project_game_row derivar o ano. Não edita cache, GameRecord, política de fusão, contratos globais ou paths de runtime. Busca continua publicando releaseDate; o bug reproduzido é no ano da Jornada. Regressoes focadas **65 passed** duas vezes; última reestruturação só tornou o tipo Mapping explícito para mypy, e será coberta na integral. Ruff src/tests/tools (721 arquivos) e mypy 306 fontes verdes. Uma tentativa de Ruff em `.` incluiu scripts históricos fora do gate do Makefile; nenhum desses scripts foi alterado.

Próxima operação: integral isolada da fonte congelada, log /tmp/steamzero-r2-year-full.log, cobertura /tmp/steamzero-r2-year-coverage.json. Aguardar resultado terminal antes de commit. Sem testes/GUI reais concorrentes ou autenticação.

Integral terminal **exit 0, 6849 passed, 47 skipped, 19 warnings**, 2355,17 s; cobertura **85,51151888176248%**, estado real sem delta. 1262 hashes sem mudança; recibo 06. Commit funcional `7d89ab0fce0486fabb51560a87ee7d1fde7fe890`. Em 24/10 o operador está presente e pediu instalação imediata da mais recente main com CI verde; esta correção local fica preservada, ainda fora da candidata main 59ecc2d8 até CI remoto próprio. Não reiniciar integral por docs.

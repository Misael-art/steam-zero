# RetroArch Flatpak: raiz de save normal

Data: 2026-10-07  
Release observada: `2.0.0rc1-213124ed513b`  
Origem: configuração do RetroArch Flatpak e módulo `steamzero.adapters.preservation` da release ativa, ambos lidos sem mutação.

## Baseline

- A configuração efetiva do usuário declara um `savefile_directory` absoluto sob o armazenamento privado do Flatpak; o diretório existe e é gravável.
- O módulo de preservação instalado consulta uma raiz diferente para saves RetroArch. A comparação ocorreu em memória e nenhum caminho de jogo, título, ID ou valor da configuração foi registrado.
- O perfil de sessão injeta `savestate_directory` apontando para a raiz SteamZero. Embora o argv por sessão não tenha uma flag filesystem dedicada, o readback efetivo das permissões do Flatpak inclui `host`; portanto, não há evidência estática de bloqueio de acesso. A leitura/escrita real pelo emulador ainda não foi exercitada.
- Nenhum jogo foi iniciado, save escrito, save-state criado, arquivo de configuração alterado ou cópia feita.

## Escopo desta correção

Descobrir e validar a raiz configurada para saves normais do RetroArch Flatpak, mantendo a recusa a symlinks e marcando destinos duplicados como ambíguos. A configuração do usuário permanece read-only.

O caminho de save-state da sessão é um problema separado e continua sem comprovação física. A implementação nessa superfície aguarda handoff serial do workstream Jornada, que detém `session_peripherals.py` e seus testes.

## Correção de branch

`preservation.py` agora lê o `savefile_directory` da configuração privada do RetroArch Flatpak e inclui apenas destinos absolutos resolvidos dentro do perfil Flatpak. Mantém a raiz nativa como candidata independente; caso o mesmo arquivo exista nas duas, a resposta continua ambígua. Configuração que tente apontar para fora do perfil Flatpak não é aceita.

Validação: `tests/integration/test_preservation.py` passou integralmente (15 testes), incluindo regressões para destino Flatpak configurado, caminho externo, configuração symlinkada, diretório de save symlinkado, valor relativo, declarações conflitantes e duplicidade ambígua. Mypy focado, Ruff check, Ruff format e `git diff --check` passaram nos arquivos alterados. O runner isolado reportou o state home real idêntico antes/depois. O patch permanece somente na branch; a release instalada não foi modificada e nenhum jogo foi iniciado.

## Readback do host com o código da branch

O adaptador da branch foi importado com origem verificada no checkout e executou apenas a descoberta de raízes. Retornou duas candidatas, incluiu a raiz declarada pela configuração real do RetroArch Flatpak e manteve a raiz nativa como candidata. Nenhum arquivo de save foi enumerado ou lido; não houve escrita. Isso confirma a correspondência de configuração→candidate root no host atual, mas não promove a implementação à release instalada.

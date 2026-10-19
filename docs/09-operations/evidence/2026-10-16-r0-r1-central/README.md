# R0/R1 — Central, requisitos e contexto

Execução serial iniciada em 2026-10-16, exclusivamente no checkout canônico,
branch `codex/product-recovery-2026-10-16`, base `a672c35a7b6e2794041941ff9617ac5cbc5f7266`.
Um executor: codex-central-executor. R2 não foi iniciado.

## Autorização e procedência

O proprietário autorizou implementação, preparação de artefatos, instalação e
interação de UI no programa, pelo prompt centralizado. Não autorizou push,
merge, publicação pública ou mudança de proteção remota. `git ls-remote` confirmou
`main` em `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7` nesta sessão. Há um único
worktree registrado e a árvore estava limpa na assunção. As frentes fechadas de
contexto/requisitos foram consultadas; a cessão prospectiva de `emulation.py`
consta no workstream cedente de biblioteca e no deste lote. Não se editou o teste
QML Python reivindicado por biblioteca nem o teste unitário reivindicado por JLS.

## Baseline e causa

Manifestos: `03-nes-famicom.platform.json` não exige Keys/Firmware/BIOS;
`21-amiga.platform.json` usa RetroArch/puae e exige `kick34005.A500` e
`kick40068.A1200`. Switch e PS3 entram como regressão dos requisitos declarados.

`01-baseline-tests.log`: 4 falhas, 6 passes. A UI fabricava health-keys e
health-firmware e ações de gestão sem declaração; não mostrava BIOS. O composer
sondava duas vezes e transformava exceção em ausência. Sem probe, BIOS
`unverified` convivia com `launchable=true`. Jogos não-Switch eram publicados
crus, sem Play e readback da preferência; seus escopos ficavam desabilitados.
O seletor de emulador da UI fabricava uma escrita global. A escolha por jogo de
RetroArch também passava pelo writer de INIs/keys/firmware do Switch.

O contrato foi corrigido: desconhecido permanece desconhecido, com preflight
pendente. O teste antigo que esperava launchable sem leitura foi atualizado para
esse contrato, e o teste de fallback PSX agora injeta explicitamente a presença
de BIOS. A igualdade com linha crua no teste de isolamento foi substituída por
preservação de TODOS os campos canônicos mais a nova ação bloqueada; a exclusão
de jogos NES do pipeline e do conteúdo Switch permanece obrigatória.

## Resultado de código

A visão geral consome requisitos declarados e ações publicadas, incluindo BIOS;
sem requisito não cria cartão, sem porta não cria importação. Falha de leitura de
BIOS não prova ausência. A mesma leitura alimenta emulador e resumo. Jogos
não-Switch recebem readback da preferência e Play pelo preflight comum; os
escopos Emulador/Por jogo podem ser navegados. As ações reais de abrir/manter
são reutilizadas do lifecycle, conservando core e identidade da plataforma. O
rótulo Keys pendentes só existe quando o adapter publica esse requisito. Seleção por jogo recusa adapter sem
perfil para a plataforma e não toca configurações de outro runtime. Navegação de
emulador despacha preferência somente quando o serviço publica essa ação.

Não foi criado formulário genérico de parâmetros de RetroArch sem writer e
readback. O ajuste utilizável deste slice é a escolha persistente de emulador por
jogo, com plano/confirmação; configurações de vídeo/timing continuam com os
limites do adapter. O inventário C0 está em `INVENTARIO-C0.md`.

## Testes e limites

`02-focused-tests.log` é tentativa INVALIDADA: executei inspect de host durante a
janela do runner; comandos externos instalados alteraram o estado observado. Não
é evidência verde e não foi tratada como vazamento resolvido por ignorar o gate.
A tentativa `03-focused-tests.log` detectou a mudança de contrato na linha crua.
`04-focused-tests.log`: 69 passed, 61 deselected; estado real sem delta.
`05-controller-tests.log`: 178 passed, sem delta no estado real.
`06-journey-tests.log`: 6 passed, 61 deselected, sem delta; inclui o harness QML
com retorno e seleção e persistência real em XDG temporário.
As fixtures de persistência são arquivos sintéticos em homes XDG temporários,
com SecretStore de sessão, sem spawn de jogo nem escrita em configuração real.
A recuperação de erro/readback é automatizada; isso não certifica gameplay.

## Host e checkpoint ainda aberto

Inspeção governada read-only confirmou release ativa
`2.0.0rc1-1470cf48bf7d`, fonte
`1470cf48bf7df4abdb3876176a7965f81e7c4455`, CLI e daemon convergentes,
units de usuário ativas. Doctor degradado por avisos preexistentes (backups e
journals órfãos, input Deck e permissão de boot); nada foi removido ou reparado.
Nenhuma instalação, rollback, reboot ou jogo iniciado por este lote.

A release ativa não contém esta correção. Bundle/candidata ainda não preparado;
rollback proposto é a release atualmente ativa, a validar pelo controlador e
instalador antes de ativar outra. A existência da release anterior sozinha não é
prova de rollback. Compatibilidade de schema e ownership ainda terão preflight
sobre a candidata exata. Credenciais GitHub disponíveis; senha de instalação não
foi solicitada nem testada. Nenhum segredo foi persistido nesta evidência.

`PENDENTE_INTEGRACAO_REMOTA`: após gates e commits, pedir somente autorização
para push da branch existente e integração governada em main. O controlador
`tools/release_host.py::prepare` exige HEAD igual ao tip remoto exato e CI push
verde do mesmo SHA; não fazer build local para contornar isso. Retomar com
`rtk proxy env PYTHONPATH=src .venv/bin/python tools/release_host.py prepare
--commit <SHA-main-completo> --output /tmp/steamzero-r0-r1-bundle`, somente após a
integração autorizada e CI terminal verde. Usar tokens exatos para install; a
autorização de instalação já existe e não precisa ser pedida outra vez.

`PENDENTE_JANELA_DE_TESTE`: listagem read-only encontrou desktop ocupado por
aplicações do operador e nenhuma janela SteamZero dedicada. Não injetei entrada.
Após release governada, garantir janela/sessão dedicada e perfil de teste antes
de interagir; validar desktop e 1280×800 com versão visível, sucesso, erro e
retorno, persistência após reinício e PNGs ordenados. Nenhum PNG funcional real
novo existe ainda; offscreen não foi promovido a prova física. Viewport não prova
controle/toque em Deck real. Corpus de jogos/BIOS próprios e dispositivos para a
prova física ainda devem ser identificados sem registrar conteúdo privado.

Se autenticação/instalação pedir senha, registrar `PENDENTE_CREDENCIAL` com SHA,
bundle, release, comando sem segredo e retomada; operador fornece somente no
terminal/diálogo. O lote permanece aberto até concluir a prova aplicável. Não
iniciar R2, outra branch, clone ou worktree.

## Tentativas adicionais do checkpoint

`07-integral-tests.log`: suíte interrompida para corrigir a publicação das ações
de lifecycle e o rótulo Keys no emulador. SIGINT/SIGTERM não encerraram o processo
pytest; foi necessário SIGKILL somente no PID filho identificado, e o runner
encerrou 247. Estado real sem delta e nenhum runner/pytest residual observado.
Não é gate aprovado. `08-integral-gates.log` aprovou lint, format, tipos e
fronteiras da versão anterior; status passou após regenerar COVERAGE.
`09-lifecycle-journey-tests.log` detectou somente core incorreto na nova asserção
(mesen no manifesto, não fceumm); asserção corrigida para o manifesto vigente.
A versão final usa `10-final-focused-tests.log`, `11-integral-final-tests.log` e
`12-integral-final-gates.log`. A suíte final inclui cobertura e nomes de teste
para tornar identificável qualquer nova parada; não enfraquece nem pula gates.

Integração preexistente: [PR #258](https://github.com/Misael-art/steam-zero/pull/258)
continua OPEN no SHA `6475947c189f2d903b83f7f242a2c5ca535fb14c`. Antes deste lote,
a branch atual já tinha 49 commits além de main e descende desse PR. Nenhum PR
existe para a branch atual. A autorização remota precisa abranger a base pendente
e a recuperação, preservando commits e proteções. Não foi criado PR duplicado
nem alterado o PR existente.

Consulta remota read-only do PR #258: `mergeable=MERGEABLE`,
`mergeStateStatus=UNSTABLE`. Run mais recente `38819667333` tem falha em
`test_launcher_journey_e2e.py::test_launcher_journey_qml_accepts_keyboard_facets_theme_and_stale_recovery`
(`check_launcher_journey.qml:312`, abertura de galeria por gesto; Qt 6.11.2).
O run anterior `38813046937` era verde. A mesma asserção passou na suíte local
final desta sessão; não é reprodução do erro remoto nem autorização para ignorar
esse check. É necessário novo CI terminal verde para o SHA integrado; não foi
reexecutado workflow remoto, alterado check ou corrigido Launcher fora do lote.

## Checkpoint de 2026-10-17 e reparo de fixture

Suíte integral final: **6807 passed, 47 skipped, 1 failed**, 2482,30 s;
cobertura **85,47%**, acima do gate de 85%; estado real sem delta. Única falha:
`test_game_emulator_set_accepts_sony_nintendo` usava uma ROM Switch para exigir
seleção de Dolphin/PPSSPP/melonDS/Azahar. O novo contrato corretamente recusa essa
preferência incompatível. Não foi flexibilizado o guard de produção.

O teste foi refeito com quatro sistemas declarados e writer/readback reais no
XDG isolado, mais quatro recusas explícitas no Switch. Registro de assunção do
path sem proprietário ativo: workstream R0/R1. `13-platform-selection-contract.log`:
**35 passed**, sem delta, incluindo a matriz Sony/Nintendo e R0/R1. O novo teste
não depende do scanner para provar preferência; a identidade canônica é porta
injetada e a persistência continua real. A mudança de contrato está no docstring
e será descrita no commit. Produção e os oito arquivos da fotografia anterior
permaneceram byte a byte iguais após a integral; ver `TEST-CONTRACT-REPAIR.json`.

Não há alegação de que `11-integral-final-tests.log` tenha encerrado verde.
Revalidação não visual do CI: `15-nonvisual-checkpoint.log`. As provas visuais
passaram na integral sobre os mesmos bytes de produção; não serão repetidas
por uma correção exclusiva de fixture não visual. Não se pulou teste falho nem
se removeu sua exigência: o conjunto corrigido acrescenta sete casos líquidos.

Preflight independente read-only: `14-host-rollback-preflight.json` verificou
integridade de artefatos, entrypoints, ownership root, smoke isolado e ownership
dos destinos de ativação para **2.0.0rc1-1470cf48bf7d**, proposta de rollback da
próxima candidata. Ativação de rollback NÃO foi executada. Dados e schema de
preferências por jogo permanecem no contrato existente; compatibilidade final
será revalidada pelo controlador sobre o bundle futuro. A senha não foi pedida.

## Resultado final do checkpoint local

`15-nonvisual-checkpoint.log`: **6421 passed, 47 skipped, 394 deselected**, runner
0, 924,04 s e estado real sem delta. Os **394 visuais** passaram na integral
sobre bytes idênticos de produção/QML/harness. Assim o conjunto final comprova
**6815 passes e 47 skips** em duas execuções complementares; não se reescreveu o
resultado de uma execução como se tivesse sido outra. Cobertura medida na
integral: **85,47%**; a correção posterior foi exclusiva de fixture não visual.
Lint/format integrais, mypy (303 fontes), independence, boundaries e status
passaram; lint/format da fixture corrigida e o status foram revalidados.

Artefatos de release ainda não existem para este lote. Nenhuma instalação,
ativação, rollback ou reboot foi executado. Somente verificações read-only da
release antiga e smoke em XDG temporário. Não existe PNG funcional novo nem
homologação de gameplay/dispositivo. O roteiro aplicável está em
`ACEITE-INSTALADO.md`; R2 continua aguardando o fechamento físico de R0/R1.

## Commits funcionais e retomada

| Item | Commit | Prova | Release/prova física |
|---|---|---|---|
| R0/R1 serviços, BIOS e preferência por jogo | `af8c0ad7be5862a8b0fef7b28a1105d9646547fc` | 15-nonvisual-checkpoint.log e 13-platform-selection-contract.log | Candidata não instalada |
| R0/R1 integração QML compartilhada | `10a2fac69ca1b5198f3cb4a7ccf044f2ef82b5d0` | 394 visuais na integral, source hashes preservados | PNG instalado pendente |

Último código testado: `10a2fac69ca1b5198f3cb4a7ccf044f2ef82b5d0`. O checkout deve permanecer nesta linha com
commits preservados. O checkpoint estruturado está em `CURRENT-CHECKPOINT.json`;
nenhuma nova cópia, branch por lote ou reconstrução é necessária. Artefato de
release futuro deve apontar o SHA integrado exato de main/CI, que ainda não existe
para este lote. O commit funcional local não é uma release instalada.

## Preparação governada efetivamente tentada

`17-prepare-checkpoint.json`: após o commit documental `d823ff857a35dedab8569a6b106e245d87ce8ce6`
e árvore limpa, `release_host.py prepare` atualizou origin/main e recusou o
checkout: **prepare aceita somente o tip exato de refs/heads/main**. O tip
conferido foi `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7`. Exit 1 do controlador,
nenhum bundle preparado e nenhuma mutação do host. A recusa não foi contornada.

**PENDENTE_INTEGRACAO_REMOTA:** falta autorização de push da linha existente e
integração governada em main (inclui o histórico pendente do PR #258). O último
run remoto desse PR possui falha visual; somente um CI push terminal verde do
SHA integrado permite preparar a candidata. O checkpoint final documental
posterior apenas registra a recusa; o código continua em `10a2fac6` com hashes
idênticos aos testados.

Retomada: no mesmo diretório, conferir HEAD/branch/árvore, executar o checkpoint
remoto autorizado e assumir o SHA exato de main/CI, preservando estes commits.
Depois: `rtk proxy env PYTHONPATH=src .venv/bin/python tools/release_host.py
prepare --commit <SHA-main-completo> --output /tmp/steamzero-r0-r1-bundle`.
Conferir bundle/run/hash/boot/ownership/rollback e usar install com o token
exato. Instalação e testes continuam autorizados; senha, se pedida, somente no
terminal/diálogo, sem documento ou argumento. Reavaliar janela dedicada antes de
input; nenhuma prova instalada nova foi feita e R0/R1 continua aberto.

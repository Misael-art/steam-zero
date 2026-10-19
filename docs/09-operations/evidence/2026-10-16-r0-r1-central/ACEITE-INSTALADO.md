# R0/R1 — roteiro pendente para a candidata instalada

Estado: NÃO EXECUTADO. Usar somente depois de main/CI, bundle verificado e
instalação pelo controlador. Não tratar fixtures/offscreen como resultado.
Central Desktop é o alvo; Launcher, Theme Engine, Studio e Aura não são
homologados por este roteiro.

1. Conferir novamente HEAD, branch, árvore limpa, CI push terminal verde e SHA
   completo do bundle. Ler a release ativa, validar rollback da release atual,
   ownership, schema de dados e entrypoints de boot. Registrar release/SHA/hash
   do wheel/run e tokens do controlador sem incluir senha ou credenciais.
2. Instalar pelo `release_host.py install` com bundle, rollback validado e token
   exato da candidata. Se falhar autenticação, parar nessa etapa e registrar
   `PENDENTE_CREDENCIAL`, comando sem segredo e ponto de retomada. Não executar
   sudo, helper arbitrário ou alteração manual de /opt, /etc ou /boot.
3. Verificar versão, daemon, units, doctor e convergência/idempotência pelo fluxo
   governado. A versão exibida na Central precisa corresponder ao manifesto
   ativo e ao SHA instalado. Erro de convergência impede seguir para o aceite.
4. Preparar perfil/corpus próprio de teste em XDG isolado, com identidades
   independentes da biblioteca e documentos ativos do operador. Identificar
   jogos próprios NES e Amiga e BIOS locais já possuídas. Não baixar ROM/BIOS,
   não persistir seus caminhos privados ou conteúdo nesta evidência. Registrar
   somente IDs públicos de teste e fingerprints saneados. Não montar cópia de
   desenvolvimento nem mudar preferências reais para semear o teste.
5. Garantir janela/sessão dedicada. Conferir alvo e foco antes de toda entrada.
   Desktop ocupado ou foco não verificável mantém `PENDENTE_JANELA_DE_TESTE`;
   não usar atalhos globais às cegas. Capturar somente a janela da aplicação.
6. NES: Central → plataforma → Emulador. Conferir RetroArch e core mesen, ações
   reais publicadas de abrir/manter e ausência de Keys/Firmware/Keys pendentes.
   Abrir a lista Por jogo, escolher o jogo e seus ajustes. Alterar a preferência
   de emulador usando plano/confirmação; cancelar primeiro e conferir ausência
   de escrita, depois aplicar e ler de volta. Configuração original do usuário
   deve conservar bytes e preferência global deve permanecer intacta.
7. Amiga: conferir core puae e nomes de BIOS exigidos no resumo; não mostrar
   importação universal de firmware. No perfil de teste, exercitar requisito
   ausente e recuperação com os arquivos próprios pelo catálogo BIOS existente,
   sem renomear conteúdo arbitrário como BIOS válida. Falha de leitura deve ser
   desconhecida, não ausente ou instalada. Se corpus/BIOS não estiver disponível,
   registrar pendência desse cenário, sem promover o aceite.
8. Para cada plataforma, conferir que o preflight e o resultado do Play concordam
   com runtime/core/BIOS/jogo reais. Reproduzir recusa controlada, voltar sem
   perder plataforma/emulador/jogo/filtro, corrigir pelo produto e retomar. ROM
   regular não exige materialização de archive. Caso archive seja escolhido,
   comprovar preparação real e catálogo atualizado; o slice não publicou um
   novo botão de extração na Central e não deve inventar prova desse fluxo.
9. Fechar/reabrir Central e conferir readback da preferência. Jogar e retornar
   quando o corpus permitir; registrar limite se gameplay não for executado.
   Verificar logs e preservação de fontes/configurações/saves antes e depois.
10. Repetir a jornada em viewport 1280×800 e desktop pertinente, com mouse e
    teclado. Deck físico, controle e toque são aceites separados, condicionados
    ao hardware; viewport nunca os comprova. Persistir PNGs ordenados
    `01-baseline.png`, `02-entrega-funcional.png`, `03-recuperacao.png`, cada qual
    vinculado à release efetivamente ativa e sem segredos/dados privados.
11. Se falhar, manter R0/R1 aberto e voltar à correção no mesmo checkout. Se
    houver regressão de instalação, seguir rollback governado, com alvo e token
    verificados. Reboot físico permanece com o operador. Só após aceite
    aplicável atualizar os cinco eixos, as visões e o fechamento de WORKLOG;
    então R2 pode começar com o mesmo conjunto de jogos.

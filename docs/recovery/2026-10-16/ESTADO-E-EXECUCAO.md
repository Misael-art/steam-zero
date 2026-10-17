# Estado e execução das capacidades de experiência

Complemento do [plano R0–R10](PLANO.md). Esta avaliação foi feita sobre `52131b87`, em 2026-10-16. O [baseline complementar](baseline-capacidades.json) preserva os cinco eixos dos dez itens diretamente relacionados. Os JSONs de status são a fonte viva; as tabelas abaixo são diagnóstico datado e backlog de integração, sem promover hardware ou release.

## O que existe e o que falta

| Recurso | Evidência existente | Lacuna para a experiência solicitada | Referência de status |
|---|---|---|---|
| Ações de sessão | `domain/session_overlay.py` e `adapters/session_control.py` publicam ações tipadas; vocabulário de 13 ações espelhado em scene surfaces | Registry abrangente, contexto e fontes para qualquer composição; execução deve continuar no serviço | `SZ-AURA-SESSION-OSD`: parcial, hardware, degradado, instalado |
| Composição de tema | `scene_surfaces.py`, schema e componentes; slots de bezel, OSD e saves | Instâncias arbitrariamente compostas pelo Studio com fontes/ações compatíveis; preservar foco em gameplay | `SZ-THEME-ENGINE`: parcial, hardware, degradado, instalado |
| Studio | Jornadas, edição de aparência e seleção de PNG de bezel | Biblioteca de capacidades, bindings tipados, estados de preview e o mesmo documento executado em todas as superfícies | `SZ-THEME-STUDIO`: parcial, hardware, degradado, instalado |
| Cast | Máquina de estados, pareamento, orquestrador, engine, providers web/game-stream | Descoberta interoperável, métodos de auth por provider, receptor remoto real, indicador e recuperação autoráveis | `SZ-CAST-LAN`: implementação completa no escopo antigo, unit, operação degradada, instalado; internet planejado |
| Multidisco | Conjuntos e descritores, materializadores e IDs estáveis; sessão RetroArch envia comandos de troca | Modelo de drive, readback, UX por controle e provas específicas PX68k/PUAE/PS1 | `SZ-MULTIDISC-SESSION-DISC-IDENTITY`: parcial, hw, ready no escopo próprio, não empacotado; reconciliação/materialização parciais |
| Saves e miniaturas | `save_states.py`, galeria QML e adapter RetroArch; backup e slots delimitados | Reutilizar fontes em composições livres, compatibilidade completa e retenção explícita | `SZ-AURA-SAVE-STATE-GALLERY`: parcial, released, hw, degradado, instalado |
| Replay e rewind | Ação `rewind` existe no vocabulário de sessão | Não localizado contrato público de galeria de replay de gameplay no recorte; vídeo, inputs determinísticos e rewind precisam de itens distintos no contrato | Novo `SZ-EXPERIENCE-SAVES-REPLAY` |
| Packs HD e melhorias | `game_enhancements.py`, recipes/renderers e instalador; formatos de patch/config específicos | Fluxo de pack gráfico/textura completo, compatibilidade por título e ação componível com estado efetivo | `SZ-EMULATION-ENHANCEMENTS`: complete no escopo antigo, unit, operação unknown, não empacotado |
| Amiibo e e-Reader | Referências de possibilidades do ecossistema; não localizada porta dedicada no código pesquisado | Identidade de acessório, inserir/remover/leitura/escrita, catálogo e integração por runtime | Novo `SZ-EXPERIENCE-PERIPHERALS` |
| Link e múltiplas telas | Catálogo de plataformas, perfis de input, sessão e cast em domínios existentes | Sessão composta, isolamento por participante e prova de comunicação entre jogos | R7/R8 e novo `SZ-EXPERIENCE-PERIPHERALS` |

Os formatos de melhorias inspecionados incluem pnach, Cemu rules, Dolphin GameINI, RPCS3 YAML e DuckStation INI; gerar um arquivo desses não equivale a instalar um pacote HD nem observar seu efeito. O código de bezel publica `launch-configured-unconfirmed`; uma imagem preparada no launch não prova overlay interativo. Na troca de disco, `_active_disc` local também não basta como confirmação de runtime.

## Integração com o roadmap existente

A sequência R0–R10 continua válida, com estas entregas explícitas encaixadas nela. Cast básico e multidisco não ficam adiados até a experiência Wii U: avançam assim que as portas e sessões necessárias estiverem disponíveis. O contrato mínimo de composição entra antes de cristalizar novas telas fixas.

| Lote | Item novo | Encaixe e dependências | Entrega e gate decisivo |
|---|---|---|---|
| C0 | `SZ-EXPERIENCE-COMPOSITION` | Inventário em R0/R1; execução R3/R4; consome Theme Engine/Studio/sessão | Registry mínimo de capacidades/ações/fontes; mesma ação em duas composições, um efeito observado, sem código externo |
| C1 | `SZ-EXPERIENCE-CAST-UX` | R1/R3/R4, reutiliza `SZ-CAST-LAN`; composição depende C0 | Compartilhar → receptor real → auth necessária → transmissão → parada/recuperação; pela UI padrão e por tema |
| C2 | `SZ-EXPERIENCE-MULTIDRIVE-UX` | R3/R4, consome identidade/materialização; composição depende C0 | PS1, X68000 e Amiga; drive correto, operação observada, troca pelo controle no bezel/menu |
| C3 | `SZ-EXPERIENCE-SAVES-REPLAY` | R3/R4, base de galeria já existente; depende C0 | Galeria livre e segura primeiro; retenção explícita depois; clipes e replay determinístico em subentregas separadas |
| C4 | `SZ-EXPERIENCE-ENHANCEMENTS-UX` | R1/R2/R4, consome domínio de melhorias e identidade do jogo | Um pack real compatível, plano/apply/readback/rollback e menu autorado; next-launch explícito |
| C5 | `SZ-EXPERIENCE-PERIPHERALS` | Estudo em R0; pilotos em R7/R8; C0 e sessão composta quando necessária | GBA e-Reader, GB/GBA link, Amiibo e periféricos em slices próprios; cada porta tem prova por runtime |
| C6 | `SZ-EXPERIENCE-PLATFORM-CATALOG` | Inventário em R0, expansão em R10, consome C0 e lotes pertinentes | Converter propostas em capabilities comprovadas por família sem publicar suporte por nome da plataforma |

Estes novos itens representam **jornadas/integrações ainda planejadas**. Os componentes existentes conservam seus próprios estados. Seus scopes documentais apontam o contrato a implementar; o agente executor deve registrar os arquivos de código e evidência no workstream do lote antes de editar. Não interpretar um contrato escrito como implementação de runtime.

## Ordem concreta de execução

1. No próximo R0/R1, incluir a matriz de requisitos e um inventário mínimo de ações/fontes/estados; mapear os 13 IDs de sessão atuais para o registry proposto. Não interromper a correção da Central para construir um framework genérico completo.
2. Em R3/R4, fechar o primeiro slice componível: `listDiscs`/`swapDisc` ou `listSaveStates`/`loadState` com seleção tipada, erro e resultado observados. Preservar os aliases de IDs atuais. Captura/save/exit continuam com as guardas atuais até migração testada.
3. Provar o slice no Studio em submenu e lateral; acrescentar bezel interativo quando compositor/runtime comprovarem a superfície. O estado comum deve ficar sincronizado nos dois lugares.
4. Executar C1 e C2 como jornadas completas em lotes separados e com donos claros. C2 começa pelo adapter mais demonstrável e só declara X68000/Amiga após suas provas de drive.
5. Fechar galeria/retention e um pack real; expandir fontes e primitivas, evitando widgets exclusivos por emulator.
6. Pilotos de acessórios: e-Reader GBA com recurso próprio; link GB separado do link GBA; Amiibo em runtime que publique porta observável. Não escolher emulador apenas porque o hardware original oferece a função.
7. Expandir famílias conforme o catálogo e depois R10 com matriz de hardware/temas/controle. Propostas sem backend ficam planejadas ou indisponíveis com motivo.

## Aceite específico dos lotes

**C0:** selecionar uma capacidade no Studio, instanciá-la duas vezes, mudar composição, salvar/reabrir/exportar/importar e executar no Launcher. Ação proibida, sessão expirada e dado inválido são recusados pelo serviço; callback antigo não altera sessão nova. Registry publicável e schema de tema devem ser verificados juntos para impedir ações de UI sem porta. Os limites atuais de 16 componentes e 32 itens/slots não podem produzir truncamento silencioso: paginação/virtualização e budgets precisam preservar acesso ao acervo.

**C1:** sucesso com e sem desafio; receptor real, nomes legíveis seguros, descoberta incremental e cancelável; dedupe; PIN inválido/expirado; revogação; queda de rede; parada liberando captura. Método de senha/aprovação só entra como suportado após provider real. Registrar latência e qualidade por via.

**C2:** identidade após conversão, drive e participante corretos, falha após ejeção, múltiplos cliques, disco removido, seleção fora de ordem e retorno ao jogo. Alternar a mesma coleção entre bezel/submenu sem mudar a operação. Detecção automática do pedido do jogo tem aceite independente de seleção explícita.

**C3:** screenshot corresponde ao estado; restore compatível; slots manuais preservados; autosaves com política verificável; fade não apaga arquivos. Clique em clipe reproduz vídeo; replay de inputs só se houver conjunto determinístico validado. Parar/reiniciar gravação não corrompe a sessão.

**C4:** jogo/versão/região/runtime corretos; conflitos e espaço conhecidos; aplicação observada; rollback restaura configuração/arquivos próprios. Pack que exige reinício não publica efeito imediato. Tema pode apresentar selector ou preset, usando a mesma operação.

**C5:** inserir/remover recurso e observar resposta do jogo; escrita protegida ou versionada quando houver; controles/saves isolados no link; falha de um participante não sobrescreve os demais. Testar GB, GBA e GameCube-GBA como cenários separados, além das funções Wii U previstas em R8.

**C6:** cada recurso promovido registra plataforma/variante, emulator/core/build, título/versão, dependências, testes, release/hardware, limite e duas formas de apresentação pelo tema quando pertinente. Atualizar manifesto operacional só após essa evidência; pesquisa upstream isolada não habilita capability.

## Coesão documental e rastreabilidade

| Documento existente | Tratamento nesta ampliação |
|---|---|
| `DIRECAO.md` | Referencia este contrato de composição e as jornadas específicas como extensão normativa |
| `PLANO.md` | Incorpora C0–C6 em R0–R10; cast/multidisco passam a ter gate explícito anterior à expansão Wii U |
| `PROXIMO-AGENTE.md` | Inclui inventário de ações/fontes no primeiro lote e preserva o foco R0/R1 |
| `AGENTS.md` | Exige leitura de capacidades componíveis e catálogo antes de ampliar recursos |
| `THEME-ENGINE-AND-STUDIO.md` seções 12/21 | Preservar contratos e implementação; este complemento amplia a autoria para instâncias livres, sem tratar slots fixos como limite do produto |
| `AURA-SURFACES.md` | Aplicar nomenclatura corrigida da direção; evidências históricas permanecem válidas apenas para seus escopos |
| ADRs 0022/0023 e itens de cast | Reutilizar arquitetura; corrigir lacunas de provider e descoberta antes de anunciar interoperabilidade |
| Itens antigos de multidisco/saves/melhorias | São dependências reutilizáveis; não mudar seus eixos para refletir planejamento novo |
| `EXPERIENCIAS-POR-PLATAFORMA.md` e JSON | Catálogo editorial completo e rastreável, explicitamente separado de manifests de runtime |

Arquivos históricos reivindicados por frentes ativas não foram editados nesta ampliação. A precedência e os vínculos acima evitam instruções conflitantes; sua consolidação editorial deve ocorrer no handoff desses arquivos, sem apagar evidências. Novas lembranças do proprietário entram primeiro no contrato/catálogo, são confrontadas com código/status e então recebem lote/aceite; não gerar um roadmap paralelo desconectado.

## Verificação desta ampliação

Bateria focal: `test_scene_surfaces.py`, `test_session_peripherals.py`, `test_save_states.py`, `test_cast_orchestrator.py`, `test_multidisc_artifacts.py`: **71 passed**, 1,67 s de pytest; runner 0 e state home sem diferença observada. Isso demonstra fundamentos reutilizáveis, não receptor físico, drive real ou composição livre concluída. O log e os checks documentais estão em `VALIDACAO.md`.

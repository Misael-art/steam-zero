# Diagnóstico e reconstrução histórica do SteamZero

Avaliação de 2026-10-16 sobre `6475947c189f2d903b83f7f242a2c5ca535fb14c`, branch de origem `codex/jornada-fisica-bateria-2026-10-12`. A referência local `origin/main` é `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7` e é ancestral dessa base. Não houve consulta remota para afirmar o tip atual do servidor. O checkout estava limpo antes da abertura da branch documental.

A análise combina história Git desde o primeiro commit disponível, documentos de fundação, mudanças de temas/launcher, registros de status, implementação atual e testes focados. Não é uma revisão linha a linha de todos os commits nem uma recertificação física das 64 plataformas. Os relatos do proprietário são requisitos de investigação; causas confirmadas no código e limites históricos aparecem separados abaixo.

## Reconstrução desde a fundação

| Momento | Evidência recuperável | Evolução e consequência |
|---|---|---|
| 15 jul, fundação | `36c43f56`, visão original; `dfd59f2b`, `8ebe4ebd`, `d45ed8b5` | Plataforma transacional, estado SQLite e jobs; preservação, controle e operação amigável já eram princípios centrais |
| 15–30 jul, primeiros marcos | `IMPLEMENTATION-REPORT.md`, M1–M15 | Forte construção de core, CLI, biblioteca e saves; o relatório distingue provas com portas fake de validação em hardware |
| 26–27 jul, framework visual | `84d213c3`, `c367198f`, `a7a9b09b` | O recorte documentado era tematizar a central por tokens/assets; importar ES-DE começou por esse contrato |
| 28 jul, cenas RetroFE | `84e8cad4`, `ab3e78d9` | Surge compilação de layout em representação intermediária; é infraestrutura de compatibilidade mais ampla que paleta |
| 5 ago, identidade de experiências | `f500a3bd` | Catálogo de hardware/sistemas organiza identidades; não representa ainda a orquestração multijogador/multitela pedida agora |
| 18–19 ago, superfícies e launcher | `226b5f4b`, `7e57ff4c`, `31eac279` | Consolidam-se a terminologia AURA UI/AURA Launcher, grafo de foco e entrypoint fullscreen |
| 30 ago–4 set, biblioteca real | `b8caac1c`, `0a6a3869`, `4cd4c848`, `bf23fd7d` | Lançamento, agrupamento, retorno e acervo Steam evoluem; já há investimento útil a preservar |
| 3 set, ES-DE em IR | `550747d9`, `e177a4de`, `2e4e7d77` | Compilação, includes, variáveis e metadados por sistema; reconhecimento de sintaxe não fecha a jornada renderizada |
| 11–21 set, cinema e sessão | `615502ce`, `000c8bbf`, `8329b47a`, `0850513a`; itens de sessão e mídia | Cinema, detalhes, OSD e mídia avançam em fatias, com provas físicas limitadas a releases/casos específicos |
| 1–11 out, jornadas e Studio | `7246f7f0`, `09033bd5`, `6af40f81`, `78a91eed`, `2b7eb541` | Normalização RetroFE, autoria de menus, ponte para Launcher e catálogo por plataforma; múltiplos caminhos de composição persistem |
| 12–15 out, correções e bateria | base `6475947c`; matriz da Tarefa 15 | Correções de sessão, erros, atalhos e contraste; a própria evidência mantém lacunas físicas e fluxos abertos |
| 16 out, correção de direção | Solicitação do proprietário nesta sessão | Central desktop e launcher são as superfícies; Aura deve ser o tema demonstrativo, com motor e experiências de plataforma como capacidades explícitas |

A causa histórica identificável não é simplesmente falta de programação: o recorte inicial de temas administrativos foi ampliado sem uma substituição coerente do contrato de produto. Documentação, nomes e implementação passaram a acomodar central, launcher, cinema, jornadas, temas e Studio sob o mesmo vocabulário AURA. Esta é uma interpretação da sequência acima, não uma atribuição de intenção aos agentes anteriores.

## Grau de desenvolvimento

O [baseline estruturado](baseline.json) preserva os 97 itens anteriores a esta entrega.

| Eixo | Contagem declarada |
|---|---|
| Implementação | 34 completas, 56 parciais, 7 planejadas |
| Verificação | 31 unitárias, 17 de desenvolvimento, 1 VM, 27 hardware, 21 sem verificação |
| Operação | 13 prontas, 41 degradadas, 41 desconhecidas, 2 bloqueadas |
| Distribuição | 46 instaladas, 1 empacotada, 50 não empacotadas, 0 certificadas |
| Manifestos de plataforma | 64; 71 declarações de capacidade `ready` e 206 `planned` |

São unidades de tamanhos diferentes, com escopos e evidências de datas distintas. Somar itens não produz um percentual útil de produto pronto. `ready` em manifesto também não é certificação funcional.

**Classificação qualitativa:** infraestrutura implementada e integração de produto parcial, com jornadas em estabilização. A versão do pacote é `2.0.0rc1`; o nome RC não substitui aceite. O projeto não está no ponto zero, mas as evidências disponíveis não sustentam declarar excelência global de Central, Launcher ou compatibilidade universal de temas.

## Achados sustentados pelo código

| ID | Evidência | Conclusão e efeito |
|---|---|---|
| REC-01 | `AGENTS.md` anterior seção 10; `AURA-SURFACES.md`; PRD | A nomenclatura normativa conflita com a intenção atual. Corrigir a autoridade documental é necessário para impedir repetição do desvio |
| REC-02 | `themes/org.steamzero.aura/theme.json` possui tokens/assets e herança; `LauncherCinema.qml` contém composição; `asset-recipes-demo` concentra cenas/receitas | O pacote Aura não demonstra sozinho a composição completa do tema pelo contrato público. É necessário extrair a composição para um pacote consumido pelo runtime comum |
| REC-03 | `theme_import_retrofe.py`, `scene_retrofe.py`, `test_theme_import_to_runtime_journey.py` | Há importador e resolução de cena; teste explicitamente cobre cena sintética sem ativação. Não confundir com jornada RetroFE pronta |
| REC-04 | `theme_import_esde_layout.py`, `scene_esde.py`, itens `SZ-THEME-IMPORT-ESDE-LAYOUT` e `SZ-THEME-ESDE-SCENE-RENDER` | Há trabalho relevante de includes/variáveis/cenas; status ainda registra ativação/renderização física e perdas em aberto |
| REC-05 | `Emulation.qml`, função `overviewCards`, aproximadamente linhas 1187–1245 | O fallback constrói cartões Keys/Firmware e ações genéricas sem demonstrar nesse trecho aplicabilidade por sistema. Dá uma causa concreta para a apresentação inadequada relatada; validar cada plataforma no próximo lote |
| REC-06 | `emulation_workspace.py`, `emulator_config.py`, manifestos | Existem composição de plataforma e perfis, mas isso não equivale a um editor detalhado por emulador. Configuração declarada precisa de writer/readback e interface por capacidade |
| REC-07 | `scraping/screenscraper.py::search`, `scraping/dispatcher.py`, `game_record.py`, importadores de metadata | O caminho examinado seleciona `medias` e retorna `MediaCandidate`; ano/gênero não são preenchidos por esse caminho. Importadores de metadados externos existem, portanto a lacuna é também de integração/aquisição e publicação, não ausência total de modelo |
| REC-08 | `LauncherMain.qml`, `launcher/app.py::resolve_journey_theme` | Há Home, Cinema e Journey com caminhos de dados/aparência distintos. Menu sem aparência cai em default; `inherit-aura` cai em Aura. A divergência pode produzir alternância de visual; a ocorrência física específica ainda precisa ser reproduzida |
| REC-09 | `35-wii-u.platform.json`, `25-wii-u-gamepad.input.json` | Manifesto declara toque/movimento/microfone, mas o perfil inspecionado traz botões e eixos básicos. Não comprova GamePad completo nem roteamento de TV/GamePad |
| REC-10 | `canonical_experiences/catalog-v1.json`, `retro_experience.py`; busca por link/multi-instance nos módulos | Existem catálogo de sistemas e presets retro. Não foi localizado um fluxo completo de GBA link com duas instâncias e saídas/input independentes no recorte inspecionado |
| REC-11 | `SZ-CAST-LAN`, `SZ-CAST-INTERNET` | LAN está `complete` no eixo implementação, mas operação degradada com receptor real pendente; internet está planejada. Não são provas de streaming de um jogador mantendo o outro local |
| REC-12 | `Main.qml` 6.885 linhas; `desktop_dashboard.py` 2.427 linhas na base | Há concentração de composição e ligação de ações. Ela aumenta o custo de mudanças compartilhadas; tamanho por si só não prova bug e não justifica reescrita total |

Os fontes acima são relativos à raiz do repositório. A pesquisa no código não demonstra que todos os botões falham. Demonstra divergências específicas e fundamenta uma auditoria por jornada, em lugar de presumir backend universalmente ausente.

## O que preservar e o que completar

| Área | Investimento existente | Trabalho de recuperação |
|---|---|---|
| Core e operação | Transações, jobs, banco, isolamento, release e rollback | Reutilizar como base e revalidar nas novas jornadas |
| Biblioteca | Identidades, importadores, projeções e catálogo | Uniformizar universo/seleção entre superfícies e fechar página de jogo |
| Mídia | Providers, cache, download, staging e associação | Unir dados descritivos e assets; explicar credenciais/ausências; publicar atualização nas duas superfícies |
| Emuladores | Manifestos, lifecycle, preflight e alguns writers/perfis | Matriz por runtime/versão; configurações aplicáveis e prontidão real por jogo |
| Temas | IR ES-DE/RetroFE, resolver, assets, efeitos, QML e testes | Ativação fullscreen, navegação, fidelidade e medição por pacote |
| Launcher | Home, detalhes, cinema, sessão e retorno | Unificar contrato de composição e estados, preservar contexto sob erro e troca de tema |
| Studio | Tokens, jornadas, arquivos e preview | Garantir que o pacote autorado é o pacote executado; autoria avançada depois da primeira jornada pronta |
| PC/web | Integração Steam e manifestos de plataformas cloud | Validar descoberta, autenticação/input, sessão e retorno como jornadas próprias; não cobertos pela bateria focal desta análise |
| Experiências especiais | Input, display, sessão e cast em domínios separados | Orquestração comprovada por perfil e topologia; piloto GBA antes de expansão |

## Estado físico e regressões conhecidas

A leitura read-only de `/opt/steamzero/current` nesta sessão apontou `releases/2.0.0rc1-1470cf48bf7d`. O diretório da release anterior `2.0.0rc1-2b7eb541b4a5` existe. Não foi executado rollback, instalação, reboot ou comando de jogo.

A [matriz de abertos da Tarefa 15](../../09-operations/evidence/2026-10-13-lote-coesao-ui/logs/28-matriz-abertos-tarefa-15.md), datada de 15/10, registra: 22/25 adapters não testados naquele recorte; retorno/fades/recuperação ainda abertos; gamepad/touch não provados; 30 reprovações residuais de contraste naquela medição; e vários testes de sessão não executados fisicamente. São fatos documentados daquela rodada, não novas medições desta sessão. “25 adapters” é o denominador daquela bateria, não contagem global do código.

Para recuperar a beleza e fluidez anteriores, montar um corpus de regressão: selecionar capturas/vídeos históricos ES-DE/Aura; ligar cada um à release, tema e hash de assets; escolher referências estéticas com o proprietário quando existirem alternativas; reproduzir a mesma biblioteca, proporção e escala antes/depois. Uma captura bonita antiga sem esses vínculos é referência visual, não baseline de desempenho. A preferência visual exata anterior não foi reconstruída por execução nesta avaliação.

## Lacunas de processo

1. Escopos estreitos permitem `complete` para importação enquanto o usuário espera execução do tema. Preservar o item estreito e criar/ligar aceite da jornada maior.
2. Status de distribuição e operação não são coerentes por dedução: “instalado” pode continuar degradado. O próprio modelo de cinco eixos já permite expressar isso corretamente.
3. Referências de entrada antigas, como o README que prioriza `IMPLEMENTATION-REPORT.md`, favorecem leitura de um relatório histórico como estado corrente. A entrada obrigatória dos agentes foi corrigida; reordenar outros índices é parte do lote documental seguinte.
4. Claims ativos persistem após trabalhos antigos. Reconciliar proprietário, branch e integração antes de tomar arquivos; não apagar claims por supor abandono.
5. Testes de contrato e offscreen são úteis, mas não fecham input físico, performance, vídeo/áudio e percepção visual.

## Evidência executada agora

Cinco arquivos de teste foram executados pelo runner isolado: importação de tema até resolver, RetroFE, includes ES-DE, metadata até catálogo e escopo de emulação. Resultado: **38 passed, 1 skipped**, 2,88 s de pytest; runner encerrou com código 0 e sem alteração observada no state home. O skip corresponde à árvore `reference/` não versionada. Essa bateria comprova partes da base técnica, não uma janela fullscreen ou serviço remoto.

As demais verificações e a integridade documental estão em [VALIDACAO.md](VALIDACAO.md).

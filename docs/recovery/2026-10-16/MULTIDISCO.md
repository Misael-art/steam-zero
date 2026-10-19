# Troca fluida de discos e disquetes

O usuário escolhe um disco por controle e o SteamZero executa o procedimento exigido pelo runtime. O tema pode apresentar a coleção na moldura, num submenu ou em qualquer composição compatível. A primeira entrega cobre seleção explícita simples; automação de detecção do pedido do jogo é uma capacidade adicional.

## Modelo de mídia e unidades

Separar `gameId`, `setId`, `mediaId`, `driveId`, participante e sessão. O conjunto lógico tem ordem, rótulos e identidade preservada após conversão/extração. Cada unidade publica tipos aceitos, mídia inserida, ejetada/ocupada, proteção de escrita e capacidade de observação. Índice M3U é detalhe do adapter; não é identidade definitiva do disco.

| Sistema | Particularidade a atender |
|---|---|
| PlayStation e outros consoles ópticos | Abrir bandeja → selecionar disco → fechar; manter mesmo jogo/conjunto/saves |
| X68000 | Identificar FDD0/FDD1, preservar mídia da outra unidade e selecionar o alvo correto |
| Amiga | Unidades DF0…DFn conforme runtime; distinguir disco de jogo e disco gravável; multidrive não é apenas lista de CDs |
| Outros computadores/disquetes | Unidades, lados, cartuchos, fitas e gravação dependem do adapter; não aplicar protocolo óptico por conveniência |

PX68k documenta seleção de FDD0/FDD1 e troca pela interface de disco; PUAE documenta playlists e inserção em múltiplas unidades. Esses recursos justificam contratos específicos de drive, mas não provam a integração SteamZero. [PX68k](https://docs.libretro.com/library/px68k/), [PUAE](https://docs.libretro.com/library/puae/).

## Três níveis de automação

1. **Procedimento automático após escolha:** usuário escolhe disco; aplicação faz ejetar/selecionar/inserir e observa o resultado quando o runtime permite. É a prioridade.
2. **Atalho contextual:** tecla abre a coleção ou alterna para próximo/anterior válido. Em jogos que pedem discos fora de sequência, usar seleção direta; debounce impede múltiplas trocas involuntárias.
3. **Troca orientada pelo jogo:** adapter recebe evento confiável de pedido de mídia ou receita específica validada para aquele jogo/versão. Sem esse sinal, oferecer seleção/sugestão e não tentar adivinhar pelo tempo decorrido. OCR ou heurística futura precisa de confiança, confirmação pertinente e fallback próprio.

Escolher ou pré-montar múltiplas unidades pode reduzir trocas quando jogo/runtime suportarem; não alterar o conjunto nem substituir conteúdo automaticamente.

## Jornada de referência X68000

Street Fighter, conforme o exemplo do proprietário, será caso de aceite quando houver jogo e runtime disponíveis. Ao pedir outro disquete, a ação do controle abre miniaturas/rótulos e identifica a unidade relevante. Selecionar mantém foco, executa a transação de troca e retorna ao jogo. O submenu alternativo produz o mesmo resultado. Validar uma sequência repetida de trocas, inclusive retorno a um disco anterior, cancelamento e falha no meio do procedimento.

Se o adapter não informar a unidade pedida, usar unidade configurada explicitamente para aquele perfil, permitindo correção simples. Não trocar FDD0 quando a operação exige FDD1. A outra unidade permanece intacta.

## Estado atual e correção necessária

`multidisc.py`, `multidisc_artifacts.py` e os materializadores fornecem fundamentos de conjuntos/descritores. `session_peripherals.py::swap_disc` envia comandos RetroArch de ejeção e avanço/retorno e atualiza `_active_disc` localmente. O trecho inspecionado não consulta o runtime para confirmar mídia efetivamente inserida e não recebe `driveId`.

Consequentemente, preservar a identidade já construída e ampliar o contrato de sessão. Não tratar `_active_disc` atualizado como confirmação física. Para um runtime sem readback, publicar `dispatched/unconfirmed` com diagnóstico e prova específica; não inventar estado observado.

## Robustez e aceite

Serializar trocas por unidade; validar sessão atual, conjunto e mídia; proteger discos graváveis; nunca sobrescrever o dump original. Tentativas após timeout reconciliam bandeja e mídia antes de reenviar comandos toggle. Restaurar o estado anterior quando seguro e observável; caso contrário mostrar recuperação precisa.

Testes de aceite: PS1 óptico; X68000 com duas unidades; Amiga com vários discos e mídia gravável em cópia gerenciada; seleção fora de ordem; arquivo removido; conversão preservando ID; resposta atrasada; troca de tema; botão pressionado várias vezes; suspensão; falha após ejeção. Capturar mídia/unidade observadas e continuidade do jogo, não somente a mensagem “troca enviada”.

A documentação PX68k consultada não anuncia save-states; portanto não condicionar a troca de disquete a um save-state inexistente nesse core. Escolher mecanismos de preservação adequados ao runtime e manter os limites visíveis. [Matriz de recursos PX68k](https://docs.libretro.com/library/px68k/).

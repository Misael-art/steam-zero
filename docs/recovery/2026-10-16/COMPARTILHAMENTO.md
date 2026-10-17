# Compartilhamento simples de tela e de superfícies de jogo

A experiência solicitada é: **Compartilhar → dispositivos disponíveis → selecionar → conectar**, pedindo PIN/senha ou aprovação somente quando o protocolo/receptor exigir. O mesmo recurso pode aparecer em botão, submenu, moldura ou painel do tema, consumindo a capacidade pública de compartilhamento.

## Jornada

1. Abrir Compartilhar inicia descoberta assíncrona e mostra resultados progressivos, com nomes amigáveis, tipo, disponibilidade e indicação de conexão prévia.
2. Um mesmo dispositivo anunciado por vários providers é deduplicado, preservando rotas alternativas compatíveis. Itens expiram quando deixam de ser observados.
3. O serviço escolhe uma rota compatível com a intenção: jogo em baixa latência, espelhamento ou mídia. O modo avançado permite escolher a rota; o fluxo normal não exige conhecer protocolos.
4. Selecionar receptor sem desafio obrigatório avança diretamente. Receptor já autorizado só renova credenciais quando necessário. Receptor com desafio abre exatamente o fluxo exigido: PIN exibido aqui ou no destino, senha, aprovação remota ou outro método suportado.
5. Captura respeita o portal/consentimento do sistema. Mostrar a fonte escolhida, priorizando janela/superfície do jogo quando disponível. Uma seleção simples de dispositivo não autoriza mudar silenciosamente para capturar todo o desktop.
6. Publicar conexão, áudio, qualidade e parada acessível. Desconexão oferece reconectar/trocar destino/continuar localmente; parar revoga captura e não encerra o jogo.

Resultado vazio explica “nenhum dispositivo compatível encontrado” e oferece atualizar/ajuda/adicionar receptor, sem aparentar travamento. Equipamento ligado na mesma rede não implica protocolo de recepção compatível. Não prometer que qualquer TV será descoberta; ampliar a matriz de providers até cobrir os dispositivos anunciados.

## Contrato e providers

O catálogo deve publicar identidade opaca estável, rótulo amigável aprovado para exibição local, protocolos/modos, método de autenticação, estado de confiança, última observação e motivo de bloqueio. Nome/endereço privado, PIN, senha e tokens não devem vazar para logs ou bindings arbitrários de tema. O serviço fornece um rótulo seguro ao tema e mantém o desafio sensível em componente do sistema com apresentação compatível. Reconciliar isso com a política atual de anonimização em `domain/screencast.py` antes de ampliar o payload.

| Via | Meta de produto | Estado do recorte inspecionado |
|---|---|---|
| Receptor próprio via WebRTC | Link/pareamento simples e transmissão LAN | Provider existente anuncia `local-browser` em loopback; isso não demonstra descoberta de navegador remoto |
| Game streaming | Baixa latência e input opcional por destinatário | `game-stream` existe; descoberta inspecionada usa broadcast próprio `STEAMZERO_DISCOVER` e endpoints `/info`/`pair` |
| Steam Remote Play | Integração contextual quando disponível | Enum no domínio não comprova provider; não consta no registro de dois providers do orquestrador |
| Espelhamento/Miracast/Cast | TVs e receptores com protocolo compatível | `screen-mirror` e `media-cast` são categorias do domínio; operação universal não demonstrada |
| Internet | Compartilhar fora da rede local | Item `SZ-CAST-INTERNET` planejado, dependente de LAN e decisão de transporte/relay |

Apesar do nome `_mdns_discover`, o método inspecionado não realiza descoberta mDNS/DNS-SD: transmite uma mensagem UDP própria e consulta os respondentes. Esse caminho não deve ser anunciado como descoberta universal de TVs ou clientes Moonlight. A documentação Moonlight distingue host e cliente; mapear corretamente quem anuncia, inicia e recebe a sessão antes de prometer seleção de um cliente a partir do host. [Guia oficial Moonlight](https://github.com/moonlight-stream/moonlight-docs/wiki/Setup-Guide).

Implementar `authMethod`/equivalente por provider, não uma regra global que sempre peça PIN. O registro público deve omitir credenciais. Confiança pode ser revogada; seleção repetida e callbacks atrasados não abrem duas transmissões. Provider indisponível falha isoladamente, sem bloquear a descoberta das demais vias.

## Uma superfície remota e outra local

A origem deve admitir seleção por sessão/participante/superfície (TV, GamePad, janela do jogador), com ID estável e propriedade. Roteamento de vídeo, áudio e eventual input remoto são independentes. Não usar monitor inteiro como substituto silencioso da janela desejada. A janela que desaparece exige reconciliação; não capturar outro app ocupando o mesmo lugar.

Transmitir a imagem não implica permitir controle remoto. Só oferecer entrada remota quando suportada e escolhida, vinculada ao participante correto. Falha de rede preserva a sessão local, saves e controle disponível.

## Aceite

Testar em receptor real: sem desafio; PIN correto/incorreto/expirado; senha quando houver provider; aprovação remota; receptor previamente autorizado e revogado; dois anúncios do mesmo dispositivo; destino que desaparece; cancelamento; perda de rede; mudança de resolução/áudio; suspend/resume; parada e nova conexão. Nos casos não implementados, registrar a lacuna em vez de substituir por mock.

Medir tempo até primeiro resultado, conexão, latência de vídeo/áudio/input quando aplicável, reconexão e frame loss. Estabelecer orçamento por protocolo e hardware após baseline. Provar o mesmo fluxo pelo botão padrão e por uma instância colocada pelo Studio. Fixtures validam estados; não certificam receptor ou latência.

# Provisionamento de captura e input funcionais (2026-10-12)

Release ativa: `2.0.0rc1-2b7eb541b4a5`. Janela alvo: `{84f3a10c-7f2e-48ec-9064-afc20ffca1f7}`
("SteamZero — Central de jogos", pid qml6 `steamzero/ui/qml/Main.qml`).

## Ferramentas confirmadas no host

| Função | Ferramenta | Constatação |
|---|---|---|
| Captura de janela | `spectacle -a <uuid> -b -n -o` | PNG 1730x1160 não vazio, sha256 registrado em `capturas/manifest.tsv` |
| Ativação/geometria | `kdotool v0.3.0` (`windowactivate`, `getactivewindow`, `search`) | funciona; **não** injeta teclas (`Unknown command: key`) |
| Input de teclado | `ydotool` 1.x via `ydotoold --socket-path=/tmp/.ydotool_socket` (device `input56`) | funciona **somente** com keycodes crus (`<code>:<state>`); tokens nomeados viram atraso silencioso |
| Estado acessível | `python3` + `gi` Atspi 2.0 | árvore completa exposta; `FOCUSED`/`FOCUSABLE` legíveis |

## Incidente de segurança operacional (registrado, sem dano)

Antes do harness, setas injetadas sem re-afirmação de foco chegaram a um diálogo
portal `Abrir arquivo` (pid 4482, `xdg-desktop-portal-kde`) que estava com o foco;
a AT-SPI reportou o quadro focado como `qoder`. Há sessões de outros agentes ativas
neste desktop compartilhado. Mitigação adotada e usada daqui em diante:
`harness/sz-harness.sh` reafirma `kdotool getactivewindow == alvo` antes de **cada**
tecla e aborta com rc=3 se o foco não for o alvo. Nenhuma tecla é enviada sem isso.

## Prova de entrega de input na janela do SteamZero

Passos: `sz_focus` (rc=0) → `probe-inicio-antes-tab.png` → `Tab` ×3 → `probe-inicio-depois-tab.png`.

- Pixel: `compare -metric AE` = **359 px** alterados (anel de foco no botão de navegação).
- Acessibilidade: antes, **nenhum** objeto com `FOCUSED`; depois, `FOCUSED: button 'Steam'`
  dentro do app `Qml Runtime`. As duas evidências são independentes e concordantes.

Conclusão: captura e input estão funcionais; a prova visual deixa de ser um bloqueio.

## Diagnóstico reproduzido nesta etapa

1. **Setas/D-pad não navegam na tela "Início" do central.** `Down` ×2 com foco confirmado
   produziram PNGs byte-idênticos (`4988b8fe…` antes e depois): nenhuma resposta visual.
   A barra de rodapé do próprio central anuncia "D-PAD NAVEGAR / A SELECIONAR / X AÇÃO DE
   CONTEXTO / B VOLTAR", mas nenhum handler de setas foi encontrado em `Main.qml` fora de
   diálogos específicos (`credentialScroll` trata Up/Down/Escape). A navegação por teclado
   real é só a cadeia de `Tab`.
2. **Central reportando desconexão do núcleo** com daemon convergido: ver `logs/04-central-desconectada.md`.

# S-1 Conectividade da Central (2026-10-15T16:31:46-03:00)

Esperado: a Central declara conexão com o núcleo (sem faixa 'Central desconectada').
Observado:
  - ocorrências de 'desconect' na árvore AT-SPI da Central (pid 3547660):
      1
            label|Central desconectada — alterações locais não serão sincroniz|ENABLED,SENSITIVE,FOCUSABLE
  - ocorrências de 'conect' (afirmativas):
            label|Contexto: Deck LCD  •  Monitor DP-1 conectado  •  Modo Deskt|ENABLED,SENSITIVE,VISIBLE,SHOWING,FOCUSABLE
              label|Deck LCD  •  Monitor DP-1 conectado  •  Modo Desktop|ENABLED,SENSITIVE,FOCUSABLE
            label|Deck LCD  •  Monitor DP-1 conectado  •  Modo Desktop|ENABLED,SENSITIVE,FOCUSABLE
            label|Deck LCD  •  Monitor DP-1 conectado  •  Modo Desktop|ENABLED,SENSITIVE,FOCUSABLE
              label|Deck LCD  •  Monitor DP-1 conectado  •  Modo Desktop|ENABLED,SENSITIVE,FOCUSABLE
  - núcleo: service status: ok { 
  - ponte do Launcher viva (sz_api model): HTTP 200 menu=platforms/Plataformas total=28 result=28 gen=0 filters={} selected=None focus=None scroll=0.0 theme=org.st
Evidência: capturas/S1-1-central-inicio.png; logs/S1-arvore-central.txt

Leitura do PNG S1-1-central-inicio.png (janela 1440x900 renderizada):
  - NÃO há faixa 'Central desconectada' na tela; o único alerta visível é
    'Perfil do Desktop desatualizado' (banner de contexto, não de conexão).
  - Na árvore AT-SPI o label 'Central desconectada — alterações locais não serão
    sincronizadas' aparece SEM VISIBLE/SHOWING (objeto carregado, oculto) — o
    controle de conexão reporta o núcleo acessível (daemon converged, ponte 200).

Avaliação de UX: a ausência da faixa é a declaração positiva de conexão; não há
  rótulo afirmativo 'conectado ao núcleo', então a tela informa apenas por omissão.

Veredito: DEMONSTRADO — a Central NÃO declara mais desconexão com o núcleo
  (defeito da rodada 2026-10-12 não reproduzido nesta release).

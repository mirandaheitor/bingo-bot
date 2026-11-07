# Bingo Bot

Bot em Python para automatizar o mini-game Bingo do Angels Online Global em duas instancias cooperando entre si.

## Estado Atual

Etapas 1 a 7 implementadas:

- estrutura inicial do projeto;
- modelos de dados;
- configuracao editavel;
- validacao de layouts 5x5;
- mapeamento numero -> celula;
- estrategia base `WINNER_LAYOUT`, `LOSER_LAYOUT` e `CALL_SEQUENCE`;
- controladores secos de setup e batalha;
- maquina de estados sem captura e sem clique real;
- calibracao interativa das duas instancias;
- persistencia de `calibration/player_left.json` e `calibration/player_right.json`;
- captura de tela por regioes calibradas;
- diagnostico visual salvando imagens em `debug/`;
- criacao/atualizacao de templates visuais;
- detector de numero de preparacao por template matching;
- detector de turno `MY_TURN` / `WAITING`;
- detector de resultado `YOU WIN` / `YOU LOSE` / `DRAW`;
- montagem segura da cartela em dry-run;
- planejamento de `Undo` quando o numero detectado pula;
- planejamento de `Confirm` somente depois dos 25 numeros;
- batalha em dry-run ao vivo usando detectores de turno e resultado;
- calculo do ponto da chamada conforme o turno ativo e a sequencia configurada;
- cliques via backend configuravel: `window_message` ou `real_mouse`;
- backend experimental `SendMessage hover+click` sem mover o mouse real;
- cliques reais com `pydirectinput` quando `INPUT_BACKEND="real_mouse"`;
- teste real de botoes;
- execucao de 1 partida, N partidas e loop infinito;
- interrupcao por ESC ou Ctrl+C;
- script de compilacao com PyInstaller;
- testes automatizados.

O bot esta funcional para fluxo completo, desde que calibracao e templates estejam corretos.

## Estrutura

```text
bingo-bot/
+-- main.py
+-- config.py
+-- requirements.txt
+-- README.md
+-- models.py
+-- calibrate.py
+-- capture.py
+-- template_matcher.py
+-- setup_number_detector.py
+-- turn_detector.py
+-- result_detector.py
+-- board_layout.py
+-- board_builder.py
+-- setup_controller.py
+-- battle_controller.py
+-- game_controller.py
+-- input_controller.py
+-- diagnostics.py
+-- assets/setup_numbers/
+-- assets/states/
+-- assets/buttons/
+-- calibration/
+-- debug/
+-- tests/
```

## Instalar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativacao:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Testar

```powershell
python -m unittest discover -s tests
```

## Rodar

```powershell
python main.py
```

Opcoes liberadas nesta etapa:

- `1 - Calibrar esquerda`;
- `2 - Calibrar direita`;
- `3 - Criar/atualizar templates`;
- `4 - Diagnostico esquerda`, captura regioes calibradas;
- `5 - Diagnostico direita`, captura regioes calibradas;
- `6 - Testar numero de preparacao`;
- `7 - Testar Undo/Confirm/Continue`;
- `8 - Simular montagem em dry-run`;
- `9 - Simular batalha em dry-run`, observando a tela real;
- `10 - Rodar 1 partida`;
- `11 - Rodar N partidas`;
- `12 - Rodar infinito`;
- `13 - Sair`;
- `14 - Testar envio de mensagem sem mover mouse`.

As opcoes `7`, `10`, `11` e `12` podem clicar de verdade e exigem confirmacao literal no terminal.

## Calibrar

Abra as duas instancias do jogo e deixe o mini-game Bingo visivel. Ao escolher `1` ou `2`, o bot captura a tela inteira e abre uma imagem para selecao visual. Ele nao clica no jogo.

Na janela de selecao:

- para regioes, arraste o retangulo e pressione Enter;
- para botoes, clique no centro do botao e pressione Enter;
- use ESC para cancelar.

Ordem de captura:

- janela inteira do mini-game;
- grade 5x5;
- regiao do numero grande de preparacao;
- regiao do texto de preparacao;
- regiao do texto de turno/rodape;
- area onde o resultado aparecera;
- botoes Undo, Clear e Confirm/Continue.

Notas:

- a area de resultado nao precisa estar mostrando `YOU WIN`, `YOU LOSE` ou `DRAW`; selecione uma area ampla do corpo da janela onde esse texto/imagem aparecera depois;
- `Ready` nao e calibrado como botao separado nesta versao, porque nas referencias ele representa o estado apos confirmar;
- `Ready` usa o mesmo ponto calibrado como `Confirm`;
- `Continue/OK` pode ser separado depois pelo submenu `3 -> 10`.

A calibracao e salva em coordenadas relativas a janela, mas carregada como coordenadas absolutas no runtime. Isso ajuda caso existam monitores com coordenadas negativas.

## Diagnostico

Depois de calibrar um lado, use `4` ou `5` para capturar as regioes configuradas. O bot salva:

- `window.png`;
- `grid.png`;
- `setup_number.png`;
- `setup_text.png`;
- `turn.png`;
- `result.png`;
- `summary.json`.

Os arquivos ficam em `debug/diagnostic_left_DATA_HORA/` ou `debug/diagnostic_right_DATA_HORA/`.

## Templates

Use `3 - Criar/atualizar templates` depois de calibrar as duas instancias.

Templates esperados:

- `assets/setup_numbers/1.png` ate `assets/setup_numbers/25.png`;
- `assets/states/my_turn.png`;
- `assets/states/waiting.png`;
- `assets/states/ready.png`;
- `assets/states/you_win.png`;
- `assets/states/you_lose.png`;
- `assets/states/draw.png`.

Para numeros de preparacao, deixe o numero desejado visivel no jogo antes de capturar. Para `YOU WIN`, `YOU LOSE` e `DRAW`, deixe a tela final visivel na instancia escolhida; o menu pergunta esquerda/direita e abre a `result_region` calibrada para recorte.

Depois de criar templates, use:

- opcao `6` para testar somente o numero atual de preparacao;
- submenu `3`, opcoes `8` e `9`, para testar numero, turno e resultado em uma instancia.
- submenu `3`, opcao `10`, para recalibrar somente o botao `Continue/OK` da tela final.

Em baixa confianca, os detectores retornam `UNKNOWN` ou `NONE` e nenhuma etapa futura deve clicar.

## Montagem Dry-Run

Use `8 - Simular montagem em dry-run` para conferir a montagem planejada sem clique real.

O simulador:

- pergunta qual lado deve vencer;
- pergunta qual instancia simular;
- carrega a calibracao da instancia;
- aplica `WINNER_LAYOUT` ou `LOSER_LAYOUT`;
- calcula os centros das celulas na grade calibrada;
- imprime as acoes que seriam executadas.

Regras da montagem:

- se o numero detectado for o esperado, planeja clicar na celula correta;
- se o numero for `UNKNOWN`, planeja `WAIT`;
- se o numero pular, planeja `UNDO` e reinicia do `1`;
- se exceder `MAX_SETUP_RETRIES`, bloqueia;
- depois do numero `25`, planeja `CONFIRM`.

## Batalha Dry-Run

Use `9 - Simular batalha em dry-run` depois de calibrar e criar templates de turno/resultado.

O simulador:

- pergunta qual lado deve vencer;
- carrega as duas calibracoes;
- detecta turno e resultado nas duas instancias;
- se houver resultado, planeja `continue_both`;
- se exatamente uma instancia estiver em `MY_TURN`, pega o proximo numero de `CALL_SEQUENCE`;
- calcula a celula e o ponto na grade calibrada da instancia ativa;
- imprime a acao planejada sem clicar.

Como essa opcao e dry-run, o simulador nao consome outro numero enquanto a mesma instancia continua com o mesmo turno na tela. Avance o jogo manualmente entre ciclos quando quiser testar a proxima deteccao.

## Entrada De Mouse

O backend de entrada fica em `config.py`:

- `INPUT_BACKEND = "window_message"` usa mensagens do Windows sem mover o mouse real;
- `WINDOW_MESSAGE_METHOD = "send_hover_child"` e o metodo validado no teste `14 -> 5`;
- `FOCUS_BACKEND = "activate_window"` ativa a janela calibrada antes da leitura visual, sem mover o mouse;
- `FOCUS_BACKEND = "right_click"` volta para o foco antigo com clique direito;
- `INPUT_BACKEND = "real_mouse"` volta para o comportamento antigo com `pydirectinput`.

Use a opcao `14 - Testar envio de mensagem sem mover mouse` para validar botoes isolados. O metodo que funcionou no Angels Online foi:

```text
5 - SendMessage hover+click no hwnd sob o ponto alvo
```

Essa opcao pede `TESTAR MENSAGEM`; a frase antiga `TESTAR POSTMESSAGE` tambem continua aceita.

Se algum trecho voltar a depender de foco fisico da janela, troque temporariamente para `INPUT_BACKEND = "real_mouse"` e rode pelo terminal como antes.

## Execucao Real

Antes de usar as opcoes reais, confirme:

- as duas instancias estao calibradas;
- os templates de numero, turno e resultado foram criados;
- a tela esta no mini-game Bingo;
- o backend configurado em `config.py` e o desejado;
- voce sabe que ESC ou Ctrl+C interrompe.

Opcoes reais:

- `7`: testa botoes calibrados na instancia escolhida;
- `10`: roda uma partida;
- `11`: roda uma quantidade definida de partidas;
- `12`: roda ate ESC, Ctrl+C, erro de deteccao ou limite de ciclos da partida.

Se no fim da partida o bot clicar no ponto de `Confirm` em vez de `Continue/OK`, deixe a tela final aberta e use `3 -> 10` para recalibrar o `Continue/OK` da instancia afetada. Isso atualiza apenas `continue_button` no arquivo de calibracao.

As opcoes reais pedem uma frase exata antes de clicar:

- `TESTAR BOTOES`;
- `RODAR UMA PARTIDA`;
- `RODAR N PARTIDAS`;
- `RODAR LOOP INFINITO`.

O runtime:

- monta as duas cartelas de forma intercalada;
- confirma cada cartela quando ela fica completa;
- observa turno/resultado;
- chama os numeros de `CALL_SEQUENCE`;
- clica `Continue/OK` nas duas instancias quando detectar resultado.

Na fase de distribuicao, o bot alterna entre esquerda e direita: coloca um numero em uma instancia, troca para a outra, e volta depois. Isso reduz o risco de reler a mesma imagem antes da UI atualizar e aproveita melhor o backend `window_message`, que nao depende do movimento fisico do mouse.

Antes de cada leitura visual no modo real, o bot ativa a janela calibrada, aguarda `DELAY_AFTER_FOCUS` e so entao captura turno, resultado ou numero de preparacao. Com `FOCUS_BACKEND="activate_window"`, essa ativacao usa Win32 e nao move o mouse real.

Durante a distribuicao, se a tela mostrar exatamente o numero anterior ao esperado, o bot nao usa `Undo` imediatamente. Ele aguarda uma leitura curta e, se o numero anterior persistir, repete o clique daquele numero. `Undo` fica reservado para quando o numero detectado for maior que o esperado, que indica numero realmente pulado.

Depois do numero `25`, o bot nao clica `Confirm` apenas porque planejou o ultimo clique. Ele primeiro valida o estado `READY` pela regiao `setup_text_region`. Se `READY` ainda nao apareceu, repete o clique no `25`; se `READY` nao aparecer apos algumas tentativas, bloqueia com erro claro em vez de ficar tentando confirmar uma cartela incompleta.

Durante a batalha, se o mesmo jogador continuar em `MY_TURN` por alguns ciclos apos uma chamada, o bot repete a ultima chamada sem consumir o proximo numero de `CALL_SEQUENCE`. Se a batalha ainda nao comecou (`seq=0`) e um lado aparece como `UNKNOWN` enquanto o outro esta `WAITING`, o bot tenta clicar `Confirm` novamente no lado `UNKNOWN`.

Ao fim da partida, o bot tambem nao considera o `Continue/OK` concluido apenas pelo clique. Ele clica nas duas instancias, relê a area de resultado, e repete `Continue/OK` somente no lado em que `YOU WIN`, `YOU LOSE` ou `DRAW` ainda estiver visivel.

Em `UNKNOWN` repetido, numero pulado sem recuperacao, resultado ausente ou sequencia esgotada, o bot para em vez de clicar no escuro.

## Configuracao

Edite `config.py` para alterar:

- `WINNER_SIDE`;
- `INPUT_BACKEND`;
- `WINDOW_MESSAGE_METHOD`;
- `FOCUS_BACKEND`;
- `WINNER_LAYOUT`;
- `LOSER_LAYOUT`;
- `CALL_SEQUENCE`;
- limites de retry e delays.
- `SAVE_DEBUG_IMAGES`, que deve ficar `False` para partidas rapidas e `True` apenas para investigar deteccoes.

Os layouts devem conter todos os numeros de `1` a `25`, sem repeticao, em uma matriz 5x5.

## Velocidade

Os delays padrao estao ajustados para execucao rapida pelo terminal. Os principais parametros ficam em `config.py`:

- `DELAY_AFTER_SETUP_CLICK`;
- `DELAY_AFTER_BATTLE_CLICK`;
- `MAX_STALE_TURN_WAITS`;
- `MAX_FINAL_NUMBER_RETRIES`;
- `MAX_READY_RECOVERY_WAITS`;
- `MAX_CONTINUE_RETRIES`;
- `MAX_BATTLE_WAIT_RETRIES`;
- `DELAY_AFTER_FOCUS`;
- `LOOP_INTERVAL`;
- `MOVE_DURATION`;
- `CLICK_HOLD`.

`SAVE_DEBUG_IMAGES=False` evita salvar imagens a cada ciclo real, o que reduz bastante I/O em disco. Os diagnosticos do menu continuam salvando imagens quando chamados manualmente.

## Estrategia

O bot trabalha com duas cartelas:

- `WINNER_LAYOUT`: cartela favoravel para a conta escolhida para vencer;
- `LOSER_LAYOUT`: cartela desfavoravel para a outra conta.

Durante a batalha, cada turno consome o proximo numero de `CALL_SEQUENCE`. O numero chamado e mapeado para a celula correta na cartela da instancia ativa.

## Seguranca

Regras operacionais:

- dry-run por padrao;
- nunca clicar em `UNKNOWN`;
- nao seguir apos erro de setup;
- limitar retries;
- salvar evidencias em `debug/`;
- usar `window_message` por padrao ou `pydirectinput` quando for necessario mover o mouse real;
- uma acao por ciclo.

## Compilar

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Compile:

```powershell
.\build_exe.bat
```

O executavel fica em:

```text
dist/BingoBot/BingoBot.exe
```

Use o modo `onedir`, nao `onefile`, porque `assets`, `calibration` e `debug` precisam continuar editaveis ao lado do executavel.

Em outra maquina, copie a pasta `dist/BingoBot/`, abra o executavel e calibre novamente as duas instancias nessa maquina.

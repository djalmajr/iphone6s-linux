# Console na tela do iPhone

## Contexto

Em 2026-09-29, o Linux ativo expôs `simpledrmdrmfb`, `/dev/fb0`, resolução 750 × 1334, pixels `x8r8g8b8` e stride 3008 bytes. O framebuffer estava em blank 4, e apenas o console serial estava ativo. A ativação com `echo 0 > /sys/class/graphics/fb0/blank`, uma escrita em `/dev/tty1` e `chvt 1` provocou `fbcon: Taking over console`. O usuário confirmou visualmente o texto na tela.

## Plano desta etapa

Arquivos: `build-runtime.py`, `init-server`, `iphone-linux.sh` e este documento.

- [x] Confirmar driver, estado da tela e texto visível sem reiniciar.
- [x] Incluir o utilitário `script` oficial do Ubuntu e suas bibliotecas no runtime.
- [x] Adicionar `start-console`, que ativa tty1 e mostra estado inicial.
- [x] Oferecer `iphone-linux.sh console`: Bash digitado no Mac com saída também na tela do telefone.
- [x] Testar o comando no Linux ativo e reconstruir a candidata.
- [x] Documentar evidências e publicar a branch para revisão: PR #1.

## Decisão

Mostrar um console de texto com framebuffer já suportado pelo kernel, dispensando GUI e touchscreen. A ativação funciona na sessão atual; o boot da imagem integrada foi confirmado posteriormente nesta mesma data. Reverter: sair do shell e desativar a tela com `echo 4 > /sys/class/graphics/fb0/blank`; isso não encerra SSH.

O console pode expor na tela comandos e resultados. Não usar o espelhamento para digitar credenciais. O arquivo de destino de `script` é o dispositivo tty1; não se cria um log persistente dos comandos.

## Operação

```bash
cd iphone-linux-tools
bash iphone-linux.sh console
```

Digite no Terminal do Mac. Os comandos e a saída do Bash aparecem também na tela física do iPhone. `exit` fecha esse shell; os serviços SSH, HTTP e Herdr permanecem. `shell` continua disponível para uma sessão apenas no Mac. O espelhamento usa `script` do util-linux 2.39.3, pacote Ubuntu `2.39.3-9ubuntu6.6`, copiado com suas bibliotecas a partir da VM. Nenhum pacote foi instalado no Mac.

## Evidências desta rodada

- Framebuffer passou de blank 4/DRM disabled para blank 0/DRM enabled.
- Driver registrou `fbcon: Taking over console` e console de 93 × 83 caracteres.
- Usuário confirmou visualmente o texto inicial e depois `CONSOLE_BASH_OK` e `7.0.12` digitados pelo Mac.
- Shell interativo retornou kernel 7.0.12 e uptime de 1h05; `exit` encerrou normalmente.
- Runtime instalado por USB após verificação SHA-256; imagem candidata reconstruída e VM parada.
- Candidata `m1n1-linux-iphone6s-console-server.bin`: 23.767.809 bytes, SHA-256 `c49e03822e164767424d1ac786c3b00eec731de66acec497915c2cc83a39ee4a`. Boot confirmado no teste abaixo.

A imagem e seu initramfs contêm a chave privada do servidor SSH e permanecem ignorados pelo Git. A ativação do console foi testada tanto na sessão existente quanto automaticamente no novo boot. A imagem original e a candidata anterior permanecem preservadas.

## Novo boot da imagem integrada — 2026-09-29

- [x] Preservar `/root` da sessão anterior em um tar privado no Mac.
- [x] Reiniciar, entrar em recuperação e executar novo DFU físico.
- [x] Confirmar checkm8/PongoOS e carregar 23.767.809 bytes da imagem integrada.
- [x] Confirmar SSH, Bash, HTTP e utilitário de console sem reinstalar runtime.
- [x] Receber confirmação visual do usuário de que o console apareceu sozinho.
- [x] Iniciar o servidor Herdr dedicado e executar `POST_BOOT_HERDR_OK` dentro do painel.

O `reboot` comum só sinaliza init; nesta imagem mínima foi necessário `sync; busybox reboot -f`. O boot voltou inicialmente ao iOS, e o palera1n o levou a recuperação. Após DFU, PongoOS carregou a nova imagem. `pongoterm` reportou timeout USB após o envio, mas o Linux reapareceu no USB e os serviços foram verificados: esse erro isolado não significou falha de boot.

O Mac pediu novamente autenticação para o alias IP USB. O init iniciou SSH e HTTP diretamente; nenhum servidor de transferência ou `install-terminal` foi usado após o novo boot. `fbcon` assumiu a tela cerca de 1,34 s após iniciar o kernel. Herdr estava instalado, mas seu servidor/sessão foi iniciado posteriormente pelo Mac; não é um daemon automático do init atual.

Evidência: [console-cold-boot.txt](evidence/console-cold-boot.txt). O tar privado de `/root` fica em `runtime/phone-root-before-console-boot.tar.gz`, fora do Git. Ele preserva arquivos/configuração, não processos nem sockets.

### Repetir

`bash iphone-linux.sh boot` agora seleciona a imagem integrada verificada. `boot-probe` seleciona a imagem original e restaura seu runtime pelo Mac. O wrapper completo ainda não foi executado de ponta a ponta desde um reboot; nesta rodada o boot foi conduzido manualmente com os mesmos componentes, e o comando `boot` foi verificado somente com a sessão já ativa.

O `boot` não reinicia um Linux já rodando: verifica SSH/HTTP e mantém a sessão. Em caso de reinício, ainda são necessários Mac, cabo USB-A → Lightning e botões físicos para DFU. A imagem anterior permanece disponível.

## Boot e troca de cabo — 2026-09-30

A tentativa com USB-C frontal entrou em DFU, mas a exploração terminou com timeout de reconexão antes de PongoOS. O wrapper passou a reconhecer essa falha, encerrar o guia que iniciou e impedir o envio do payload. O teste de integração local confirmou esses três resultados com um guia simulado; depende dos artefatos privados para validar seus hashes e é omitido quando eles não estão disponíveis.

Com USB-A → Lightning na porta traseira, PongoOS apareceu. Uma corrida entre o fim do processo e a enumeração USB provocou uma interrupção incorreta do wrapper; o tratamento foi corrigido para aguardar a enumeração após DFU. Foi então executado `boot` novamente com PongoOS já ativo: a imagem integrada iniciou, SSH autenticado e HTTP responderam, e o operador confirmou o console.

Essa execução ocorreu em duas etapas e **não comprova ainda o wrapper completo em um único boot frio** (#3). Não houve reinstalação do runtime. Depois, o operador trocou para outro cabo USB-C → Lightning na porta frontal: o console permaneceu e SSH/HTTP continuaram acessíveis após configurar novamente apenas o alias USB no Mac. Isso demonstra continuidade da sessão, não carga sustentada da bateria (#2).

### Execução completa e retirada do contador

Na tentativa seguinte, ainda nesta data, o wrapper completou uma única execução desde iOS/recuperação até o Linux, com saída 0, SSH autenticado, HTTP 200 e `simpledrmdrmfb` em blank 0. O uptime inicial foi 123,09 s. O usuário relatou conseguir fazer a sequência manualmente e pediu a retirada do contador e das páginas de apoio.

O protótipo `dfu_visual.py` foi então removido. `dfu_boot.py` acompanha a enumeração DFU e o processo pelo terminal, sem navegador, contador ou servidor HTTP de apoio. O wrapper conserva a espera por PongoOS e a interrupção antes do envio em caso de falha. Uma pasta privada `runtime/dfu-active` impede dois monitores simultâneos deste checkout; é removida ao encerrar normalmente. Se restar após interrupção abrupta, confirmar que não há execução ativa antes de remover esse diretório.

Os 15 testes locais passaram, incluindo retomada apenas após DFU simulado e encerramento do processo filho. A saída do monitor fica em log privado ignorado pelo Git.

Na tentativa seguinte, a versão sem contador também completou uma única execução com saída 0: DFU manual, PongoOS, upload da imagem integrada, alias USB, SSH e HTTP 200. O usuário confirmou console Linux e aparelho frio/morno. Foi observado Linux 7.0.12, uptime 46,12 s e framebuffer blank 0. O monitor encerrou e removeu sua pasta de estado; nenhum servidor HTTP de apoio foi iniciado. Isso conclui a validação física do wrapper (#3), sem encerrar a investigação de alimentação (#2).

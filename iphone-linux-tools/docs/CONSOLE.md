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
- [ ] Documentar evidências e publicar a branch para revisão.

## Decisão

Mostrar um console de texto com framebuffer já suportado pelo kernel, dispensando GUI e touchscreen. A ativação funciona na sessão atual; o boot da candidata permanece uma checagem separada. Reverter: sair do shell e desativar a tela com `echo 4 > /sys/class/graphics/fb0/blank`; isso não encerra SSH.

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
- Candidata `m1n1-linux-iphone6s-console-server.bin`: 23.767.809 bytes, SHA-256 `c49e03822e164767424d1ac786c3b00eec731de66acec497915c2cc83a39ee4a`. Construída, ainda sem teste de boot.

A imagem e seu initramfs contêm a chave privada do servidor SSH e permanecem ignorados pelo Git. A ativação do console foi testada na sessão existente, não durante o boot da candidata. A imagem original e a candidata anterior permanecem preservadas.

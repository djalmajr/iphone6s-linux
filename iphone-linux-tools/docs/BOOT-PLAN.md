# Boot experimental de Linux no iPhone 6s

## Contexto

O aparelho é um iPhone 6s `iPhone8,1` com A9 Samsung S8000. O toque falha mesmo após a atualização para iOS 15.8.8. O usuário quer Linux no próprio telefone e autorizou alterações locais nele, sem alterar contas ou serviços remotos e sem instalar ferramentas inseguras no Mac.

## Arquivos

- `STATUS.md`: fatos do aparelho, hashes e resultado de cada tentativa.
- `scripts/boot/dfu_boot.py`: monitor USB para DFU manual, sem página ou contador. O protótipo visual foi removido a pedido do operador.
- `artifacts/Pongo.bin`, `bin/pongoterm`, `artifacts/m1n1-linux-iphone6s.bin`: cadeia de boot Hoolock já preparada (caminhos relativos a `iphone-linux-tools`).

## Detalhes

- O boot documentado é DFU → PongoOS → m1n1 → kernel/initramfs Linux; no A9, este teste usa RAM e depende do Mac. Não executar fakefs, particionamento nem restauração de fábrica nesta etapa.
- A USB-C frontal passa por um hub interno; a USB-C traseira foi testada e o iPhone aparece diretamente sob `AppleT8112USBXHCI@03000000`.
- A finalização do iOS terminou e o usuário conseguiu digitar o PIN. A tela de configuração do iOS não é necessária para o boot Linux.
- DFU de hardware exige tela preta e USB `05ac:1227`. Tela de cabo é recovery. Cabo USB-C–Lightning pode falhar; se o teste traseiro não funcionar, usar USB-A–Lightning numa das USB-A traseiras.
- O payload probe original oferece Telnet sem autenticação para bootstrap isolado. A imagem integrada atual inicia SSH por chave e HTTP automaticamente; a LAN e operação contínua continuam pendentes.

## Tarefas

- [x] Conferir modelo, fontes, hashes e ferramentas já presentes.
- [x] Comparar pesquisa própria com Grok e agy Gemini 3.8 Flash Medium; corrigir sugestões inseguras de fakefs.
- [x] Trocar da USB-C frontal para a traseira e confirmar o novo caminho USB.
- [x] Aguardar a finalização do iOS e colocar o iPhone em recovery sem precisar do toque.
- [x] Tentar DFU guiado pela USB-C traseira e confirmar que permaneceu em Recovery Mode, não em DFU.
- [x] Repetir com cabo USB-A–Lightning na USB-A traseira: DFU e PongoOS confirmados em 2026-09-29.
- [x] Carregar o payload Linux em RAM; confirmar gadget USB, terminal, modelo e `uname`.
- [x] Servir um painel HTTP no endereço USB do iPhone e verificar a resposta real.
- [x] Preparar comandos locais para terminal e repetição do serviço; testar `status`, `shell` e `serve`.
- [x] Registrar o resultado da tentativa com USB-C traseira e o limite atual para operação como servidor.

- [x] Instalar e verificar Bash, SSH por chave e Herdr no telefone; encerrar Telnet após validação.
- [x] Construir candidata com terminal integrado, preservando a original.
- [x] Documentar Multipass, builds, falhas, insumos e evidências para reprodução.
- [x] Testar novo boot completo da candidata pelo wrapper sem contador: saída 0, SSH/HTTP e console confirmados em 2026-09-30 (#3).
- [x] Restaurar snapshot em novo boot e verificar conteúdo, modo, identidade SSH e arquivos extras (#4).

## Verificação

`ioreg -p IOUSB -w0` e `idProduct` distinguem recovery de DFU; o log de palera1n confirma PongoOS; `pongoterm` envia o payload; interface USB e `uname -a` confirmam Linux. Nenhum pacote é instalado no Mac, nenhum dado remoto é alterado e nenhuma operação de disco do iPhone é feita nesta etapa.

## Decisões e alternativas

**D1 — Boot RAM dependente do Mac.** Escolhido por ser o caminho documentado para A9 e dispensar a tela defeituosa. Instalação autônoma no armazenamento interno não está documentada neste modelo; servidor sobre iOS foi descartado pelo usuário. Reversão: reinício do aparelho, desde que o iOS local permaneça íntegro. Status: em curso.

**D2 — Porta traseira antes de trocar cabo.** A tentativa com USB-C traseira retornou a Recovery Mode. A troca para USB-A–Lightning foi seguida por DFU, PongoOS e Linux confirmados em 2026-09-29. Reversão: trocar o cabo. Status: aplicada.

**D3 — Primeiro serviço limitado ao USB e à RAM.** O servidor BusyBox HTTP usa `172.16.42.1:8080`; o terminal usa o mesmo enlace USB. A interface dedicada do Mac recebeu apenas o alias temporário `172.16.42.2/24`. O armazenamento interno e a leitura da bateria não apareceram no Linux atual. Reversão: reiniciar o telefone e remover o alias com `bash scripts/host/iphone-linux.sh disconnect` enquanto o dispositivo estiver conectado. Status: aplicada e verificada; boot autônomo e armazenamento interno continuam indisponíveis. Persistência de arquivos por snapshots no Mac foi validada.

Fontes: [HoolockLinux](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP_pongoOS.md), [suporte de armazenamento](https://github.com/HoolockLinux/docs/blob/master/tools/README.md), [palera1n](https://github.com/palera1n/palera1n/blob/main/README.md), [DFU](https://theapplewiki.com/wiki/DFU_Mode).

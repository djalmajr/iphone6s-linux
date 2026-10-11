# Userspace Wi-Fi N71 sem novo boot

## Contexto

O goal Wi-Fi/energia está aprovado. A imagem de calibração real contém BusyBox, mas não iw, wpa_supplicant ou wpa_cli; a VM dedicada também não tem esses programas. O kernel/radio ainda aguardam a coleta física. Preparar as ferramentas agora evita uma futura reinicialização por falta de userspace. Não iniciar rádio, associação, DHCP ou serviço no Mac/VM durante esta preparação.

## Decisão D43

Preparar um pacote ARM64 isolado de iw/wpa_supplicant/wpa_cli e suas bibliotecas, extraído de pacotes oficiais Ubuntu autenticados. Usar seu próprio loader e library-path no telefone, sem substituir /lib, Bash, SSH ou as identidades da imagem funcional. A transferência e os comandos de rede serão explícitos por SSH no mesmo boot, depois que o driver expuser uma interface. A associação precisará de uma rede autorizada; não ler ou publicar senha nesta fase.

## Arquivos e fases

1. Aquisição privada na VM: diretório novo /home/ubuntu/n71-wifi-userspace-source-20261010, APT lists/cache/sources próprios, Ubuntu noble/updates/security via HTTPS e keyring existente conferido. Usar somente update/download/consulta, sem install, postinst ou serviço. Salvar InRelease, fingerprints, versões, tamanhos/SHA e o status dpkg antes/depois. Recusar metadados/pacotes não autenticados. Não alterar fontes, chaves ou pacotes globais da VM ou do Mac. A tentativa inicial falhou por DNS; curl com --resolve e validação TLS retornou HTTP200. Para o APT, bind de hosts privado somente em mount namespace filha da VM, propagação privada e execução com UID ubuntu. Conferir /etc/hosts e status dpkg antes/depois; não alterar o resolver global.
2. Após conhecer os inputs reais, implementar até três executáveis: scripts/build/n71_wifi_userspace.py, scripts/build/build-n71-wifi-userspace.py e tests/test_n71_wifi_userspace.py. O builder offline deve exigir Linux/aarch64, inputs fixados, output novo privado, nomes/caminhos/ELF/closure controlados. Extrair somente dados regulares necessários; resolver links apenas dentro dos dados autenticados e criar pacote final sem links/scripts de manutenção. Sem rede ou instalação pelo builder.
3. Qualificar ABI ELF64/AArch64, DT_NEEDED/loader e closure real na VM, executar somente versão/help sem inicializar rede, e provar recusas de hash/path/closure/overwrite em cópias descartáveis. Não executar ELF Linux no Mac. AST/lint fatal e testes/mutações relevantes; declarar ausência de typechecker Python. Os gates I2C/kernel/runtime não afetados permanecem válidos.
4. Documentar reprodução, versões, origem, licença, SHA e limitações; publicar scripts/evidência sanitizada na branch autorizada. Binários/archives/libraries/logs/credenciais permanecem privados. Concluir a issue de preparação somente com aceite local/CI; não usar isso como prova de Wi-Fi físico.
5. Quando houver SSH/radio na sessão agrupada, conferir pacote antes/depois do envio e executar por loader isolado. Associar somente à rede autorizada, conservar o enlace USB e a configuração do Mac, registrar prova física e salvar snapshot/cleanup. Não pedir confirmação de tela/cabo/temperatura.

## Tarefas

- [x] Confirmar a falta dos programas na imagem e na VM reais.
- [x] Autenticar e congelar os pacotes oficiais e suas dependências:38 debs,11.638.132 bytes, três InRelease verificados e SHA/bytes reais conferidos; nenhuma instalação ou execução do conteúdo.
- [ ] Implementar builder offline e recusa de misturas/paths inválidos.
- [ ] Qualificar pacote ARM64 isolado e execução real sem rede.
- [ ] Publicar reprodução e gates sanitizados.
- [ ] Integrar/testar no mesmo boot físico do rádio, sem ampliar o aceite offline.

## Verificação

APT authenticates Release→Packages→deb; comparar arquivos reais com os SHA/bytes do índice autenticado. Verificar o keyring existente e não aceitar allow-unauthenticated/trusted=yes. O status dpkg deve permanecer idêntico; nenhum maintainer script roda. Prova sintética testa guards; versão/help e closure real comprovam execução/embalagem no ARM64, sem provar driver, associação, IRQ/DMA ou carga física. O telefone continua dependente do DFU já solicitado para a parte física.

Fontes primárias: [apt-get noble](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html), [apt-secure noble](https://manpages.ubuntu.com/manpages/noble/man8/apt-secure.8.html), [wpa_supplicant](https://w1.fi/wpa_supplicant/).

## Resultado da aquisição

iw 6.7-1build1 e wpasupplicant 2:2.10-21ubuntu0.4, arquitetura arm64. O plano de dependências com status dpkg vazio selecionou38 pacotes; todos foram adquiridos por apt-get download com versões explícitas e conferidos contra o índice autenticado. A variante download-only install foi recusada pelo lock frontend fora do cache; não foi elevada nem usada para instalar. Hosts/status dpkg globais ficaram iguais e a namespace encerrou. Receipts/logs/scripts exatos privados em runtime/n71-wifi-userspace-source-20261010 e na pasta equivalente /home/ubuntu da VM. Manifesto/evidência sanitizados em docs/evidence; builder/ELF/closure/execução real e rádio ainda pendentes.

# Reprodução e análise do Linux no iPhone 6s

Atualizado em 2026-09-30. Este documento reúne o procedimento, os artefatos preservados, os comandos comprovados e as lacunas. Os comandos locais abaixo partem de `~/iphone6s-linux/iphone-linux-tools`. Em um clone novo, crie os destinos privados antes de baixar ou transferir arquivos:

```bash
cd ~/iphone6s-linux/iphone-linux-tools
mkdir -p bin artifacts keys runtime backups logs
chmod 700 keys runtime backups logs
```

## 1. Escopo e estado atual

O usuário autorizou alterações locais e perda dos dados do iPhone; contas e serviços remotos ficam fora do escopo. Nenhum pacote foi instalado no macOS. Pacotes de construção foram instalados somente na VM isolada `iphone6s-build`.

Hardware: iPhone 6s, `iPhone8,1`, placa `N71AP`, A9 Samsung S8000, armazenamento nominal de 32 GB. Host: Mac Studio M2 Max, `Mac14,13`. Linux verificado: kernel postmarketOS 7.0.12, ARM64, páginas de 16 KB, dois processadores e 1.973 MiB de RAM.

Funciona no aparelho: boot Linux em RAM, rede NCM por USB, HTTP, Bash 5.2.21, SSH Dropbear por chave e Herdr 0.9.1. O servidor Herdr e o painel sobreviveram ao fechamento da conexão SSH. Nenhum agente de IA, conta ou credencial de provedor foi instalado no telefone.

Não estabelecido: armazenamento interno, Wi-Fi, leitura de bateria, temperatura, carga sustentada, boot autônomo e estabilidade prolongada. Em 2026-09-30, a árvore reorganizada completou o wrapper desde um reinício e o novo CLI restaurou a sentinela em um boot seguinte. A imagem integrada com console, Bash, SSH e HTTP deu boot no aparelho; o usuário confirmou que o console apareceu sozinho. Veja seção 17.

## 2. Linha do tempo e decisões

### Diagnóstico e preparação — 2026-09-27

- O usuário relatou pouca autonomia e toques fantasmas. Diagnóstico anterior reportou 1.462 ciclos de bateria. Esse número é histórico; não foi medido pelo Linux.
- Os toques continuaram com o cabo desligado. O vídeo da Calculadora mostrou teclas sendo acionadas sem contato e artefatos próximos à parte inferior. A ausência de artefatos durante a maçã não isolou software versus hardware.
- O Home respondia à pressão prolongada abrindo Siri, mas Siri não executava os comandos tentados.
- Várias sequências de DFU com USB-C → Lightning terminaram em maçã ou desenho de cabo. Recuperação funcionou, DFU não.
- Foi preparada a cadeia HoolockLinux: DFU → checkm8 → PongoOS → m1n1 → kernel/DTB/initramfs. Foi usada uma VM Multipass para o initramfs ARM64 e módulos USB.
- CleanMyMac classificou `palera1n-macos-arm64` como jailbreak/riskware. O binário foi obtido da distribuição oficial e seu SHA-256 comparado ao digest oficial. Essa comparação prova a origem do artefato distribuído; não é uma auditoria integral do código.
- A atualização oficial pelo Finder, opção **Atualizar**, reinstalou o iOS 15.8.8. O usuário digitou o PIN e concluiu a instalação. O toque continuou defeituoso. Não foi feita restauração completa/apagamento pelo Finder.
- O cabo USB-C foi movido da porta frontal à USB-C traseira. O caminho USB passou de um hub ASMedia para `AppleT8112USBXHCI@03000000`; ainda assim, a tentativa sincronizada reportou `Whoops, device did not enter DFU mode`.
- O guia e o cliente foram encerrados; `palera1n -n` retirou o telefone da recuperação, e iOS 15.8.8 foi confirmado.
- Foram consultados advisors Grok e Gemini pelo Herdr, e as conclusões comparadas a fontes primárias. Sugestões de fakefs/particionamento A11 foram rejeitadas. Ambos os métodos documentados do Hoolock ainda exigiam DFU físico.
- Um adaptador na ponta do mesmo cabo USB-C não comprovou solucionar o problema. Não foi afirmado que o cabo era a única causa possível.

### Primeiro boot Linux — 2026-09-29

- O usuário trocou para um cabo verdadeiro **USB-A → Lightning**, ligado à porta USB-A traseira do Mac.
- A cópia local do palera1n estava ausente. Foi baixada novamente a versão oficial v2.4; tamanho e digest da API GitHub foram conferidos antes de executar.
- `dfu_visual.py` colocou o telefone em recuperação e abriu uma página local. O usuário iniciou a contagem e pressionou Power + Home por 4 segundos, depois apenas Home por 10 segundos.
- O log confirmou `Device entered DFU mode successfully`, `Checkmate!` e `Booting PongoOS...`. O USB identificou `PongoOS USB Device`.
- O guia foi encerrado após PongoOS, como permitido no procedimento upstream.
- `pongoterm` enviou 11.700.549 bytes do payload original e executou `bootm`.
- Após a reconexão, apareceu `iPhone 6s Linux probe`, com interface NCM `en12` no Mac. A tela ficou preta, conforme relato do usuário.
- O macOS recebeu um alias temporário `172.16.42.2/24` somente nessa interface. `sudo -n` pediu senha; o comando foi autorizado no diálogo padrão do macOS via AppleScript. Nenhuma senha foi coletada no chat.
- O shell retornou kernel, modelo e RAM reais. O telefone usa `172.16.42.1/24`. A rota ao telefone foi confirmada por `en12`.
- BusyBox HTTP passou a servir o painel em `172.16.42.1:8080/cgi-bin/status`.

### Terminal Bash, SSH e Herdr — 2026-09-29

- Foi iniciado apenas `iphone6s-build`, que estava parado. Configuração observada: Ubuntu 24.04 LTS ARM64, 6 vCPUs e aproximadamente 8 GiB RAM. O disco e a imagem-base estão no snapshot JSON de evidência.
- A resolução de `ports.ubuntu.com` falhou dentro da VM. O Mac resolveu o domínio. Um mapeamento temporário para `91.189.91.102`, identificado por `# iphone-build-temporary`, foi adicionado somente ao `/etc/hosts` da VM.
- `apt-get update` verificou os índices pelos keyrings do Ubuntu; `apt-get install --no-install-recommends dropbear-bin ncurses-base bash` preparou o runtime. Não foram iniciados daemons SSH da VM por esse procedimento.
- Foi escolhido Herdr 0.9.1 para coincidir com a versão do Mac. O artefato oficial `herdr-linux-aarch64` teve seu digest SHA-256 conferido na release. ELF estático, segmentos alinhados a 64 KB: compatível com as páginas de 16 KB usadas neste kernel. Execução real no telefone confirmou a compatibilidade.
- Uma chave cliente Ed25519 dedicada foi gerada em `keys/`. Somente a chave pública foi enviada à VM/telefone. A chave do servidor foi criada na VM e preservada no pacote; `keys/known_hosts` foi preenchido com essa chave pública, antes da conexão.
- `scripts/build/build-runtime.py` empacotou Bash, Dropbear, bibliotecas detectadas por `ldd`, terminfo, Herdr, contas mínimas e scripts de inicialização.
- O pacote foi servido temporariamente pelo Mac, **somente em `172.16.42.2:8766`**. O telefone baixou, verificou SHA-256 e extraiu na RAM. O servidor de transferência foi encerrado.
- O primeiro SSH foi recusado porque o tar conservava UID 1000 da VM. A propriedade foi corrigida no telefone e no filtro do tar, agora UID/GID 0. As permissões das chaves também são conferidas no startup.
- Bash precisava de `/sbin`, `/usr/bin` e `/usr/sbin` existentes para os links BusyBox. Foram criados e incluídos no runtime.
- Foi aberto Herdr pela conexão SSH com PTY, na sessão exclusiva `iphone-linux`. Uma checagem dentro do painel retornou `HERDR_PHONE_OK` e Bash 5.2.21. A conexão de teste foi fechada; servidor e painel continuaram ativos.
- O Telnet sem senha foi encerrado somente após confirmar o SSH. `scripts/host/iphone-linux.sh` passou a usar SSH para os comandos e a reinstalar o runtime após um boot da imagem original.
- Foi construída uma imagem candidata `m1n1-linux-iphone6s-server.bin`, preservando a original. A candidata não foi carregada no telefone nesta rodada.

## 3. Artefatos, origem e limites de proveniência

`artifacts.json` registra SHA-256 e tamanho dos arquivos locais. Ele não inclui conteúdo de chaves. `runtime/SHA256SUMS` registra o pacote específico desta construção.

| Artefato | Origem/uso |
|---|---|
| `bin/palera1n-macos-arm64` | Release oficial v2.4, `https://github.com/palera1n/palera1n/releases/download/v2.4/palera1n-macos-arm64`; SHA-256 `950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9` |
| `artifacts/herdr-linux-aarch64` | Release oficial v0.9.1; SHA-256 `f4ccf4de745f2cb9a39a983e9ba3703dad50ec2a58dea83026ceab721bbd8d9e` |
| `artifacts/linux-postmarketos-apple-16k-7.0.12-r0.apk` | Kernel ARM64 pré-compilado; não compilamos o kernel. Novo download com HTTPS obrigatório corresponde ao preservado; controle e dados autenticados por índice oficial assinado. [Procedimento e limites](KERNEL-VERIFY.md), [identidade](evidence/kernel-package-provenance.json). `.PKGINFO` declara `commit = -dirty`; assinatura própria não verificada |
| `artifacts/vmlinuz-apple-16k`, `artifacts/s8000-n71.dtb`, módulos `.ko.zst` | Extraídos do APK preservado; caminhos internos abaixo |
| `artifacts/Pongo.bin`, `artifacts/m1n1.bin`, `bin/pongoterm` | Insumos preservados da primeira preparação, usados no boot confirmado. Clones locais: Hoolock `23ebe1fbc375599221553a7e1815e5de182a6b42`; PongoOS `4c9b7541629234147fcc778f0ce4162482aaccef`. Os comandos originais completos não foram recuperados |
| m1n1 reconstruído de clone novo na VM existente | HEAD `d5a10ac52a6468484854419a6c5130f1d62073eb`, fetch com profundidade 1 e sem tags, build offline: saída idêntica ao `m1n1.bin` preservado. [Receita e limites](M1N1-BUILD.md), [inventário original/CI](evidence/m1n1-source-provenance.json), [prova do rebuild](evidence/m1n1-rebuild.json) |
| `artifacts/iphone6s-initramfs.gz` | Initramfs mínimo original, criado na VM com BusyBox estático e módulo NCM |
| `artifacts/m1n1-linux-iphone6s.bin` | Payload original que deu boot; SHA-256 `7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520` |
| `runtime/iphone6s-runtime.tar.gz` | Bash, Dropbear, bibliotecas e Herdr, mais chave privada **do servidor**; proteger este arquivo |
| `artifacts/iphone6s-server-initramfs.gz` / `artifacts/m1n1-linux-iphone6s-server.bin` | Candidatos com o runtime incluído; construídos, ainda sem prova de boot no telefone |

Lacunas importantes: o comando original de criação da VM não foi recuperado; o snapshot descreve seu estado real. O APK foi baixado novamente com HTTPS obrigatório e teve controle/dados autenticados pelo índice oficial assinado, mas a assinatura própria e o commit imutável do kernel permanecem pendentes. O endpoint original `master` tenta redirecionar para HTTP; usar a rota HTTPS equivalente registrada em [KERNEL-VERIFY.md](KERNEL-VERIFY.md), sem permitir downgrade. m1n1 foi reconstruído byte por byte em clone novo, na VM e cache existentes; falta a prova da imagem completa em VM nova. O binário do CI upstream tem diferenças dentro de `.rodata`, incluindo referências a outro compilador Rust; não foi selecionado nem carregado no telefone. O HEAD de PongoOS não prova sozinho a origem do binário Pongo usado. Preservar os artefatos e hashes permite repetir o boot já confirmado; não equivale a uma reconstrução integral a partir de commits imutáveis. Não preencher essas lacunas com versões atuais presumidas.

## 4. Preparar um ambiente equivalente

Os comandos de criação abaixo são uma receita equivalente, não uma transcrição da criação original. Não execute `launch` se a VM já existir:

```bash
multipass launch 24.04 --name iphone6s-build --cpus 6 --memory 8G --disk 25G
multipass start iphone6s-build
multipass info iphone6s-build --format json
multipass exec iphone6s-build -- sudo apt-get update
multipass exec iphone6s-build -- sudo apt-get install -y --no-install-recommends busybox-static cpio zstd file bash dropbear-bin ncurses-base
```

O `launch` novo resolve a imagem disponível naquele momento. Para análise histórica, compare com o `image_hash` em `evidence/multipass-build.json`. Os pacotes atuais podem ter versões diferentes; consulte `evidence/ubuntu-package-versions.txt` para a construção desta rodada.

Se DNS falhar na VM, diagnostique antes de alterar qualquer coisa. O contorno desta sessão foi temporário no `/etc/hosts` da VM, para o domínio oficial; não fixe permanentemente o IP usado aqui. O arquivo foi limpo ao terminar a construção.

## 5. Extrair kernel, DTB e módulos do APK preservado

No Mac, em uma pasta de extração separada:

```bash
tar -tf artifacts/linux-postmarketos-apple-16k-7.0.12-r0.apk
tar -xOf artifacts/linux-postmarketos-apple-16k-7.0.12-r0.apk .PKGINFO
```

Caminhos internos confirmados:

```text
boot/vmlinuz
boot/dtbs/apple/s8000-n71.dtb
usr/lib/modules/7.0.12/kernel/drivers/usb/gadget/function/usb_f_ncm.ko.zst
usr/lib/modules/7.0.12/modules.dep
```

O kernel local recebeu o nome `artifacts/vmlinuz-apple-16k`. O DTB é específico da variante Samsung N71; não substituir pelo DTB de outra variante. Na VM, `zstd -d usb_f_ncm.ko.zst` produz o módulo usado pelo `scripts/build/build-initramfs.sh`. Kernel e módulo precisam corresponder; não misture releases.

## 6. Reconstruir o initramfs original

`scripts/build/build-initramfs.sh` documenta os arquivos e caminhos originais na VM. Envie `phone/init/init` como `/home/ubuntu/init-iphone6s`, o módulo descomprimido para `/home/ubuntu/iphone6s-modules/usb_f_ncm.ko` e o script para a VM. Depois:

```bash
multipass transfer phone/init/init iphone6s-build:/home/ubuntu/init-iphone6s
multipass transfer scripts/build/build-initramfs.sh iphone6s-build:/home/ubuntu/build-initramfs.sh
multipass transfer artifacts/usb_f_ncm.ko.zst iphone6s-build:/home/ubuntu/usb_f_ncm.ko.zst
multipass exec iphone6s-build -- mkdir -p /home/ubuntu/iphone6s-modules
# zstd recusa sobrescrever um módulo existente; use o existente se já foi conferido.
multipass exec iphone6s-build -- zstd -d /home/ubuntu/usb_f_ncm.ko.zst -o /home/ubuntu/iphone6s-modules/usb_f_ncm.ko
multipass exec iphone6s-build -- bash /home/ubuntu/build-initramfs.sh
multipass transfer iphone6s-build:/home/ubuntu/iphone6s-initramfs.gz artifacts/iphone6s-initramfs-rebuilt.gz
```

Use um destino novo para conservar a imagem comprovada. Cpio, metadados e timestamps podem produzir bytes diferentes; essa receita reproduz a estrutura funcional, não promete hash idêntico a cada execução. O original permanece disponível localmente; binários e imagens não são distribuídos neste repositório.

O init monta proc/sysfs/devtmpfs/devpts/configfs, configura o gadget NCM, atribui `172.16.42.1/24` e abre um shell Telnet somente nesse endereço. Esse é o bootstrap original, ainda acessível por `boot-probe`. A imagem integrada padrão usa `phone/init/init-server` e inicia SSH por chave diretamente, sem Telnet.

## 7. Montar o payload m1n1

A ordem exata foi confirmada comparando a concatenação com o arquivo original, byte por byte:

```text
m1n1.bin
chosen.bootargs=rdinit=/init console=ttySAC0,115200 loglevel=7 + newline
s8000-n71.dtb
vmlinuz-apple-16k
iphone6s-initramfs.gz
```

```bash
python3 scripts/build/compose-payload.py artifacts/iphone6s-initramfs.gz artifacts/m1n1-linux-reproduzido.bin
shasum -a 256 artifacts/m1n1-linux-reproduzido.bin
```

Com os insumos originais preservados, a concatenação reproduziu exatamente `7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520`. O utilitário recusa sobrescrever um destino que tenha conteúdo diferente.

## 8. Repetir o boot confirmado

```bash
cd ~/iphone6s-linux/iphone-linux-tools
bash scripts/host/iphone-linux.sh boot
```

O wrapper confere os hashes do palera1n e da imagem integrada, espera PongoOS, envia o payload e espera a interface do Linux. Depois atribui o IP USB temporário do Mac e verifica SSH e HTTP iniciados pelo init. `boot-probe` conserva o fluxo original com instalação posterior do runtime. Em 2026-09-30, uma invocação de `scripts/host/iphone-linux.sh boot` completou a árvore reorganizada desde um reinício, com saída 0, PongoOS, upload intacto da imagem integrada de 23.767.809 bytes, SSH autenticado, HTTP 200 e confirmação do console pelo operador.

Fluxo manual original comprovado (para a integrada, substituir o nome do payload conforme seção 17):

1. Cabo **USB-A → Lightning**, porta USB-A traseira do Mac. Recuperação mostra cabo/computador.
2. `scripts/boot/dfu_boot.py` usa `PALERA1N_BYPASS_PASSCODE_CHECK=1 bin/palera1n-macos-arm64 -lp -k artifacts/Pongo.bin`. No A9 deste teste, o bypass evita a verificação de passcode da ferramenta; não desbloqueia dados de usuário nem altera conta.
3. Entrar em DFU manualmente pelos botões físicos. O monitor aguarda a enumeração USB e não abre página nem contador. Tela preta é necessária, mas só a detecção USB comprova DFU (`05ac:1227`). Cabo na tela significa recuperação. O guia visual histórico foi removido em 2026-09-30 a pedido do operador; o monitor substituto passou em testes locais simulados e na revalidação física da árvore reorganizada.
4. Confirmar log de sucesso e `PongoOS USB Device`. O monitor pode ser interrompido depois disso.
5. Enviar o payload:

```bash
printf '/send %s/artifacts/m1n1-linux-iphone6s.bin\nbootm\n' "$PWD" | ./bin/pongoterm
```

6. Esperar `iPhone 6s Linux probe` e sua interface Ethernet USB. A desconexão momentânea após `bootm` é parte da transição; não prova sozinha que houve boot.
7. `bash scripts/host/iphone-linux.sh connect` identifica a interface pelo dispositivo no IORegistry. Não presumir `en12` em todo boot. O Mac pode pedir autenticação para um alias IPv4 temporário somente nessa interface.
8. `bash scripts/host/iphone-linux.sh install-terminal`, depois `status` e `serve`, caso o fluxo tenha sido manual.

Não executar fakefs, particionamento A11, restore ou scripts desconhecidos para contornar falhas de boot.

## 9. Reconstruir Bash, SSH e Herdr

Em uma reconstrução com a identidade SSH atual, conservar `keys/` e a chave de servidor já presente na VM/runtime. Não regenerar chaves por rotina.

Para uma implantação nova, criar `keys/` com permissão 700 antes de gerar a chave; `ssh-keygen -t ed25519 -N '' -f keys/iphone_ed25519 -C iphone6s-linux-local` cria a chave cliente dedicada. A chave privada fica no Mac; envie **somente** `.pub`.

Baixe o Herdr da release oficial `https://github.com/herdrdev/herdr/releases/download/v0.9.1/herdr-linux-aarch64` para `artifacts/herdr-linux-aarch64` e confira o digest da API `https://api.github.com/repos/herdrdev/herdr/releases/tags/v0.9.1`. Não use um instalador remoto executado via pipe. O binário do Mac não foi alterado.

```bash
multipass transfer artifacts/herdr-linux-aarch64 iphone6s-build:/home/ubuntu/herdr-linux-aarch64
multipass transfer keys/iphone_ed25519.pub iphone6s-build:/home/ubuntu/iphone_ed25519.pub
multipass transfer scripts/build/build-runtime.py iphone6s-build:/home/ubuntu/build-runtime.py
multipass exec iphone6s-build -- python3 /home/ubuntu/build-runtime.py
multipass transfer iphone6s-build:/home/ubuntu/iphone6s-runtime.tar.gz runtime/iphone6s-runtime.tar.gz
multipass transfer iphone6s-build:/home/ubuntu/iphone-host-public.txt runtime/iphone-host-public.txt
```

`build-runtime.py` copia bibliotecas listadas por `ldd`, terminfo e arquivos de conta/configuração; usa UID/GID 0 no tar e permissões restritas para SSH. O script preserva a chave do servidor existente na VM. Antes de implantar, recalcular `runtime/SHA256SUMS` e construir `keys/known_hosts` com a linha pública `ssh-ed25519` do servidor, prefixada por `172.16.42.1`. Nunca aceitar uma chave diferente silenciosamente. Para preparar os arquivos locais, depois de transferir o runtime e a chave pública do servidor:

```bash
mkdir -p keys runtime
chmod 700 keys runtime
(cd runtime && shasum -a 256 iphone6s-runtime.tar.gz > SHA256SUMS)
awk '/^ssh-ed25519 / {print "172.16.42.1 " $1 " " $2}' runtime/iphone-host-public.txt > keys/known_hosts
chmod 600 keys/known_hosts runtime/iphone6s-runtime.tar.gz
```

Confirme que `keys/known_hosts` contém exatamente uma linha válida. O fingerprint deve vir da construção confiável na VM; não substituir por `ssh-keyscan` sem conferir sua origem.

```bash
bash scripts/host/iphone-linux.sh install-terminal
bash scripts/host/iphone-linux.sh shell
bash scripts/host/iphone-linux.sh herdr
```

`install-terminal` verifica o pacote local, abre um servidor HTTP temporário somente no USB, verifica novamente o hash no telefone, instala na RAM e testa SSH. Só então encerra Telnet. Após uso, fecha o servidor de transferência. As conexões usam uma chave e um known_hosts locais dedicados, `StrictHostKeyChecking=yes` e nenhum forwarding de agente SSH.

## 10. Construir a imagem candidata com o terminal incluído

Transferir para `/home/ubuntu` da VM: `scripts/build/build-server-image.sh`, `phone/init/init-server`, `phone/http/status` com nome `iphone-status`, o `artifacts/iphone6s-initramfs.gz` original e o runtime final. Depois:

```bash
multipass transfer scripts/build/build-server-image.sh iphone6s-build:/home/ubuntu/build-server-image.sh
multipass transfer phone/init/init-server iphone6s-build:/home/ubuntu/init-server
multipass transfer phone/http/status iphone6s-build:/home/ubuntu/iphone-status
multipass transfer artifacts/iphone6s-initramfs.gz iphone6s-build:/home/ubuntu/iphone6s-initramfs.gz
multipass transfer runtime/iphone6s-runtime.tar.gz iphone6s-build:/home/ubuntu/iphone6s-runtime.tar.gz
multipass exec iphone6s-build -- bash /home/ubuntu/build-server-image.sh
multipass transfer iphone6s-build:/home/ubuntu/iphone6s-server-initramfs.gz artifacts/iphone6s-server-initramfs.gz
python3 scripts/build/compose-payload.py artifacts/iphone6s-server-initramfs.gz artifacts/m1n1-linux-iphone6s-server.bin
```

O build combina o rootfs original com o runtime, `phone/init/init-server` e HTTP. O payload candidato desta rodada tem 23.746.076 bytes e SHA-256 `a12e2e36c7ee9b47c92a2b56c8679bb94908cd1f3dded7615ec2f3da65742a4e`. **Construção não é prova de boot.** Esses bytes descrevem a candidata anterior. A imagem posterior com console foi testada em DFU e passou a ser o padrão, conforme seção 17.

## 11. Operação, persistência e atualizações

- Shell: `bash scripts/host/iphone-linux.sh shell`; sair com `exit`.
- Herdr: `bash scripts/host/iphone-linux.sh herdr`; sessão `iphone-linux`. O detach normal do Herdr é `Ctrl+B`, depois `q`, conforme a documentação upstream. Neste teste, a permanência foi comprovada fechando a conexão SSH, não por validar esse atalho no terminal do usuário.
- Fechar SSH não encerra os painéis do Herdr. Reiniciar o iPhone encerra todos os processos e perde os arquivos em RAM, inclusive layout/configuração do Herdr que não tenham backup no Mac.
- Atualização do Linux: construir outro payload, conferir fontes/hashes, manter o anterior, fazer boot do novo e verificar o resultado. Não precisa formatar NAND. Não há apt/apk completo na imagem mínima atual.
- Configurações iniciais e chaves são persistidas nos artefatos do Mac; alterações arbitrárias feitas no telefone ainda não têm sincronização automática.
- O Mac precisa manter o enlace USB disponível. Carregador sozinho não fornece a rede USB; não há interface Wi-Fi disponível nesta imagem.
- DNS local ainda não foi instalado. Nenhum DNS do Mac/roteador foi alterado; não há NAT/encaminhamento para a LAN nem internet de saída no telefone.
- Para remover somente o alias USB do Mac enquanto o telefone estiver conectado: `bash scripts/host/iphone-linux.sh disconnect`. Não altera a rota padrão de Ethernet/Wi-Fi.
- Restaurar pelo Finder reinstala iOS e apaga dados locais; não é parte da atualização do Linux em RAM. O boot normal continua Apple/iOS.

### Reboot controlado e retorno ao iOS

Antes de reiniciar, salve o estado no Mac e abra um Bash remoto:

```bash
bash scripts/host/iphone-linux.sh backup
bash scripts/host/iphone-linux.sh shell
```

Dentro do Bash remoto, execute:

```bash
sync
reboot -f
```

Nesta imagem, um `reboot` comum retornou saída 0, mas o Linux continuou exposto no USB com o PID 1 (`init`). `reboot -f` foi necessário para concluir a transição; o retorno ao iOS foi confirmado pelo USB e por `ideviceinfo -k ProductVersion`. Não interprete a saída ou o encerramento da sessão SSH como prova de que o iOS voltou: o cliente pode aguardar a desconexão usando `ServerAliveInterval=5` e `ServerAliveCountMax=3`. Não é necessário ler ou digitar no display do telefone para essa confirmação.

O telefone retornou ao iOS com 100%, `BatteryIsCharging=true` e `ExternalConnected=true` após aproximadamente 17 minutos, com uptime Linux anterior de 1019,88 s. Esses campos confirmam o estado observado naquele instante, mas não comprovam carga sustentada ou operação contínua de 24 horas.

## 12. Falhas e aprendizado reproduzível

| Sintoma | Causa/ação comprovada |
|---|---|
| Maçã/cabo após sequência | Recuperação, não DFU. USB-A → Lightning foi a mudança seguida de sucesso; o cabo não foi provado como única causa |
| PongoOS iniciado, ferramenta ainda esperando | O upstream permite interromper após PongoOS; confirmar pelo USB antes de enviar |
| Nenhuma interface logo após bootm | Esperar a transição; confirmar gadget USB e shell, não apenas tela preta |
| sudo pede senha | Usar diálogo de administrador do macOS para o alias dedicado; não pedir senha no chat |
| /sys/block sem disco interno | Driver/acesso ao storage indisponível nesta imagem A9; formatar não resolve |
| Transferência de comando longo corrompida | Editor BusyBox limitou a linha; usar base64 em linhas de 76 caracteres/heredoc |
| Cliente Telnet esperava indefinidamente | Prompt inclui `ESC[6n`; cliente trata a sequência e espera confirmação explícita de execução |
| ioreg plist não contém BSD Name | Identificar o nó `IOEthernetInterface` pelo `IORegistryEntryName` dentro do gadget específico |
| SSH Permission denied apesar da chave certa | Tar mantinha UID 1000; usar UID/GID 0, diretório .ssh 700, authorized_keys 600 |
| Bash não acha head/insmod/etc. | Criar os diretórios padrão e instalar links BusyBox; ash antes conseguia usar applets internamente |
| Comandos via helper saem sem resposta | A sondagem SSH consumia stdin; `ssh_ready` usa `ssh -n` |
| DNS quebrado na VM | Contorno temporário no /etc/hosts somente da VM; apt mantém a verificação de assinatura |

O cliente OpenSSH atual imprime um aviso de ausência de troca pós-quântica com esta versão do Dropbear. A conexão usa SSH autenticado convencional pelo enlace USB dedicado. Não foram relaxadas a verificação de host ou a autenticação. Isso fica como diferença a considerar se a conexão deixar de ser local/dedicada.

## 13. Evidência e próximos gates

Evidências locais: `evidence/multipass-build.json`, `evidence/ubuntu-package-versions.txt`, `evidence/ssh-linux-status.txt`, `evidence/herdr-phone.txt`, `evidence/linux-boot-proof.txt`, `evidence/linux-http-proof.html`, `artifacts.json`. O log `../logs/install-last.log` permanece somente local. Alguns registros iniciais são históricos, anteriores ao SSH; os mais novos mostram o estado atualizado.

Gates pendentes: confirmação física de carga sustentada; estabilidade prolongada; serviço DNS; e os demais itens do backlog. SSH/HTTP pela LAN foram comprovados pelo Windows após novo boot com loopback automático; [procedimento e limites](REDE.md). O boot frio pelo wrapper, a restauração após novo boot e os snapshots automáticos foram revalidados fisicamente nesta árvore, mas isso não prova que a alimentação mantenha carga positiva ou operação contínua. Não confundir o HTTP/Bash/Herdr já verificados com esses gates.

Fontes primárias: [Hoolock PongoOS](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP_pongoOS.md), [Hoolock A9](https://github.com/HoolockLinux/docs/blob/master/features/A9.md), [armazenamento](https://github.com/HoolockLinux/docs/blob/master/tools/README.md), [palera1n](https://github.com/palera1n/palera1n), [Herdr](https://github.com/herdrdev/herdr), [processo de boot Apple](https://support.apple.com/en-ca/guide/security/secb3000f149/web).

## 14. Fontes preservadas e reconstrução do cliente Pongo

Clones locais sem alterações observadas no inventário:

```bash
git clone https://github.com/HoolockLinux/docs.git ../hoolock-docs
git -C ../hoolock-docs checkout 23ebe1fbc375599221553a7e1815e5de182a6b42
git clone https://github.com/checkra1n/PongoOS.git ../pongoOS
git -C ../pongoOS checkout 4c9b7541629234147fcc778f0ce4162482aaccef
clang -Os -x objective-c -framework IOKit -framework CoreFoundation ../pongoOS/scripts/pongoterm.c -lobjc -framework Foundation -mmacosx-version-min=10.8 -o bin/pongoterm
```

A linha de compilação acima vem do tutorial upstream; não foi reexecutada nesta rodada. A comparação confirmou que `artifacts/Pongo.bin` corresponde byte por byte à cópia do clone Hoolock; o resultado também está no manifesto. m1n1 e o APK ainda precisam de proveniência completa para uma reconstrução independente. Um clone público deste projeto contém scripts e registros, não uma imagem pronta para boot: obtenha e confira os insumos antes de executar.

## 15. Publicação e privacidade

O repositório público guarda fontes, procedimentos, evidências selecionadas e hashes. `keys/`, `runtime/`, downloads, imagens, logs brutos e clones upstream ficam ignorados. Runtime e imagem candidata contêm a chave privada do servidor SSH: nunca os publique. Cada nova implantação deve gerar suas próprias chaves. A configuração de rede privada da VM foi retirada da evidência pública. Emails de autoria podem constar nos commits.

## 16. Console no display

A tela e um Bash espelhado foram ativados sem reiniciar, com confirmação visual do usuário. Consulte [CONSOLE.md](CONSOLE.md) para comandos, diagnóstico, versões e hashes da candidata nova. O runtime agora inclui `script`; a candidata nova inclui ativação de tty1. Os hashes da candidata anterior na seção 10 descrevem a construção histórica, não a nova imagem. Ambas permanecem preservadas localmente.

## 17. Boot confirmado da imagem integrada

Após autorização do usuário e confirmação de que estava pronto para os botões, a imagem `artifacts/m1n1-linux-iphone6s-console-server.bin` deu boot via DFU → PongoOS → m1n1. SHA-256 `c49e03822e164767424d1ac786c3b00eec731de66acec497915c2cc83a39ee4a`, 23.767.809 bytes. SSH, Bash 5.2.21, HTTP e console foram confirmados sem transferência posterior do runtime. O usuário confirmou a tela automaticamente ativa. Herdr 0.9.1 foi iniciado e um comando dentro do painel retornou `POST_BOOT_HERDR_OK` e kernel 7.0.12.

Essa foi a imagem integrada original com console. Após a correção de loopback da #6, `scripts/host/iphone-linux.sh boot` seleciona `artifacts/m1n1-linux-iphone6s-loopback-server.bin`, 23.765.032 bytes, SHA-256 `8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66`, também comprovada em novo boot/restore e teste Windows independente. A anterior está preservada; a receita e comparação de arquivos estão em [REDE.md](REDE.md). `boot-probe` conserva o payload original. Evidências históricas do console: [CONSOLE.md](CONSOLE.md) e [console-cold-boot.txt](evidence/console-cold-boot.txt). Os dados modificados continuam em RAM; snapshots guardam arquivos no Mac, não processos ativos.

## 18. Persistência de arquivos no Mac

`scripts/host/iphone-linux.sh backup`, `backups`, `restore` e `autosnap` guardam snapshots privados de `/srv/data` e arquivos de trabalho de `/root`. Identidade SSH e estado vivo de sessões Herdr são excluídos. A restauração verifica hash/escopo, salva a cópia anterior e recupera conteúdo/permissões sem remover arquivos extras. A automação optativa, retenção e `boot --restore ID` foram validados em teste físico curto, local e VM. O procedimento completo e seus limites estão em [PERSISTENCIA.md](PERSISTENCIA.md), com evidência sanitizada em [autosnapshot-check.txt](evidence/autosnapshot-check.txt).

Os backups ficam no Mac e não são publicados. Alterações após o último snapshot continuam vulneráveis à perda de energia. A recuperação após outro DFU foi revalidada fisicamente com o CLI da árvore reorganizada. Não há restauração implícita no boot; `boot --restore ID` é sempre uma opção explícita.

## 19. Investigação de Wi-Fi

A inspeção do rádio/barramento no Linux ativo e do device tree oficial A9 no commit `6831bc701a6ce059e71e5aaa9488c9195bea6927` não encontrou um caminho pronto para habilitar Wi-Fi nativo no N71. O fork que documenta Wi-Fi funcionando foi validado em A10, não A9. Não foi instalada ferramenta nem alterada a rede do Mac. Evidências, fontes e limites: [WIFI.md](WIFI.md).

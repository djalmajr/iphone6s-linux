# Userspace Wi-Fi no mesmo boot — #44

## Estado

A imagem real de calibração contém BusyBox, mas não iw/wpa_supplicant/wpa_cli. A preparação autenticou38 pacotes oficiais Ubuntu ARM64/all,11.638.132 bytes, incluindo iw 6.7-1build1 e wpasupplicant 2:2.10-21ubuntu0.4. Não houve instalação, maintainer script ou execução desses binários. Builder isolado, closure ELF e versão/help reais ainda estão pendentes; associação Wi-Fi, bateria e carga não foram demonstradas.

[Manifesto com versões, nomes, SHA e bytes](evidence/n71-wifi-userspace-packages.json), [prova de aquisição](evidence/n71-wifi-userspace-source-qualified.json), [plano](../.agents/plans/n71-wifi-userspace.md), decisões D43/D44. Os debs, scripts exatos de aquisição e logs ficam privados em runtime/n71-wifi-userspace-source-20261010; na VM dedicada, /home/ubuntu/n71-wifi-userspace-source-20261010.

## Reprodução da origem

1. Na VM Ubuntu ARM64 dedicada, criar diretório novo privado700 e subpastas lists/partial,cache/archives/partial,debs. Usar uma sources.list própria com HTTPS ports.ubuntu.com/ubuntu-ports, suites noble/noble-updates/noble-security, componente main, arch=arm64 e signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg. Conferir tipo/root/mode/hash do keyring e `dpkg --verify ubuntu-keyring` vazio antes de confiar nele.
2. Passar opções APT que apontem somente para esses lists/cache/sources e sourceparts=-. O status=/dev/null na consulta de plano representa um sistema vazio, trazendo as dependências que a imagem não tem. `APT::Update::Error-Mode=any` deve recusar índice indisponível. Executar update e conferir os três InRelease por `gpgv --status-fd 1 --keyring` contra o keyring fixado; conservar fingerprints/SHA. A autenticação APT liga Release→Packages→deb. [apt-secure](https://manpages.ubuntu.com/manpages/noble/man8/apt-secure.8.html).
3. Consultar `apt-get --print-uris --download-only --no-install-recommends -y install iw wpasupplicant` apenas para o plano. Para cada URI HTTPS oficial, conferir metadata apt-cache show: Package/Version/Architecture/Size/Filename/SHA256. O manifesto público congela os38 resultados. Não usar install para realizar a aquisição.
4. Usar `apt-get download` com os38 argumentos package=version do manifesto, cwd na pasta debs. Esse comando baixa binários para a pasta corrente e mantém a autenticação usual. [apt-get](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html). Conferir cada arquivo real por tamanho/SHA-256 e unicidade; recusar ausência/mistura. Salvar o receipt apenas depois disso.
5. Conferir /etc/hosts e /var/lib/dpkg/status globais por SHA antes/depois. Não executar dpkg install, hooks ou binários de pacote. Manter diretórios700/arquivos600; logs/archives continuam privados. Se uma versão desaparecer do repositório, não escolher automaticamente outra: preservar os dados locais ou qualificar uma aquisição nova.

### Falha DNS observada

O update inicial retornou falha de resolução e zero InRelease; a aquisição foi recusada apesar do exit0 do APT. curl --resolve com certificado TLS validado retornou HTTP200 do endpoint oficial. O IP foi aplicado somente num hosts privado bindado em mount namespace filha da VM (`sudo -n unshare --mount --propagation private`). Depois do bind, o processo removeu grupos e mudou gid/uid para ubuntu antes do APT. A namespace encerrou; hosts e dpkg globais permaneceram idênticos. Não se editou resolver global nem configuração do Mac.

Uma tentativa download-only install foi recusada porque o frontend lock derivado do status=/dev/null não podia ser aberto. A correção usou download com versões exatas, sem desabilitar locks ou autenticação. As duas tentativas recusadas permanecem no relatório privado; não contaram como sucesso ou teste de mutação.

## Próxima fase e limites

Extrair somente os programas e bibliotecas de dados autenticados. Montar pacote com loader/library-path próprios e sem symlinks ou scripts de manutenção; não substituir /lib do SSH em execução. Conferir ELF64/AArch64 e todos os DT_NEEDED, depois versão/help numa raiz/namespace isolada da VM, sem rádio ou associação. Testar guards em cópias descartáveis e documentar licenças selecionadas. Não há execução ELF Linux no Mac.

Depois que o rádio expuser uma interface no iPhone, enviar/conferir o pacote por SSH e operar explicitamente no mesmo boot. Conservar a rede USB para recuperação. Credenciais de Wi-Fi não foram lidas e só serão necessárias para uma rede autorizada na etapa de associação.

## Relatório da aquisição

- **Arquivos:** plano, D43/D44, documentação, manifesto de38 pacotes e prova sanitizada.
- **Verificação:** três assinaturas InRelease; SHA/tamanho de todos os debs; hosts/dpkg globais idênticos. Nenhum novo executável de projeto foi implementado nesta fase, portanto AST/lint/tipagem/mutações do builder ainda não se aplicam.
- **Reuso:** gates I2C/kernel/runtime anteriores não afetados; a CI do head 0c61631 continua sendo uma execução separada.
- **Banco/dependências:** nenhum banco ou pacote instalado. Dados de aquisição privados na VM;11,6 MB de debs ainda não representam o tamanho do pacote final.
- **Próximo:** builder offline e prova ARM64; a issue44, a issue9 e o goal funcional continuam abertos.

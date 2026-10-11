# Userspace Wi-Fi no mesmo boot — #44

## Estado

A imagem real de calibração contém BusyBox, mas não iw/wpa_supplicant/wpa_cli. A preparação autenticou 38 pacotes oficiais Ubuntu ARM64/all, 11.638.132 bytes, incluindo iw 6.7-1build1 e wpasupplicant 2:2.10-21ubuntu0.4. Builder 51abc5b gerou quatro programas e 19 bibliotecas isolados, com execução real somente na VM. Associação Wi-Fi, bateria e carga no iPhone ainda não foram demonstradas.

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

O builder offline extrai somente programas, bibliotecas necessárias e textos de licença de dados autenticados. Usa os bytes conferidos do deb em stdin de dpkg-deb, sem reabrir o input depois do hash. Links são resolvidos no catálogo virtual; nenhum link ou maintainer script entra no pacote. ELF64/AArch64, interpreter e DT_NEEDED são conferidos; RPATH/RUNPATH são recusados. O pacote tem loader/library-path próprios e conserva /lib do SSH em execução.

Na pasta do projeto na VM Linux ARM64, com runtime privado já criado:

```bash
python3 -B scripts/build/build-n71-wifi-userspace.py \
  --package-dir /home/ubuntu/n71-wifi-userspace-source-20261010/debs \
  --output-dir "$PWD/runtime/meu-pacote-wifi"
python3 -B -m unittest discover -s tests -p test_n71_wifi_userspace.py -v
```

O output deve ser novo e diretamente sob runtime. A fonte deve conter exatamente os 38 debs com nomes/tamanho/SHA do manifesto fixado; arquivo público diferente também é recusado. No Mac, o CLI recusa antes de escrever. Saída privada700/600, arquivos bin/lib/licenças regulares, receipt e wifi-userspace-private.tar. Uma falha conserva a pasta parcial sem aceite; use outro nome na tentativa seguinte. O builder não acessa rede ou inicia programas/serviços.

Quando houver pacote enviado e conferido no iPhone, a forma de executar é explícita:

```bash
wifi_root=/tmp/n71-wifi-tools
"$wifi_root/lib/ld-linux-aarch64.so.1" --inhibit-cache \
  --library-path "$wifi_root/lib" "$wifi_root/bin/iw" --version
"$wifi_root/lib/ld-linux-aarch64.so.1" --inhibit-cache \
  --library-path "$wifi_root/lib" "$wifi_root/bin/wpa_supplicant" -v
```

Não executar o ELF diretamente com o loader global da imagem. Esses comandos ainda não foram rodados no telefone. O pacote contém copyrights de 37 pacotes e 17 textos de licenças comuns, com SHA dos arquivos no receipt. A closure DT_NEEDED e os testes de versão/PSK não comprovam plugins opcionais, rádio ou associação em uma rede real.

Depois que o rádio expuser uma interface no iPhone, enviar/conferir o pacote por SSH e operar explicitamente no mesmo boot. Conservar a rede USB para recuperação. Credenciais de Wi-Fi não foram lidas e só serão necessárias para uma rede autorizada na etapa de associação.

## Relatório da aquisição

- **Arquivos:** plano, D43/D44, documentação, manifesto de38 pacotes e prova sanitizada.
- **Verificação:** três assinaturas InRelease; SHA/tamanho de todos os debs; hosts/dpkg globais idênticos. Nenhum novo executável de projeto foi implementado nesta fase, portanto AST/lint/tipagem/mutações do builder ainda não se aplicam.
- **Reuso:** gates I2C/kernel/runtime anteriores não afetados; a CI do head 0c61631 continua sendo uma execução separada.
- **Banco/dependências:** nenhum banco ou pacote instalado. Dados de aquisição privados na VM;11,6 MB de debs ainda não representam o tamanho do pacote final.
- **Próximo:** builder offline e prova ARM64; a issue44, a issue9 e o goal funcional continuam abertos.

## Resultado do pacote

[Evidência sanitizada](evidence/n71-wifi-userspace-builder-qualified.json). Quatro programas, 19 bibliotecas, 23 objetos ELF e 77 arquivos; tar 17.786.880 bytes, SHA 5f1396ae55f41783c360cd28c111ee6d78d9d72a6188f9714e0b6e3b48dfd617. Binários/tar/receipts/logs privados em runtime/n71-wifi-userspace-builder-20261010 e /home/ubuntu equivalente da VM. No Mac, o tar foi tratado somente como dados e teve SHA/tamanho reconferidos; não foi instalado ou executado.

Mac: 11 testes/10 mutações únicas por AssertionError; ARM64: 11/10 com um skip do gate específico do Mac. AST/lint fatal e F401/F841 aprovados nos três arquivos, sem typechecker Python. A execução real da VM usou chroot/network namespace sem interface de rede: iw 6.7, wpa_supplicant/wpa_cli 2.10 e PSK de fixture igual ao PBKDF2 independente. O primeiro ambiente sem urandom produziu aviso; repetiu-se somente a execução afetada com urandom/null bindados na namespace filha. O gate final não teve esses avisos.

Uma cópia sem libnl-genl retornou 127 mesmo com bibliotecas presentes na VM externa; nenhum fallback para elas foi usado. Deb alterado e ausente retornaram 1 antes de criar output. O pacote aceito e os 38 inputs originais permaneceram idênticos. Os gates kernel/I2C/runtime anteriores não afetados foram reutilizados. Não houve banco, instalação de pacote/configuração global ou ação no telefone. Próximo: CI do novo head e transferência/associação no mesmo boot físico do rádio; #44/#9/#2/#42 e o goal continuam abertos.

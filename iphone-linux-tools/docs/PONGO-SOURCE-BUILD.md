# Reprodução de PongoOS — #12

## Plano e contexto

O payload Pongo preservado permite repetir o boot conhecido, mas o commit do clone local não prova que ele gerou esse binário. Esta fase tenta produzir uma candidata independente a partir das fontes fixadas. O iPhone não será reiniciado nem receberá esta candidata durante a compilação.

Arquivos públicos desta fase: este documento, `scripts/build/build-pongo-source.sh`, `scripts/build/verify-pongo-build.py`, `docs/evidence/pongo-source-build.json` e `tests/test_pongo_verifier.py`, no máximo cinco arquivos. A referência em `REPRODUCAO.md` será atualizada em fase posterior. Fontes, logs, metadados de pacotes e artefatos permanecem privados em `runtime/`.

- [x] Criar VM Ubuntu ARM64 nova, própria deste build, sem mounts ou identidades do servidor/cliente.
- [x] Autenticar repositórios/pacotes do guest com assinaturas APT; registrar chave oficial, fingerprints, hashes e versões. Sem instalação ou mudança de confiança no Mac.
- [x] Fixar PongoOS `bb492b004265ce91123caa23b8bc04b2eff6d2b7` e newlib `f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8`, mais cctools-port `e79d784d667816e4b15a0abd78828f9abb0a0b99`; conferir árvores e receitas antes de execução.
- [x] Compilar apenas `Pongo.bin` e ferramentas necessárias, conservar qualquer falha e validar arquitetura/formato/hashes da saída. Não presumir igualdade com o binário preservado.
- [ ] Copiar somente artefatos/resultados privados, conferir hashes, parar a VM própria, publicar receita/resultado sanitizado e atualizar #12/#17.

## D1. Compilação no guest

- **Decisão:** usar VM Multipass dedicada sem mounts, com dependências Ubuntu autenticadas por APT e ld64/cctools compilados de fonte fixada. Não instalar ferramentas no Mac nem executar o userspace do telefone no host.
- **Por quê:** contém os scripts e utilitários da compilação externa no guest e preserva o Mac, identidades e imagens conhecidas.
- **Alternativas:** Xcode já disponível permite build macOS, mas executaria o helper vmacho e configure no host; compilar a cadeia ld64 de fonte acrescentaria outras dependências e fases.
- **Reverter:** parar a VM e deixar de selecionar a candidata. Não há troca do Pongo preservado ou configuração do boot atual.
- **Status:** build corrigido concluído com saída 0, copiado e verificado; VM parada. Publicação e piloto físico ainda separados.

## Fontes e limites de confiança

[README de PongoOS no commit fixado](https://github.com/checkra1n/PongoOS/blob/bb492b004265ce91123caa23b8bc04b2eff6d2b7/README.md) descreve a compilação Linux com clang, ld64 e cctools-strip. [newlib no gitlink fixado](https://github.com/checkra1n/newlib/blob/f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8/Makefile) mantém prefixo dentro da árvore de trabalho. [ld64-build oficial](https://github.com/checkra1n/ld64-build/blob/master/README.md) declara binários arm64 e x86_64 e publicação no repositório APT checkra1n.

As receitas Pongo/newlib e o helper vmacho foram inspecionados. A ferramenta vmacho lê o Mach-O compilado e escreve o arquivo de saída; não é o userspace do iPhone. Essa leitura não é uma auditoria exaustiva nem prova ausência de malícia em toda a cadeia. A chave do repositório externo foi obtida da origem oficial por HTTPS; assinaturas APT validaram seus metadados, mas a instalação foi recusada por dependências incompatíveis. Nenhum ld64/cctools desse repositório foi instalado. A toolchain será compilada de fonte fixada no guest. Hashes de commits não provam autoria independente ou ausência de malícia. A VM não deve conter chaves do projeto, mounts ou credenciais de contas remotas.

## Critérios de verificação

Build saída 0, identificação ARM64 do Mach-O, correspondência da extração Pongo.bin, hashes/tamanhos e versões/commits registrados. Artefatos originais e cadeia operacional permanecem inalterados. Sucesso de compilação não comprova exploração DFU, boot de Linux, retorno ao iOS ou suporte de carregamento. Gates físicos continuam abertos.

## Evidência que mudou a escolha

O clone histórico `4c9b754...` não contém `bootm`; ele é insuficiente para reproduzir o fluxo usado. O binário preservado contém `bootm`, `boots m1n1` e `PongoOS-2.6.3-bb492b00`. O upstream resolve o prefixo para [`bb492b004265ce91123caa23b8bc04b2eff6d2b7`](https://github.com/checkra1n/PongoOS/commit/bb492b004265ce91123caa23b8bc04b2eff6d2b7), mudança de posicionamento de m1n1; o gitlink newlib é `f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8`. Essa correspondência orienta o rebuild, mas só comparar a saída permite afirmar identidade binária.

APT recusou `ld64` por depender de `libssl1.1` indisponível no Ubuntu 24.04 e `cctools-strip:amd64` por arquitetura/dependências incompatíveis. O repositório adicionado apenas no guest foi desabilitado. Nenhum downgrade, pacote não autenticado ou dependência forçada. O README Hoolock recomenda [cctools-port](https://github.com/tpoechtrager/cctools-port), cuja fonte admite host aarch64 e target arm64; TAPI é necessário para SDKs com stubs, que esta compilação freestanding não utiliza. A primeira resolução DNS falhou; alteração temporária de DNS ocorreu somente na VM e precisa ser revertida antes de pará-la.

## Alteração gerada pelo configure

Na primeira compilação, cctools e Pongo terminaram, mas o gate de árvore limpa recusou `cctools/include/llvm-c/lto.h`. A macro upstream `m4/llvm.m4` copia esse cabeçalho do LLVM detectado. O arquivo gerado corresponde byte a byte a `/usr/include/llvm-c-18/llvm-c/lto.h`, do pacote Ubuntu autenticado `llvm-18-dev`; `dpkg --verify` não encontrou alterações nos pacotes LLVM verificados. SHA-256: `e9fc2f15bf371966799309ddaf3510b0dae412d52ed7093adab2369c2aea61e3`.

A receita continua exigindo árvores limpas antes de começar. Depois do build, aceita somente essa alteração de caminho e somente se os bytes corresponderem ao cabeçalho do pacote LLVM; demais arquivos rastreados precisam permanecer inalterados. A primeira tentativa foi preservada. A receita corrigida é validada com novos clones e nova pasta de build, mantendo os mesmos commits e dependências autenticadas.

## Receita atual

No Mac, use o Multipass já instalado para criar uma VM local ARM64 nova, sem mounts:

```sh
multipass launch 24.04 --name iphone6s-pongo-20261001 --cpus 2 --memory 4G --disk 20G
multipass info iphone6s-pongo-20261001 --format json
```

Na VM, com APT recusando pacotes não autenticados:

```sh
sudo apt-get -o APT::Get::AllowUnauthenticated=false -o Acquire::AllowInsecureRepositories=false -o APT::Update::Error-Mode=any update
sudo apt-get -o APT::Get::AllowUnauthenticated=false -o Acquire::AllowInsecureRepositories=false install -y --no-install-recommends clang-18 llvm-18 llvm-18-dev llvm-18-tools build-essential autoconf automake libtool pkg-config libssl-dev zlib1g-dev uuid-dev libxml2-dev
```

Confira InRelease por `gpgv --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg ARQUIVO_InRelease` para cada origem Ubuntu em `/var/lib/apt/lists/`, `dpkg --verify ubuntu-keyring llvm-18-dev llvm-18 libllvm18` e versões por `dpkg-query -W`. Preserve os logs. A tentativa checkra1n descrita acima foi diagnóstico; não é necessária para esta receita de fonte.

Clone os três repositórios para `SOURCES/PongoOS`, `SOURCES/PongoOS/newlib` e `SOURCES/cctools-port`. Para cada um, inicialize um diretório novo, adicione a URL HTTPS como `origin` e faça fetch do SHA completo com tempo mínimo de transferência limitado:

```sh
git -c core.hooksPath=/dev/null -c http.sslVerify=true -c protocol.file.allow=never -c protocol.ext.allow=never -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=120 fetch --depth 1 origin SHA_COMPLETO
git -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
git rev-parse HEAD
git status --porcelain --untracked-files=no
```

URLs e SHAs estão na lista do plano. O gitlink `newlib` precisa corresponder ao commit declarado. A compilação exige fontes limpas sem `build/` ou `aarch64-none-darwin/` prévios em Pongo/newlib. Transfira apenas `scripts/build/build-pongo-source.sh` e `scripts/build/verify-pongo-build.py` para uma pasta de receitas na VM, mantendo-os juntos:

```sh
bash /home/ubuntu/pongo-recipe/build-pongo-source.sh /home/ubuntu/pongo-sources /home/ubuntu/pongo-build
```

A receita compila cctools-port no target `aarch64-apple-darwin`, com TAPI/XAR desabilitados porque não usa SDK/stubs ou bitcode_bundle; LTO usa LLVM 18. O prefixo da toolchain fica dentro da pasta de build privada. Depois compila apenas `build/Pongo.bin`, com newlib fixado, LLVM ar/ranlib e SOURCE_DATE_EPOCH do commit. Os arquivos do telefone, NAND, iOS, palera1n e perfil padrão não são selecionados ou modificados.

`verify-pongo-build.py` lê os arquivos, confere Mach-O ARM64/preload, limites dos comandos/segmentos/seções e mapa bruto de até 512 KiB, incluindo padding entre seções. Compara esse mapa com Pongo.bin e exige markers `bootm` e `2.6.3-bb492b00`; não executa o candidato.

## Recuperação do segundo fetch

O segundo download de cctools ficou com pack de 434.175 bytes sem gravação por mais de oito minutos, embora processos Git e conexão TCP permanecessem vivos. Encerramos somente os três processos identificados do fetch próprio; a operação confirmou saída terminal 143. Não interpretamos um timeout de observação como encerramento.

A validação da receita corrigida usa clones locais com `git clone --no-hardlinks --no-checkout ORIGEM_VERIFICADA DESTINO_NOVO`, checkout destacado dos mesmos SHAs e `git fsck --no-reflogs --connectivity-only`. Os objetos Git vieram dos downloads HTTPS completos da primeira tentativa; alterações não commitadas, bibliotecas, objetos e outputs de compilação não foram copiados. Isto valida uma nova compilação com checkouts limpos na mesma VM, não uma segunda VM ou uma segunda obtenção independente da rede.

## Gates locais do verificador

Seis testes CLI sintéticos passaram: mapa com padding não zero, CPU/tipo errados, comandos/seções malformados, arquivo bruto alterado, versão/bootm errados e links/tamanho excessivo. Seis mutações executadas em cópias temporárias foram detectadas: ignorar CPU, tipo, comparação bruto/Mach-O, markers, tipo de arquivo e padding. Parsing/Flake8 E9/F63/F7/F82, Bash e ShellCheck passaram. Não há type checker configurado. A execução real no macOS recusou o builder antes de tocar fontes ou criar saídas.

A primeira compilação gerou Pongo.bin com 238.096 bytes; mapeamento ARM64 e markers foram verificados também no Mac após transferência privada. SHA-256 `17d3df93213bb24f8ba73a8ad390e6bcc56351b41d87a315d47d37aa51100efd`, diferente do preservado `1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575`; mesmo tamanho, 183.208 bytes diferentes. Não atribuir a diferença somente a metadados nem declarar reprodução byte a byte. O novo artefato tem proveniência de fonte/cadeia conhecida; ainda requer piloto físico separado.

## Resultado da receita corrigida

O segundo build terminou com `PONGO_SOURCE_BUILD_VERIFIED`, saída 0. Os artefatos copiados ao Mac correspondem aos hashes do guest, e a extração independente passou novamente. Pongo e Pongo.bin são idênticos byte a byte às saídas da primeira compilação, apesar de novas pastas/checkouts e nenhuma cópia dos objetos/libc/outputs de build. Essa repetição usa os mesmos objetos Git previamente obtidos e a mesma VM/toolchain; não é prova de outra toolchain ou outro host.

[Manifesto sanitizado](evidence/pongo-source-build.json): Pongo Mach-O 339.224 bytes, SHA-256 `4b882d0da8c4e1bae2e6638d7b6edf760c8e0cd5f21e232182d471b33c049e97`; Pongo.bin 238.096 bytes, SHA-256 `17d3df93213bb24f8ba73a8ad390e6bcc56351b41d87a315d47d37aa51100efd`. Fontes, logs e binários permanecem privados.

Cinco InRelease foram conferidos por gpgv; metadados do repositório diagnóstico checkra1n foram autenticados pela chave de fingerprint `18FAA99F5FC57B3B46279DC87F9943C7A5217279`, obtida do endpoint oficial. Seus pacotes não foram instalados. A compilação usa dependências Ubuntu assinadas e cctools-port de fonte; versões completas estão no manifesto. O keyring Ubuntu e os pacotes LLVM verificados não apresentaram alterações por dpkg.

O arquivo temporário `/etc/systemd/resolved.conf.d/iphone6s-pongo-build.conf` foi removido somente após conferir seu conteúdo. O override de enp0s1 foi revertido; systemd-resolved voltou à configuração padrão do guest. O repositório externo permanece desabilitado. Só a VM própria deste build foi parada e seu estado `Stopped`, sem mounts, foi confirmado. O payload conhecido e Pongo preservado mantêm seus hashes anteriores; nenhuma ação USB ou pacote no Mac.

## Pendências

- Publicar os cinco arquivos desta fase e registrar #12/#17; CI dos testes públicos ainda pendente.
- Registrar as mutações em CI e atualizar a referência geral na fase seguinte.
- Integrar a seleção explícita da candidata Pongo sem substituir o padrão; validar negativa por hash antes de USB.
- Piloto físico separado com o kernel de fonte e Pongo de fonte, console/NCM/SSH/HTTP e snapshot/retorno ao iOS. Fontes/binários conhecidos não comprovam carregamento sustentado, estabilidade, NAND, Wi-Fi ou boot autônomo.

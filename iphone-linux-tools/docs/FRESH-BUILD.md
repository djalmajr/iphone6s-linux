# Reprodução da imagem em VM nova — #12

## Contexto

m1n1 já foi reconstruído de fonte fixada na VM antiga; os conteúdos do kernel foram autenticados pelo índice oficial assinado. Esta etapa cria a imagem de servidor completa em uma VM Ubuntu nova, a partir do repositório público e insumos conferidos. Não reutiliza rootfs, runtime, identidades ou cache de compilação da VM anterior. A assinatura própria do APK e seu `commit = -dirty` continuam lacunas separadas.

## Arquivos e limites

- VM nova: `iphone6s-repro-20260930`, Ubuntu 24.04, dois núcleos, 4G de RAM, 10G de disco; sem mounts ou bridge. O nome deve estar ausente antes do launch.
- Fontes: commit público `e8bd879` deste projeto; m1n1 `d5a10ac52a6468484854419a6c5130f1d62073eb`, profundidade 1 e sem tags; artwork `80d14f8b6f485b310e305a84b4b806361518ddd1`.
- Receitas existentes: `scripts/build/build-initramfs.sh`, `build-runtime.py`, `build-server-image.sh`, `compose-payload.py`; fontes `phone/init/init`, `phone/init/init-server`, `phone/http/status`.
- Dados privados novos no Mac: `runtime/fresh-build-20260930/`, incluindo identidade cliente nova, pin do servidor, runtime e imagem candidata. Não substituir `keys/`, runtime anterior ou payload conhecido.
- Registros públicos: este plano e `docs/evidence/fresh-build-provenance.json`, sem IPs, identidades SSH ou conteúdo de chaves.

## Procedimento

1. Criar a VM oficial com recursos limitados; conferir ARM64, image hash, ausência de mounts e diretórios vazios de build. Registrar cloud-init e estado das VMs anteriores sem alterá-las.
2. Inspecionar fontes APT e keyring da imagem, instalar somente dependências Ubuntu necessárias com verificação de assinatura ativa; registrar versões. Obter Rust 1.98.1 e target `aarch64-unknown-none-softfloat` da distribuição oficial, com manifesto fixado, HTTPS obrigatório e hashes conferidos antes de executar instaladores. Ler instaladores; usar prefixo na home da VM, sem instalar ferramentas no Mac.
3. Clonar fontes nos commits fixados. Baixar/conferir Herdr 0.9.1 contra o digest da release oficial. Usar o APK preservado com a prova do índice assinado, extraindo somente kernel, DTB N71 e módulo NCM correspondentes; registrar identidades dos insumos. Preparar cache Cargo novo a partir de fontes oficiais e lockfile, depois compilar offline.
4. Gerar identidade cliente dedicada no Mac; transferir somente sua chave pública. Gerar chave de servidor nova durante o runtime. Reconstruir base initramfs, runtime, imagem integrada e payload m1n1, sempre em destinos novos. O init integrado deve ter loopback ativo desde o início e SSH por chave, sem Telnet.
5. Conferir arquivo a arquivo do initramfs, permissões, ausência da chave privada cliente, correspondência de kernel/DTB/módulo, identidade servidor nova e preservação dos artefatos anteriores. Verificar Bash, Dropbear/SSH, HTTP e Herdr com o rootfs novo em namespace isolado da VM. Essa prova de userspace não equivale a boot físico do kernel no iPhone.
6. Registrar comandos, versões, hashes e resultados, preservando arquivos privados de build. Parar somente a VM nova quando não houver job ativo. O payload conhecido continua selecionado até o teste físico da candidata; aguardar disponibilidade do operador para DFU manual.

## Insumo Rust confirmado antes do launch

Manifesto oficial: `https://static.rust-lang.org/dist/channel-rust-1.98.1.toml`, SHA-256 `a7c8774a5fd8441c997d94c029776cbc5eb111e9d72ab5d256fa69866644347e`, data 2026-09-03; rustc `1.98.1 (48a229cea 2026-09-01)`. Tanto o host ARM64 GNU quanto o target bare metal foram marcados disponíveis. As URLs datadas e hashes de componentes selecionados serão registrados antes de sua instalação na VM.

## Tarefas

- [x] Receitas atuais lidas; diretórios, recursos e insumos definidos.
- [x] VM nova pronta, image hash e isolamento conferidos.
- [x] Dependências autenticadas e fontes fixadas preparadas.
- [x] m1n1 e imagem completa reconstruídos com identidades novas.
- [x] Userspace da imagem nova verificado e evidências registradas.
- [ ] Boot físico da candidata verificado; gate depende de DFU manual.

## D1. Recursos e preservação

- **Decisão:** VM nova limitada a 10G/4G/dois núcleos; conservar VMs existentes e a imagem selecionada.
- **Por quê:** o espaço livre observado no host é limitado, e esta etapa compila m1n1/empacota userspace; não compila uma árvore inteira do kernel. As identidades novas tornam a candidata uma implantação distinta.
- **Alternativas:** usar a VM antiga reduz downloads, mas não atende a prova de ambiente novo; uma VM maior amplia o consumo sem uma necessidade demonstrada nesta etapa.
- **Reverter:** baixo; os arquivos e a VM são dedicados. A reversão do telefone não será necessária antes de carregar a candidata.
- **Onde:** VM e pasta privada indicadas acima; #12.
- **Status:** aplicada; VM nova parada após concluir a construção.

## D2. DNS temporário da VM

- **Decisão:** usar `sudo resolvectl dns enp0s1 1.1.1.1` somente na VM nova durante os downloads. Ao terminar, executar `sudo resolvectl revert enp0s1` e conferir o retorno à configuração DHCP.
- **Por quê:** o resolver DHCP não resolveu nenhum dos quatro domínios oficiais testados; o resolver temporário resolveu os quatro. Certificados HTTPS e assinaturas APT continuam obrigatórios. DNS simples não autentica os conteúdos baixados.
- **Alternativas:** copiar downloads verificados do Mac aumenta etapas e dependências do host; editar `/etc/hosts` exige manter vários endereços de CDN. Alterar a rede do Mac amplia o escopo sem necessidade.
- **Reverter:** baixo; alteração transitória por interface, sem editar arquivos de rede, sem mudar as VMs anteriores.
- **Onde:** `iphone6s-repro-20260930`; não se aplica ao iPhone nem ao DNS da LAN.
- **Status:** aplicada e revertida; retorno ao DNS DHCP conferido antes de parar a VM.

## Verificação e limites

Registrar cada gate com seu alcance real: fontes/integridade, compilação, estrutura da imagem, userspace na VM e boot físico. Nenhum índice verde ou execução de Bash na VM comprova carregamento no iPhone, carga sustentada ou estabilidade prolongada. Não fechar #12 nem trocar o payload padrão apenas por uma construção bem-sucedida.

## Receita para reconstrução

Os comandos a seguir usam os diretórios novos indicados no plano. Execute somente na VM dedicada quando o bloco disser “VM”; nenhum pacote de construção é instalado no Mac. As suítes APT são mutáveis: as versões observadas estão no [registro](evidence/fresh-build-provenance.json); uma reprodução byte a byte de todo o userspace futuro exige preservar os pacotes ou usar um snapshot do arquivo Ubuntu.

### VM, pacotes e fontes

No Mac, conferir que o nome está ausente antes do launch:

```bash
multipass launch 24.04 --name iphone6s-repro-20260930 --cpus 2 --memory 4G --disk 10G
multipass info iphone6s-repro-20260930 --format json
multipass exec iphone6s-repro-20260930 -- cloud-init status
```

Na VM, ler `/etc/apt/sources.list.d/ubuntu.sources`, conferir `dpkg --verify ubuntu-keyring` e o SHA-256 do keyring. Se o DNS DHCP falhar, aplicar somente o contorno D2. O APT desta imagem usa HTTP, com índices assinados e hashes de pacotes; não é uma prova de TLS do transporte APT.

```bash
sudo apt-get -o APT::Update::Error-Mode=any -o Debug::Acquire::gpgv=true update
sudo env DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install \
  busybox-static cpio zstd file bash dropbear-bin ncurses-base util-linux git make \
  gcc libc6-dev ca-certificates curl openssh-client xz-utils
mkdir -m 700 /home/ubuntu/repro-evidence
git -c credential.helper= -c http.sslVerify=true clone --no-checkout \
  https://github.com/djalmajr/iphone6s-linux.git /home/ubuntu/project-source
git -C /home/ubuntu/project-source checkout --detach e8bd87913c06bddeed2485c0365e4d743ee46e8f
mkdir /home/ubuntu/m1n1
cd /home/ubuntu/m1n1
git init
git remote add origin https://github.com/HoolockLinux/m1n1.git
git -c credential.helper= -c http.sslVerify=true fetch --depth=1 --no-tags origin \
  d5a10ac52a6468484854419a6c5130f1d62073eb
git checkout --detach FETCH_HEAD
git -c credential.helper= -c http.sslVerify=true submodule update --init --depth=1 -- artwork
git -C artwork rev-parse HEAD
sha256sum rust/Cargo.lock
```

Conferir artwork `80d14f8b6f485b310e305a84b4b806361518ddd1`, lockfile `5ae145509cda84c067426690fee2083d5a51374fb9264c3c59d67f3f8d1321fb`, shallow verdadeiro, nenhuma tag e árvores rastreadas limpas. Ler Makefile, versionador e proc macro antes do build.

### Rust e cache Cargo novo

No clone do Mac que contém este relatório, criar a pasta privada com modo 700 e salvar o objeto `rust` de `docs/evidence/fresh-build-provenance.json` como `runtime/fresh-build-20260930/rust-components.json`, modo 600. Transferir esse JSON público para `/home/ubuntu/repro-evidence/rust-components.json` na VM. Ele contém as quatro URLs datadas e seus hashes, além do hash do manifesto.

Esta receita reúne os downloads conferidos. Na execução inicial, rustc falhou em HTTP/2 e passou ao repetir somente esse componente com HTTP/1.1. Para uma pasta nova:

```python
import hashlib
import json
import pathlib
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor

base = pathlib.Path("/home/ubuntu/toolchain-downloads")
base.mkdir(mode=0o700, exist_ok=False)
config = json.loads(pathlib.Path("/home/ubuntu/repro-evidence/rust-components.json").read_text())

def fetch(item):
    target = base / item["url"].rsplit("/", 1)[1]
    subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                    "--proto", "=https", "--proto-redir", "=https",
                    "--http1.1", "--connect-timeout", "20", "--max-time", "300",
                    "--output", str(target), item["url"]], check=True)
    target.chmod(0o600)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"], target.name
    if target.suffixes[-2:] == [".tar", ".xz"]:
        with tarfile.open(target, "r:xz") as archive:
            members = archive.getmembers()
            top = {pathlib.PurePosixPath(m.name).parts[0] for m in members}
            assert len(top) == 1, target.name
            for member in members:
                path = pathlib.PurePosixPath(member.name)
                assert not path.is_absolute() and ".." not in path.parts
                assert member.isfile() or member.isdir() or member.issym()
                if member.issym():
                    link = pathlib.PurePosixPath(member.linkname)
                    assert not link.is_absolute() and ".." not in link.parts
            archive.extractall(base, filter="data")
    print("verified", target.name, item["sha256"], flush=True)

manifest = {"url": config["manifest_url"], "sha256": config["manifest_sha256"]}
fetch(manifest)
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(fetch, config["components"]))
```

Ler `install.sh` completo de Cargo; comparar as outras variantes. Nesta distribuição, elas diferem somente na mensagem de sucesso. Conferir os caminhos em `manifest.in`, sem caminhos absolutos ou `..`. Instalar como usuário ubuntu:

```bash
for part in rustc-1.98.1-aarch64-unknown-linux-gnu cargo-1.98.1-aarch64-unknown-linux-gnu \
  rust-std-1.98.1-aarch64-unknown-linux-gnu rust-std-1.98.1-aarch64-unknown-none-softfloat; do
  bash /home/ubuntu/toolchain-downloads/$part/install.sh \
    --prefix=/home/ubuntu/toolchains/rust-1.98.1 --disable-ldconfig
done
export PATH=/home/ubuntu/toolchains/rust-1.98.1/bin:/usr/bin:/bin
export CARGO_HOME=/home/ubuntu/.cargo
export CARGO_HTTP_MULTIPLEXING=false
test ! -e "$CARGO_HOME"
cargo fetch --locked --manifest-path /home/ubuntu/m1n1/rust/Cargo.toml
```

Antes de compilar, conferir os quatro `.crate` contra o lockfile e seus arquivos extraídos contra os arquivos do tar: nesta execução, 64 + 23 + 14 + 30 = 131 arquivos corresponderam. Conferir fatfs no commit `4eccb50d011146fbed20e133d33b22f3c27292e7`, sem mudanças rastreadas. Não havia `build.rs` ou proc macros externos nesses insumos; o proc macro local foi lido. Compilar offline:

```bash
cd /home/ubuntu/m1n1
env -u M1N1_VERSION_TAG CARGO_NET_OFFLINE=true make -j2 ARCH= CHAINLOADING=1 \
  CARGO_FLAGS='--locked --offline --features chainload' build/m1n1.bin
sha256sum build/m1n1.bin
```

### Kernel, Herdr e identidades

Transferir somente o APK público preservado para `project-source/iphone-linux-tools/artifacts/` e repetir a [cadeia do índice assinado](KERNEL-VERIFY.md) dentro da VM. O verificador desta rodada foi OpenSSL 3.0.13; os três controles negativos passaram. Extrair somente membros regulares únicos: `boot/vmlinuz` como `artifacts/vmlinuz-apple-16k`, `boot/dtbs/apple/s8000-n71.dtb` como `artifacts/s8000-n71.dtb` e `usr/lib/modules/7.0.12/kernel/drivers/usb/gadget/function/usb_f_ncm.ko.zst` como `/home/ubuntu/iphone6s-modules/usb_f_ncm.ko.zst`. Não extrair o APK inteiro sobre o sistema.

```bash
zstd -d -q -o /home/ubuntu/iphone6s-modules/usb_f_ncm.ko \
  /home/ubuntu/iphone6s-modules/usb_f_ncm.ko.zst
```

Obter o asset `herdr-linux-aarch64` da release v0.9.1 com HTTPS obrigatório nos redirects, salvar como `/home/ubuntu/herdr-linux-aarch64` e conferir tanto tamanho (24.101.456 bytes) quanto digest da [API oficial](https://api.github.com/repos/herdrdev/herdr/releases/tags/v0.9.1): SHA-256 `f4ccf4de745f2cb9a39a983e9ba3703dad50ec2a58dea83026ceab721bbd8d9e`. Aplicar modo 755 somente após conferir.

No Mac, gerar cliente novo; a pasta deve estar protegida e o destino ausente:

```bash
ssh-keygen -q -t ed25519 -N '' -C iphone6s-fresh-build \
  -f runtime/fresh-build-20260930/client_ed25519
multipass transfer runtime/fresh-build-20260930/client_ed25519.pub \
  iphone6s-repro-20260930:/home/ubuntu/iphone_ed25519.pub
```

A chave privada cliente permanece no Mac. O builder gera a identidade de servidor nova na VM; o runtime e o initramfs conterão essa chave privada de servidor e devem permanecer privados, modo 600. O pin novo foi obtido de `iphone-host-public.txt` e conferido diferente do pin da implantação anterior.

### Imagem integrada

Na VM, após os insumos conferidos:

```bash
project=/home/ubuntu/project-source/iphone-linux-tools
cp "$project/phone/init/init" /home/ubuntu/init-iphone6s
cp "$project/phone/init/init-server" /home/ubuntu/init-server
cp "$project/phone/http/status" /home/ubuntu/iphone-status
bash "$project/scripts/build/build-initramfs.sh"
python3 "$project/scripts/build/build-runtime.py"
chmod 600 /home/ubuntu/iphone6s-runtime.tar.gz /home/ubuntu/iphone6s-initramfs.gz
bash "$project/scripts/build/build-server-image.sh"
cp /home/ubuntu/m1n1/build/m1n1.bin "$project/artifacts/m1n1.bin"
python3 "$project/scripts/build/compose-payload.py" \
  /home/ubuntu/iphone6s-server-initramfs.gz /home/ubuntu/iphone6s-repro-server.bin
```

Os dois scripts Bash usam sudo somente para nós de dispositivo e propriedade/leitura do rootfs da VM. A imagem integrada substitui o init mínimo de Telnet pelo init de servidor com SSH por chave.

## D3. Caminho Cargo faz parte da identidade do binário

- **Decisão:** usar `CARGO_HOME=/home/ubuntu/.cargo`, preparado exclusivamente com downloads desta VM.
- **Por quê:** o primeiro build usou `cargo-fresh`, incorporou dez referências a esse caminho e diferiu do componente conhecido. Copiar somente esse cache novo para o caminho padrão e recompilar offline produziu exatamente o SHA conhecido. Nenhum cache ou toolchain da VM antiga foi transferido.
- **Alternativas:** aceitar o componente diferente preserva a função pretendida, mas perde a prova de identidade; remapear caminhos altera a receita original.
- **Reverter:** baixo; primeiro build, segunda saída e logs foram preservados.
- **Onde:** esta receita e registro JSON.
- **Status:** aplicada; m1n1 idêntico.

## Resultado e verificação

A VM oficial lançou com Ubuntu 24.04.5 LTS ARM64, image hash `1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55`, sem mounts ou bridge. O APT validou quatro InRelease com a chave de arquivo Ubuntu registrada no JSON. Rust foi instalado sem sudo em prefixo privado e com ldconfig desativado. As árvores rastreadas permaneceram limpas.

| Gate | Resultado executado |
|---|---|
| m1n1 offline, cache novo | 1.196.032 bytes; SHA `13d49ab42c6e071857ca05c8414f30dca70699df8a3f472b9c70e4f1233a092b`, idêntico ao conhecido |
| Índice/kernel | Cadeia assinada passou; três alterações foram rejeitadas |
| Estrutura do initramfs | 2.970 entradas; 11 arquivos essenciais correspondem ao rootfs; UID/GID 0 e permissões conferidos |
| ELF | 15 arquivos encontrados; segmentos de carga com alinhamento de pelo menos 16 KB |
| Bash + SSH | Login real do Mac, cliente novo, pin estrito; Bash 5.2.21 e hostname do namespace |
| HTTP/CGI | 200 e título esperado; ausência de device-tree do iPhone na VM registrada |
| Herdr | 0.9.1; servidor próprio, painel Bash com marcador e continuidade entre conexões SSH |
| Limites SSH | Chave não autorizada rejeitada; pin incorreto rejeitado |
| Preservação | Payload conhecido e identidades anteriores mantidos; privada cliente ausente dos bytes do initramfs |
| Limpeza | Namespace/veth/serviços removidos, hostname guest preservado, DNS revertido e VM parada |

O teste de userspace criou uma cópia privada do rootfs, um netns próprio e um par veth somente dentro da VM. Usou namespaces privados de montagem, UTS e PID, proc e devpts novos, dispositivos básicos em tmpfs, BusyBox `--install -s` antes do startup, sem executar o `/init` que inicializa o USB físico. O roteiro executado está em [check-userspace.sh](../scripts/build/check-userspace.sh). Ele exige destinos novos e termina ao criar `/home/ubuntu/repro-evidence/userspace-finish` ou após cinco minutos; não é um daemon para operação contínua.

O SSH do Mac usou `ProxyCommand=multipass exec iphone6s-repro-20260930 -- /usr/bin/busybox nc 172.16.42.1 22`, `-F /dev/null`, `BatchMode=yes`, `IdentitiesOnly=yes`, pin privado com alias `iphone6s-fresh-vm` e cliente novo. Nenhuma chave privada cliente entrou na VM. Herdr foi iniciado somente na sessão `iphone6s-fresh-repro`; seu painel foi criado e lido por IDs retornados pela API. Esse servidor foi encerrado antes da limpeza.

Dois problemas do harness foram corrigidos antes de aceitar resultados: faltavam links BusyBox antes do start-terminal; o primeiro detector ELF reconheceu zero arquivos. O gate final exigiu uma contagem positiva e encontrou 15. A descompressão inicial usou uma opção longa inválida de zstd; repetir somente esse passo com `-o` passou. Essas falhas não alteraram a candidata nem os fontes upstream.

O build emitiu um aviso de descritores jobserver do Cargo indisponíveis e os dois avisos upstream já conhecidos; concluiu com saída 0 e o componente idêntico. São avisos registrados, sem mudanças na fonte fixada. Os scripts de produção não foram alterados. Não há typechecker configurado para este conjunto Python/shell; parsing dos registros e sintaxe do harness foram verificados. Gates anteriores de código não relacionado foram reutilizados.

A candidata privada `runtime/fresh-build-20260930/iphone6s-repro-server.bin` tem 23.767.750 bytes e SHA-256 `274e632b599ba94efc3b6512402ee15762232a9a34e679d034afd0c04eebf496`. O runtime e initramfs privados foram trazidos com hashes conferidos. O hash integral não deve ser esperado em outra implantação com identidades e metadados novos.

**Pendente:** boot físico com as identidades novas, carga sustentada, estabilidade e as lacunas de proveniência já descritas. O wrapper atual usa payload/chaves fixos da implantação conhecida; este build não o retargeteou para a candidata. O próximo teste deverá preparar um perfil privado coerente de imagem/chave/pin sem substituir a seleção padrão. Não fechar #12 apenas por estes gates da VM.

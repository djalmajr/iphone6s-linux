# Kernel N71 a partir de fonte — #12

## Contexto

O APK 7.0.12 atual tem conteúdo autenticado por índice assinado, mas metadado `commit=-dirty`, sem configuração empacotada ou embutida identificada. Não permite vincular cada driver ao código consultado. Esta fase gera artefatos em uma VM; a integração será validada antes de usá-los no telefone.

Fonte escolhida: fork oficial `HoolockLinux/linux`, branch estável consultada `hoolock-stable`, commit imutável `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, versão declarada **7.2.0** e DT N71 presente. A branch principal consultada é 7.3-rc1 e não será usada nesta etapa. Compilar a fonte escolhida não reproduz byte a byte o APK 7.0.12: produz uma nova candidata rastreável, que exigirá gates próprios.

## Plano e limites

1. Criar VM Ubuntu ARM64 dedicada `iphone6s-kernel-20261001`, 2 CPUs/4 GiB, disco virtual 20 GiB, sem mounts do Mac e sem chaves/imagens do servidor. Conferir disco livre, origem da imagem, cloud-init e configuração; preservar VMs anteriores. Nenhuma dependência nova no macOS.
2. Instalar somente na VM dependências de compilação via APT com metadados assinados; registrar versões/keyring. Não aceitar pacotes não autenticados, habilitar execução de scripts baixados no Mac ou montar sua pasta pessoal.
3. Clonar fonte oficial via HTTPS e fixar o commit; conferir árvore limpa, versão e receitas. Preparar `defconfig` ARM64 e fragmento explícito N71/16 KiB/USB NCM incorporado. Registrar o `.config` final e verificar que as opções exigidas sobreviveram ao Kconfig. Não adicionar carregadores de outro SoC.
4. Compilar somente Image e DTB N71, sem instalar kernel ou módulos no Mac/VM. Manter build separado da fonte, limitar paralelismo a dois jobs, registrar log/status e hashes. Interromper se recursos forem insuficientes; não apagar caches ou imagens alheios para obter espaço.
5. Transferir apenas artefatos/configuração/proveniência para pasta privada do projeto; publicar receita e relatório sanitizado. Nenhuma imagem contendo chaves será publicada. Encerrar a VM própria quando o trabalho terminar.
6. Integração de initramfs/payload e boot físico serão outra fase, com identidade/pin corretos, snapshot, imagem antiga preservada e DFU coordenado. Sem prova física, não substituir a implantação atual nem encerrar #12/#21/#2.

Arquivos públicos previstos desta fase: este documento, `scripts/build/build-kernel-source.sh`, `scripts/build/kernel-n71.config`, `docs/evidence/kernel-source-build.json` e atualização da referência em `REPRODUCAO.md`. Completar/verificar cada fase de até cinco arquivos antes de ampliar escopo. Artefatos/logs/fontes de pesquisa ficam privados em `runtime/` e não entram no Git.

## D1. Nova candidata com proveniência verificável

- **Decisão:** fonte estável oficial em commit fixado, build em VM nova sem identidades do telefone; USB necessário incorporado no kernel.
- **Por quê:** separa código/driver verificável do APK `-dirty` e evita depender de módulo NCM com ABI da versão anterior. A VM não expõe chaves do Mac/servidor ao build.
- **Alternativas:** preservar somente o APK conserva a lacuna de fonte; usar a branch principal acrescenta uma versão RC; portar carga A10 não fornece binding/topologia comprovados para A9.
- **Reverter:** baixo nesta fase; parar a VM e conservar os artefatos privados. Implantação atual não depende do resultado.
- **Status:** kernel compilado, verificado e transferido; VM própria parada. Empacotamento verificado em perfil privado separado; gates físicos pendentes. [Integração](KERNEL-INTEGRATION.md).

## Critérios de verificação

- [x] Origem/recursos/mounts da VM e metadados APT registrados.
- [x] Commit/árvore/versão/configuração final conferidos; sem config obrigatório silenciosamente removido.
- [x] Build com saída 0, Image ARM64/16 KiB e DTB N71 correspondentes; configuração embutida igual e hashes dos resultados.
- [x] Receitas/parsing/ShellCheck e documentação verificados, branch publicada e issues atualizadas.
- [x] VM própria parada, originais preservados e artefatos privados.

O build não comprova suporte de carregamento, Wi-Fi, storage, reinício ou boot autônomo. #2 requer carga líquida/telemetria específica ou medição qualificada; #8 conserva essa dependência. Nenhum novo experimento DFU será iniciado sem disponibilidade do operador.

## Configuração conferida em 2026-10-01

A VM dedicada usa Ubuntu 24.04.5 ARM64, imagem `1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55`, sem mounts. APT recusou pacotes não autenticados; quatro assinaturas InRelease foram verificadas por `gpgv`, e o keyring passou em `dpkg --verify`. Versões e logs foram preservados na VM. O fetch HTTPS fixado terminou com árvore limpa e versão 7.2.0 conferida.

A primeira configuração foi recusada porque `BACKLIGHT_CLASS_DEVICE=m` limitou `BACKLIGHT_APPLE_DWI` a módulo. O fragmento agora exige ambos incorporados. A segunda tentativa, em outro diretório, preservou a primeira e conferiu as 47 opções obrigatórias antes de iniciar o build com dois jobs. Sintaxe Bash, ShellCheck e recusa real de execução no macOS passaram. O build terminou com saída 0; a integração foi verificada depois em perfil privado separado; boot físico desta candidata continua pendente.

[Registro sanitizado](evidence/kernel-source-build.json): fonte, imagem da VM, dependências, hashes dos inputs/configuração, resultados e limites. O checkpoint original de 3ee2692 registrava `status=compiling`; o resultado final registra `compiled_verified`, saída 0, outputs com hashes e VM parada. A integração posterior foi verificada em [KERNEL-INTEGRATION.md](KERNEL-INTEGRATION.md); boot físico não é declarado concluído.

[CI da PR em 3ee2692](https://github.com/djalmajr/iphone6s-linux/actions/runs/36806363771) e [CI do push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36806359794) concluíram com sucesso. Ubuntu/macOS executaram 79 testes cada: 70 aprovados e nove skips explícitos de VM/artefatos privados; 20 mutações de perfil e nove de retorno foram rejeitadas nos dois sistemas. Guard público, lint/parsing e sintaxe passaram; ShellCheck passou no Linux. Não há typechecker configurado. Esses gates conferem as fontes públicas e contratos sintéticos; não compilam este kernel nem comprovam hardware.

## Resultado real do build

`KERNEL_BUILD_VERIFIED 7.2.0-iphone6s-source`, saída 0. O log de compilação cobre 2242 segundos (37 min 22 s); esse intervalo exclui preparação, compressão final e transferências. `Image` tem 52.070.912 bytes, ARM64/16 KiB conferidos pelo header; gzip corresponde exatamente à imagem descomprimida. `Image.gz` tem 15.659.651 bytes. O DTB tem 22.884 bytes e compatibles `apple,n71 apple,s8000 apple,arm-platform`; seu SHA-256 é idêntico ao DTB preservado, sem atribuir por isso uma origem exata ao kernel 7.0.12.

O extrator da fonte fixada recuperou a configuração da imagem; `cmp` e SHA-256 conferiram igualdade com a configuração usada no build. `vmlinux` contém os símbolos `apple_wdt_driver`, `apple_wdt_of_match` e `apple_wdt_restart`. Isso liga o driver à nova candidata compilada, sem provar binding ou reinício físico no A9. A árvore rastreada da fonte permaneceu limpa após o build.

Artefatos/logs foram transferidos para `runtime/kernel-source-build-20261001/` e seus hashes recalculados no Mac. O inventário inicial da VM já existia nessa pasta; foi preservado. A primeira transferência de logs recusou a subpasta ausente, criada com modo privado antes de repetir somente essa cópia. Diretórios 700, arquivos privados 600; verificador de cópias e relatórios locais preservados. Payloads conhecido e da candidata anterior mantiveram seus hashes. DNS temporário revertido e somente `iphone6s-kernel-20261001` parada. Nenhum kernel foi instalado ou enviado ao iPhone nesta fase.

## Receita de reprodução

Multipass já deve estar instalado no Mac. Confira que o nome escolhido está ausente; não reutilize uma VM com identidades do servidor. Os comandos abaixo partem da raiz deste repositório. Preserve pelo menos 10 GiB livres no Mac durante a construção; o script também exige 8 GiB livres no guest antes de começar.

```bash
multipass launch 24.04 --name iphone6s-kernel-20261001 --cpus 2 --memory 4G --disk 20G
multipass info iphone6s-kernel-20261001 --format json
multipass exec iphone6s-kernel-20261001 -- cloud-init status
multipass shell iphone6s-kernel-20261001
```

No shell da VM, leia `/etc/apt/sources.list.d/ubuntu.sources` e confira `dpkg --verify ubuntu-keyring`. A imagem usa índices APT assinados; isso não autentica por TLS o transporte HTTP dos pacotes. Não habilite `--allow-unauthenticated`, `trusted=yes` ou repositório inseguro. Se o resolver DHCP não funcionar, use apenas na VM `sudo resolvectl dns enp0s1 1.1.1.1 8.8.8.8`; reverta ao terminar os downloads. Na execução registrada, DHCP substituiu o primeiro ajuste durante o fetch; a segunda tentativa manteve o mesmo checkout e passou após reaplicar o ajuste e limpar o cache da VM.

```bash
set -euo pipefail
umask 077
mkdir -m 700 /home/ubuntu/kernel-preflight-20261001
sudo apt-get -o APT::Update::Error-Mode=any \
  -o APT::Get::AllowUnauthenticated=false \
  -o Acquire::AllowInsecureRepositories=false update \
  > /home/ubuntu/kernel-preflight-20261001/apt-update.log 2>&1
sudo env DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends \
  -o APT::Get::AllowUnauthenticated=false \
  -o Acquire::AllowInsecureRepositories=false install \
  gcc make git flex bison bc libssl-dev libelf-dev pkg-config python3 device-tree-compiler \
  > /home/ubuntu/kernel-preflight-20261001/apt-install.log 2>&1
mkdir -m 700 /home/ubuntu/kernel-n71-source-20261001
git -C /home/ubuntu/kernel-n71-source-20261001 init
git -C /home/ubuntu/kernel-n71-source-20261001 remote add origin https://github.com/HoolockLinux/linux.git
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
git -C /home/ubuntu/kernel-n71-source-20261001 \
  -c core.hooksPath=/dev/null -c http.sslVerify=true -c http.followRedirects=false \
  -c credential.helper= -c protocol.allow=never -c protocol.https.allow=always \
  fetch --depth=1 --no-tags origin 958481f87fee0949ff6a9a4af77f7eb6dac8a149
git -C /home/ubuntu/kernel-n71-source-20261001 -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
git -C /home/ubuntu/kernel-n71-source-20261001 rev-parse HEAD
git -C /home/ubuntu/kernel-n71-source-20261001 status --porcelain --untracked-files=no
sudo resolvectl revert enp0s1
mkdir -m 700 /home/ubuntu/kernel-inputs-20261001
exit
```

APT e a tag de imagem são mutáveis. Compare versões e hash da imagem com o registro da execução; este procedimento fixa a fonte do kernel, mas não promete reprodução futura byte a byte sem preservar também imagem e pacotes. Na execução registrada foram verificadas separadamente as quatro assinaturas InRelease com `gpgv`, além da validação normal do APT. Logs, versões, configuração e hashes dos inputs devem acompanhar cada nova tentativa.

No Mac, transfira somente a receita e o fragmento, confira seus SHA-256 no host e no guest, e execute como usuário `ubuntu`:

```bash
multipass transfer iphone-linux-tools/scripts/build/build-kernel-source.sh \
  iphone-linux-tools/scripts/build/kernel-n71.config \
  iphone6s-kernel-20261001:/home/ubuntu/kernel-inputs-20261001/
shasum -a 256 iphone-linux-tools/scripts/build/build-kernel-source.sh \
  iphone-linux-tools/scripts/build/kernel-n71.config
multipass exec iphone6s-kernel-20261001 -- sha256sum \
  /home/ubuntu/kernel-inputs-20261001/build-kernel-source.sh \
  /home/ubuntu/kernel-inputs-20261001/kernel-n71.config
multipass exec iphone6s-kernel-20261001 -- bash \
  /home/ubuntu/kernel-inputs-20261001/build-kernel-source.sh \
  /home/ubuntu/kernel-n71-source-20261001 /home/ubuntu/kernel-n71-build-20261001-v2
```

O diretório de build deve ser novo. O script conserva uma tentativa anterior e recusa diretório dentro da fonte, commit diferente, árvore rastreada modificada, usuário root, sistema/arquitetura incompatíveis ou opções Kconfig demovidas. `KERNEL_BUILD_VERIFIED` exige build bem-sucedido, magic/header ARM64 com páginas de 16 KiB e compatible N71 no DTB. Não use ausência de mensagem de erro como substituto desse gate. Nenhum comando de instalação é executado.

Depois de saída 0, confira também a configuração embutida usando o extrator da mesma fonte fixada. Execute no shell da VM, antes de transferir:

```bash
set -euo pipefail
umask 077
kernel_guest_source=/home/ubuntu/kernel-n71-source-20261001
kernel_guest_build=/home/ubuntu/kernel-n71-build-20261001-v2
sh "$kernel_guest_source/scripts/extract-ikconfig" "$kernel_guest_build/artifacts/Image" \
  > "$kernel_guest_build/artifacts/config-embedded"
cmp "$kernel_guest_build/artifacts/config" "$kernel_guest_build/artifacts/config-embedded"
sha256sum "$kernel_guest_build/artifacts/config-embedded"
```

Copie `Image`, `Image.gz`, `s8000-n71.dtb`, `config`, `config-embedded`, `provenance.json` e os logs para uma pasta nova em `iphone-linux-tools/runtime/`, com modos privados. Recalcule os hashes após a transferência. Confira o DNS DHCP e pare somente a VM própria com `multipass stop iphone6s-kernel-20261001`. A integração do kernel e o teste no iPhone seguem uma fase própria; mantenha os payloads conhecidos e snapshots preservados.

## Patchset DART separado — #34

O writer S5L do commit fixado perde bits de outros streams e não desloca o
valor pelo SID. A [evidência](evidence/dart-s5l-stream-tcr.json) reproduz a
função original e a correção com MMIO simulado. Não comprova layout/SID do
N71 nem autoriza habilitar DMA. Topologia DART continua desativada no perfil.

Para agregar esse fix a uma futura imagem, preserve o checkout e o output
funcionais. Crie uma worktree separada, com HEAD no mesmo commit. Transfira
somente código público para um bundle com a estrutura abaixo; nenhuma chave,
firmware, captura DT ou calibração entra na VM:

```text
/home/ubuntu/n71-patch-inputs-20261002/
  scripts/build/build-kernel-source.sh
  scripts/build/kernel-n71.config
  scripts/build/kernel_patchset.py
  phone/kernel/patches/0001-s5l8960x-dart-stream-tcr.patch
```

Confira hashes host/guest antes de executar. O patch está fixado em
`da321ed0e213a5ab4e3e27691f64d529b186474c556a00a2e7ee90957c785f74`.
No shell da VM, como usuário ubuntu:

```bash
set -euo pipefail
umask 077
kernel_baseline_source=/home/ubuntu/kernel-n71-source-20261001
kernel_patch_source=/home/ubuntu/kernel-n71-dart-source-20261002
kernel_patch_inputs=/home/ubuntu/n71-patch-inputs-20261002
test ! -e "$kernel_patch_source"
git -c core.hooksPath=/dev/null -c core.fsmonitor=false \
  -C "$kernel_baseline_source" worktree add --detach "$kernel_patch_source" \
  958481f87fee0949ff6a9a4af77f7eb6dac8a149
python3 "$kernel_patch_inputs/scripts/build/kernel_patchset.py" \
  apply "$kernel_patch_source" n71-dart-tcr-v1
python3 "$kernel_patch_inputs/scripts/build/kernel_patchset.py" \
  check "$kernel_patch_source" n71-dart-tcr-v1
git -C "$kernel_baseline_source" diff --exit-code
```

Aplicação é idempotente e exige `.git` regular de worktree vinculada, base
fixada, patch/hunk originais por SHA e conteúdo completo esperado do único
arquivo alterado. Recusa symlinks, staged/untracked/deltas extras e flags de
índice que escondam mudanças. Não reseta ou apaga alterações recusadas.
`check` retorna JSON sem caminhos pessoais, com hashes dos blobs/patch.

Somente quando a imagem agregar os drivers/configurações necessários, rode:

```bash
bash "$kernel_patch_inputs/scripts/build/build-kernel-source.sh" \
  "$kernel_patch_source" /home/ubuntu/kernel-n71-dart-build-new n71-dart-tcr-v1
```

O modo padrão de dois argumentos continua exigindo fonte limpa. O terceiro
argumento aceita exclusivamente esse patchset e verifica o estado exato antes
e depois do build. `artifacts/provenance.json` inclui `source_patchset`; uma
candidata modificada não deve passar pelo compositor fixado ao Image baseline.
Exigir novo registro de outputs, configuração embutida e perfil separado na
fase de integração. Não mudar o perfil funcional só por build passar.

Gates de preparo são testes reais de Git/filesystem no Mac e VM, aplicação
na fonte fixada em worktree separada e objeto kernel/Werror. Nenhuma imagem
com esse patch foi qualificada fisicamente; integração, serialização TCR,
SID/mapeamento e faults seguem na [issue #34](https://github.com/djalmajr/iphone6s-linux/issues/34).

### Resultado do patchset — 2026-10-02

O build separado terminou com exit0 e `KERNEL_BUILD_VERIFIED`. Os47 valores
obrigatórios Kconfig sobreviveram; configuração extraída do Image igual à
usada no build. Gzip/Image, header ARM64/16KiB, DTB N71 e hashes após cópia
privada para o Mac foram conferidos. A worktree conservou exatamente o
patchset antes/depois, e a fonte funcional anterior permaneceu intacta.

[Registro selecionado](evidence/kernel-dart-build.json): Image SHA
`844a85705d0ce79ee97e878bbbd4ff62e76054e6547eabcdf36882e2eef6bd52`;
DTB igual à baseline. Artefatos estão somente no runtime privado. Nenhuma
imagem desse patchset foi instalada, enviada ao telefone ou qualificada
fisicamente. O compositor da baseline continua fixado ao registro anterior;
a integração precisa de gate próprio e perfil separado. Não trocar hashes
do registro antigo para fazê-lo aceitar outro kernel.

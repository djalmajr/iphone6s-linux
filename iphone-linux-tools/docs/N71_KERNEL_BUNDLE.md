# Candidata agregada N71 — fonte, Image e módulos verificados

O bundle `n71-dart-serdev-v1` reúne a correção DART S5L8960X e a operação
serdev de stop bits. Empacotar os deltas antes de um boot ajuda a reduzir
DFUs. **Image, módulos, perfis e o primeiro boot físico foram verificados.**
A [sessão agrupada](N71_LINK_EXPERIMENT.md) confirmou link PCIe e GPIO2 somente
de leitura. [Módulos Wi-Fi PCIe](N71_WIFI_MODULES.md) agora compilam externamente
para esse mesmo Image. Wi-Fi, gauge e carga sustentada ainda não estão
qualificados. As seções abaixo preservam o histórico das etapas de build.

## Identidade e preservação

- Fonte base: commit958481f87fee0949ff6a9a4af77f7eb6dac8a149.
- Patches: `0001-s5l8960x-dart-stream-tcr.patch` e
  `0002-serdev-stop-bits.patch`, ambos fixados porSHA.
- Quatro arquivos completos conferidos: DART, header serdev, core e TTY.
- Identificação exigida para a futura build: `-iphone6s-dart-serdev1`.
  A build de objetos confirmou `7.2.0-iphone6s-dart-serdev1`.
- Worktree e output próprios; fonte, builds e perfil funcionais preservados.

O [helper](../scripts/build/kernel_bundle.py) recusa checkout original,
alias/symlink, HEAD divergente, índice ocultando mudanças, patch alterado,
blob divergente, bundle parcial, staging e trabalho externo. Aplica ambos
os patches numa única chamada Git após `--check`; repetir no worktree
já aplicado é idempotente. Não deve haver outros escritores nesse worktree.
Um erro não autoriza apagar/resetar trabalho para fazer o guard passar.

O helper registra a versão necessária; ele não configura nem compila o
kernel. Na prova de objetos, a configuração foi copiada para um output novo
e seu LOCALVERSION alterado explicitamente. Como serdev mudou layout de
operações, módulos da implantação atual não são candidatos para essa ABI.
O helper DART legado e seus registros/perfis continuam separados.

## Reprodução na VM dedicada

Dependências e origem da VM: [build fonte](KERNEL-SOURCE-BUILD.md).
Somente fonte, patches e testes públicos vão para a VM. Firmware, calibração,
chaves, snapshots e DT runtime privados permanecem fora dela.

Os caminhos abaixo correspondem à execução registrada. Já existem nesta
VM: para repetir, escolha novos nomes de worktree/output e preserve os
resultados anteriores. No diretório da cópia pública do projeto:

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-bundle-source-20261002
build_dir=/home/ubuntu/kernel-n71-bundle-build-20261002
base_dir=/home/ubuntu/kernel-n71-source-20261001
test ! -e "$work_dir" && test ! -L "$work_dir"
test ! -e "$build_dir" && test ! -L "$build_dir"
git -C "$base_dir" worktree add --detach "$work_dir" \
  958481f87fee0949ff6a9a4af77f7eb6dac8a149
python3 scripts/build/kernel_bundle.py apply "$work_dir"
python3 scripts/build/kernel_bundle.py check "$work_dir"
mkdir -m 700 "$build_dir"
cp /home/ubuntu/kernel-n71-build-20261001-v2/.config "$build_dir/.config"
"$work_dir/scripts/config" --file "$build_dir/.config" \
  --set-str LOCALVERSION -iphone6s-dart-serdev1
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 \
  KCFLAGS=-Werror olddefconfig
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror drivers/iommu/apple-dart.o \
  drivers/tty/serdev/core.o drivers/tty/serdev/serdev-ttyport.o
cat "$build_dir/include/config/kernel.release"
python3 scripts/build/kernel_bundle.py check "$work_dir"
git -C "$base_dir" diff --exit-code
```

O apply da CLI só é permitido em Linux como usuário sem privilégios.
Nenhum comando instala resultados ou altera o aparelho.

## Gates executados e faltantes

Mac/ARM64: três testes com Git real e11 mutações detectadas por asserção.
Incluem preservação da fonte original, aplicação exata/idempotente,
recusas de escopo/integridade e metadados que não inventam boot/Image.
O helper também aplicou os patches na fonte pública real da VM e conferiu
os quatro blobs após compilar. Os três objetos são ELF64/AArch64 e passaram
Werror. [Hashes, configuração e escopo](evidence/kernel-n71-bundle.json).

```sh
python3 -B -m unittest discover -s tests -p test_kernel_bundle.py -v
python3 tests/run_kernel_bundle_mutations.py
```

Objetos não provam comportamento elétrico. O link completo, configuração
embutida, exports e rebuild dos diagnósticos passaram na fase seguinte,
registrada abaixo. Antes de deployment ainda faltam perfil separado e
gate de boot físico. A receita de build legado continua separada.
UART5/I2C1 continuam desativados; ownership GPIO2/clocks, cleanup SN2400 e
identificação do gauge seguem em [desenvolvimento HDQ](N71_HDQ.md).

## Integração preparada, dependente de Image completo

O integrador agora aceita seleção explícita
`--kernel-patchset n71-dart-serdev-v1`. Exige um registro separado
`docs/evidence/kernel-n71-bundle-build.json` com status `compiled_verified`,
Image, modpost e export serdev conferidos, base/patches/quatro blobs fixados,
release `7.2.0-iphone6s-dart-serdev1` e configuração embutida correspondente.
Enquanto esse registro de build completo estiver ausente, a integração
real é recusada; o registro de objetos acima não serve como substituto.

DART, serdev e seu adapterTTY devem estar incorporados. O initramfs não
pode trazer módulos extras da ABI anterior: arquivos sob `lib/modules/` e
módulos `.ko` ou comprimidos são recusados antes de criar saída. O NCM legado
conhecido pode ser retirado pela migração existente para builtin. Demais
entradas, identidades e perfil original permanecem preservados.

Depois dos gates reais e usando uma pasta privada nova:

```sh
python3 scripts/build/integrate-source-kernel.py \
  --kernel-patchset n71-dart-serdev-v1 \
  --kernel-dir "$PWD/runtime/BUNDLE-ARTEFATOS-VERIFICADOS" \
  --output-dir "$PWD/runtime/BUNDLE-PERFIL-NOVO"
```

`IPHONE_LINUX_PROFILE` deve apontar para o perfil anterior a preservar.
Esse comando prepara um perfil local; não faz USB/DFU ou escolhe o perfil
padrão. Rebuild dos módulos e prova física da ABI nova ainda precisam de
gates reais.

Gates sintéticos do integrador: 14 testes e 19 mutações por asserção no
Mac/ARM64. Na VM, dois timeouts durante a compilação foram tratados como
interrupções; os casos pendentes passaram após reduzir a prioridade do
build e usar a espera limitada do runner. Nenhum timeout contou como kill.

## Composição diagnóstica com release selecionada

O compositor também aceita `--kernel-patchset n71-dart-serdev-v1` e
encaminha a seleção ao validador de artefatos acima. A release conferida
no registro determina o vermagic exigido do módulo; baseline e bundle
não são intercambiáveis. Releases desconhecidas ou marcadas com `+`
são recusadas. O padrão continua o baseline registrado.

O compositor preserva o layout exato do payload, loader, kernel,
initramfs e identidades; troca somente o DTB por sua versão diagnóstica
conferida. O módulo fica fora do initramfs e não é carregado automaticamente.
Release e patchset selecionados entram na proveniência privada.

Depois de integrar o kernel e rebuildar/conferir o módulo, selecione
pastas privadas e nova saída para a composição:

```sh
python3 scripts/build/compose-n71-diagnostic.py \
  --kernel-patchset n71-dart-serdev-v1 \
  --source-profile "$PWD/runtime/BUNDLE-PERFIL-VERIFICADO/deployment.json" \
  --kernel-dir "$PWD/runtime/BUNDLE-ARTEFATOS-VERIFICADOS" \
  --diagnostic-dir "$PWD/runtime/DTB-DIAGNOSTICO-VERIFICADO" \
  --module "$PWD/runtime/BUNDLE-MODULOS/n71-pcie-diagnostic.ko" \
  --module-sha256 HASH-VERIFICADO \
  --output-dir "$PWD/runtime/BUNDLE-DIAGNOSTICO-NOVO"
```

Não é receita para reutilizar o módulo 7.2.0-iphone6s-source. São exigidos
ELF relocável AArch64, hash selecionado e vermagic correspondente ao
kernel novo. Testes sintéticos: cinco casos e cinco mutações por asserção
no Mac/ARM64 (ABI conhecida, cruzamento de ABI, arquitetura, vínculo
do payload e máscara DT). Não houve composição real ou USB nessa prova.

## Image completo e diagnósticos da ABI nova — 2026-10-03

[Registro completo separado](evidence/kernel-n71-bundle-build.json):
`7.2.0-iphone6s-dart-serdev1`, Image ARM64/16KiB de 52.070.912 bytes,
gzip correspondente, configuração embutida idêntica e DTB N71 igual ao
preservado. `serdev_device_set_stop_bits` está no vmlinux e no export GPL
de vmlinux.symvers. Fonte/bundle foram conferidos antes/depois; somente
LOCALVERSION mudou na configuração. O registro anterior de objetos foi
mantido como evidência daquela etapa.

A única build terminou com saída 0 e 2352 s (39 min 12 s), partindo do output
já configurado e seus três objetos. O intervalo inclui link, verificações,
cópias e gzip; exclui preparação anterior e transferências ao Mac.
VM tinha 6.989.680 KiB livres (≈6,67 GiB), contra 1.082.716 KiB do output
completo anterior mais 2.097.152 KiB de margem exigida. Não reduzimos o requisito de 8 GiB do
builder que inicia um output novo. Os builds anteriores foram preservados.

Na VM, depois da configuração/objetos acima, a conclusão registrada usa:

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-bundle-source-20261002
build_dir=/home/ubuntu/kernel-n71-bundle-build-20261002
epoch=$(git -C "$work_dir" show -s --format=%ct HEAD)
export SOURCE_DATE_EPOCH="$epoch"
export KBUILD_BUILD_TIMESTAMP="$(date -u -d "@$epoch" '+%a %b %e %T %Y')"
export KBUILD_BUILD_USER=build KBUILD_BUILD_HOST=iphone6s-kernel-source KBUILD_BUILD_VERSION=1
export LC_ALL=C LOCALVERSION=
python3 scripts/build/kernel_bundle.py check "$work_dir"
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror Image apple/s8000-n71.dtb
python3 scripts/build/kernel_bundle.py check "$work_dir"
"$work_dir/scripts/extract-ikconfig" "$build_dir/arch/arm64/boot/Image" \
  > "$build_dir/CONFIG-EXTRAIDO-NOVO"
cmp "$build_dir/.config" "$build_dir/CONFIG-EXTRAIDO-NOVO"
nm "$build_dir/vmlinux" | sed -n '/ serdev_device_set_stop_bits$/p'
```

Na execução, logs/cópias foram para `full-link-20261003`, subpasta privada
nova. Para repetir, use nomes novos e recuse arquivos de saída já existentes.
Não basta aceitar qualquer linha do nm: o gate exigiu símbolo T/t único e
export GPL correspondente, além dos hashes de todos os artefatos.

Os diagnósticos da fase 50 foram recompilados em outro diretório M com a
ABI nova. A primeira tentativa parou porque `scripts/module.lds` estava
ausente no output de Image; `modules_prepare` gerou o pré-requisito e
somente o link externo foi repetido, sem suprimir erros:

```sh
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 modules_prepare
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  M=/home/ubuntu/n71-diagnostic-bundle-abi-inputs-20261003/phone/kernel \
  KBUILD_EXTRA_SYMBOLS="$build_dir/vmlinux.symvers" modules
```

Esse diretório M contém cópia apenas das fontes públicas de `phone/kernel`.
Kbuild pode avisar da ausência de Module.symvers global; usamos os exports
reais do mesmo vmlinux em KBUILD_EXTRA_SYMBOLS, com erros de símbolo fatais.
Não foi usado KBUILD_MODPOST_WARN. Fonte, Image e configuração mantiveram
seus hashes após a preparação dos módulos. [Documentação da fonte fixada
sobre módulos externos](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/Documentation/kbuild/modules.rst).

Ambos passaram Werror/modpost, ELF relocável AArch64 e vermagic exato da
release nova. Todos os hashes foram recalculados após transferência para
`runtime/kernel-n71-bundle-artifacts-20261003/`, privada no Mac. Imagens,
módulos e logs não foram publicados. Nada foi instalado ou carregado no
telefone; [descoberta de link](N71_LINK_EXPERIMENT.md), Wi-Fi/DMA e HDQ
físicos continuam gates futuros.

## Composição real separada — 2026-10-03

O integrador e o compositor foram executados com os artefatos conferidos,
seleção explícita do bundle e saídas novas em `runtime/`. O [registro
sanitizado](evidence/n71-bundle-profile.json) documenta os gates reais.
A integração troca kernel/DTB; a composição aplica somente o delta DTB
diagnóstico validado. As cinco entradas do initramfs permaneceram idênticas
ao perfil fonte: orçamento USB declarado de 500 mA, identidades preservadas
e nenhum módulo incorporado ou carregado automaticamente. A declaração
USB não mede corrente nem prova carregamento.

Perfis privados no Mac:

- Base: `runtime/n71-bundle-base-profile-20261003/deployment.json`.
- Diagnóstico: `runtime/n71-bundle-diagnostic-profile-20261003/deployment.json`.
- Artefatos: `runtime/kernel-n71-bundle-artifacts-20261003/`.

Os dois módulos externos foram conferidos por hash, ELF e ABI nova. Arquivos
600/pastas 700; chaves permaneceram no Mac. Um snapshot de 44 entradas passou
na validação do armazenamento local. Isso comprova composição e disponibilidade
de restauração, sem comprovar restore no kernel novo. Nenhum perfil padrão
foi alterado e nenhuma ação USB ocorreu nessa etapa. O coletor e o boot físico
agrupado passaram depois, conforme o [registro físico](N71_LINK_EXPERIMENT.md).

## Candidata GPIO/PMGR separada — preparação da fonte

O profile explícito `n71-dart-serdev-power-v1` reúne as patches001 a006:
DART, serdev, propagação de erros GPIO, callbacks/probe PMGR e cleanup da
falha de publicação. Exige LOCALVERSION `-iphone6s-dart-serdev-power1`.
O default `n71-dart-serdev-v1` e o perfil físico funcional são preservados.
Não altera DT nem habilita I2C1, HDQ ou carregador. O nome identifica as
correções de providers; **não significa carregamento funcional**.

O helper confere hashes das seis patches e seis arquivos completos na
mesma base958481f. Uma aplicação parcial do bundle legado é recusada
quando se seleciona power. Todas as patches passam pelo Git --check antes
do apply conjunto, incluindo o encadeamento004→005→006 sobre o mesmo arquivo.
Erro de patch tardia deixa o candidato intacto. Os gates sintéticos usam
Git real; não qualificam hardware, Image ou módulos para a ABI futura.

Na VM dedicada, a partir do diretório público do projeto:

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-power-source-20261004
legacy_src=/home/ubuntu/kernel-n71-bundle-source-20261002
test ! -e "$work_dir" && test ! -L "$work_dir"
git -C "$legacy_src" worktree add --detach "$work_dir" \
  958481f87fee0949ff6a9a4af77f7eb6dac8a149
python3 scripts/build/kernel_bundle.py apply "$work_dir" \
  --profile n71-dart-serdev-power-v1
python3 scripts/build/kernel_bundle.py check "$work_dir" \
  --profile n71-dart-serdev-power-v1
python3 -B -m unittest discover -s tests -p test_kernel_power_bundle.py -v
python3 tests/run_kernel_bundle_mutations.py
```

Escolha nomes novos ao reproduzir: o worktree acima não deve ser apagado
para permitir nova execução. A fonte aplicada terá somente seis mudanças
esperadas. A [prova selecionada](evidence/kernel-n71-power-bundle.json)
registra gates e digests. Full Image/link, rebuild de módulos, integração
de perfil e boot permanecem etapas separadas. Nenhum novo DFU é necessário
para conferir essa fonte.

### Espaço da VM

A VM dedicada foi ampliada de20 para32GiB com o [procedimento oficial do
Multipass](https://canonical.com/multipass/docs/latest/how-to-guides/manage-instances/modify-an-instance/).
O Mac tinha215GiB livres; nenhum processo make estava ativo. Foram executados
`multipass stop iphone6s-kernel-20261001`,
`multipass set local.iphone6s-kernel-20261001.disk=32G` e
`multipass start iphone6s-kernel-20261001`. O filesystem expandiu automaticamente:
18.360.807.424 bytes livres antes do checkout novo. Não se modificou partição
manualmente nem se instalou pacote/configuração global. Config/Image/exports
do rollback conservaram seus hashes. A próxima build usa output novo e
mantém o requisito de8GiB livres antes de iniciá-lo.

## Image completo da candidata GPIO/PMGR — 2026-10-04

[Registro separado](evidence/kernel-n71-power-bundle-build.json):
`7.2.0-iphone6s-dart-serdev-power1`, Image ARM64/16KiB de52.070.912 bytes,
configuração embutida exata, modpost e export GPL serdev conferidos.
GPIO/PMGR compilados como objetos incorporados, sem MODULE. A configuração
só mudou LOCALVERSION; DTB conservou o hash do bundle anterior.
Config/Image/exports e source do rollback foram preservados.

A conclusão levou761s (12min41s), incluindo prepare, Image/DTB, verificações,
gzip e modules_prepare; exclui preparo inicial da configuração e transferências.
O primeiro script parou antes de Image por ler kernel.release antes de prepare.
O output próprio já configurado foi reutilizado, com logs v2 novos;
nenhuma falha foi apagada ou contada como build aprovada.

Para reproduzir, use o source aplicado acima e um output novo. Abaixo,
os caminhos correspondem à execução registrada; não sobrescreva os resultados.

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-power-source-20261004
build_dir=/home/ubuntu/kernel-n71-power-build-20261004
legacy_build=/home/ubuntu/kernel-n71-bundle-build-20261002
test ! -e "$build_dir" && test ! -L "$build_dir"
python3 scripts/build/kernel_bundle.py check "$work_dir" \
  --profile n71-dart-serdev-power-v1
python3 - "$build_dir" <<'PY'
from pathlib import Path
import shutil
import sys
assert shutil.disk_usage(Path(sys.argv[1]).parent).free >= 8 * 1024**3
PY
mkdir -m 700 "$build_dir"
cp "$legacy_build/.config" "$build_dir/.config"
"$work_dir/scripts/config" --file "$build_dir/.config" \
  --set-str LOCALVERSION -iphone6s-dart-serdev-power1
epoch=$(git -C "$work_dir" show -s --format=%ct HEAD)
export SOURCE_DATE_EPOCH="$epoch"
export KBUILD_BUILD_TIMESTAMP="$(date -u -d "@$epoch" '+%a %b %e %T %Y')"
export KBUILD_BUILD_USER=build KBUILD_BUILD_HOST=iphone6s-kernel-source KBUILD_BUILD_VERSION=1
export LC_ALL=C LOCALVERSION=
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror olddefconfig
python3 - "$legacy_build/.config" "$build_dir/.config" <<'PY'
from pathlib import Path
import sys
before, after = [Path(name).read_text() for name in sys.argv[1:]]
assert after == before.replace('CONFIG_LOCALVERSION="-iphone6s-dart-serdev1"',
                               'CONFIG_LOCALVERSION="-iphone6s-dart-serdev-power1"')
PY
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror prepare
test "$(cat "$build_dir/include/config/kernel.release")" = 7.2.0-iphone6s-dart-serdev-power1
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror Image apple/s8000-n71.dtb
python3 scripts/build/kernel_bundle.py check "$work_dir" \
  --profile n71-dart-serdev-power-v1
"$work_dir/scripts/extract-ikconfig" "$build_dir/arch/arm64/boot/Image" \
  > "$build_dir/config-embedded-checked"
cmp "$build_dir/.config" "$build_dir/config-embedded-checked"
cmp "$build_dir/arch/arm64/boot/dts/apple/s8000-n71.dtb" \
  "$legacy_build/arch/arm64/boot/dts/apple/s8000-n71.dtb"
nm "$build_dir/vmlinux" | sed -n '/ serdev_device_set_stop_bits$/p'
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror modules_prepare
sha256sum "$build_dir/.config" "$build_dir/arch/arm64/boot/Image" "$build_dir/vmlinux.symvers"
sha256sum "$legacy_build/.config" "$legacy_build/arch/arm64/boot/Image" "$legacy_build/vmlinux.symvers"
```

A prova registrada exigiu símbolo T único, export GPL único e hashes antes/
depois do legado; a linha nm isolada não substitui essas validações. Os cinco
artefatos e logs foram empacotados/transferidos com SHA e recalculados no Mac,
em `runtime/kernel-n71-power-artifacts-20261004/`. O validador real
`kernel_inputs(..., 'n71-dart-serdev-power-v1')` aceitou esse conjunto.
Nada foi instalado no telefone ou escolhido como default.

## Módulos e perfis da ABI power — 2026-10-04

Os cinco módulos foram recompilados contra esse Image, com Werror/modpost,
ELF relocatable AArch64 e vermagic exato
`7.2.0-iphone6s-dart-serdev-power1 SMP preempt mod_unload aarch64`.
Os corpos das fontes permaneceram iguais; os gates de lógica anteriores
continuam separados da prova de ABI. Os hashes, tamanhos e inputs estão no
[registro de módulos e composição](evidence/n71-power-profile.json).

Na VM, transfira somente `phone/kernel/` do checkout público para um diretório
novo. O Makefile seleciona PCIe, WLAN, GPIO HDQ, topologia I2C e PMGR;
nenhum provider incorporado ao Image é duplicado. A execução registrada usou
`/home/ubuntu/n71-power-modules-v1-inputs-20261004/phone/kernel`.
Para uma reprodução, a partir da raiz do checkout público na VM:

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-power-source-20261004
build_dir=/home/ubuntu/kernel-n71-power-build-20261004
module_dir=/home/ubuntu/n71-power-modules-repro/phone/kernel
test ! -e "$module_dir" && test ! -L "$module_dir"
mkdir -p "$module_dir"
cp phone/kernel/Makefile phone/kernel/*.c phone/kernel/*.h "$module_dir/"
test "$(cat "$build_dir/include/config/kernel.release")" = 7.2.0-iphone6s-dart-serdev-power1
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror M="$module_dir" \
  KBUILD_EXTRA_SYMBOLS="$build_dir/vmlinux.symvers" modules
for name in n71-pcie-diagnostic n71-wlan-power-diagnostic n71-hdq-gpio-observe \
            n71-i2c-topology-observe n71-pmgr-power-observe; do
  test "$(modinfo -F vermagic "$module_dir/$name.ko")" = \
    '7.2.0-iphone6s-dart-serdev-power1 SMP preempt mod_unload aarch64'
  readelf -h "$module_dir/$name.ko"
  sha256sum "$module_dir/$name.ko"
done
```

Além dessas linhas de inspeção, a execução registrada validou os campos ELF,
SHA de todos os inputs e config/Image/exports antes e depois da build.
Os módulos e logs foram transferidos para
`runtime/n71-power-module-artifacts-20261004/` no Mac e conferidos novamente.
Não carregue módulos da release anterior no kernel power.

No Mac, o integrador compôs um perfil base privado novo a partir do bundle
anterior. O compositor criou outro perfil com o delta DT diagnóstico já
validado e o módulo PCIe novo, fora do initramfs e sem autoload.
Para reproduzir a composição, dentro de `iphone-linux-tools/`, escolha
destinos novos diretamente sob `runtime/`:

```sh
set -eu
umask 077
kernel_dir="$PWD/runtime/kernel-n71-power-artifacts-20261004"
base_dir="$PWD/runtime/n71-power-base-profile-repro"
diagnostic_dir="$PWD/runtime/n71-power-diagnostic-profile-repro"
IPHONE_LINUX_PROFILE="$PWD/runtime/n71-bundle-base-profile-20261003/deployment.json" \
  python3 scripts/build/integrate-source-kernel.py \
  --kernel-patchset n71-dart-serdev-power-v1 \
  --kernel-dir "$kernel_dir" --output-dir "$base_dir"
python3 scripts/build/compose-n71-diagnostic.py \
  --kernel-patchset n71-dart-serdev-power-v1 \
  --source-profile "$base_dir/deployment.json" --kernel-dir "$kernel_dir" \
  --diagnostic-dir "$PWD/runtime/n71-pcie-diagnostic-20261002" \
  --module "$PWD/runtime/n71-power-module-artifacts-20261004/n71-pcie-diagnostic.ko" \
  --module-sha256 a2d77a6786e8837963602810df5e58618eaff817ac6b36648025f60bb179c532 \
  --output-dir "$diagnostic_dir"
```

Esses caminhos dependem dos artefatos privados produzidos nas etapas
documentadas; não são downloads do repositório público. As ferramentas
recusam destinos existentes e artefatos divergentes. As identidades SSH
ficaram somente no Mac: initramfs, chave cliente e known_hosts são idênticos
entre o legado e os dois perfis novos, com diretórios700 e arquivos600.
O snapshot local preservado passou digest/estrutura sob lock, com44 entradas.
Nenhum perfil default foi alterado nem houve USB/DFU nessa preparação.

Boot/restore/SSH/HTTP/snapshot na ABI nova e comportamento físico continuam
gates futuros. Esse Image ainda não habilita I2C1/HDQ/SN2400 nem comprova
carga ou Wi-Fi; a próxima sessão física deve agrupar as observações de energia.

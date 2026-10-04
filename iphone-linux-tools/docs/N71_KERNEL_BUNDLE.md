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

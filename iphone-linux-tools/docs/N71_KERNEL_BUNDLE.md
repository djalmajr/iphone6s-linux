# Candidata agregada N71 — fonte e objetos verificados

O bundle `n71-dart-serdev-v1` reúne a correção DART S5L8960X e a operação
serdev de stop bits. Empacotar os deltas antes de um boot ajuda a reduzir
DFUs. **Ainda não há Image linkado, modpost, perfil de deployment ou prova
física desse bundle.** Wi-Fi, gauge e carga não estão habilitados por ele.

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

Objetos não provam Image, exports linkados/modpost ou comportamento elétrico.
Antes de qualquer deployment, faltam build completo, configuração embutida,
validação de ABI/artefatos, rebuild dos módulos, perfil separado e gate de
boot físico. A receita/integrador legado ainda não aceita este bundle.
UART5/I2C1 continuam desativados; ownership GPIO2/clocks, cleanup SN2400 e
identificação do gauge seguem em [desenvolvimento HDQ](N71_HDQ.md).

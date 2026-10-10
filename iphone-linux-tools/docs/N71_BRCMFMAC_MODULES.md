# Módulos brcmfmac PCIe para N71

## Estado e limites

O build preservado power2 habilitava brcmfmac SDIO/BCDC, mas não PCIe/MSGBUF; não havia brcmfmac.ko. Uma cópia do O agora habilita apenas os dois flags internos PCIe/MSGBUF e produz módulos oficiais da mesma fonte, com outputs MO separados. Não substitui a Image/config/exports base. [Evidência](evidence/n71-brcmfmac-pcie-modules-qualified.json), [plano](../.agents/plans/n71-brcmfmac-pcie-build.md).

Oito módulos têm ELF64/AArch64, vermagic `7.2.0-iphone6s-dart-serdev-power2 SMP preempt mod_unload aarch64` e imports resolvidos na união de exports preservados/dependências. brcmfmac tem alias PCI do endpoint14e4:43a3. Bytes/hash/ELF dos oito artefatos foram auditados no Mac. A soma é1.245.480 bytes; o principal brcmfmac tem498.800 bytes/SHA `ffc713a0ecf94d30dff765fd33f1fb4eb7be572fbeac954507b9229013f84660`.

| Módulo | Dependências registradas |
| --- | --- |
| rfkill | Nenhuma modular |
| rfkill-gpio | rfkill |
| cfg80211 | rfkill |
| brcmutil | Nenhuma modular |
| brcmfmac | brcmutil, cfg80211 |
| brcmfmac-wcc | brcmfmac |
| brcmfmac-bca | brcmfmac |
| brcmfmac-cyw | cfg80211, brcmfmac |

A tabela registra os módulos construídos; não autoriza carregar todos. A seleção da candidata ainda precisa decidir o vendor requerido e fornecer o loader/dep graph correto. CFG80211 conserva a exigência de regdb assinado. Firmware/calibração, unload/lifetime/journal, seleção explícita, IRQ/DMA/radio e energia físicos continuam pendentes. Nenhum módulo foi executado no Mac nem instalado/carregado no iPhone.

## Reprodução na VM dedicada

Usar a fonte `958481f87fee0949ff6a9a4af77f7eb6dac8a149` e o build power2 preservados. Antes/depois conferir HEAD/diff/status da fonte e hashes .config/Image/gzip/vmlinux.symvers da evidência; o gzip preservado está em full-link-v1-20261005/Image.gz. O espaço livre deve comportar a cópia de1,10GB e outputs. Não instalar pacote, modificar source/build base ou executar modules_install.

```bash
set -e
N71_SOURCE=/home/ubuntu/kernel-n71-binding-source-20261005
N71_BASE=/home/ubuntu/kernel-n71-binding-build-20261005
N71_WORK=$(mktemp -d /home/ubuntu/n71-brcmfmac-reproduce-XXXXXX)
N71_VARIANT="$N71_WORK/kernel-build"
cp -a "$N71_BASE" "$N71_VARIANT"
bash "$N71_SOURCE/scripts/config" --file "$N71_VARIANT/.config" \
  --enable BRCMFMAC_PCIE
make -C "$N71_SOURCE" O="$N71_VARIANT" LOCALVERSION= olddefconfig
python3 - "$N71_BASE/.config" "$N71_VARIANT/.config" <<'PYCONFIG'
import sys
from pathlib import Path

def read(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('CONFIG_'):
            name, value = line.split('=', 1)
            values[name] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            values[line[2:-11]] = 'n'
    return values

before, after = map(read, sys.argv[1:])
changes = {name: [before.get(name, 'n'), after.get(name, 'n')]
           for name in before.keys() | after.keys()
           if before.get(name, 'n') != after.get(name, 'n')}
assert changes == {'CONFIG_BRCMFMAC_PCIE': ['n', 'y'],
                   'CONFIG_BRCMFMAC_PROTO_MSGBUF': ['n', 'y']}, changes
PYCONFIG
cp "$N71_BASE/vmlinux.symvers" "$N71_VARIANT/Module.symvers"
make -C "$N71_SOURCE" O="$N71_VARIANT" LOCALVERSION= -j2 \
  prepare modules_prepare
N71_EXPORTS=
build_n71_module() {
  N71_NAME="$1"
  N71_RELATIVE="$2"
  N71_OUT="$N71_WORK/module-$N71_NAME"
  mkdir -m 700 "$N71_OUT"
  make -C "$N71_SOURCE" O="$N71_VARIANT" LOCALVERSION= \
    M="$N71_SOURCE/$N71_RELATIVE" MO="$N71_OUT" W=1 KCFLAGS=-Werror \
    KBUILD_EXTRA_SYMBOLS="$N71_EXPORTS" -j2 modules || return
  N71_EXPORTS="${N71_EXPORTS:+$N71_EXPORTS }$N71_OUT/Module.symvers"
}
build_n71_module rfkill net/rfkill
build_n71_module cfg80211 net/wireless
build_n71_module brcmutil drivers/net/wireless/broadcom/brcm80211/brcmutil
build_n71_module brcmfmac drivers/net/wireless/broadcom/brcm80211/brcmfmac
modinfo -F vermagic "$N71_WORK/module-brcmfmac/brcmfmac.ko"
modinfo -F alias "$N71_WORK/module-brcmfmac/brcmfmac.ko"
readelf -h "$N71_WORK/module-brcmfmac/brcmfmac.ko"
nm -u "$N71_WORK/module-brcmfmac/brcmfmac.ko"
sha256sum "$N71_WORK/module-brcmfmac/brcmfmac.ko"
```

Conferir todos os imports contra Module.symvers do O e das quatro pastas, sem aceitar warning/erro de modpost ou MODPOST_WARN. Repetir ELF/vermagic/dependencies/bytes/hash para cada ko, inclusive vendors. Pastas/toolchain diferentes podem alterar hashes; uma reprodução deve qualificar seus próprios artefatos antes da seleção. Copiar artefatos/logs somente para a área privada e auditar novamente no Mac, sem executá-los.

## Falhas conservadas e correções

A primeira verificação procurava gzip no caminho errado e parou antes do copy/build; scripts/config chamado com sh falhou antes de modificar a cópia. A leitura integral mostrou que ele requer Bash. O booleano interno MSGBUF ausente é n em Kconfig; a comparação registra tanto essa forma original quanto a normalizada, sem aceitar outros flags.

A preparação inicial gerou sufixo+ na versão porque LOCALVERSION estava indefinido. scripts/setlocalversion declara que o argumento vazio explícito evita esse sufixo quando LOCALVERSION_AUTO está desligado. Os módulos anteriores com+ não foram aceitos; prepare/build foram retomados com LOCALVERSION= e vermagic exato. A tabela agregada de exports ausente também foi resolvida copiando somente os exports do kernel preservado no O privado, usando KBUILD_EXTRA_SYMBOLS apenas para dependências modulares. Os logs finais não têm warnings/erros; não se forçou vermagic nem se alterou artefato depois do build.

## Relatório

- **Entrega:** variante e oito módulos privados compilados/auditados; receita e metadados públicos conservados. Preparação/build/auditoria do plano concluídos; seleção e prova física pendentes.
- **Verificação:** Kbuild oficial ARM64, W=1/Werror/modpost, dois flags, exports, ELF/vermagic/PCI alias e auditagem de bytes no Mac; baseline source/config/Image/gzip/exports/status intactos. Não houve nova suíte C do diagnóstico:69 inputs iguais mantêm575/455 válidos. AST/lint fatal90/169 da integração host permanecem com inputs executáveis inalterados; não há typechecker Python configurado.
- **Dependências/banco:** CLI/toolchain da VM existentes, sem pacote ou configuração global do Mac, banco ou instalação de módulos. Regdb/calibração/driver vendor devem ser preparados para a candidata.
- **Riscos/desempenho:** configurações internas do driver mudaram; ABI estática não comprova execução/throughput/radio/energia físicos. Nenhum DFU, reboot, kernel Image novo ou firmware no telefone nesta fase.
- **Próximo:** integrar journal/unload/recovery, seleção/loader de módulos e firmware/regdb/calibração/energia; reunir scan/associação/DHCP/SSH e IRQ/DMA/carga num boot necessário. Goal e issues9/40/2 continuam abertos.

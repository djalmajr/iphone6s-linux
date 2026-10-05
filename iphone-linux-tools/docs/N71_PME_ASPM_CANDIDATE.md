# Candidata PME e ASPM — 2026-10-05

## Estado

O helper PME, o adapter e o caller estão integrados e compilados para a ABI
`7.2.0-iphone6s-dart-serdev-power2`. O composer oferece `--pcie-aspm-off`
explicitamente. Esta candidata **ainda não foi carregada no iPhone**; o coletor
e o perfil privado precisam da integração correspondente antes do teste.
[Hashes, inputs e provas](evidence/n71-pcie-pme-aspm-build.json).

A última sessão física continua sendo a
[tentativa PME anterior](evidence/n71-pme-first-physical.json): um boot,
um scan, primeira recusa no endpoint `04c/c008` e cleanup verificado.
O retorno automático não foi confirmado; o fallback físico recuperou o iOS,
com 99% e carregamento ativo. Esse resultado não é prova desta candidata.

## Alterações

- `scan_pme_disable=1` é um parâmetro explícito do módulo diagnóstico,
  permitido somente com `run=1 enumerate=1 config_inventory=1 host_scan=1`.
  O padrão continua usando o caminho anterior.
- O helper valida identidade, capability PM e COMMAND, prepara somente
  PME_ENABLE (`4108 → 4008`) e restaura o bit por máscara. Não escreve `1`
  em PME_STATUS, não altera D-state e preserva eventos novos.
- O callback aceita o pedido exato `c008` como no-op somente depois da
  preparação comprovada, com ownership e releituras. Eventos ou divergências
  continuam recusados.
- Depois da remoção do bus, o adapter restaura config, PME e TLS nessa ordem.
  Em falha, conserva bridge, estado e os recursos do caller. `action=cleanup`
  tenta restaurar sem repetir enumeração ou scan.
- `--pcie-aspm-off` altera apenas a linha de bootargs da candidata RAM,
  além do delta DT diagnóstico já permitido. Kernel, loader, initramfs,
  identidades e perfil padrão são preservados.

## Por que agrupar com ASPM off

Na fonte PCIe fixada, `pcie_aspm=off` desativa `aspm_support_enabled` durante
o boot. `pcie_aspm_init_link_state()` retorna antes de configurar common clock,
retrain e L1SS. A remoção também retorna sem link_state. O simples
`pcie_no_aspm()` não tem o mesmo efeito nessa versão.

Os pedidos posteriores `bc/40`, `80/40`, retrain e L1SS da sessão anterior
foram latched após a primeira recusa PME. A sequência é compatível com os
caminhos da fonte, por inferência; não é um trace independente nem autorização
para liberar cada write. O parâmetro permite reunir esse obstáculo e PME numa
única próxima candidata. Seu efeito físico ainda precisa de confirmação.

ASPM off não comprova menor consumo ou carregamento sustentado. Wi-Fi, IRQ,
DMA, firmware, telemetria e carga continuam pendentes nas issues
[#9](https://github.com/djalmajr/iphone6s-linux/issues/9) e
[#2](https://github.com/djalmajr/iphone6s-linux/issues/2).

## Provas offline

| Parte | Mac e Ubuntu ARM64 |
|---|---|
| Helper PME | Baseline C e 19 mutações compiladas por SIGABRT/assertion |
| Adapter | 29 cenários; 18 mutações compiladas por SIGABRT/assertion |
| Caller | 73 cenários; 21 mutações compiladas por SIGABRT/assertion |
| Composer | 7 testes; 13 mutações por AssertionError |
| Build real na VM ARM64 | 6 módulos; Werror, modpost, ELF AArch64 e vermagic |

As quatro provas têm inputs e logs por SHA. O build usa 46 inputs e conserva
a fonte power2, `.config`, Image e `vmlinux.symvers`. O módulo PCIe tem
73.576 bytes; seu SHA está no JSON. REG_ON mantém o binário anterior.
Compilação, import e timeout não contam como morte de mutação.

## Reprodução

Use uma cópia descartável do código público e a VM Linux ARM64 dedicada.
A preparação de fonte/kernel está em [N71_KERNEL_BUNDLE.md](N71_KERNEL_BUNDLE.md).
Não envie chaves ou payloads com identidades para a VM.

Na pasta `iphone-linux-tools` da cópia:

```sh
set -e
python3 -B -m unittest discover -s tests -p test_n71_pcie_pme_control.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_diagnostic_caller.py -v
python3 -B -m unittest discover -s tests -p test_n71_diagnostic_payload.py -v
python3 -B tests/run_n71_diagnostic_payload_mutations.py
```

Na VM, depois de conferir a fonte e os outputs power2 existentes:

```sh
set -e
python3 scripts/build/kernel_bundle.py check "$kernel_source" \
  --profile n71-dart-serdev-power-v2
LOCALVERSION= make -C "$kernel_source" O="$kernel_output" ARCH=arm64 \
  -j2 W=1 KCFLAGS=-Werror M="$PWD/phone/kernel" \
  KBUILD_EXTRA_SYMBOLS="$kernel_output/vmlinux.symvers" modules
modinfo -F vermagic phone/kernel/n71-pcie-diagnostic.ko
```

`kernel_source` e `kernel_output` são os diretórios da fonte e do build
dedicados. Confira novamente seus hashes e todos os inputs após o build.
Paths de build podem alterar o binário; registre a nova provenance em vez de
presumir igualdade com o SHA desta sessão.

O composer diagnóstico aceita `--pcie-aspm-off` com os argumentos de perfil,
kernel, DT e módulo já descritos em [N71_LINK_EXPERIMENT.md](N71_LINK_EXPERIMENT.md).
A saída exige uma pasta privada nova. A provenance registra o booleano e o
hash de bootargs. A composição não inicia USB, SSH ou load de módulo.

## Próximo gate físico

Integrar o coletor para selecionar o novo build e exigir os opt-ins exatos,
SHA/ABI do módulo, layout do payload e `pcie_aspm=off` no cmdline real antes
de qualquer insmod. O parsing deve exigir prepare/restore PME completos e
conservar REG_ON se não houver prova de cleanup.

Depois dos checks locais e CI, fazer um único boot com restore e serviços
confirmados. Continuar os testes compatíveis por SSH, sem desbloquear o iOS
entre passos. Ao final, snapshot/sync e retorno para recarga; o fallback
físico continua necessário quando o retorno automático não for confirmado
([#21](https://github.com/djalmajr/iphone6s-linux/issues/21)).

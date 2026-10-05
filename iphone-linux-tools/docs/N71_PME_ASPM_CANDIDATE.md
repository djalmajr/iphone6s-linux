# Candidata PME e ASPM — 2026-10-05

## Estado

O helper PME, o adapter e o caller estão integrados e compilados para a ABI
`7.2.0-iphone6s-dart-serdev-power2`. O composer oferece `--pcie-aspm-off`
explicitamente. O coletor e o perfil privado real foram integrados e verificados.
Esta candidata **ainda não foi carregada no iPhone**.
[Build e inputs](evidence/n71-pcie-pme-aspm-build.json),
[coletor e perfil](evidence/n71-pme-aspm-session.json).

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
| Coletor PME/ASPM | 45 testes; 81 mutações por AssertionError; 29 inputs |
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
python3 -B -m unittest discover -s tests -p test_n71_link_session.py -v
python3 -B tests/run_n71_link_session_mutations.py
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

### Perfil privado real

A composição desta sessão usou o perfil base power2, o DT diagnóstico existente
e o módulo do build acima. Os argumentos podem ser reproduzidos no Mac:

```sh
python3 -B scripts/build/compose-n71-diagnostic.py \
  --source-profile "$base_profile/deployment.json" \
  --kernel-dir "$kernel_artifacts" \
  --kernel-patchset n71-dart-serdev-power-v2 \
  --diagnostic-dir "$diagnostic_dt" \
  --module "$pcie_module" --module-sha256 "$pcie_sha256" \
  --output-dir "$candidate" --pcie-aspm-off
```

Essas variáveis apontam para diretórios/artefatos privados verificados pelas
receitas anteriores. `candidate` deve ser uma pasta nova diretamente em
`runtime`. Copie o REG_ON verificado da candidata anterior para essa pasta,
como `n71-wlan-power-diagnostic.ko`, com modo 600. Na `provenance.json`,
registre booleanos JSON exatos: `pcie_scan_link_target: true`,
`pcie_scan_pme_noop: false`, `pcie_scan_pme_disable: true`; o composer já
registra `pcie_aspm_off: true` e o SHA de bootargs. Não use strings ou números.

Confira novamente os hashes da fonte e da saída e execute:

```sh
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --check
python3 -B scripts/boot/boot_tools.py palera1n-macos-arm64 pongoterm
python3 -B scripts/host/persist.py verify "$snapshot_id"
```

O perfil real passou esses checks. O payload mudou apenas pela adição de
14 bytes de bootargs em relação ao diagnóstico anterior. Loader, DT, kernel
comprimido e descomprimido, initramfs, identidades e REG_ON foram conferidos
por igualdade/hash; fonte anterior e default permaneceram intactos. Nenhum
perfil, chave, alias SSH ou snapshot é publicado no GitHub.

## Próximo gate físico

O coletor seleciona o novo build e exige os opt-ins exatos, SHA/ABI do módulo
e bootargs literais no payload. No telefone, antes de transferir módulos,
exige um único `pcie_aspm=off` no cmdline e o marcador de suporte ASPM
desativado. O parser exige prepare/restore PME completos e conserva REG_ON
se não houver prova de cleanup. Retry de restauração não executa novo scan.

Depois dos checks locais e CI, fazer um único boot com restore e serviços
confirmados. Continuar os testes compatíveis por SSH, sem desbloquear o iOS
entre passos. Ao final, snapshot/sync e retorno para recarga; o fallback
físico continua necessário quando o retorno automático não for confirmado
([#21](https://github.com/djalmajr/iphone6s-linux/issues/21)).

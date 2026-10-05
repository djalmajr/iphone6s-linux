# Candidata PME e ASPM — 2026-10-05

## Estado

O helper PME, o adapter e o caller estão integrados e compilados para a ABI
`7.2.0-iphone6s-dart-serdev-power2`. O composer oferece `--pcie-aspm-off`
explicitamente. O coletor e o perfil privado real foram integrados e verificados.
Esta candidata passou uma sessão física com quatro etapas no mesmo boot,
cleanup completo e retorno automático ao iOS.
[Build e inputs](evidence/n71-pcie-pme-aspm-build.json),
[coletor e perfil](evidence/n71-pme-aspm-session.json),
[sessão física](evidence/n71-pme-aspm-physical.json).

A sessão física anterior foi a
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
única candidata. Nesta sessão, a opção foi verificada antes dos módulos e o
scan PCI-core terminou sem recusas. Não houve comparação A/B no mesmo boot
para atribuir individualmente o resultado a ASPM ou PME.

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

## Sessão física — quatro etapas sem reiniciar

O código `dd2b0da` e os módulos qualificados não mudaram antes do load.
O primeiro monitor expirou antes de transferir o payload; o segundo reutilizou
o DFU já estabelecido, sem outra sequência de botões. Houve um DFU manual,
um boot Linux, restore de44 entradas e zero reinícios intermediários.

| Etapa | Resultado físico |
|---|---|
| PCI-core com PME/ASPM | error0; dois dispositivos/um endpoint; 660 leituras,40 tentativas,23 escritas,zero recusas |
| BAR/ChipCommon direto | BAR0 de32KiB/BAR2 de4MiB; BCM4350 revisão8; uma leitura MMIO ChipCommon |
| DART passivo | 38 leituras;16 words TTBR preservadas; sem DMA |
| Provider DART temporário | error0; quatro snapshots/152 leituras;16 words restauradas; nenhuma mudança de controle; sem DMA |

Cada etapa terminou com bus removido, config/PME/TLS/reset/power e REG_ON
restaurados quando aplicáveis, módulos ausentes e sem erro de cleanup.
Boot ID e histórico de cleanup foram conferidos antes das continuações.
O provider temporário foi inicializado, mas isso não comprova entrega de IRQ,
attachment IOMMU do endpoint ou DMA.

### Reprodução da continuação por SSH

Depois de boot/restore e serviços confirmados, execute o scan com o perfil
PME/ASPM explícito:

```sh
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --output-dir "$scan_result" \
  --host-scan --scan-link-target --scan-pme-disable
```

Para as três etapas seguintes foi selecionado o módulo diagnóstico anterior
qualificado, SHA `e715ad64013eb0238c9074dba9b05157d2a7153835fd4a800bd53adb0e170785`,
com REG_ON presente, através de seu perfil privado. **O payload desse perfil
anterior não foi bootado.** Kernel/DT/initramfs/identidades/REG_ON são iguais;
seus bootargs diferem somente pela opção ASPM. O payload efetivamente em
execução continuou PME/ASPM, com ASPM off já verificado. Não modifique a
metadata para fingir igualdade: confira artefatos, ABI e diferença literal,
conservando o registro privado da seleção.

```sh
set -e
python3 -B scripts/host/n71-link-session.py \
  --profile "$hot_module_profile/deployment.json" \
  --previous-clean "$scan_result" --output-dir "$chip_result" --chip-id
python3 -B scripts/host/n71-link-session.py \
  --profile "$hot_module_profile/deployment.json" \
  --previous-clean "$chip_result" --output-dir "$dart_result" --dart-observe
python3 -B scripts/host/n71-link-session.py \
  --profile "$hot_module_profile/deployment.json" \
  --previous-clean "$dart_result" --output-dir "$cycle_result" --dart-cycle
```

Os diretórios de resultado são novos e privados. Os checks `--check` com os
mesmos argumentos precedem cada execução. Continue somente com histórico
completo do mesmo boot, sem owner/cleanup pendente; uma recusa não autoriza
repetir probes ou substituir o histórico. Um perfil antigo sem REG_ON foi
recusado no check local, antes de qualquer transferência; o perfil correto
passou sem mudança de código ou reinício.

Ao final, SSH/HTTP/Bash/Herdr foram conferidos, com uptime506,59s, PCI vazio
e módulos ausentes. `return_ios.py --wait 90`, usando o perfil PME/ASPM,
salvou/verificou snapshot44 e sync, encerrou Linux e confirmou iOS pelo USB.
Não precisou de fallback físico. iOS100→100%, carregando às19:00:58UTC;
nenhuma corrente líquida foi medida no Linux, que continua com zero entradas
`power_supply` e MaxPower USB declarado de500mA. Não derivar saúde ou carga
sustentada desses dados. Logs/identidades/snapshot ficam privados; o JSON
público conserva contagens, estados e hashes.

### CI do código testado

[PR37356247973](https://github.com/djalmajr/iphone6s-linux/actions/runs/37356247973)
passou nos três jobs; Mac/Ubuntu executaram81 mutações por AssertionError do
coletor. [Push37356242967](https://github.com/djalmajr/iphone6s-linux/actions/runs/37356242967)
falhou somente no Ubuntu por timeout de10s num mutante PMGR após baseline
positiva. Causa não confirmada; timeout não contou como mutation kill.
[#38](https://github.com/djalmajr/iphone6s-linux/issues/38) permanece aberta.

## Próximos gates

O coletor seleciona o novo build e exige os opt-ins exatos, SHA/ABI do módulo
e bootargs literais no payload. No telefone, antes de transferir módulos,
exige um único `pcie_aspm=off` no cmdline e o marcador de suporte ASPM
desativado. O parser exige prepare/restore PME completos e conserva REG_ON
se não houver prova de cleanup. Retry de restauração não executa novo scan.

O scan atual enumera e remove o bus; os BARs ainda não têm endereços
persistentes atribuídos. Para Wi-Fi, preparar offline o lifecycle do host PCI,
atribuição de recursos, IRQ/IOMMU do endpoint e depois driver/firmware/radio.
Esses passos não estão habilitados pela prova diagnóstica. Alimentação e
telemetria precisam de acesso HDQ/charger e medição própria.

Manter o telefone no iOS para recarga durante desenvolvimento/build. Reunir
checks e módulos compatíveis para a próxima sessão por SSH; novo DFU somente
quando uma candidata agrupada exigir boot novo. Snapshot/sync e retorno
automático devem ser verificados novamente ao final. Um retorno positivo não
fecha a confiabilidade de [#21](https://github.com/djalmajr/iphone6s-linux/issues/21);
o fallback físico continua disponível quando USB não confirmar o iOS.

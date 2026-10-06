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

## Lifecycle do bus retido — preparação offline

O adapter `b0c0933` acrescenta a API interna `n71_pcie_scan_hold()`, somente
com PME e scan completamente positivo. Bridge, bus, config/PME/TLS e callbacks
permanecem válidos entre chamadas. Os wrappers usados pelo caller daquele
checkpoint continuavam removendo o bus imediatamente. Nenhum parâmetro de
módulo, CLI ou perfil selecionava hold nessa etapa; a integração posterior
está descrita abaixo e tem prova própria.

Cleanup de bus retido faz stop/remove sob o lock de rescan antes de restaurar
config, PME e TLS e liberar o bridge. Uma falha de restore conserva owner para
retry, sem outro scan. Uma recusa de callback durante stop é conservada
inclusive depois de retry de restore; se todo o rollback passou, o bridge pode
ser liberado mesmo com essa saída negativa. Não confundir erro do experimento
com owner ainda pendente: a integração do caller precisa tratar ambos.

A fonte PCI fixada confirma o guard de binding em `pci_bus_match()` e a
liberação explícita em `pci_bus_add_device()`. O adapter não chama essa API,
`pci_host_probe()` ou atribuição de recursos, e continua negando enable_device.
`pci_remove_root_bus()` limpa `host_bridge->bus` depois de remover o bus.
Arquivos e hashes estão na [prova do lifecycle](evidence/n71-pci-held-bus.json).
Isso qualifica o contrato desta fonte, sem comprovar IRQ/DMA/driver no aparelho.

Dois testes C com45 cenários (29 anteriores e16 de hold) e26 mutações compiladas
por SIGABRT/assertion passaram no Mac e Ubuntu ARM64, com dez inputs iguais.
Cobrem callback após retorno hold, novo scan recusado, scan negativo/parcial,
stop-refusal, os três restores e link perdido no teardown; retries não repetem
scan. Timeout ou falha de compilação não contam como mutation kill.

Na cópia descartável do código público:

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
```

O build real usou M novo `/home/ubuntu/n71-held-bus-modules-20261005/phone/kernel`,
com os46 inputs do JSON. Somente `n71-pcie-scan.h` mudou desde o build PME/ASPM
anterior. Reproduza com a mesma receita W=1/KCFLAGS=-Werror desta página, depois
de validar o bundle power2, usando um novo diretório M. Os seis módulos passaram
modpost/ELF/vermagic; PCIe74008 bytes, REG_ON idêntico e fonte/config/Image/exports
preservados. PCIe e REG_ON copiados para o Mac tiveram hashes/ELF/vermagic
conferidos independentemente.

Não substitua módulos nos perfis físicos anteriores mantendo seus manifests:
o hash novo é distinto e não foi integrado à seleção do coletor. Caller deve
reter referências de módulo/MMIO/energia enquanto houver bus ou restore
pendente; depois virão seleção/provenance/coletor e recursos PCI/IRQ/IOMMU.
A [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39) acompanha esse
desenvolvimento. Esta prova é offline; o resultado físico acima continua
pertencendo ao módulo PME/ASPM anterior. Nenhum novo DFU foi solicitado.

## Caller retido — integração e build offline

O caller `3d410c7` expõe `scan_hold`, desativado por padrão, somente com
`run=1 enumerate=1 config_inventory=1 host_scan=1 scan_pme_disable=1`.
Os guards de N71 e modos exclusivos permanecem. Depois de scan positivo,
exige bridge, bus e ownership reais antes de retornar com binding/MMIO,
referência do módulo, reset e quatro domínios de energia vivos.

O getter separado `held`, modo0400, retorna `held=1` somente enquanto o bus
estiver presente e retido pelo adapter, sob `session_lock`. Não há flag
espelhada no diagnóstico, e o formato do getter `status` permanece igual.
`scan_pending=1` indica bridge presente, não necessariamente bus ativo:
após remoção do bus, uma falha de restore pode deixar `held=0` com owner
pendente. O coletor precisa verificar os dois contratos.

`action=cleanup` remove o bus antes de config/PME/TLS, reset e energia.
Os recursos e o pin do módulo somente são liberados depois de todos os
owners terem sido encerrados. Stop refusal conserva a saída negativa;
se o bridge já foi liberado após rollback, o caller conserva reset/energia
até a próxima limpeza comprovada. Retry não enumera, não faz outro scan
e não descarta duas vezes a mesma referência de uso.

O caller real e o MMIO real, com APIs do kernel e dependência scan simuladas,
passaram73 cenários anteriores e21 de hold, com30 mutações compiladas por
SIGABRT/assertion no Mac e Ubuntu ARM64, cinco inputs idênticos/preservados.
A prova isolada do adapter45/26 foi reutilizada após conferir seus dez inputs
sem alterações. O build kernel integra os headers reais; não substitui uma
prova física dos callbacks no telefone.

Na cópia descartável do código público:

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_diagnostic_caller.py -v
```

O build ARM64 usa a receita W=1/KCFLAGS=-Werror acima, em M novo
`/home/ubuntu/n71-held-caller-modules-20261005/phone/kernel`. Os46 inputs
diferem do build174 somente em `n71-pcie-diagnostic.c`. Os seis módulos
passaram modpost/ELF/vermagic; PCIe76.112 bytes, SHA
`b7e51d4d8ee281ace121c11dc60af04265a63c7395613fa8503af590927520b3`.
REG_ON conserva o SHA anterior. Fonte/bundle/config/Image/exports foram
conferidos antes/depois; os módulos PCIe e REG_ON copiados para o Mac também
passaram SHA/ELF/vermagic. [Inputs, logs e limites](evidence/n71-pci-held-caller.json).

Nenhum perfil funcional foi trocado e o coletor ainda não seleciona esse build
ou hold. Não use provenance antiga com o binário novo nem carregue o módulo
diretamente para contornar os checks do coletor. A próxima fatia implementa
seleção explícita, validação de hold e cleanup/REG_ON no mesmo boot.
Recursos PCI, bind, IRQ/DMA/IOMMU, firmware/radio e carga Linux continuam
pendentes. Nenhum DFU, PIN, firmware ou Image novo foi necessário.

## Parser held — aquisição e limpeza separadas

O parser `49d2158` usa o protocolo emitido pelo módulo caller acima. O scan
positivo retido retorna antes de `SCAN_RESULT`, portanto não exige ou cria
esse resumo temporário. Valida um `SCAN_HELD`, um `SESSION_HELD`, getter vivo
`held=1`, status completo, TLS/PME preparados e todos os dispositivos/BARs
antes do hold. COMMAND permanece zero e os BARs medidos permanecem sem
atribuição, com32KiB e4MiB. Binding/MMIO, pin do módulo, reset e quatro
domínios ativos precisam estar comprovados; uma falha não vira retenção válida.

O resultado inclui somente campos observados: topology/BARs, ownership e
preparações. Não declara contagens de reads/writes/refusals nem cleanup
que esse caminho ainda não emitiu. `device_resources()` compartilha a
validação existente de topologia/BAR; `restore_owned()` compartilha os
registros e a ordem de restauração PME. Os modos anteriores continuam usando
suas próprias APIs e módulos.

Cleanup held exige getter0 e caller bound sem owners pendentes, remoção única,
config→PME→TLS→reset→energia→caller final. Registros truncados, duplicados,
campos adicionais, restore fora de ordem ou retry indevidamente positivo são
recusados. Uma recusa no stop conserva o mesmo errno da primeira escrita
recusada, inclusive depois da restauração; prova de cleanup não apaga erro do
experimento. Se o hold nunca foi adquirido, a prova negativa e a limpeza PME
anterior são necessárias; ausência de owners sozinha não prova esse caminho.

Seleção local usa a prova `n71-pci-held-caller.json`, somente ABI power2,
flags booleanas exatas, Werror/modpost/ELF e módulos de nomes fixos. Os hashes
e o vermagic ainda precisam passar pelo integrador e pelo perfil privado
antes de qualquer transferência. Esta função não chama USB, SSH ou insmod.

Na cópia descartável do código público, em Mac e Ubuntu ARM64:

```sh
set -e
python3 -B -m unittest discover -s tests -p test_n71_scan_held_result.py -v
python3 -B -m unittest discover -s tests -p test_n71_scan_result.py -v
python3 -B tests/run_n71_scan_result_mutations.py
python3 -B -m unittest discover -s tests -p test_n71_link_session.py -v
python3 -B tests/run_n71_link_session_mutations.py
```

Novo parser12 testes/29 mutações por AssertionError; scan6/8 e coletor45/81
foram requalificados pela mudança compartilhada: total63 testes/118 mutações
por plataforma,34 inputs iguais e preservados, cinco logs/hash por plataforma.
Compilação/import/timeout não contam como mutation kill.
[Inputs e provas selecionadas](evidence/n71-pci-held-parser.json).

Os inputs C e46 inputs de build permaneceram intactos; suas provas anteriores
foram reutilizadas, sem outro build ou Image. CLI de aquisição/retomada,
provenance/perfil e prova física continuam pendentes. O módulo não foi
carregado no telefone, e nenhuma nova intervenção DFU/PIN/console foi pedida.
Wi-Fi, recursos PCI/IRQ/DMA/firmware e telemetria/carga continuam abertos.

CI do caller `6e26fac`: [PR37374903992](https://github.com/djalmajr/iphone6s-linux/actions/runs/37374903992)
passou nos três jobs; [push37374896899](https://github.com/djalmajr/iphone6s-linux/actions/runs/37374896899)
terminou cancelled, com Mac/Windows success e Ubuntu cancelled. Causa não
confirmada; não tratar esse cancelamento como aprovação. Essa CI antecede
o parser `49d2158`, que conserva seus próprios gates Mac/ARM64 acima.

## CLI retido — aquisição e retomada no mesmo boot

O CLI `36c7f53` seleciona o módulo caller de 76.112 bytes somente com
`--host-scan --scan-link-target --scan-pme-disable --scan-hold`.
Exige `pcie_scan_hold: true` na provenance, os opt-ins PME/ASPM anteriores
e SHA/ELF/vermagic exatos. `--check` verifica somente arquivos locais.
Naquele checkpoint, o composer/perfil correspondente ainda estava pendente;
a composição completa abaixo tem prova própria. Use uma candidata separada.

Com a candidata privada qualificada e um boot Linux já estabelecido:

```sh
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" --output-dir "$held_result" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold
```

Uma aquisição positiva conserva bus, módulo, reset/energia, REG_ON e staging.
O resultado declara `held_verified=true` e `cleanup_verified=false`.
Estado de tentativa é reservado antes dos efeitos; depois, o checkpoint
privado registra histórico completo, getters e hashes. As identidades ligam
deployment, payload, initramfs e os dois módulos; esses dados não são publicados.

Para liberar os recursos posteriormente, usando saída privada nova:

```sh
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" --output-dir "$released_result" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --release-held "$held_result"
```

Antes da escrita, o comando exige o mesmo boot e histórico, staged hashes,
parâmetros imutáveis reais, bind/unbind ausentes e ownership PCI/REG_ON.
Booleanos sysfs são lidos como `Y/N`, conforme a fonte kernel fixada.
Diretório PCI ausente não equivale a barramento vazio. Remoção/config/PME/TLS,
reset/energia e unload PCI precedem restore/unload REG_ON.

Em falha, o resultado conserva o erro e as provas das etapas concluídas.
Retome com `--release-held "$released_result"` e outra saída privada nova.
Cleanup já comprovado não é solicitado novamente; unload PCI concluído
permite retomar somente REG_ON, e restore REG_ON concluído permite repetir
apenas seu unload. A saída continua negativa se o stop teve erro, mesmo
quando `cleanup_verified=true`. Não há rescan ou puts duplicados nesses caminhos.

Tentativas sem checkpoint não autorizam escrita. Mudanças de boot, perfil,
histórico, módulos, parâmetros ou estado vivo recusam a retomada.
Novos coletores que alterem o histórico/estado deverão participar do protocolo
de checkpoint antes de serem agrupados; esta versão não aceita eventos
arbitrários como continuação válida. Falta de evidência não é limpeza concluída.

Na cópia descartável do código público:

```sh
set -e
python3 -B -m unittest discover -s tests -p test_n71_held_session.py -v
python3 -B -m unittest discover -s tests -p test_n71_link_session.py -v
python3 -B tests/run_n71_link_session_mutations.py
```

Mac/Ubuntu ARM64 passaram 18 testes/22 mutações novos e compatibilidade45/81:
total63/103 por plataforma, 36 inputs finais preservados e logs por SHA.
Os comandos snapshot foram executados contra sysfs sintético; 17 comandos
gerados passaram `bash -n`, AST e lint de erros fatais passaram.
A correção isolada do diretório PCI repetiu somente os gates novos;
os inputs relevantes do caminho legado permaneceram iguais.
[Prova sanitizada e inputs](evidence/n71-pci-held-session.json).

Parser e C/build anteriores foram reutilizados por hashes; nenhum módulo foi
transferido ou carregado no iPhone nesta integração. Não comprova retenção
física, recursos atribuídos, bind, entrega IRQ, DMA/IOMMU, rádio, telemetria
ou carregamento Linux. O próximo passo prepara o perfil e controles
compatíveis antes de uma sessão física agrupada.

## Perfil retido completo — composição verificada sem boot

Composer `c30a4ac` acrescenta `--pcie-scan-hold` e `--reg-on-module`.
Hold exige explicitamente `--pcie-aspm-off`, patchset power2 e o arquivo REG_ON.
REG_ON sem hold é recusado. A seleção usa a prova do caller qualificado,
com tamanho/SHA/ELF/vermagic dos dois módulos antes de criar a saída.
O padrão anterior conserva a ausência de hold e da cópia REG_ON.

Use artefatos privados já qualificados e uma pasta de saída nova:

```sh
python3 -B scripts/build/compose-n71-diagnostic.py \
  --source-profile "$base_profile/deployment.json" \
  --kernel-dir "$kernel_artifacts" \
  --kernel-patchset n71-dart-serdev-power-v2 \
  --diagnostic-dir "$diagnostic_dt" \
  --module "$pcie_module" --module-sha256 "$pcie_sha256" \
  --reg-on-module "$reg_on_module" --output-dir "$candidate" \
  --pcie-aspm-off --pcie-scan-hold
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold --check
```

O composer copia REG_ON automaticamente e grava `pcie_scan_link_target: true`,
`pcie_scan_pme_noop: false`, `pcie_scan_pme_disable: true` e
`pcie_scan_hold: true`, além de ASPM/bootargs. Não há edição manual de
provenance, autoload ou USB. Mantém o layout/preservação DT anterior e verifica
as identidades da saída antes de declarar o perfil composto.

O perfil real desta etapa passou esses checks com PCIe de 76.112 bytes/SHA b7e51d4d
e REG_ON de 17.688 bytes/SHA fdf887e7. O payload inteiro é idêntico ao PME/ASPM
anterior, portanto loader/DT/kernel/userspace permanecem iguais; initramfs,
chave cliente e pin SSH também foram conferidos por igualdade.
Fonte/default e perfis anteriores ficaram intactos.

Ferramentas de boot e snapshot local com 44 entradas foram verificados.
O argumento de `persist.py verify` é o ID canônico do manifesto privado,
não o número 44 de entradas. Esses checks não consultam o telefone.

Na cópia descartável do código público, em Mac e Ubuntu ARM64:

```sh
set -e
python3 -B -m unittest discover -s tests -p 'test_n71_diagnostic_*.py' -v
python3 -B tests/run_n71_diagnostic_payload_mutations.py
```

13 testes/29 mutações por AssertionError: 7/13 anteriores e 6 testes/16 mutações
novos. Mutações antigas usam o contrato do payload; mutações held usam o
contrato do perfil completo, com filesystem real e dependências de
identidade/kernel sintéticas. Os 20 inputs e logs foram preservados e
conferidos por SHA; AST e lint de erros fatais passaram. Import, compilação
e timeout não contam como mutation kill.
[Prova sanitizada e inputs](evidence/n71-pci-held-profile.json).

O perfil não foi bootado e nenhum módulo foi transferido ou carregado no
iPhone. Prova de composição não comprova bus retido, atribuição de recursos,
IRQ/DMA/IOMMU, rádio, telemetria ou carregamento. Preparar os controles
compatíveis antes da sessão física agrupada.

## Política de escritas de atribuição PCI — preparação offline

Código `8c16d0a` prepara a política de configuração para o alocador PCI.
O código-fonte selecionado e `vmlinux.symvers` confirmaram exports de
`pci_bus_size_bridges`, `pci_bus_assign_resources`, `pci_get_slot` e
`pci_dev_put`. Referências públicas: [alocação de barramentos](https://github.com/torvalds/linux/blob/master/drivers/pci/setup-bus.c)
e [atualização de BARs](https://github.com/torvalds/linux/blob/master/drivers/pci/setup-res.c).
Os hashes do código-fonte realmente inspecionado estão na prova abaixo;
essas URLs são referências upstream, não substituem a versão selecionada.

A captura é somente leitura e exige BAR0 de 32 KiB/BAR2 de 4 MiB,
identidades/classes/configuração N71 e decode/bus-master desligados.
Registra os três campos adicionais que o alocador pode mudar:
MEM_BASE/LIMIT em `0x20`, PREF_LIMIT_UPPER32 em `0x2c` e
IO_BASE/LIMIT_UPPER16 em `0x30`. Captura incompleta não publica ownership;
captura repetida recusa sobrescrever estado ativo ou pendente.

Na fase explícita, aceita BARs 64-bit não prefetch alinhados na janela PCI
`c0000000–ffffffff`, upper32 zero e janela MEM dentro dessa faixa.
IO/PREF só podem ser desativados; COMMAND e BRIDGE_CONTROL são preservados.
Identidade e decode/master das duas funções são conferidos antes das escritas,
com readback, orçamento de 64 tentativas e primeiro erro conservado.
Recusa capacidades/W1C e larguras que alcançariam STATUS adjacente.

A restauração adicional exige fase encerrada e confirmação de remoção do bus
pelo adaptador. Confere identidade/decode e readback; falha conserva pending
para retry sem recaptura. BARs e as janelas anteriores ainda pertencem à
limpeza genérica do scan, que deve ocorrer depois desses campos adicionais.
O helper isolado não comprova que um bus real foi removido.

Para reproduzir a prova nativa em uma cópia descartável do código público:

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_resource_write.py -v
```

Mac e Ubuntu ARM64 passaram 188 cenários e 25 mutações compiladas por
SIGABRT/assertion, uma prova unittest em cada plataforma. Seis inputs e os
dois logs foram preservados/conferidos por SHA; AST e lint de erros fatais
passaram. O backend de configuração é sintético, executando a política real.
Compilação, import e timeout não contam como mutation kill.
[Prova sanitizada, inputs e referências](evidence/n71-pci-resource-write.json).

A prova isolada deste checkpoint não chama o adaptador/caller/journal.
Não há PCI core, build de módulo, boot ou USB nessa prova. Reserva e
atribuição na árvore de recursos, ausência de sobreposição final, readback
de registradores opcionais no hardware, IRQ/DMA/IOMMU, rádio e energia
continuam pendentes. A próxima integração deve permitir atribuição por SSH
no mesmo boot; não pedir DFU somente para repetir o helper.

## Atribuição no bus retido — adaptador, caller e build real

O adaptador `3f09eec` reserva a janela MEM32 na árvore `iomem`, captura a
configuração e chama `pci_bus_size_bridges`/`pci_bus_assign_resources`
sob rescan lock. Exige topologia N71/BCM4350 exata e recursos inicialmente
sem parent. A política anterior cobre as escritas do alocador; ao final,
confere árvore/flags/tamanhos/alinhamento, tradução CPU→PCI, ausência de
sobreposição, BAR0/BAR2 e janela MEM por readback. IO/PREF permanecem
desativados, COMMAND/decode/master e BRIDGE_CONTROL são preservados.

Caller `3ff8769` oferece `action=assign` somente em `scan_hold=1` com bus
retido, módulo/reset e quatro domínios ativos, sem erro anterior ou power-put
pendente. Um pin temporário e o mutex da sessão cobrem a operação. A ação
não repete enumeração/scan nem encerra os owners; repetição retorna EALREADY
sem contaminar `primary_error`. Falhas reais conservam o primeiro erro e
impedem outra atribuição no mesmo bus.

O getter somente leitura `resources` informa
`ready/attempted/assigned/pending/claimed/active/error`. `assigned=1` exige
bus vivo/retido, atribuição concluída, janela na árvore iomem e ausência de
fase/erro. Um bus removido continua `assigned=0` mesmo com rollback ou
reserva pendentes. Recusas anteriores à fase e erros após liberar o bridge
continuam observáveis. Os formatos anteriores de `status` e `held` permanecem.

Cleanup recusa fase ativa, remove o bus, restaura os três campos adicionais
e a configuração genérica, depois libera a janela global somente com child
vazio. Falhas mantêm bridge/owners para retry; reset/energia/REG_ON continuam
dependendo dessa limpeza comprovada. A validação da árvore sintética não
substitui readback e restauração no iPhone.

Reprodução nativa numa cópia descartável do código público:

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_diagnostic_caller.py -v
```

Em cada plataforma Mac/Ubuntu ARM64: adaptador64 cenários/51 mutações,
três provas unittest e12 inputs; caller121 cenários/59 mutações, uma prova
unittest e cinco inputs. Todas as mutações compilaram com Werror e falharam
por SIGABRT/assertion; compile/import/timeout não contam como kills.
O código real foi executado com dependências de kernel/PCI sintéticas,
e inputs/logs/exit foram conferidos por SHA. AST/Flake8 fatal passaram.

O build real ocorreu numa cópia exclusiva dos48 inputs públicos,
`/home/ubuntu/n71-resource-caller-modules-20261005/phone/kernel`, na VM
dedicada, usando o source/output power2 já qualificado:

```sh
make -C /home/ubuntu/kernel-n71-binding-source-20261005 \
  O=/home/ubuntu/kernel-n71-binding-build-20261005 ARCH=arm64 -j2 \
  W=1 KCFLAGS=-Werror LOCALVERSION= \
  M=/home/ubuntu/n71-resource-caller-modules-20261005/phone/kernel \
  KBUILD_EXTRA_SYMBOLS=/home/ubuntu/kernel-n71-binding-build-20261005/vmlinux.symvers \
  modules
```

Os seis módulos passaram Werror/modpost/ELF AArch64/vermagic
`7.2.0-iphone6s-dart-serdev-power2 SMP preempt mod_unload aarch64`.
PCIe84.696 bytes; REG_ON17.688 bytes/SHA anterior intacto. Fonte/config/Image
e exports foram conferidos antes/depois. `modinfo -p` confirmou os getters
e a ação, `nm -u` confirmou alocação/reserva/release vinculados. A prova
sanitizada contém os48 inputs, módulos e logs por SHA; payload/DT,
identidades, chaves e logs completos permanecem privados.
[Evidência integrada](evidence/n71-pci-resource-assignment.json).

Neste checkpoint, seleção/provenance/journal do host ainda precisavam
reconhecer esse build e registrar o checkpoint antes de `assign`. A seleção
e o checkpoint da ação posteriores estão descritos abaixo.
Nenhum módulo novo carregado, novo Image, boot ou DFU nesta etapa.
Atribuição/restauração no kernel em execução, IRQ/IOMMU, driver/firmware/radio,
Wi-Fi e telemetria/carga Linux continuam pendentes.

CI anterior `3f09eec`: [PR37394918817](https://github.com/djalmajr/iphone6s-linux/actions/runs/37394918817)
e [push37394914087](https://github.com/djalmajr/iphone6s-linux/actions/runs/37394914087)
concluíram cancelled; Mac/Windows success e Ubuntu cancelled nos dois eventos.
O log do job Ubuntu da PR não foi disponibilizado (`log not found`);
causa segue não confirmada na [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38).
Esses resultados não cobrem o caller novo.

## Seleção do módulo com atribuição — candidata privada preparada

Código `d94a14e` acrescenta `--pcie-resource-capable` ao composer e
`--resource-capable` ao coletor. As flags selecionam exclusivamente o build
de atribuição acima, através do contrato `n71_resource_result`; exigem held
explícito e seus pré-requisitos power2/ASPM/REG_ON. A aquisição conserva o
bus e não executa `assign` automaticamente. Sem essas flags, o seletor held
anterior continua sendo usado.

O composer grava `pcie_resource_capable` como booleano exato. O coletor
exige correspondência exata com sua flag; ausência da chave nos perfis
antigos equivale somente a false. Tamanho/SHA/ELF/vermagic dos módulos e
ASPM no payload são conferidos antes dos efeitos. A seleção também é
propagada à Session no caminho de aquisição e no check local de retomada.

Com os módulos privados do build186 e os artefatos já qualificados:

```sh
python3 -B scripts/build/compose-n71-diagnostic.py \
  --source-profile "$base_profile/deployment.json" \
  --kernel-dir "$kernel_artifacts" \
  --kernel-patchset n71-dart-serdev-power-v2 \
  --diagnostic-dir "$diagnostic_dt" \
  --module "$pcie_module" --module-sha256 "$pcie_sha256" \
  --reg-on-module "$reg_on_module" --output-dir "$candidate" \
  --pcie-aspm-off --pcie-scan-hold --pcie-resource-capable
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --check
```

A candidata real completa passou esses checks sem SSH/USB. O payload
inteiro, deployment, initramfs, identidades e REG_ON são iguais ao perfil
held anterior; PCIe84.696 bytes/SHA2dcdebc2 e provenance são novos. Os48
inputs do build real permaneceram iguais, sem recompilar kernel ou módulos.
O perfil novo e os anteriores permanecem privados.

Reprodução dos contratos host numa cópia descartável do código público:

```sh
set -e
python3 -B -m unittest discover -s tests -p 'test_n71_diagnostic_*.py' -v
python3 -B -m unittest discover -s tests -p test_n71_held_session.py -v
python3 -B -m unittest discover -s tests -p test_n71_link_session.py -v
python3 -B tests/run_n71_diagnostic_payload_mutations.py
python3 -B tests/run_n71_link_session_mutations.py
```

Mac/Ubuntu ARM64: 82 testes/144 mutações por AssertionError em cada
plataforma, com53 inputs e cinco logs por SHA. Composer16/33, held21/30 e
coletor legado45/81; seis testes/12 mutações novos. Após corrigir somente a
fixture composer, foram reutilizados held21/30 e45 testes legados, com52
inputs intactos; composer16/33 e81 mutações legadas foram executados no
pacote final. AST e Flake8 fatal passaram. Gates interrompidos não foram
contados como qualificação completa; import/compile/timeout não são kills.
[Prova sanitizada da seleção](evidence/n71-pci-resource-profile.json).

Nesse checkpoint, o journal ainda precisava incluir a ação, getter e prova
de atribuição e sua restauração; a integração está descrita abaixo.
A candidata desta seleção não foi carregada no
iPhone; Wi-Fi, IRQ/IOMMU/driver e telemetria/carga Linux continuam pendentes.

## Atribuição com journal — ação e limpeza no mesmo boot

Código `2e07258` oferece `--assign-held DIR`, exclusivo de `--release-held`.
Exige fonte privada held com `--resource-capable`, os demais opt-ins do
perfil e ausência de previous-clean. Confere perfil, boot, módulos/params,
REG_ON, histórico e getter resources antes dos efeitos; a ação não refaz
insmod, scan, reset ou ativação de REG_ON.

O journal salva `resource_attempted` antes do setter. A saída da ação,
getter e evento kernel precisam ser completos e concordar, incluindo erro,
owners e orçamento. A prova privada possui hash e acompanha o checkpoint.
Uma retomada com prova íntegra reutiliza a atribuição sem outro setter.
Flags de modo/intenção são booleanas exatas; journals antigos sem esses
campos são aceitos somente como false. Prova perdida, getter diferente,
histórico desconhecido ou restauração incoerente recusam efeitos.

No boot Linux qualificado, use diretórios novos diretamente sob runtime:

```sh
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --output-dir "$held_acquisition"
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --assign-held "$held_acquisition" \
  --output-dir "$held_assignment"
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --assign-held "$held_assignment" \
  --output-dir "$held_reuse"
python3 -B scripts/host/n71-link-session.py \
  --profile "$candidate/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --release-held "$held_reuse" \
  --output-dir "$held_released"
```

O exemplo de reuso pressupõe atribuição positiva. Um resultado negativo
com prova completa conserva o erro e os owners; use release sobre a saída
comprovada, sem repetir assign. Cleanup confere remoção/restore extra,
configuração genérica, release da janela e PME/TLS/reset/energia antes de
PCI unload e REG_ON restore. Falha de cleanup preserva o estado para nova
invocação release no mesmo boot; etapas completas não são repetidas.
O código de saída continua negativo após liberar todos os owners quando
houve erro de atribuição ou stop; confira `cleanup_verified` separadamente.

Se transporte/saída não permitirem prova completa ou não concordarem,
a intenção fica pendente e a retomada é recusada. Não criar prova ou
checkpoint manualmente para contornar esse controle.

Reprodução host sem aparelho numa cópia descartável:

```sh
set -e
python3 -B -m unittest discover -s tests -p test_n71_resource_stage.py -v
python3 -B -m unittest discover -s tests -p test_n71_held_session.py -v
python3 -B -m unittest discover -s tests -p test_n71_link_session.py -v
python3 -B tests/run_n71_link_session_mutations.py
```

Mac/Ubuntu ARM64: 82 testes/137 mutações por AssertionError por plataforma,
55 inputs/quatro logs/exit SHA conferidos. Estágio16/26, held21/30 e
legado45/81;37 testes/56 mutações Mac já aprovados foram reutilizados com
55 inputs intactos, ARM64 executou o conjunto. Ação e snapshot rodaram em
Bash contra sysfs/arquivos privados sintéticos; testes também exercitaram
CLI real. AST/Flake8 fatal passaram; import/compile/timeout não são kills.
[Prova sanitizada do journal](evidence/n71-pci-resource-session.json).

A candidata real anterior passou o check local atualizado;48 inputs do
build real permaneceram iguais, sem recompilar módulos/kernel. Essa prova
ainda não carrega o módulo nem comprova atribuição/restauração no iPhone.
A próxima sessão física deve reunir esses controles sem reboots entre
etapas. IRQ/IOMMU/driver/firmware, Wi-Fi e telemetria/carga seguem abertos.

## Primeira atribuição física — erro preservado e cleanup retomado

A sessão power2 real fez uma aquisição retida positiva e uma atribuição,
sem reiniciar entre etapas. Restore de44 entradas e SSH/HTTP/Bash/Herdr
passaram. C/module/payload/identidades permaneciam os qualificados;
nenhum Image ou módulo foi recompilado durante a sessão.
[Prova física selecionada](evidence/n71-pci-resource-first-physical.json).

A continuação inicial encontrou uma leitura extra
`N71_REG_ON_READ error=0 value_valid=1 value=81`. O getter do módulo emite
esse registro a cada leitura; o comparador exigia histórico idêntico e
recusou antes do setter. `eba8f30` preserva o prefixo integral e admite
somente sufixo de leituras positivas completas, com value_valid1 e valor
igual ao getter vivo único. Com REG_ON ausente, exige histórico exatamente
igual. Estado/controle/módulos/ownership continuam comparados ao checkpoint.
Nenhuma linha é eliminada, reescrita ou rebased manualmente.

A fixture passou a emitir essas leituras. `71df973` corrige o caso
adversarial que esquecia uma leitura de uma tentativa recusada: o checkpoint
passa a conter o delta real antes da operação desconhecida, exercitando
o guard de operação, com recusa antes do cleanup. Mac/Ubuntu ARM64:
44 testes/63 mutações por AssertionError por plataforma,57 inputs/AST,
Flake8 fatal e diff aprovados. História7/7, held21/30 e resource16/26.
Os dois primeiros gates intactos foram reutilizados após corrigir somente
a fixture resource; import/compile/timeout não são kills.
[Regressão e inputs](evidence/n71-reg-on-held-history.json).

Reprodução host numa cópia descartável, sem aparelho:

```sh
set -e
python3 -B -m unittest discover -s tests -p test_n71_held_history.py -v
python3 -B -m unittest discover -s tests -p test_n71_held_session.py -v
python3 -B -m unittest discover -s tests -p test_n71_resource_stage.py -v
```

Após qualificação, a continuação usou a aquisição original no mesmo boot.
A ação retornou-5,9 tentativas/2 escritas e assigned0/pending1/claimed1.
A primeira recusa foi root0:08/030/dword/0000ffff. O código preservado faz
write/readback exato; o valor real pós-write não foi registrado. Não
presumir campos hardwired ou ampliar a máscara com base somente no errno.
As recusas posteriores são latched, sem prova independente para permissões.

O primeiro release removeu o bus e comprovou restore extra/genérico e
release da janela, mas reteve reset/energia pelo stop-error-5. Um retry
somente de cleanup liberou esses owners e descarregou PCIe/REG_ON,
restaurando controle80. Não repetiu scan ou assign. O resultado continuou
negativo; cleanup_verified true não transforma a atribuição em sucesso.
Não foi exercitado reuso de atribuição positiva, bind, enable ou DMA.

```mermaid
flowchart TD
    A["Aquisição retida positiva"] --> B["Getter registrado: correção host no mesmo boot"]
    B --> C["Atribuição negativa: primeiro erro -5"]
    C --> D["Release: bus/configuração/janela restaurados"]
    D --> E["Retry: reset/energia/REG_ON liberados"]
    E --> F["Serviços, snapshot44, sync e retorno ao iOS"]
```

Os serviços, snapshot44/sync e retorno automático USB ao iOS passaram.
Uptime final26 minutos; a duração aumentou pela correção host no boot,
sem reinícios intermediários. iOS100→77% incluindo transições; recarga e
fonte externas ativas no retorno. Não é medição de corrente líquida,
saúde ou carga sustentada Linux; power_supply continuou sem entradas.
O telefone voltou ao iOS para recarga durante desenvolvimento offline.
Firmware/DT/payload/identidades/boot ID/snapshot ID/logs brutos continuam
privados. O próximo gate registra o readback real da primeira recusa
antes de alterar o contrato de escrita.

## Readback da primeira falha — candidata qualificada sem reiniciar

A falha física em 0x30 mostrou que faltava o valor retornado pela leitura
obrigatória após a escrita. A política agora conserva somente a primeira
falha que alcançou essa operação: pedido, valor anterior, valor retornado
válido e erros brutos dos callbacks. Não acrescenta I/O ou retries e não
altera permissões, orçamento ou restauração. `writes` conta somente escritas
verificadas; uma verificação negativa pode ocorrer depois de uma escrita
executada que não incrementou o contador.

`N71_PCIE_ASSIGN_READBACK` aparece uma vez antes de `RESOURCE_RESULT`.
`failed=0` exige campos zerados e não inventa uma leitura; `failed=1` exige
validade/valores/erro consistentes com a primeira recusa. Write ou read que
retornou erro não prova um valor retornado válido. Os registros brutos ficam
no checkpoint/proof e são comparados ao retomar e limpar. Build selecionado
com `assignment_readback=true` exige a linha; o build legado conserva seu
contrato. Resultado negativo continua negativo mesmo com cleanup completo.

A seleção usa o SHA concreto do arquivo no composer e da provenance no
coletor; não há outra flag CLI. O registro do build novo verifica a evidência
base, contrato, ABI/interface e REG_ON preservado. SHA desconhecido ou
metadata divergente recusam a candidata antes de transferir módulos.
[Build/contratos](evidence/n71-pci-resource-readback.json),
[integração/candidata](evidence/n71-pci-readback-profile.json),
[plano e decisões](../.agents/plans/n71-primeiro-readback-pci.md).

| Gate por plataforma Mac/Ubuntu ARM64 | Resultado |
|---|---|
| Política real em backend sintético | 194 cenários; 36 mutações compiladas/SIGABRT |
| Adaptador real com PCI API sintética | 65 cenários; 57 mutações compiladas/SIGABRT |
| Integração final composer/coletor/journal | 64 testes; 108 mutações/AssertionError; 62 inputs |
| Seletor de build e contrato anterior | 14 testes; 38 mutações/AssertionError |
| Módulos na VM dedicada | Seis módulos; Werror/modpost/ELF/vermagic; 48 inputs |

Os gates foram incrementais. Código e fixtures alterados foram
requalificados; provas de C/build intactas foram reutilizadas durante a
integração host. Compilação/importação/timeout e fixtures recusadas por um
controle diferente não contam como mutation kill. A leitura de um arquivo
deliberadamente removido pelo mutante foi substituída por uma assertion do
contrato de arquivos antes da leitura. O último anchor legado foi atualizado
e somente held21/30 repetido. AST/lint fatal/diff e hashes/exit passaram.

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_resource_write.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_resource_readback.py -v
python3 -B -m unittest discover -s tests -p test_n71_resource_build.py -v
python3 -B tests/run_n71_diagnostic_payload_mutations.py
python3 -B -m unittest discover -s tests -p test_n71_held_session.py -v
python3 -B -m unittest discover -s tests -p test_n71_resource_stage.py -v
```

O build real usa o source/output power2 qualificado e um diretório externo
novo, seguindo o comando `make` da reprodução anterior. PCIe: 85.096 bytes,
SHA a56fafb4; os outros cinco módulos, fontes PCI verificadas e
config/Image/exports permaneceram iguais. A candidata real separada passou
composer e --check, com oito arquivos privados, diretório 700/arquivos 600.
Deployment, payload/DT/kernel/loader, initramfs, identidades
e REG_ON são byte a byte iguais ao perfil resource anterior. Somente PCIe e
seu SHA na provenance mudaram. O perfil anterior e o default permanecem.

Comandos executados na raiz `iphone-linux-tools`; a pasta de saída deve ser
nova. Os arquivos referenciados são locais privados produzidos pelas receitas
anteriores, não downloads públicos. A seleção depende do hash completo do
módulo qualificado:

```sh
python3 -B scripts/build/compose-n71-diagnostic.py \
  --source-profile runtime/n71-binding-base-profile-20261005/deployment.json \
  --kernel-dir runtime/kernel-n71-binding-artifacts-20261005 \
  --kernel-patchset n71-dart-serdev-power-v2 \
  --diagnostic-dir runtime/n71-pcie-diagnostic-20261002 \
  --module runtime/n71-first-readback-20261006/modules/n71-pcie-diagnostic.ko \
  --module-sha256 a56fafb49ec8df0746241f45c5ff4efb1b5e01b680cfb0429f9933c09d1bd2cf \
  --pcie-aspm-off --pcie-scan-hold --pcie-resource-capable \
  --reg-on-module runtime/n71-first-readback-20261006/modules/n71-wlan-power-diagnostic.ko \
  --output-dir runtime/n71-binding-readback-profile-20261006
python3 -B scripts/host/n71-link-session.py \
  --profile runtime/n71-binding-readback-profile-20261006/deployment.json \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --check
```

Esta rodada não executou o módulo novo no iPhone. Atribuição positiva,
registradores opcionais, IRQ/DMA/IOMMU, rádio e alimentação precisam de prova
física. O iPhone foi reconfirmado no iOS com 100%; isso não é saúde da bateria
nem carga Linux. A próxima sessão agrupa aquisição, assign/coleta, limpeza
com retry, serviços, snapshot/sync e retorno ao iOS. O readback real orientará
a correção seguinte; não presumir bits hardwired apenas pelo errno-5.

## Próximos gates

O coletor PME/ASPM usado na sessão física seleciona o build169 e exige os
opt-ins exatos, SHA/ABI do módulo e bootargs literais no payload. No telefone,
antes de transferir módulos,
exige um único `pcie_aspm=off` no cmdline e o marcador de suporte ASPM
desativado. O parser exige prepare/restore PME completos e conserva REG_ON
se não houver prova de cleanup. Retry de restauração não executa novo scan.

A aquisição/atribuição negativa e sua restauração já têm prova física
acima; ainda não há endereços persistentes atribuídos positivamente.
Registrar readback da recusa0x30, qualificar sua semântica e comprovar
atribuição positiva, IRQ/IOMMU do endpoint e depois driver/firmware/radio.
Esses passos não estão habilitados pela prova diagnóstica. Alimentação e
telemetria precisam de acesso HDQ/charger e medição própria.

Manter o telefone no iOS para recarga durante desenvolvimento/build. Reunir
checks e módulos compatíveis para a próxima sessão por SSH; novo DFU somente
quando uma candidata agrupada exigir boot novo. Snapshot/sync e retorno
automático devem ser verificados novamente ao final. Um retorno positivo não
fecha a confiabilidade de [#21](https://github.com/djalmajr/iphone6s-linux/issues/21);
o fallback físico continua disponível quando USB não confirmar o iOS.

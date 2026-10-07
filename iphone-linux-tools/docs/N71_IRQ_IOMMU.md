# N71: IRQ e IOMMU antes do rádio

## Checkpoint — 2026-10-06

[Issue40](https://github.com/djalmajr/iphone6s-linux/issues/40), [plano](../.agents/plans/n71-irq-iommu-bindings.md). A atribuição/retomada/cleanup da [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39) está concluída no hardware. IRQ255/0 e links of_node/IOMMU ausentes foram medidos com enable0/sem driver, sem MASTER/DMA. Esses valores descrevem a sessão; não demonstram entrega IRQ, attachment ou defeito da associação.

## Fontes fixadas e fatos observados offline

Fonte958481f87fee0949ff6a9a4af77f7eb6dac8a149, já preservada na VM de build. A leitura não modificou fonte/config/Image/exports nem o telefone.

| Ponto | Observação e consequência |
|---|---|
| [scan local](../phone/kernel/n71-pcie-scan.h#L368) | Usa `pci_alloc_host_bridge`, parent do diagnóstico, config ops próprias e enable negado. Não chama `devm_of_pci_bridge_init`, nem inicia driver/radio. |
| [probe.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/probe.c#L685) | Alloc simples e alloc devm são paths diferentes; devm chama inicialização OF em721. Não inferir hooks devm no path simples. |
| [of.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/of.c#L638) | Inicialização OF prepara swizzle/map_irq e ranges. Adotar devm inteiro também muda aquisição de recursos, já qualificada separadamente; não trocar o constructor sem estudar ownership. |
| [irq.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/irq.c#L142) | Sem callback map_irq, assign não cria rota INTx funcional. O callback sozinho não prova que o controlador encaminhe a interrupção. |
| [pci-driver.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/pci-driver.c#L1668) | DMA configure consulta o OF node do parent do host; uso do default domain depende do driver/managed DMA. Não exigir um endpoint of_node como prova universal nem iniciar bind para observar sysfs. |
| [brcmfmac/pcie.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L968) | Solicita MSI e depois IRQ do pdev; caminho anterior habilita dispositivo e MASTER. Registrar o driver mistura IRQ, DMA e firmware; precisa de guards/attachment antes. |
| [provider DART local](../phone/kernel/n71-dart-provider.h#L54) | Valida IRQ248, domain/cells/ownership e faz ciclo temporário; não estabelece attachment PCI persistente. Retenção/teardown precisam de desenho próprio. |
| [topologia](../scripts/build/prepare-n71-topology.py#L124) | Declara PCIeIRQ244/247/250/253 e DART248. A declaração não determina qual rota é INTx/MSI ou qual máscara/status N71 aciona o sinal. |

O upstream [pci_dma_configure](https://github.com/torvalds/linux/blob/master/drivers/pci/pci-driver.c) confirma a função geral; o checkout fixado acima é a autoridade para offsets/API desta build. O driver Apple atual tem domains de MSI/port e dados de outros SoCs; isso não valida seus registradores no A9.

## O que reaproveitar

- [Módulos brcmfmac/cfg80211 já qualificados](evidence/n71-wifi-binding-modules.json): ler ABI/dependências/limites antes de decidir outro build; adicionais não são carregados automaticamente.
- [Seleção de firmware](evidence/n71-firmware-selection.json): tabela/compatibilidade e ausência de validação da calibração Apple permanecem. Firmware/calibração privados.
- [Prova física PCIe](evidence/n71-pci-pref64-unsized-physical.json): ownership e recursos devem permanecer enquanto callbacks puderem acessar hardware.
- [Perfil corrigido](evidence/n71-pci-pref64-unsized-profile.json): console/SSH/Bash/Herdr/HTTP/snapshots e retorno iOS devem continuar funcionando.

## Próximo recorte

Fechar referências primárias de INTx/MSI, pin/porta/cells e streams/mapping N71 a partir da topologia/logs/artefatos já disponíveis. Planejar a candidata de provider retido e associação com refs/domains/teardown separados, conservando a rota diagnóstica default e recusando drift. Preparar qualquer coleta ainda necessária junto das demais antes de um boot; não reiniciar apenas para investigar um dado que possa ser lido na sessão por SSH.

Sem alteração de hardware nesta investigação. Não há nova prova de IRQ/DMA/Wi-Fi, carga ou gauge Linux. Alimentação contínua permanece na#2. O telefone ficou no iOS para carregar durante desenvolvimento/builds; nenhuma ação no Mac fora da VM e das operações já autorizadas do projeto.

## MSI N71 e capacidade física recuperada — 2026-10-07 UTC

[Referência selecionada](evidence/n71-irq-iommu-reference.json). O log de aquisição da sessão física já concluída contém `interrupt=00000100`, portanto line0/pin1, e capability MSI em58/header00886805: endereço64 bits, até16 vetores, MSI desativado e MSI-X ausente. A leitura teve error0/19 reads. Reutilizamos esse log pelo hash, sem outro boot ou escrita de config. Pin1 não prova rota INTx funcional.

O ADT N71 fixado declara `msi-address=0xbffff000`, `msi-vector-offset=256`, total32 e parent AIC phandle16. A bridge1 declara base8/count8. O driver Apple lê essas propriedades e acrescenta o offset do controlador ao índice lógico ao publicar a interrupção no parent: os números AIC de registro são264..271. Isso é referência estática, não entrega de IRQ no Linux. A codificação do **message data** ainda precisa ser fechada separadamente; não confundir o índice lógico8 com o número AIC264.

O ADT Apple usa uma célula no AIC; o FDT Linux fixado usa três. A função `aic_irq_domain_translate` aceita três/quatro, trata célula0 como tipo e aplica sua própria codificação de hwirq. Para MSI, a referência de requisição Linux é `<0, 264 + índice, 1>` (edge rising), índice0..7. Um virq Linux ou hwirq interno não pode ser comparado diretamente com264. [Fonte AIC fixada](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/irqchip/irq-apple-aic.c#L683).

O caminho do mapper Apple já publicado liga WLAN/bridge1 ao DART1, stream0; o driver Linux S5L oferece quatro streams, OAS36 e nenhum bypass. Para PCI, `of_iommu_configure` percorre aliases e usa o mapping do host. Acrescentar `iommus` apenas ao endpoint não reproduz esse caminho. Provider retido, associação PCI, domínio, teardown e restauração permanecem pendentes. [Referência de stream](evidence/n71-dart-apple-stream-reference.json), [fonte OF/IOMMU](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/iommu/of_iommu.c#L136).

### Decisão de implementação

Preparar MSI para o WLAN, mantendo INTx sem rota implementada. A capacidade MSI foi medida e o brcmfmac solicita MSI; liberar INTx como fallback agora pressuporia encaminhamento ainda não comprovado. A primeira fatia calcula e valida somente as células AIC dos oito vetores. Não cria IRQ/domain, não compõe message data e não altera MMIO, DT ou driver. A integração posterior exige refs/ownership, baseline e restauração, inclusive falhas parciais. Decode/MASTER continuam negados até os gates de DMA.

### Reprodução das referências existentes

Use os arquivos privados obtidos pelo [procedimento N71](N71_REFERENCIA.md), sem baixar firmware novamente. Confira SHA do ADT/kernel e os sete recortes listados no JSON. Os endereços pertencem somente ao binário fixado. `file_offset`, tamanho e digest permitem validar os recortes com Python, sem executar firmware:

```python
import hashlib, json
from pathlib import Path

e = json.loads(Path('docs/evidence/n71-irq-iommu-reference.json').read_text())
raw = Path('runtime/SUA_REFERENCIA/kernelcache.n71.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest() == e['apple_kernel_sha256']
for w in e['source_windows']:
    part = raw[w['file_offset']:w['file_offset'] + w['bytes']]
    assert len(part) == w['bytes']
    assert hashlib.sha256(part).hexdigest() == w['sha256']
```

A [fonte oficial IOPCIFamily fixada](https://github.com/apple-oss-distributions/IOPCIFamily/blob/4822b27a36e2de70e231ecf2bf3021384fab6ec2/IOPCIMessagedInterruptController.cpp) separa alocação de vetor e message data. Serve para conferir o contrato; o driver N71 privado é a referência dos registradores. Referências selecionadas status100/mask104/MSI config124/base128 não são autorização para leitura/escrita: efeitos de leitura e contrato completo de restore ainda não foram qualificados.

Energia: os dois cycles genpd/inspect de I2C1 já passaram no hardware, conforme [N71_HDQ](N71_HDQ.md#primeira-sessão-física-power2--ciclos-e-inspeção-verificados). Pinos/clock/IRQ/controller restore e SN2400/HDQ continuam necessários; não iniciar transferência no carregador apenas porque o domínio responde. O iPhone está no iOS durante a preparação offline.

## F1a — células AIC qualificadas, sem alocação de IRQ

O [helper isolado](../phone/kernel/n71-wlan-irq-reference.h) valida a topologia32/offset256/porta1/base8/count8/células3 e calcula os oito pedidos Linux. Recusa topologia diferente com EINVAL e índice fora da porta com ERANGE, preservando output em erro. Não converte para virq/hwirq interno nem produz message data. Nenhum caller, perfil, initramfs ou Image foi alterado; não houve carga no telefone. [Prova selecionada](evidence/n71-wlan-aic-reference.json).

Mac e Ubuntu ARM64 passaram61 cenários/14 mutações compiladas por SIGABRT/asserção: oito vetores,48 topologias recusadas, três índices inválidos e dois contratos nulos. As mutações cobrem guards, fronteira, erro, soma do offset, células tipo/IRQ/trigger e output em recusa. Falha de compilação/import/timeout não conta como kill. AST e lint fatal passaram; não há typechecker Python neste projeto. C usa C11/Wall/Wextra/Werror/pedantic.

Probe kernel na VM passou W=1/Werror/modpost/ELF64 AArch64/vermagic power2. Fonte958481f, config, Image e vmlinux.symvers permaneceram nos hashes fixados. O runner tentou primeiro o nome ausente Module.symvers e parou antes de executar os gates; corrigimos para vmlinux.symvers com KBUILD_EXTRA_SYMBOLS. A descrição ausente do módulo de prova foi adicionada e somente o build afetado foi repetido; os testes nativos foram reutilizados com os três inputs intactos. A baseline avisa que Module.symvers da raiz está ausente; exports explícitos são fornecidos e erros de símbolos não foram permitidos. O módulo de prova é privado e não foi carregado.

### Reproduzir os contratos

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_wlan_irq_reference.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_wlan_irq_reference.py
```

Para o probe ABI, use a VM dedicada e os diretórios de fonte/build já fixados. Crie uma pasta M nova, copie o header e use um módulo mínimo com licença GPL/descrição que chame `n71_wlan_irq_reference` no init com `{3,32,256,1,8,8,0}`. **Apenas compile**; esse probe não é módulo de diagnóstico para o aparelho. Makefile: `obj-m += n71-wlan-irq-abi-probe.o`. Na VM:

```sh
source_dir=/home/ubuntu/kernel-n71-binding-source-20261005
build_dir=/home/ubuntu/kernel-n71-binding-build-20261005
probe_dir=/home/ubuntu/SUA_PASTA_M_NOVA
make -C "$source_dir" O="$build_dir" M="$probe_dir" W=1 KCFLAGS=-Werror \
  KBUILD_EXTRA_SYMBOLS="$build_dir/vmlinux.symvers" modules -j2
```

Compare config/Image/exports antes/depois com os hashes do JSON; confira ELF/vermagic e preserve logs privadamente. Sem dependências/pacotes novos ou alteração de configuração do Mac. Testes anteriores de PCI/transportes conservam sua validade porque o helper não foi integrado. O próximo resultado esperado é fechar message data e ownership/restore MSI/provider DART retido; #40/#9/#2 e o goal permanecem abertos.

## F1b/F1c — provider DART retido e recuperação na mesma sessão

[Qualificação sanitizada](evidence/n71-dart-retained-qualification.json), commits c0fb252/003998d. O ciclo anterior mantinha o provider numa variável local e descartava MMIO/node/claim mesmo após falha de stop ou restauração. Agora o estado pertence à sessão desde antes do start. Probe parcial, impossibilidade de reclamar MMIO, falha de leitura/guard/write ou readback divergente conservam baseline e ownership para nova tentativa, sem reboot. O ciclo temporário continua disponível; seu contrato de sucesso mantém quatro snapshots/16 escritas/17 guards explícitos.

### Alterações e contrato do caller

- [Lease](../phone/kernel/n71-dart-lease.h): guarda baseline uma vez, impede aquisição repetida, marca tentativa antes do probe e retoma no primeiro TTBR não confirmado. Confere o prefixo antes da retomada e todos os16 words depois; uma divergência comprovada recua o cursor. Write que retorna erro, inclusive depois de armazenar, não avança o cursor. Cleanup invalida readiness antes de stop parcial e conserva o primeiro erro de operação.
- [Backend](../phone/kernel/n71-dart-provider.h): conserva struct/MMIO/node/IRQ/device/claim enquanto houver recuperação pendente. Orçamentos de snapshot/quiet reiniciam por tentativa; não descarta owner em falha. Liberação de ownership não apaga um erro de operação já medido. A aquisição das IRQs ainda usa o backend anterior, cujo lookup/criação precisa de qualificação atômica.
- [Estado da sessão](../phone/kernel/n71-pcie-mmio.h) e [caller](../phone/kernel/n71-pcie-diagnostic.c): cleanup DART precede PCI/reset/power/module_put. `dart-hold` exige scan_hold, barramento vivo, recursos atribuídos/claimed e sessão sem erro. `dart-release` libera somente DART, conservando host/energia para os testes seguintes; cleanup completo tenta recuperar antes de soltar os outros owners. O getter `dart` mostra estado e cursor; status/held/resources mantêm o formato anterior.
- [Testes](../tests/test_n71_dart_lease.py), [fixtures nativas](../tests/test_n71_dart_provider.py): falhas de cada write/guard/snapshot, start parcial, stop/claim/owner externos, idempotência, recursos/refcounts, baseline/cursor/readback e ordem de cleanup/pin.

As ações estão no código do módulo e não foram adicionadas ao perfil/autoload ou ao coletor físico. O parser temporário existente aceita o sucesso anterior; múltiplos resultados de retry/hold precisam de collector próprio. Não use esse parser como prova de lifecycle retido.

### Verificação e reprodução

Mac e Ubuntu ARM64:73 cenários do lease,15 do backend e quatro do cleanup real, total92 por plataforma.15+14+3 mutações compilaram e foram detectadas por SIGABRT/asserção, total32. O fixture executa o header de produção; duas funções do caller são extraídas literalmente, compiladas e exercidas com owners vivos/falhas. APIs de platform/OF/IRQ/MMIO são simuladas e têm recursos/refcounts verificados. Não são provas de IRQ, hardware, DMA ou concorrência. O build completo cobre o contexto kernel real.

No Mac, regressão de ciclo/parser passou seis testes; no Ubuntu, ciclo temporário passou um teste com seis mutações C. AST/lint fatal passaram. Não há typechecker Python neste projeto; C usa Werror, C11/pedantic no lease/cleanup e GNU11 no fixture do backend. Este fixture suprime somente warnings de funções stub não usadas; o módulo real usa W=1/Werror sem essa supressão.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_dart_lease.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_dart_provider.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_dart_cycle*.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_dart_lease.py tests/test_n71_dart_provider.py
```

Para reproduzir o build externo, copie todos os headers de `phone/kernel/` e `n71-pcie-diagnostic.c` para uma pasta M nova na VM dedicada. Confira os hashes do JSON; crie `Makefile` com `obj-m += n71-pcie-diagnostic.o`. Não modifique a fonte/build preservados, não execute insmod e não sobrescreva o módulo físico anterior. Use o comando make acima com os mesmos source_dir/build_dir e KBUILD_EXTRA_SYMBOLS.

O módulo final tem91.736 bytes/SHAae3e71f24b748e81af25ed4ae7c73dd5f9dac90524f39f5b0c5238fbf6b21bfd, ELF64 AArch64/vermagic7.2 power2. Fonte/config/Image/vmlinux.symvers preservados.44 inputs conferidos por digest tanto na VM quanto localmente. O aviso esperado da raiz sem Module.symvers permanece; exports são fornecidos explicitamente, sem KBUILD_MODPOST_WARN ou permissão para símbolos não resolvidos. Após corrigir preservação do primeiro erro/readiness na revisão, apenas os gates afetados e o build completo foram repetidos. Logs/módulo privados não foram publicados.

### Plano, limites e próximo desenvolvimento

F1b/F1c offline concluídos; nenhuma mudança de banco, dependência ou pacote/configuração global no Mac. Default/autoload/perfil físico anterior permanecem; não houve novo boot/DFU/PIN nem prova nova de SSH/HTTP/carga nesta rodada. O custo é retenção de uma struct/MMIO/node e owners até cleanup; cada tentativa de restauração permanece limitada a16 words e snapshots estáveis.

F0/F1 globais, F2 seleção/perfil e F3 hardware continuam abertos. Antes de carregar a candidata, fechar ownership IRQ e máscara/restore: consultar mapping antes de criar não constitui aquisição atômica. Na [fonte fixada do IRQ core](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/irq/chip.c#L981), handler NULL pode executar mask_ack_irq; portanto alloc/free não pode ser declarado sem efeitos físicos. Preparar collector/provenance e reunir os gates numa sessão física, preservando serviços/snapshot/sync/retorno iOS. [Decisões D3/D4](../.agents/plans/n71-irq-iommu-bindings.md#d3-reter-o-provider-dart-e-seu-rollback-na-sessão-nativa), issue40; Wi-Fi#9 e energia#2 continuam pendentes.

## F1d/F1e/F1f — IRQ exclusiva e caller completo qualificados

[Prova sanitizada](evidence/n71-dart-irq-qualification.json), código53c70ea/6b4d8a3/71663be. Este checkpoint atualiza os limites de ownership da fatia anterior. [IRQ nativa](../phone/kernel/n71-dart-irq.h): um domínio privado abaixo do AIC, fwnode próprio e referência OF retida. No callback alloc, lookup do parent e sua alocação ocorrem sob o mesmo root mutex do IRQ core; mapping já existente é recusado e não é reutilizado/disposto. Validamos cells0/248/4, hwirq100f8, root hierárquico e chipAIC. Falhas parciais conservam owner para cleanup.

O [provider](../phone/kernel/n71-dart-provider.h) remove o dispositivo antes de liberar a IRQ. Release recusa action, started, enabled ou unmasked, identidade divergente e domínio não vazio; mantém os recursos quando a recuperação ainda depende deles. `dart-hold`, `dart-release`, nova aquisição e retry podem ocorrer no mesmo scan/session. Getter inclui `irq_domain` e `irq_fwnode`; getters anteriores mantêm seu formato.

### Baseline de máscara e limite da prova

[AIC init](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/irqchip/irq-apple-aic.c#L1076) mascara inicialmente todas as IRQs. O [IRQ descriptor](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/irq/irqdesc.c#L131) nasce disabled/masked. O [core de alocação](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/irq/irqdomain.c#L1710) serializa callbacks e publicação dos mappings pelo root mutex. Esses fatos sustentam a baseline derivada da fonte e o protocolo do owner exclusivo. Os flags do descriptor e o modelo de máscara não são readback físico do AIC; nenhum acesso a SET/CLR foi acrescentado para presumir leitura válida. Free pode mascarar hardware. A coordenação depende do teardown do dispositivo e do owner privado, sem alegação de segurança contra usuários arbitrários do virq.

### Verificação realizada

| Gate | Mac e Ubuntu ARM64, por plataforma |
|---|---|
| Callbacks IRQ de produção |37 cenários/21 mutações compiladas por asserção |
| Backend provider de produção |27/14; sucesso temporário conserva frames e contadores |
| Cleanup extraído do caller |4/3; header gerado termina em newline |
| Caller completo de produção |143/89; inclui22 cenários DART, mantém73 probe/21 held/27 resource |
| Total |211 cenários/127 mutações; SIGABRT e texto de asserção obrigatórios |
| C/kernel |Werror; módulo completoW=1/modpost/ELF64 AArch64/vermagic power2 |
| Python |AST e lint fatal passaram; sem typechecker Python no projeto |

As fixtures exercitam os callbacks e owners reais com dependências kernel rastreadas. O backend DART no caller completo é um stub de recursos; o gate separado executa o provider real. Não são provas de entrega de IRQ, MMIO, DMA ou rádio. No ARM64,64 cenários/35 mutações IRQ/backend foram reutilizados com todos os inputs pertinentes intactos; caller e cleanup147/92 foram repetidos. A mudança do Python do provider foi exclusivamente a newline do header extraído, conferida literalmente.50 inputs finais têm o mesmo manifest no Mac/VM;38 inputs de produção correspondem ao módulo já compilado.

O módulo privado final tem95.512 bytes/SHA13ff0388800bccfa505e2236e70a93ece4cbedd4a6760ead09ffc3d98a5fd8ac. Fonte/config/Image/vmlinux.symvers permanecem nos hashes fixados; sem KBUILD_MODPOST_WARN, load ou composição de perfil. O aviso esperado de Module.symvers ausente na raiz permanece com exports explícitos. O primeiro build falhou por constness de fwspec: corrigimos usando cópia local mutável. O preflight confundiu metadados gerados pelo make com fontes; corrigimos sua classificação e conferimos38 fontes, Makefile e módulo separadamente, sem rebuild desnecessário.

### Regressão de CI e timeout preservados

A [CI de4739cb5](https://github.com/djalmajr/iphone6s-linux/actions/runs/37558331536) falhou por newline ausente no header extraído e APIs/tipos DART ausentes na fixture do caller completo. Ambas foram corrigidas mantendo Werror. Não confundir essa regressão determinística com a intermitência anterior da [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38), que permanece aberta. A CI do novo head precisa terminar para haver prova remota.

O primeiro caller ARM64 teve timeout numa mutação, que passou isoladamente em1,631s. A VM usa Apport por core_pattern piped; a [fonte Linux](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/fs/coredump.c#L984) confirma que RLIMIT_CORE não impede pipes. A fixture desabilita dumpability somente no processo C Linux para evitar handlers externos. O gate completo corrigido passou sem aumento de timeout, sysctl ou configuração de máquina. O vínculo do timeout com Apport permanece uma hipótese; logs e manifest da falha foram preservados, e ela não foi contada como mutation kill.

### Reprodução e próximos passos

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_dart_irq.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_dart_provider.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_diagnostic_caller.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_dart_irq.py tests/test_n71_dart_provider.py tests/test_n71_pcie_diagnostic_caller.py
```

O build externo usa uma pasta M nova, os38 inputs de produção registrados no JSON, Makefile com `obj-m += n71-pcie-diagnostic.o` e o comando make já documentado acima. Compare todos os hashes antes/depois. Nenhuma dependência, banco ou pacote/configuração global do Mac mudou; logs, módulo e firmware permanecem privados. Custo adicional: domínio/fwnode/virq e referência OF por owner DART até release comprovado; desempenho físico não medido.

F1d/F1e/F1f locais concluídos; F0/F1 globais, F2 perfil/collector e F3 físico permanecem abertos. Próximo desenvolvimento: mensagem/domínio MSI e lifecycle das máscaras, attachment PCI/IOMMU e política de enable, depois collector/perfil por SHA e um boot agrupado. Wi-Fi e carga/gauge ainda não funcionam nesta candidata. Nenhum novo reboot/DFU/PIN nesta rodada; iPhone detectado no iOS para carregar enquanto o trabalho offline avança. O goal e as issues40/9/2 permanecem ativos.

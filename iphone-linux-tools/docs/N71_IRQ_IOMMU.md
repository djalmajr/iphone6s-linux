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

O ADT N71 fixado declara `msi-address=0xbffff000`, `msi-vector-offset=256`, total32 e parent AIC phandle0x16 (22). A bridge1 declara base8/count8. O driver Apple lê essas propriedades e acrescenta o offset do controlador ao índice lógico ao publicar a interrupção no parent: os números AIC de registro são264..271. Isso é referência estática, não entrega de IRQ no Linux. A referência do **message data** foi inferida na F1g abaixo; entrega e mensagem física permanecem sem prova. Não confundir o índice lógico8 com o número AIC264.

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

A [CI de4739cb5](https://github.com/djalmajr/iphone6s-linux/actions/runs/37558331536) falhou por newline ausente no header extraído e APIs/tipos DART ausentes na fixture do caller completo. Ambas foram corrigidas mantendo Werror. Não confundir essa regressão determinística com a intermitência anterior da [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38), que permanece aberta. A [CI de19ffb03](https://github.com/djalmajr/iphone6s-linux/actions/runs/37566057928) passou nos três jobs após a correção da issue41; essa prova antecede a implementação MSI nativa abaixo.

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

## F1g — referência da mensagem MSI, sem integração física

O [helper](../phone/kernel/n71-wlan-msi-message.h), commit0c1fbe5, exige a topologia N71 já qualificada, address_lo0xbffff000/high0 e controller vectorBase0. Produz três words da mensagem e a requisição AIC em campos separados. Os oito dados esperados são8..15; os números parent AIC são264..271. Endereço/base/topologia divergentes ou índice fora da porta são recusados com EINVAL/ERANGE e output intacto. Não cria IRQ/domain, não escreve config/MMIO e não foi ligado ao caller/perfil/autoload.

### Referência primária e incerteza explícita

[Nove recortes por hash/offset](evidence/n71-msi-message-reference.json), binário/ADT já fixados e privados. A factory N71 de216 bytes aponta ao allocator tipado; o import resolve para OSObject_typed_operator_new, cujos flags de zone são0xd1004. O [header oficial anterior8020.140.41](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/osfmk/kern/zalloc.h) identifica bit0x4 como Z_ZERO e0x1000 como VM tag. O tag exato8020.241.44 retornou404 na API oficial e não foi usado como fonte. O caminho completo de zeroing do binário não foi fechado; portanto vectorBase0 permanece inferência pela comparação e init que não grava esse campo, sem claim de leitura física da memória inicial.

A [fonte IOPCIFamily fixada](https://github.com/apple-oss-distributions/IOPCIFamily/blob/4822b27a36e2de70e231ecf2bf3021384fab6ec2/IOPCIMessagedInterruptController.cpp#L501) separa firstVector + _vectorBase do registro parent. O binário soma o campoA0 ao firstVector para o argumento de mensagem; a bridge copia esse argumento do x5 para o terceiro word, enquanto o offset de registro256 reside emC4. A propriedade ADT fornece o endereço0xbffff000. Esse encadeamento sustenta os valores de referência; ainda não prova entrega MSI, máscara, firmware ou DMA.

### Verificação e reprodução

[Qualificação sanitizada](evidence/n71-wlan-msi-message-qualification.json):30 cenários/13 mutações compiladas e detectadas por SIGABRT/asserção no Mac e Ubuntu ARM64. O teste cobre oito mensagens, endereços/high/base recusados, seis topologias, índices adjacentes/extremos, nulos, erro combinado e preservação de output. A primeira fixture não incluía stdbool para mutants com false; a falha de compilação foi corrigida e não contada como kill. O processo da fixture Linux desabilita dumpability para evitar handler externo de crash, sem mudar configuração da máquina.

Quatro inputs idênticos por SHA; helper AIC anterior permanece intacto e seus gates são reutilizados. C11/Wall/Wextra/Werror/pedantic, AST/lint fatal passaram; sem typechecker Python. Probe ABI na VM passou W=1/Werror/modpost/ELF64 AArch64/vermagic power2,5.736 bytes/SHAe0abf356ebe8b42f2050c320f8caa310e940e876b84ce6f90c0f09cb064dca06, sem load. Fonte/config/Image/vmlinux.symvers preservados, exports explícitos e sem KBUILD_MODPOST_WARN. Esse probe valida contexto kernel do helper; não implementa domínio MSI.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_wlan_msi_message.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_wlan_msi_message.py
```

Para ABI, crie pasta M nova na VM e copie os dois headers registrados no JSON; crie módulo GPL de prova que chame n71_wlan_msi_message no init com os valores N71 e Makefile `obj-m += n71-wlan-msi-abi-probe.o`. Compile pelo comando make já documentado, confira hashes/ELF/vermagic e conserve o probe privadamente, sem executá-lo. Para conferir a referência binária, use o procedimento Python dos recortes acima com o novo JSON e seus nove source_windows. Firmware, bytes e disassembly não foram publicados.

Nenhum pacote/configuração global, banco, dependência ou estado físico foi alterado. Custo: cálculo e structs locais, sem recurso persistente; desempenho físico não medido. F1g offline concluída e pronta para o domínio nativo; CI do código IRQ/caller e publicação final seguem registradas no plano. Próximo desenvolvimento: bitmap/alocação exclusiva dos oito parents MSI com rollback, máscaras/teardown, attachment PCI/IOMMU e enable controlado. Wi-Fi/carga/gauge e goal continuam pendentes; não houve novo boot/DFU/PIN.


## F1h — domínio MSI nativo isolado

[Implementação](../phone/kernel/n71-wlan-msi-native.h), commit295c7c2, [plano D7](../.agents/plans/n71-irq-iommu-bindings.md#d7-próxima-fatia-domínio-msi-nativo-e-rollback-de-vetores) e [prova sanitizada](evidence/n71-wlan-msi-native-qualification.json). Um domínio MSI-parent privado abaixo do AIC retém fwnode e referência OF; usa as APIs modernas exportadas do kernel fixado. Somente MSI/multi-MSI, com oito slots e grants alinhados de1/2/4/8. MSI-X é recusado. Não usa os helpers de bitmap não exportados nem offsets da bridgeM1.

Lookup e parent alloc compartilham o root mutex. Mappings externos são recusados, sem reuso ou dispose. Cada falha parcial de parent/set-leaf libera o que foi adquirido, preservando outros grants e permitindo retry. A tradução de todas as oito células exige `<0,264+índice,1>` e hwirq10108+índice. [AIC alloc](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/irqchip/irq-apple-aic.c#L751) traduz o tipo mas não o salva; MSI é implicitamente edge nesse chip. O callback mantém os flags compartilhados do IRQ core em edge, sem declarar configuração/readback físico do trigger.

### Lifetime do filho e liberação por vetor

O [core fixado](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/irq/irqdomain.c#L1604) chama free separadamente por vetor, inclusive após alloc multi-MSI. O owner libera apenas aquele bit, faz reset e free do parent; não arredonda a liberação para a região original. A fixture comprova liberar um vetor no meio de oito, reutilizar esse slot e preservar os restantes.

[PCI mantém o domínio por dispositivo](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/msi/irqdomain.c#L235) após desativar MSI. Portanto bitmap/mapcount zero não basta. Prepare/teardown mantêm a identidade do único filho WLAN e do dispositivo; descriptor de outro dispositivo e filho duplicado são recusados. Release recusa o filho vivo, mesmo sem IRQs. [Teardown do core](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/irq/msi.c#L1113) roda antes de remover o domínio filho. O futuro consumidor precisa excluir criação/teardown concorrentes com release, remover/quiescer PCI e soltar referências antes de liberar o owner. Esse requisito ainda não foi integrado ao caller; não há claim de exclusão contra usuários arbitrários do domínio.

Compose utiliza a referência qualificada: address0xbffff000/high0 e dados8..15, separados dos parents AIC264..271. Domínio/grant/índice inválidos resultam em mensagem zero. VectorBase0 continua inferência estática descrita na F1g; entrega MSI real e máscara/restore permanecem gates físicos.

### Verificação, reprodução e limites

| Gate | Resultado por plataforma |
|---|---|
| macOS e Ubuntu ARM64 |1132 cenários e45 mutações compiladas por assertion |
| Propriedade do allocator |256 máscaras × quatro tamanhos =1024 combinações; alinhamento/overlap/preservação |
| Falhas |Conflito em cada parent, prefixo parcial de alloc, chip/domain/hwirq divergentes, set-leaf, retry |
| Lifetime |Filho sem vetores impede release; cleanup constructor, free de identidade/grant inválidos, release idempotente |
| C/Python |gnu11/Wall/Wextra/Werror, AST nos dois ambientes, lint fatal no Mac; sem typechecker Python |
| Kernel |W=1/Werror/modpost, ELF64 AArch64/vermagic power2; fonte/config/Image/exports intactos |

Cada mutant precisa compilar e falhar por SIGABRT com texto de asserção. Import/compiler/timeout não são kills. Seis inputs idênticos por SHA; helpers anteriores intactos, sem repetir seus gates. Core/OF/MSI library são modelos de dependências; callbacks de produção executam diretamente. Não são provas de entrega física, DMA, concorrência global ou carregamento do domínio no kernel do iPhone.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_wlan_msi_native.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_wlan_msi_native.py
```

Para ABI, crie pasta M nova na VM e copie os três headers phone/kernel registrados no JSON. Faça um módulo GPL com funções globais, previamente declaradas, que chamem acquire/release com os mesmos argumentos; essas funções conservam os callbacks e dependências exportadas no objeto. Seu init retorna `-EOPNOTSUPP` e exit é vazio, impedindo uso como módulo funcional. Makefile: `obj-m += n71-wlan-msi-native-abi-probe.o`. Compile com o comando make e exports já documentados; confira SHA dos inputs/baselines, ELF e vermagic. O probe privado tem13136 bytes/SHAd6ce0910ccafe7375ef8bbaab842134f7a64319311b9b717a315bb1921a0ce44; não foi carregado ou publicado.

F1h offline concluída. Nenhuma dependência, banco, pacote/configuração global do Mac ou estado do telefone mudou; nenhum novo DFU/boot/PIN. Custo adicional: oito bits de grant, identidade de filho/dispositivo e um domínio/fwnode/OF ref até teardown. Desempenho físico não medido. CI19ffb03 passou antes deste código e encerrou a issue41; a [CI da F1h/fcb1326](https://github.com/djalmajr/iphone6s-linux/actions/runs/37568094109) passou nos três jobs em2026-10-07T03:54:41Z. Próximo: associação MSI ao PCI e attachment DART, owners/pins/cleanup e guards antes de enable/MASTER, depois collector/perfil para uma sessão física agrupada. Wi-Fi#9, energia#2, issue40 e goal continuam abertos.


## F1i — lease da associação MSI ao host PCI

[Helper](../phone/kernel/n71-wlan-msi-host.h), código0abc339, [prova sanitizada](evidence/n71-wlan-msi-host-qualification.json) e [decisão D8](../.agents/plans/n71-irq-iommu-bindings.md#d8-lease-da-associação-msi-antes-do-primeiro-scan). Acquire exige bridge sem bus e sem domínio preexistente. Retém a identidade do owner, salva a flag msi_domain anterior, chama o owner nativo e só então associa o domínio à bridge. Assim, a integração futura pode usar a [herança normal do PCI](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/probe.c#L930), antes da enumeração.

Release recusa bus vivo ou associação/flag divergentes. Depois da [remoção do root bus](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/remove.c#L161), desfaz exclusivamente a associação própria e restaura a flag anterior antes de pedir a liberação nativa. Filho MSI ainda referenciado ou erro de teardown mantém a lease/bridge para retry, já sem associação. Não repete cleanup nativo após sucesso. O futuro caller precisa reter bridge/módulo e serializar scan/teardown/release; o helper não toma essas referências automaticamente. Ainda não está ligado ao scan/caller/perfil.

O [matching PCI](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/pci-driver.c#L1536) verifica PCI_DEV_ALLOW_BINDING. O [estágio pci_bus_add_device](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/bus.c#L370) libera esse guard e inicia probe; o diagnóstico atual não o chama e nega enable_device. Contudo [device_add ocorre durante scan](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/probe.c#L2763), notificando IOMMU. Attachment DART precisa respeitar essa publicação e o teardown de consumidores antes do provider, antes de liberar driver/MASTER. Associação MSI não prova nem libera DMA.

### Verificação e reprodução

Mac e Ubuntu ARM64 passaram21 cenários/22 mutações compiladas por assertion cada: dois valores prévios da flag, erros parciais de acquire, owner duplicado, bus vivo, domínio alheio, associação/flag alteradas, filho retido, falha de cleanup, retry e idempotência. Cgnu11/Wall/Wextra/Werror, AST nos dois ambientes e lint fatal Mac passaram. Não há typechecker Python. Sete inputs idênticos por SHA; gates do owner MSI real foram reutilizados com inputs intactos. As dependências PCI/native lease do teste host são modelos; não equivalem a execução do core no aparelho.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_wlan_msi_host.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_wlan_msi_host.py
```

Probe ABI composto com os quatro headers phone/kernel registrados no JSON: funções globais previamente declaradas chamam n71_wlan_msi_host_acquire/release; init retorna `-EOPNOTSUPP`, exit vazio. Makefile `obj-m += n71-wlan-msi-host-abi-probe.o`, pasta M nova e o make/exports já documentados. W=1/Werror/modpost/ELF64 AArch64/vermagic power2 passaram. Fonte/config/Image/vmlinux.symvers intactos. Probe privado13400 bytes/SHA6980b4d0501478cfbff7899574c35d6b1fedb2127dc824f98ce734f4a8d508b2, não carregado/publicado.

F1i offline concluída e [CI de cdb0395](https://github.com/djalmajr/iphone6s-linux/actions/runs/37569239640) aprovada nos três jobs em2026-10-07T04:08:24Z. Essa prova antecede a integração ao scan abaixo. Não houve dependência, banco, pacote/configuração global do Mac, novo boot/DFU/PIN ou escrita no telefone. Custo: identidade da bridge, flag salva e owner nativo embutido até release; desempenho físico não medido. Próximo: F1j liga a lease antes do scan com opt-in/guard/getter/cleanup e fixtures do caller. Wi-Fi#9, energia#2, issue40 e goal continuam abertos.


## F1j — herança MSI durante o scan PCI

[Scan](../phone/kernel/n71-pcie-scan.h), código36998e8, [plano D9](../.agents/plans/n71-irq-iommu-bindings.md#d9-associar-msi-antes-do-scan-preservando-o-diagnóstico-padrão), [prova sanitizada](evidence/n71-msi-scan-qualification.json). O host incorpora a lease MSI. Options internos exigem held bus e PME preparado para MSI; wrappers existentes permanecem MSI-off. O novo hold_msi prepara o parent OF, equilibra referências temporárias e conclui acquire/associação antes do core scan. Nesta fatia ainda não havia parâmetro de seleção ou getter MSI no caller; F1k abaixo os acrescenta.

Report confere a identidade do domínio na bridge, root bus, root port, child bus e endpoint; divergência é recusada. Guard de driver/MASTER e enable negado permanecem. Não acrescenta bind, IRQ alocada ou DMA. Cleanup remove o bus antes de liberar a lease. Filho ainda referenciado/erro nativo retém bridge/config/resources/power e impede restauração antecipada; retry usa a mesma sessão sem rescan.

### Gates e reprodução

Mac e Ubuntu ARM64:152 cenários/117 mutações compiladas por assertion por plataforma. Scan79/69 conserva os29 casos de scan,16 held bus e20 resource, além de14 MSI; optional18/14, IO1620/17 e PREF6435/17. A nova fixture MSI modela core inheritance/OF/native release; scan, report, host lease e cleanup são produção. Os callbacks MSI nativos mantêm seus gates separados, reutilizados com fonte intacta. Sem typechecker Python; AST e lint fatal passaram no Mac, AST também no ARM64.

Duas mutações skip-call iniciais falharam na compilação por função unused. Não contam como kills. Os selectors mantêm agora uma referência não avaliada à função, preservando Werror; o método MSI passou por SIGABRT/asserção nos dois ambientes. Três métodos antigos aprovados (baseline e57 mutações) e compile helper foram reutilizados por hash/AST idênticos, junto dos54 outros inputs intactos; somente o método MSI corrigido foi repetido. Optional/IO16/PREF64 foram executados por compartilharem o C alterado. Nenhum prazo ou critério foi enfraquecido.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_scan_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_optional_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_io16_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_pref64_host.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_pcie_scan_host.py
```

Build completoW=1/Werror/modpost/ELF64 AArch64/vermagic power2 passou.55 inputs protegidos:46 C/headers arquivados e nove testes, dos quais30 arquivos de produção são includes efetivos do objeto. A cópia de build do caller contém um wrapper global privado que chama hold_msi e mantém a nova rota no objeto, pois o caller público ainda usa os wrappers padrões. SHA288ae87c8c43ee67d732d8e7c4f11f7e696cbe73c0d5f504f0c8ae2c49408819,102888 bytes; esse probe não é o futuro artefato físico selecionado. Fonte/config/Image/vmlinux.symvers preservados, exports explícitos, sem KBUILD_MODPOST_WARN, load ou publicação do módulo/logs.

Para reproduzir ABI, use pasta M separada com os arquivos phone/kernel do JSON e Makefile `obj-m += n71-pcie-diagnostic.o`. Na cópia privada de n71-pcie-diagnostic.c, acrescente declaração e função global n71_msi_scan_probe(device,state) que retorna n71_pcie_scan_hold_msi(device,state). Use make/exports fixados já documentados, confira todos os hashes, ELF/vermagic e mantenha o probe privado, sem insmod. O primeiro parser de includes buscou paths absolutos e retornou zero; corrigimos por basenames e conferimos as30 dependências, sem rebuild.

F1j offline concluída e [CI de0ae5922](https://github.com/djalmajr/iphone6s-linux/actions/runs/37572779793) aprovada nos três jobs em2026-10-07T04:54:34Z. Essa CI antecede a seleção pelo caller da F1k. Nenhuma dependência, banco, pacote/configuração global do Mac, novo boot/DFU/PIN ou escrita no telefone. O campo lease é interno ao módulo; perfil anterior não foi alterado. Custo adicional: conferências de identidade por dispositivo e lease retida até cleanup; desempenho físico não medido. Próximo: F1k seleciona a rota/getter no caller e qualifica seu lifecycle; attachment DART, collector/perfil e física continuam antes de rádio funcional. Wi-Fi#9, energia#2, issue40 e goal permanecem abertos.

## F1k — seleção MSI e estado recuperável no caller

[Caller](../phone/kernel/n71-pcie-diagnostic.c), códigoe65c709, [decisão D10](../.agents/plans/n71-irq-iommu-bindings.md#d10-selecionar-msi-no-caller-e-expor-ownership-sem-mudar-o-perfil-físico), [prova sanitizada](evidence/n71-msi-caller-qualification.json). Parâmetro msi_parent default false/0400; exige scan_hold e os guards anteriores de PME/host_scan/inventory/enumerate. MSI sem hold é recusado antes do registro do driver. Somente o opt-in seleciona hold_msi. Nenhuma mudança de perfil ou autoload nesta fatia; não executar insmod como parte da reprodução offline.

O getter msi/0400 usa session_lock e mantém os formatos anteriores intactos. requested indica a opção solicitada; ready indica sessão existente; held exige bus vivo/retido. associated é o estado da associação salva pelo owner, e owner/domain indicam a lease e o parent privado retidos. mappings é mapcount desse domínio privado; child indica filho MSI ainda retido. session_error é cleanup_error da sessão inteira, podendo continuar negativo depois de a lease MSI ter sido liberada. Esses campos não provam entrega IRQ, identidade física da máscara, attachment DMA ou rádio.

Falhas de acquire ou teardown deixam a bridge/pin do módulo/reset/power retidos. O getter diferencia owner pendente de bus já removido. Depois de quiescer a dependência, action=cleanup tenta novamente na mesma sessão sem rescan nem put duplicado. Provider DART ainda é removido antes do PCI na rota atual sem attachment/DMA; essa ordem precisa mudar antes de habilitar consumidores DMA.

### Gates e reprodução

Mac e Ubuntu ARM64 passaram156 cenários/103 mutações compiladas por assertion por plataforma. São143 cenários antigos e13 MSI;89 mutações antigas e14 MSI. Cobertura inclui default, guard antes de efeitos, seleção, campos exatos sob lock, mapping/filho pendente, erro parcial, retry e erro de reset após release. Caller/init/probe/getters/actions/cleanup e MMIO executam produção; PCI/MSI/kernel APIs são dependências modeladas. Gates nativos de scan/MSI permanecem separados e foram reutilizados com seus inputs intactos.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_diagnostic_caller.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_pcie_diagnostic_caller.py
```

Não há typechecker Python; AST/lint fatal passaram no Mac e AST no ARM64. Os dois corpos de produção extraídos pelo gate de cleanup DART estão idênticos por hash; reutilizamos seus quatro cenários/três mutações anteriores. A fixture de caller atual executou seu gate completo uma vez por ambiente. Sem falhas de compile/assertion nessa rodada; nenhum prazo enfraquecido.

ProduçãoW=1/Werror/modpost/ELF64 AArch64/vermagic power2 passou.48 inputs protegidos,46 C/headers arquivados,30 includes efetivos. A pasta M usa cópias exatas da produção e Makefile `obj-m += n71-pcie-diagnostic.o`; agora não há wrapper privado. Use o make/exports fixados descritos anteriormente e confira fonte/config/Image/vmlinux.symvers antes/depois. modinfo confirma msi_parent/msi e nm confirma o getter e a API nativa retida. Módulo104288 bytes/SHA0c0783806158eb88a4bc390644a3186d474d1fe20d2026a046719751f875f8a5; não carregado nem publicado. Image/config/exports preservados, sem KBUILD_MODPOST_WARN.

F1k offline concluída e [CI de2192cbe](https://github.com/djalmajr/iphone6s-linux/actions/runs/37573824732) aprovada nos três jobs em2026-10-07T05:06:28Z. Sem banco, dependência, pacote/configuração global do Mac, novo boot/DFU/PIN ou escrita no telefone. Custo adicional: getter sob lock e seleção opt-in; desempenho físico não medido. Próximo: associação PCI/DART antes de device publication/binding/MASTER, teardown de consumidores antes do provider, collector/perfil e preparação de energia para coletas agrupadas. Wi-Fi#9, carga/gauge#2, issue40 e goal permanecem abertos.

## Disponibilidade OF do DART antes da associação

[Auditoria sanitizada](evidence/n71-iommu-of-lifetime-audit.json), [próximo contrato D11](../.agents/plans/n71-irq-iommu-bindings.md#d11-preparar-a-associação-ofdart-com-rollback-observável). Na fonte fixada, [of_iommu_xlate](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/iommu/of_iommu.c#L28) recusa o nó com status disabled antes de iniciar fwspec. A topologia atual mantém esse status para controlar o probe. Ter o provider manual registrado e bound, portanto, não basta para associar PCI/DART.

Tornar o nó disponível aciona o [notifier OF](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/of/platform.c#L726): OF_POPULATED evita criação duplicada; ao desativar um nó populado, o notifier pode remover o platform device correspondente. O próximo owner precisa proteger o provider manual e seus consumidores durante essas transições. A ordem proposta é remover consumidores PCI, desfazer o mapa do host, parar o provider manual e restaurar status/flag; ainda não foi implementada nem provada no aparelho.

Há outro limite na API: [apply](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/of/dynamic.c#L767) pode retornar erro de notify depois de aplicar as propriedades. Um retorno negativo não garante que a árvore foi restaurada. É necessário conferir identidade/readback e manter owner/refs para retry quando houver efeitos vivos. [Destroy](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/of/dynamic.c#L533) libera entries e referências, sem liberar a propriedade dinâmica retida pela árvore; não usar propriedade embutida em um owner que será liberado nem declarar todo o heap recuperado.

As APIs changeset e helpers de propriedades estão exportados no kernel fixado. CONFIG_OF_DYNAMIC/OVERLAY estão habilitados e o domínio default é DMA strict. [SID0 da referência N71](evidence/n71-dart-apple-stream-reference.json) continua sendo a entrada para o mapa restrito; máscaras/aliases precisam ser conferidos antes de permitir DMA. A auditoria preservou fonte/config/Image/exports e não aplicou mudanças OF, não carregou módulos nem pediu outro DFU. D11 abaixo qualifica o helper isolado; integração do caller e prova física continuam pendentes na issue40.

## Referência DART na DTB desativada

[Preparador](../scripts/build/prepare-n71-topology.py), [D12](../.agents/plans/n71-irq-iommu-bindings.md#d12-gerar-primeiro-um-phandle-dart-estável-na-dtb-desativada), [prova sanitizada](evidence/n71-dart-phandle-qualification.json). A topologia anterior não referencia o label DART e sua delta exige exatamente os campos sem phandle. Antes do helper de associação, o novo modo `--dart-phandle` reserva um identificador válido e exclusivo, igual ao maior phandle da baseline mais um. Pins da baseline continuam intactos; dtc aloca os providers novos em outros números.

O modo default continua sem phandle DART ou novo campo de provenance. Opt-in admite somente o phandle reservado no DART, registra seu valor e recusa overflow, baseline inválida, colisão/drift, status ativo, mapa IOMMU ou qualquer outra alteração. UART/DART/PCIe permanecem desativados. Isso prepara uma referência para o mapa futuro, sem ativar provider, DMA ou rádio.

Mac: 16 testes passaram, cinco testes de compilação nativa foram pulados e 13 mutações falharam por assertion. Ubuntu ARM64: todos os 21 testes e 15 mutações passaram, incluindo GCC/dtc reais e opt-in, em 23,528 segundos. Mutantes precisam de `FAIL` do unittest, sem `ERROR`; import/compile/runtime não contam como kills. AST e lint fatal passaram no Mac; AST também no ARM64. Não há typechecker Python.

```sh
python3 -B tests/run_n71_topology_mutations.py
IPHONE_N71_VM_SOURCE=/CAMINHO/FONTE_LIMPA python3 -B tests/run_n71_topology_mutations.py
python3 -B scripts/build/prepare-n71-topology.py \
  --source-dir /CAMINHO/FONTE_LIMPA \
  --reference /CAMINHO/REFERENCIA_N71.json \
  --output-dir /CAMINHO/SAIDA_NOVA --dart-phandle
```

A fonte de binding original tem seis alterações tracked de DART/GPIO/power/serdev. Para este build usamos uma cópia Git sparse limpa e separada do commit fixado, com arch/arm64/boot/dts e include. O hash do diff original foi preservado, junto de config/Image/vmlinux.symvers; não fizemos reset, rebuild da Image ou instalação. A referência JSON deve corresponder ao contrato já documentado do preparador, sem nova extração de firmware.

CLI default e opt-in geraram DTBs reais com a mesma baseline. Phandle DART41 na candidata qualificada; SHA797275305a2bc5fdf49b8639075a8ac46768f8ea1de80fa682ebe460288341bd. DTBs/logs ficam privados. [CI de22031b8](https://github.com/djalmajr/iphone6s-linux/actions/runs/37575497590) aprovada nos três jobs em2026-10-07T05:28:11Z. Não houve composição, seleção de perfil, load, novo boot/DFU/PIN ou escrita no telefone. Nenhuma dependência, banco ou configuração global do Mac mudou; custo de runtime não medido. D11 abaixo qualifica o helper; integração/collector e física agrupada continuam pendentes. Wi-Fi#9, energia#2, issue40 e goal permanecem abertos.

## D11 — lease OF recuperável para o host DART

[Helper](../phone/kernel/n71-dart-host.h), códigoa042c8b, [plano D11](../.agents/plans/n71-irq-iommu-bindings.md#d11-preparar-a-associação-ofdart-com-rollback-observável), [prova sanitizada](evidence/n71-dart-host-qualification.json). Prepare valida N71, bridge sem bus, parent/nós fixos, provider manual bound/único, status disabled original e phandle/células. Recusa propriedades IOMMU e flag de população preexistentes. Retém devices/nodes e publica owner antes de alocações/efeitos; duas changesets de uma entry cada disponibilizam o provider e acrescentam o mapa do parent. O mapa contém somente RID0x0008 e RID0x0100, SID0 e length1 por entrada.

O caller deve serializar o lifecycle e manter o módulo. Unmap recusa bus vivo, reverte somente o mapa próprio e conserva disponibilidade/refs. Release recusa qualquer provider registrado para o nó; o caller deve pará-lo depois da remoção dos consumidores e do unmap. Só então são restaurados status disabled e flag própria. A última referência da bridge pode liberar o priv: o helper copia as refs e zera o owner antes dos puts. Ainda não está integrado ao scan/caller, não verifica aliases runtime e não configura domínio DMA.

Apply/revert podem falhar depois de efetivar a propriedade. Identidade e readback distinguem original/próprio/alheio; owner permanece em erro/drift e retry reconhece uma etapa já restaurada sem repetir revert. Não remove provider alheio. Destroy libera entries/refs, sem liberar manualmente properties retidas pela árvore ou alegar todo o heap recuperado.

### Gates e reprodução

Mac e Ubuntu ARM64 passaram49 cenários/38 mutações compiladas por assertion cada. Cobrem guard antes de efeitos, refs enquanto bridge/provider perdem refs de registro, mapa big-endian exato, duplicação de provider, falhas de queue/apply/revert antes e depois dos efeitos, readback divergente, consumidores vivos e retry. Os callbacks prepare/unmap/release são produção; dependências OF/PCI/device são modeladas. Mutantes precisam compilar com Werror e falhar por SIGABRT/asserção; timeout, erro de import, compilação e selector ambíguo não contam como kills.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_dart_host.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_dart_host.py
```

Na primeira execução houve oito erros de compilação em selectors e uma ambiguidade, sem contá-los como kills. Selectors foram corrigidos e repetidos seletivamente, com logs privados preservados. O primeiro probe ABI detectou falta de include linux/of_platform.h; corrigimos a dependência explícita e repetimos o gate completo nos dois ambientes. A evidência final contém49/38 novos por plataforma, sem reutilizar resultados de execuções com falha. AST/lint fatal passaram no Mac e AST no ARM64; não há typechecker Python.

Para reproduzir ABI, use pasta M separada com o header exato e Makefile `obj-m += n71-dart-host-probe.o`. O probe inclui linux/module.h e n71-dart-host.h, mantém owner estático e três wrappers globais com prototypes que chamam prepare(owner,request), unmap(owner) e release(owner). module_init retorna -EOPNOTSUPP e module_exit é vazio; licença GPL. O probe é somente de compilação: nunca executar insmod. Use make/exports fixados descritos acima, W=1/KCFLAGS=-Werror, sem KBUILD_MODPOST_WARN, e confira hashes antes/depois.

Build/modpost/ELF64 AArch64/vermagic power2 passaram. Módulo11456 bytes/SHAe7bf28e5cede9bf1fad52be38b3ea468af4b6b7b2140bbc265fb5221adbcc634; source/config/Image/vmlinux.symvers e as seis alterações tracked da fonte original foram preservados. Header/fixture/C/Python correspondem aos quatro hashes da prova. Módulo e logs privados, sem load.

[CI de04ae283](https://github.com/djalmajr/iphone6s-linux/actions/runs/37578130334) concluída nos três jobs em2026-10-07T05:59:44Z. Essa CI prova a publicação do helper D11; a extração D13 foi publicada depois e tem sua CI própria, ainda pendente nesta atualização.

Arquivos desta fatia: helper, fixture OF/device, cenários C, runner Python e plano; documentação/prova publicadas separadamente. Sem API/perfil físico alterado, dependência, banco ou configuração global do Mac. Custo: refs e duas changesets durante a lease, properties dinâmicas retidas pelo core; desempenho físico não medido. Próximo: integração pré-scan e cleanup consumidores → mapa → provider → disponibilidade → config/resources/bridge/reset/power. Driver/MASTER, aliases/máscaras, entrega IRQ/DMA, rádio e alimentação permanecem gates abertos. Wi-Fi#9, energia#2, issue40 e goal continuam ativos.

## D13 — remover consumidores conservando o host

[Scan](../phone/kernel/n71-pcie-scan.h), código269c1c9, [decisão D13](../.agents/plans/n71-irq-iommu-bindings.md#d13-separar-remoção-de-consumidores-da-restauração-do-host-pci), [prova sanitizada](evidence/n71-consumer-removal-qualification.json). A nova etapa n71_pcie_scan_remove_consumers(state) remove o bus sob rescan/remove lock e libera a lease MSI. Config/resources/window/PME/target e a bridge ficam retidos, permitindo ao próximo caller intercalar teardown do provider e disponibilidade OF. O cleanup completo usa essa etapa e mantém a restauração/free anteriores.

Fase de alocação ativa ou bus sem ownership recusa antes de efeitos. Child MSI/release incompleto bloqueia sucesso sem restaurar IO. Retry não repete remoção; held_stop_error permanece até o cleanup completo reportá-lo. Essa extração não muda a ordem DART do caller e não acrescenta attachment/driver/MASTER. É preparação para integrar o helper D11.

### Gates e reprodução

Mac/ARM64: scan86 cenários/72 mutações, optional18/14, IO1620/17 e PREF6435/17, total159/120 por plataforma. Sete cenários novos executam a etapa real e conferem bridge/config/PME/target retidos, ausência de writes/restore/free, erro MSI/stop, retry e API antiga. Três novas mutações detectam skip da fase, perda de stop-error e restauração antecipada. As dependências PCI/MMIO são modeladas; não é prova física.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_scan_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_optional_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_io16_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_pref64_host.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_pcie_scan_host.py
```

Primeiro gate scan passou baseline86 e71 mutações; uma mutação antiga que zerava o retorno stop-error deixou a variável unused após a extração. Erro de compile não contou como kill. Corrigimos apenas seu selector para consumir a variável e repetimos esse mutante por SIGABRT/asserção nos dois ambientes. Os55 outros inputs, compiler helper e demais selectors permaneceram idênticos; resultados aprovados foram reutilizados. Os três gates compartilhados, ainda não executados na primeira tentativa, foram rodados integralmente. Logs iniciais/retry privados preservados, sem prazo ou critério enfraquecido. AST/lint fatal passaram no Mac e AST no ARM64; não há typechecker Python.

Build de produção em M separado, sem wrapper privado, passouW=1/Werror/modpost/ELF64 AArch64/vermagic power2. Módulo104352 bytes/SHA456134c0783cfffd0ce59676d35234a544993602c665d84b4534f1c0bc7d1c67; nunca carregado.56 inputs protegidos,47 C/headers e nove arquivos de teste;30 includes efetivos. Use cópias exatas phone/kernel e Makefile `obj-m += n71-pcie-diagnostic.o`, mais o make/exports fixados descritos acima. Fonte original com seis alterações tracked, config/Image/vmlinux.symvers intactos; não usar KBUILD_MODPOST_WARN.

Arquivos: scan, cenários C compartilhados, runner Python e plano; doc/prova separadas. Sem pacote, dependência, banco, perfil, configuração global do Mac ou novo DFU. Custo: uma chamada interna adicional de lifecycle; desempenho físico não medido. Próximo: associação DART pré-scan, remoção/unmap, teardown provider e restore da disponibilidade antes da restauração final. IRQ/DMA/radio e energia permanecem abertos na issue40 e no goal.

[CI de83924a8](https://github.com/djalmajr/iphone6s-linux/actions/runs/37579331022) aprovada nos três jobs em2026-10-07T06:14:19Z; cobre a remoção D13 publicada. A integração D14/D15 posterior ainda requer sua própria CI e prova física.

### Publicação PCI não comprova associação IOMMU

[Auditoria primária](evidence/n71-iommu-publication-audit.json), [contrato D14](../.agents/plans/n71-irq-iommu-bindings.md#d14-associar-o-dart-no-scan-e-exigir-readback-do-core-iommu). Na fonte fixada, iommu_init_device:469–488 chama o dma_configure do bus antes de existir driver. O notifier ADD_DEVICE:1820–1824 retorna NOTIFY_DONE em erro do probe; um scan bem-sucedido, portanto, pode coexistir com associação ausente. Remoção do device dispara a liberação IOMMU. A integração precisará preparar mapa/provider antes da publicação e conferir fwspec/fwnode/SID e domínio traduzido depois, mantendo owners até a remoção dos consumidores.

As consultas iommu_group_get/put e iommu_get_domain_for_dev têm export fixado; dev_iommu_fwspec_get é inline. pci_for_each_dma_alias e pci_real_dma_dev são declarações sem export no vmlinux.symvers utilizado. Não chamá-las de módulo externo nem enfraquecer modpost. O contrato de aliases precisa ser fechado por caminho disponível ou export explícito em futura fatia antes de liberar driver/MASTER. D14/D15 abaixo implementam a integração e corrigem o contrato Apple; os dados desta auditoria são de fonte/ABI, sem prova física.

## D14 — associação DART antes do scan e readback IOMMU

[Scan](../phone/kernel/n71-pcie-scan.h), integraçãof11a91a e correçãoAppleea49c7e, [contrato D14](../.agents/plans/n71-irq-iommu-bindings.md#d14-associar-o-dart-no-scan-e-exigir-readback-do-core-iommu), [prova final](evidence/n71-dart-scan-qualification.json). Options internos incluem provider manual, default NULL. O wrapper hold_iommu exige provider não nulo, held bus/MSI/PME e prepara o owner OF/DART após PME/target e antes de PCI publication. Wrappers anteriores conservam provider NULL. Nenhum parâmetro do caller, perfil ou autoload seleciona essa rota nesta fatia.

Report exige disponibilidade e identidade das propriedades status/mapa próprios, exatamente oito células e todos os valores RID0x0008/0x0100, phandle do owner, SID0/range1. Fwspec deve ter fwnode do provider, num_ids0 e flags0. Ambos os dispositivos devem observar o mesmo domínio IOMMU_DOMAIN_DMA strict. Ausência/drift/erro, domínio identity/blocked/diferente e contagem incompleta recusam sucesso. O log usa map_sid0 e explica que não há readback privado do SID; não expõe ponteiros ou chama aliases sem export. Isso é observação de software, sem prova física de tradução/IRQ/rádio.

[Auditoria D15](evidence/n71-dart-fwspec-audit.json): apple-dart.c:913–961 guarda SIDs no stream_maps privado e não preenche fwspec.ids. O core inicializa fwspec zerado e delega of_xlate. A primeira fixture/modelo190/146 assumiu um ID0 e passou ABI, mas esse contrato recusaria a associação real. A leitura primária detectou o erro antes de selecionar o caller ou executar no telefone; corrigimos produção e fixture, sem reutilizar essa prova inicial para o contrato final. SID0 é inferido da leitura exata do mapa e da rotina xlate fixada; não é leitura do estado privado ou teste DMA. Não espelhar layout interno do driver para fabricar essa observação.

Remove_consumers remove bus/MSI e desfaz o mapa; limpa ponteiro de domínio emprestado e contagem depois de bus gone, mesmo com erro MSI. A bridge permanece retida. Cleanup completo tenta release D11 antes de restaurar config/resources/window/PME/target/free: provider registrado retorna busy e preserva estado. O próximo caller precisa intercalar provider stop entre as etapas. Retry conserva refs e não repete unmap já comprovado. Driver/enable/MASTER permanecem negados.

### Gates e reprodução

Mac/ARM64: scan125 cenários/102 mutações, optional18/14, IO1620/17 e PREF6435/17, total198/150 por plataforma. São39 cenários/30 mutações DART. Cobrem prepare antes de publication, guards/default, falhas antes/depois de efeitos, fwspec Apple/provider/flags/domínio, identidade/tamanho/células/read-error do mapa, MSI pendente, unmap/release e retry. Scan/report/cleanup são produção; API da lease D11 e core IOMMU são dependências modeladas. Prova isolada D11 reutilizada com input de produção intacto.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_scan_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_optional_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_io16_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_pref64_host.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_pcie_scan_host.py
```

O baseline scout inicial esperava que retry repetisse um erro de unmap pos-efeito. Readback já comprova o mapa restaurado; retry avança e retorna busy pelo provider registrado. A expectativa foi corrigida. Após o ajuste Apple, baseline125 e100 mutações passaram; dois selectors geraram unused de função/array, sem contar compile como kill. Corrigimos só esses selectors e repetimos os dois mutantes por SIGABRT/asserção. Os56 demais inputs e compiler helper permaneceram idênticos; a prova válida125/100 foi reutilizada. Os três gates compartilhados pendentes rodaram completos. Mutantes exigem Werror, SIGABRT/assertion; timeout/import/compile não são kills. AST/lint fatal passaram no Mac e AST no ARM64; não há typechecker Python.

ABI finalW=1/Werror/modpost/ELF64 AArch64/vermagic power2 passou.57 inputs protegidos:47 C/headers e dez testes,31 includes efetivos. Módulo privado110520 bytes/SHA17df226eea6d767cb05a042809e355751ad114fd6170d67ef80fea07fdef8bc0, nunca carregado. Fonte original com seis patches tracked, config/Image/vmlinux.symvers intactos; sem KBUILD_MODPOST_WARN ou pacote/configuração global do Mac.

Para reproduzir ABI, copie os phone/kernel exatos do JSON para M separado e use Makefile `obj-m += n71-pcie-diagnostic.o`. Só na cópia privada do caller, acrescente prototype global `int n71_iommu_scan_probe(struct device *, struct n71_diagnostic *, struct platform_device *);` e a função correspondente que retorna n71_pcie_scan_hold_iommu(dev,state,provider). Esse wrapper mantém a rota no objeto enquanto o caller público não a seleciona. Use make/exports fixados, compare todos os hashes e não carregue o probe nem trate esse artefato como candidata física.

Arquivos: scan, C compartilhado, runner Python, fixture DART e plano; stubs IOMMU nos quatro runners preparados separadamente em36aa20d. Sem dependência/banco/perfil físico novo. Custo: lease OF retida e consultas de fwspec/domínio por dispositivo; desempenho físico não medido. Próximo: seleção/getter do caller e cleanup consumidores/unmap → provider stop → release/restore/free. Alias/máscaras, collector/perfil e energia antes da sessão física agrupada. Wi-Fi#9, energia#2, issue40 e goal permanecem abertos.

## D16 — seleção IOMMU e lifecycle completo no caller

[Caller](../phone/kernel/n71-pcie-diagnostic.c), código311cf77, [prova sanitizada](evidence/n71-iommu-caller-qualification.json), [decisão D16](../.agents/plans/n71-irq-iommu-bindings.md#d16-selecionar-iommu-no-caller-e-intercalar-teardown-do-provider). iommu_parent é bool0400, default false, exigindo msi_parent e scan_hold, além dos guards PME/inventário existentes. Depois do inventário e antes do scan, o caller adquire o provider e recusa owner ausente, lease não running ou device ausente antes de selecionar hold_iommu. Nenhum perfil/autoload físico seleciona a rota nesta fatia.

Cleanup associado remove consumidores PCI/MSI e desfaz o mapa antes de parar o provider; então release D11 restaura disponibilidade/status, seguido por config/resources/bridge/reset/power. Erro bloqueia a próxima etapa e conserva owners/pin. Retry opera na mesma sessão, sem rescan nem releases duplicados. Modos anteriores sem associação conservam a ordem antiga. dart-release recusa enquanto existir owner OF e orienta action=cleanup. Getters anteriores preservados.

Getter iommu sob session_lock: requested, ready, held, owner, available, mapped, observed, map_checked, session_error. map_checked só resume a última observação OF/core com barramento ainda retido; não lê SID privado, não comprova tradução DMA, IRQ ou rádio. Após remoção do bus, domínio emprestado/count desaparecem mesmo com falha MSI; falha posterior pode conservar owner/status enquanto mapped já é zero.

### Verificação e reprodução

Mac/ARM64: caller185 cenários/129 mutações compiladas, incluindo29 cenários/26 mutações IOMMU; provider27 e cleanup isolado4 cenários/17 mutações, total216/146 por plataforma. Caller e cleanup são produção; dependências kernel/PCI/provider modeladas. D14/D15 com56 inputs não caller idênticos e helper isolado D11 foram reutilizados. Mac provider foi reutilizado com inputs relevantes intactos.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_pcie_diagnostic_caller.py' -v
python3 -B -m unittest discover -s tests -p 'test_n71_dart_provider.py' -v
python3 -m flake8 --select E9,F63,F7,F82 tests/test_n71_pcie_diagnostic_caller.py tests/test_n71_dart_provider.py
```

O primeiro pacote ARM64 omitiu o header existente n71_dart_irq_fixture.h: caller passou, provider teve15 falhas de compile, sem contar como kills. Pacote corrigido executado em pasta VM separada. A fixture do caller foi corrigida para limpar domínio/count antes do release MSI, como produção; adicionamos conferência do getter em sete falhas de teardown e repetimos caller completo nos dois ambientes. Produção não mudou nessa correção de fixture. Logs/falhas privados preservados. Mutantes exigem compileWerror e SIGABRT/asserção; AST/lint fatal passaram. Não há typechecker Python; ABI real é o gate de tipos/kernel.

Build exato, sem wrapper privado: W=1/Werror/modpost/ELF64 AArch64/vermagic power2 passou. Módulo112832 bytes/SHA6250c41b4f5427586e69764f12b0fae01b234cda8839082b74a3197a0996547b, nunca carregado.53 inputs:47 C/headers de produção e seis testes/fixtures; fonte original com seis patches tracked, config/Image/vmlinux.symvers intactos. Reprodução em M separado com cópias exatas phone/kernel e Makefile obj-m += n71-pcie-diagnostic.o; use make/exports fixados acima, sem KBUILD_MODPOST_WARN e sem wrapper.

[CI do parent e8307e9](https://github.com/djalmajr/iphone6s-linux/actions/runs/37582690113) passou os três jobs em2026-10-07T06:50:49Z. Essa CI comprova a publicação D14/D15; D16 exige sua própria CI após publicação.

Arquivos desta fase: plano, caller, C/runner do caller e fixture isolada de cleanup; doc/prova separadas. Mudança de API opt-in sem quebrar modos antigos. Sem pacote/dependência/banco, instalação/configuração global no Mac, novo boot/DFU ou load. Custo: provider retido durante o scan e leitura de estado sob mutex; desempenho físico não medido. Próximo: collector/perfil e contrato de aliases/máscaras, depois sessão física agrupada com orçamento de energia. Wi-Fi#9, energia#2, issue40 e goal permanecem abertos.

## D17 — coleta MSI/IOMMU e journal na mesma sessão

Código9c3c177, [coletor](../scripts/host/n71_iommu_result.py), [prova sanitizada](evidence/n71-iommu-collector-qualification.json). A API interna Session aceita iommu_parent bool default false, somente com held/resource-capable/power2 e bytes/hash/vermagic exatos da ABI D16 qualificada sem wrapper. Adiciona msi_parent=1/iommu_parent=1 ao único insmod e coleta getters/parâmetros imutáveis. Nenhuma opção CLI, perfil ou autoload físico seleciona a rota nesta fase.

Coleta exige requested/ready/held/erro coerentes entre MSI/IOMMU/caller, flags imutáveis Y e ownership/counts completos. Provider bound/acquired deve preceder os dois registros MSI/OF/core, cada um antes do respectivo root/endpoint PCI e antes da sessão retida. Root0:08 e endpoint1:00 são exatos; SID0 é somente o mapa OF e o domínio traduzido observado no core. O resumo mantém IRQ delivery, DMA translation, Wi-Fi e energia como false.

Journal salva modo e resumo de associação. Retomada confere checkpoint, boot/hashes existentes, modo e estado antes de comandos. Resumo de cleanup salvo é reconstruído da prova, recusando promoção a readback físico. Antes de unload, exige ownership vazio e caller limpo; consumer removal precede provider release, que precede host restore. Helpers OF ainda não emitem readback físico independente de unmap/status: software_ownership_released não equivale a tradução ou readback físico.

Falha do provider antes de scan distingue start não tentado/index0 de restore necessário/index16. Para caller bound com primary error negativo e sem scan, o contrato exige erro do provider correspondente, nenhuma atribuição, getter resources vazio, final caller/reset/power em ordem e provider release antes de reset. O helper desse caminho é testado diretamente; os fluxos completos do coordenador são positivos, captura inicial inválida, drift antes de efeitos, cleanup pendente e resumo salvo adulterado, com dependências de telefone sintéticas. Não atribuir prova física ou prova de todo caminho de erro a esses testes.

### Gates e reprodução

Mac e Ubuntu ARM64:95 testes unittest e83 mutações por plataforma, nos quatro gates: IOMMU13/27 (12 métodos funcionais e um gate de mutações), held21/30, resource-stage16/26 e link45/0. Fixtures executam o coordenador/caller Python reais; dependências SSH/telefone são modeladas. Fonte dos mutantes é compilada e executada; requer AssertionError, sem ERROR/import/timeout.

```sh
python3 -B -m unittest discover -s tests -p 'test_n71_iommu_result.py'
python3 -B -m unittest discover -s tests -p 'test_n71_held_session.py'
python3 -B -m unittest discover -s tests -p 'test_n71_resource_stage.py'
python3 -B -m unittest discover -s tests -p 'test_n71_link_session.py'
python3 -m flake8 --select E9,F63,F7,F82 scripts/host/n71_iommu_result.py scripts/host/n71-link-session.py scripts/host/n71_held_session.py tests/test_n71_iommu_result.py
```

O teste integrado expôs colisão real: one() contava bound= dentro do log DART como segunda resposta REG_ON. Validação agora exige regex ancorada e linhas prefixadas do campo; logs originais conservados. Primeiro mutant cleanup-gate produziu KeyError no teste além de assertion e não foi contado como kill. Asserções de shape corrigidas; fixtures de wire getters independem das constantes do parser. Gate novo e quatro regressões finais repetidos completos em ambos os ambientes. Falhas/logs privados preservados. AST e lint fatal passaram; não há typechecker Python.

ABI D16 reutilizada com53 inputs relevantes intactos; nenhum C/headers/kernel/config/Image/exports mudou. Snapshot privado completo dos inputs públicos protegeu582 arquivos na VM, sem instalações/configuração global no Mac. Não repetir build do kernel por mudança apenas no coletor. [CI parent4898914](https://github.com/djalmajr/iphone6s-linux/actions/runs/37584482214) passou os três jobs; cobre D16 publicado, enquanto D17 recebe CI separada após publicação.

Arquivos: plano, coletor, teste, link-session e held-session; doc/prova em fase separada. Mudança opt-in da API interna, sem novo banco/pacote/dependência; formatos antigos conservados e journal sem modo explícito continua default false. Custo: quatro leituras sysfs adicionais e parsing sob orçamento existente por coleta opt-in, sem desempenho físico medido. Próximo: auditoria de aliases/máscaras e seleção/composição do perfil, mantendo uma sessão física agrupada e orçamento de energia. Wi-Fi#9, energia#2, issue40 e goal continuam abertos.

Refinamento de selectors D17: duas mutações adicionais exigem index16 indevidamente quando start não foi tentado e promovem software association a wifi_verified. Ambas morreram por AssertionError nos dois ambientes. Gate IOMMU13/27 repetido completo; produção e25 selectors anteriores intactos. Três gates anteriores reutilizados com inputs relevantes idênticos. Total final95/83 por plataforma.

## D18 — topologia DMA, máscaras e grupo IOMMU

[Códigoe0d81ca](../phone/kernel/n71-pcie-scan.h), [contrato](../.agents/plans/n71-irq-iommu-bindings.md#contrato-d18-após-leitura-primária), [prova sanitizada](evidence/n71-dma-topology-qualification.json). A rota continua opt-in, sem driver, enable, MASTER ou DMA. O coletor D17 ainda seleciona o módulo D16; esta etapa não compõe nem carrega um perfil físico novo.

Na fonte fixada, [pci_for_each_dma_alias](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/search.c#L28) percorre dispositivo real, bitmap local e bridges upstream. [pci_real_dma_dev](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/pci.c#L6351) é weak; a auditoria conferiu binding W no vmlinux e ausência de override ARM64. Ambos continuam sem export, portanto o módulo não os chama. Campos PCI públicos e APIs iommu_group_get/put/id exportadas são suficientes para conferir o caso limitado do N71, sem espelhar layout privado.

[PCI probe](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/probe.c#L2733) fornece dev.dma_mask apontando para pci_dev.dma_mask e coherent32; streaming32 é inicializado em2043–2046. [brcmfmac PCIe](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1116) e msgbuf usam buffers dma_alloc_coherent; a busca nas fontes C/headers do driver não encontrou setters de máscaras. CONFIG_PCI_IOV=y, BRCMFMAC=m e IOMMU_DMA=y foram conferidos. Isso ainda não identifica revisão/calibração do chip nem prova a viabilidade de seus buffers no hardware.

O guard exige rootbus0 sem parent/self e sysdata próprio; root0:08 Apple106b1004/class060400/header bridge; endpointbus1:00 Broadcom14e443a3/class028000/header normal diretamente sob root/subordinate e sysdata próprio, sem subordinate. Ambos recusam multifunction/PF/VF, bitmap local não vazio e flags PCIE_BRIDGE_ALIAS, BRIDGE_XLATE_ROOT ou PCI_BRIDGE_NO_ALIAS. Masks streaming/coherent devem ser exatamente32 e o ponteiro deve ser o PCI próprio. Root aceita Root Port PCIe ou bridge legado sem capability PCIe; endpoint aceita Endpoint ou Legacy Endpoint PCIe.

Sob essas premissas públicas e o weak binding fixado, os aliases inferidos são o próprio RID e, para endpoint sob bridge legado, também RID0008. RID0008/0100 já pertencem ao mapa OF de SID0 validado em D14/D15. Não copiamos o iterador genérico nem chamamos helpers sem export. O log `N71_PCIE_SCAN_DMA` conserva RID, quantidade inferida, grupo e masks, com a indicação explícita de topologia/fonte, somente leitura e ausência de DMA. Grupo deve ter o mesmo ID não negativo para os dois devices; get/id/put são balanceados antes de retornar. O host guarda só o inteiro, sem ref de grupo, e limpa o ID após bus removal antes de MSI release, mesmo se essa liberação falhar. Guards de remoção conservam observações enquanto o bus segue vivo.

### Qualificação e reprodução

Os quatro gates afetados rodaram completos no Mac e Ubuntu ARM64: scan180 cenários/142 mutações, optional18/14, IO1620/17 e PREF6435/17; total253/190 por plataforma. D18 acrescenta55 cenários e40 mutações. Cada mutant contado compilou com Werror e morreu por SIGABRT com asserção; compile/selector/import/timeout não foram kills. Produção scan executa diretamente; PCI/core IOMMU, drift de campos públicos e a lease OF separadamente qualificada são dependências modeladas. Não prova concorrência global, requesters físicos, IRQ delivery, tradução DMA, rádio ou carga.

```sh
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_optional_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_io16_host.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_pref64_host.py -v
```

AST e lint fatal passaram; não há typechecker Python. A primeira fixture omitiu typedef u64 e uma âncora nova apareceu duas vezes; ambos corrigidos antes da matriz final. O runner ARM64 comparou inicialmente o Makefile temporário de alvo único ao público de seis alvos depois de o build passar. Corrigimos só essa conferência e repetimos ABI em M separado; os quatro gates ARM64 aprovados foram reutilizados com84 inputs intactos. O Makefile original e todos os C/headers foram conferidos por SHA, sem alterar a fonte pública.

Build exato de produção, sem wrapper, passou W=1/KCFLAGS=-Werror/modpost/ELF64 AArch64/vermagic power2:114008 bytes/SHA46dfdfda600ad1bfa21606a7a758f7764b899c38959ba877fca819571e49106f. Fonte958481f com seis patches tracked, config/Image/vmlinux.symvers preservados; nenhum MODPOST_WARN, pacote ou configuração global do Mac. Para reproduzir, copie C/headers exatos do JSON para M isolado, mantenha o Makefile original intacto e use nele um seletor temporário `obj-m += n71-pcie-diagnostic.o`, make com as flags da prova e KBUILD_EXTRA_SYMBOLS do vmlinux.symvers fixado. Não carregar o módulo como parte da reprodução de ABI.

[CI parent6aeb88c](https://github.com/djalmajr/iphone6s-linux/actions/runs/37588573148) passou os três jobs; a publicação D18 recebe sua própria CI. Arquivos: plano/scan/C compartilhado/fixture/runner, até cinco nesta fase; documentação/prova separadas. API antiga/defaults preservados; custo adicional apenas de validação de campos e get/id/put por device na rota opt-in. Sem banco/dependência nova e sem desempenho físico medido. Próximo: collector deve validar o log DMA, conservar a inferência no journal e selecionar esta ABI com premissas de fonte/exports; depois composição e sessão física agrupada com orçamento de energia. Wi-Fi#9, energia#2, issue40 e goal permanecem abertos.

## D19 — collector e journal DMA

[Códigof8ab47a](../scripts/host/n71_iommu_result.py), [decisão](../.agents/plans/n71-irq-iommu-bindings.md#d19-exigir-o-diagnóstico-dma-no-collector-e-no-journal), [prova](evidence/n71-dma-collector-qualification.json). O opt-in interno IOMMU seleciona agora somente a ABI D18 por bytes/SHA/vermagic. Exige prova de build exato sem wrapper/load, fonte958481f, digest dos seis patches, weak real_dma_dev sem override ARM64, APIs de grupo exportadas e helpers de alias sem export/não referenciados pelo módulo. O módulo/provas D16 permanecem preservados, mas o novo opt-in recusa essa ABI anterior antes de efeitos SSH. Modos default false não mudam. A Image física exata ainda precisa ser vinculada pelo selector/composer posterior; esta etapa não compõe perfil ou libera carga no telefone.

Cada captura retida exige exatamente dois registros N71_PCIE_SCAN_DMA completos, ordenados root0:08/RID0008 e endpoint1:00/RID0100. Root tem um alias inferido, endpoint um ou dois; grupo é compartilhado, não negativo e até INT_MAX; streaming/coherent são exatamente00000000ffffffff. A ordem passa a ser provider/lease, depois MSI/DMA/IOMMU/device para root e endpoint, antes de held. As máscaras/grupo são observações de software; aliases continuam inferidos da fonte/topologia. O resumo conserva essa distinção e mantém tradução física/IRQ/Wi-Fi/energia como não verificadas.

O journal reconstrói os detalhes DMA da captura salva, sem confiar em resumo editado. O coordinator real foi exercitado em acquire/resume/release, incluindo recusa de grupo/masks/RIDs/aliases/proof tier alterados antes de qualquer comando no resume. Hardware e wire getters são dependências sintéticas independentes das constantes do parser. Cleanup e falhas anteriores ao scan mantêm os contratos D17. Não há getter de grupo/masks vivo novo nem readback físico de tradução; igualdade do resumo não amplia o nível de prova.

Mac e Ubuntu ARM64 passaram99 testes/98 mutações por AssertionError por plataforma: IOMMU17/42, held21/30, resource16/26 e link45/0. Quatro métodos funcionais e15 selectors novos. A matriz final dos quatro gates rodou completa nas duas plataformas; todos os mutants contados compilaram e falharam com AssertionError, sem ERROR/import/timeout. AST e lint fatal passaram; não há typechecker Python. Snapshot privado de584 arquivos públicos conferido antes/depois dos gates; atualização posterior do status do plano não modifica inputs executáveis qualificados.

```sh
python3 -B -m unittest discover -s tests -p test_n71_iommu_result.py
python3 -B -m unittest discover -s tests -p test_n71_held_session.py
python3 -B -m unittest discover -s tests -p test_n71_resource_stage.py
python3 -B -m unittest discover -s tests -p test_n71_link_session.py
```

ABI D18 foi reutilizada com84 inputs relevantes por SHA intactos, incluindo os C/headers e gates PCI anteriores; nenhum rebuild de módulo/kernel/Image, load, boot ou DFU. Arquivos desta fase: plano, collector e teste; documentação/prova separadas. Sem banco, pacote, instalação/configuração global do Mac; custo adicional de parsing de dois registros e armazenamento do pequeno resumo, sem desempenho físico medido. Próximo: selector/flags/composer ligam ABI e premissas à Image power2 exata num perfil privado separado, conservando modos anteriores, rollback, SSH/Bash/Herdr/HTTP, snapshot e orçamento de energia. Wi-Fi#9, energia#2, issue40 e goal continuam abertos.

## D20 — seleção, Image e candidata privada

A implementação foi dividida em três fatias: [53a9789](https://github.com/djalmajr/iphone6s-linux/commit/53a9789) centraliza a qualificação e confere Image; [eeb6a50](https://github.com/djalmajr/iphone6s-linux/commit/eeb6a50) integra os selectors/flags/coordinator; [482aadf](https://github.com/djalmajr/iphone6s-linux/commit/482aadf) completa a referência exclusiva do DART. [Decisões D20](../.agents/plans/n71-irq-iommu-bindings.md#d20-integrar-seleção-e-composição-do-perfil-iommu).

`n71_iommu_build.py` conserva a autoridade D18 de fonte/patch/exports/ABI e liga config/Image/vmlinux.symvers ao registro de build power2. Exige SHA/bytes de Image.gz, um único stream gzip completo com limite128MiB e SHA/bytes da Image descomprimida. No collector, o prefixo loader/ASPM é conferido primeiro; o FDT enquadrado e o initramfs protegido delimitam a faixa comprimida, que passa pelo mesmo helper. Mudança de kernel, streams concatenados, tamanho/tipo errado ou sufixo alterado são recusados antes de SSH. [Prova Image](evidence/n71-iommu-image-qualification.json).

`--pcie-iommu-parent` exige held/resources/ASPM-off/power2/REG_ON. `--iommu-parent` exige metadata booleano exatamente correspondente, o módulo D18 explícito e a Image exata. Os nove headers de atribuição precisam conservar seus hashes entre o build PREF64-unsized, D18 e a árvore atual; readback/optional/IO16/PREF64 são herdados do seletor anterior. Somente o registro PCIe muda; REG_ON e modos antigos são preservados. A seleção é passada aos caminhos run/check/resume/release do Session. O teste integrado usa o coordinator/journal reais e um backend físico modelado; acquire/check/release executam uma enumeração. Isso não comprova associação no hardware. [Prova de integração](evidence/n71-iommu-profile-qualification.json).

A composição real revelou ausência do phandle DART no DTB diagnóstico antigo. Reservar o próximo valor apenas do baseline colidiria com41, já usado por um provider acrescentado no staging. O composer valida o DTB completo existente, reserva45 depois das referências41–44 e adiciona somente `phandle` ao DART desativado. Revalida todos os nós/propriedades, sem mapa IOMMU permanente nem mudança dos providers antigos. D12, que compila a topologia com o pin reservado antecipadamente, conserva sua semântica. Um caso sintético reproduz essa colisão; o primeiro smoke recusado não conta como sucesso. [Prova de composição](evidence/n71-iommu-private-profile.json).

### Reprodução da preparação

Os artefatos privados vêm da build D18 e dos perfis já verificados. Defina `TASK_SOURCE_PROFILE`, `TASK_KERNEL_DIR`, `TASK_DIAGNOSTIC_DIR`, `TASK_PCIE_MODULE`, `TASK_REG_ON_MODULE` e `TASK_IOMMU_PROFILE_DIR` para esses caminhos. O output deve ser um diretório novo diretamente sob runtime; nunca sobrescreva a candidata anterior. Execute a partir da pasta iphone-linux-tools:

```sh
python3 -B scripts/build/compose-n71-diagnostic.py \
  --source-profile "$TASK_SOURCE_PROFILE" \
  --kernel-dir "$TASK_KERNEL_DIR" \
  --kernel-patchset n71-dart-serdev-power-v2 \
  --diagnostic-dir "$TASK_DIAGNOSTIC_DIR" \
  --module "$TASK_PCIE_MODULE" \
  --module-sha256 46dfdfda600ad1bfa21606a7a758f7764b899c38959ba877fca819571e49106f \
  --reg-on-module "$TASK_REG_ON_MODULE" \
  --output-dir "$TASK_IOMMU_PROFILE_DIR" \
  --pcie-aspm-off --pcie-scan-hold --pcie-resource-capable --pcie-iommu-parent
python3 -B scripts/host/n71-link-session.py \
  --profile "$TASK_IOMMU_PROFILE_DIR/deployment.json" \
  --host-scan --scan-link-target --scan-pme-disable --scan-hold \
  --resource-capable --iommu-parent --check
```

Ambos os comandos são locais: não iniciam USB/SSH, carregam módulo ou dão boot. A composição real conferiu oito arquivos700/600, igualdade de initramfs/chaves/REG_ON e de todo o payload fora da única propriedade DART; deployment difere somente no hash do payload. O snapshot preservado tem44 entradas. Os84 inputs relevantes da ABI D18 permaneceram idênticos, sem reconstrução de Image/módulo. Payload/DTB, chaves, identificadores, snapshots e logs ficam privados.

```sh
python3 -B -m unittest discover -s tests -p test_n71_iommu_build.py
python3 -B -m unittest discover -s tests -p test_n71_iommu_profile.py
python3 -B -m unittest discover -s tests -p test_n71_diagnostic_payload.py
python3 -B -m unittest discover -s tests -p test_n71_diagnostic_held_profile.py
```

Mac e Ubuntu ARM64: D20a107 testes/122 mutações; D20b125/130, seis gates intactos reutilizados após a correção de um selector legado; D20c30/24, novo perfil8/21. Escopos sobrepostos não são somados. Mutants contados compilaram e falharam por AssertionError, sem import/ERROR/timeout. AST e lint fatal passaram; não há typechecker Python. A fase de integração teve cinco públicos, composição três, documentação separada. Sem dependência/pacote/banco/configuração global do Mac; desempenho físico não medido.

### Sessão física agrupada preparada

```mermaid
flowchart LR
    A["DFU manual uma vez"] --> B["Linux e restore"]
    B --> C["MSI/DART e PCI retidos"]
    C --> D["Recursos e inventário"]
    D --> E["Cleanup verificado"]
    E --> F["Serviços, snapshot e sync"]
    F --> G["Retorno ao iOS"]
```

A execução física aguarda DFU manual. A primeira janela do monitor expirou sem Pongo e sem envio de payload Linux; a leitura USB posterior confirmou recuperação (0x1281). A candidata e a sessão agrupada permanecem preparadas; uma leitura USB nova deve confirmar o modo antes de retomar. A sessão preparada reúne associação, resume/check sem segundo scan, atribuição, inventário PCI e energia, cleanup, SSH/Bash/Herdr/HTTP e snapshot/sync/retorno iOS. Erro de cleanup conserva owners e bloqueia reboot automático; os logs privados indicam a etapa a recuperar. Não habilitar driver/MASTER/rádio nesta candidata. Percentual/estado de carga lidos no iOS delimitam a sessão, sem comprovar saúde ou carregamento no Linux. Nenhuma prova física nova está incluída nesta documentação de preparação; issue40, Wi-Fi#9, energia#2 e o goal permanecem abertos.

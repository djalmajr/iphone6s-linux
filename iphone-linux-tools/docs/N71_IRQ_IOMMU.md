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

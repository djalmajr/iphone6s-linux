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

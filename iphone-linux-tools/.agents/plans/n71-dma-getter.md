# Getter DMA explícito no diagnóstico PCIe

## Contrato

Adicionar dma_observe=false e dma_iova=0x3ffff028, parâmetros root-only em leitura, e dma_observation root-only. Cada leitura captura até dois conjuntos, sob session_lock e o backend com device_lock. Exigir também driver_runtime e iommu_parent. Devolver sempre os campos de validade, horário e erro, inclusive capturas parciais; não transformar erro em sucesso, alterar owners ou latchear erro primário por causa de uma observação.

Os words mostram command, TCR, status/endereço raw de erro e quatro TTBRs do stream 0. PA é resultado da API de software, não acesso físico nem prova de tradução do dispositivo. stable não é prova de mapping. A captura posterior ao fault pode ocorrer depois de buffers liberados; preparar coleta limitada antes de publish.

## Checklist

- [x] Getter ligado ao módulo, opt-in e IOVA imutáveis após carga, no máximo 16 reads DART por leitura.
- [x] Fixture compila caller, getter e backend reais; modela PCI/IOMMU/clock/mapping e observa release dos locks, dados completos/parciais e recusas de opt-in.
- [x] Mac: 275 cenários do caller (cinco do getter) e 242 mutações por SIGABRT/assert, incluindo oito novas. AST/lint aprovados. Backend e helper têm gates independentes já publicados.
- [ ] Compilação externa kernel/ARM64, nova identidade de módulo e coleção física agrupada com I2C.

Até cinco arquivos nesta fase, incluindo evidência sanitizada. O perfil e os módulos PMD antigos continuam selecionáveis somente pelos bytes compilados preservados, sem atualizar seus pins. Reversão: retirar getter/parâmetros/include; backend pode permanecer sem caller. Sem VM ou DFU nesta fase.

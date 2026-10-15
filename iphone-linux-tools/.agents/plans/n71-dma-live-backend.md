# Backend DMA sob a vida do endpoint vinculado

## Decisão

Reutilizar o mapping MMIO que o provider DART já mantém no diagnóstico, sob session_lock. Não abrir outro mapping nem reivindicar a região do driver. Serializar também device_lock do endpoint, na mesma ordem session → device usada pelo caller de prepare/release. Exigir brcmfmac vinculado, DMA gerenciada pelo core, identidade N71, domínio DMA atual igual ao registrado e owners/provider/power ativos antes de cada callback.

Consultar somente API pública iommu_iova_to_phys; sem casts de estruturas privadas. Retornar dois conjuntos com boottime, PA, words e validade, preservando falhas parciais. Igualdade/stable não demonstra tradução física ou estado exato do fault. Memória de tabelas pode mudar no driver enquanto o device permanece vinculado. IOVA e aperture seguem o helper limitado a 32 bits.

## Checklist

- [x] Backend opt-in sem alocação, mapeamento, DMA ou writes novos; 16 reads DART no máximo.
- [x] Locks liberados em todo retorno; não consultar domínio antes de validar o driver sob device_lock.
- [x] Gate C Mac: 58 cenários e 15 mutações compiladas por SIGABRT/assert. AST/lint aprovados. A primeira tentativa detectou um mutante que não compilava por função não usada; corrigido para preservar a referência, sem contá-lo como kill.
- [ ] Ligar getter explícito no módulo, qualificar contexto kernel/ARM64 e coleta limitada antes de publish.

Até cinco arquivos nesta fase. Não há nova sessão física, build de kernel ou alteração do perfil padrão. Compilar o backend real contra mocks não prova a vida do driver ou o hardware; modpost e teste físico continuam obrigatórios. Reversão: remover este header, ainda sem caller nesta fase.

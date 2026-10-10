# Coleta passiva MSI e continuidade (#40/#9)

## Contexto

O diagnóstico em f79c19b expõe actions/getter, com módulo real e gates Mac/ARM64 qualificados em6c7ef24. Nenhum artefato novo foi selecionado/carregado no telefone. `scripts/host/n71_iommu_result.py:39` reúne getters, `:70` verifica snapshot e `:147` compara a continuidade. O histórico de associação é anterior à alocação e precisa continuar separado. O goal aprovado autoriza a integração; nenhuma ação do operador necessária.

## Arquivos e detalhes

Fatia de quatro arquivos: este plano, `scripts/host/n71_msi_allocation_result.py`, `scripts/host/n71_iommu_result.py` e `tests/test_n71_msi_allocation_result.py`. Acrescentar coleta somente de leitura do getter quando ele existir. Módulos anteriores não possuem esse arquivo e preservam seu comportamento; o modo IOMMU desligado continua sem coleta. Não mudar seleção/perfil/build, emitir actions, aprovar IRQ/DMA/rádio ou escrever novo estado de intent nesta fatia.

Parser opcional do marcador `N71_PCIE_MSI_ALLOCATION `:12 campos exatos/ordenados/canônicos, um registro, máximo2MiB, booleans exatos, phase0..2, IRQs0..INT_MAX, slots0..ff, mappings0..8, erros negativos Linux até4095. Representar falhas/leases parciais sem convertê-las em sucesso. Sem host, ownership é zero e os erros de sessão podem sobreviver. Snapshot compara host/held/cleanup_error/primeiro erro com o caller; resume exige estado/presença idênticos antes de qualquer efeito. Getters/histórico de associação permanecem idênticos.

## Tarefas

- [x] Implementar parser e coleta passiva usados por snapshot/resume existentes.
- [x] Verificar estados completos/parciais, dados inválidos, shell de leitura real e continuidade; executar mutações que removem as guardas.
- [x] Rodar gate de associação existente, AST e lint fatal; conservar gates/kernel/artefatos anteriores.
- [ ] Documentar/publicar evidência e CI na branch existente.
- [ ] Integrar depois intent/proof de alocação, causalidade do primeiro erro de cleanup, seleção/perfil e driver/DMA/firmware/energia antes do DFU agrupado.

## Verificação e limites

Implementação em57e8fa1:Mac/Ubuntu ARM64,7 testes/16 mutações de getter/coordenador,21/53 da associação, shell real/AST/lint fatal aprovados. Ampliamos somente o novo teste de12 para16 mutações e retomamos esse gate/lint; associação permaneceu válida. CI6c7ef24 falhou por fixture DART desatualizada, corrigida em21bd91c sem remover cobertura:31 cenários/17 mutações C, dois métodos, nas duas plataformas. [Reprodução e evidência](../../docs/evidence/n71-msi-passive-collector-qualified.json). Publicação/CI atuais continuam em acompanhamento; intent/proof/actions e seleção/perfil não foram acrescentados nesta fatia.

`python3 -B -m unittest discover -s iphone-linux-tools/tests -p test_n71_msi_allocation_result.py -v` e gate `test_n71_iommu_result.py` no Mac/Ubuntu ARM64; mutações reais de fonte precisam de compilação Python válida e falha por asserção. AST/lint fatal, nenhum typechecker Python configurado. Não repetir gates C/build com inputs intactos. Publicar somente fontes/evidência sanitizados, sem raw logs/artefatos privados. Esta coleta não exige novo boot; seleção e execução física seguem pendentes.

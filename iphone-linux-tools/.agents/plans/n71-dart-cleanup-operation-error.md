# Erro preservado do provider após associação física — #40

## Contexto

A candidata OF corrigida passou associação MSI/OF/core, aquisição e atribuição PCIe no aparelho. O cleanup removeu bus/provider, restaurou16 TTBRs, recursos/config/PME/TLS/reset/energia e zerou owners, mas preservou EIO do DART porque command mudou entre snapshots. O parser de recursos exigia que o erro final fosse exatamente o erro da atribuição anterior (zero), confundindo operação negativa preservada com ownership pendente. Recuperação específica no mesmo boot comprovou liberação e unload normal, REG_ON original e serviços; snapshot/sync salvos. Não tratar esse EIO como ciclo DART positivo nem ativar driver/DMA/rádio.

## Arquivos e detalhes

Fase host, no máximo cinco arquivos: `scripts/host/n71_iommu_result.py` valida e expõe a operação negativa somente com lease/restauração completas; `scripts/host/n71_resource_stage.py` passa essa prova ao parser; `scripts/host/n71_resource_result.py` separa erro da atribuição do primeiro erro do cleanup; `tests/test_n71_iommu_result.py` exercita parser e coordinator/journal reais; `tests/test_n71_resource_result.py` conserva o contrato legado e os erros de atribuição. Não alterar hardware, módulo, kernel, payload, logs ou permissões de escrita. Fixtures públicos sintéticos, nunca copiar registros privados.

## Tarefas

- [x] Um DFU/boot com associação, atribuição, inventário e recuperação agrupados.
- [x] Owners zerados, restauração, unload normal e serviços comprovados no mesmo boot.
- [x] Registrar prova física sanitizada, separando associação de IRQ/DMA/Wi-Fi.
- [x] Validar causa DART negativa única, bounded, causal e com restore completo; conservar primeiro erro.
- [x] Exercitar release/resume sem segunda ação, inclusive prova ausente/duplicada/erro diferente/owner pendente.
- [x] Gates relevantes e mutações por asserção no Mac e Ubuntu ARM64; AST/lint fatal.
- [ ] Documentar causa/limites e atualizar issues/branch autorizada; aguardar CI completa para conclusão de código.
- [x] Auditar a semântica de command/stream mask na fonte fixada; a alteração observada é compatível com invalidate stream0. Não houve mudança de política de restore.
- [ ] Qualificar entrega IRQ/DMA e driver/radio em fatia própria; não inferir desses registros.

## Verificação

`python3 -B -m unittest discover -s tests -p test_n71_iommu_result.py` e gate de recursos, estágio/journal afetados. Mutações devem produzir AssertionError, sem contar import/compilação/timeout como kill. Revalidar o log original sem alterações; não fabricar erro/caller/restores para satisfazer parser. Reusar gates de módulo/OF/perfil quando seus inputs permanecerem intactos. Nenhum novo boot para validar parsers. Não há typechecker Python configurado; AST/lint fatal substituem somente a checagem sintática.

## Decisão sobre CI e teste físico

A exigência anterior de aguardar a execução completa antes do teste físico era uma escolha do plano local. Neste teste usamos gates relevantes já aprovados no Mac/Ubuntu ARM64, build/exports/identidade e composer/check reais; a CI completa permaneceu ativa e ainda não foi declarada verde. Isso não dispensa CI de publicação/conclusão nem altera hooks. O operador já estava em DFU, e outra espera não acrescentaria prova aos inputs da candidata. Próximos testes continuam agrupados e subordinados a evidências relevantes completas.

## Resultado da correção offline

Mac/Ubuntu ARM64:113 testes/141 mutações Python por AssertionError por plataforma; AST e Flake8 fatal E9/F63/F7/F82 passaram. Gate IOMMU21/53 reexecutado após ampliar a cobertura do primeiro erro de atribuição; demais gates aprovados são reutilizados com produção/inputs relevantes intactos. Inputs541 conferidos antes/depois. O primeiro mutant de estágio não alcançava o coordinator e o primeiro de tipo gerou TypeError; ambos foram corrigidos e somente asserções finais contam. Logs físicos originais revalidados sem alteração, candidato real `--check` aprovado e artefatos de kernel/módulo/perfil intactos. [Qualificação](../../docs/evidence/n71-dart-cleanup-operation-qualified.json).

Lint usa quatro wheels puros da PyPI com hashes fixados na requirements da CI, carregados diretamente de pasta privada; sem instalação no Mac/VM. O primeiro wrapper não protegia a reentrada de multiprocessing; single worker resolveu a execução local. Nenhuma mudança no programa público por causa desse wrapper. Não há typechecker Python. CI completa3a61c76 passou seis jobs; a correção terá CI própria. O operador não precisa de outra ação física nesta fase.

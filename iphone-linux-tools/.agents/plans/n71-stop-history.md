# Histórico anterior ao stop — issue47

## Contexto

O caso físico788a49c conservou duas recusas PCI durante falha do firmware, depois executou native release com sucesso e bus removal stop-error=0. Owners/power/reset ficaram limpos e primary_error=-1 foi conservado. O parser tratou toda recusa histórica como erro do stop e bloqueou o aceite de cleanup.

## Decisão D47

- **Decisão:** transportar ao parser somente o prefixo anterior ao native release proveniente do journal já validado por cleanup_cause. Não alterar o texto bruto nem apagar dmesg. Apenas recusas integralmente presentes nesse prefixo, antes do release e após aquisição, podem ser classificadas como anteriores. Toda recusa posterior continua sujeita à verificação original de stop_error.
- **Por quê:** impede que uma falha anterior seja reportada como falha de remoção e mantém a primeira causa. Um prefixo forjado, outro boot, release incompleto ou owners pendentes continuam recusados.
- **Alternativas:** ignorar todas as recusas com primary_error negativo ocultaria falhas reais e foi descartado; transformar/apagar linhas perderia evidência e foi descartado.
- **Reverter:** baixo; API antiga sem contexto mantém o comportamento anterior.
- **Status:** em curso.

## Arquivos e detalhes

1. scripts/host/n71_scan_held_result.py: cleanup aceita prior_history opcional. Exigir lista bounded canônica de linhas kernel, prefixo exato do log atual e causa negativa; prefixo não pode conter release. Exigir release único completo com owners0, antes de remoção. Separar recusas por linha completa e posição; validar ordem de todas. API sem prefixo permanece estrita.
2. scripts/host/n71_resource_result.py: cleanup_errors aceita schema legado ou schema acrescido de driver_history; somente com driver_error negativo e assignment bem-sucedido. Encaminhar o contexto a held.cleanup sem perder precedência assignment→driver→provider. Contexto ausente não acrescenta flags ao resultado legado.
3. scripts/host/n71_resource_stage.py: somente depois de cleanup_cause validar boot/journal/native release, incluir o histórico da última entrada quando contiver recusas. Não obter contexto do checkpoint atual inteiro nem da entrada externa do CLI.
4. novo tests/test_n71_driver_stop_history.py: helpers e dispatch reais dos testes de cleanup, transporte/hardware modelados. Reproduzir duas recusas anteriores, erro preservado e stop0; erro de stop posterior permanece negativo. Provar prefixo falsificado, release/ordem, owners e causa ausentes/alterados recusados. Baseline e mutações AssertionError, sem tratar exceções de infraestrutura como kill.

5. tests/test_n71_scan_held_result.py: atualizar somente a âncora da mutação existente de preservação de erro do stop para a expressão atual; manter seu teste comportamental legado. A fase toca cinco arquivos executáveis.

## Tarefas

- [x] Implementar cinco arquivos executáveis e gate novo.
- [x] Validar regressões afetadas, AST/lint, Mac/ARM64 e mutações.
- [x] Reexecutar parsers sobre a captura física privada original com o journal original, sem telefone; não forjar conclusão do ciclo antigo.
- [ ] Documentar evidências sanitizadas e publicar na branch autorizada após a CI corrente terminar.
- [ ] Reunir com diagnóstico HDQ e candidata DMA antes de outro DFU.

## Verificação

Preservar bytes de texto/journal recebidos; provas de contexto não podem relaxar causa, cleanup, power/reset, módulo ou descarregamento. Gates antigos dos builders/kernel com inputs inalterados são reutilizados. Não há typechecker Python configurado. Replay do log físico valida o parser; não prova uma nova limpeza remota, reaquisição, Wi-Fi ou carga.

## Resultado da qualificação

Mac/ARM64:64 testes e119 mutações AssertionError por plataforma; novo gate4/10, AST/lint e660 inputs íntegros. Replay do Session real validou14 proofs,3 completions nativas e10 de módulos, mantendo16 arquivos de origem; stop0 e causa-1. Sem novo hardware, sem typechecker Python. Publicação/CI permanecem pendentes. Relatório proporcional ao modo closure da skill agile-status em docs/N71_STOP_HISTORY.md; o goal completo permanece ativo.

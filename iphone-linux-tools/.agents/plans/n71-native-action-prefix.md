# Prefixo real dos eventos nativos N71

## Contexto

A sessão física de 11/10/2026 passou acquire/assign e driver-prepare com exit0. O parser recusou o evento dev_info porque a fixture omitia o prefixo real `n71-pcie-diagnostic 610000000.pcie:`. O intent e os owners permanecem preservados para reconciliação no mesmo boot.

## Arquivos e detalhes

- scripts/host/n71_driver_runtime_result.py: aceitar somente o prefixo exato do dispositivo N71 depois do timestamp; manter unicidade, campos, sufixo e causa.
- tests/test_n71_driver_runtime_result.py: regressão positiva para prepare/publish/release/cleanup e negativas para dispositivo/endereço/prefixo arbitrário, duplicação e texto adicional; mutações que removem suporte ou ampliam origem.
- Este plano: registrar resultado físico e gates.

## Tarefas

- [x] Corrigir e qualificar parser/gates dependentes no Mac.
- [x] Reconciliar intent e continuar/limpar runtime no mesmo boot, dentro de600 segundos.
- [ ] Qualificar ARM64 e publicar evidência sanitizada/pendência.

## Verificação

Unittest e mutações AssertionError do parser, stage e recovery; AST/lint fatal. Reutilizar gates inalterados. Recuperação exige boot/histórico e origem completos, sem reaplicar prepare ambíguo. Não há typechecker Python configurado. Não considerar driver-prepare como prova de rádio ou carga.

## Resultado

31 testes e49 mutações AssertionError por Mac/ARM64; AST/lint aprovados, sem typechecker Python. Intent prepare reconciliado com shell_exit=null e driver publicado no mesmo boot. Duas tentativas de lint com infraestrutura inválida e transferência VM parcial não contaram como gates; execução final qualificada com --jobs=1 e archive completo autenticado. CI/publicação e issue45 aguardam o commit desta fase.

O teste físico encontrou fault DART e timeout do rádio (issue46), recusa do parser de stop por eventos anteriores (issue47) e HDQ EBUSY (issue48). Owners/power/reset limpos em readbacks; unload normal e REG_ON80 verificados em log separado, sem forjar aceite do coordenador. Snapshot e sync salvos; retorno USB iOS não confirmado.

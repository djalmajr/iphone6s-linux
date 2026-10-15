# Cleanup N71 com erro anterior — issue47

## Resultado da correção

O parser agora distingue recusas anteriores do rádio de uma falha no próprio stop, conservando a primeira causa. O replay offline da captura física de11/10/2026 passou: stop_error=0, driver_primary_error=-1 e cleanup_primary_error=-1. Os14 proofs registrados foram conferidos por SHA e os16 arquivos de origem permaneceram intactos. Não houve novo SSH, cleanup remoto, DFU ou reboot.

[Evidência sanitizada](evidence/n71-stop-history-qualified.json), [plano/decisão D47](../.agents/plans/n71-stop-history.md) e [issue47](https://github.com/djalmajr/iphone6s-linux/issues/47).

## Causa e contrato

O firmware falhou antes da remoção e deixou duas recusas PCI no histórico. Mais tarde, native release e bus removal concluíram sem erro de remoção. O parser antigo exigia que toda recusa histórica correspondesse a stop_error negativo e recusava o cleanup correto.

O dispatch só encaminha driver_history depois de cleanup_cause verificar boot, journal, resultado nativo e owners. O prefixo vem da última entrada de native release, antes de seu efeito; nunca do checkpoint atual inteiro ou de um argumento externo do CLI. O parser exige lista bounded de linhas kernel canônicas, prefixo exato do log atual, causa negativa e ausência de release dentro do prefixo. O release completo e único deve preceder bus removal.

Somente uma recusa com a linha inteira naquele prefixo e posição anterior ao release pode ser classificada como anterior. Todas as recusas devem estar entre aquisição e remoção. Uma linha antiga duplicada depois do release continua sendo uma recusa nova. Um evento não comprovado entre intent e release também continua novo. Recusas do stop ainda precisam corresponder ao seu erro negativo. Logs, journals e proofs não são reescritos.

A API interna cleanup_errors mantém o schema antigo; o campo opcional driver_history só é aceito com causa negativa do driver depois de assignment bem-sucedido. Sem contexto, o comportamento anterior permanece estrito. Precedência de assignment/driver/provider e invariantes de reset/power/unload ficam preservadas.

## Verificação

| Gate | Resultado |
| --- | --- |
| Mac |64 testes;119 mutações por AssertionError |
| Ubuntu ARM64 |64 testes;119 mutações por AssertionError |
| Gate novo |4 testes;10 mutações por plataforma |
| AST/lint fatal | aprovados nos5 arquivos executáveis |
| Typecheck | não há typechecker Python configurado |
| Inputs |660 arquivos públicos conferidos antes/depois |
| Replay físico offline |14 proofs;16 arquivos íntegros; sem ação no aparelho |

Helpers, dispatch, journals, parsers e filesystem são reais; o hardware/transporte dos testes são fixtures declaradas. O replay separado usa perfil/identidades e logs reais, com capture remoto explicitamente bloqueado. Uma mutação inicial sobreviveu porque faltava o caso stop=-13 versus recusa=-5; o contraexemplo foi acrescentado antes do gate final. Sobrevivência não contou como kill.

```bash
python3 -B -m unittest discover -s tests -p test_n71_driver_stop_history.py -v
```

A matriz afetada também inclui test_n71_driver_runtime_cleanup, test_n71_scan_held_result, test_n71_resource_result, test_n71_resource_stage, test_n71_driver_runtime_session e test_n71_runtime_reacquire_cli. A âncora de uma mutação existente foi atualizada para a expressão atual, conservando seu teste legado.

Logs, archive/fingerprints, script ARM64 e replay ficam privados em runtime/n71-stop-history-20261015; a VM usa /home/ubuntu/n71-stop-history-20261015. O replay não transforma o checkpoint antigo em uma nova sessão encerrada nem comprova reaquisição física. CI nova e issue47 ainda aguardam aceite.

## Status da entrega

Mudaram três parsers/dispatch e dois testes, todos ligados ao aceite da issue47; não houve ampliação de escopo. Kernel, módulos, banco, dependências instaladas e configuração global ficaram intactos. Desempenho físico não foi medido. Gates inalterados de kernel/builders foram reutilizados; a matriz afetada foi executada em ambas as plataformas.

Próximo: aceite de CI, diagnóstico HDQ (#48) e uma sessão física agrupada com a candidata DMA (#46). Wi-Fi, telemetria/carga e reaquisição (#42) continuam pendentes; não encerrar o goal por este parser.

# Coleta DMA limitada — issue #49

## Contexto e decisão

O perfil pmd-observers-v1 já foi composto e validado localmente. Preparar um leitor antes de driver-publish, com identidade de boot, limite de dados/tempo, arquivos privados e encerramento somente do processo SSH criado. O getter mantém session_lock e device_lock: uma leitura pode aguardar a publicação. Horários registrados são os da leitura efetiva; não representam o instante da falha nem provam tradução física pelo DART.

## Arquivos

- scripts/host/n71_dma_observation.py: comando somente de leitura e parser do protocolo.
- scripts/host/n71_dma_collector.py: processo próprio, prontidão, prazo e preservação dos resultados parciais.
- tests/test_n71_dma_collector.py: contratos, execução local do shell, transições reais de processo e mutações.
- docs/evidence/n71-dma-collector-qualified.json: resultados sanitizados após os gates.

## Tarefas

- [x] Validar boot/ABI/opções antes de anunciar prontidão; limitar a 100 leituras com pausa de 0,1 s ou 20 com pausa de 1 s.
- [x] Preservar máscara de validade, amostras parciais e erros; PA zero não conta como mapeamento.
- [x] Confirmar prontidão antes de permitir publicação; prazo absoluto, término e reap sem retry.
- [x] Dez testes/seis mutações por AssertionError aprovados; shell executado nos dois orçamentos, filhos reais encerrados/reaped, AST e lint aprovados. A primeira mutação de máscara sobreviveu porque o caso completo também era protegido por outra condição; acrescentado caso parcial com máscara inválida e repetido o gate.
- [ ] Integrar a captura ao journal do runtime em uma fase posterior, sem alargar os perfis anteriores.

## Verificação

Executar apenas tests/test_n71_dma_collector.py e lint dos arquivos novos. Fixtures de shell substituem os caminhos fixos por uma árvore temporária; não acessam USB, SSH real, sysfs ou firmware. A integração e o teste físico permanecem pendentes. A VM permanece parada.

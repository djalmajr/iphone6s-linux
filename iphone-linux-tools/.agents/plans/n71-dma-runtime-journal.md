# Integrar captura DMA ao runtime — issue #49

## Contexto

O coletor local passou em dez testes e seis mutações. Integrar somente o perfil com a interface qualificada, imediatamente antes da publicação, preservando a causa primária da ação. Não repetir coleta ao retomar uma publicação já comprovada.

## Arquivos e detalhes

- scripts/host/n71_dma_collector.py: contexto de coleta e receipt verificável, prova privada registrada e validação na retomada.
- scripts/host/n71_driver_runtime_stage.py: registrar a prova adicional somente quando a seleção e o receipt a autorizarem; verificar conteúdo e boot na carga.
- scripts/host/n71_driver_runtime_session.py: envolver a única publicação existente no contexto do coletor.
- tests/test_n71_dma_runtime_journal.py: transição local com filho real, falha primária, persistência/retomada, adulteração e ausência de efeito em perfis anteriores.

## Decisão

O receipt armazena os dados derivados do arquivo bruto privado e o resultado observado do processo. A prova segue o mecanismo existente de cópia/hash do journal. Uma captura com errno ou timeout não demonstra tradução física nem Wi-Fi; não altera o resultado nativo. Falha de captura durante uma exceção de publicação é registrada separadamente e preserva a exceção primária. Falha anterior à prontidão impede publicar e mantém o arquivo original para diagnóstico.

## Checklist

- [x] Integrar sem efeito nos modos anteriores ou na retomada já publicada.
- [x] Provar identidade da Session/SSH, scope da prova, conteúdo e boot. O conjunto de campos nativos usado pela validação em memória não traz result; nesses casos o escopo DMA usa o result da Session atual. Registros persistidos continuam usando seu próprio result.
- [x] Preservar causa primária e encerrar o filho em todos os caminhos.
- [x] Sete testes/cinco mutações por AssertionError aprovados; regressão afetada: 57 métodos/65 mutações aprovados. AST/lint e CLI --check do perfil real com firmware privado aprovados. Modelo de seleção/perfil e telefone; processos e arquivos locais reais. Não houve novo acesso físico.
- [ ] Preparar I2C e o roteiro conjunto antes de pedir DFU.

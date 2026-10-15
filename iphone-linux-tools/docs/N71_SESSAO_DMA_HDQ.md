# Sessão física DMA + HDQ — 15/10/2026

## Resultado

Um DFU iniciou a candidata Linux 7.2 com a janela DMA explícita. A sessão preservou SSH com identidade fixada, HTTP, Herdr e restauração do snapshot. O módulo HDQ novo localizou a recusa no controlador. O firmware Wi-Fi iniciou, mas a tradução DMA continuou falhando. Nenhuma interface WLAN ou leitura válida de bateria foi obtida.

[Evidência sanitizada](evidence/n71-grouped-dma-hdq-20261015.json). Os oito checkpoints do runtime têm o mesmo boot; todos os hashes de proofs registrados e dos checkpoints foram conferidos. Logs, UUID de boot, snapshots, perfis, calibração, firmware e chaves permanecem privados.

| Etapa | Prova observada | Limite |
| --- | --- | --- |
| Baseline | SSH/HTTP/Herdr/restore e brilho baixo | Não prova energia ou rádio |
| I2C inspect | REV 2, SMSTA 08010100 estável, XFSTA zero, idle | Não identifica gauge |
| I2C configure | stage 3, erro -16, CTL salvo 0104, cleanup zero e unload normal | O transporte HDQ não foi atingido |
| Wi-Fi | REG_ON, enlace, recursos e publicação; firmware executado | Publicação não é interface WLAN |
| DMA | fault stream 0, código 2, NO PMD em bfffe000 | Tradução e IRQ do rádio não comprovados |
| Primeiro stop | stop_error 0, cleanup_errors vazio, recursos ausentes | Erro primário -1 preservado |
| Segundo ciclo | reaquisição e reatribuição verificadas, mesmo boot | Não houve segundo start de firmware |
| Segundo stop | stop_error 0, cleanup_errors vazio, recursos ausentes | Erro primário -5 preservado |
| Encerramento | SSH/HTTP, snapshot e sync verificados; última leitura de uptime 449,86 s | iOS confirmado pelo operador; USB não confirmou o retorno |

## Recusa I2C identificada

O código de aquisição grava a baseline antes de recusar CTL com bits fora de 00ff. O valor físico 0104 contém o bit 8 e satisfaz essa condição de recusa. Isso explica a falha local antes de programar o controlador ou enviar o comando HDQ.

Na [fonte PASemi fixada](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/i2c/busses/i2c-pasemi-core.c), CTL_UJM é bit 8, CTL_MTR é bit 9 e CTL_MRR é bit 10. O hash do arquivo foi conferido contra a [qualificação anterior](evidence/n71-i2c-controller-reset.json). Não interpretar 0104 como divisor puro nem como uma leitura de bateria. A origem e a política segura para esse estado inicial ainda precisam ser tratadas na issue #48, preservando ownership, IRQ mask, baseline e recuperação.

O roteiro parou no primeiro erro de configure. Não chegou a read-hdq-control e não emitiu N71_I2C_HDQ_TRACE nesta sessão. A integração do trace de transporte permanece qualificada em fixtures; esta prova física valida o marcador de configuração e a limpeza.

## Janela DMA testada

A candidata mudou somente apple,dma-range para base 80000000 e tamanho 3ffff000. O endereço de fault reportado anteriormente era 3ffff028; nesta sessão foi bfffe000. O novo endereço está dentro da janela inclusiva 80000000..bfffefff. O handler fixado recompõe o endereço reportado com OR dma_min; portanto, essa diferença de base não comprova que o hardware tenha emitido esses bits. A mudança do endereço do fault não comprova correção da tradução, nem determina sozinha a causa da ausência de PMD.

O primeiro comando de inicialização do firmware expirou com -5 e o driver não criou WLAN utilizável. A interrupção do handler de fault DART não é prova de entrega de IRQ do rádio. A issue #46 permanece aberta.

## Recuperação sem outro DFU

Após o primeiro stop, um readback independente confirmou ausência dos módulos de diagnóstico/WCC e dos dispositivos PCI. O CLI aceitou o source stopped, conferiu firmware restaurado, boot e histórico, e realizou outra aquisição e atribuição em diretórios privados novos. A segunda limpeza também terminou sem owners.

Os erros primários -1 e -5 foram preservados mesmo com stop_error zero. Não converter phase=stopped em sucesso do ciclo inteiro. A issue #42 recebeu prova física de reaquisição/atribuição/limpeza; seu segundo start completo de firmware continua pendente.

## Reprodução e encerramento

Usar a [composição DMA](N71_DMA_WINDOW.md) e o [módulo HDQ qualificado](N71_I2C_STAGE.md), com o receipt histórico selecionado explicitamente. O roteiro privado desta sessão está em runtime/n71-hdq-trace-module-20261015/runbook-private.json; capturas e auditoria em runtime/n71-grouped-dma-hdq-20261015a.

Depois do único boot com restore: baseline → inspect → configure; parar HDQ no primeiro erro e exigir cleanup/unload. No runtime: acquire → assign → start → observe → stop → reacquire → assign → stop, com source igual ao output anterior e novo output a cada ação. Não repetir firmware quando a causa ainda for a mesma falha DMA. Verificar módulos/PCI ausentes independentemente e preservar SSH/HTTP.

O snapshot existente foi verificado novamente sem duplicar o backup; sync foi confirmado antes de um único pedido de reboot por software. A enumeração USB não confirmou o iOS, e o operador confirmou a tela de bloqueio. Isso não determina sozinho sucesso ou falha do reboot por software. Tela de bloqueio passa a ser o estado padrão após retorno ao iOS; pedir ação do operador somente quando indispensável.

Power supply e thermal zones continuaram ausentes. Não há prova de carregamento Linux ou medida de bateria. Não houve instalação de pacotes/configuração global do Mac, mudança em contas ou publicação de artefatos privados. O objetivo de Wi-Fi e telemetria funcionais permanece incompleto.

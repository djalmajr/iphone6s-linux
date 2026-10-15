# Sessão física PMD + HDQ/UJM — 15/10/2026

## Resultado

A candidata `7.2.0-iphone6s-dart-serdev-pmd1` iniciou com restore, SSH fixado, HTTP e hook Herdr. Houve um pedido de DFU ao operador. A primeira tentativa do host terminou com erro de acesso USB; a segunda reutilizou o DFU já confirmado, sem novos botões. [Prova sanitizada](evidence/n71-grouped-pmd-hdq-20261015.json).

| Componente | Observação física | Consequência |
| --- | --- | --- |
| I2C inspect | REV 2, SMSTA 08010100 estável, XFSTA zero | Baseline legível; não identifica gauge |
| I2C configure | CTL salvo 0104; stage 3, erro -110; antes era -16 | UJM deixou de ser a primeira recusa; configuração ainda falha |
| I2C cleanup | Owners limpos, erro de cleanup zero e unload normal | Sem comando HDQ nem escrita de valor no carregador |
| Wi-Fi | REG_ON, enlace, atribuição e publicação concluídos | Publicação não comprova rádio |
| DMA/firmware | NO PMD, stream 0, código 2; cur_etheraddr expirou com -5 | A alteração PMD não resolveu o fault; nenhuma WLAN |
| Userspace | iw 6.7, wpa_supplicant/wpa_cli 2.10 executados no aparelho | Loader/bibliotecas isolados funcionam; nenhuma associação |
| Stop | Erro primário -1 preservado; stop_error zero | Cleanup passou; o ciclo funcional não passou |
| Readback independente | Módulos de teste/WCC e dispositivos PCI ausentes; path de firmware restaurado | SSH e HTTP continuaram funcionando |

Os cinco checkpoints e as identidades pertencem ao mesmo boot; hashes conferidos. UUID, chaves, firmware, perfis, snapshots e logs completos permanecem privados. O erro retornado pela operação de publicação/observação não substitui o getter nativo ou o resultado do primeiro comando do firmware.

## DART: hipótese PMD insuficiente

O fault tem status 80000102 e endereço reportado 3ffff028. O kernel inclui o bit 1 da PMD somente no S5L/APPLE_DART. Portanto, a diferença observada na referência Apple não foi suficiente para corrigir este caso. Não concluir que o endereço impresso representa os bits brutos emitidos pelo rádio: o handler continua combinando o valor com dma_min.

Não se repetiu o firmware depois desse erro. O próximo diagnóstico deve confrontar a tradução de software, as tabelas/TTBR visíveis ao hardware e o IOVA durante a primeira falha. É necessário preservar o momento da leitura: após o probe falhar, o driver pode já ter liberado seus buffers. Outra mudança de flags ou de janela sem essa evidência não isola a causa.

## I2C: falta observar a conclusão do reset

O módulo PMD contém a correção UJM já qualificada e o diagnóstico de transporte. O configure retornou timeout, restaurou CTL 0104 e não chegou a read-hdq-control. O valor de CTL nas amostras posteriores ao reset não foi registrado. O próximo desenvolvimento deve expor essas amostras já realizadas, sem acrescentar reads, writes, polling ou ampliar os estados aceitos antes da evidência.

A condição atual aceita CTL 000f ou 070f depois do comando de reset. Um retorno com outros bits, inclusive UJM, é uma hipótese a verificar; esta sessão não mediu esse valor. Não alterar a máscara para converter o timeout em sucesso por suposição.

## Energia e encerramento

O host expôs UsbPowerSinkAllocation=500. Essa propriedade de orçamento USB não é corrente medida da bateria. power_supply permaneceu vazio; não houve telemetria ou prova de carga no Linux. O brilho ficou baixo, sem leitura ou operação do console pelo usuário.

Snapshot e sync foram verificados depois do cleanup. O primeiro comando simples de reboot não encerrou o init do ramdisk, que permanece em loop; foi usado o wrapper existente return_ios.py com backup/sync e reboot de kernel. Esse wrapper foi iniciado antes do corte solicitado de 600 s. O gadget Linux desapareceu, mas a enumeração não confirmou iOS. Aplicou-se a regra de tratar essa ausência como tela de bloqueio, sem pedir confirmação rotineira ou PIN.

## Reprodução e pendências

Usar a [candidata e composição PMD](N71_DART_PMD.md), o diagnóstico I2C PMD cujo hash está na prova, o firmware privado fixado e o pacote userspace autenticado. O roteiro local está em runtime/n71-pmd-grouped-preparation-20261015/runbook-private.json. Sequência: restore → baseline → inspect/configure/read somente se setup passar → cleanup/unload HDQ → acquire/assign/start/observe → stop → readback independente → snapshot/sync → return_ios.py. Cada ação de runtime usa como source a saída anterior e um output novo.

Nenhuma VM ou worker novo foi iniciado; nenhum pacote/configuração global do Mac foi alterado. Permanecem abertas as issues de DMA/Wi-Fi #46, HDQ #48, energia #2, continuidade #42 e userspace/associação #44. O goal funcional continua incompleto. Reunir a próxima instrumentação antes de outro DFU.

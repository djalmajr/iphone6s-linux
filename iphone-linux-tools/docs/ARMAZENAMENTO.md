# Armazenamento interno do iPhone 6s — #10

## Resultado atual

O Linux comprovado executa em RAM; o armazenamento interno de 32 GB não foi exposto como dispositivo de bloco. Persistência é por snapshots privados no Mac e restore após DFU. O conteúdo que o iOS consegue gravar não torna esse controlador automaticamente acessível ao kernel Linux.

A candidata de fonte `7.2.0-iphone6s-source` foi examinada sem boot novo. No commit `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, o [driver Apple NVMe](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/nvme/host/apple.c#L1696) tem matches ANS2 para T8015/T8103 e um fallback com dados T8103. Não foi encontrado match/topologia N71 comprovado na cadeia examinada. Isso delimita a fonte atual; não prova que o controlador A9 seja impossível de implementar.

| Camada | Evidência e requisito pendente |
|---|---|
| Controlador real A9 | Identidade/revisão, firmware e interface ainda precisam de dados privados da placa N71; não atribuir ANS2/T8010 ao A9 por semelhança de nomes. |
| Device tree | DTB compilado com 136 nós, sem controlador de disco ANS/NVMe/SART/MMC/UFS/NAND correspondente. Endereços, interrupts, clocks, energia e DMA continuam pendentes. |
| Configuração | `BLK_DEV_NVME`, `NVME_APPLE`, `APPLE_RTKIT`, `APPLE_SART` e `APPLE_MAILBOX` como módulos; a imagem selecionada não contém `.ko`. Ativar uma opção não fornece a topologia do hardware. |
| NVMEM | `CONFIG_NVMEM=y` e `apple,pmic-nvmem` descrevem pequenas células do PMIC/RTC, não o disco do telefone. A busca inicial por substring `nvme` também encontrou `nvmem`; os três nós foram separados antes da conclusão. |
| Filesystem | ext4 está incorporado, mas isso só serve depois de existir um dispositivo de bloco confiável. Nenhum filesystem interno foi criado ou montado. |

[Fontes fixadas, hashes e inspeção](evidence/storage-boot-n71.json). A [prova A10 do fork](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/README.md) é J172/D111; não estabelece compatibilidade N71. O [tutorial gdisk](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/tutorials/gdisk.md) opera a partir de iOS com jailbreak e menciona o mapeamento Linux A11. Alterar GPT por esse caminho não cria um driver A9. Nenhum comando daquele tutorial foi executado.

## Desenvolvimento e critérios de prova

1. Após boot selecionado com USB/SSH funcionando, fazer inventário read-only de `/sys/block`, `/sys/class/nvme`, `/proc/partitions`, compatibles em execução e logs de probe. Loop/zram ou células NVMEM não contam como storage interno. Não montar partições, fazer fsck, resetar controlador ou enviar comandos de escrita nesta detecção.
2. Identificar privadamente o controlador N71 e seu firmware/topologia, com origem e integridade dos insumos. Mapear energia, DMA/IOMMU, filas e boot do controlador antes de propor driver/configuração. Não usar dumps de outros SoCs como mapa validado.
3. Em candidata separada compilada na VM, validar enumeração, capacidade/sector size e leitura controlada. Preservar USB e recovery. O driver pode executar inicialização de hardware; leitura de blocos sem comando de escrita não equivale a ausência de efeitos do probe.
4. Somente com driver, geometria e recuperação comprovados planejar um filesystem persistente. O requisito atual é investigar/detectar/ler; particionamento, formatos e escrita interna seguem fora desta fase. Nenhum fakefs, `resize_apfs`, `gdisk` ou `dd` será aplicado por analogia com A10/A11.

A issue #10 continua aberta: o controlador específico e a detecção/leitura nativas não foram comprovados. Snapshot no Mac conserva os arquivos recuperáveis, mas não estabelece independência do host. Persistência interna e [boot autônomo](BOOT-AUTONOMO.md) são gates separados.

## Atualizar o Linux existente

A receita atual gera uma nova imagem/payload privados na VM e seleciona um perfil com chaves correspondentes; não formata o telefone. Salvar e verificar snapshot, iniciar a candidata por DFU supervisionado, restaurar dados e validar serviços. Para voltar, retornar ao iOS pelo procedimento de [recuperação](REBOOT.md), selecionar a implantação anterior preservada e repetir DFU/restore. Não misturar perfis, kernel e módulos de outra ABI. A nova cadeia de kernel/Pongo ainda precisa piloto/rollback físicos (#12/#21).

Para repetir a inspeção estática, conferir os hashes da evidência, examinar DTB com `dtc` na VM e buscar os compatibles acima, ler a tabela do driver no commit exato e conferir as opções `.config`. A receita de listagem newc sem extração está em [WIFI.md](WIFI.md). Nenhum pacote, mount do Mac, VM ou operação de NAND foi necessário nesta pesquisa.

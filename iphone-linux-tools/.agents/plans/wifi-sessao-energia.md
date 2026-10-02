# Wi-Fi, sessão SSH e energia — execução autorizada

## Contexto

O operador autorizou os três pontos em 2026-10-02. Direção: mínima reinicialização e desenvolvimento solo. Linux 7.2 responde por SSH; preservar o boot existente. #9 requer topologia N71; #32 requer atualização reversível de serviço; #2 não tem sensor/driver de carga comprovado.

## Fases e arquivos

1. Insumos Wi-Fi/energia: obter DeviceTree N71 de distribuição Apple documentada, manter dados brutos em runtime privado e analisar offline. Comparar barramento/DMA/PMIC/gauge com drivers da fonte. Não executar ferramentas baixadas no Mac nem programar registradores do telefone.
2. Sessão (cinco arquivos públicos): este plano; scripts/host/dev.py; phone/dev/update-dns.sh; tests/test_dev.py; tests/run_dev_mutations.py. Primeiro serviço: DNS já disponível no projeto. Transferir hosts e manager versionado, destinos fixos, SHA256, validação de links/tipos, lock, cópia anterior e rollback. Checkpoint privado antes; confirmar uptime/SSH e resposta DNS após; só reiniciar o DNS. Nenhum DFU implícito.
3. Documentação (até cinco arquivos): docs/DESENVOLVIMENTO.md, docs/WIFI.md, docs/ALIMENTACAO.md e evidências sanitizadas de sessão e topologia/energia. Atualizar #9/#32/#2/#17; publicar na branch de trabalho autorizada, sem merge/tag/release.

## Decisões

- Primeiro updater específico DNS, em vez de executor genérico arbitrário. Adicionar outros serviços exige destinos/lifecycle declarados. Atualização de hosts deve aceitar somente registros privados home.arpa, com arquivo local regular sem links e tamanho limitado.
- Artefato oficial da Apple serve como referência de placa, não prova da revisão/calibração deste aparelho. Metadata de índice externo só localiza a URL Apple. Não usar o artefato para restaurar/flashear.
- Se não houver mapa A9 validado, registrar os campos conhecidos e as lacunas; não substituir parâmetros T8010 no S8000. Hardware exige uma candidata offline e um boot agregado posterior, se tecnicamente preparado.
- Reutilizar checagens existentes que não mudaram. Testar os novos limites de transporte/rollback com comportamento real e mutações por asserção; não contar erro de fixture como kill.

## Tarefas

- [x] Obter/analisar insumo Apple N71 offline; registrar proveniência, hashes e limites.
- [x] Mapear Wi-Fi e energia até os bloqueios concretos de drivers/topologia.
- [x] Implementar updater DNS/checkpoint/rollback da sessão SSH.
- [x] Provar positivos, erro parcial, integridade, destino/link/lock inválido e mutações críticas local/VM.
- [x] Provar deploy e rollback no mesmo boot do telefone, preservando SSH/kernel/uptime e DNS UDP/TCP.
- [ ] Atualizar documentação/issues e publicar resultados, conservando hardware/energia não comprovados como abertos.

## Verificação

Usar perfil explícito, identidade SSH presa, backup/persistência existentes. Logs e snapshots privados. Nenhum pacote no Mac, política global de rede/sudoers, escrita de NAND, firmware/driver por hipótese ou encerramento de sessões alheias. AST/lint fatal não equivalem a typecheck; projeto não tem typechecker configurado. Testes de fixture não equivalem a hardware. Wi-Fi só conclui com rádio enumerado/associação/DHCP; energia só conclui com telemetria/medição sustentada validada.


## Fase de orçamento USB identificada no ponto 3

O boot real reportou MaxPower2 em configfs. As duas fontes de init não atribuem orçamento antes do bind; não confundir isso com corrente medida. Correção específica: declarar500mA/atributo bus-powered0x80 antes de selecionar/bindar UDC, em init e init-server. Cinco arquivos nesta fase: este plano, as duas fontes de init, tests/test_usb_budget.py e tests/run_usb_budget_mutations.py. Fixtures executam o trecho real de configuração com observação do orçamento no momento de descobrir UDC; mutações retiram os dois campos ou os movem para depois dessa descoberta. Não mudar kernel/driver, desbindar USB ou reiniciar o telefone nesta fase. Novo initramfs/piloto físico ficam separados; fonte corrigida não altera a imagem já em RAM.

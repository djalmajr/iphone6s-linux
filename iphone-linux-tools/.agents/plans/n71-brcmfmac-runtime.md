# Modo PCI para o brcmfmac N71

## Contexto

Demanda aprovada: Wi-Fi nativo e energia, em sessão Linux agrupada, com o mínimo de DFUs. O modo MSI de diagnóstico mantém COMMAND decode/MASTER desligados; o brcmfmac usa `pci_enable_device`, `pci_set_master`, BAR0_WINDOW, mailbox e firmware assíncrono. Aplicar esse modo ao driver recusaria o probe. A revisão física já identificou chip4350/revisão8; não pedir outro boot para identificá-lo.

A fonte fixada958481f fornece a barreira de lifetime: `request_firmware_nowait` mantém referências ao módulo e ao device até depois do callback. O unload normal recusa referências ativas e executa remove antes de terminar. Carregar um módulo ou retornar0 do probe não comprova conclusão do firmware, interface ou rádio. Não usar unload forçado nem unbind manual durante firmware pendente.

## Arquivos e fases

1. `phone/kernel/n71-brcmfmac-config.h`, `tests/n71_brcmfmac_config.c`, `tests/test_n71_brcmfmac_config.py`, este plano e decisões: contrato de configuração usado pelo driver, com capture/readback/restore. Compilar o código real e mutantes nos dois sistemas e no contexto do kernel ARM64.
2. Adapter de runtime, scan e caller: opt-in explícito após recursos atribuídos, MSI/DART associados e energia retida; habilitar somente os dois devices N71. Recusar cleanup do bus enquanto o modo estiver ativo. O brcmfmac aloca/libera seu próprio vetor; não misturar a lease MSI de diagnóstico. Qualificar callers/adapters/build antes de seleção.
3. Host/journal/perfil: intenção antes de cada efeito, módulos e firmware privados por hash, acompanhamento do firmware/interface/IRQ/DART e unload normal antes de release. Preservar parsers/defaults legados. Requerer prova de rádio, não apenas probe0.
4. Firmware/calibração correspondente e energia/HDQ: preparar as dependências offline, agrupar a sessão física, scan/associação/DHCP/SSH por Wi-Fi e coletas de energia; salvar snapshot/sync e retornar ao iOS para recarga quando necessário.

Cada commit toca no máximo cinco arquivos públicos. Nenhum pacote/configuração global do Mac, kernel/config/Image/exports, perfil físico, autoload ou firmware público será alterado nesta fase.

## Detalhes da fase1

Capture separado conserva COMMAND dos dois devices, MSI, BAR0_WINDOW e Link Control do endpoint, com identidade/capability/PMCSR D0 e decode/MASTER inicialmente desligados. O runtime aceita os writes do driver fixado e do core PCI: COMMAND16 sem IO, PMCSR idêntico, um grant MSI/mensagem AIC, BAR0_WINDOW alinhado, mailbox1 e Link Control. O write DWORD de Link Control vira WORD para não reenviar STATUS W1C. Doorbell não vira noop mesmo se sua leitura repetir1. Falhas conservam a primeira causa e não impedem operações permitidas de teardown.

Restore exige ausência de driver registrado/bound, MSI software e grants/mappings. Depois verifica identidade, desabilita MSI/decode/MASTER, restaura mensagem/window/link/COMMAND e verifica todos os baselines antes de liberar o owner. Erro ou drift conserva o owner para retry. Esse contrato não substitui a API PCI nem garante stop-before-free se o hardware falhar durante o remove upstream; o erro de write/readback será conservado e impedirá declarar o experimento bem-sucedido. O caller deve conservar energia/providers até restore verificado.

## Tarefas

- [x] Implementar política runtime e regressões/mutações compiladas.
- [x] Qualificar Mac/Ubuntu ARM64 e objeto real do kernel, preservando baseline.
- [ ] Integrar adapter/caller e cleanup retido, sem ativação automática.
- [ ] Integrar journal/seleção/firmware/energia e candidata agrupada.
- [ ] Comprovar Wi-Fi e telemetria/carga fisicamente; atualizar issues9/2/40.

## Verificação

Testar recusas sem IO, grants/messages incorretos, MASTER/decode permitidos somente no modo ativo, W1C preservado, doorbells repetidas, readback falho, erro positivo normalizado, primeira causa, owner retido/retry e baseline completo. Mutações devem compilar e morrer por asserção; compilação/timeout não contam como kill. AST/lint fatal dos inputs Python. Objeto W=1/Werror contra kernel power2 preservado, sem MODPOST_WARN/instalação. Nenhum typechecker Python configurado. Prova offline não comprova IRQ entregue, tradução DMA, firmware compatível, rádio ou carga Linux.

Fase1:58 cenários/23 mutações compiladas por plataforma, AST/lint fatal aprovados. Probe ARM64 real11.184 bytes/SHAbcb2b125, ELF/vermagic e dois imports conferidos; os sete inputs e fonte/config/Image/exports foram conservados e o binário foi auditado no Mac. O primeiro ensaio da fixture falhou porque a injeção de drift usava uma leitura posterior ao fim do capture; corrigida para a segunda leitura de BAR0_WINDOW e gates repetidos. Nenhum kill dessa rodada inválida foi usado como prova. O probe somente compila as três funções reais; não é caller, driver ou teste físico. Nenhum módulo/perfil/carga/DFU alterado. Próxima tarefa: integrar o contrato ao scan/adapter/caller retido, antes do journal e da candidata física agrupada.

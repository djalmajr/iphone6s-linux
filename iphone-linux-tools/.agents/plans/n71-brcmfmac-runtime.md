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

## Detalhes da fase2

Fase2a (cinco arquivos): este plano, `phone/kernel/n71-pcie-scan.h`, novo `phone/kernel/n71-pcie-brcmfmac.h`, `tests/n71_pcie_brcmfmac.c` e `tests/test_n71_pcie_brcmfmac.py`. Integrar estado/configuração ao host, callbacks ECAM/enable e guarda de consumer removal. Adapter retém referências PCI dos dois devices e runtime PM sem transição de hardware; usa `device_set_driver_override` exportado pelo kernel7.2 para root=`none` e endpoint=`brcmfmac`, antes de `pci_bus_add_devices`. Publicação é explícita/separada e não comprova fim do firmware. Release requer unload normal/nenhum driver registrado ou bound, software MSI/grants/mapcounts zerados e contadores enable0/1; balanceia enables PCI, restaura configuração, limpa só overrides próprios/verificados, balanceia PM e libera refs. Falha/ownership parcial conserva o host para retry. Usar APIs públicas/exports existentes; não acessar private driver data nem escrever diretamente driver_override.

Fase2b, antes de selecionar/carregar: guarda de exclusão mútua no adaptador MSI manual e fixture; caller com opt-in, prepare/publish/release/getter e cleanup serializados; fixtures específicas e build completo em fatias subsequentes de até cinco arquivos. Não publicar/selecionar a candidata física só com o adapter: o caller e journal ainda precisam provar uso ordenado e causalidade dos erros. Gate de host legado deve continuar passando; `.enable_device` continua recusando o default.

Fatia2b1 (cinco arquivos: este plano, scan, adapter e duas fixtures runtime): reunir active/refs/PM/overrides em `n71_scan_driver_pending`, usado por consumer removal e adapter. Conservar owners parciais mesmo com active/refs zerados; capturar erro assíncrono de publish sob o lock do host depois da API de presença. Qualificar somente o gate runtime afetado, preservando a política e os gates legados cujos contratos não mudarem.

Fatia2b2 (três arquivos: adaptador MSI manual e fixtures C/Python correspondentes): recusar acquire e release manual quando o predicado runtime estiver pendente, antes de power/config/core IRQ. Fixture compila o predicado real extraído; testar os seis owners parciais sem efeitos, com mutations de remoção das guardas. Não criar outro predicado.

Fatia2b3 (cinco arquivos: diagnóstico, novo caller runtime, fixture de caller, fixture focada runtime e wrapper Python): `driver_runtime=false` por default e dependência de scan_hold/MSI/IOMMU; actions `driver-prepare`, `driver-publish`, `driver-release`. Sem prepare no probe ou autoload de firmware. Actions retêm pin/lock/power/DART; publish registra intenção e não readiness. Release/cleanup admitem erros anteriores, conservam primeira causa e só removem consumidores depois de pending=false. Getter `driver_runtime_status` separado, só observação sob locks, preservando formatos anteriores. O caller novo não deve elevar sucesso de insmod/publicação a Wi-Fi pronto. Corrigir a fixture DART isolada numa fatia própria se a extração precisar das dependências novas; manter sua cobertura específica.

Depois de todos os gates nativos, compilar diagnóstico completo contra power2 preservado e auditar exports/ELF/vermagic/hashes; nenhuma seleção/carga/DFU antes de journal/seleção e preparação de firmware/energia. Defaults/módulos/perfis anteriores ficam disponíveis.

## Tarefas

- [x] Implementar política runtime e regressões/mutações compiladas.
- [x] Qualificar Mac/Ubuntu ARM64 e objeto real do kernel, preservando baseline.
- [x] Integrar adapter/callbacks e guarda de consumer removal; qualificar sem ativação automática.
- [ ] Integrar caller/opt-in/actions/getter e exclusão mútua MSI, com cleanup retido.
- [ ] Integrar journal/seleção/firmware/energia e candidata agrupada.
- [ ] Comprovar Wi-Fi e telemetria/carga fisicamente; atualizar issues9/2/40.

## Verificação

Testar recusas sem IO, grants/messages incorretos, MASTER/decode permitidos somente no modo ativo, W1C preservado, doorbells repetidas, readback falho, erro positivo normalizado, primeira causa, owner retido/retry e baseline completo. Mutações devem compilar e morrer por asserção; compilação/timeout não contam como kill. AST/lint fatal dos inputs Python. Objeto W=1/Werror contra kernel power2 preservado, sem MODPOST_WARN/instalação. Nenhum typechecker Python configurado. Prova offline não comprova IRQ entregue, tradução DMA, firmware compatível, rádio ou carga Linux.

Fase1:58 cenários/23 mutações compiladas por plataforma, AST/lint fatal aprovados. Probe ARM64 real11.184 bytes/SHAbcb2b125, ELF/vermagic e dois imports conferidos; os sete inputs e fonte/config/Image/exports foram conservados e o binário foi auditado no Mac. O primeiro ensaio da fixture falhou porque a injeção de drift usava uma leitura posterior ao fim do capture; corrigida para a segunda leitura de BAR0_WINDOW e gates repetidos. Nenhum kill dessa rodada inválida foi usado como prova. O probe somente compila as três funções reais; não é caller, driver ou teste físico. Nenhum módulo/perfil/carga/DFU alterado. Próxima tarefa: integrar o contrato ao scan/adapter/caller retido, antes do journal e da candidata física agrupada.

Fase2a:24 cenários/23 mutações novas e host183/147 por plataforma, total207/170; AST/lint fatal aprovados. Mac conservou os quatro métodos intactos e retomou só os dois com âncoras antigas afetadas pelo callback/guarda; VM executou os seis métodos. Não contar ambiguidade de âncora, SIGSEGV inicial da fixture ou erro de staging como kill. O callback agora verifica a referência antes de acessar o bus; a fixture modela pci_disable_device sem retorno de erro e exige readback no restore. O helper is_added é privado ao core PCI7.2, portanto não foi usado: published registra intenção emitida e `pci_device_is_present` só comprova resposta ao config, não fim de registro/binding/firmware. Reads de runtime têm contador próprio e não consomem o orçamento finito de scan/rollback.

Diagnóstico completo ARM64:129.416 bytes/SHA2c743b7d,127 imports; probe de adapter+diagnóstico real137.368 bytes/SHAb7340c49,135 imports incluindo cinco APIs públicas novas. ELF/vermagic/bytes/hashes foram conferidos no Mac;63 inputs e fonte/config/Image/exports conservados. Lint VM encontrou diretório scripts ausente no staging; criado apenas esse diretório e retomado o lint/auditoria, preservando gates/build já aprovados. Nenhuma seleção, carga, publicação PCI física, firmware ou DFU. Próximo gate obrigatório antes do aparelho: fase2b caller/exclusão MSI; depois journal/seleção/firmware/energia e prova física agrupada.

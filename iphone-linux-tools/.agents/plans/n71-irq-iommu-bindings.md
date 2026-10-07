# IRQ/IOMMU N71 — issue40

## Contexto

[Issue39](https://github.com/djalmajr/iphone6s-linux/issues/39) concluída; [prova física b50e65b](../../docs/evidence/n71-pci-pref64-unsized-physical.json). Host retido e BARs atribuídos, reuso/cleanup/serviços/snapshot/iOS passaram. Decode/master/driver/radio desligados. Inventário IRQ255/0 e ausência de links of_node/IOMMU sem bind não é prova de defeito nessas camadas. [Issue40](https://github.com/djalmajr/iphone6s-linux/issues/40) integra Wi-Fi#9; energia/carga/gauge permanecem na#2.

## D1. Conferir o lifecycle real antes de acrescentar associações

- **Decisão:** investigar hooks do PCI, DT e provider existente antes de alterar associações ou liberar driver/DMA. Ausência de sysfs no modo sem bind não justifica, sozinha, acrescentar um nó ou chamar configure DMA.
- **Por quê:** `pci_dma_configure` da fonte958481f usa o OF node do parent do host e só usa domínio default para driver sem managed DMA. A fonte separa aquisição simples de bridge da inicialização OF devm. O diagnóstico usa bridge simples com enable negado; provider DART foi validado em ciclo temporário, sem attachment PCI permanente.
- **Alternativas:** preencher OF/fwnode apenas para aparecer em sysfs não prova o caminho DMA; usar driver T8103 no A9 presume registradores não comprovados; iniciar brcmfmac agora mistura IRQ/DMA/firmware e amplia o risco de perder observabilidade. Rejeitados.
- **Reverter:** baixo na investigação; próximo opt-in precisa de cleanup/rollback e perfil por SHA.
- **Onde:** fontes/arquivos abaixo e prova privada sanitizada. Sem modificar hardware nesta fase.
- **Status:** em curso offline; não precisa de PIN, DFU ou operação do console para a investigação inicial.

## Arquivos e fontes a conferir

- `phone/kernel/n71-pcie-scan.h:368`: parent, callbacks, enable negado e registro/scan; `n71-pcie-resource-assign.h` mantém a atribuição já comprovada.
- `phone/kernel/n71-dart-provider.h:54`: IRQ248/provider temporário, ownership/stop; `n71-dart-cycle.h` e `n71-dart-mmio.h` mantêm snapshot/restauração.
- `scripts/build/prepare-n71-topology.py:124`: topologia atual declara PCIeIRQ244/247/250/253 e DART248; isso não identifica por si só semântica INTx/MSI/port status.
- Fonte fixada958481f na VM: `drivers/pci/probe.c:685–727` (alloc vs devm/OF), `drivers/pci/of.c:638–649` (swizzle/map_irq), `drivers/pci/irq.c:142–175` (assign), `drivers/pci/pci-driver.c:1668–1700` (DMA), driver Apple e brcmfmac PCIe, bindings e DTS.
- Reutilizar [módulos Wi-Fi](../../docs/evidence/n71-wifi-binding-modules.json), [seleção de firmware](../../docs/evidence/n71-firmware-selection.json) e perfis anteriores; não repetir builds com inputs relevantes intactos. Firmware/calibração e DT bruto ficam privados.
- F1a: `phone/kernel/n71-wlan-irq-reference.h`, `tests/n71_wlan_irq_reference.c`, `tests/test_n71_wlan_irq_reference.py`. Validar topologia N71 e produzir somente índice lógico/número AIC/células Linux; sem alocar IRQ/domain nem produzir message data.

## Detalhes e fases

F0 somente leitura e plano (até cinco arquivos públicos): auditar fontes/config/exports, extrair da topologia e logs privados apenas referências técnicas, distinguir capability de rota, mapear chamadas automáticas e o lifecycle dos providers. Documentar o que falta e a decisão da próxima candidata antes de código.

F1 opt-in com ownership separado (cada fatia até cinco arquivos): apenas depois de provas primárias da rota/cells/streams. Manter defaults diagnósticos e recusar mismatch; planejar refs, domains, mapping preexistente, teardown e retry. Não permitir driver/MASTER/DMA sem attachment comprovado. Testes de callbacks precisam observar associação/cleanup, não apenas contagem.

F2 composição/build e integração (até cinco por fatia): fonte/config/Image/exports/REG_ON preservados quando possível, novo SHA/contrato explícito; perfis antigos continuam válidos. Qualificar Mac/Ubuntu/Werror/modpost/ABI/AST/lint e mutations por assertion. Compiler/import/timeout não são kills.

F3 hardware: um boot com todas as coletas/estágios preparados; SSH/Bash/Herdr/HTTP preservados, snapshot/sync e iOS ao fim. Sem DFU/PIN novo para operações que possam ocorrer na mesma sessão. Não pedir temperatura; operador avisa se houver mudança.

## Tarefas

- [x] Criar issue40 com critérios e dependências.
- [x] Confirmar na fonte fixada os hooks de alloc/OF/IRQ/DMA e ler o lifecycle do provider existente.
- [x] Recuperar pin1/MSI64/capability física do log já salvo, sem novo boot; fixar ADT32/offset256/porta1/base8/count8, registro AIC264..271 e células Linux.
- [ ] F0: fechar a identificação de INTx/MSI/cells/streams e as provas ainda necessárias; guardar hashes/recortes privados e relatório sanitizado.
- [x] F1a: qualificar o cálculo de requisição AIC isolado no Mac/Ubuntu e contexto kernel, sem integração física.
- [ ] F1: definir e implementar a candidata em fatias qualificadas.
- [ ] F2: build/seleção/composição/check e reprodução.
- [ ] F3: comprovar no hardware associações/IRQ e teardown, antes de rádio funcional.

## Verificação

Nenhuma modificação de firmware/NAND, credenciais de rede, pacote/configuração global do Mac ou coisas remotas. Manter USB-A traseiro. Linux em RAM não oferece carga/gauge comprovados; desenvolver/buildar com telefone no iOS carregando. Inventário, associação, entrega IRQ, DMA e rádio são provas distintas. Não há typechecker Python; AST/lint fatal e contratos são necessários, C com Werror.

## Auditoria inicial salva

[Fatos e fontes fixadas](../../docs/N71_IRQ_IOMMU.md). Confirmados alloc simples vs devm/OF, map_irq, DMA configure pelo parent, enable/MASTER/IRQ no brcmfmac e provider DART temporário. Sem carregar driver ou alterar hardware. Fechar semântica INTx/MSI e mapping N71 continua pendente antes de código.

## D2. Preparar MSI e qualificar primeiro somente as células do parent AIC

- **Decisão:** caminho MSI para o WLAN; primeira fatia F1a valida32/offset256/porta1/base8/count8 e calcula `<0, 264 + índice, 1>`, índice0..7. Não declara message data ou virq como equivalentes ao número AIC. F0 e a integração ativa continuam abertas até fechar esses contratos.
- **Por quê:** capacidade MSI já medida; registro Apple do parent soma offset256 ao vetor lógico. Linux usa células e hwirq distintos do ADT Apple. Esse cálculo pode ser verificado offline sem outro DFU, independente das escritas do controlador.
- **Alternativas:** INTx exige rota ainda não comprovada; copiar domínio/offsets M1 para S8000 presume equivalência; registrar driver agora mistura MASTER/DMA/firmware. Rejeitadas nesta etapa.
- **Reverter:** baixo; helper isolado, sem caller/autoload ou alteração do perfil.
- **Onde:** arquivos F1a acima; [referência sanitizada](../../docs/evidence/n71-irq-iommu-reference.json), sete recortes por digest. Doc/status/referência/plano compõem a fase de auditoria, quatro arquivos públicos.
- **Status:** helper F1a passou61 cenários/14 mutações compiladas por assertion no Mac e Ubuntu ARM64, AST/lint fatal e probe kernel Werror/modpost/ELF/vermagic. O runner VM procurou inicialmente `Module.symvers`, ausente; foi corrigido para `vmlinux.symvers`/`KBUILD_EXTRA_SYMBOLS` antes dos testes. Fonte/config/Image/exports preservados; módulo de prova não carregado. Message data, ownership/restore MSI e provider DART retido permanecem pendentes; nenhuma integração de hardware por esta decisão.

## D3. Reter o provider DART e seu rollback na sessão nativa

- **Decisão:** integrar aquisição/retorno do provider ao estado persistente do diagnóstico, com ações explícitas `dart-hold` e `dart-release`. Cleanup deve concluir o DART antes de remover o barramento, GPIO e referências de energia; falhas conservam estado e permitem tentar novamente na mesma sessão.
- **Por quê:** o ciclo atual usa uma struct local e libera MMIO/node/claim mesmo quando stop ou restauração falham. Isso perde o owner necessário para recuperar. O provider precisa permanecer registrado para a associação PCI posterior. A próxima fatia corrige esse lifecycle sem habilitar MASTER, DMA ou rádio.
- **Alternativas:** repetir o ciclo e reiniciar o telefone perde estado e exige DFU; liberar o provider imediatamente impede attachment; iniciar brcmfmac mistura gates ainda não comprovados. Rejeitadas.
- **Reverter:** baixo antes da prova física; sem autoload ou mudança de perfil. O caminho temporário continua disponível com o mesmo contrato de sucesso.
- **Onde:** F1b toca somente este plano, `phone/kernel/n71-dart-lease.h`, `n71-dart-provider.h`, `n71-pcie-mmio.h` e `n71-pcie-diagnostic.c`. F1c qualifica cenários de aquisição/rollback/retomada com falhas e callbacks reais do backend, build Werror/modpost e reprodução sanitizada.
- **Status:** implementação e qualificação offline concluídas nos commits c0fb252/003998d. Mac e Ubuntu ARM64 passaram92 cenários/32 mutações compiladas por asserção; módulo completo passou W=1/Werror/modpost/ELF/vermagic, com fonte/config/Image/exports preservados. Preparar o módulo não libera seu uso físico: ownership IRQ, efeitos de mask/free e baseline/restore ainda devem ser qualificados antes de carregar.

### Contratos F1b/F1c

- [x] Estado retido desde antes do start, inclusive probe parcial e stop/claim/restauração com erro.
- [x] Salvar baseline uma vez, impedir aquisição duplicada, retomar TTBR no primeiro índice não confirmado e verificar todas as palavras ao final. Tentativa de cleanup tem orçamento próprio; não reiniciar nem repetir writes já confirmados sem divergência medida.
- [x] `dart-hold` exige host retido, recursos atribuídos e sessão sem erro; `dart-release` preserva host/energia para outros testes. `cleanup` bloqueia remoção PCI/reset/power enquanto houver DART pendente. Getter separado não muda o formato dos getters já usados.
- [x] Qualificar falhas antes/depois de start, stop, reads, guards e cada write; idempotência/ownership/retomada e mutações compiladas por asserção, Mac/Ubuntu e módulo nativo completo. Não contar build/import/timeout como kill.
- [ ] Fechar ownership IRQ antes de qualquer boot da nova candidata; `irq_set_handler(NULL)` pode mascarar o AIC no free, portanto não é operação exclusivamente de software.

## D4. Qualificar IRQ antes de compor o perfil físico retido

- **Decisão:** próxima fatia fecha aquisição atômica e teardown/máscara da IRQ248 e dos parents MSI. Não compor/carregar o perfil retido até esse gate; o seletor atual continua nos hashes físicos anteriores.
- **Por quê:** o backend herdado consulta mapping antes da criação, fora de uma aquisição atômica. A fonte fixada também mostra que liberar o handler pode mascarar o parent. Fixtures e ABI não provam concorrência ou preservação de máscaras reais.
- **Alternativas:** considerar lookup anterior ownership suficiente deixa uma corrida; declarar alloc/free sem efeito físico contradiz `kernel/irq/chip.c`; pedir outro DFU agora não resolve o contrato. Rejeitadas.
- **Reverter:** baixo, código opt-in sem mudança de perfil/DT/Image. O módulo anterior continua disponível.
- **Onde:** issue40, `phone/kernel/n71-dart-provider.h`, APIs AIC/irqdomain fixadas e próximo collector. [Qualificação e limites](../../docs/evidence/n71-dart-retained-qualification.json).
- **Status:** na fila de implementação; F0/F1 globais, F2 seleção/perfil e F3 físico continuam abertos. Nenhum novo DFU, PIN ou reboot nesta rodada.

## D5. Domínio privado hierárquico para a IRQ248 do DART

- **Decisão:** substituir lookup/criação/reuso por domínio privado abaixo do AIC. O callback alloc verifica ausência de mapping e chama alloc do parent sob o mesmo root mutex do IRQ core; recusa conflito. O provider recebe somente o virq que esse domínio criou. Stop remove o dispositivo antes de liberar IRQ/domain/fwnode e conserva o owner se handler/IRQ ainda estiver ativo.
- **Por quê:** callbacks de alloc hierárquicos rodam dentro de `irq_domain_alloc_irqs` com o mutex do root. AIC fixado inicializa todas as IRQs mascaradas; ausência de mapping sob esse lock é uma precondição de baseline derivada da fonte. Probe pode abrir a IRQ e remove/free_irq deve fechá-la; não declarar readback de máscara ou alloc/free sem MMIO.
- **Alternativas:** reutilizar mapping preexistente mistura owners; bloquear manualmente o root e chamar create_mapping recursivamente pode deadlock; escrever AIC por MMIO presume efeitos de registradores ainda não qualificados. Rejeitadas.
- **Reverter:** baixo antes do hardware, nenhuma alteração de FDT/Image/perfil/autoload. O ciclo passa a recusar IRQ previamente mapeada.
- **Onde:** F1d: este plano, `phone/kernel/n71-dart-irq.h`, `n71-dart-provider.h`, `n71-pcie-diagnostic.c` (até quatro arquivos). F1e: fixtures de callbacks reais/IRQ lock/conflict/retry e build completo na VM; publicações sanitizadas em fatia separada.
- **Status:** aplicada e qualificada offline. Células0/248/4 e hwirq100f8 da fonte fixada; parent deve ser root hierárquico AIC1. MSI permanece separado até integrar a sua mensagem/domínio. [Prova selecionada](../../docs/evidence/n71-dart-irq-qualification.json).

### Contratos F1d/F1e

- [x] Checagem de conflito dentro do callback sob root mutex; nenhuma mutação/reuso/dispose de mapping alheio. Prova pela fonte/protocolo e fixtures; sem claim de concorrência física global.
- [x] Um domínio/fwnode/virq exclusivo com referência OF retida; cada falha parcial permite cleanup idempotente e retry.
- [x] Teardown recusa IRQ com action/started/unmasked/enabled e domain com mappings restantes. Não libera recursos enquanto a recuperação depender deles.
- [x] Preservar ciclo de sucesso e lease/primeiro erro; atualizar getters e fixtures, qualificar Mac/Ubuntu/ABI/modpost e mutações por asserção.
- [ ] Collector/perfil e sessão física agrupada, distinguindo baseline de máscara derivada da fonte de readback/entrega IRQ reais. Wi-Fi/carga/telemetria continuam pendentes.

### F1f — regressão de CI do caller completo

A CI de4739cb5 falhou no Mac: o header extraído não terminava em newline e a fixture do caller inteiro não tinha as APIs/tipos DART novos. Corrigir somente essas fixtures/geração, mantendo Werror. Arquivos: `tests/test_n71_dart_provider.py`, `tests/n71_pcie_diagnostic_caller.c`, `tests/test_n71_pcie_diagnostic_caller.py` e este plano. Integrar testes das ações/getter/cleanup e owners DART no caller real; conservar os73/21/27 casos e mutações anteriores. Qualificar o gate afetado Mac/Ubuntu e acompanhar CI do novo head; não declarar CI aprovada por prova local.

No primeiro gate completo ARM64, uma mutação ultrapassou5 segundos; o mesmo caso isolado passou em1,631s. A VM usa core_pattern piped pelo Apport e a fonte Linux confirma que RLIMIT_CORE não suprime pipes. Desabilitar dumpability somente no processo C da fixture Linux para evitar chamar um crash handler externo em cada SIGABRT; nenhum sysctl/configuração da VM/Mac ou prazo será alterado. O vínculo do timeout ao Apport é uma hipótese; repetir o gate afetado e manter o timeout anterior como falha, nunca como kill.

- [x] Caller completo143 cenários/89 mutações no Mac e ARM64; cleanup corrigido4/3 em ambos. IRQ37/21 e backend27/14 reutilizados com inputs pertinentes intactos;50 inputs finais conferidos nas duas plataformas.
- [x] Módulo completoW=1/Werror/modpost e ABI passou;38 inputs de produção, fonte/config/Image/exports preservados. Nenhum módulo novo carregado.
- [x] A CI de [19ffb03](https://github.com/djalmajr/iphone6s-linux/actions/runs/37566057928) passou nos três jobs após a correção da issue41. O timeout Ubuntu anterior de ec09d4f fica preservado; prazo de15 minutos intacto. A intermitência anterior da issue38 não foi encerrada.
- [ ] Fechar lifecycle MSI e attachment PCI/DART; só então preparar seleção/collector e prova física agrupada.

## D6. Mensagem MSI separada do número AIC

- **Decisão:** qualificar um helper de referência que produz address_lo/hi/data somente para N7132/offset256/porta1/base8/count8, endereço0xbffff000 e vectorBase0. Dados esperados8..15; parent AIC264..271 permanece separado. Helper sem integração ao caller/DT/perfil ou alocação IRQ/MMIO; próxima fatia nativa usará esse contrato para compose_msg.
- **Por quê:** a referência Apple oficial soma firstVector e _vectorBase para pedir a mensagem. No binário N71, a factory chama o allocator tipado com flags0xd1004; o bit0x4 é identificado como Z_ZERO no header Apple8020.140.41 anterior. Init do controlador não grava _vectorBase e coloca o offset256 em outro campo. O bridge escreve o argumento de vetor diretamente no terceiro word da mensagem. VectorBase0 é uma inferência do código e dessa comparação, não estado/mensagem medidos no hardware; a consulta ao tag exato8020.241.44 retornou404.
- **Alternativas:** usar264 como message data confunde registro parent com vetor; copiar doorbell do driverM1 ignora a propriedade N71; bind do brcmfmac antes do contrato mistura DMA/IRQ/firmware. Rejeitadas.
- **Reverter:** baixo, quatro arquivos públicos em fatia isolada, sem mudança de runtime/hardware. Evidência primária e limites em publicação separada.
- **Onde:** este plano, `phone/kernel/n71-wlan-msi-message.h`, `tests/n71_wlan_msi_message.c`, `tests/test_n71_wlan_msi_message.py`. Qualificar C11/Werror/AST/lint/Mac/ARM64 e probeABI na VM dedicada, preservando kernel/exports.
- **Status:** qualificada offline nos commits0c1fbe5/0720cf6. A CI de ec09d4f terminou com timeout Ubuntu; publicar MSI junto da correção da issue41 já qualificada para produzir nova prova remota. Sem claim de green, novo boot/DFU/PIN ou domínio MSI implementado.

### Contratos F1g

- [x] Oito mensagens de referência esperadas, parâmetros de endereço/base/topologia/índice recusados e output intacto em erro; preservar EINVAL/ERANGE.30 cenários por plataforma.
- [x]13 mutações compilam e falham por asserção; sem compiler/import/timeout como kill e sem aumentar prazos. Faltava stdbool na primeira fixture; esse erro de compilação foi corrigido e não contado como kill.
- [x] Mesmos quatro inputs Mac/ARM64; probe kernelW=1/Werror/modpost/ELF/vermagic; sem load/integração ao caller. Kernel e exports preservados, helperAIC anterior intacto e reutilizado.
- [x] Guardar hashes/offsets de nove recortes primários privados e preparar referência sanitizada, distinguindo inferência estática de entrega MSI real. Fonte XNU8020.140.41 de flags é uma comparação anterior, não a versão exata8020.241.44 do binário; zeroing completo ainda não fechado. [Reprodução e limites](../../docs/N71_IRQ_IOMMU.md#f1g--referência-da-mensagem-msi-sem-integração-física).

## D7. Próxima fatia: domínio MSI nativo e rollback de vetores

- **Decisão:** usar msi_create_parent_irq_domain e msi_lib_init_dev_msi_info fixados/exportados, somente MSI/multi-MSI, sem MSI-X. Domínio/fwnode/OF ref privados e allocator limitado aos oito slots da porta. Lookup de conflito e alloc dos parentsAIC264..271 sob o root mutex; rollback do grant em todo erro parcial. Parent/data/message permanecem tipos distintos.
- **Por quê:** o kernel tem a API MSI-parent moderna; a bridge Apple atual serve de referência de API, não de registradores A9. O exports fixado contém msi_create_parent_irq_domain, mas não bitmap_find_free_region/bitmap_release_region. Usar allocator de oito bits local com testes de alinhamento/contagem/rollback evita dependência não exportada, sem patch do kernel ou rebuild de Image.
- **Alternativas:** copiar offsets/doorbellM1 não qualifica N71; usar bitmaps não exportados quebra modpost; iniciar brcmfmac agora mistura IRQ/DMA/firmware. Rejeitadas.
- **Reverter:** baixo antes da integração física; header novo e fixtures isolados. Perfil/caller existente não muda nesta fatia.
- **Onde:** F1h de até cinco arquivos: este plano, `phone/kernel/n71-wlan-msi-native.h`, `tests/n71_wlan_msi_native_fixture.h`, `tests/n71_wlan_msi_native.c`, `tests/test_n71_wlan_msi_native.py`. Probe ABI privado na VM; publicação sanitizada separada.
- **Status:** F1h aplicada e qualificada offline no commit295c7c2. CI anterior corrigida e três jobs aprovados no head19ffb03; nova CI da F1h pendente. Conferidos include/linux/msi.h SHA93b85e1e508914ef1c41e880bf399356b719ed383bf81eff58b1451c682829aa e exports da fonte958481f. Sem domínio/IRQ/MSI/config/MMIO novo no telefone.

### Contratos F1h planejados

- [x] Allocation count1/2/4/8 alinhada; recusa conflito/owner/cells/chip. Todas as256 combinações de bitmap por quatro tamanhos foram verificadas, com preservação de outros grants. Falhas parciais de parent/set-leaf e retry passaram.
- [x] Free por vetor conforme o core fixado, reset/free-parent e proteção de identidade/grant comprovados nas fixtures. Release recusa bitmap/mapcount e filho registrado mesmo sem IRQs. Não declara readback físico ou free sem MMIO.
- [x] Compose usa o helper e recusa domínio/grant/índice inválidos. Mac e ARM64 passaram1132 cenários e45 mutações compiladas por assertion cada; AST/lint fatal Mac e AST ARM64. ProbeABI W=1/Werror/modpost/ELF/vermagic passou, seis inputs idênticos e kernel/exports preservados; não carregado.
- [x] F1h permanece isolada: sem associação PCI, caller, perfil ou autoload. A integração F1i, collector e hardware continuam pendentes depois dos gates de máscara/attachment; nenhum novo boot nesta qualificação.

### D7: precondições de lifetime antes do código

A fonte fixada cria o domínio MSI por dispositivo em kernel/irq/msi.c:1029–1105 e só o remove por devres/remoção explícita em1113–1133. PCI free_irqs deixa esse domínio vivo (drivers/pci/msi/irqdomain.c:235–249). Não basta bitmap/mapcount zero. A fatia isolada instalará prepare/teardown que retêm a identidade do único filho WLAN, recusando release mesmo sem vetores. O caller futuro precisa excluir criação/teardown e release concorrentes, remover/quiescer PCI e soltar suas referências antes de liberar MSI; teardown roda antes de irq_domain_remove do filho. A exclusão de lifetime é uma precondição do consumidor, ainda sem integração física. Não associar o domínio ao PCI nesta fatia.

Allocation sob root mutex exige descriptor do dispositivo retido, count1/2/4/8, eight-slot grant e parents exclusivos. Free do core é por vetor; conferir identidade, preservar os outros grants e não reutilizar mapping alheio. Callback compose exige owner/domain/slot válido. Fixtures executam callbacks reais com modelos separados de core/OF/MSI; probe ABI usa fonte/exports fixados.


## D8. Lease da associação MSI antes do primeiro scan

- **Decisão:** implementar primeiro um owner da associação entre pci_host_bridge e domínio MSI nativo, isolado do caller. Acquire exige bridge ainda sem bus e sem domínio alheio; salva a flag msi_domain, cria o domínio e associa bridge->dev antes do scan. Release recusa bus vivo/identidade divergente, desfaz só a associação própria, restaura a flag anterior e mantém owner em falha do teardown nativo. A integração ao scan/caller será F1j depois dessa qualificação.
- **Por quê:** a fonte fixada herda MSI do host em drivers/pci/probe.c:930–979,1050 e2710–2764. Associar depois do scan perde o caminho normal e exige editar várias referências. pci_remove_root_bus:161–185 remove filhos/bus e deixa bridge->busNULL antes da liberação do domínio; referências externas podem manter filho MSI vivo e precisam de recusa/retry. A bridge e o módulo permanecem pertencendo ao futuro caller enquanto houver lease.
- **Alternativas:** remendar a cadeia de dispositivos já enumerados amplia rollback; liberar parent por mapcount zero ignora domínio filho; incorporar enable/MASTER agora exige attachment IOMMU ainda não qualificado. Rejeitadas.
- **Reverter:** baixo; helper isolado, sem perfil/caller/autoload ou hardware nesta fatia. Não alterar fonte/config/Image/exports.
- **Onde:** F1i de até cinco públicos: este plano, phone/kernel/n71-wlan-msi-host.h, tests/n71_wlan_msi_host_fixture.h, tests/n71_wlan_msi_host.c e tests/test_n71_wlan_msi_host.py. Probe composto ABI privado na VM; doc/evidência separadas.
- **Status:** F1i qualificada offline:21 cenários/22 mutações por assertion no Mac/ARM64, AST/lint fatal Mac/AST ARM64, probe compostoW=1/Werror/modpost/ELF/vermagic. Sete inputs idênticos, kernel/exports intactos. PCI device_add ocorre durante pci_device_add:2767; não presumir que scan seja invisível ao core/IOMMU. Antes de liberar driver/DMA, a F1j/F2 precisa verificar guards reais de binding, configurar DART/host OF antes dessa publicação e mudar teardown para remover consumidores antes do provider. A associação MSI sozinha não libera esse estágio.

### Contratos F1i

- [x] Bridge sem bus/domínio alheio, args válidos, owner exclusivo e acquire nativo antes da associação. Defaults false/true da flag preservados em release.
- [x] Cleanup remove associação própria antes de destruir parent; bus vivo, domínio alheio ou flag divergente recusam. Falha nativa mantém lease/bridge para retry; reter módulo/bridge é precondição do futuro caller, sem integração nesta fatia.
- [x] Helper real executado com dependências PCI/MSI modeladas, falhas parciais, idempotência e22 mutações compiladas por assertion; Mac/ARM64 e probe ABI compostoWerror/modpost com hashes/baselines preservados. Native MSI gate anterior foi reutilizado com seus inputs intactos.
- [ ] F1j integrará os dois helpers antes do primeiro scan, com guard/getter/cleanup e fixtures do caller/scan; manter enable negado e não adicionar bind ou DMA nesta etapa. Sessão física continua agrupada após collector/perfil e gates restantes.

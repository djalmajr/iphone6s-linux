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
- **Status:** F1h aplicada e qualificada offline no commit295c7c2. CI anterior corrigida e três jobs aprovados no head19ffb03; [CI da F1h](https://github.com/djalmajr/iphone6s-linux/actions/runs/37568094109) aprovada nos três jobs em2026-10-07T03:54:41Z. Conferidos include/linux/msi.h SHA93b85e1e508914ef1c41e880bf399356b719ed383bf81eff58b1451c682829aa e exports da fonte958481f. Sem domínio/IRQ/MSI/config/MMIO novo no telefone.

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


### Guard de binding confirmado para a próxima integração

A fonte958481f em drivers/pci/pci.h:804–806 recusa match enquanto PCI_DEV_ALLOW_BINDING estiver desligado. drivers/pci/bus.c:370–375 libera esse bit antes de device_initial_probe, no pci_bus_add_device. O diagnóstico atual não chama esse estágio; seu enable_device também permanece negado. Device_add durante scan ainda publica o dispositivo e aciona notifiers IOMMU. Não substituir essa distinção por "scan não registra dispositivo". A F1j irá associar MSI antes do scan, manter binding/enable negados e preservar a bridge até release completo; attachment DART requer configuração antes da publicação/IOMMU e teardown de consumidores antes do provider na fase seguinte.


## D9. Associar MSI antes do scan, preservando o diagnóstico padrão

- **Decisão:** F1j integra a lease no n71_scan_host e adiciona options internos para MSI somente com held bus/PME preparado. Os wrappers existentes continuam MSI-off. Novo wrapper hold_msi prepara parent OF e lease antes de pci_scan_root_bus_bridge; report recusa herança divergente na bridge, root bus, bus/dispositivos. Cleanup remove o bus antes de liberar a lease e para em erro nativo antes de restaurar config/resources/liberar bridge. A seleção pelo módulo/getter será F1k depois das fixtures.
- **Por quê:** o kernel herda o domínio durante device_add/scan. O owner precisa existir antes desse estágio e pode permanecer necessário após bus removal quando filhos têm referências externas. Preservar os wrappers permite verificar os29/16/20 casos antigos junto da nova rota, sem mudar o perfil físico ou bind/DMA.
- **Alternativas:** aplicar setter em dispositivos já escaneados exige snapshot de várias associações; criar domínio fora do owner da bridge quebra lifetime; ligar o driver antes de attachment DART mistura gates ainda abertos. Rejeitadas.
- **Reverter:** baixo antes do hardware; API nova opt-in, wrappers atuais intactos. Campo adicional de lease é interno ao módulo, ainda sem seletor/collector.
- **Onde:** até cinco públicos: este plano, phone/kernel/n71-pcie-scan.h, tests/n71_pcie_scan_host.c, tests/n71_pcie_msi_scan_fixture.h, tests/test_n71_pcie_scan_host.py. O modelo MSI novo fica no header de fixture, mantendo dependências separadas dos casos PCI existentes. O runner de mutações scan-config permanece intacto. As fixtures optional/IO16/PREF64 reutilizam o C base e precisam do gate afetado por essa dependência.
- **Status:** aplicada e qualificada offline no commit36998e8; documentação0ae5922 publicada e CI aprovada nos três jobs em2026-10-07T04:54:34Z. As funções existentes do scan estão referenciadas; não há função morta a remover. Firmware, Image/config/exports e Mac permanecem intactos; nenhuma nova sessão física até integração/collector/gates necessários.

### Contratos F1j

- [x] MSI exige hold/PME opt-in; parent OF com referências equilibradas; acquire/associação antes do core scan. Wrappers padrões não criam domínio.
- [x] Herança nas cinco associações e divergências verificadas na fixture; enable permanece negado e guard de driver/MASTER preservado. Sem IRQ/bind/DMA novo nessa fatia.
- [x] Bus removido antes da lease; falha nativa conserva bridge/config/power e permite retry sem rescan/restauração antecipada. Falhas parciais de acquire/scan exercitadas.
- [x] Gates afetados Mac/ARM64 passaram152 cenários/117 mutações por assertion cada; ABI completoW=1/Werror/modpost/ELF/vermagic com wrapper MSI privado,55 inputs/baselines conferidos.57 mutações e três métodos antigos reutilizados por hashes/AST intactos. Duas falhas iniciais de compile não contam como kills; selectors corrigidos e somente o método MSI repetido. F1k selecionará a rota no caller/getter.

## D10. Selecionar MSI no caller e expor ownership sem mudar o perfil físico

- **Decisão:** F1k acrescenta msi_parent opt-in (default false,0400), válido apenas com scan_hold e suas precondições existentes. Probe escolhe hold_msi somente quando solicitado. Getter msi, sob session_lock, informa requested/ready/held/associated/owner/domain/mappings/child/session_error sem endereços ou identificadores. Não declara entrega IRQ ou attachment DMA a partir desses campos.
- **Por quê:** a rota nativa já está qualificada no scan, mas o caller ainda não pode selecioná-la. Tornar selection/ownership observáveis permite agrupar futuras coletas e retries na mesma sessão. A bridge e o pin do módulo devem continuar retidos enquanto o cleanup MSI recusar, inclusive depois da remoção do bus.
- **Alternativas:** habilitar MSI por default muda o diagnóstico físico anterior; publicar perfil antes da integração DART/collector deixa gates essenciais ausentes; usar getter como prova de entrega confunde identidade com hardware. Rejeitadas.
- **Reverter:** baixo antes do hardware; flag default false e getter adicional, formatos anteriores preservados. Nenhuma mudança na Image/config/exports ou autoload.
- **Onde:** quatro arquivos públicos nesta fatia: este plano, phone/kernel/n71-pcie-diagnostic.c:41,399,544,634, tests/n71_pcie_diagnostic_caller.c e tests/test_n71_pcie_diagnostic_caller.py. Código das dependências scan/MSI permanece intacto. Build de produção em M separado, agora sem wrapper privado para manter a rota.
- **Status:** aplicada e qualificada offline. Mac/ARM64 passaram156 cenários/103 mutações compiladas por assertion cada; AST/lint fatal Mac, AST ARM64 e produçãoW=1/Werror/modpost/ELF/vermagic.48 inputs idênticos e30 includes efetivos; módulo104288 bytes/SHA0c0783806158eb88a4bc390644a3186d474d1fe20d2026a046719751f875f8a5, sem wrapper privado ou load. Fonte/config/Image/exports preservados. Os dois corpos de cleanup extraídos pelo gate DART permanecem idênticos por hash, assim como provider e gates de scan/MSI independentes: provas anteriores reutilizadas. Na leitura USB desta rodada o aparelho estava no iOS, sem novo boot/escrita.

### Contratos F1k

- [x] Default preservado, MSI sem hold recusado antes de registro/efeitos, rota selecionada só por opt-in; antigos guards e formatos intactos.
- [x] Getter sob lock, valores exatos antes/depois do scan/release e com owner pendente sem bus; mapcount privado e child distintos de entrega física.
- [x] Falhas de acquire/teardown conservam bridge/pin/reset/power; retry sem scan ou put duplicado. Getter mantém session_error até cleanup bem-sucedido.
- [x] Caller completo Mac/ARM64 com cenários antigos e novos/mutações compiladas por assertion; AST/lint fatal; produção W=1/Werror/modpost/ELF/vermagic com hashes/baselines preservados. Não repetir gates independentes com inputs intactos.
- [x] Prova/limites documentados e issue40 atualizada; CI2192cbe aprovada nos três jobs em2026-10-07T05:06:28Z. Attachment DART, collector/perfil e energia continuam antes da sessão física agrupada.

## D11. Preparar a associação OF/DART com rollback observável

- **Decisão:** próximo helper n71-dart-host.h terá duas changesets de uma propriedade cada: disponibilidade do provider manual e iommu-map do parent do host. Validar nó/driver/provider/SID0 e recusar mapa/máscara preexistentes. Manter refs explícitas de bridge/devices/nodes; claim exclusivo de OF_POPULATED evita outro probe ao tornar o DART disponível. O caller futuro remove consumidores PCI, desfaz o mapa, para o provider manual e só então restaura status/flag. Sem bind/MASTER/DMA nesta fatia isolada.
- **Por quê:** of_iommu_xlate:28 recusa status disabled. OF notifier:743/764 controla criação/remoção por OF_POPULATED; reverter status enquanto o provider ainda existe pode removê-lo fora do owner. Kernel dynamic.c:767 retorna erro de notify sem reverter propriedades já aplicadas; readback de identidade é obrigatório em todo erro/retry. Changeset destroy libera entries/refs, não a propriedade dinâmica retida pelo tree; não liberar manualmente essa memória nem declarar recuperação completa do heap.
- **Alternativas:** status okay no DT de boot antecipa probe antes dos owners/baselines do diagnóstico; setters brutos no valor status ignoram notificações/lifetime; ignorar disponibilidade permite falso sucesso de associação; copiar a topologia M1 não prova o stream N71. Rejeitadas.
- **Reverter:** médio na integração futura; envolve refs e duas fases de teardown. Baixo no helper isolado, sem seleção no caller/perfil/autoload. Manter props alocadas pelo próprio core OF e owner até restauração comprovada.
- **Onde:** futura fatia de até cinco públicos: este plano, phone/kernel/n71-dart-host.h, tests/n71_dart_host_fixture.h, tests/n71_dart_host.c e tests/test_n71_dart_host.py. Fonte958481f: drivers/iommu/of_iommu.c:22–57,114–167; apple-dart.c:913–961,1393–1425; drivers/of/platform.c:726–790; dynamic.c:533–547,767–801,860–895,1032–1065. Referência stream0 já publicada; não repetir extração de firmware.
- **Status:** helper isolado qualificado offline:49 cenários e38 mutações compiladas por assertion no Mac e ARM64; AST/lint fatal e probeW=1/Werror/modpost/ELF/vermagic aprovados. Primeiro build detectou include of_platform.h ausente, corrigido explicitamente; gate completo repetido nos dois ambientes após a correção. Probe11456 bytes/SHAe7bf28e5cede9bf1fad52be38b3ea468af4b6b7b2140bbc265fb5221adbcc634, init recusa execução e nunca foi carregado. Fonte/config/Image/exports preservados. Integração/aliases/attachment e prova física continuam pendentes; nenhum efeito no aparelho.

CI da publicação04ae283 aprovada nos três jobs em2026-10-07T05:59:44Z. [Prova sanitizada](../../docs/evidence/n71-dart-host-qualification.json) inclui o head e resultados; não é prova de hardware.

### Contratos planejados da próxima fatia

- [x] Validate-before-effects: bridge sem bus, parent/of_node fixos, provider manual bound/único, status disabled original, OF_POPULATED não reivindicado, SID0/células e mapa/máscara ausentes. Preservar mappings/flags/refcounts alheios.
- [x] Helper prepara somente RIDs0x0008/0x0100 para SID0, mantendo status/mapa separados e refs. Não configura domínio DMA nem verifica aliases runtime nesta fatia isolada.
- [ ] Integrar antes de PCI publication e recusar alias fora do contrato antes de attachment/DMA; associação OF sozinha não comprova domínio ou DMA físico.
- [x] Erro de apply/notify ou revert interpretado com identidade/readback das propriedades. Owner/refs conservados em efeito vivo/drift; retry sem aplicar/reverter a mesma etapa já restaurada duas vezes.
- [x] Unmap recusa bus vivo; ref da bridge sobrevive ao put do scan. Release da disponibilidade recusa provider registrado; restaura status disabled e só depois flag própria. Nenhum provider alheio removido pelo notifier.
- [x] Produção executada com dependências OF/PCI modeladas e falhas antes/depois dos efeitos;49 cenários/38 mutações por plataforma. ABI fixadaWerror/modpost sem load. Integração/getter/collector e física posteriores, agrupadas com energia.

### Interface e ordem da próxima implementação

Usar n71_dart_host_prepare(owner,request), n71_dart_host_unmap(owner) e n71_dart_host_release(owner). Request reúne bridge e provider; derivar master de bridge->dev.parent e conferir seu nó /soc/pcie@610000000, provider /soc/iommu@602008000 e driver apple-dart. Mapa restrito com entradas RID0x0008 e RID0x0100 para SID0, length1 cada, phandle verificado por lookup. São RIDs já medidos; o walker fixado search.c:28–115 também percorre aliases explícitos e tipos de bridge. Não alegar ausência de quirks runtime: alias diferente deve recusar associação.

Owner retém get_device/put_device da bridge/master/provider e referências OF originais, além das duas changesets e identidades de suas propriedades. A ref da bridge impede uso após o put do scan. OF_POPULATED deve ser adquirido exclusivamente antes de disponibilizar o nó, preservado enquanto o provider manual existe e restaurado apenas com status disabled comprovado; uma flag previamente alheia recusa acquire.

Em cada operação, distinguir propriedade original, propriedade própria aplicada e drift alheio. Apply/revert com erro de notify pode deixar o efeito concluído: guardar o erro e estado por readback, permitindo retry sem aplicar/reverter novamente uma etapa já restaurada. Dados/names de propriedades devem ser alocados pelos helpers OF exportados, nunca apontar para stack, owner liberado ou rodata de módulo descarregado. Destroy não recupera as propriedades retidas pelo tree. Sem liberação manual dessas props.

Unmap exige bridge sem bus e mantém disponibilidade enquanto o provider está vivo. Release de disponibilidade exige ausência de platform device registrado para o nó, evitando remoção indireta pelo notifier. A futura integração precisa concluir PCI removal/unmap antes de provider stop, depois restaurar disponibilidade, antes de reset/power/module release. Esta é uma precondição a qualificar; ainda não é o comportamento do caller atual.

## D12. Gerar primeiro um phandle DART estável na DTB desativada

- **Decisão:** antes do helper D11, acrescentar --dart-phandle opt-in ao preparador de topologia. Reservar max(phandles baseline)+1 após validação dos pins; inserir somente o phandle do DART na candidata e exigir valor exclusivo/exato na delta. Status disabled e todas as propriedades anteriores permanecem. Default produz a topologia anterior. Não acrescentar iommu-map nem editar phandle live no kernel.
- **Por quê:** a candidata atual não referencia o label n71_dart1, e verify_delta exige no DART exatamente os campos sem phandle. O helper proposto precisa de um identificador não nulo para o OF map; não pode presumir que o nó já o tenha. A alocação explícita antes de dtc deixa os providers novos escolherem outros números, preservando referências da baseline.
- **Alternativas:** adicionar só a propriedade phandle em runtime presume atualização do campo/cache OF; escolher número arbitrário pode colidir; permitir qualquer propriedade extra no DART enfraquece a boundary. Rejeitadas.
- **Reverter:** baixo; flag default off, sem Image/config/exports, perfil físico, status ativo, probe ou novo boot.
- **Onde:** próxima fatia de quatro públicos: este plano, scripts/build/prepare-n71-topology.py, tests/test_n71_topology.py e tests/run_n71_topology_mutations.py. Depois, docs/prova sanitizada separadas. Fonte e fragmento anteriores preservados.
- **Status:** aplicada e qualificada offline: Mac16 testes aprovados/5 native skips e13 mutações; ARM64todos21 testes e15 mutações por assertion,23.528s. CLI default e opt-in compilaram DTBs reais, DART phandle41 exclusivo, todos os nós novos desativados. Usamos cópia sparse limpa em pasta separada; as seis alterações tracked da fonte de binding original foram preservadas por hash do diff, assim como config/Image/exports. Nenhum load/composição/DFU.

### Contratos D12

- [x] Flag off conserva o default; flag on gera handle válido, único, determinístico e pins anteriores intactos. Recusar overflow, baseline inválida e colisão/drift.
- [x] Delta opt-in aceita somente o phandle esperado no DART; recusa mapa, status ativo e qualquer outra alteração. Registrar o identificador na provenance somente no modo opt-in.
- [x] Testes/mutações dos guards e compilação real dtc na VM; comparar baseline/default/candidata com hashes, sem alterar source/config/Image/exports. AST/lint fatal e scope de saída preservados.
- [x] Reprodução publicada em22031b8 e issue40 atualizada; D11 recusa DTBs sem phandle. CI desse head aprovada nos três jobs em2026-10-07T05:28:11Z, sem prova de hardware. Nenhum autoload/DFU/hardware novo nesta preparação.

### D11: detalhes fechados antes do helper

O helper não remove o provider. Caller mantém o pin do módulo e serializa essas operações com scan/teardown. Prepare só publica ownership depois dos guards iniciais, mas antes de alocações das properties/claim/apply; falhas posteriores mantêm refs para cleanup. Ambos os nós, os três devices e os phandles originais devem permanecer identificáveis. Provider manual deve corresponder ao lookup OF, nome n71-dart-cycle, parent do host, driver apple-dart e drvdata presente.

Changesets de status e mapa possuem exatamente uma entry cada. Identidades das propriedades alocadas pelo core ficam no owner antes de apply. Unmap/release leem estado real, distinguem original/próprio/alheio e só chamam revert para a propriedade própria ainda aplicada. Erro com readback restaurado continua reportado nessa chamada; retry reconhece restauração e não duplica revert. Release exige unmap concluído, ausência do provider registrado, status disabled e flag própria conservada até a restauração. Conservar todo o owner em drift/erro pendente.

Antes de soltar a última referência a um device, zerar o owner e guardar localmente as referências a liberar. Isso também protege owner eventualmente embutido no priv da bridge. Destroy de changesets só libera entries/refs; a árvore retém memória de properties, como documentado na auditoria. Fixtures precisam modelar notifications que falham depois da aplicação e as refs enquanto bridge/provider já perderam a referência de registro. Nenhum campo readback implica entrega IRQ/DMA física.

## D13. Separar remoção de consumidores da restauração do host PCI

- **Decisão:** extrair n71_pcie_scan_remove_consumers(state) do cleanup atual. Remove bus sob rescan/remove lock e libera a lease MSI; conserva bridge/config/resources/window/PME/target e held_stop_error. Cleanup completo chama a etapa e só restaura/free após sucesso. Sem seleção nova ou mudança da ordem DART no caller nesta fatia.
- **Por quê:** a próxima integração precisa remover consumidores e desfazer o mapa antes de parar o provider, conservando a bridge até restaurar disponibilidade OF. Cleanup monolítico libera o priv cedo demais para essa ordem. Preservar a API antiga permite preparar a integração sem ativar attachment.
- **Alternativas:** parar DART antes de consumidores contradiz o lifetime IOMMU; liberar bridge antes de availability depende de priv possivelmente liberado; copiar o cleanup em outro caller duplica rollback. Rejeitadas.
- **Reverter:** baixo nesta fatia; API antiga conserva comportamento e nenhum perfil muda. Médio depois da integração DART que dependerá da etapa.
- **Onde:** até quatro públicos: este plano, phone/kernel/n71-pcie-scan.h, tests/n71_pcie_scan_host.c e tests/test_n71_pcie_scan_host.py. Funções existentes referenciadas, sem código morto a remover antes da extração. Gates optional/IO16/PREF64 afetados pelo C compartilhado; ABI completa em M separado, sem load.
- **Status:** extração e API antiga qualificadas offline:159 cenários/120 mutações compiladas por assertion no Mac e ARM64; AST/lint fatal e produçãoW=1/Werror/modpost/ELF/vermagic aprovados. Uma mutação antiga gerou unused-variable após a extração, sem contar compile como kill; selector corrigido e só esse caso repetido, com71 mutações e baseline86 reutilizados por55 inputs idênticos. Gates optional/IO16/PREF64 executados integralmente. Módulo104352 bytes/SHA456134c0783cfffd0ce59676d35234a544993602c665d84b4534f1c0bc7d1c67, sem wrapper/load; source/config/Image/exports preservados. Caller/getter/collector e alias/attachment são próximos, com mínimos boots.

### Contratos D13

- [x] Remover consumidores conserva config/resources/bridge/energia; lease MSI pendente bloqueia retorno de sucesso. Sem bus/lease, retry não repete remoção nem restaura IO.
- [x] Fase resource ativa e bus alheio recusam antes de efeitos. Stop-error fica registrado e é reportado pelo cleanup completo, mesmo após retry da lease MSI.
- [x] Cleanup antigo mantém restore/free e erros; sete novos cenários executam a etapa real e provam ausência de writes/restauração/free entre as fases.
- [x] Mac/ARM64: scan86/72, optional18/14, IO1620/17 e PREF6435/17, total159/120. Módulo completoW=1/Werror/modpost/ELF/vermagic; source/config/Image/exports intactos.
- [x] Reprodução sanitizada publicada emf656ab1 e issue40 atualizada no comentário6031987027 antes da futura integração/candidata física. CI desse head ainda em execução na publicação; nenhuma claim de green ou DFU nesta fatia.

## D14. Associar o DART no scan e exigir readback do core IOMMU

- **Decisão:** próxima fatia adiciona owner D11 ao priv do scan e opção interna provider manual, default NULL. Exigir held bus, PME e MSI preparados; o caller futuro fornecerá provider bound adquirido antes do scan. Preparar disponibilidade/mapa antes de pci_scan_root_bus_bridge. Report confere fwspec/fwnode/SID0 e domínio traduzido obtidos pelo core; scan sem associação não é sucesso. Remoção D13 seguida de unmap; cleanup completo só restaura config/resources/free depois de release D11, que recusa provider ainda registrado.
- **Por quê:** iommu_init_device:469–488 pode chamar pci_dma_configure sem driver; notifier ADD_DEVICE:1820–1824 ignora a falha com NOTIFY_DONE. Bus publicado não prova attachment. O provider precisa sobreviver à remoção dos consumidores, mapa e status disponíveis até seus efeitos terminarem. Auditoria nova em docs/evidence/n71-iommu-publication-audit.json.
- **Alternativas:** editar mapa depois da publicação perde o caminho normal; alegar sucesso só pela changeset mascara falha silenciosa do core; parar provider dentro do scan duplica seu owner; ignorar modpost de aliases enfraquece ABI. Rejeitadas.
- **Reverter:** baixo antes do caller/perfil; modo antigo conserva provider NULL. Médio depois da seleção física, por lifetime e estado de cleanup retido.
- **Onde:** primeiro preparar stub iommu.h nos quatro runners compartilhados, mais este plano (cinco públicos); depois integrar em cinco públicos: plano, phone/kernel/n71-pcie-scan.h, tests/n71_pcie_scan_host.c, tests/test_n71_pcie_scan_host.py e nova tests/n71_pcie_dart_scan_fixture.h. A preparação não muda cenários ou assertions. Fixture nova modela core OF/IOMMU e API do helper; D11 é produção qualificada separadamente. Probe completo retém wrapper privado só enquanto o caller não selecionar a nova rota. Caller/getter em fatia seguinte.
- **Status:** scan integrado, mas a primeira qualificação190/146 de f11a91a usou uma suposição incorreta sobre fwspec IDs. Auditoria primária posterior mostrou que apple-dart usa stream_maps privado e deixa num_ids0. Essa prova de fixture/ABI não libera a rota física; D15 abaixo corrige o contrato e executa nova qualificação completa. Probe inicial privado nunca foi carregado ou selecionado em perfil. Caller/getter/collector, aliases/máscaras e física continuam pendentes.

Contrato corrigido em D15: fwspec tem num_ids0/flags0 e fwnode do provider; conferir mapa OF próprio/exato de dois RIDs para SID0, sem ler private stream_maps. Domínio IOMMU_DOMAIN_DMA (strict fixado), igual nos dois dispositivos. Ponteiros são empréstimos do core durante bus vivo, sem ownership novo; não dereferenciar após remoção. Map SID e domínio são observações de software, não prova de DMA ou readback privado de SID. Sem aliases indisponíveis ou alteração da Image nesta fatia.

### Contratos D14

- [x] Guard before effects: provider opt-in só com held bus/MSI/PME; defaults e wrappers antigos mantêm provider NULL. Disponibilidade/mapa preparados com refs antes da publicação PCI.
- [x] Contrato D15 qualificado: mapa OF próprio/exato, fwspec Apple vazio/provider/flags0 e mesmo domínio DMA strict; ausência/drift/core error recusa held success. Sem claim de readback privado de SID/IRQ/DMA.
- [x] Scan remove consumidores → unmap; cleanup recusa provider vivo e conserva bridge/config/resources até release D11. Ponteiros emprestados apagados após remoção, mesmo com erro MSI. Ordem do caller ainda precisa selecionar essa API antes de parar o provider.
- [x] Contrato corrigido: scan125/102 +optional18/14+IO1620/17+PREF6435/17=198/150 por plataforma. Baseline125/100 mutações reutilizados após corrigir só dois selectors unused,56 inputs idênticos; esses dois mutantes e três gates restantes executados. Prova190/146 não reutilizada. D11 separado intacto; ABI novo aprovado.
- [ ] Caller/getter/collector, aliases/máscaras, seleção de DTB e energia fechados antes de uma única sessão física agrupada. Nenhum novo DFU durante a implementação offline.

## D15. Corrigir o readback para o fwspec real do Apple DART

- **Decisão:** exigir num_ids0 e flags0/fwnode do provider, validar identidade de status/mapa próprios, exatamente oito células do mapa e todos os valores RID/phandle/SID0/range1. Report usa map_sid0, explicando que não lê stream_maps privado. Manter observação do mesmo domínio DMA strict e guards de lifecycle.
- **Por quê:** apple-dart.c:913–961 grava SIDs em cfg->stream_maps[].sidmap, sem iommu_fwspec_add_ids. of_iommu.c:22–41 só inicializa fwspec e chama of_xlate; iommu.c:3073–3097 aloca fwspec zerado. Exigir num_ids1 recusaria toda associação real, apesar do gate modelado verde. Remove:1393–1403 faz hw_reset antes de IRQ/unregister/clocks; a restauração real ainda precisa de prova no aparelho.
- **Alternativas:** espelhar struct privado do driver cria dependência de layout sem API; declarar ID preenchido pela fixture fabrica prova; adicionar export/patch kernel só para essa observação amplia o escopo antes de precisar. Rejeitadas. Readback direto de SID privado permanece limite explícito, sem substituir a prova física.
- **Reverter:** baixo; somente correção do diagnóstico opt-in ainda sem seleção/perfil. Mesmo contrato de ownership e defaults.
- **Onde:** cinco públicos: este plano, phone/kernel/n71-pcie-scan.h, tests/n71_pcie_scan_host.c, tests/test_n71_pcie_scan_host.py e tests/n71_pcie_dart_scan_fixture.h. Documentação/prova finais substituem o draft anterior numa fase separada. Logs/probe190/146 preservados privados como história do contrato corrigido.
- **Status:** implementada e qualificada offline:198 cenários/150 mutações por plataforma; AST/lint fatal e probe completoW=1/Werror/modpost/ELF/vermagic aprovados.39 cenários/30 mutações DART; dois selectors com compile unused não contaram como kill, corrigidos e repetidos seletivamente por56 inputs intactos. Probe110520 bytes/SHA17df226eea6d767cb05a042809e355751ad114fd6170d67ef80fea07fdef8bc0, wrapper privado/nunca carregado. Kernel/patches/config/Image/exports preservados. Caller e física continuam antes de rádio funcional.

## D16. Selecionar IOMMU no caller e intercalar teardown do provider

- **Decisão:** adicionar iommu_parent bool0400 default false exigindo msi_parent/scan_hold e guards atuais. No probe, adquirir provider DART depois de inventário e antes do scan; verificar running/device, então selecionar hold_iommu. Cleanup de associação pendente chama remove_consumers/unmap antes de provider cleanup e só depois scan cleanup/release/status/free; outros modos preservam sua ordem atual. Getter iommu separado sob session_lock, sem alterar formatos anteriores. Recusar dart-release enquanto houver owner OF associado, orientando cleanup da sessão.
- **Por quê:** scan não deve possuir o ciclo MMIO/IRQ/provider do caller. RemoveD13/unmapD14 e releaseD11 são etapas distintas: provider disponível deve sobreviver aos consumidores, e bridge/map/status owner sobreviver ao provider stop. Os guards/pin existentes já conservam energia enquanto scan_bridge ou dart ficam pendentes. Acquiring antes do scan exige adaptar a fixture que hoje só modela dart-hold depois da atribuição.
- **Alternativas:** parar provider antes do PCI deixa consumidores órfãos; associar depois do scan não repete o notifier; realizar provider stop dentro do scan duplica ownership; liberar dart-release isolado durante a associação ignora lifecycle. Rejeitadas.
- **Reverter:** médio na candidata futura por parâmetros, ordem e getter; baixo antes de perfil porque flag default false. Sem Image/kernel patch nova ou alias helper não exportado.
- **Onde:** próxima fase de preparação adapta apenas o gate isolado de cleanup DART e este plano, se necessário, após ler suas extrações atuais. Implementação até cinco públicos: plano, phone/kernel/n71-pcie-diagnostic.c, tests/n71_pcie_diagnostic_caller.c, tests/test_n71_pcie_diagnostic_caller.py e gate de cleanup afetado. Não supor mocks compatíveis: ler os arquivos reais antes de fechar essa preparação. ABI seguinte usa produção exata, sem wrapper privado. Collector/perfil em fatia posterior.
- **Status:** aplicada e qualificada offline: caller185 cenários/129 mutações em Mac e ARM64; provider27+cleanup4/17 mutações por plataforma. Build exato sem wrapper passou W=1/Werror/modpost/ELF/vermagic. Collector/perfil, aliases/máscaras e prova física permanecem abertos. Fonte provider_acquire aceita powered4/attached4 e publica owner antes de start; D16 conserva esses guards e a recusa de driver/MASTER. Sem novo DFU até rota/collector/energia preparados.

### Contratos D16

- [x] Default/guards/seleção antes de efeitos; provider running/bound presente antes de hold_iommu, erro parcial conserva owners e pin.
- [x] Getter requested/ready/held/owner/available/mapped/observed/map_checked/session_error usa só estado sob lock; map_checked significa última leitura OF/core, sem private SID/IRQ/DMA proof.
- [x] Consumers/unmap antes de provider stop; erro nessa etapa bloqueia provider cleanup, restore/reset/power/unpin. Depois de stop, disponibilidade/status e recursos restaurados na mesma sessão; retry sem rescan ou puts duplicados.
- [x] dart-release associado recusa, enquanto modos antigos permanecem compatíveis. Getters anteriores iguais; falhas MMIO/IRQ/provider/MSI/OF/reset/power conservam owners.
- [x] Fixtures reais do caller/cleanup, mutações compiladas por assertion Mac/ARM64, produçãoW=1/Werror/modpost/ELF/vermagic sem wrapper/load. Alias/máscaras e hardware permanecem gates abertos.

Preparação D16: o gate isolado de cleanup usa bridge tipado sem associação para preservar os quatro casos anteriores; cobertura associada executa o caller real com falhas independentes em consumidores/MSI, unmap, provider, host, reset e runtime-PM. Esta fase altera cinco arquivos públicos (plano, caller, fixture do caller, runner do caller, fixture isolada de cleanup).

Qualificação D16: primeiro pacote ARM64 omitiu tests/n71_dart_irq_fixture.h; caller passou mas provider teve 15 falhas de compilação, sem contar como kills. Pacote corrigido em pasta VM separada e provider completo repetido. Fixture do caller corrigida para limpar domínio/count antes de release MSI, como produção; getter verificado em cada falha de teardown e caller completo repetido nos dois ambientes. Mac provider reutilizado com todos os inputs relevantes intactos; D14/D11 helpers e gates conservam hashes. Sem load, reboot/DFU, pacote novo ou alteração global do Mac.

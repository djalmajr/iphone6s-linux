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
- [ ] Acompanhar a CI do head publicado; corrigir eventual falha concreta sem repetir gates alheios. A intermitência anterior da issue38 não foi encerrada por essa correção.
- [ ] Fechar lifecycle MSI e attachment PCI/DART; só então preparar seleção/collector e prova física agrupada.

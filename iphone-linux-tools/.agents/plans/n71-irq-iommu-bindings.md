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
- [ ] F1a: qualificar o cálculo de requisição AIC isolado no Mac/Ubuntu e contexto kernel, sem integração física.
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
- **Status:** referência preparada, qualificação F1a seguinte. Message data, ownership/restore MSI e provider DART retido permanecem pendentes; nenhuma integração de hardware por esta decisão.

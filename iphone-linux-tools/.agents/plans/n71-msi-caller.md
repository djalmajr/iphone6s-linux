# MSI no host retido — ação, getter e cleanup (#40/#9)

## Contexto

Baseb7436e9: owner/callback e adaptador nativo qualificados offline; kernel/config/Image/exports e perfil físico anteriores preservados. CIcceccab aprovou seis jobs; CIb7436e9 tem execuções38025617857/38025615082 em acompanhamento. Não há Linux ativo confirmado nem ação necessária do operador. Não solicitar DFU para testar somente alocação.

`phone/kernel/n71-pcie-msi-allocate.h:8` declara uma lease com endpoint/default_irq/vector; `phone/kernel/n71-pcie-scan.h:22` conserva owners no host. `phone/kernel/n71-pcie-diagnostic.c:187` remove consumidores antes de DART/restauração; a nova lease precisa terminar antes dessa remoção. `:241` despacha actions e `:420` publica o getter MSI de associação. Preservar o contrato desse getter para não quebrar parsers anteriores; criar getter separado de alocação.

## Decisões e arquivos

Guardar a lease no host PCI, junto do owner de configuração. Evita estado global paralelo à sessão e acompanha o lifetime da bridge. A estrutura compartilhada será pequena, sem dependências do host/PCI, em `phone/kernel/n71-msi-allocation-lease.h`; incluir no adaptador e no scan. Todas as actions operam sob session_lock e pin temporário do módulo. Os defaults não executam alocação no probe.

### Fase A — armazenamento (até cinco arquivos)

`phone/kernel/n71-msi-allocation-lease.h`, `phone/kernel/n71-pcie-msi-allocate.h`, `phone/kernel/n71-pcie-scan.h`, `tests/test_n71_pcie_msi_allocate.py` e este plano. Mover o mesmo tipo de lease, sem alterar layout ou política, e armazená-lo no host. A cópia temporária do gate precisa incluir o novo header. Nenhum setter/ABI físico muda nessa fase. O caller/cleanup seguinte usará o campo; não publicar uma candidata incompleta.

### Fase B — actions/getter/cleanup (até cinco arquivos)

`phone/kernel/n71-pcie-diagnostic.c`, `tests/n71_pcie_diagnostic_caller.c`, `tests/test_n71_pcie_diagnostic_caller.py`, `tests/n71_pcie_scan_host.c` e este plano. Incluir o adaptador e actions explícitas `msi-hold`/`msi-release`. `msi-hold` requer scan_hold/msi_parent/iommu_parent, sessão com module/reset/power/domains completos, bus vivo/recursos/providers próprios e ausência de erros. `msi-release` admite erro anterior para cleanup verificado e conserva a primeira causa. A action de cleanup sempre libera MSI antes de remover consumidores/DART; falha ou lease pendente retém bus/reset/power/módulo. Getters antigos permanecem idênticos.

Getter novo `msi_allocation`: ready/held/owner/phase/vector/default_irq/software_enabled/slots/mappings/child/error/session_error. Representa ownership e última validação; não executar novo MMIO nem alegar entrega IRQ. Fase0/1/2 corresponde a EMPTY/ACTIVE/STOPPED. Fields sem host são zero; vector/default_irq dependem da lease, slots/mapcounts do owner nativo. Definir o registro de resultado e cleanup antes de adaptar o collector.

As dependências PCI/IRQ da fixture de caller são modelos; exercitar o código de action/getter/cleanup real. Mutantes devem selecionar funções explicitamente, preservando seletores dos gates anteriores. Cenários: defaults sem ação, opt-in incompleto, pin/lock/lifetime, acquire sucesso/erro antes e depois do capture, getter coerente, release com primeira causa conservada, stop/restore recusados, retry sem nova alocação, cleanup antes de consumers e ausência de put/power/reset prematuros. Guarda de remoção por config phase já existe; testar que o campo de lease fica zerado antes de consumer removal.

### Fase C — build e integração host

Build completa do diagnóstico contra source/config/Image/exports power2 exatos e intactos, W=1/Werror/modpost/ELF/vermagic/imports/bytes/hash. Probe anterior permanece para histórico. Collector/journal/seleção/perfil em fatias subsequentes de até cinco arquivos com plano específico após ler os contratos atuais; getter novo não pode modificar o histórico de associação dos modos antigos. Depois, preparar driver/DMA/firmware e energia na mesma candidata antes de pedir a sessão física agrupada.

## Tarefas

- [ ] Mover tipo da lease e armazenar no host sem alterar a política.
- [ ] Integrar action/getter/cleanup e regressões/mutações compiladas.
- [ ] Qualificar diagnóstico completo ARM64 e preservar os artefatos anteriores.
- [ ] Integrar collector/journal/seleção/perfil com defaults e histórico preservados.
- [ ] Preparar driver/DMA/firmware/energia antes do teste físico agrupado.
- [ ] Publicar reprodução/evidência sanitizada e CI na branch existente, sem main.

## Verificação e limites

Reutilizar os gates de configuração91/27 e os componentes intactos do host183/147 somente se os inputs relevantes permanecerem iguais. Mudanças em scan/caller exigem os respectivos gates, com compilação exit0 e SIGABRT/asserção; nenhuma falha de import/compile/timeout conta como kill. Mac e Ubuntu ARM64, AST e lint fatal, sem instalar ferramentas; nenhum typechecker Python configurado. Compilar a ABI real depois de integrar o caller, sem alterar kernel, exportar símbolos novos ou usar MODPOST_WARN. Fonte build/CI não comprova alocação/IRQ/DMA/rádio/carga/gauge no aparelho. A prova física virá junto dos testes de driver/energia, preservando SSH/Bash/Herdr/HTTP/snapshot/sync e orçamento de bateria.

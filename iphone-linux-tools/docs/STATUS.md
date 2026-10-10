# iPhone 6s Linux — atualizado em 2026-10-10

## Checkpoint atual — configuração MSI qualificada; caller e rádio pendentes

O owner de configuração MSI e o callback PCI passaram no Mac/Ubuntu ARM64:91 cenários/27 mutações do owner e183 cenários/147 mutações do host. O módulo completo passou W=1/Werror/modpost,116.192 bytes/SHA59dc95da,123 imports/ELF/vermagic conferidos. Kernel/config/Image/exports e a candidata física anterior foram preservados. AST/lint fatal passaram; não há typechecker Python. Na VM, o runner atingiu180s; três métodos completos foram reutilizados com inputs intactos, e os três restantes passaram na retomada. [Reprodução](N71_IRQ_IOMMU.md#configuração-msi--owner-e-callback-qualificados), [evidência](evidence/n71-msi-config-qualified.json).

O controle exige grant único, mensagem/readback exatos e MSI off comprovado antes de free/restore. Replays idênticos do core não escrevem; mensagens zeradas são aceitas somente depois de stop. Enable/decode/MASTER continuam negados. Caller nativo, collector/journal/perfil, driver/DMA/firmware e prova física Wi-Fi/energia permanecem pendentes. Nenhum módulo foi carregado, nem DFU/reboot solicitado; não há ação necessária do operador nesta fase.

## Etapa anterior — brcmfmac corrigido e recompilado

A correção do retorno MSI passou gates offline no Mac/Ubuntu ARM64 e build dos oito módulos com ABI power2. Uma falha MSI agora retorna antes do request IRQ. Fonte/kernel/Image/config/exports e os oito módulos de rollback foram preservados; somente o novo brcmfmac mudou,499.496 bytes/SHA1c54194c.16 cenários C,13 mutações compiladas mais regressão original,15 testes/24 mutações do builder por plataforma; AST/lint fatal e verificação independente dos artefatos passaram. [Reprodução e limites](N71_WIFI_MODULES.md#correção-de-falha-msi--2026-10-09), [evidência](evidence/n71-brcmfmac-msi-error-qualified.json).

Nenhum novo DFU, reboot, instalação ou módulo/firmware carregado nesta etapa. As provas físicas abaixo permanecem válidas. A integração PCI/MSI/driver/DMA e a validação de Wi-Fi nativo e carga/gauge permanecem nas issues #40/#9/#2 e no goal ativo. Só será pedida uma ação física indispensável, com todos os testes preparados. CI desta publicação será acompanhada na própria branch; nenhuma integração em main.

## Associação IOMMU e atribuição físicas positivas; IRQ/DMA, Wi-Fi e energia pendentes

A candidata corrigida SHA48df330a passou em um DFU/boot: associação MSI/OF/core dos dois dispositivos ao mesmo grupo IOMMU0, RIDs0008/0100, masks32/map_sid0 e atribuição error0/assigned1,17 tentativas/cinco escritas. SSH/Bash/HTTP/Herdr/restore passaram. O gate GPIO já aprovado não foi repetido. [Prova física atual](evidence/n71-of-scope-association-physical.json), [procedimento e limites](N71_IRQ_IOMMU.md#associação-física-após-corrigir-of--erro-preservado-no-cleanup).

O cleanup real restaurou16 TTBRs/recursos/config/PME/TLS/reset/energia, removeu bus/provider e zerou owners, preservando EIO do DART por command00000f02→00000102. O verificador confundiu esse erro posterior com ownership pendente. Recuperação no mesmo boot comprovou unload normal, REG_ON original e serviços. Snapshot44/sync salvos; retorno automático não confirmado pelo USB, sem nova confirmação de tela solicitada conforme orientação do operador. Não houve segundo DFU, scan ou setter.

A correção host conserva o erro e exige prova completa/causal/ordenada para liberar recursos; reparse dos logs originais passou. Mac/Ubuntu ARM64:113 testes/141 mutações por asserção por plataforma, AST e `--check` real passaram. Lint fatal também passou nas duas plataformas; CI própria pendente, anterior3a61c76 completa verde em ambos os eventos. Nenhum novo módulo/kernel/perfil/pacote/configuração global do Mac. Entrega IRQ, tradução DMA, driver/rádio/Wi-Fi, gauge e carga Linux continuam pendentes; power_supply0/MaxPower500mA não provam corrente. [Plano da correção](../.agents/plans/n71-dart-cleanup-operation-error.md), [qualificação](evidence/n71-dart-cleanup-operation-qualified.json).

O primeiro teste D20 havia recusado a associação OF antes do scan, mas permitiu a prova GPIO115/114 no mesmo boot; [histórico físico](evidence/n71-iommu-pins-physical.json). A guarda OF e o parser negativo foram corrigidos, módulo real Werror/modpost e candidata qualificados preservando kernel/payload/initramfs/identidades/REG_ON. [Build](evidence/n71-of-scope-negative-cleanup.json), [perfil](evidence/n71-of-scope-profile-qualified.json). Esses gates continuam reutilizados com inputs relevantes intactos.

A candidata15617e32 passou no hardware: atribuição error0/assigned1,17 tentativas/cinco escritas verificadas, IO16 noops1 e PREF64 writes1. Um DFU/um boot reuniu inventário, reuso sem segundo setter, cleanup na primeira tentativa, SSH/Bash/Herdr/HTTP e snapshot44/sync/retorno automático ao iOS.100→100%, carregando após o retorno. [Prova física](evidence/n71-pci-pref64-unsized-physical.json).

Root MEM7c0000000..7c04fffff; BAR0 7c0400000..7c0407fff/BAR2 7c0000000..7c03fffff. Decode/master/driver/radio permaneceram desligados. IRQ255/0, links IOMMU/of_node/driver ausentes e power_supply0 não comprovam IRQ/DMA/Wi-Fi/carga. Issue39 conclui host retido/atribuição/rollback; próxima fatia trata associação IRQ/IOMMU na [issue40](https://github.com/djalmajr/iphone6s-linux/issues/40), para Wi-Fi (#9). [Plano inicial](../.agents/plans/n71-irq-iommu-bindings.md), [auditoria de fontes](N71_IRQ_IOMMU.md). Alimentação/gauge continuam na #2.

### Pinos I2C1 — novo módulo qualificado, sem reinicializar

Um módulo separado reserva/libera GPIO115/114 com ASIS em dois ciclos síncronos, usando consumidor/lookup próprios e leituras cache/bypassed antes/durante/depois. Não seleciona mux nem ativa I2C1. Mac/Ubuntu ARM64: 107 cenários e 22 mutações compiladas por asserção por plataforma. Build real de 13.720 bytes, ELF64/AArch64/vermagic power2; 39 imports conferidos no vmlinux.symvers preservado, fornecido por KBUILD_EXTRA_SYMBOLS após o aviso de Module.symvers agregado ausente. Fonte/patch/config/Image/exports intactos; AST/lint fatal passaram. [Procedimento e limites](N71_I2C_PINS.md), [prova offline](evidence/n71-i2c-pin-cycles.json), [plano](../.agents/plans/n71-i2c-pin-cycle.md).

O gate integra a descoberta de testes da CI existente. As duas execuções do head `ba9473c` concluíram com seis jobs aprovados; os quatro logs de fonte confirmaram 107 cenários/22 mutações do gate novo por job. [Prova terminal](evidence/n71-i2c-pin-cycles-ci.json). Em2026-10-09, o módulo passou por SSH no mesmo boot D20: dois ciclos de descriptors GPIO e readback integral, unload e cleanup comprovados. Mux, I2C/SN2400, gauge e carga Linux seguem pendentes; GPIO reservation não equivale a essas provas.

### D20 — perfil IOMMU composto e qualificado; teste físico preparado

Flags explícitas `--pcie-iommu-parent` no composer e `--iommu-parent` no collector ligam a ABI D18 à Image power2 exata, com decompression limitada e igualdade de perfil/CLI antes de SSH. As políticas de atribuição anteriores e REG_ON são preservados. A candidata privada tem oito arquivos700/600; conserva loader/bootargs/kernel/initramfs/chaves e acrescenta somente phandle45 ao DART desativado, sem mapa permanente. O staging antigo já usa41–44; essa colisão foi detectada e corrigida antes do boot. Perfil anterior e snapshot44 permanecem preservados. [Reprodução D20](N71_IRQ_IOMMU.md#d20--seleção-image-e-candidata-privada), [Image](evidence/n71-iommu-image-qualification.json), [integração](evidence/n71-iommu-profile-qualification.json), [composição real](evidence/n71-iommu-private-profile.json).

Mac/Ubuntu ARM64: D20a107 testes/122 mutações; D20b125/130, com seis gates intactos reutilizados; D20c30/24, novo perfil8/21. Os escopos se sobrepõem e não devem ser somados. AST/lint fatal passaram; não há typechecker Python. Composer real e `--check` passaram,84 inputs da ABI D18 intactos e nenhum rebuild de kernel/módulo. A prova publicada cobre preparação, não execução do novo perfil. A sessão física agrupada está preparada; a primeira janela de DFU terminou sem Pongo/envio de payload e o USB confirmou recuperação (0x1281); Wi-Fi, entrega IRQ/tradução DMA, gauge e carga Linux continuam pendentes. Sem pacote/configuração global do Mac, banco ou desempenho físico novo medido.

O gate externo de mutações foi corrigido em `9faff88`: a cópia pública temporária agora inclui `n71_iommu_build.py`, importado pelo composer e pelo resource selector. Erro de import reproduzido antes da edição, sem contar como kill; depois baseline22 testes e34/34 mutants por AssertionError passaram no Mac24.80s/Ubuntu ARM6414.91s. AST/lint fatal passaram; candidata e os sete inputs executáveis D20/84 inputs da ABI D18 permaneceram intactos. A CI completa do novo head ainda precisa terminar. [Reprodução do gate](N71_IRQ_IOMMU.md#d20d--dependência-do-helper-na-cópia-pública-de-mutações), [prova limitada](evidence/n71-iommu-mutation-dependencies.json). Sem nova ação USB/DFU, rebuild ou alteração de produção.

A falha da CI33fca56 foi corrigida em `25b9f82`: dois selectors antigos das mutações de Session passaram a conservar o argumento IOMMU novo enquanto removem somente resource_capable. Gate held completo21 testes/30 mutants passou no Mac42.88s/Ubuntu ARM6419.67s, inclusive ambos os selectors; AST/lint fatal passaram e592 inputs foram conferidos. A CI anterior executou638 testes por source job e falhou nesse parent de mutações, com20 skips; Windows passou. Produção/candidata/84 inputs da ABI D18 intactos. [Reprodução](N71_IRQ_IOMMU.md#d20e--selectors-das-mutações-de-session), [prova](evidence/n71-held-iommu-selectors.json). As duas execuções completas do headab118aa concluíram com sucesso: seis jobs Mac/Ubuntu/Windows aprovados. [Prova da CI](evidence/n71-iommu-ci-qualified.json). Isso não comprova o teste físico ainda pendente.

### D19 — collector e journal DMA qualificados

O opt-in IOMMU seleciona agora somente a ABI D18 exata, com fonte/patch/weak binding/exports conferidos na prova. Exige dois registros MSI/DMA/IOMMU/device ordenados, RIDs0008/0100, mesmo grupo não negativo, masks32 e aliases inferidos root1/endpoint1 ou2. O journal reconstrói essas observações; alterações em grupo, máscaras, RIDs, aliases ou nível de prova são recusadas antes de qualquer efeito no resume. Default false e modos antigos permanecem; o opt-in IOMMU D16, que só foi qualificado offline, é recusado pelo novo seletor. [Reprodução](N71_IRQ_IOMMU.md#d19--collector-e-journal-dma), [prova](evidence/n71-dma-collector-qualification.json).

Mac/Ubuntu ARM64 passaram99 testes/98 mutações por plataforma; novo gate17/42. AST/lint fatal passaram; não há typechecker Python. ABI D18 reutilizada com84 inputs relevantes intactos, sem rebuild/load/DFU. Próximo: flags/selector/composer de perfil privado devem ligar o módulo D18 à Image power2 exata e preservar rollback/serviços/snapshot/orçamento energético antes do teste físico agrupado. Wi-Fi, entrega IRQ/tradução DMA, gauge e carga Linux seguem pendentes. Sem banco/pacote/configuração global do Mac; desempenho físico não medido.

### D18 — fundamentos DMA qualificados offline

O diagnóstico opt-in IOMMU agora recusa drift no grafo PCI N71, aliases locais/flags especiais, multifunction/PF/VF e máscaras streaming/coherent diferentes de32 bits ou ponteiro DMA estrangeiro. Confere o mesmo ID de grupo por get/id/put exportados, sem reter a referência. Aliases são inferidos da topologia pública e do binding weak fixado; o log distingue essa inferência de tradução física. Cleanup limpa o ID depois da remoção PCI e antes de liberar MSI, inclusive em falha posterior. [Código/fontes/reprodução](N71_IRQ_IOMMU.md#d18--topologia-dma-máscaras-e-grupo-iommu), [prova](evidence/n71-dma-topology-qualification.json).

Mac/Ubuntu ARM64 passaram253 cenários/190 mutações compiladas por asserção por plataforma,55/40 novos; AST/lint fatal e módulo exato W=1/Werror/modpost/ELF/vermagic passaram. PCIe114008 bytes/SHA46dfdfda; fonte com seis patches, config/Image/exports preservados. CI parent6aeb88c passou os três jobs; CI própria D18 iniciou separadamente. Nenhum load/perfil físico novo nesta etapa. Collector concluído em D19 acima; falta composição e teste físico agrupado. Wi-Fi, IRQ/DMA reais, gauge e carregamento Linux continuam pendentes; nenhum novo DFU solicitado nesta rodada. Sem banco/dependência/pacote ou configuração global do Mac; desempenho físico não medido.

Auditoria2026-10-07 UTC recuperou pin1/MSI64 do log físico anterior, sem novo boot. ADT/driver N71: MSI32/offset256/porta1/base8/count8, registro parent AIC264..271; Linux usa células3/hwirq próprio. Helper F1a qualificado:61 cenários/14 mutações por asserção no Mac/Ubuntu ARM64, AST/lint fatal e probe kernel Werror/modpost/ELF/vermagic, fonte/config/Image/exports preservados. Calcula somente `<0, 264 + índice, 1>`, sem IRQ/domain/MMIO/message data/caller ou carga no telefone. Codificação MSI, restore/ownership e provider DART retido permanecem abertos. [Referência e limites](evidence/n71-irq-iommu-reference.json), [prova e reprodução F1a](N71_IRQ_IOMMU.md#f1a--células-aic-qualificadas-sem-alocação-de-irq). Telefone no iOS durante a preparação; carga/gauge Linux não comprovados.

### DART retido — implementação e qualificação offline

Commits c0fb252/003998d integram o provider ao owner da sessão, com `dart-hold`, `dart-release` e getter separado. Erros de stop/claim/read/guard/write conservam baseline/MMIO/node/estado para tentar novamente no mesmo boot; cleanup PCI/reset/energia/module pin espera o DART terminar. Readiness é invalidada quando começa o cleanup, inclusive stop parcial. Erro original permanece após liberar ownership. [Código e reprodução](N71_IRQ_IOMMU.md#f1bf1c--provider-dart-retido-e-recuperação-na-mesma-sessão), [prova sanitizada](evidence/n71-dart-retained-qualification.json).

Mac e Ubuntu ARM64 passaram92 cenários/32 mutações compiladas por asserção; callbacks reais do provider e funções reais do cleanup foram executados com APIs kernel simuladas. Regressão temporária passou; build do módulo completo W=1/Werror/modpost/ELF/vermagic passou,91.736 bytes/SHAae3e71f2, fonte/config/Image/exports preservados. Isso não prova hardware. Nenhum perfil/autoload/load/DFU novo; o Mac não detectou o iPhone no USB na última leitura desta rodada. Próximo gate: ownership IRQ atômico e baseline/restore de máscaras, seguido de collector/seleção e sessão física agrupada. IRQ/DMA/Wi-Fi e carga/gauge continuam abertos, assim como o goal.

### Qualificação offline da candidata física


A elegibilidade aceita recurso PREF vazio exato antes do sizing, além do recurso tipado exato anterior. Probes64, ownership, baseline00010001/uppers0, estado vivo, readback completo0001fff1, primeiro erro e rollback continuam estritos. Fixture reproduziu a recusa física anterior e passou com a correção. [D3/plano](../.agents/plans/n71-pref64-disable-pci.md), [adapter](evidence/n71-pci-pref64-unsized-adapter.json).

Mac/Ubuntu ARM64:138 cenários/105 mutações C nos gates afetados; pure319/97 reutilizado com42 inputs intactos, total457/202 por plataforma. Só a suíte IO16 com âncoras de mutação ambíguas foi repetida após delimitação. Build externo passou seis módulos Werror/modpost/ELF/vermagic,50 inputs;PCIe88.184 bytes/SHA15617e32. Fonte/config/Image/exports/REG_ON/outros cinco módulos preservados. Seleção41/68 por plataforma liga qualificação e base por hash, conservando rollback pelos hashes anteriores. [Build](evidence/n71-pci-pref64-unsized-build.json).

Integração95 testes/150 mutações por plataforma,80 inputs/AST/lint fatal. Candidata real passou composer/check: oito arquivos700/600; só PCIe/provenance hash mudam, sem carga automática. Snapshot44 recente verificado. Próximo boot agrupa acquire/assign/inventário PCI-IRQ-IOMMU sem escrita/cleanup/services/snapshot/sync/iOS. Essa preparação foi seguida da prova física positiva acima; Wi-Fi, carga e gauge continuam pendentes. [Candidata](evidence/n71-pci-pref64-unsized-profile.json), [reprodução](N71_PME_ASPM_CANDIDATE.md#lifecycle-pref64-corrigido--reprodução).

### PREF64 físico anterior — recusa antes de capture; contexto de D3

A candidata968e6a06 iniciou em um DFU/um boot, com restauração44 e sem reinícios intermediários. Acquire, inventário PCI/IRQ/IOMMU sem escrita, cleanup/retry, SSH/Bash/Herdr/HTTP, snapshot/sync e retorno automático ao iOS passaram. Bateria iOS100→100%, carregando após o retorno. [Prova física sanitizada](evidence/n71-pci-pref64-physical.json).

Assign recusou error-13 antes de capture/claim/tentativas/escritas; os três reports ficaram captured0 e owners foram liberados por retry somente de limpeza. A leitura confirmou recursos da ponte todos0 e PREF lower00010001/uppers0. A hipótese foi introduzida no adapter: exigir recurso PREF já preenchido antes de `pci_bus_size_bridges`. Na fonte fixada, scan sonda capabilities com recurso temporário e sizing preenche flags da ponte posteriormente. Corrigir a elegibilidade para aceitar o estado vazio exato também, mantendo probes64/capture/estado vivo/readback/rollback estritos. [Decisão D3 e sequência](../.agents/plans/n71-pref64-disable-pci.md).

IRQ root255/endpoint0, driver/IOMMU/of_node ausentes e power_supply0 são inventário do modo sem bind/DMA, sem prova de funcionamento ou de defeito nesses componentes. Wi-Fi, telemetria e carga Linux continuam pendentes. Desenvolvimento/build prosseguem offline enquanto o iPhone carrega no iOS; nenhuma nova sessão até qualificação/composição completas.

### Qualificação PREF64 anterior ao teste físico

C final442 cenários/199 mutações compiladas por plataforma; host/journal89/149, seleção32/62 e integração94/150 passaram no Mac/Ubuntu ARM64. Seis módulos Werror/modpost/ELF/vermagic,50 inputs;PCIe88.120 bytes/SHA968e6a06. Kernel/fonte/config/Image/exports/REG_ON/outros cinco preservados. Candidata passou composer/check com oito arquivos700/600. Essa qualificação sintética não cobriu a janela vazia medida no hardware. [Política](evidence/n71-pci-pref64-policy.json), [build](evidence/n71-pci-pref64-build.json), [candidata](evidence/n71-pci-pref64-profile.json).

### IO16 físico anterior — correção comprovada; primeira recusa em PREF

Um DFU/um boot Linux reuniu acquire, assign, leitura sem escrita, cleanup/retry e serviços, sem reinícios intermediários. O primeiro monitor expirou antes de enviar payload; o segundo carregou a candidata no DFU já detectado, sem outra sequência de botões. IO16 foi habilitado e o pedido upper0000ffff recebeu exatamente um no-op; lower00f0 e BARs/MMIO avançaram com readback estrito. [Prova física](evidence/n71-pci-io16-physical.json).

A atribuição continua negativa: error-5,14 tentativas/quatro escritas verificadas. Primeira falha root0:08/0x24/dword: pedido0000fff0, anterior00010001, retorno válido0001fff1, callbacks sem erro. A leitura separada confirmou PREF lower0001fff1/uppers0 e IO lower00f0/upper0. Os bits de endereço foram alterados, mas os dois tipos64 ficaram1; a próxima correção será restrita a esse disable, com probe/recurso/baseline/estado vivo e readback completo comprovados. Não aceitar mismatch geral.

Cleanup/retry somente de limpeza liberou PCI/REG_ON e preservou o primeiro erro e os reports. SSH/Bash/Herdr/HTTP/sync passaram; snapshot44 e sync foram verificados antes do pedido de retorno. O retorno automático não apareceu no USB no prazo; fallback físico chegou à tela de bloqueio segundo o operador, ainda sem confirmação USB/bateria posterior. Não requer PIN. Wi-Fi/IRQ/IOMMU/driver/radio e telemetria/carga continuam pendentes.

### Preparação IO16 anterior ao teste físico

A nova política trata somente o pedido temporário root0:08/upper0x30/dword0000ffff em IO16 presente padrão4K, com os dois tipos e o recurso coerentes, lower/upper baseline0 e estado vivo confirmado. Faz no-op sem escrita upper; lower00f0 continua gravado/verificado, junto de MMIO/BARs. Primeiro erro, decode/master, budgets e rollback permanecem. Report próprio é exigido somente para o novo SHA e conservado no journal/reuso/cleanup. [Plano](../.agents/plans/n71-io16-upper-pci.md), [política](evidence/n71-pci-io16-policy.json), [build](evidence/n71-pci-io16-build.json), [integração](evidence/n71-pci-io16-profile.json).

Mac/Ubuntu ARM64: C final367 cenários/159 mutações compiladas por assertion por plataforma; host/journal78 testes/131 mutações, seleção25/54 e integração82/132,72 inputs/AST/lint fatal. Gates independentes reutilizados somente com inputs relevantes intactos. Seis módulos Werror/modpost/ELF/vermagic,49 inputs;PCIe87.008 bytes/SHAd6188a13. Outros cinco módulos e fonte/config/Image/exports preservados.

Candidata real separada passou composer/--check: oito arquivos700/600, mesmo deployment/payload/DT/kernel/loader/initramfs/identidades/REG_ON do perfil optional. Somente PCIe e seu SHA na provenance mudaram. Defaults/perfis anteriores conservados, nenhum pacote/configuração global instalado no Mac ou Image novo. Esse checkpoint de preparação não era prova física; o teste posterior está registrado acima em arquivo próprio. Atribuição positiva, IRQ/IOMMU/driver/radio, Wi-Fi e telemetria/carga continuam pendentes até provas próprias.

### Sessão anterior — janelas presentes, atribuição recusada e limpeza comprovada

A candidata SHA fba31cb2 rodou em um único boot/DFU, sem reinícios intermediários. Aquisição PCI retida passou; o PCI core declarou IO/prefetch presentes (`io_absent=0`, `pref_absent=0`), portanto nenhum no-op de range ausente foi aplicado. A atribuição preservou o primeiro erro -5 em root0:08/0x30: pedido0000ffff, anterior/retorno0, callbacks sem erro. Essa sessão não comprova atribuição positiva nem ausência das janelas. [Prova física](evidence/n71-pci-optional-physical.json).

Leitura sem escrita confirmou IO base/limit e upper zerados. Os tipos base/limit são0 (IO16 na fonte PCI fixada); em `pci_setup_bridge_io`, Linux escreve upper0000ffff antes de desativar lower00f0 mesmo quando a janela é de16 bits. O próximo desenvolvimento qualificará somente esse pedido upper sem efeito, com opt-in, tipo/baseline/estado vivo verificados; lower/MMIO/BARs permanecem estritos. Não aceitar qualquer readback zero nem inferir ausência de IO.

Cleanup/retry somente de limpeza liberou PCI/REG_ON, preservando o erro original e ambos os reports. SSH/Bash/Herdr/HTTP/sync passaram em86,61 segundos de uptime. Snapshot44 e retorno automático iOS confirmados; bateria100% e recarga ativa no retorno. Percentual arredondado e fonte externa não comprovam corrente ou carregamento Linux. Telefone fica no iOS durante desenvolvimento/build, sem nova intervenção física nesta etapa.

### Preparação anterior — candidata de janelas opcionais qualificada

A correção trata somente pedidos de desativação de IO/prefetch quando flags/probes PCI core comprovam ausência, os recursos estão vazios, a baseline é zero e os registradores vivos continuam zerados. Faz no-op sem escrita nesses ranges; BARs/MMIO implementados, decode/master, primeiro erro e rollback continuam estritos. Registro único conserva flags/counters; o journal o exige somente para o novo módulo selecionado por hash e preserva seu conteúdo até o cleanup. [Plano](../.agents/plans/n71-janelas-opcionais-pci.md), [build](evidence/n71-pci-optional-build.json), [integração/candidata](evidence/n71-pci-optional-profile.json).

Mac/Ubuntu ARM64: conjunto C final 298 cenários/122 mutações compiladas por assertion por plataforma; contrato/journal 70 testes/119 mutações por AssertionError; seleção 19/45; integração final 73/120, 67 inputs/AST/lint fatal. Seis módulos Werror/modpost/ELF/vermagic; PCIe 86.304 bytes/SHA fba31cb2, outros cinco preservados. Fonte/config/Image/exports conferidos antes/depois, incluindo oito fontes PCI e seis patched.

Candidata real separada passou composer/--check: oito arquivos privados700/600; deployment, payload/DT/kernel/loader/initramfs, identidades e REG_ON iguais ao perfil readback anterior. Somente PCIe e seu SHA na provenance mudaram. A preparação não instalou pacote/configuração global no Mac nem reconstruiu Image. A sessão agrupada acima executou aquisição/assign/coleta, cleanup/retry, serviços, snapshot/sync e retorno ao iOS. Wi-Fi/IRQ/IOMMU/driver e energia permanecem pendentes até provas próprias.

CI do checkpoint publicado e04e0e6: macOS e Windows passaram; Ubuntu marcou erros nos testes PMGR e encerrou antes do resumo com exit143. Causa não confirmada, registrada na #38; gates locais/VM não substituem a matriz completa.

### Primeiro readback físico — uma sessão agrupada

Um DFU/um boot, sem reinícios intermediários: aquisição PCI retida positiva; atribuição negativa `error=-5`, nove tentativas/duas escritas verificadas. O novo registro conserva a primeira falha root 0:08/0x30/dword: pedido `0x0000ffff`, anterior `0`, retorno válido `0`, write/read callbacks sem erro. Leitura separada confirmou IO base/limit 0x1c e upper 0x30 zerados, no mesmo boot e sem escrita. Isso mede o comportamento; a semântica de janela opcional ainda precisa de correção qualificada. [Prova física](evidence/n71-pci-readback-physical.json).

Primeiro cleanup restaurou bus/configuração/janelas e reteve owners; retry somente de limpeza liberou PCI/REG_ON, preservando o erro -5 e a mesma leitura. SSH/Bash/Herdr/HTTP e sync passaram, com uptime de serviços de 235 segundos. Snapshot com 44 entradas foi verificado e o retorno automático ao iOS foi confirmado pelo USB. Bateria iOS após a sessão: 94%, carregando e com fonte externa conectada/capaz. Não é prova de corrente/carga no Linux ou de saúde da bateria.

Próxima implementação: tratar janelas opcionais ausentes com base nos flags/probes do PCI core e nos registradores zerados, conservando readback estrito das janelas implementadas e MMIO/BARs. Preparar IO e prefetch compatíveis antes de outro DFU; desenvolver com o telefone no iOS para recarga. Wi-Fi nativo e energia continuam em curso; CI completa permanece gate separado (#38).

### Preparação da candidata de readback

A correção conserva a primeira escrita/leitura que falhar na atribuição PCI, com pedido, valor anterior, valor retornado válido e erros brutos. Usa as operações que já eram exigidas; as permissões de escrita e o rollback continuam iguais. O adaptador emite um registro único antes do resultado; o journal conserva esse registro no checkpoint, reuso e cleanup. A seleção por hash exige o registro somente para o build novo e mantém o build anterior disponível. [Plano](../.agents/plans/n71-primeiro-readback-pci.md), [reprodução](N71_PME_ASPM_CANDIDATE.md#readback-da-primeira-falha--candidata-qualificada-sem-reiniciar).

Mac/Ubuntu ARM64: política194 cenários/36 mutações e adaptador65/57 por plataforma, com compilação Werror e SIGABRT/assertion. Integração final64 testes/108 mutações por AssertionError por plataforma,62 inputs/AST/lint fatal; seleção5/9 e contrato9/29 também passaram. Gates anteriores intactos foram reutilizados; tentativas de import, fixture ou anchor inválidos ficaram excluídas. [Build e contratos](evidence/n71-pci-resource-readback.json), [integração e candidata](evidence/n71-pci-readback-profile.json).

Seis módulos passaram build real na VM dedicada, com 48 inputs. PCIe: 85.096 bytes/SHA a56fafb4; outros cinco módulos, fontes PCI verificadas e config/Image/exports preservados. Candidata privada separada com oito arquivos passou composer/--check: deployment, payload/DT/kernel/loader, initramfs, identidades e REG_ON iguais ao perfil anterior; somente PCIe e seu SHA na provenance mudaram. Nenhum pacote/configuração global instalado no Mac, novo Image ou boot físico nesta preparação.

O iPhone foi reconfirmado no iOS com100% e alimentação externa conectada/capaz. A próxima sessão reúne aquisição, atribuição, primeira leitura, cleanup/retry, serviços e snapshot/sync/retorno ao iOS no mesmo boot. O valor real0x30 ainda não foi medido pelo módulo novo; atribuição positiva, IRQ/IOMMU/driver/firmware, Wi-Fi e telemetria/carga permanecem pendentes. CI completa continua como gate separado (#38); a preparação local não comprova execução no hardware.

### Sessão física anterior — aquisição e atribuição negativa com cleanup comprovado

Um boot power2 restaurou44 entradas e confirmou SSH/HTTP/Bash/Herdr. A aquisição retida passou com dois dispositivos/um endpoint Broadcom e decode/master desativados. A primeira continuação foi recusada antes do setter por uma leitura REG_ON registrada pelo getter; correção `eba8f30`/fixture `71df973` passou Mac/Ubuntu ARM6444 testes/63 mutações por AssertionError por plataforma,57 inputs/AST/Flake8 fatal. Conserva o prefixo integral e admite somente leituras positivas completas com valor igual ao getter vivo; todos os registros e hashes privados permanecem. [Reprodução](N71_PME_ASPM_CANDIDATE.md#primeira-atribuição-física--erro-preservado-e-cleanup-retomado), [regressão](evidence/n71-reg-on-held-history.json).

Atribuição uma vez: error-5,9 tentativas/2 escritas verificadas, assigned0/pending1/claimed1. O contador não inclui uma escrita que falhou na verificação posterior. Primeira recusa root0:08/030/dword/0000ffff; readback real não foi registrado, e recusas seguintes são latched. Primeiro release restaurou bus/configuração/janela e reteve reset/energia; retry somente de cleanup liberou owners/módulos e REG_ON80. Resultado permaneceu negativo, cleanup_verified true/stop-error-5. Snapshot44/sync e retorno automático iOS passaram; uptime final26 minutos, zero reinícios intermediários. iOS100→77%, incluindo transições, com recarga/fonte externas ativas no retorno; não comprova corrente, saúde ou carga Linux. [Prova física selecionada](evidence/n71-pci-resource-first-physical.json).

Próximo desenvolvimento: registrar o readback real da primeira recusa0x30 antes de mudar permissões. Kernel/payload/módulos preservados nesta correção; iPhone no iOS para recarga durante trabalho offline. Atribuição positiva, IRQ/IOMMU/driver/firmware, Wi-Fi e telemetria/carga continuam pendentes. CI de `9aebe85` terminou cancelled nos eventos PR/push, causa não confirmada; gates locais separados não substituem CI completa (#38).

### Journal anterior — preparação host

Código `2e07258` oferece `--assign-held`, exclusivo de release e dependente do perfil resource-capable held. Confere boot/perfil/módulos/params/REG_ON/histórico/getter e salva intenção antes do setter, depois prova privada/hash/checkpoint. Retomada reutiliza atribuição sem outro setter; cleanup comprova rollback extra/janela e owners antes de PCI unload/REG_ON restore. Erros de atribuição/stop continuam negativos mesmo após cleanup completo; prova perdida ou estado contraditório recusam efeitos. Mac/Ubuntu ARM64: 82 testes/137 mutações por AssertionError por plataforma,55 inputs/logs/exit SHA, estágio16/26, held21/30 e legado45/81;37/56 Mac intactos reutilizados, ARM64 executou o conjunto. Comandos de ação/snapshot rodaram em Bash contra arquivos privados sintéticos. [Reprodução](N71_PME_ASPM_CANDIDATE.md#atribuição-com-journal--ação-e-limpeza-no-mesmo-boot), [prova sanitizada](evidence/n71-pci-resource-session.json).

Candidata real preparada abaixo passou o check atualizado;48 inputs do build real intactos, sem nova compilação/load/DFU naquele checkpoint. A sessão agrupada seguinte está descrita acima. IRQ/IOMMU/driver/firmware, Wi-Fi e telemetria/carga Linux continuam pendentes. Provas host/sintéticas e build não comprovam os recursos físicos.

### Seleção anterior — candidata privada preparada

Código `d94a14e` liga o build com atribuição ao composer/coletor através de `--pcie-resource-capable`/`--resource-capable`. Exige held/power2/ASPM/REG_ON explícitos, provenance booleana exata, módulos qualificados e --check sem SSH/USB. A aquisição não atribui automaticamente; defaults e seletor held anterior permanecem. Mac/Ubuntu ARM64: 82 testes/144 mutações por AssertionError em cada plataforma,53 inputs/logs/exit por SHA, seis testes/12 mutações novos. Após correções somente na fixture composer,66 testes/30 mutações foram reutilizados com52 inputs intactos; demais gates executados sobre o pacote final. [Reprodução](N71_PME_ASPM_CANDIDATE.md#seleção-do-módulo-com-atribuição--candidata-privada-preparada), [prova sanitizada](evidence/n71-pci-resource-profile.json).

Candidata privada real completa passou composer/--check, preservando payload/DT/kernel/loader/initramfs/identidades/deployment/REG_ON do perfil held anterior. PCIe84.696 bytes/SHA2dcdebc2 e provenance novos;48 inputs do build real186 intactos e reutilizados. Nenhum load ou DFU naquela etapa. O journal avançou acima; atribuição/restauração no aparelho, IRQ/IOMMU/driver, Wi-Fi e telemetria/carga permanecem abertos. CI anterior `5df8a73`: [PR37401468009](https://github.com/djalmajr/iphone6s-linux/actions/runs/37401468009) e [push37401463964](https://github.com/djalmajr/iphone6s-linux/actions/runs/37401463964) cancelled; Mac/Windows success e Ubuntu cancelled nos dois eventos, causa não confirmada. Não cobre esta seleção.

### Atribuição PCI anterior — caller integrado e módulos compilados

Adaptador `3f09eec` reserva a janela MEM32 na árvore iomem, chama sizing/atribuição e valida recursos/configuração. Caller `3ff8769` expõe `action=assign` no bus retido, com mutex/pin e módulo/reset/quatro domínios ativos; sem repetir scan, enable/bind/DMA. Getter `resources` exige ownership vivo, conserva o primeiro erro e não apresenta bus removido como atribuído. Mac/Ubuntu ARM64: adaptador64 cenários/51 mutações e caller121/59 por plataforma, inputs/logs/exit por SHA; dependências PCI/kernel sintéticas. Seis módulos passaram build real Werror/modpost/ELF/vermagic, com48 inputs públicos, PCIe84.696 bytes e REG_ON intacto, fonte/config/Image/exports preservados. Interface action/resources/held/status e referências alocador/reserva/release vinculadas verificadas. [Reprodução](N71_PME_ASPM_CANDIDATE.md#atribuição-no-bus-retido--adaptador-caller-e-build-real), [prova sanitizada](evidence/n71-pci-resource-assignment.json), [decisão D3](../.agents/plans/n71-funcional-goal-decisoes.md#d3-atribuição-pci-pelo-alocador-do-kernel).

Neste checkpoint, seleção/provenance/journal do host ainda precisavam reconhecer a atribuição antes de efeitos por SSH; a seleção e o checkpoint da ação avançaram acima. Nenhum novo módulo carregado, Image, USB/DFU ou prova física naquela etapa. Atribuição/restauração no aparelho, IRQ/IOMMU/driver/firmware/radio, Wi-Fi e telemetria/carga Linux continuam pendentes. CI anterior `3f09eec`: [PR37394918817](https://github.com/djalmajr/iphone6s-linux/actions/runs/37394918817) e [push37394914087](https://github.com/djalmajr/iphone6s-linux/actions/runs/37394914087) cancelled; Mac/Windows success e Ubuntu cancelled nos dois eventos. Log Ubuntu da PR indisponível, causa não confirmada na [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38); não cobre o caller novo.

### Política isolada anterior — qualificação do contrato de escrita

Política `8c16d0a` delimita as escritas que o alocador PCI poderá fazer no barramento retido: BAR0/BAR2 alinhados na janela MEM32 selecionada, upper32 zero, janela MEM compatível, IO/PREF somente desativados, COMMAND/BRIDGE_CONTROL preservados. Antes dos efeitos, captura a configuração e três registradores adicionais; confere identidade/decode/master e readback, conserva o primeiro erro e mantém pending em falhas de restauração. Mac/Ubuntu ARM64: 188 cenários nativos e 25 mutações compiladas por SIGABRT/assertion em cada plataforma, seis inputs/logs por SHA, AST e Flake8 fatal. [Reprodução e limites](N71_PME_ASPM_CANDIDATE.md#política-de-escritas-de-atribuição-pci--preparação-offline), [prova sanitizada](evidence/n71-pci-resource-write.json).

As APIs do alocador estão exportadas pelo kernel selecionado. Naquele checkpoint, a política ainda não estava conectada ao adaptador/caller/journal e a prova não chamava PCI core; reserva/atribuição, sobreposição final, registradores opcionais, IRQ/DMA/IOMMU, Wi-Fi e carga/telemetria Linux permaneciam pendentes. Nenhum novo kernel/módulo, USB ou DFU naquela etapa. A CI do perfil anterior `8f35fd2` concluiu success nos seis jobs: [PR37390299442](https://github.com/djalmajr/iphone6s-linux/actions/runs/37390299442) e [push37390295065](https://github.com/djalmajr/iphone6s-linux/actions/runs/37390295065). Não cobre a política nem as integrações posteriores.

### Perfil PCI retido anterior — composição completa preparada

Composer `c30a4ac` oferece `--pcie-scan-hold --reg-on-module`, exigindo ASPM off e power2 explícitos. Antes da saída, verifica o par PCIe/REG_ON contra o build qualificado e SHA/tamanho/ELF/vermagic; copia os dois módulos e gera os booleanos target/PME/noop/hold automaticamente. Default conserva ausência de hold/REG_ON. Mac/Ubuntu ARM64: 13 testes/29 mutações por AssertionError, incluindo 7/13 anteriores e 6 testes/16 mutações novos, 20 inputs preservados e logs conferidos por SHA. [Reprodução](N71_PME_ASPM_CANDIDATE.md#perfil-retido-completo--composição-verificada-sem-boot), [prova](evidence/n71-pci-held-profile.json).

Perfil privado real separado composto e aprovado no check do coletor sem SSH/USB. Payload byte a byte igual ao PME/ASPM anterior; kernel/DT/loader/initramfs/identidades e default preservados, PCIe de 76.112 bytes/REG_ON de 17.688 bytes verificados. Snapshot local com 44 entradas e ferramentas de boot verificados; identidades, payload/DT e ID do snapshot ficam privados. Nenhum módulo carregado ou novo build/DFU nesta etapa. Atribuição de recursos/IRQ/IOMMU, rádio e energia/HDQ continuam pendentes; a próxima sessão física deve reunir controles compatíveis. CI do CLI `17d4c3c`: [PR37386576700](https://github.com/djalmajr/iphone6s-linux/actions/runs/37386576700) e [push37386571327](https://github.com/djalmajr/iphone6s-linux/actions/runs/37386571327) success nos seis jobs. Não cobre o composer novo.

### CLI anterior — aquisição persistente e limpeza por SSH qualificadas

CLI `36c7f53` acrescenta `--scan-hold` e `--release-held`: aquisição positiva conserva o barramento e REG_ON; limpeza posterior exige o mesmo perfil, boot, histórico e ownership vivo. Estado privado é reservado antes dos efeitos e atualizado por substituição atômica. Retomadas de cleanup e descarga dos módulos pulam etapas já comprovadas, sem outro scan; stop-error negativo permanece negativo mesmo após liberar os recursos. Mac/Ubuntu ARM64: 18 testes/22 mutações novos e compatibilidade45/81, total63/103 por plataforma, 36 inputs finais preservados e logs conferidos por SHA. Comandos shell foram executados contra sysfs sintético; 17 comandos gerados passaram `bash -n`, AST e lint de erros fatais passaram. [Reprodução](N71_PME_ASPM_CANDIDATE.md#cli-retido--aquisição-e-retomada-no-mesmo-boot), [prova](evidence/n71-pci-held-session.json).

Naquele checkpoint, o perfil separado e a prova do barramento retido no iPhone ainda estavam pendentes. Nenhum módulo novo foi transferido ou carregado, Image recompilado ou DFU solicitado nesta integração. Wi-Fi, recursos/IRQ/IOMMU e telemetria/carga permanecem abertos; o próximo passo prepara o perfil e agrupa os controles compatíveis. Novos coletores que alterem o histórico precisam integrar o checkpoint da sessão. CI do parser `b8ae125`: [PR37379581085](https://github.com/djalmajr/iphone6s-linux/actions/runs/37379581085) success nos três jobs; [push37379576536](https://github.com/djalmajr/iphone6s-linux/actions/runs/37379576536) cancelled, Mac/Windows success e Ubuntu cancelled. Esse resultado antecede o CLI novo.

### Parser anterior — contrato held e seleção de build qualificados

Parser `49d2158` valida `SCAN_HELD`/`SESSION_HELD` e getter vivo, com módulo/reset/quatro domínios de energia ativos e preparações TLS/PME ordenadas. Topologia/BAR e restore PME compartilham os validadores anteriores; não fabrica resumo temporário, contagens ou limpeza. A limpeza é comprovada separadamente, com remoção→config→PME→TLS→reset→energia→caller e stop-error preservado. Seleção local aceita somente o build caller abaixo, flags booleanas exatas e ABI power2. Novo parser12 testes/29 mutações por AssertionError, scan anterior6/8 e coletor45/81 requalificados nas duas plataformas: total63/118,34 inputs iguais e logs conferidos por SHA/preservados. [Reprodução](N71_PME_ASPM_CANDIDATE.md#parser-held--aquisição-e-limpeza-separadas), [prova](evidence/n71-pci-held-parser.json), [decisão D2](../.agents/plans/n71-funcional-goal-decisoes.md#d2-aquisição-held-e-limpeza-com-contratos-próprios).

Naquele checkpoint, CLI/retomada/perfil ainda não selecionavam hold; nenhum load, DFU, PIN ou console adicional. C/build anteriores foram reutilizados com hashes intactos, sem outra compilação ou Image. Wi-Fi, IRQ/DMA e telemetria/carga continuam pendentes. A próxima fatia integra seleção explícita e retenção/retomada para limpeza no mesmo boot. CI do caller `6e26fac`: [PR37374903992](https://github.com/djalmajr/iphone6s-linux/actions/runs/37374903992) success nos três jobs; [push37374896899](https://github.com/djalmajr/iphone6s-linux/actions/runs/37374896899) cancelled, Mac/Windows success e Ubuntu cancelled, sem causa confirmada. Esse resultado não cobre o parser novo.

### Caller PCI retido anterior — integrado e compilado

Caller `3d410c7`: `scan_hold=1` explícito exige host-scan/PME e conserva bus, callbacks, binding/MMIO, módulo/reset/energia até `action=cleanup`. Getter `held` lê o ownership real sob lock; o formato de `status` foi preservado. Caller real/MMIO com dependências de kernel/scan simuladas passou94 cenários e30 mutações compiladas por SIGABRT/assertion no Mac e Ubuntu ARM64, cinco inputs iguais. Build real de seis módulos Werror/modpost/ELF/vermagic passou com46 inputs, somente caller alterado desde o build abaixo; PCIe76.112 bytes/SHA b7e51d4d, REG_ON e fonte/config/Image/exports intactos. [Reprodução e limites](N71_PME_ASPM_CANDIDATE.md#caller-retido--integração-e-build-offline), [prova](evidence/n71-pci-held-caller.json), [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39).

Naquele checkpoint, coletor/perfil ainda não selecionavam esse build ou hold; nenhum módulo novo foi carregado no telefone. Próxima fatia integra seleção/provenance e retenção REG_ON/staging antes de recursos PCI/IRQ/IOMMU. Wi-Fi, telemetria/carga e hardware persistente seguem pendentes. Telefone mantido no iOS para recarga, zero DFU/PIN/console adicional. CI da integração será vinculada ao próprio head; o checkpoint anterior `fa53768` terminou cancelled nos dois eventos, Mac/Windows success e Ubuntu cancelled: [PR37363958817](https://github.com/djalmajr/iphone6s-linux/actions/runs/37363958817), [push37363951510](https://github.com/djalmajr/iphone6s-linux/actions/runs/37363951510). Causa não confirmada, sem tratar cancelamento como aprovação.

### Lifecycle PCI retido anterior — adapter qualificado offline

Adapter `b0c0933`: API interna hold mantém bridge/bus/callbacks e owners depois de scan positivo com PME, ainda sem bind, atribuição de recursos ou DMA. Cleanup faz stop/remove sob rescan lock antes de restore config/PME/TLS; falhas conservam owner e permitem retry sem novo scan. Dois testes C/45 cenários e26 mutações compiladas por SIGABRT/assertion passaram Mac/Ubuntu ARM64, dez inputs iguais. Seis módulos Werror/modpost/ELF/vermagic passaram com46 inputs; PCIe74008 bytes, REG_ON e fonte/config/Image/exports preservados. [Reprodução e limites](N71_PME_ASPM_CANDIDATE.md#lifecycle-do-bus-retido--preparação-offline), [prova](evidence/n71-pci-held-bus.json), [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39).

Naquele checkpoint, caller/coletor/perfil ainda não selecionavam hold e o módulo novo não foi carregado no telefone. Seus dez inputs e provas45/26 continuam iguais, reutilizados na integração acima. Gates físicos e CI anteriores não comprovam esse hardware persistente. Nenhum DFU/PIN adicional, firmware ou Image novo; telefone no iOS para recarga.

### Última sessão física — quatro etapas no mesmo boot PME/ASPM

Um DFU manual reuniu scan PCI-core, leitura ChipCommon/BAR, observação DART e ciclo temporário do provider DART, sem reinícios intermediários. O scan passou com dois dispositivos, um endpoint, 660 leituras/40 tentativas/23 escritas/zero recusas. BCM4350 revisão8, BAR0 de32KiB e BAR2 de4MiB confirmados; as quatro etapas concluíram cleanup e conservaram SSH/HTTP/Bash/Herdr. Snapshot44/sync e retorno automático ao iOS passaram. Uptime final506,59s; iOS100→100% e carregamento ativo após retorno. Esses percentuais não comprovam carga no Linux. [Resultado e reprodução](N71_PME_ASPM_CANDIDATE.md#sessão-física--quatro-etapas-sem-reiniciar), [prova selecionada](evidence/n71-pme-aspm-physical.json).

ASPM off foi conferido no payload, cmdline e marcador kernel antes da transferência. PME prepare/restore e restauração de config/TLS/reset/power/REG_ON passaram. A enumeração ainda é temporária: recursos PCI persistentes, entrega IRQ, DMA/IOMMU do endpoint, firmware/radio e telemetria/carga continuam pendentes. O telefone voltou ao iOS para recarga; o próximo desenvolvimento é offline.

CI do código físico `dd2b0da`: [PR37356247973](https://github.com/djalmajr/iphone6s-linux/actions/runs/37356247973) success nos três jobs, com81 mutações por AssertionError do coletor nos logs Mac/Ubuntu. [Push37356242967](https://github.com/djalmajr/iphone6s-linux/actions/runs/37356242967) failure somente no Ubuntu: baseline PMGR passou, mas um binário mutante excedeu10s; Mac/Windows passaram. A causa segue não confirmada na [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38); timeout não foi contado como mutation kill.

### Preparação offline da candidata testada

Helper PME, adapter e caller integrados; opt-in `scan_pme_disable=1` e composer `--pcie-aspm-off` preparados para uma candidata agrupada. Helper 1/19, adapter 29/18, caller 73/21 e composer 7/13 passaram no Mac e Ubuntu ARM64. Os seis módulos passaram build real Werror/modpost/ELF/vermagic, com fonte, kernel, Image e exports preservados. PCIe novo: 73.576 bytes; REG_ON intacto. [Procedimento e limites](N71_PME_ASPM_CANDIDATE.md), [prova](evidence/n71-pcie-pme-aspm-build.json).

Coletor `7708a5c`:45 testes/81 mutações por AssertionError passaram Mac/Ubuntu ARM64,29 inputs/hash e sintaxe Bash conferidos. Novo perfil privado passou checks reais de identidade/payload/ABI/módulo, ferramentas e snapshot44; somente bootargs, PCIe, deployment SHA e provenance mudaram, com kernel/DT/initramfs/identidades/REG_ON preservados. [Prova do coletor e perfil](evidence/n71-pme-aspm-session.json). A prova offline foi preservada separadamente da sessão física acima. ASPM off reúne common clock/retrain/L1SS com PME, sem comprovar consumo, Wi-Fi ou carga.

CI anterior do checkpoint `120352c`: push success; PR failure no Ubuntu, com dois timeouts de fixtures anteriores e duas recusas Pongo encerradas por SIGTERM no deadline sintético. Mac/Windows passaram nos dois eventos. Esses resultados não cobrem o novo coletor; sua CI própria está registrada acima. A falha continua registrada para análise na [issue38](https://github.com/djalmajr/iphone6s-linux/issues/38), sem atribuição causal confirmada.

### Checkpoint físico anterior — PME do endpoint e alimentação

A candidata PME foi testada em um boot/um scan/zero reboots intermediários: root044 já não foi a primeira recusa; endpoint04c/wordc008 sobre4108 bloqueou. Scan negativo613/33/23/1; cleanup de bus/config/TLS/reset/power e REG_ON80 passou, serviços preservados. Snapshot44/sync íntegros; retorno automático não confirmado, fallback físico recuperou iOS99%/carregando. [Resultado e limites](N71_LINK_EXPERIMENT.md#pme-root-superado--endpoint-e-retorno-manual-delimitados), [prova selecionada](evidence/n71-pme-first-physical.json). Issue21 volta a acompanhar confiabilidade do retorno; Wi-Fi e carga Linux continuam abertos.

Helper PME `0098def` qualificado offline: baseline C/14 mutações SIGABRT/assertion nas duas plataformas, sete inputs; disable/restore somente bit0100, sem W1C e owner retido em falhas. Ainda não integrado ao scan/caller, módulo ou telefone. Próxima etapa reúne integração/retention e controles PCI antes de outro DFU. GasGauge1465 ciclos; saúde percentual não derivada de FullChargeCapacity100. Nenhum Image novo, rádio/firmware/DMA ou configuração global do Mac.

CI c08c PR success/push failure pré-enumeração sintética; fixture shell d5ead20/11/4 Mac/ARM64, PR success nos três jobs e push cancelled com Ubuntu cancelado/Mac/Windows success. Issue38 permanece aberta; CI do helper será registrada separadamente.

### Preparação PME anterior à sessão

Coletor PME `4cea1ce` pronto para perfil separado:39 testes/53 mutações Mac/ARM64,26 inputs e dez comandos bash-n; check real de payload/initramfs/identidades/SHA/ELF/vermagic sem SSH/USB. Seleção explícita `--host-scan --scan-link-target --scan-pme-noop`, provenance booleano exato e contratos no-write/evento/root/releitura obrigatórios. Seis arquivos anteriores preservados, somente PCIe/provenance novos, default intacto. [Receita e continuação sem outro boot](N71_LINK_EXPERIMENT.md#coletor-pme--perfil-separado-e-continuação-no-mesmo-boot), [prova selecionada](evidence/n71-pme-scan-session.json). Candidata ainda não carregada; CI do head publicado e gates USB/carga frescos precedem próximo boot agrupado.

PME inativo qualificado offline (`5bc966e`): pedido root044/word8008 sobre PMCSR8 recebe no-op sem W1C/escrita no hardware, com identidade/capability/COMMAND/releitura verificadas. Evento ativo/enable/D-state e controles do endpoint continuam recusados. Seis suítes/8 testes compiladores,36 mutações config e scan21/13 passaram Mac/ARM64; seis módulos Werror/modpost/ELF/vermagic, kernel/fonte preservados. PCIe70424 bytes; REG_ON intacto, nenhum Image/perfil/default substituído ou novo DFU. [Reprodução e limites](N71_LINK_EXPERIMENT.md#pme-já-inativo--candidata-sem-escrita-w1c), [prova selecionada](evidence/n71-pcie-pme-noop-build.json). Candidata ainda não carregada; próxima fatia integra sua seleção/provenance no coletor antes de outra sessão agrupada.

CI7adc PR falhou em dois testes antigos de retorno/backup; push cancelado, Mac/Windows aprovados. Diagnóstico `402943a` passou20/20 Mac/ARM64 e expõe fase/erro da fixture sem ampliar timeouts. [Issue38](https://github.com/djalmajr/iphone6s-linux/issues/38) continua aberta; essa CI não cobre a correção PME nova. Telefone mantido no iOS para recarga, Wi-Fi e telemetria/carga Linux ainda pendentes.

Sessão física da candidata: um DFU/um scan/zero reinícios intermediários. TLS1→2→1 passou com readback/link qualificados; scan continuou negativo pela primeira recusa root044/word8008, correspondente à limpeza PME W1C. Driver removeu bus/config/TLS/reset/power e ficou ready0 após probe negativo. O coletor conservou REG_ON por não reconhecer esse caso; correção `d1cee21` passou37 testes/47 mutações Mac/ARM64 e concluiu unload/restore normal no mesmo boot, sem outro scan. SSH/HTTP/Herdr finais, snapshot44/sync e retorno ao iOS por software passaram. iOS100→90 inclui transições, carregando após retorno; gadget500mA e zero power_supply não comprovam carga. [Resultado e próximos gates](N71_LINK_EXPERIMENT.md#sessão-física-do-target--um-boot-correção-do-coletor-sem-reiniciar), [prova selecionada](evidence/n71-scan-target-physical.json). Próximo desenvolvimento offline: qualificar PMECSR/lifecycle; Wi-Fi, IRQ/DMA/firmware e energia/telemetria continuam abertos.

CI d045d24 terminou success em PR37330736713/push37330728149, seis jobs; push passou no segundo attempt após retry do único job Ubuntu que falhou em testes antigos de return_ios. Rechecks sem mudanças passaram; a intermitência será investigada separadamente. Essa CI não cobre d1cee21; os gates Mac/ARM64 e físicos dessa correção estão registrados acima.

### Preparação e checkpoints anteriores

Coletor `e1a4835` e perfil separado estão qualificados:36 testes/45 mutações por AssertionError passaram Mac/Ubuntu ARM64,25 inputs conferidos e10 comandos bash-n. O perfil real passou payload/initramfs/identidades/módulos sem USB/SSH. Seleção explícita `--host-scan --scan-link-target`; uma tentativa de cleanup no mesmo boot, REG_ON/staging conservados quando a restauração PCIe não é comprovada. Gates C/build anteriores reutilizados com inputs iguais. Ainda não carregado no iPhone; próximo gate é uma sessão física agrupada, sem reinícios intermediários para os passos que puderem ocorrer por SSH. [Receita e limites](N71_LINK_EXPERIMENT.md#coletor-com-retenção-reg_on--candidata-pronta-para-sessão-agrupada), [prova selecionada](evidence/n71-scan-target-session.json). Wi-Fi, telemetria e carga continuam abertos; nenhum Image, firmware, pacote/configuração global ou default alterado.

Scan `e03bdc9` e caller `cae5955` integram TLS1→2→1 com ownership persistente: bridge/config/target e energia/reset/módulo ficam retidos se o rollback falhar; ação `cleanup` tenta restaurar sem outro scan. Readback real do GPIO, bind/unbind suprimidos e put de uso não duplicado. Scan21 cenários/13 mutações e caller67/18 passaram Mac/Ubuntu ARM64; seis módulos operacionais Werror/modpost/ELF/vermagic, Image/config/exports intactos. Naquele checkpoint, o coletor ainda precisava conservar REG_ON/staging sob retenção; essa preparação avançou acima. Módulo ainda não carregado no iPhone. [Reprodução e limites](N71_LINK_EXPERIMENT.md#scan-e-caller-integrados--cleanup-sem-novo-boot), [prova selecionada](evidence/n71-pcie-scan-target-build.json). Sem novo DFU, firmware ou pacote/configuração global no Mac; Wi-Fi e carga continuam pendentes.

CI `096d69a` concluiu success em PR37326642354/push37326631225, seis jobs, cobrindo a integração e documentação anteriores. A preparação do coletor acima tem prova local/ARM64 própria; sua CI será vinculada ao novo head publicado. Os registros seguintes conservam a cronologia.

Primeira sessão física power2 no head `70d4736`: boot/restore/SSH/HTTP/Herdr passaram, assim como proteção de binding PMGR, dois ciclos genpd e inspeção I2C1 estável/idle (`REV=2`, `SMSTA=08010100`, `XFSTA=0`). No mesmo boot, sem reinicializações intermediárias, PCIe identificou `14e4:43a3`, BCM4350rev8, BAR0 de32KiB/BAR2 de4MiB e ciclo DART com16 words restaurados. Scan PCI permaneceu negativo: primeira recusa root0:08/0a0/word/value2; demais recusas são latched. Cleanup, snapshot/sync e retorno por software ao iOS passaram; iOS91→81% incluindo transições, carga ativa no retorno. Não comprova corrente, saúde/carga Linux ou Wi-Fi. [Prova selecionada](evidence/n71-power2-first-physical.json), [energia e próximos gates](N71_HDQ.md#primeira-sessão-física-power2--ciclos-e-inspeção-verificados), [recusa PCIe](N71_LINK_EXPERIMENT.md#primeira-sessão-power2--link-chip-dart-e-scan-agrupados). Desenvolvimento seguinte é offline; não exige outro DFU para registrar a coleta.

CI do head `70d4736` concluiu success em PR37266850654/push37266847052, seis jobs. Logs Mac/Ubuntu confirmam os testes do coletor e26 mutações por asserção. Código, perfis e módulos não mudaram para a coleta física; esses gates foram reutilizados. Os registros abaixo conservam a cronologia da preparação e das sessões anteriores.

Coletor Wi-Fi `dfad0ff`: qualifica os pares legados/power2 e propaga a release para módulo, preflight, resultado e histórico de continuação.31 testes/26 mutações passaram Mac/Ubuntu ARM64; perfil privado power2 com PCIe/REG_ON passou seis checks reais sem SSH/USB e recusou dart-cycle sem histórico. Payload/initramfs/identidades e perfil anterior intactos, nenhum Image/módulo recompilado ou DFU. [Reprodução e continuação](N71_LINK_EXPERIMENT.md#coletor-de-link-na-abi-power2--continuação-no-mesmo-boot), [prova selecionada](evidence/n71-link-binding-session.json). Teste físico aguarda USB; preparação não habilita rádio, telemetria ou carga.

Módulos Wi-Fi `3ce8aaf`: seleção explícita `n71-dart-serdev-power-v2`, com release e hashes power2 conferidos; default e artefatos legados preservados. Oito módulos passaram build nativo ARM64/Werror/modpost e verificação independente SHA/ELF/vermagic/dependências no Mac. Os12 testes e17 mutações por asserção passaram nas duas plataformas. Preparação aproveita o Image existente, sem recompilar ou reiniciar o telefone; nenhum módulo/firmware foi instalado ou carregado. PCIe/DART/IRQ/chip/firmware, Wi-Fi, carga e telemetria continuam pendentes. [Reprodução](N71_LINK_EXPERIMENT.md#módulos-wi-fi-para-power2--preparados-sem-novo-image), [prova selecionada](evidence/n71-wifi-binding-modules.json).

CI `38c5df6` do builder142/documentação143 terminou success em PR37265593416/push37265590595, três jobs cada. Esse head antecede a correção144 do coletor; CI nova deve ser vinculada ao seu próprio commit.

CI anterior `6e37876` terminou success em PR37263273839/push37263270142, seis jobs. Logs reais Ubuntu/macOS do PR confirmam observador I2C37/18 e caller52/14. Esse resultado cobre a preparação I2C139–141; não prova hardware nem o builder Wi-Fi142, cuja evidência local/ARM64 está registrada acima.

Nova preparação `14117a4`: ação explícita `inspect` integrada ao caller power2. Reserva MMIO e lê REV/SMSTA/XFSTA duas vezes, sem reset, FIFO ou comandos ao carregador; sempre tenta encerrar genpd e conserva referências em cleanup pendente. Observador37 cenários/18 mutações e caller52/14 passaram Mac/Ubuntu ARM64; módulo real Werror/modpost/ELF/vermagic conferido. Coletor agrupa dois cycles e uma inspeção no mesmo boot, com guards/fixtures locais. Nenhum desses ciclos ou leituras foi executado no telefone; carga, telemetria e Wi-Fi continuam pendentes. [Reprodução e próximos gates](N71_HDQ.md#inspeção-do-controlador-i2c1--preparada-sem-reset), [prova selecionada](evidence/n71-i2c-controller-inspection.json).

iPhone no iOS para recarga depois de uma sessão curta power1. Um DFU
manual reuniu restore, SSH/HTTP/Herdr e os dois observadores I2C1/GPIO/PMGR;
módulos/staging removidos, snapshot/sync e retorno por software verificados.
Leituras iOS100→99% em160s incluindo DFU/reboot/iOS; carregamento ativo
no retorno às00:56:31UTC de2026-10-05. Isso não prova carga no Linux.
Linux não está online; desenvolvimento segue no Mac/VM para implementar
aquisição/restauração I2C1 e carga/telemetria N71, sem repetir esse DFU.
[Evidência e limites](ALIMENTACAO.md), [issue P0](https://github.com/djalmajr/iphone6s-linux/issues/2).

Image separado `7.2.0-iphone6s-dart-serdev-power1` compilou com as patches
DART/serdev/GPIO/PMGR001→006, em12min41s. Config só difere na identidade;
config embutida, modpost, export serdev, objetos builtin e DTB preservado
conferidos. Fonte/config/Image/exports do rollback intactos; artefatos no Mac
passaram por SHA e pelo integrador real. [Reprodução e limites](N71_KERNEL_BUNDLE.md#image-completo-da-candidata-gpiopmgr--2026-10-04).
Os cinco módulos também passaram rebuild Werror/modpost/ELF/vermagic.
Perfis base e diagnóstico foram compostos/validados separadamente no Mac,
com initramfs/identidades preservados e snapshot local de44 entradas validado.
Boot/restore/SSH/HTTP na ABI nova e observadores passivos passaram;
acesso físico ao carregador continua pendente.
[Prova de composição](evidence/n71-power-profile.json),
[sessão física](evidence/n71-power-session-gate.json).
O Image novo ainda não habilita carga, telemetria ou Wi-Fi.

Lifecycle runtime PM `29e61ec`:12 cenários/13 mutações compiladas por asserção
Mac/ARM64 e objeto kernel/Werror passaram. Contrato retém cleanup pendente,
preserva erro primário e impede novo put após uma falha que já consumiu uso.
O backend genpd e o caller operacional agora estão compilados no checkpoint
acima; ativação/inspeção físicas e acesso a pinos/carregador seguem pendentes.
[Reprodução e limites](N71_HDQ.md#lifecycle-runtime-pm-i2c1--sequência-testada-backend-pendente).
Nenhum novo DFU nessa implementação. O passo novo passou Ubuntu/macOS
em ambos os runs do código29e61ec. O run
push falhou depois por PID vazio numa fixture antiga de cancelamento do
reboot. Publicação atômica corrigida somente no teste, com regressão de
escrita incompleta e mutação por asserção Mac/ARM64; gate afetado passou
20 testes/11 mutações em ambas as plataformas. CI8974389 terminou success
em PR37251729490/push37251726729, seis jobs; issue37 concluída.

Acesso PMGR compartilhado `152e07b`:97 cenários/22 mutações por asserção
Mac/ARM64 e módulo Werror/modpost/ELF/vermagic power1 passaram. Mantém
validação N71/caminhos/metadata/provider sob lock e limpa o handle no unlock.
Não foi carregado no aparelho nem implementa backend genpd ou carga.
[Contrato e reprodução](N71_HDQ.md#acesso-pmgr-compartilhado--qualificado-sem-ativação),
[prova selecionada](evidence/n71-pmgr-access.json).

Backend genpd `1cdfa72`:87 cenários/20 mutações Mac/ARM64, callbacks reais
linkados Werror/modpost e patch007 aplicada/compilada em cópia do provider.
Proteção suppress_bind_attrs obrigatória: power1 atual recusa esse backend;
Image power2 e caller operacional passaram build separado; teste físico ainda pendente. Suspend
com domínio ligado mantém cleanup pendente, sem detach nem outro put.
[Contrato/reprodução](N71_HDQ.md#backend-genpd-i2c1--compilado-proteção-de-binding-pendente-no-image),
[prova selecionada](evidence/n71-i2c-genpd.json). CI da primeira versão
`a476729` terminou verde nos seis jobs; guard e seletor power2 passaram nos seis jobs de `a684a93`.
Nenhum DFU, acesso ao carregador ou configuração global do Mac nesta rodada.

Image separado `7.2.0-iphone6s-dart-serdev-power2` compilou em19min06s com001→007. Patch007 integra a proteção de binding exigida pelo backend. Image/config/gzip/DTB/logs passaram SHA no Mac; config só difere de power1 na identidade e fonte/config/Image/exports anteriores ficaram intactos. Nenhum boot ou perfil default alterado. Integração real, seis módulos e controles operacionais passaram; falta a sessão física agrupada. [Reprodução](N71_KERNEL_BUNDLE.md#image-power2-e-proteção-de-binding--2026-10-05), [prova de link](evidence/kernel-n71-binding-build.json). Ausência física de bind/unbind, carga, telemetria e Wi-Fi continuam sem comprovação.

Perfis power2 base/diagnóstico preparados: initramfs e identidades byte a byte iguais, fonte preservada,700/600 e nenhum autoload. Integrador22 testes/25 mutações; compositor6/8; caller genpd39 cenários/11 mutações, todos Mac/ARM64. Seis módulos W=1/Werror/modpost/ELF/vermagic e hashes conferidos no Mac. Caller permite cycle explícito e cleanup retido, preservando módulo/referências se a restauração falhar. CI5fa e CI6a66ff5 terminaram success nos seis jobs cada, cobrindo integração e caller/compositor. Nenhum novo DFU ou I/O do carregador. [Prova selecionada](evidence/n71-binding-profile.json), [procedimento da próxima sessão](N71_HDQ.md#próxima-sessão-física-uma-entrada-dfu-operação-pelo-mac).

Transporte da próxima sessão preparado: coletor passivo power2 conserva o corpo testado e passou três fixtures; coletor de dois ciclos genpd passou sintaxe, oito contratos de resultado e guards de unload em Bash temporário, incluindo duas mutações por asserção. Nenhum comando no telefone ou prova do transporte ativo completo. Na consulta USB atual o Mac não detectou iPhone/iOS; reconexão foi solicitada antes de iniciar qualquer monitor/DFU. Goal permanece ativo e o aparelho não foi reiniciado nesta preparação. [Detalhes e limites](N71_HDQ.md#transporte-da-sessão-power2--preparado-sem-ação-no-telefone).

No boot anterior, DART provider/INTx/probes de ponte tiveram cleanup verificado
e SSH/HTTP/snapshot preservados. Scan PCI ainda negativo; primeira recusa
seguinte é SERR. A candidata controls/SERR compilada não foi carregada por
causa da bateria; Wi-Fi/DMA/IRQdelivery continuam pendentes. O último snapshot
válido é posterior ao scan de ponte. [Estado e reprodução](N71_LINK_EXPERIMENT.md).

Novo cálculo SN2400 específico N71 passou Mac/ARM64/oito mutações e contexto
kernelWerror. É aritmética sem I/O, não um driver de carga. I2C1/HDQ/revisão,
cleanup e corrente líquida continuam na #2; teste prolongado #8 não começou.
CI da correção das fixtures PCI aprovado no SHA85aa0f5 (PR37226272040 e
push37226267211). Gates dos novos arquivos são registrados por SHA nas issues.

Observador I2C1/GPIO114/115 preparado no código `98bc26b`: 86 casos e 15 mutações
Mac/ARM64, módulo de 15.768 bytes Werror/modpost contra o bundle preservado, oito leituras
via provider existente e nenhuma ativação ou escrita. O rebuild power1 foi
carregado/descarregado: GPIO114/115 estáveis/cache coerente, controller disabled
sem adapter. [Reprodução e limites](N71_HDQ.md#coleta-agrupada-de-energia-na-abi-power--verificada),
[prova selecionada](evidence/n71-i2c-topology-observer.json). Continua pendente
aquisição/restauração ativa do I2C1, HDQ e corrente líquida; #2 permanece aberta.
CI do head `c683145`, que contém o código `98bc26b`, aprovado nas duas
execuções PR 37230516183/push 37230513184, seis jobs Ubuntu/macOS/Windows.
Referência Apple I2C1 confrontada: SCL 115/SDA 114 coincidem com o grupo Linux;
descriptor de 12 bytes usa modo 2 e role `AP`, não phandle. Init/reset/unjam são
operações ativas; ownership/idle/restauração e carga continuam pendentes.
[Fatos e reprodução](N71_HDQ.md#i2c1-pinos-apple-e-abi-do-descriptor-confrontados).

Correção GPIO `19f6129`: 816 cenários, 11 mutações e regressão compilada da
fonte original aprovados no Mac/ARM64. CI desse head aprovado nos seis jobs
PR 37233188196/push 37233183384. Integração no bundle permanece na
[issue #35](https://github.com/djalmajr/iphone6s-linux/issues/35); erro propagado
não comprova rollback ou carga funcional.

Observador PMGR `80b3fe0` preparado: 88 cenários/16 mutações Mac/ARM64,
build externo Werror, seis leituras de I2C1/sio_p/sio_busif via syscon existente
qualificado pelo binding sob lock. Rebuild power1 passou load/unload no mesmo
boot dos pinos; seis amostras estáveis, sem ativação ou ownership da cadeia.
[Reprodução e limites](N71_HDQ.md#observador-pmgr--i2c1-e-domínios-pais),
[prova e checkpoint iOS](evidence/n71-pmgr-power-observer.json).

Correção dos callbacks PMGR `301a61f`: 492 casos/14 mutações Mac/ARM64,
regressão da fonte original detectada e arquivo completo compilado Werror
como objeto embutido. Modpost externo recusou esse provider embutido;
erros preservados; a sequência004→006 agora passou integração/link/boot na
[issue #36](https://github.com/djalmajr/iphone6s-linux/issues/36).
Essa patch004 isolada não corrige probe/is_active ou rollback de efeitos parciais.
CI desse código aprovado em PR37236898569/push37236896067, seis jobs.
[Reprodução e limites](N71_HDQ.md#erros-dos-callbacks-pmgr--correção-preparada).

Correção inicial do probe PMGR `21a786c`, patch005 após004: 3.138 cenários,
12 mutações Mac/ARM64 e arquivo completo obj-y/Werror. Primeiro erro de I/O
chega ao caller antes de registrar domínio/provider/reset; bool de estado
só muda após leitura válida. Integração/link/boot passou com004→006;
cleanup após registro, efeitos parciais e ownership/idle seguem na issue #36.
CI21a786c aprovado em PR37238520733/push37238517260, seis jobs.

Cleanup PMGR006 `f728099`: 3.258 casos/seis mutações Mac/ARM64 e objeto
completo004+005+006 obj-y/Werror. Falha de add_provider remove domínio sem
apagar provider alheio; primeiro erro preservado. Integração/link/boot passou;
pós-publicação/iterator e efeitos parciais continuam na #36. Não habilita
carga no Linux e não motivou DFU. [Reprodução](N71_HDQ.md#falha-de-publicação-do-provider-pmgr--cleanup-preparado).
[Reprodução e limites](N71_HDQ.md#erros-iniciais-do-probe-pmgr--correção-preparada).

As seções anteriores abaixo são checkpoints históricos; afirmações sobre
serviços ativos ou VM parada descrevem a data indicada em cada uma.

## Direção de desenvolvimento — 2026-10-02

Prioridade do operador: Wi-Fi e recursos que facilitem a iteração, com o mínimo de reinicializações. [Fluxo de sessões e ordem](DESENVOLVIMENTO.md). DNS53 deixa de ser a próxima entrega; seus gates aprovados são preservados e o piloto funcional continua pendente.

Inventário físico por SSH no boot já ativo 7.2.0-iphone6s-source: somente lo/usb0, ieee80211 ausente, PCI/SDIO/MMC sem dispositivos, nenhum módulo e nenhum compatible correspondente entre 118 propriedades examinadas. Sem power_supply ou ADT original no chosen consultado. Nenhum reboot, firmware, driver ou política de rede nesta fase. [Wi-Fi](WIFI.md), [evidência](evidence/wifi-runtime.json). A topologia foi identificada e a preparação compilável avançou depois, no fechamento N71 abaixo; controlador/PHY e associação/DHCP continuam pendentes.

O boot imediatamente anterior desta rodada restaurou os três arquivos DNS com hashes/tamanhos exatos, SSH/kernel/HTTP e Herdr confirmados. Roteiro privado de preflight errou ao chamar dns.start inexistente; não é prova de DNS5353. Controlador DNS53 expirou esperando prontidão e não abriu o endpoint. Nenhuma consulta DNS53 Mac/Windows executada. A nova prioridade não transforma esse piloto em sucesso.

## Entrega Wi-Fi, sessão e energia — 2026-10-02

**Zero reinicializações nesta entrega.** Updater DNS específico implementado e provado no mesmo Linux: SHA256, quatro checkpoints verificados, UDP/TCP, rollback exato e SSH preservado; Herdr ainda respondeu `running` na conferência final, uptime 8441,32 s no mesmo boot. [Procedimento](DESENVOLVIMENTO.md), [evidência](evidence/dev-session.json). Mac 15 testes (cinco skips VM explícitos)/sete mutações; VM 15 testes/12 mutações. Os demais relatos abaixo permanecem históricos e não representam garantia de continuidade após este checkpoint.

Topologia Apple N71 extraída/reproduzida privadamente: BCM4350/PCIe S8000 porta 1, DART S5L8960X, referência `gas-gauge,bq27540` em UART5/HDQ (não identifica revisão física/register map) e SN2400 em I2C1. Não habilita rádio, sensores ou carga. [Wi-Fi](WIFI.md), [mapa sanitizado](evidence/n71-board-map.json). #9/#2 seguem abertas; próximo desenvolvimento é controlador/PHY/DT S8000 e HDQ/mux/regmap específico da placa.

Configfs da imagem atual anunciou 2 mA. Fontes corrigidas e candidata privada separada declaram 500 mA antes do bind; seis mutações de ordem e quatro de repack passaram no Mac/VM, preservando arquivos/metadados/identidades. Candidata não carregada; orçamento não equivale a corrente/carga e host ainda não confirmou o descritor. #33 conserva esse gate para próximo boot agregado. DNS53 fica em espera; nenhum pacote no Mac ou política global alterada.

## Fechamento da preparação N71 — 2026-10-02

**Fonte:** [plano de topologia](../.agents/plans/n71-topologia.md), #9/#2. **Modo:** fechamento desta etapa offline; o projeto e as issues de Wi-Fi/carga permanecem abertos.

### Resultado

Fragmento N71 e builder separados compilam UART5, DART PCIe1 e recursos PCIe S8000, todos desativados. A baseline reproduz exatamente o DTB funcional preservado; a candidata mantém todas as propriedades anteriores e os phandles antigos. O primeiro build detectou e recusou renumeração de CPUs; a fixação e a regressão nativa agora cobrem esse defeito. [Procedimento/reprodução](WIFI.md#topologia-n71-compilada--2026-10-02), [hashes e evidência](evidence/n71-topology.json).

O diff foi conferido contra o plano: fragmento, builder, testes/mutações, documentação e gate CI correspondem ao escopo aprovado. Sem mudança adicional de comportamento. Ajustes de implementação registrados no plano: parser Python limitado em lugar de fdtget, fixação de phandles e domínios AUX/REF próprios do A9. Nenhum driver PCIe/HDQ operacional foi acrescentado; não há candidata aprovada para boot, firmware/calibração ou nova imagem instalada.

### Verificação executada

| Gate | Resultado |
|---|---|
| Testes Mac | 13 passaram; quatro compilações Linux explicitamente ignoradas; sete mutações rejeitadas por asserção |
| VM ARM64 nativa | 17/17 passaram, oito mutações por asserção; GCC13.3.0/DTC1.7.0 existentes; fonte limpa preservada |
| Lint | AST/Flake8 fatal aprovados; nenhuma fonte shell alterada |
| Typecheck | Não configurado para Python; compilação DTS não é typecheck Python |
| Artefatos/privacidade | Hashes Mac/VM iguais; DTBs/logs privados; guard público e diff aprovados |
| Hardware | Nenhum novo boot/probe/ativação; não fornece prova de Wi-Fi, sensores ou carga |
| CI | Gate portátil incorporado; resultados do SHA final publicados na [PR #1](https://github.com/djalmajr/iphone6s-linux/pull/1) e nos checkpoints das issues |

### Pendências, responsáveis e próximo passo

| Pendência | Impacto | Responsável | Próxima prova |
|---|---|---|---|
| #9: sequência PCIe/PHY S8000, porta1 e DMA | Rádio não enumera | Desenvolvimento do projeto | Mapear recursos/sequência verificáveis, implementar controlador separado e revisar offline antes da enumeração |
| #2: UART5/pin routing/mux HDQ/register map | Sem telemetria ou carga sustentada comprovada | Desenvolvimento do projeto; medição física se necessária | Validar ABI/topologia, integrar leitura do gauge sem limites de carga presumidos |
| #33: orçamento USB | Candidata500mA não bootada | Desenvolvimento e operador no futuro teste físico | Conferir configfs/descritor recebido pelo host em sessão agregada necessária |

A VM dedicada de kernel retornou a **Stopped**, com fonte/builds preservados. DTBs finais foram copiados para runtime privado no Mac. Zero reinicializações, instalação de pacotes ou mudança de perfil/política global nesta etapa. Entrega registrada nas issues existentes, sem criar duplicatas ou encerrar critérios físicos pendentes. Próxima fatia: controlador/PHY e HDQ específicos; sem novo DFU apenas para repetir inventário já conhecido.

## Estado atual e gates pendentes

As provas abaixo resumem os pilotos históricos; o estado verificado na sessão de desenvolvimento está no checkpoint acima. O telefone executou Linux 7.0.12 em RAM, console automático, Bash/SSH/HTTP por USB e serviços encaminhados para a LAN. A cadeia compilada (kernel 7.2.0 e Pongo de fonte) iniciou no aparelho, com console/SSH/HTTP, restore e DNS USB UDP/TCP. Driver apple-watchdog vinculado; retorno espontâneo ao iOS confirmado pelo operador e USB. O CLI antigo perdeu a confirmação de sync e retornou falha; correção passou em novo piloto com snapshot/sync/retorno verificados e CI aprovada. Rollback Linux7.0.12 também passou com restore/SSH/HTTP/retorno; limite de proveniência do legado permanece na #12. [Evidência física](SOURCE-CHAIN-PILOT.md).

DNS padrão #19: diferenças Darwin de grupos (#30) e adoção/fechamento de sockets (#31) corrigidas. Fonte32c39d4 passou33 casos/26 mutações Mac,37/31 na VM isolada e CI terminal com seis jobs. Helper nativo da fonte exata passou UID/GID/grupos/peer/nonce, dados UDP/TCP depois de sua saída e cleanup de FDs/diretório/endpoints53. Isso é teste de sockets, sem consulta ao telefone: piloto DNS53 do iPhone/Windows e política dos clientes continuam pendentes. Retorno físico ao iOS confirmado por USB após fallback,98% e carga ativa; retornoCLI1 anterior preservado. Sem serviço53 do projeto ativo ou política global alterada. [Contrato e reprodução](DNS-STANDARD.md), [evidência](evidence/dns-standard-port.json).

| Área | Evidência e limite atual |
|---|---|
| Boot e recuperação de arquivos (#3/#4) | Wrapper com DFU manual e restore comprovados no aparelho; [operação](EXECUCAO.md) e [perfil](PROFILES.md) |
| Snapshots e falhas (#5/#15) | Agendador/retenção com prova física curta; recuperação explícita de ENOSPC/interrupção em VM. Correção #22 recusa desvios locais por links, validada em Mac/VM/CI; [procedimentos](RECUPERACAO.md) e [evidência](evidence/local-snapshot-paths.json) |
| LAN e DNS (#6/#7) | Correção #24 valida nomes do bundle antes do SSH, com prova local/VM; SSH/HTTP e DNS UDP/TCP pelo Mac/Windows; DNS recuperado em segundo boot. Não configura DNS global ou saída geral de internet; porta 53 e política de resolvedores continuam na #19. Fixture LAN independente reproduziu falha do nslookup por argumentos/stdin sem perguntas recebidas, enquanto quatro consultas de sockets Windows UDP/TCP passaram nas mesmas portas 15953/1053; controle em loopback Windows também reproduziu oito falhas nativas enquanto quatro consultas sockets passaram, com listeners encerrados. Cliente de sockets completo implementado: 61 casos e 18 mutações passaram no Windows real; CLI UDP/TCP passou em fixture LAN nas duas portas e recusou sete entradas inválidas. Cliente público passou contra o iPhone em novo boot/restore: dois positivos UDP/TCP e três negativos nome/endereço/porta, controle Mac e cleanup/retorno CLI0; [evidência física](evidence/windows-dns-physical.json). Causa específica do nslookup desconhecida. [Diagnóstico Windows](DNS-WINDOWS.md) e [DNS](DNS.md) |
| DNS padrão (#19) | [Preparação](DNS-STANDARD.md): inventário do kernel mostrou binds 53 existentes; endpoint LAN selecionado sem bind IPv4 observado, mas UDP/TCP não root recusados por EACCES. Bootstrap mínimo implementado e validado em testes Mac/VM/CI; helper nativo com ACK/dados/cleanup aprovado; piloto DNS53 do telefone e política dos clientes pendentes. Sem listener 53 do projeto no Mac, upstream ou alteração global. [Evidência](evidence/dns-standard-port.json) |
| Reprodução (#12) | m1n1 reproduzido, imagem userspace validada em VM nova e dois boots curtos. Kernel/Pongo de fonte compilados, empacotamento/seleção com hashes fixos; nova cadeia com boot/restore/DNS USB comprovados; rollback Linux conhecido comprovado; proveniência do legado ainda limitada; [Pongo](PONGO-SOURCE-BUILD.md) |
| CI (#14) | Matriz pública Ubuntu/macOS e novo job Windows de DNS, sem chaves/imagens reais; job DNS Windows aprovado. Tests/skips/mutações associados ao commit no [manifesto Pongo](evidence/pongo-source-build.json); CI não prova hardware |
| Alimentação/estabilidade (#2/#8) | Carga sustentada e estabilidade prolongada não estabelecidas; sem sensores Linux validados; [alimentação](ALIMENTACAO.md) |
| Retorno ao iOS (#21) | Helper salva/verifica snapshot e confirma USB/modelo; novo kernel com watchdog vinculado e retorno espontâneo comprovados. CLI corrigido passou com snapshot/sync/retorno USB, saída0 e CI aprovada; fallback físico preservado; [recuperação](REBOOT.md) |
| Herdr/hardware (#13/#9/#10/#11) | [Herdr optativo](HERDR.md) implementado com Bash, lock, restart explícito e marcador restaurável; testes locais/VM passaram; correção #29 dispensa nohup ausente no runtime, com regressão/mutações, VM real e CI aprovados. Dois boots da cadeia de fonte passaram com Bash/TUI SSH pelo Mac, reconexão sem duplicação e autostart após restore de marcador/arquivo; [prova física](evidence/herdr-physical.json). [Storage N71](ARMAZENAMENTO.md) sem controlador/driver comprovado e [boot autônomo](BOOT-AUTONOMO.md) sem cadeia pronta; [Wi-Fi N71](WIFI.md) sem caminho operacional na candidata, com requisitos de barramento/energia/firmware ainda abertos |
| Integração (#16) | Branch/PR #1 abertas; descrição alinhada aos gates realizados, revisão parcial de persistência/boot/DNS/build com correções #22/#23/#24 e proteção de saída #25 verificada em Mac/CI; proteção do estado do agendador #26 verificada em Mac/CI. Contratos de provas DNS #27 e restore #28 corrigidos e verificados em Mac, VM isolada e CI; inventário de 169/170 leituras no checkpoint `49d8747`, todos os textos conferidos; índice APK binário verificado separadamente por estrutura/assinatura, sem leitura textual declarada; checklists DNS/execução/fresh-build alinhados aos pilotos concluídos e histórico identificado. [Cobertura e limites](PR-REVIEW.md); revisão completa e autorização de merge pendentes |

Nenhum pacote instalado no Mac nesta evolução. Downloads, fontes externas, artefatos, chaves e snapshots ficam privados; builds externos somente em VMs dedicadas. Para trocar Pongo ou perfil de Linux, confirmar primeiro o fim da sessão anterior; retirar uma variável não altera uma sessão já iniciada.


## Checkpoint histórico — reprodução de m1n1 (#12)

Dois clones novos da fonte oficial foram compilados offline na VM existente. O clone com profundidade 1 e sem tags reproduziu o componente preservado byte por byte: 1.196.032 bytes, SHA-256 `13d49ab42c6e071857ca05c8414f30dca70699df8a3f472b9c70e4f1233a092b`. O clone completo gerou uma versão diferente via `git describe`; a profundidade foi incorporada à receita, sem override manual de versão. Ambos terminaram com saída 0 e dois avisos upstream. Quatro arquivos crate e 131 fontes em cache foram conferidos; fontes e payload conhecido preservados. Nenhum pacote foi instalado, nem candidato carregado no telefone. A VM dedicada foi parada após confirmar ausência de processos de build. [Receita, decisão e limites](M1N1-BUILD.md), [evidência](evidence/m1n1-rebuild.json).

Naquele checkpoint, #12 ainda aguardava autenticidade do pacote/reprodução em VM nova e #7 aguardava o piloto DNS. Esses gates avançaram depois, conforme o estado atual e os documentos acima. A assinatura própria do APK original/commit `-dirty` mantém limites específicos; a candidata de kernel de fonte é separada. #8 continua dependente de alimentação validada (#2). Nenhuma dessas pendências é resolvida pela igualdade do componente m1n1. Nenhum typechecker do projeto foi configurado; esta etapa alterou apenas documentação e executou builds upstream. JSON, identidade dos artefatos e links locais foram verificados; testes de código inalterado permanecem válidos.

## Validated capabilities: Linux, Bash, SSH, HTTP and Herdr

Bash 5.2.21, key-only Dropbear SSH and Herdr 0.9.1/protocol 22 were verified on the phone. The Herdr pane survived disconnecting the SSH client. Bootstrap Telnet is now stopped. The runtime and candidate image contain a private SSH server key and remain local. Before the folder reorganization on 2026-09-30, the manual-DFU wrapper completed a full boot with exit 0, integrated SSH/HTTP and operator-confirmed console (#3). The dedicated build VM was stopped after recording package versions. See `REPRODUCAO.md` for the full chronology and public evidence.

## File persistence — verified 2026-09-29

Private snapshots on the Mac cover `/srv/data` and work files in `/root`. Restore checks integrity/scope and captures a pre-restore snapshot before overwriting. Tests recovered contents/modes, retained extras and blocked invalid links. On 2026-09-30, recovery after a fresh DFU also passed: sentinela/hash, mode 640, extra file, SSH identities and HTTP verified (#4). Snapshots exclude SSH identity and live Herdr state. Opt-in automatic snapshots/retention and boot restore later passed a short physical pilot (#5); explicit interrupted-restore recovery passed ENOSPC/process-interruption fixtures in the dedicated VM (#15). See `PERSISTENCIA.md`, `AUTOSNAPSHOTS.md` and `RECUPERACAO.md`.

## Display console — verified 2026-09-29

`simpledrm` exposed fb0 at 750 × 1334. Unblanking, writing tty1 and switching VT activated fbcon. The user confirmed both the initial console text and commands typed through an SSH Bash mirrored by util-linux `script`. The `console` helper is tested. The integrated image booted and the user confirmed the console appeared automatically; see `CONSOLE.md`.

## Folder organization and power checks — 2026-09-30

Scripts now live in `scripts/host`, `scripts/boot` and `scripts/build`; phone sources in `phone`; ignored binaries/images/logs in `bin`, `artifacts` and `logs`. Run `bash scripts/host/iphone-linux.sh ...` from the tools directory. Reorganization preserves all 18 artifact hashes; warm status/HTTP and snapshot creation passed using the new paths. A subsequent cold boot and restore using the relocated CLI also passed: wrapper exit 0, operator-confirmed console, strict SSH/HTTP and sentinel content/mode restored with SSH identities unchanged.

Sustained charging remains open (#2). A roughly 12-minute USB-A interval returned iOS charge 100% from a 94% baseline; a later roughly 25-minute Linux interval returned 90% after an earlier 100% reading. Both include preparation/reboot and possible gauge variation. A later 17-minute interval with reduced/variable brightness returned iOS 100% from 98%, but raw current-capacity decreased (873 to 854) and raw maximum changed (884 to 877); units and semantics of those fields remain unvalidated. The percentage ceiling and conflicting gauge fields prevent a sustained-charge claim. Effective gadget MaxPower was 500 mA; no descriptor was changed. The operator reported cold/lukewarm and visible console. No Linux battery/temperature sensors were available. See `ALIMENTACAO.md`.


### Cliente Windows53 — evidência e CI publicados

Extensão b4fe9e4: seleção explícita53 adicionada, default1053 conservado;54–1023 continuam recusadas. Regressão nova contra fonte antiga terminou1 por DNS_TEST_ASSERTION standard-port, com compilação válida. Fonte corrigida passou64 casos/20 mutações reais por asserção e sete invocações públicas novas sem marcador nos negativos. Parser PowerShell/compilação C# nativos passaram; quatro fontes conferidas conjuntamente por SHA256. [Evidência sanitizada](evidence/windows-dns53-client.json).

CI exato b4fe9e4 concluído: [PR36949215659](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949215659) e [push36949211094](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949211094), seis jobs aprovados (Windows/Ubuntu/macOS). Log Windows confirmou baseline64 e o passo de mutações terminou verde. CI valida fonte/fixtures; não executa o telefone nem DNS53 nativo no Mac. Nenhuma suíte local foi repetida para esta fase documental.

Quatro arquivos próprios de testes/logs e diretório tests do Windows removidos; dois arquivos cliente verificados preservados para o próximo piloto. Filhos próprios concluíram e nenhuma fixture permanece ativa. Sudo não interativo Mac exigiu autenticação; nenhum bootstrap privilegiado Mac ou DNS53 funcional executados. Android fica pendente; Mac/Windows são os clientes da rodada atual. Não houve instalação, agente, chave, DNS/firewall/política global ou mudança do telefone. #19 conserva os gates nativos/NRPT/IP estável/rollback; #2/#8 e revisão integral #16 continuam separados.


## DNS53 — correção Darwin #30 e limite nativo

Primeiro piloto com wrapper0, restore exato de três arquivos DNS, SSH estrito/HTTP/kernel7.2.0-iphone6s-source e DNS5353 UDP/TCP passou. Bootstrap Mac53 recusou antes de handoff: leitura Python17 grupos da conta, versus kernel com um único grupo primário e zero não primários; UID/GID reais/efetivos do usuário conferidos em filho isolado. Nenhum DNS53 Mac/Windows foi executado; sockets53/túnel1054 ausentes após erro. Não é prova de serviço funcional.

Correção f969696 usa getgroups da libc/ctypes stdlib no Darwin, limita contagem/errno e exclui somente o GID primário já conferido; Linux conserva os.getgroups/lista vazia. Regra de UID/GID/sudo original/nonce/peer/FDs e frame suplementar0 mantida. Regressão antiga falhou por asserção. Mac27 casos/21 mutações; VM31 casos/25 mutações em namespace próprio, fonte/hash conferidos. AST/Flake8 fatal do Python3.12.6 já instalado, JSON/links/diff/guard passaram. [Plano e procedimento](DNS-STANDARD.md), [evidência sanitizada](evidence/dns-standard-port.json), [issue30](https://github.com/djalmajr/iphone6s-linux/issues/30).

CI exato f969696 terminal aprovado: [PR36953017204](https://github.com/djalmajr/iphone6s-linux/actions/runs/36953017204) e [push36953013523](https://github.com/djalmajr/iphone6s-linux/actions/runs/36953013523), seis jobs Windows/Ubuntu/macOS. A fonte/fixtures foram testadas; helper Darwin corrigido e consultas DNS53 reais do telefone continuam pendentes. Prova standalone privada preparada com pins/TTY/sockets/dados/cleanup, mas cache local expirou. Não iniciar silenciosamente sem autenticação.

Cleanup do episódio: daemon DNS próprio parou, bootstrap/túnel/sockets Mac ausentes e VM devolvida ao estado parado. Snapshot/sync passaram; CLI de retorno saiu1, Linux deixou o USB, porém iOS não reapareceu até a última observação. Fallback físico Power+Home até maçã foi solicitado e ainda aguarda confirmação. Tentativa herdr.py stop era inválida e não foi contada como parada; reboot encerrou o runtime, sem comprovar iOS. Logs/IDs/endpoints privados em runtime/dns53-physical-20261001. Dois arquivos cliente verificados permanecem intencionalmente na pasta exclusiva Windows para próximo piloto; sem teste/servidor próprio ativo lá.

Nenhum pacote no Mac, agente novo, configuração de DNS/NRPT/PF/sudoers/firewall/roteador/conta ou merge/tag/release. #30/#19 continuam abertas para prova nativa/piloto/clientes/política; Android pendente, rodada atual Mac/Windows. #2/#8/proveniência e revisão integral #16 continuam separados; complete_pr_review=false e inventário integral49d8747 preservados. Esta fase documental não repete gates de código inalterado nem declara serviço ativo/contínuo.

## Historical snapshot: first Linux and USB HTTP session — 2026-09-29

The following observations describe the first probe session, before the later console, SSH and full-wrapper validations above. Its active-session statements are historical.

- On 2026-09-29 the user replaced the cable with a genuine **USB-A-to-Lightning** cable connected to a rear Mac port. The first guided attempt with that cable succeeded: palera1n reported `Device entered DFU mode successfully`, `Checkmate!`, and `Booting PongoOS...`. `ioreg` confirmed `PongoOS USB Device`.
- `pongoterm` uploaded the verified 11,700,549-byte combined payload and ran `bootm`. The Mac subsequently detected `iPhone 6s Linux probe` and its NCM network interface `en12`.
- A temporary `172.16.42.2/24` alias was added only to `en12`, using the macOS administrator dialog. The phone is `172.16.42.1`; `route -n get 172.16.42.1` confirmed `en12`.
- A real shell returned `Linux (none) 7.0.12 #1-postmarketOS SMP PREEMPT Fri Jun 12 10:53:24 UTC 2026 aarch64 GNU/Linux`, model `Apple iPhone 6s (Samsung)`, two processors, and 1,973 MiB RAM. The interactive shell was also tested with `uname -a` and `exit`. Evidence: `evidence/linux-boot-proof.txt`.
- BusyBox HTTP serves a live status page at **http://172.16.42.1:8080/cgi-bin/status**, bound to the USB address only. The real HTTP response was saved to `evidence/linux-http-proof.html`. Repeated `serve` completed successfully without launching another HTTP server.
- `/sys/block` exposed only loop devices and zram; no internal-storage block device appeared. `/sys/class/power_supply` was empty. Persistent internal storage and battery/charging monitoring are therefore **not established** in this session.
- The screen is black, as reported by the user; the shell and HTTP service work independently of it. This is an experimental **RAM session**, requiring Mac-assisted boot and physical DFU buttons after a restart. It is not an autonomous or unattended server installation.
- `iphone-linux.sh` provides `status`, `shell`, `serve`, `connect`, `disconnect`, and a prepared `boot` wrapper. `status`, interactive `shell`, and repeated `serve` were verified against the phone. The assembled `boot` wrapper has not been rerun from a fresh restart; its individual DFU/Pongo/upload stages were used successfully in this session.
- The visual guide and pongoterm processes were stopped after use. The phone's Linux/HTTP session and the dedicated Mac USB IP alias remain intentionally active. No Mac package was installed and no remote account/service was changed.

## Earlier diagnostics and preparation

## Device and findings

- iPhone 6s (`iPhone8,1`, `N71AP`, Samsung A9 S8000), 32 GB. The official Finder recovery-mode **Update** completed on 2026-09-27; `ideviceinfo -k ProductVersion` confirmed **iOS 15.8.8** after reboot. It was previously on iOS 15.7.5.
- Mac USB pairing validates. After the update, the phone requested a PIN to continue installation; the user entered it, and iOS finished setup before the Linux boot test.
- Battery reported 1,462 cycles in an earlier diagnostic; its runtime is poor.
- The touch panel generates phantom touches even with Lightning disconnected. A video shows calculator keys activating without contact and a row of display artifacts near the bottom of the 0 key. This points to the screen assembly or its connection, but does not isolate the exact component.
- Home responds to a long press by opening Siri. Siri did not execute a spoken command, and Wi-Fi connectivity is uncertain.
- Recovery mode worked. Multiple DFU attempts with a direct USB-C-to-Lightning cable ended in an Apple logo followed by Recovery, and palera1n reported `Whoops, device did not enter DFU mode`.
- The USB-C-to-Lightning cable was moved from the Mac Studio M2 Max front USB-C port to a rear USB-C port. `ioreg -p IOUSB -w0` then showed the iPhone directly under `AppleT8112USBXHCI@03000000`, instead of behind the front path's ASMedia USB2 hub. `ideviceinfo -k ProductVersion` still returned 15.8.8.
- A synchronized visual DFU attempt on the rear USB-C port ran through palera1n's 4-second Power+Home and 10-second Home stages. The tool reported `Whoops, device did not enter DFU mode`; `ioreg` showed `Apple Mobile Device (Recovery Mode)`, not DFU. The guide process was stopped, the browser page closed, and `palera1n -n` exited recovery. `ioreg` then showed a normal `iPhone`, and `ideviceinfo -k ProductVersion` returned 15.8.8. No Linux payload was uploaded.
- The user confirmed that phantom touches still occur after the official iOS 15.8.8 update. Whether display artifacts also recur after the update is awaiting observation. The artifacts were absent on black screens and during the Apple logo before the update; this does not alone identify a software or hardware cause.

## Preserved local inputs (current paths)

- `bin/palera1n-macos-arm64`: official v2.4 binary; SHA-256 `950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9` matched the official GitHub release digest. CleanMyMac classified it as jailbreak riskware. It was executed locally on the Mac; its present path is under `bin/`.
- `artifacts/Pongo.bin`, `bin/pongoterm`, `artifacts/m1n1.bin`, `artifacts/vmlinuz-apple-16k`, `artifacts/s8000-n71.dtb`, and `artifacts/iphone6s-initramfs.gz` are staged for an experimental RAM boot.
- `artifacts/m1n1-linux-iphone6s.bin` is the combined boot payload (SHA-256 `7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520`). It **booted successfully on 2026-09-29**.
- The local DFU countdown prototype was removed at the operator's request on 2026-09-30. `scripts/boot/dfu_boot.py` monitors manual DFU without opening a browser or HTTP listener; local simulated tests and a physical full-wrapper boot passed before the folder reorganization.
- The isolated Multipass VM `iphone6s-build` was used to build arm64 components and is stopped. Existing VMs were not modified.

## Practical limits and next test

HoolockLinux supports experimental A9 boots, but documents internal storage support only for A11. For this A9 phone, a Linux boot would be tethered and RAM based; autonomous boot after a restart is not established. The original probe initramfs exposes a temporary unauthenticated Telnet shell on the dedicated USB link for boot proof. The default integrated image starts key-only SSH directly. Sustained power and production operation remain unverified.

Ghost touches did return after the official update. The user chose Linux rather than any iOS-based server and asked to stop repeating the failed DFU timing approach. A full Restore has not been done. Both documented HoolockLinux methods, PongoOS and iBoot, require hardware DFU. The materially different USB-A-to-Lightning cable test **succeeded on 2026-09-29**; palera1n documents that USB-C-to-Lightning may prevent DFU. Do not use fakefs or the A11 partitioning tools on this A9. The worn battery and absence of battery-monitoring data remain limits for unattended use.

An iOS-based route using Dopamine/TrollStore avoids DFU, but installation and initial launch require working on-device interaction. TrollRestore's backup method also requires Find My disabled, which would change remote account state if currently enabled; that was not attempted. No remote accounts or services were modified.

Sources: [HoolockLinux setup](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP_pongoOS.md), [HoolockLinux storage status](https://github.com/HoolockLinux/docs/blob/master/tools/README.md), [palera1n guide](https://ios.cfw.guide/installing-palera1n/), [Dopamine](https://github.com/opa334/Dopamine), [TrollRestore](https://github.com/JJTech0130/TrollRestore).

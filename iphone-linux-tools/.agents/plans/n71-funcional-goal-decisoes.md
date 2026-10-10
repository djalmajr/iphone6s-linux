# Decisões — Wi-Fi e energia N71

## D1. Caller com hold explícito e getter separado

- **Decisão:** expor `scan_hold` desativado por padrão, exigir PME/host-scan e manter módulo, binding/MMIO e energia até `action=cleanup`. O getter `held` lê bus/ownership do adapter sob o lock; o formato de `status` permanece igual.
- **Por quê:** permite continuar o desenvolvimento por SSH no mesmo boot e usa o estado real do bridge. Os parsers atuais já dependem do protocolo de status, então a leitura nova terá um contrato próprio.
- **Alternativas:** acrescentar `held` ao status exigiria migrar os parsers existentes; armazenar uma flag no diagnóstico exigiria sincronizá-la com o adapter durante falhas e retry.
- **Reverter:** baixo; opção nova é explícita e os wrappers anteriores continuam removendo o bus imediatamente. A migração para um protocolo versionado pode reunir os getters posteriormente.
- **Onde:** incremento175 de [n71-funcional-goal.md](n71-funcional-goal.md), caller PCI e fixtures nativas; [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39).
- **Status:** aplicada no caller; 94 cenários e30 mutações compiladas por SIGABRT/assertion passaram Mac/Ubuntu ARM64 com cinco inputs iguais. Seis módulos passaram build real Werror/modpost/ELF/vermagic; PCIe76.112 bytes, REG_ON e fonte/config/Image/exports preservados. Seleção/coletor/perfil e prova física seguem pendentes. Wi-Fi, IRQ/DMA/firmware e carga Linux não são comprovados por hold.

## D2. Aquisição held e limpeza com contratos próprios

- **Decisão:** usar um parser próprio para `SCAN_HELD`/`SESSION_HELD` e getter separado, compartilhando os validadores de topologia/BAR e restore PME. Seleção de build é explícita e o modo retido terá retomada para limpeza por SSH, ligada ao perfil, boot e histórico; falhas conservam owners até limpeza comprovada.
- **Por quê:** o adapter positivo retorna antes do resumo temporário; converter registros ou criar contagens/restores fictícios esconderia a ausência de prova. Retenção validada permite continuar operações compatíveis no mesmo boot.
- **Alternativas:** remover o bus ao terminar cada coletor exige outra aquisição PCI para continuar; acrescentar logs sintéticos para reutilizar o parser temporário mistura prova de ownership com prova de cleanup. Uma migração completa do protocolo pode vir depois, com custo maior para os perfis anteriores.
- **Reverter:** baixo para o opt-in; os caminhos anteriores continuam selecionando seus próprios builds. A retomada deverá conservar o contrato de cleanup mesmo se o comando CLI mudar.
- **Onde:** incremento177 e integração posterior de [n71-funcional-goal.md](n71-funcional-goal.md), parser/coletor host; [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39).
- **Status:** parser/seleção aplicados em `49d2158`, CLI de aquisição/retomada em `36c7f53` e composer do perfil completo em `c30a4ac`. CLI 18/22 e compatibilidade 45/81; composer 13/29, com 20 inputs, passaram Mac/Ubuntu ARM64 e logs por SHA. Perfil privado real separado passou checks locais; payload, kernel/DT/loader/initramfs/identidades preservados, ambos os módulos e booleanos verificados. Prova física continua pendente; coletores futuros que alterem histórico/estado precisam participar do checkpoint da sessão. Manter iOS para recarga durante desenvolvimento offline.

## D3. Atribuição PCI pelo alocador do kernel

- **Decisão:** integrar o alocador PCI padrão ao bus retido, com uma fase explícita de configuração e restauração própria dos três registradores adicionais. BAR0/BAR2 devem caber na janela MEM32 N71 já documentada; decode e bus-master continuam desligados durante a atribuição.
- **Por quê:** Wi-Fi exige recursos atribuídos que o núcleo PCI e o driver reconheçam. O scan anterior só sonda tamanhos; a política dele recusa as escritas de atribuição e não captura todos os registradores usados pelo alocador.
- **Alternativas:** escrever endereços fixos manualmente também exige atualizar e reservar a árvore de recursos; pci_host_probe habilita etapas de registro/bind antes dos controles IRQ/IOMMU. Repetir um scan temporário não prepara o driver.
- **Reverter:** baixo para a fase opt-in; módulos/perfis anteriores permanecem disponíveis. A limpeza deve remover o bus antes da restauração e não liberar owners em erro.
- **Onde:** incremento 183 e integração seguinte do plano; política de configuração, adaptador PCI, caller e journal; issue39.
- **Status:** política aplicada em `8c16d0a`, adaptador em `3f09eec` e caller em `3ff8769`. Adaptador64 cenários/51 mutações e caller121/59 passaram Mac/Ubuntu ARM64, com inputs/logs/exit por SHA; árvores/PCI APIs sintéticas. Seis módulos passaram build real Werror/modpost/ELF/vermagic, PCIe84.696 bytes e REG_ON intacto, fonte/config/Image/exports preservados; action/resources e referências ao alocador/reserva/release verificadas. A ação conserva o primeiro erro e EALREADY não invalida a sessão; getter exige ownership vivo. Seleção/provenance/journal e prova física da atribuição/restauração continuam pendentes; depois integrar IRQ/IOMMU/driver/radio e HDQ/carga na sessão agrupada. [Reprodução e limites](../../docs/N71_PME_ASPM_CANDIDATE.md#atribuição-no-bus-retido--adaptador-caller-e-build-real), [prova](../../docs/evidence/n71-pci-resource-assignment.json).

## D4. Separar erro operacional DART de ownership liberado

- **Decisão:** conservar EIO/command change como resultado negativo do provider, aceitar cleanup somente com restore/owners/caller completos e causais, e preservar a precedência do erro da atribuição. Revalidar logs sem reescrever campos e testar resume sem novo setter.
- **Por quê:** o hardware passou associação e atribuição; o kernel já tinha liberado os recursos quando o parser declarou ownership pendente. Prova de liberação não comprova um ciclo DART inalterado, IRQ entregue ou tradução DMA.
- **Alternativas:** continuar exigindo o erro anterior zero força recuperação manual e não corresponde ao protocolo; aceitar qualquer negativo ocultaria erro divergente ou owner ativo. Alterar command/restore agora exige outra qualificação física e não é necessário para corrigir o parser.
- **Reverter:** baixo; mudança somente host, com defaults/artefatos/módulos preservados e regressões dos modos anteriores.
- **Onde:** [plano](n71-dart-cleanup-operation-error.md), [prova física](../../docs/evidence/n71-of-scope-association-physical.json), issue40/Wi-Fi9.
- **Status:** implementada e gates Mac/Ubuntu ARM64 aprovados; publicação/CI da correção seguem gates próprios.

## D5. Solicitar somente intervenção física indispensável

- **Decisão:** pedir DFU diretamente quando a candidata e o monitor estiverem prontos. Não pedir disponibilidade/conexão/confirmação de tela ou desbloqueio quando não houver ação dependente. Após encerrar Linux e salvar snapshot, continuar offline conforme instrução do operador; confirmação não observada fica ausente da prova.
- **Por quê:** o touch defeituoso torna desbloqueios caros e o operador pediu redução de intervenções, reboots e perguntas de estado. Leitura USB pode ser feita pelo Mac.
- **Alternativas:** confirmar cada transição amplia trabalho do operador; declarar sucesso físico sem observação produziria evidência incorreta. Agrupar teste/coleta/cleanup reduz DFUs.
- **Reverter:** baixo; solicitar novamente apenas uma ação concreta quando um bloqueio físico impedir o trabalho autorizado.
- **Onde:** wrapper/execução supervisionada, documentação atual e próximos testes agrupados; preferência explícita do operador nesta sessão.
- **Status:** aplicada; nenhuma ação do operador é necessária durante as correções offline.

## D6. Corrigir a falha MSI na cópia do pacote Wi-Fi

- **Decisão:** devolver o erro de `pci_enable_msi` antes do request IRQ, aplicando patch fixado por hashes apenas ao brcmfmac copiado pelo builder; preservar kernel e conjunto original para rollback.
- **Por quê:** a associação do provider não garante alocação MSI. O driver upstream ignorava a falha e tentava uma IRQ sem sucesso MSI comprovado. O pacote externo permite corrigir isso sem outro kernel/DFU.
- **Alternativas:** carregar o driver original arrisca fallback/IRQ inválida; alterar o kernel inteiro aumenta custo/reboots sem necessidade; acrescentar fallback INTx não corresponde ao transporte qualificado para N71.
- **Reverter:** baixo; os oito módulos anteriores continuam intactos e não houve carga no aparelho.
- **Onde:** [plano](n71-brcmfmac-msi-error.md), [reprodução](../../docs/N71_WIFI_MODULES.md#correção-de-falha-msi--2026-10-09), [evidência](../../docs/evidence/n71-brcmfmac-msi-error-qualified.json), issues9/40.
- **Status:** patch, regressão C e gates/build Mac/Ubuntu ARM64 aprovados; integração e prova física de IRQ/DMA/rádio permanecem na fila.

## D7. Configuração MSI com readback e cleanup separado

- **Decisão:** integrar um owner de configuração específico ao callback PCI, sem habilitar decode/MASTER. Capture exato, grant único e mensagem comprovada precedem enable; stop com readback precede free, e restore espera grants/mappings zerados. Replays idênticos são noops; zeros do core só após stop.
- **Por quê:** a fonte PCI fixada ignora retornos dos writes MSI; sucesso da API não garante programação do hardware. O core pode reescrever a mensagem ao ativar/alterar afinidade e zerá-la ao desativar.
- **Alternativas:** liberar writes gerais perde o limite da concessão; confiar somente no retorno PCI pode liberar vetores enquanto MSI permanece habilitado. Alterar o kernel inteiro aumenta o custo sem resolver ownership.
- **Reverter:** baixo para o opt-in; owner vazio mantém o caminho anterior. Driver/DMA precisam de contrato próprio antes de liberar decode/MASTER.
- **Onde:** [plano](n71-wlan-msi-config.md), [reprodução](../../docs/N71_IRQ_IOMMU.md#configuração-msi--owner-e-callback-qualificados), [evidência](../../docs/evidence/n71-msi-config-qualified.json), issues40/9.
- **Status:** helper/callback e build ARM64 qualificados; caller/getter/collector/journal e driver/energia em curso. Sem teste físico isolado de alocação.

## D8. Alocar um vetor pelo core e conservar a referência até restore

- **Decisão:** usar `pci_alloc_irq_vectors` com min/max1 e somente MSI; API D0 exportada após PMCSR4008 e guarda de identidade/COMMAND. Recusar ASPM existente no pai, validar hierarquia AIC/tupla/configuração e conservar endpoint/owner em falha. Stop/readback precedem free; IRQ inicial, grants/mappings e baseline precedem put.
- **Por quê:** o core exige cache D0; atribuí-lo manualmente omite a API e o readback. A fonte fixada chama reconfiguração ASPM pela API D0, portanto a ausência do link é uma condição explícita. O retorno PCI sozinho não comprova mensagem/hardware.
- **Alternativas:** permitir INTx fallback muda o transporte; usar cache manual contorna o estado real; reconstruir kernel para exportar outro helper aumenta o custo. Teardown automático sem stop/readback pode liberar vetores enquanto MSI permanece ativo.
- **Reverter:** baixo; adaptador ainda não exposto no aparelho. Os defaults, kernel e perfil físico anteriores continuam preservados.
- **Onde:** [plano](n71-wlan-msi-config.md), [reprodução](../../docs/N71_IRQ_IOMMU.md#adaptador-de-alocação-msi--qualificação-sem-ação-no-aparelho), [evidência](../../docs/evidence/n71-msi-allocation-qualified.json), issues40/9.
- **Status:** adaptador e probe ARM64 qualificados; ação/getter/cleanup e integração driver/energia seguem em curso, sem DFU isolado.

## D9. Armazenar a lease no host e isolar crashes da fixture

- **Decisão:** tipo compartilhado e lease junto dos owners PCI, com layout da lease/política preservados. A fixture Linux usa PR_SET_DUMPABLE0 no próprio executável; não alterar core_pattern/global para resolver o teste.
- **Por quê:** a alocação precisa acompanhar o lifetime da bridge e a futura limpeza da sessão. O pipe Apport estava habilitado durante três timeouts de executáveis de mutações; tais timeouts não comprovam asserção. Após a supressão,29 mutações compiladas passaram por SIGABRT/asserção.
- **Alternativas:** estado global separado exige associação manual à sessão; configuração global do crash handler altera outros processos. Aumentar timeout não isola a coleta nem melhora a prova do kill.
- **Reverter:** baixo; estrutura simples, sem nova ação/perfil físico; a supressão pertence somente ao teste.
- **Onde:** [plano](n71-msi-caller.md), [evidência](../../docs/evidence/n71-msi-lease-storage-qualified.json), issue40.
- **Status:** armazenamento e probe qualificados; action/getter/cleanup e host ARM64 seguinte pendentes. SSH da VM voltou sem reinicialização; telefone não foi reiniciado.

## D10. Integrar alocação explícita sem reiniciar para testá-la isoladamente

- **Decisão:** actions serializadas `msi-hold`/`msi-release`, getter separado e release antes de consumer/DART no cleanup. Lease ou phase ainda pendente conserva bus/reset/power/módulo, inclusive quando o helper retorna zero. Publicar o erro efetivo do caller no resultado de cleanup. Os novos cenários ficam em fixture focada, incluída pelo caller.
- **Por quê:** a referência PCI e o estado MSI precisam sobreviver até stop/free/restore completos. O getter de associação existente tem parsers e histórico próprios. Testar somente alocação com outro DFU consumiria bateria e trabalho do operador sem habilitar rádio.
- **Alternativas:** alocar no probe muda defaults; reutilizar o getter anterior quebra o contrato de associação; teardown após retorno zero sem conferir a lease permite remover consumidores prematuramente. Um novo boot somente para MSI adia o teste agrupado de driver/energia.
- **Reverter:** baixo; ações explícitas e getter separado, sem perfil selecionado ou módulo carregado no telefone. Kernel e candidata física anterior intactos.
- **Onde:** [plano](n71-msi-caller.md), [reprodução](../../docs/N71_IRQ_IOMMU.md#ações-msi-e-cleanup-no-diagnóstico-completo), [evidência](../../docs/evidence/n71-msi-allocation-caller-qualified.json), issue40.
- **Status:** caller/cleanup e diagnóstico ARM64 qualificados; collector/journal/seleção/perfil, driver/DMA/firmware e energia seguem em curso. Nenhuma ação física do operador necessária agora.

## D11. Coletar estado MSI sem emitir nova action

- **Decisão:** getter opcional em módulos anteriores, parser canônico e comparação de ownership/presença com caller/checkpoint. O modo IOMMU desligado continua sem coleta. A exigência do getter no novo perfil e o journal de actions entram na integração seguinte.
- **Por quê:** permite conservar e verificar o estado real na continuidade sem antecipar seleção de artefato, alocação ou prova de IRQ/rádio. O histórico de associação anterior continua separado.
- **Alternativas:** tornar o getter obrigatório agora quebra módulos anteriores; inferir sucesso a partir de campos parciais gera prova incorreta; emitir hold automaticamente mistura coleta com uma mudança de hardware ainda sem journal.
- **Reverter:** baixo; helper passivo e chamadas locais, nenhum perfil/boot alterado.
- **Onde:** [plano](n71-msi-collector.md), [evidência](../../docs/evidence/n71-msi-passive-collector-qualified.json), issue40.
- **Status:** coleta/snapshot/resume qualificados no Mac/ARM64; intent/proof/seleção/perfil e driver/energia seguem em curso.

## D12. Corrigir a fixture isolada sem retirar sua cobertura específica

- **Decisão:** conservar cleanup DART isolado, com tipos MSI compartilhados e predicado real extraído; release/report são dependências proibidas no caminho que não aloca. Isolar dumpability somente no executável Linux.
- **Por quê:** CI6c7ef24 mostrou um modelo de host antigo incompatível com o cleanup real. O caso de retorno zero com DART ainda owned agrega cobertura específica e precisa continuar.
- **Alternativas:** retirar o gate perde esse cenário; devolver sempre false no predicado MSI mascara o estado; modificar o crash handler global afetaria outros processos.
- **Reverter:** baixo; alteração de fixture/runner, sem produção ou artefatos físicos.
- **Onde:** [plano](n71-dart-cleanup-msi-fixture.md), [evidência](../../docs/evidence/n71-msi-passive-collector-qualified.json), issue40.
- **Status:**31 cenários/17 mutações C e AST/lint fatal aprovados em Mac/Ubuntu ARM64. Falha original preservada; CI do head corrigido em acompanhamento.

## D13. Dar ao driver um modo PCI próprio e usar unload normal como barreira

- **Decisão:** fechar primeiro o contrato do brcmfmac real, depois integrar seu journal. Configuração runtime permite decode/MASTER e writes fixados do driver/core PCI, com capture/readback/restore próprios; não reutiliza a lease manual de diagnóstico. Unload normal deve terminar antes de release/remoção dos consumidores/providers. Probe0 não comprova firmware assíncrono concluído. Modo ativo permitirá agrupar testes e recarregar módulos por SSH antes do cleanup final, sem um DFU por operação.
- **Por quê:** a política qualificada de diagnóstico recusa os writes necessários ao brcmfmac; registrar só `msi-hold` no journal adia a integração do rádio. A fonte fixada do firmware loader mantém referências de módulo/device até depois do callback; o core recusa unload com referências ativas e termina o remove antes de retornar.
- **Alternativas:** ampliar a política de diagnóstico invalida seus limites e evidências; liberar configuração geral aceita efeitos não auditados; acrescentar notifier/ABI de callbacks ao driver duplica a barreira já fornecida pelo kernel. O modo runtime ainda precisa de adapter/caller e acompanhamento assíncrono explícitos. Writes indiretos via MMIO e o free IRQ upstream pertencem ao driver confiável, não são interceptados pela política ECAM; não declarar stop-before-free comprovado em falha de hardware.
- **Reverter:** baixo nesta fase; contrato novo ainda não ligado ao scan/caller ou selecionado no aparelho. Baselines e perfis anteriores permanecem intactos.
- **Onde:** [plano](n71-brcmfmac-runtime.md), política `n71-brcmfmac-config.h`, fixtures compiladas; issues9/40 e demanda de energia2.
- **Status:** política com58 cenários/23 mutações, AST/lint fatal e probe ARM64 Werror/ELF/vermagic/hash qualificados, sem ativação. Integração e prova física de rádio/energia em curso. CI6a9ed79 confirmou os seis jobs dos dois eventos verdes; essa prova pertence ao head anterior.

## D14. Reter energia e referências PCI e usar somente APIs públicas para attach

- **Decisão:** adapter retém os dois devices e PM usage sem transição de hardware, antes de publicar. Overrides pela API do kernel7.2 limitam root=`none` e endpoint=`brcmfmac`. Release bloqueia driver registrado/bound, MSI/grants/mapcounts e enables estranhos; restore e limpeza dos overrides próprios antecedem PM/ref put. Guardar intenção de publicação; não copiar a flag privada is_added. O callback valida a referência antes de acessar o bus. Contador de reads runtime separado do orçamento de scan/rollback.
- **Por quê:** brcmfmac inicializa firmware de modo assíncrono; bus/power não podem desaparecer com callbacks vivos. `pci_bus_add_devices` retorna void e pci_dev_is_added pertence ao header interno do core. A API pública de presença verifica config, não registro completo ou rádio. O orçamento finito do diagnóstico não serve a um driver duradouro nem deve prejudicar o rollback após uso runtime.
- **Alternativas:** copiar priv_flags acopla o código a detalhe interno; inferir registro/firmware pelo retorno0 cria prova incorreta; permitir qualquer driver amplia o experimento; consumir o contador de scan com cada acesso runtime pode impedir a restauração. Remover PCI/PM refs antes de readback deixa owners sem proteção.
- **Reverter:** baixo para esta etapa sem seleção/carga; os defaults e perfis anteriores permanecem disponíveis. A futura seleção só ocorrerá após caller/journal e exclusão MSI completos.
- **Onde:** [fase2a](n71-brcmfmac-runtime.md), `n71-pcie-scan.h`, `n71-pcie-brcmfmac.h`, fixtures e [prova](../../docs/evidence/n71-brcmfmac-host-adapter-qualified.json), issues40/9.
- **Status:** aplicada em662e162;207 cenários/170 mutações por plataforma, AST/lint fatal, diagnóstico completo e probe real ARM64 qualificados com63 inputs/kernel intactos. Caller/guardas MSI/journal/seleção e prova física de rádio/energia em curso; nenhum DFU adicional.

## D15. Separar actions runtime e conservar a primeira causa antes do cleanup

- **Decisão:** opt-in `driver_runtime=false`, actions prepare/publish/release e getter passivo separado, sem efeitos novos no probe. Reunir active/refs/PM/overrides num predicado compartilhado. MSI manual recusa antes de tocar seu adapter ou contaminar a sessão. Cleanup libera runtime antes de consumers/DART/reset/power e conserva owners parciais/false-zero para retry no mesmo boot. Release admite erros anteriores e independe do opt-in; latch sob spinlock conserva a primeira causa antes de descartar o host.
- **Por quê:** firmware termina de forma assíncrona; publicação não comprova readiness e a causa pode chegar depois do setter. Descartar o host antes de copiar o erro perde diagnóstico; liberar providers enquanto há PM/refs/overrides prejudica recuperação. Actions explícitas permitirão reunir os efeitos no mesmo boot, reduzindo a necessidade de DFU.
- **Alternativas:** autoload no probe adianta firmware/efeitos antes do journal; alterar getters legados quebra consumidores; duplicar o predicado permite divergência entre release e remoção; exigir uma sessão sem erro para release bloqueia recuperação. A barreira continua sendo unload normal, sem notifier extra ou acesso a private driver data.
- **Reverter:** baixo antes da seleção física; baselines e perfis anteriores continuam íntegros. A integração host seguinte precisa observar o novo formato explicitamente.
- **Onde:** [plano](n71-brcmfmac-runtime.md), `n71-pcie-brcmfmac-caller.h`, diagnóstico/MSI/scan, [reprodução](../../docs/N71_BRCMFMAC_RUNTIME.md), [evidência](../../docs/evidence/n71-brcmfmac-caller-qualified.json), issues40/9/2.
- **Status:** aplicada em4576d7b/c370096/e088212/b2429a4;575 cenários/455 mutações por plataforma e diagnóstico completo ARM64 qualificados,69 inputs/kernel preservados. Journal/seleção/firmware/energia e prova física permanecem em curso. Nenhuma intervenção necessária do operador nesta etapa.

## D16. Observar a causa assíncrona sem admitir novos efeitos pelo getter

- **Decisão:** integrar getter runtime opcional/passivo ao coordinator IOMMU e exigir sua presença/seleção imutável no novo modo. Schema canônico de15 campos, pending derivado dos seis owners, vínculo ao caller/held/cleanup e primeira causa. Retomada permite somente reads crescentes e causa0→negativa, conservando seleção/owners/publicação e erros anteriores. O delta de uma action possui resultado nativo único com action esperada; publicar0 com erro assíncrono no report não vira prova de firmware/radio.
- **Por quê:** firmware pode falhar depois do retorno do setter e o driver lê configuração durante runtime. Igualdade completa de snapshots recusaria observações legítimas; permitir mudança de owners/publicação a partir de getter dispensaria o journal. O collector conserva as duas distinções.
- **Alternativas:** ignorar o erro posterior perde a primeira causa; permitir qualquer drift aceita um efeito sem intenção/prova; modificar os formatos MSI/IOMMU legados afeta perfis existentes. Esses formatos permanecem iguais e sua retomada estrita não é relaxada nesta fase.
- **Reverter:** baixo antes da seleção física; helper/coleta opcionais e nenhum setter, perfil, módulo ou firmware ativado. A próxima fase integra journal/actions/unload e a seleção explícita.
- **Onde:** [plano host](n71-driver-runtime-host.md), `n71_driver_runtime_result.py`, `n71_iommu_result.py` e fixture do protocolo/coordinator.
- **Status:** coleta/parser/coordinator qualificados com80 testes/154 mutações por AssertionError em Mac/Ubuntu ARM64,260 inputs finais e AST/lint íntegros. Kernel/caller/build anterior intactos; CI6e1cc9c terminou com seis jobs verdes nos dois eventos. Actions/journal/seleção e firmware/energia continuam em curso; goal e issues40/9/2 abertos, sem ação necessária do operador.

## D17. Journal de actions antes de habilitar a candidata

- **Decisão:** registrar cada prepare/publish/release com intent fsync, native result e getter; reconciliar interrupção apenas por leitura no mesmo boot. Habilitação do perfil/CLI fica após unload/cleanup e integração MSI/DMA.
- **Por quê:** evita reexecutar um setter após perda de SSH e reduz a necessidade de DFU para recuperar uma sessão retida.
- **Alternativas:** repetir setter sem proof perde a distinção entre execução e transporte; liberar providers automaticamente pode descartar owners; adiar todo o journal até o teste físico aumentaria reboot/intervenção.
- **Reverter:** baixo antes da ativação; ledger privado novo e defaults false, sem seleção física alterada.
- **Onde:** .agents/plans/n71-driver-runtime-host.md faseB1 e scripts/host/n71_driver_runtime_stage.py, integração no journal held.
- **Status:** em curso; B1 qualificada90/169 com263 inputs e defaults preservados. B2 deve integrar unload/cleanup/MSI-DMA e a janela anterior ao hash/checkpoint; C e firmware/energia continuam necessários antes do DFU.

## D18. Módulos PCIe com configuração de build isolada

- **Decisão:** copiar o O preservado e habilitar somente BRCMFMAC_PCIE/PROTO_MSGBUF nessa cópia, compilando módulos oficiais com outputs MO separados e exports conferidos. Não mudar source/config/Image do baseline nem instalar no Mac/iPhone.
- **Por quê:** o build atual só seleciona SDIO/BCDC; firmware e runtime caller sozinhos não fornecem o driver PCIe necessário para Wi-Fi. MO é suportado pela fonte e evita outputs dentro dela.
- **Alternativas:** flags/header shim por módulo ocultariam divergência de Kconfig; reconstruir/substituir a Image base ampliaria o teste físico e o rollback; continuar sem módulo PCIe não permite o objetivo de rádio.
- **Reverter:** baixo; staging novo descartável, baseline e perfil anteriores conservados, sem ativação física.
- **Onde:** .agents/plans/n71-brcmfmac-pcie-build.md e staging privado da VM; pendência registrada na issue9.
- **Status:** aplicada ao staging; oito módulos/1.245.480 bytes/ABI/imports/alias qualificados e auditados no Mac, baseline intacto. Journal/seleção/calibração/energia e compatibilidade física ainda pendentes.

## D19. Observação MSI durante o driver com publicação comprovada

- **Decisão:** aceitar somente o vetor único e o domínio child retido no modo runtime comprovado pelo ledger; preservar providers, owners e primeira causa. Não remover domínio vazio manualmente.
- **Por quê:** a fonte oficial deixa o domínio do dispositivo vivo depois de liberar vetores; igualdade legacy recusaria callbacks legítimos e forçaria retomadas desnecessárias. O kernel adapter já permite child vazio e conserva o provider até consumer removal.
- **Alternativas:** igualdade total bloqueia o driver ativo; permitir qualquer drift pela flag aceita grants/owners não comprovados; remover domínio manualmente interfere no lifetime core e não é necessário.
- **Reverter:** baixo antes da ativação, helper opcional e defaults/formatos antigos preservados.
- **Onde:** plano hostB2a, n71_driver_runtime_result.py e n71_iommu_result.py, fixture de continuidade/coordinator.
- **Status:** aplicada em c8ab8ee;98/186 por plataforma Mac/ARM64,267 inputs íntegros e69 C preservados, AST/lint. Coordenador/histórico/resources/cleanup e seleção C ainda exigem integração antes do teste físico agrupado.

## D20. Recuperar por observação sem alterar a evidência interrompida

- **Decisão:** revalidar a origem e observar o boot atual; produzir uma cópia privada com completion observada/checkpoint novo para o loader existente. Proof órfão sem hash registrado permanece intacto e não prova exit SSH.
- **Por quê:** um crash pode acontecer depois da action e antes do hash/checkpoint. Repetir o setter ou sobrescrever o proof causa efeitos duplicados ou perde a evidência; a observação nativa no mesmo boot resolve a janela comprovável sem DFU.
- **Alternativas:** exigir sempre checkpoint bloqueia recuperação legítima; confiar no órfão fabrica a prova de transporte; reconstruir a origem apaga a evidência do crash.
- **Reverter:** baixo antes da ativação; caminho limitado ao runtime com ledger, loader legacy preservado.
- **Onde:** plano hostB2b1 e helper runtime de recuperação, chamada localizada no coordinator held.
- **Status:** aplicada em4e4177f;110/196 por plataforma Mac/ARM64,270 inputs íntegros, AST/lint e69 C preservados. Origem/órfão intactos e observação sem exit inventado; unload/coordenador/resources/cleanup e seleção física continuam pendentes.

## D21. Preparar o host, carregar WCC e só então publicar

- **Decisão:** carregar rfkill/cfg80211/brcmutil/brcmfmac/WCC depois de prepare e antes de publish; unload normal em ordem inversa, com receipt exclusivo e ledger antes de cada efeito. Não depender de modprobe automático nem carregar vendors não usados.
- **Por quê:** a tabela PCI BCM4350 seleciona WCC; o PCI core bloqueia binding até a publicação. Prepare exige core ausente, e pre-load após prepare permite registrar WCC antes de callbacks. Pins/refcounts e holders ocupados impedem unload, conservando a sessão para nova observação.
- **Alternativas:** publicar antes de carregar WCC exige autoload ainda não preparado no rootfs; carregar core antes de prepare viola a guarda nativa; remover core antes do vendor conflita com sua dependência; force/unbind perde a barreira de lifetime e foi descartado.
- **Reverter:** baixo antes da ativação; módulos/perfil antigos e defaults legacy conservados, sem mudança no kernel.
- **Onde:** plano hostB2b2, protocolo e journal de módulos, depois coordenador e seleção C.
- **Status:** M1 aplicada em0a315b9 e M2 em4d857bf; matriz afetada131/230 Mac/ARM64,276 inputs íntegros, AST/lint. Ledger/hooks/recuperação de módulos qualificados offline; coordenador/causalidade/seleção física continuam em curso.69 C e oito módulos byte/SHA preservados; nenhum boot/load no aparelho.

## D22. Conservar a causa runtime ao limpar os providers

- **Decisão:** integrar uma causa de cleanup somente quando a release nativa completa e bem-sucedida estiver comprovada no ledger/histórico do mesmo boot. Assignment anterior precede essa causa; provider posterior não a substitui. Usar implementação compartilhada de cleanup e conservar a entrada legacy.
- **Por quê:** release0 remove ownership, mas não apaga a falha anterior do driver. O collector atual só conhece assignment/provider e recusaria a limpeza legítima ou perderia sua causa.
- **Alternativas:** inferir pelo getter sozinho dispensa prova de release; usar sempre erro provider perde a ordem causal; ignorar a causa transformaria uma operação falha em sucesso. A prova da release e seu histórico mantém o escopo explícito.
- **Reverter:** baixo antes da ativação; helpers passivos e caminho legacy conservado, sem mudança de kernel/perfil.
- **Onde:** plano hostB2b3a e helpers runtime/resource/IOMMU, teste de cleanup runtime.
- **Status:** aplicada em b8fdd56,147/273 por plataforma Mac/ARM64,278 inputs íntegros, AST/lint. C/build preservados, nenhuma ação física. Continuidade/histórico/source, coordenador/seleção/candidata física ainda pendentes; captura held deverá acrescentar boot e log completo.

## D23. Limitar a continuidade ao lifetime comprovado

- **Decisão:** usar validação passiva específica para o runtime, conservando os contratos legacy. Aceitar publicação/release somente pelo ledger/proofs e recusas ECAM assíncronas somente dentro do driver publicado, vinculadas à sua causa e ao mesmo boot.
- **Por quê:** igualdade de snapshots antigos recusaria mudanças legítimas do driver; relaxar todo o histórico/ownership poderia admitir outro efeito sem intenção. A ponte comprovada permite continuar o desenvolvimento por SSH no mesmo boot.
- **Alternativas:** exigir outro DFU após cada diferença perde a sessão; ignorar diferenças perde ownership e erro; ampliar o parser legacy afeta perfis anteriores. O contrato runtime separado conserva esses limites.
- **Reverter:** baixo antes da ativação; helper passivo e hooks específicos, sem mudança de kernel/perfil/CLI.
- **Onde:** plano hostB2b3b e lifetime/module-ledger/recovery/resource-retained; coordenador na fatia seguinte.
- **Status:** na fila, com contrato fechado; Wi-Fi/energia e prova física ainda pendentes. Nenhuma ação do operador necessária agora.

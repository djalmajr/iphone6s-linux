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

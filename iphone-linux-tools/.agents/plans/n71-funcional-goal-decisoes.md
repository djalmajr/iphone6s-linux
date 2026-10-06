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
- **Status:** política aplicada em `8c16d0a`: 188 cenários/25 mutações compiladas por SIGABRT/assertion no Mac/Ubuntu ARM64, seis inputs/logs por SHA, captura sem efeitos, limites/readback e pending conservado em erro. APIs exportadas do kernel conferidas. Adaptador/caller/journal, reserva e validação da árvore de recursos, registradores opcionais e build real permanecem pendentes; integrar esses controles antes da sessão física agrupada.

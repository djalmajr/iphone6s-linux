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
- **Status:** parser/seleção aplicados em `49d2158` e CLI de aquisição/retomada em `36c7f53`. O coordenador passou 18 testes/22 mutações e a compatibilidade anterior 45/81 no Mac/Ubuntu ARM64; 36 inputs finais e logs por SHA. Retomadas de cleanup/unload/REG_ON pulam etapas comprovadas e preservam stop-error negativo. Perfil físico e prova de hardware continuam pendentes; coletores futuros que alterem histórico/estado precisam participar do checkpoint da sessão. Manter iOS para recarga durante desenvolvimento offline.

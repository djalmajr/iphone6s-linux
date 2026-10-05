# Decisões — Wi-Fi e energia N71

## D1. Caller com hold explícito e getter separado

- **Decisão:** expor `scan_hold` desativado por padrão, exigir PME/host-scan e manter módulo, binding/MMIO e energia até `action=cleanup`. O getter `held` lê bus/ownership do adapter sob o lock; o formato de `status` permanece igual.
- **Por quê:** permite continuar o desenvolvimento por SSH no mesmo boot e usa o estado real do bridge. Os parsers atuais já dependem do protocolo de status, então a leitura nova terá um contrato próprio.
- **Alternativas:** acrescentar `held` ao status exigiria migrar os parsers existentes; armazenar uma flag no diagnóstico exigiria sincronizá-la com o adapter durante falhas e retry.
- **Reverter:** baixo; opção nova é explícita e os wrappers anteriores continuam removendo o bus imediatamente. A migração para um protocolo versionado pode reunir os getters posteriormente.
- **Onde:** incremento175 de [n71-funcional-goal.md](n71-funcional-goal.md), caller PCI e fixtures nativas; [issue39](https://github.com/djalmajr/iphone6s-linux/issues/39).
- **Status:** aplicada no caller; 94 cenários e30 mutações compiladas por SIGABRT/assertion passaram Mac/Ubuntu ARM64 com cinco inputs iguais. Build real, seleção/coletor/perfil e prova física seguem pendentes. Wi-Fi, IRQ/DMA/firmware e carga Linux não são comprovados por hold.

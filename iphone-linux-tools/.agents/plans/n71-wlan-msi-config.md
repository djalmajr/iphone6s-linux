# Configuração MSI com ownership e readback — #40/#9

## Contexto

HEAD inicial963c52b: brcmfmac corrigido, módulos power2 e CI aprovados; ainda não houve carga de driver/firmware. A fonte PCI fixada ignora retornos de writes MSI. O endpoint observado tem cap0x58/header00886805, MSI64/16 vetores possíveis, sem MSI-X e desabilitado. O transporte N71 usa endereço bffff000/0 e vetor lógico8..15. A prova de associação não é prova de alocação/IRQ/DMA.

`phone/kernel/n71-pcie-scan.h:135` ainda encaminha writes somente ao owner de recursos/PME e `:174` nega enable. `phone/kernel/n71-wlan-msi-host.h:44` retém child/domain até remover consumidores. O core escreve flags word0x5a, endereço dword0x5c/0x60 e data word0x64, altera INTx em COMMAND word e não restaura mensagem ao liberar vetores. O enable de endpoint também habilita a bridge e tenta MASTER mesmo quando enable da bridge falha: não liberar esse caminho até a fase driver/DMA estar pronta.

## Arquivos e detalhes

Fase1 (quatro arquivos): este plano, `phone/kernel/n71-wlan-msi-config.h`, `tests/n71_wlan_msi_config.c`, `tests/test_n71_wlan_msi_config.py`. Helper real de capture/write/stop/restore, com estado único, primeiro erro conservado, MMIO bounded, grants exatos e readback; testes C exercitam I/O e falhas. A fase não publica ação no aparelho nem libera enable/MASTER. Fase2: integrar callbacks/lifetime em `phone/kernel/n71-pcie-scan.h` e seus testes C/Python, com defaults anteriores preservados. Fase3: caller/getter/collector/journal e build/profile em grupos de até cinco arquivos; documentar campos antes de testar fisicamente. Driver/firmware/DMA serão reunidos ao mesmo boot necessário, sem pedir DFU só para testar a alocação MSI.

## Contrato escolhido

Capture aceita identidade/layout exatos, MSI desabilitado, COMMAND sem decode/MASTER, baseline completo e owner vazio. Normal writes: apenas endpoint, larguras2/4 conhecidas; bits de COMMAND preservados, exceto INTx-disable. Mensagem/endereço/enable exigem uma única concessão do parent em slots0..7; vetor precisa corresponder ao slot concedido. Enable exige readback de mensagem e INTx-disable. Nada de byte writes, MSI-X, QSIZE multi-MSI, root writes ou fallback INTx.

Stop desabilita MSI e comprova readback antes do core liberar vetores. Falha retém owner; erro anterior não impede uma tentativa de stop verificada. Após stop, só os writes de desligamento do core são aceitos. Restore espera software MSI desabilitado e grants/mapcount zerados, restaura mensagem/COMMAND e confere baseline completo antes de soltar o owner. Child MSI continua retido até remoção de consumidores. O primeiro erro fica separado de ownership liberado. Root/endpoint identity, cap e ausência de MASTER são revalidados antes de efeitos; callback positivo vira EIO.

## Tarefas

- [x] Auditar fontes PCI/MSI/driver fixadas e registrar obrigações em #40.
- [x] Implementar owner de configuração completo e regressões compiladas/por asserção.
- [x] Integrar ao host com defaults negados e lifetime coerente de grants/consumidores.
- [ ] Caller/getter/collector/journal e validação da alocação/readback/restore no mesmo boot.
- [x] Build externa ARM64 desta fase com exports/ABI power2; kernel e rollback preservados. Requalificar as integrações futuras.
- [ ] Integrar driver/DMA/firmware e preparação de energia para agrupar a próxima sessão física.
- [ ] Publicar reprodução/evidência/pendências e acompanhar CI; sem main.

## Verificação

Fases1/2 qualificadas: Mac e Ubuntu ARM64,91 cenários/27 mutações compiladas do owner e183 cenários/147 mutações do host em seis métodos. Todos os kills exigem build aprovado, SIGABRT e texto de asserção. O runner Ubuntu atingiu180s após três métodos completos; eles foram reutilizados com54 inputs intactos e somente os três métodos restantes foram executados novamente. A leitura do delimitador do resultado foi corrigida no runner privado antes da retomada. Módulo completo116.192 bytes/SHA59dc95da, W=1/Werror/modpost,123 imports resolvidos, ELF64/AArch64/vermagic conferidos. AST/lint fatal passaram; não há typechecker Python. [Prova e limites](../../docs/evidence/n71-msi-config-qualified.json).

Ativação/afinidade podem repetir a mesma mensagem habilitada: validar a tupla completa e não escrever. A desativação do core pode zerar os três campos da mensagem somente após stop e readback de MSI off. O COMMAND do endpoint anterior ao capture precisa estar sem decode/MASTER. O próximo caller deve validar PMCSR/D0 real e usar a API exportada de power state, sem atribuir o cache manualmente. O helper diagnóstico atual não libera decode/MASTER do driver.

### Adaptador nativo de alocação — qualificado offline

Arquivos: `phone/kernel/n71-pcie-msi-allocate.h`, `tests/n71_pcie_msi_allocate.c`, `tests/test_n71_pcie_msi_allocate.py` e este plano. Reutilizar validação de recursos e owner real; APIs PCI/IRQ externas serão modeladas no gate C e compiladas contra a fonte real no probe ARM64. Caller serializado retém referência ao endpoint até stop/free/restore; sem driver, request_irq, DMA ou API pública no aparelho nesta fatia. Exigir bus/resources/providers próprios, topologia exata, PMCSR4008/D0 real, cache UNKNOWN/D0, API exportada `pci_set_power_state`, uma concessão/IRQ hierárquica AIC correta e readback MSI completo. Falha após capture conserva lease/owner para release explícito; só free após stop comprovado. Domínio child fica retido para remoção do consumidor. Validar free sem grants/mappings, IRQ inicial restaurada e baseline antes de soltar a referência. Não editar kernel, perfil ou fonte preservados; nenhum DFU nesta fatia.

- [x] Adaptador/configuração reais com referências/locks, retorno e primeiro erro preservados.
- [x] Recusa de ASPM existente no pai antes da API D0; evita reconfiguração auxiliar do core. PMCSR4008 tem NO_SOFT_RESET e D0 físico; não há restauração de BAR neste caminho fixado.
- [x] Mac/Ubuntu ARM64:55 cenários e29 mutações compiladas por SIGABRT/asserção; AST/lint fatal aprovados. Testes iniciais detectaram callbacks sintéticos não usados em mutações e retorno genérico que não verificava o erro original; corrigidos, sem contar falha de compilação como kill.
- [x] Probe real W=1/Werror/modpost:124.504 bytes/SHA9d6f7664,127 imports resolvidos incluindo oito APIs PCI/IRQ requeridas; ELF64/AArch64/vermagic/bytes/hash conferidos no Mac.51 inputs e fonte/config/Image/exports preservados. [Prova e limites](../../docs/evidence/n71-msi-allocation-qualified.json).
- [ ] Integrar ação/getter/cleanup ao módulo real, collector/journal/seleção/perfil e driver/DMA/firmware; nenhum teste físico isolado nesta fatia.

Mac/Ubuntu ARM64: compilar o header de produção e mutações, testando capture sem efeito em falha, grants/offsets/larguras/bit-preservation, enable prematuro, write/readback parcial, primeiro erro, stop antes de free, restore/refusal/retry e ownership retido. Mutações contam somente com compilação aprovada e falha de asserção. Lint/AST e fonte preservada são gates próprios; não há typechecker Python. Testar o wrapper anterior e o módulo completo antes de alterar a seleção. A sessão física futura deve provar IRQ/DMA/interface/scan/associação e telemetria, preservar serviços/snapshot/sync e encerrar antes do orçamento de bateria; nenhuma conclusão por prova offline.

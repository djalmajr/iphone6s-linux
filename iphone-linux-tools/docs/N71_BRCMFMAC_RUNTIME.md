# brcmfmac — configuração PCI runtime N71

## Estado em 2026-10-10

A política de configuração do driver está qualificada offline em `5a1c8df`:58 cenários e23 mutações compiladas por asserção, tanto no Mac quanto no Ubuntu ARM64. AST e lint fatal passaram. O probe no kernel power2 passou W=1/Werror/modpost, ELF/vermagic/imports:11.184 bytes, SHAbcb2b125. Binário/hash/bytes/ELF foram conferidos no Mac e sete inputs/fonte/config/Image/exports foram conservados. [Evidência sanitizada](evidence/n71-brcmfmac-runtime-config-qualified.json), [plano e checklist](../.agents/plans/n71-brcmfmac-runtime.md), [decisão D13](../.agents/plans/n71-funcional-goal-decisoes.md#d13-dar-ao-driver-um-modo-pci-próprio-e-usar-unload-normal-como-barreira).

Esse probe somente compila as funções reais de capture/write/restore. O scan/caller ainda não chama a política e não houve seleção, carga, firmware ou DFU no aparelho. Interface, entrega IRQ, tradução DMA, scan/associação Wi-Fi, gauge e carregamento continuam sem prova física. O primeiro teste da fixture falhou porque a simulação de drift ocorria depois do capture; corrigida a leitura, ambos os gates passaram. Nenhum kill da rodada com baseline falho foi contado.

## Por que existe um contrato separado

O diagnóstico MSI qualificado mantém decode/MASTER desligados e detém uma alocação manual. O [brcmfmac fixado](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L1787) chama `pci_enable_device`, `pci_set_master`, mapeia BAR0/BAR2 e aloca DMA/IRQ durante a inicialização. Ele precisa possuir sua própria alocação MSI e seu teardown. Reaproveitar a lease manual para esse probe recusaria a configuração ou produziria ownership incorreto.

O contrato novo conserva COMMAND dos dois devices, MSI, BAR0_WINDOW e Link Control. Permite somente os writes auditados: COMMAND16 sem IO, PMCSR D0 idêntico, mensagem MSI de um grant AIC, BAR0_WINDOW alinhado, mailbox1 e os dois bits ASPM de Link Control. O replay DWORD do driver vira WORD para preservar STATUS W1C. Os dois writes idênticos da mailbox são eventos e continuam produzindo duas escritas. Após uma falha, a primeira causa permanece registrada enquanto os writes permitidos de teardown ainda podem ocorrer.

Restore exige driver PCI não registrado/não bound, MSI software desligado e grants/mappings zerados. Verifica identidade, desabilita MSI/decode/MASTER, restaura os baselines e confere todos antes de liberar o owner. Erro/drift conserva ownership para retry. Essa política não intercepta writes indiretos via MMIO e não altera a API de free IRQ do driver; em falha de hardware não comprova stop-before-free. O futuro caller precisa conservar bus/providers/energia até restore verificado e registrar o erro efetivo.

## Firmware assíncrono e release

O [loader fixado](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/base/firmware_loader/main.c#L1147) conserva referências ao módulo e device até depois do callback. O brcmfmac passa `THIS_MODULE` nas chamadas assíncronas. O [unload normal](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/kernel/module/main.c#L772) recusa referências ativas e termina o remove antes de retornar. Usar essa barreira; não forçar rmmod nem emitir unbind manual com firmware pendente.

Probe0 ou insmod0 não comprova firmware pronto: o callback pode falhar, disparar remove ou ainda estar em execução. O journal deverá acompanhar registro/binding, erro do modo, módulos, interface/IRQ/DART e depois rádio. A aquisição inicial de associação sem DMA mantém seu histórico próprio. A identificação física existente já confirmou chip4350/revisão8 e seleciona a família `brcmfmac4350-pcie`; compatibilidade da imagem e calibração da placa ainda precisam ser qualificadas.

## Reprodução offline

No checkout, executar o gate nativo sem dispositivo ou pacotes novos:

```bash
python3 -B -m unittest discover -s tests -p test_n71_brcmfmac_config.py -v
```

Para compilar o probe, usar a VM ARM64 dedicada, a fonte/build power2 preservados e conferir os hashes da evidência antes/depois. O diretório do probe deve ser novo e privado. Executar dentro da raiz `iphone-linux-tools` copiada para a VM:

```bash
umask 077
n71_probe_dir=$(mktemp -d /tmp/n71-brcmfmac-config.XXXXXX)
cp phone/kernel/n71-brcmfmac-config.h phone/kernel/n71-wlan-msi-config.h \
  phone/kernel/n71-pcie-scan-config.h phone/kernel/n71-pcie-ecam.h \
  phone/kernel/n71-pcie-contract.h "$n71_probe_dir/"
cp tests/n71_brcmfmac_config_probe.c "$n71_probe_dir/n71-brcmfmac-config-probe.c"
printf 'obj-m += n71-brcmfmac-config-probe.o\n' > "$n71_probe_dir/Makefile"
make -C /home/ubuntu/kernel-n71-binding-source-20261005 \
  O=/home/ubuntu/kernel-n71-binding-build-20261005 M="$n71_probe_dir" \
  W=1 KCFLAGS=-Werror \
  KBUILD_EXTRA_SYMBOLS=/home/ubuntu/kernel-n71-binding-build-20261005/vmlinux.symvers \
  -j2 modules
modinfo -F vermagic "$n71_probe_dir/n71-brcmfmac-config-probe.ko"
readelf -h "$n71_probe_dir/n71-brcmfmac-config-probe.ko"
nm -u "$n71_probe_dir/n71-brcmfmac-config-probe.ko"
```

Os três entrypoints reais devem existir na tabela de símbolos; os imports precisam constar no `vmlinux.symvers` preservado. O probe público é idêntico ao compilado, SHA8d3c8df7. O SHA do binário documenta o artefato qualificado naquele diretório/ambiente; não implica build binariamente reprodutível em outro caminho. Não carregar esse probe no telefone: ele não habilita o driver. Logs completos/binaries permanecem privados em `runtime/n71-brcmfmac-runtime-20261010/`, também na pasta correspondente da VM.

## Relatório da política inicial

- **Arquivos:** política nova, fixtures C/Python, probe de reprodução, plano/D13 e evidência/status/documentação.
- **Plano:** implementação e qualificação da política concluídas; scan/adapter/caller, journal/seleção, firmware/energia e sessão física pendentes.
- **Compatibilidade:** defaults, getters, módulos/perfis anteriores, kernel/config/Image/exports preservados; nenhuma ação física adicional.
- **Verificação:**58 cenários/23 mutações por plataforma; probe ARM64 real e auditado; AST/lint fatal. Gates anteriores intactos foram reutilizados. Nenhum typechecker Python configurado.
- **Banco/dependências:** nenhum banco ou pacote/configuração global instalado/alterado. Desempenho físico não medido.
- **CI anterior:** head6a9ed79 aprovado em [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/38030989085) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/38030986233), três jobs por evento. Essa prova não é a CI da nova política.
- **Próxima tarefa:** ligar a política ao modo runtime retido e impedir cleanup enquanto driver/firmware possuírem os consumidores. Depois journal e candidata de Wi-Fi/energia para uma sessão física agrupada. Issues9/2/40 e goal continuam abertos.

Não há ação necessária do operador nesta fase. Pedir somente DFU quando a candidata/monitor estiverem prontos; confirmação de tela após retorno ao iOS só será solicitada se alguma ação dependente a exigir. Uma transição não observada permanece fora da prova física.

## Host retido e adapter — fase2a

Em662e162, o host guarda configuração e referências do modo brcmfmac. `.enable_device` recusa o default e aceita somente as referências próprias com energia/recursos/DART retidos. Writes ECAM passam pela política runtime e os reads usam contador próprio, preservando o orçamento de scan/rollback. Consumer removal recusa modo ativo ou referências ainda pendentes. O adapter oferece prepare/publish/release separados; essas funções ainda não foram ligadas a actions/opt-in/getter do caller nem à seleção física. Exclusão no adaptador MSI manual também deve entrar antes da ativação. [Evidência](evidence/n71-brcmfmac-host-adapter-qualified.json), [checklist](../.agents/plans/n71-brcmfmac-runtime.md).

Prepare verifica bus/recursos/MSI/DART/topologia/DMA32 e ausência de driver/overrides anteriores. Retém root/endpoint e PM usage com `pm_runtime_get_noresume`, aplica os overrides pela API pública7.2 e conserva referências/configuração se houver falha parcial. Publish emite `pci_bus_add_devices` uma única vez; a flag indica intenção emitida. `pci_device_is_present` verifica resposta ao config; não comprova registration/binding/firmware completos. Não usar pci_dev_is_added/priv_flags internos.

Release exige driver PCI ausente, MSI software desligado, grants/mapcounts zerados e enable_cnt0/1. Após balancear enables PCI, restore/readback precedem a limpeza dos overrides próprios, PM put e PCI put. Override divergente ou write/readback falho conserva ownership para retry; não liberar DART/reset/clock nessa falha. A API void pci_disable_device não devolve o erro de escrita; a prova é o readback final, com a primeira causa registrada separadamente.

### Reprodução e provas

```bash
python3 -B -m unittest discover -s tests -p test_n71_pcie_brcmfmac.py -v
python3 -B -m unittest discover -s tests -p test_n71_pcie_scan_host.py -v
```

Novo gate24 cenários/23 mutações e gate legado183/147 por plataforma, total207/170. Fixture usa adapter e callbacks ECAM reais; PCI/driver/PM/IOMMU são dependências modeladas. O gate legado usa scan completo e adapter de recursos reais. Mac retomou somente os dois métodos com âncoras afetadas, conservando os quatro restantes; Ubuntu ARM64 passou os seis métodos completos. AST/lint fatal passaram; nenhum typechecker Python configurado.

Para reproduzir o build na mesma fonte/build power2, copiar os arquivos C/H de `phone/kernel` para uma pasta nova privada. Compilar o diagnóstico completo e um probe com este conteúdo, que força prepare/publish/release no contexto/layout real:

```c
// SPDX-License-Identifier: GPL-2.0-only
#include "n71-pcie-diagnostic.c"
#include "n71-pcie-brcmfmac.h"
int n71_probe_prepare(struct pci_host_bridge *, struct n71_scan_host *);
int n71_probe_publish(struct pci_host_bridge *, struct n71_scan_host *);
int n71_probe_release(struct pci_host_bridge *, struct n71_scan_host *);
int n71_probe_prepare(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{ return n71_pcie_brcmfmac_prepare(bridge, host); }
int n71_probe_publish(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{ return n71_pcie_brcmfmac_publish(bridge, host); }
int n71_probe_release(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{ return n71_pcie_brcmfmac_release(bridge, host); }
```

Salvar como `n71-brcmfmac-host-probe.c` e usar Makefile com `obj-m += n71-pcie-diagnostic.o n71-brcmfmac-host-probe.o`. Aplicar o comando make da reprodução anterior, com W=1/KCFLAGS=-Werror/exports preservados, sem MODPOST_WARN. Diagnóstico completo129.416 bytes/SHA2c743b7d e127 imports; probe137.368 bytes/SHAb7340c49 e135 imports, incluindo `driver_find`, `__device_set_driver_override`, `pci_bus_add_devices`, `pci_disable_device` e `pci_device_is_present`. Ambos passaram ELF/vermagic/hash/bytes e auditoria no Mac;63 inputs/fonte/config/Image/exports conservados. Os hashes identificam os builds qualificados, não uma promessa de reprodução binária em outro caminho. Logs/módulos ficam privados em `runtime/n71-brcmfmac-adapter-20261010/` e na VM correspondente.

O primeiro baseline falhou por device estrangeiro sem bus na fixture; a guarda agora verifica referência antes de acessar bus. A fixture passou a modelar pci_disable_device sem retorno de erro e testar retenção por readback no restore. Duas âncoras antigas ficaram ambíguas/ausentes; ficaram específicas novamente, sem remover testes. Lint VM encontrou pasta scripts ausente no staging; só esse diretório/lint/auditoria final foram retomados. SIGSEGV, falha de âncora e E902 não contaram como kills. Os gates/build anteriores aprovados foram preservados.

### Relatório e próxima tarefa

- **Arquivos:** scan/adapter/fixtures/plano em662e162; esta reprodução, evidência, STATUS e D14 registram a qualificação.
- **Plano:** fase2a concluída; caller/opt-in/actions/getter/cleanup e exclusão MSI ainda pendentes. Depois journal/seleção/firmware/calibração/energia e sessão física agrupada.
- **Compatibilidade:** defaults e perfis físicos anteriores intactos; nenhum módulo, firmware ou DFU no aparelho. PM usage e hardware ainda não foram provados fisicamente.
- **Testes/tipos/lint:**207/170 por plataforma, build real de dois módulos com Werror/modpost/ELF/vermagic/imports; AST/lint fatal, sem typechecker Python. Nenhuma dependência/banco/configuração global alterada, desempenho físico não medido.
- **CI anterior c7240a1:** [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/38034484984) com três jobs verdes; [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/38034481962) com Windows/Ubuntu verdes e Mac cancelado. Não transformar cancelamento em sucesso nem repetir gates só por haver um segundo evento. CI desta publicação continua separada.
- **Próxima tarefa:** integrar o caller e bloquear lease MSI manual durante runtime antes de preparar journal/seleção. Wi-Fi/IRQ/DMA/firmware, gauge/carga, goal e issues9/2/40 permanecem abertos. Nenhuma ação necessária do operador nesta fase.

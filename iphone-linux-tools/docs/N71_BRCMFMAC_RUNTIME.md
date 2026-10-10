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

## Relatório e continuação

- **Arquivos:** política nova, fixtures C/Python, probe de reprodução, plano/D13 e evidência/status/documentação.
- **Plano:** implementação e qualificação da política concluídas; scan/adapter/caller, journal/seleção, firmware/energia e sessão física pendentes.
- **Compatibilidade:** defaults, getters, módulos/perfis anteriores, kernel/config/Image/exports preservados; nenhuma ação física adicional.
- **Verificação:**58 cenários/23 mutações por plataforma; probe ARM64 real e auditado; AST/lint fatal. Gates anteriores intactos foram reutilizados. Nenhum typechecker Python configurado.
- **Banco/dependências:** nenhum banco ou pacote/configuração global instalado/alterado. Desempenho físico não medido.
- **CI anterior:** head6a9ed79 aprovado em [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/38030989085) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/38030986233), três jobs por evento. Essa prova não é a CI da nova política.
- **Próxima tarefa:** ligar a política ao modo runtime retido e impedir cleanup enquanto driver/firmware possuírem os consumidores. Depois journal e candidata de Wi-Fi/energia para uma sessão física agrupada. Issues9/2/40 e goal continuam abertos.

Não há ação necessária do operador nesta fase. Pedir somente DFU quando a candidata/monitor estiverem prontos; confirmação de tela após retorno ao iOS só será solicitada se alguma ação dependente a exigir. Uma transição não observada permanece fora da prova física.

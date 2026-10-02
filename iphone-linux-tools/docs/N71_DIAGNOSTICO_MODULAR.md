# Diagnóstico PCIe modular N71

O objetivo deste experimento é identificar o endpoint WLAN1 sem habilitar DMA,
firmware ou rádio. Não fornece ainda uma interface Wi-Fi. O kernel funcional,
USB500mA, initramfs e identidades SSH são preservados; somente o DT privado
recebe o binding diagnóstico e as tabelas extraídas do próprio runtime N71.
O módulo fica separado e exige carga explícita. Não usar em outras placas.

## Preparação sem USB

Na raiz do repositório, o gerador aceita somente os insumos privados fixados
por hash: baseline, topologia desativada e captura Pongo já validada.
Escolha diretórios novos; os exemplos não devem sobrescrever resultados.

```sh
python3 iphone-linux-tools/scripts/build/prepare-n71-pcie-diagnostic.py \
  --baseline iphone-linux-tools/runtime/a9-implementation-20261002/baseline.dtb \
  --staged iphone-linux-tools/runtime/a9-implementation-20261002/candidate.dtb \
  --capture iphone-linux-tools/runtime/pongo-n71-reference-20261002/dt-private.txt \
  --output-dir iphone-linux-tools/runtime/n71-diagnostic-new
```

Na VM dedicada, use a fonte Hoolock fixada em
`958481f87fee0949ff6a9a4af77f7eb6dac8a149` e o output do kernel funcional.
Transfira somente os arquivos públicos `phone/kernel/n71-pcie-*` e Makefile
para uma pasta externa à fonte. Não transferir DT/tunables, chaves ou firmware.

```sh
export LOCALVERSION=
make -C /home/ubuntu/kernel-n71-source-20261001 \
  O=/home/ubuntu/kernel-n71-build-20261001-v2 ARCH=arm64 modules_prepare
make -C /home/ubuntu/kernel-n71-source-20261001 \
  O=/home/ubuntu/kernel-n71-build-20261001-v2 ARCH=arm64 \
  M=/home/ubuntu/n71-diagnostic-module-20261002 \
  KBUILD_EXTRA_SYMBOLS=/home/ubuntu/kernel-n71-build-20261001-v2/vmlinux.symvers modules
```

`LOCALVERSION=` evita ABI com sufixo `+`. O build Image-only não tinha
`scripts/module.lds`; `modules_prepare` gerou esse suporte. Modpost avisa que
o `Module.symvers` global não existe, mas recebe os símbolos do mesmo vmlinux
via `KBUILD_EXTRA_SYMBOLS`; não suprimir erros de símbolos indefinidos.
Conferir vermagic `7.2.0-iphone6s-source SMP preempt mod_unload aarch64`.
Copiar o `.ko` de volta para runtime privado no Mac, modo600.

```sh
python3 iphone-linux-tools/scripts/build/compose-n71-diagnostic.py \
  --source-profile iphone-linux-tools/runtime/kernel-usb-budget-20261002/deployment.json \
  --kernel-dir iphone-linux-tools/runtime/kernel-source-build-20261001/artifacts \
  --diagnostic-dir iphone-linux-tools/runtime/n71-diagnostic-new \
  --module iphone-linux-tools/runtime/n71-diagnostic-new/n71-pcie-diagnostic.ko \
  --module-sha256 SHA256_DO_BUILD_VERIFICADO \
  --output-dir iphone-linux-tools/runtime/n71-diagnostic-profile-new
```

O compositor confere ELF/ABI/hash, delta DT e layout do payload. Não carrega
módulo, altera perfil default ou inicia USB. Na candidata de 2026-10-02,
o módulo tem SHA256
`8d62aebade3e122d350a6510b88270be0e0291cb40a3b5e74b7244f16c2883ec`.

## Uma sessão física, dois gates

Boot pelo wrapper com `IPHONE_LINUX_PROFILE` apontando ao perfil privado e
`boot --restore ID` com snapshot previamente verificado. Preservar USB-A
traseiro; fazer DFU manual somente quando o monitor estiver pronto.
SSH usa a chave e o pin do perfil, sem fallback para terminal sem senha.

Após conferir kernel, SSH e HTTP, transferir módulo por stdin SSH para `/run`
e conferir SHA no telefone. Primeiro carregar com `run=1` (enumerate desligado).
Exigir no dmesg `N71_PCIE_CLOCKS_READY` e ausência de falha/cleanup pendente.
O exit zero de insmod sozinho não prova probe: registro do driver pode passar
enquanto o dispositivo falha. Se esse gate passar, descarregar e carregar
no mesmo boot com `run=1 enumerate=1`. Exigir `N71_PCIE_ENDPOINT_ID`, vendor
válido e bus-master desabilitado. Em ambos os modos, o driver mantém/reasserta
PERST e balanceia os quatro domínios ao terminar.

Guardar dmesg bruto somente em runtime privado. Publicar estágio/errno,
status selecionados e identidade PCI, sem identificadores pessoais/tabelas.
Falha exige diagnóstico antes de nova tentativa; atualização do módulo pode
ser enviada por SSH no mesmo boot. Não repetir DFU para trocar um `.ko`.

Ao encerrar, snapshot verificado, sync e `return_ios.py --wait 60`; confirmar
iOS USB e ausência do gadget Linux. Leitura de bateria antes/depois inclui
DFU/reboot/iOS: não é medição de corrente líquida ou prova de carga sustentada.

## Gates já executados

C nativo Mac/ARM64 e objeto kernel/Werror passaram. Fixtures sintéticas testam
ordem/RMW, erros por operação, timeout, capability cycle, Gen1, reset e recusa
de DMA. Gerador e compositor passaram com fixtures e insumos privados reais.
Asserções das mutações são executadas separadamente; falha de compilação
não conta como kill. Nenhum desses gates identifica o chip físico.

### Primeira sessão física — 2026-10-02

Um DFU preservou SSH/HTTP e restaurou o snapshot DNS/Herdr. O modo clocks
passou com marker explícito e driver bound: porta raiz `106b:1004`,
`port88=0000000c`. A enumeração terminou em `-110/ETIMEDOUT`.
Uma versão que registra o último status foi compilada e carregada por SSH
no mesmo boot: novamente `0000000c`, após10000 leituras, sem identidade
do endpoint. Não repetir essa sequência sem corrigir uma causa concreta.

O módulo foi descarregado; SSH continuou respondendo. Backup, sync e retorno
por software ao iOS foram verificados. Bateria100→92 inclui todas as fases
e não comprova carga em Linux. Os sensores e Wi-Fi continuam pendentes.
[Evidência sanitizada](evidence/n71-pcie-first-physical.json).

## Alimentação WLAN no PMIC — candidata reversível

REG_ON está no PMIC D2255, GPIO10/registro8fc/I2C74, separado do device_wake73
do SoC. A referência N71 usa endereço BE de dois bytes sem paginação.
O módulo `n71-wlan-power-diagnostic.ko` usa o binding I2C temporário somente
se o cliente exato não tem driver. Não substituir outro dono. Não faz probe
de endereços nem escreve configuração de carregador, direção ou drive.

Transfira também os headers `n71-wlan-power*.h` para a pasta do módulo na VM.
O mesmo Makefile/build acima produz ambos os módulos sem nova imagem.
A carga `run=1` apenas observa o byte e mantém o cliente bound. Ausência de
`N71_REG_ON_OBSERVED` não é sucesso, mesmo que o comando pareça terminar.
Não passar `power` ao insmod; o controle só fica disponível após observação.

Comandos seguintes são **no Linux do iPhone**, na mesma sessão SSH:

```sh
insmod /run/n71-wlan-power-diagnostic.ko run=1
cat /sys/module/n71_wlan_power_diagnostic/parameters/state
# Só após conferir byte/mode conhecido e marker compatible-plan=1:
printf '1\n' > /sys/module/n71_wlan_power_diagnostic/parameters/power
cat /sys/module/n71_wlan_power_diagnostic/parameters/state
# Executar o diagnóstico PCIe e descarregá-lo antes de restaurar REG_ON.
printf '0\n' > /sys/module/n71_wlan_power_diagnostic/parameters/power
cat /sys/module/n71_wlan_power_diagnostic/parameters/state
# Exigir active=0 restore_pending=0 antes de remover o módulo.
rmmod n71_wlan_power_diagnostic
```

Valor originalmente ativo não precisa de escrita. Modos desconhecidos são
recusados. Escrita parcial marca restauração pendente antes do I2C; falha de
ativação tenta restaurar. Falha/byte divergente no restore mantém pendência
e permite retry. Bits de outro dono alterados impedem sobrescrita.
O kernel não permite retornar erro do callback remove: não usar rmmod para
ocultar pendência; verificar `power=0`/state primeiro. Remoção tenta cleanup
e registra errno/pendência, mas seu exit zero não comprova restauração.

Gates da sequência: C Mac/ARM64, objeto kernel/Werror, sete mutações por
asserção (incluindo write parcial, posse e verificação). Build/modpost do
adapter usa símbolos do vmlinux preservado. Isso ainda não comprova leitura
PMIC, sinal físico REG_ON, link ou Wi-Fi. A próxima sessão reúne esses gates
observáveis e atualizações `.ko` por SSH, sem DFU por ajuste de código.

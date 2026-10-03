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

REG_ON está no PMIC D2255, GPIO10/registro914/I2C74, separado do device_wake73
do SoC. A referência N71 usa endereço BE de dois bytes sem paginação.
O mapper seleciona900+2*pin abaixo17, portanto GPIO10=914. A interpretação
anterior inverteu os operandos de CSEL e escolheu8fc; os testes históricos
desse endereço não qualificam REG_ON. Não reutilizar módulos antigos.
A primeira candidata usava binding I2C temporário e recusou EBUSY no hardware:
simple-mfd-i2c já controla o cliente e mantém filhos RTC/NVMEM. A versão atual
compartilha o regmap16r/8v desse MFD, validando driver/mapa a cada operação sob
device_lock. Não desassociar o driver nem remover seus filhos. Não faz probe
de endereços nem escreve configuração de carregador, direção ou drive.
A escrita usa regmap_update_bits com máscara1, preservando os demais bits;
a referência de vida do cliente não substitui o lock/checagem do mapa devm.
Um futuro driver GPIO deve arbitrar o pin pela API GPIO; este experimento não
fornece essa posse genérica e exige o perfil fixado sem esse outro consumidor.

Transfira também os headers `n71-wlan-power*.h` para a pasta do módulo na VM.
O mesmo Makefile/build acima produz ambos os módulos sem nova imagem.
A carga `run=1` apenas observa o byte e mantém uma referência ao cliente/MFD. Ausência de
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

### Sessão REG_ON compartilhado — 2026-10-02

No mesmo boot, o adapter foi recompilado e transferido por SSH. Leitura8fc
retornou00, sem alterar o PMIC. A candidata antiga classificava o modo de
forma incorreta e recusou ativação; nenhum novo teste PCIe/DMA foi feito.

A referência Apple classifica byte<40 como mode1 (comparação006933e08 e
classificação006933e0c). Porém o byte00 desta sessão veio de8fc, endereço
selecionado incorretamente; não comprova o modo do GPIO10 no registro914.
O contrato corrigido aceita somente bits7:6=00/bits4:3=00, preservando bits5,
2 e1; plano00→01→00 passou nos contratos e falhas sintéticas, mas ainda não
foi aplicado no aparelho. Módulo corrigido SHA92aefccc9c5992f50abb4df350c181d7a2eab71ba4413d5089c3b435f5c3dcca.
Não substituir esta qualificação por um teste que apenas aceite todo byte.

Power0 confirmou active0/pending0; unload preservou MFD/HTTP. Backup/sync
concluídos, retorno USB iOS não confirmado em60s; operador confirmou tela de
bloqueio após fallback. Isso não é prova de reboot por software nem carga.
[Evidência sanitizada](evidence/n71-reg-on-first-physical.json).

### Sessão mode1 e readback — 2026-10-02

A versão com guard de modo corrigido ainda selecionava8fc incorretamente;
aceitou00, mas a tentativa nesse endereço terminou EIO. Um módulo com trace
foi compilado e atualizado por SSH, mantendo o boot: regmap_write retornou0,
porém a leitura válida de8fc continuou00. A segunda tentativa acrescentou
esse diagnóstico; não repetir a operação esperando resultado diferente.

A versão seguinte acrescentou somente getter `level`, sem transmitir ou mudar
modo: a função original GPIO read usa187/bit2 para GPIO10. Leitura retornou
raw20/bit2=0. Isso não qualifica direção/mux, firmware ou rádio. A próxima
etapa deve explicar a configuração elétrica/lógica e semântica do registrador,
em vez de retirar a verificação ou forçar outros bits.

```sh
# Somente leitura, depois de insmod run=1/owner verificado:
cat /sys/module/n71_wlan_power_diagnostic/parameters/level
```

Todos os módulos temporários foram removidos com active0/pending0; PCIe não
foi repetido sem ativação comprovada. Kernels/chaves/DT preservados, duas
atualizações de módulos no mesmo boot. [Evidência](evidence/n71-reg-on-mode1-physical.json).

Snapshot/sync e retorno automático ao iOS USB foram verificados nesta sessão.
Bateria97→91 inclui DFU/Linux/reboot/iOS; não mede corrente líquida nem prova
carga sustentada. iOS voltou a mostrar carregamento ativo. Não recomendar
operação permanente em Linux enquanto esse gate de energia estiver aberto.

### Correção do endereço — conferência binária de CSEL

Os 11 opcodes do helper006933a88 foram conferidos no Mach-O fixado.
`csel w9,w9,w10,lo` em006933aa4 escolhe **w9 quando pin<17**:900+2*pin.
Pinos17..20 escolhem8c0+6*pin; acima20 retornaFFFF. GPIO10=914. O contrato
agora testa todos os pinos válidos, a fronteira16/17 e a recusa21; exige
endereçoBE09 14 e rejeita8fc. A candidata anterior não deve ser reutilizada.

Baseline e14 mutações por asserção passaram no Mac e ARM64; sequência com
sete mutações também passou. Módulo Werror/modpost compilado na mesma ABI,
hash02cb9f6b6c9395addcca5c98f90f7657bf12c20c97d6c8a6b56aaf71ad41d1c7.
Fontes funcionais preservadas sem diff. Isso ainda não prova ativação física.

A próxima sessão começa por leitura914/level187, sem valor escrito no insmod.
Ativação permanece condicionada ao guard de modo e proprietário MFD;
identificação PCIe somente após control readback e nível alto confirmados.
Não retirar essas verificações para fazer o experimento passar.

Consultas iOS somente leitura `ioregentry AppleD2255PMU` e `ioregentry pmu`
não retornaram gpio-activate-defaults, gpio-suspend-defaults,
gpio-quiesce-defaults ou gpio-pin-config. Prova restrita a essas duas
consultas; não demonstra ausência em toda a IORegistry nem autoriza
presumir uma configuração elétrica. Dados completos permanecem privados.

### Controle914 observado e latch80/81 — mesma sessão, 2026-10-03 UTC

No boot corrigido, o módulo02cb9f... leu914=80 e amostra187/raw20/bit2=0.
O guard original recusou ativação; cleanup e unload passaram sem escrita
de valor. Isso foi observado no GPIO10 correto, separado do histórico8fc.

A referência writer006933eb0, com polarity1 do packet101 e tabela ausente,
limpa bits0/3/4 e ajusta bit0, preservando bits7:6. Qualificamos apenas os
bytes exatos80/81: a exceção não aceita82..ff nem muda modo/drive. A
classificação Apple de80 continua mode2; não rebatizamos esse byte como
mode1. gpio-pin-config não aparece no DT runtime completo fixado ou nas
chaves do XML prelinkado; a ausência das consultas iOS continua restrita
aos dois objetos consultados. [Janelas e limites](evidence/n71-wlan-power-reference.json).

Contrato Mac/ARM64:16 mutações por asserção; sequência: sete. O módulo
383b85... passou Werror/modpost com símbolos do mesmo vmlinux e ABI
7.2.0-iphone6s-source. A primeira build omitiu KBUILD_EXTRA_SYMBOLS e foi
recusada pelo modpost; corrigimos a receita, sem suprimir erro de símbolo.
Atualizamos o módulo por SSH, sem outro DFU.

Uma tentativa escreveu81 via regmap mask1 e confirmou readback81. A
amostra187/raw20/bit2 permaneceu0. Portanto, **alimentação WLAN não foi
qualificada e PCIe não foi executado**. O registro de amostragem não é
medição direta de tensão da linha ou do rail. Não forçamos bits de modo,
DMA, firmware ou rádio para ultrapassar esse gate.

Cleanup escreveu80, confirmou readback80/active0/pending0 e removeu o
diagnóstico mantendo o parent. Snapshot/sync e retorno software ao iOS
passaram. [Evidência selecionada](evidence/n71-reg-on-latch80-physical.json).
Próxima investigação: função/mux e validade da amostragem GPIO versus
alimentação real; não repetir a mesma escrita esperando outro resultado.

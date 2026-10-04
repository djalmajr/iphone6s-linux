# Alimentação e bateria do iPhone 6s

Etapa [#2](https://github.com/djalmajr/iphone6s-linux/issues/2), iniciada em 2026-09-29. **Ainda não há comprovação de carga sustentada ou autorização técnica para uso contínuo sem supervisão.**

## Evidência atual

### Descarga no Linux e recarga no iOS — 2026-10-04

O operador informou bateria quase descarregada durante o Linux e que o
aparelho já havia voltado ao iOS. A leitura local, sem pedir PIN, confirmou
**5%**, `BatteryIsCharging=true`, `ExternalConnected=true` e
`ExternalChargeCapable=true`. [Registro sanitizado](evidence/n71-low-battery-ios-20261004.json).

Uma segunda leitura cerca de15 minutos depois confirmou **17%**, com carga
e alimentação externas ativas. O cabo/porta repôs carga no iOS nessa condição;
esse aumento não mede corrente nem comprova carregamento no Linux.

Um checkpoint local desta recarga foi **51% às 19:23:44 UTC**, com carga
externa ativa. É uma leitura anterior registrada na
[issue #2](https://github.com/djalmajr/iphone6s-linux/issues/2#issuecomment-5983537603),
não medição de corrente ou atualização em tempo real.

Uma leitura nesta rodada confirmou **79% às 19:58:58 UTC**, com
carregamento e alimentação externos ativos, sem PIN. Os quatro campos e
digest do log privado estão no [checkpoint selecionado](evidence/n71-i2c-topology-observer.json).
Isso confirma recarga no iOS; corrente líquida no Linux continua sem medição.

O checkpoint seguinte confirmou **89% às 20:29:05 UTC**, com carregamento
e alimentação externos ativos, sem PIN. [Campos e digest selecionados](evidence/n71-i2c-acquisition-reference.json).
O telefone permanece no iOS; a subida do percentual não mede corrente de
bateria nem valida o carregamento Linux.

Nova leitura sem PIN: **93% às 20:48:17 UTC**, ainda com carregamento e
alimentação externos ativos. [Checkpoint e observador PMGR preparado](evidence/n71-pmgr-power-observer.json).
Esse observador mede somente estados PMGR do I2C1 e seus pais; ainda não
foi carregado e não fornece percentual/corrente da bateria no Linux.

Checkpoint seguinte: **100% às 21:23:03 UTC**, alimentação externa conectada
e capaz de carregar; `BatteryIsCharging=false` nessa leitura. São os campos
informados pelo iOS, sem leitura de corrente ou cálculo de saúde da bateria.
[Registro sanitizado](evidence/n71-pmgr-errors.json). Nenhum boot Linux novo
foi iniciado nesta etapa.

Isso reprova o uso contínuo na configuração atual. Não houve leitura de
corrente de bateria no Linux, portanto não distingue carga zero, consumo
superior à entrada ou falha específica do controle de carga. O orçamento
USB500mA não é prova de corrente líquida nem implementação do carregador.
O iPhone permanece no iOS para recarregar; novos testes físicos de Wi-Fi
foram interrompidos, e o desenvolvimento segue offline na alimentação N71.

O último snapshot válido foi salvo após os probes de ponte restaurados.
As mudanças seguintes existem só no Mac/VM. Ao tentar novo snapshot, SSH
já não estava disponível: o comando parou antes de backup/reboot, e não
se atribui esse retorno ao script. O módulo novo de controls/SERR foi
compilado/testado, **não carregado no iPhone**.

Prioridade: confrontar SN2400@75/I2C1 da referência N71, identificar estados
e efeitos dos registradores, implementar acesso/ownership/cleanup qualificados
e telemetria gauge/HDQ. A DTS fixada deixa I2C1 desativado. Nenhum limite de
corrente/tensão, mux, UART ou registrador do carregador foi alterado.
Uma consulta de IORegistry pelo nome AppleSN2400Charger retornou metadados
do serviço, mas não corrente, limites ou estado dos registradores. Não é
prova de ausência de hardware ou de driver no iOS.

Foi preparado um [observador passivo I2C1/GPIO114/115](N71_HDQ.md#observador-passivo-i2c1gpio114115--preparado-sem-teste-no-aparelho)
para reunir metadados e oito leituras de GPIO no próximo boot necessário.
Não ativa o barramento nem aciona o carregador; passou 86 casos e 15 mutações
Mac/ARM64 e build externo do bundle, ainda **sem teste no aparelho**.
Esse módulo pode ser atualizado por SSH no mesmo boot, sem trocar kernel.
Ele prepara aquisição/cleanup, sem resolver por si só a descarga no Linux.

A coleta será agrupada com seis leituras PMGR de I2C1/sio_p/sio_busif no
mesmo boot necessário. Os dois módulos externos usam o ABI preservado;
nenhum Image novo é necessário para essa observação. A correção de erros
GPIO tem [integração pendente](https://github.com/djalmajr/iphone6s-linux/issues/35)
e não pode ser carregada como duplicata do provider embutido.

Os callbacks de estado/reset PMGR também descartavam erros de I/O. A
[patch preparada e seus limites](N71_HDQ.md#erros-dos-callbacks-pmgr--correção-preparada)
passou 492 casos/14 mutações Mac/ARM64 e compilou como objeto embutido
Werror. A integração está na [issue #36](https://github.com/djalmajr/iphone6s-linux/issues/36);
os erros iniciais de probe/is_active foram corrigidos na
[patch seguinte](N71_HDQ.md#erros-iniciais-do-probe-pmgr--correção-preparada),
com 3.138 casos/12 mutações Mac/ARM64 e fonte completa004+005 obj-y/Werror.
Cleanup após registro, ownership/idle e rollback de efeitos parciais continuam
pendentes antes de aquisição ativa do barramento. Isso ainda não implementa
carga no Linux; nenhum DFU foi realizado por esta entrega.

A [patch006](N71_HDQ.md#falha-de-publicação-do-provider-pmgr--cleanup-preparado)
corrige a remoção do domínio quando add_provider falha, preservando provider
alheio e primeiro erro. Passou3.258 casos/seis mutações Mac/ARM64 e objeto
completo004+005+006 obj-y/Werror. Pós-publicação, efeitos parciais e aquisição
ativa continuam pendentes. Essa correção ainda não habilita o carregador;
o iPhone foi mantido no iOS para recarga durante o trabalho offline.

### Encoder SN2400 específico N71 — cálculo implementado, driver pendente

A referência Apple fixada mostra clamp90..2000mA e quantização10mA no caminho
sem calibração de `getInputCurrentSetting`. O
[header puro](../phone/kernel/n71-sn2400-input-reference.h) reproduz esse
cálculo. Pedido0 resulta em suspend separado: código0 também representa90mA
quando a entrada não está suspensa. Calibração habilitada é recusada porque
sua tabela/interpolação não foi portada. Valores representam codificação,
**não corrente medida nem limites seguros para esta bateria ou porta USB**.

Mac e ARM64 passaram fronteiras, domínio16bit, extremosu32 e oito mutações
compiladas por asserção. O header compilou em objeto kernel ARM64 comWerror;
.config/Image/exports permaneceram iguais. Não foi criado ou carregado um
driver de carregador. [Fatos, trechos verificáveis e gates](evidence/n71-sn2400-input-reference.json).

O setter Apple N71 suspende escrevendo0 no registro09 e depois
`(cached_control & ~3) | 8` no10. O caminho positivo usa controle em cache
antes do limite09. O cache é inicializado em4, com bits3 opcionais por
`spread-spectrum-enable`; não é snapshot vivo para restore. O retorno
considera o segundo write, sem propagar diretamente a falha do primeiro.
Não adotar esse tratamento de erro no futuro adapter.

A [fonte Linux A10 fixada](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/drivers/power/supply/apple_sn2400_charger.c)
usa ordem contrária na suspensão e escreve limite de corrente da bateria
no probe. Portanto, compartilharem SN2400 não qualifica copiar a inicialização.
O timer Apple identificado chama modo de software1 e agenda o retorno
pelo `IOTimerEventSource::setTimeout(interval,1e9)`, default8s; o callback
seleciona modo0. Isso não identifica um watchdog físico como causa da descarga.
A [API Apple](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOTimerEventSource.h)
descreve intervalo/escala; o símbolo/slot da versão N71 foi conferido no binário.

Próximos passos: qualificar I2C1/clocks/pinos e proprietário, efeitos de leitura
e revisão do SN2400; implementar captura/readback/cleanup que trate escrita
parcial; depois integrar gauge/HDQ e limites autorizados pela negociação USB
e pela bateria identificada. A aritmética não autoriza aplicar os2000mA máximos.
Preparar o adapter offline e agrupar os testes numa sessão curta, após recarga.

### Retorno do teste de latch WLAN — 2026-10-03 UTC

O teste físico de controle GPIO10 terminou com restauração/readback de
0x80, pendência zerada e módulo removido. Snapshot, sync e retorno por
software ao iOS passaram. Às **02:49:22 UTC**, o iOS informou **85%**,
`BatteryIsCharging=true` e `ExternalConnected=true`, no mesmo USB-A traseiro.
[Registro selecionado](evidence/n71-reg-on-latch80-physical.json).

A leitura anterior de100% precedeu o primeiro monitor expirado e a espera
do operador; não houve baseline imediatamente antes do boot bem-sucedido.
O intervalo inclui recuperação, iOS, DFU, Linux e retorno. Não atribuir os
quinze pontos inteiros ao Linux nem calcular corrente líquida. Carregamento
informado pelo iOS não comprova carregamento no Linux; #2/#8 continuam abertas.
O próximo desenvolvimento segue offline enquanto o aparelho recarrega,
sem novo DFU para repetir essa observação.

### Candidata USB500mA no aparelho — 2026-10-02

Em um único DFU, após colher privadamente o ADT do bootloader, foi carregada a candidata init-only cujo payload tem SHA256 `1a29df4c49bb76c12bb3bcd5929182734172b4f6f0aed76ffbadf885c5f1dbab`. SSH por identidade estrita e HTTP passaram. Aos 105,76 s de uptime, o diagnóstico leu **MaxPower=500 mA**, bmAttributes=80; o IORegistry do Mac reportou **UsbPowerSinkAllocation=500**. Esse campo comprova o orçamento que o host alocou; não é leitura de corrente física. O descritor binário bruto não foi salvo. [Evidência](evidence/n71-runtime-reference.json).

Não apareceram sensores de bateria/temperatura. Brilho foi reduzido temporariamente para 256, conforme preferência do operador. Snapshot/sync passaram e o retorno por software foi confirmado por iPhone8,1 USB e ausência do gadget Linux. iOS reportou 100% antes da preparação e 92% após o retorno, com carga/alimentação externas ativas nessa segunda leitura. O procedimento inclui DFU, Linux, reboot e iOS; não houve medição exata da duração final nem corrente líquida. **A correção do orçamento USB não comprova carga sustentada; #2/#8 continuam abertas.** Não atribuir a queda exclusivamente ao Linux ou tratá-la como oito pontos de consumo medido do intervalo.

### Desenvolvimento HDQ N71 — 2026-10-02

A análise privada do kernel Apple N71 fixado em [referência reproduzível](N71_REFERENCIA.md) identificou o codec de `AppleHDQGasGaugeControl`: cada byte vira oito símbolos UART C0/FE, bit menos significativo primeiro. Na recepção, um bit vale um somente para símbolo **maior que F8**. O limiar F0 do driver A10 não corresponde a essa rotina N71.

Os eventos seriais da rotina Apple, interpretados pelos cabeçalhos oficiais [IOSerialStreamSync](https://github.com/apple-oss-distributions/IOSerialFamily/blob/1c12ee3d9ec665bb53d0151644408d25e54fe012/IOSerialFamily.kmodproj/IOSerialStreamSync.h) e [IORS232SerialStreamSync](https://github.com/apple-oss-distributions/IOSerialFamily/blob/1c12ee3d9ec665bb53d0151644408d25e54fe012/IOSerialFamily.kmodproj/IORS232SerialStreamSync.h), indicam 57.600 baud, oito bits, sem paridade e dois stop bits. Os valores de taxa/tamanho/stop no evento usam unidades de meio-bit; 115.200 no evento não significa baud físico de 115.200.

`phone/kernel/n71-hdq-codec.h` implementa somente transformações de bytes e junção estável high/low/high; não aciona UART, pinmux, GPIO, I2C ou carregador. Echo estrito é uma proteção opcional mais restritiva que o caminho Apple sem coalescimento. Palavra FFFF, um escravo sintético ou bytes decodificados não identificam gauge nem validam unidades/carga.

O ADT N71 liga `function-battery_swi` ao pin2/config102 e `function-battery_swi_request` ao provider `tigris` por HDQm. São referências da placa: a operação do mux compartilhado precisa ser confirmada antes de transmissão. Não copiar pin173 A10 nem programar limites SN2400. **Telemetria física e carga sustentada continuam pendentes (#2/#8).**

```sh
python3 -B -m unittest discover -s tests -p test_n71_hdq_codec.py -v
```

Linux 7.0.12 responde por SSH, com mais de uma hora de uptime. `/sys/class/power_supply` está vazio e não há zonas térmicas utilizáveis. `/proc/config.gz` não está disponível. O barramento I2C expõe `0-0074`; o log mostra PMIC/RTC, mas isso não estabelece suporte de carregamento. O PMU `apple_twister_pmu` citado no log é de contadores de desempenho, não leitura de bateria.

Na checagem inicial não foram escritos registradores, ativados drivers experimentais ou instalado pacote. Não assumir compatibilidade com implementações de carga A10 de outro fork.

O operador confirmou aparelho frio e fisicamente intacto. Após snapshot privado e reinício solicitado para medição em iOS, apareceu a tela de desbloqueio; depois o aparelho saiu do USB. Ao pressionar somente Power, o operador viu novamente a tela de desbloqueio e logo o símbolo de bateria descarregada. Isso comprova carga insuficiente naquele momento, sem estabelecer a causa: não há medição inicial nem leitura de corrente durante o Linux. Cabo/porta, controle de carga no Linux e bateria continuam hipóteses distintas.

O teste inicial de carga sustentada **não passou**. Em 2026-09-30, com outro cabo na USB-C frontal e após desbloqueio, o iPhone voltou ao USB: `BatteryCurrentCapacity=100`, `BatteryIsCharging=true`, `ExternalConnected=true`. O cabo atual suporta dados e alimentação informada pelo iOS. O operador autorizou retomar com teste Linux curto e supervisionado; a comparação posterior de carga continua pendente. O snapshot com sentinela para #4 foi salvo antes do reboot; nenhum backup foi publicado.

## Diagnóstico de desgaste em iOS

Leitura real em 2026-09-30, por `idevicediagnostics diagnostics GasGauge` e `ioregentry AppleARMPMUCharger`, selecionando somente campos de bateria:

| Campo | Valor reportado |
|---|---:|
| CycleCount | 1462 |
| DesignCapacity | 1690 |
| NominalChargeCapacity | 1146 |
| AppleRawMaxCapacity | 830 |
| BatteryData.MaxCapacity | 820 |
| BatteryHealthMetric | 725 |

A relação nominal/projeto é `1146 / 1690 ≈ 67,8%`: estimativa nominal de capacidade restante, **não percentual oficial da tela Saúde da Bateria**. Os outros campos divergem e não têm aqui um contrato de interpretação validado; não combinar suas unidades/semânticas nem apresentar um percentual exato de saúde. `GasGauge.FullChargeCapacity=100`, `IORegistry.MaxCapacity=100` e carga atual 100% também apareceram: não representam bateria nova ou saúde de 100%.

Contagem elevada e capacidade nominal reduzida sugerem desgaste importante. A Apple informa o projeto de retenção de 80% após 500 ciclos em condições ideais para essa geração; isso não estabelece a saúde exata deste exemplar. Avaliação/substituição da bateria continua uma alternativa para uso contínuo. A inspeção visual anterior não detectou anormalidade física, mas não mede capacidade.

### Checkpoint no iOS — 2026-10-04, 23:45–23:47 UTC

GasGauge e AppleARMPMUCharger responderam novamente, sem PIN, reboot ou
escrita no telefone. [Campos selecionados e digests privados](evidence/n71-ios-battery-checkpoint-20261004.json):

| Campo | Valor reportado |
|---|---:|
| CycleCount | 1465 |
| DesignCapacity | 1690 |
| NominalChargeCapacity | 1130 |
| AppleRawMaxCapacity | 985 |
| BatteryData.MaxCapacity | 985 |
| BatteryData.BatteryHealthMetric | 793 |
| CurrentCapacity | 100 |

Nominal/projeto resulta em `1130 / 1690 ≈ 66,9%`. É uma estimativa a partir
desses dois campos, **não a saúde oficial do iOS**. Os demais valores não
devem ser combinados ou interpretados como porcentagens. A diferença entre
as duas datas inclui usos e reinicializações distintos; não isola desgaste
ou consumo causado pelo Linux.

O iOS também informou alimentação externa conectada/capaz de carregar e
`IsCharging=false`, com nível100%; Amperage/InstantAmperage reportaram0.
Isso não mede entrada USB ou corrente líquida durante Linux. Voltage4195,
BatteryData.Voltage4196 e Temperature3030 são mantidos como valores brutos,
sem atribuir unidades ainda não verificadas. Nenhum limite de corrente,
tensão ou temperatura foi programado a partir desta leitura.

O [perfil power e os módulos](evidence/n71-power-profile.json) estão
compostos/validados; a [coleta curta agrupada](N71_HDQ.md#coleta-agrupada-de-energia-na-abi-power--preparada)
continua aguardando um único DFU manual. Os seis jobs da CIe0dc355 passaram;
isso verifica software/documentação e não substitui carga física sustentada.

## Piloto com outro cabo — 2026-09-30

A leitura inicial de 100% ocorreu às 11:07:57 UTC. Houve depois tentativas DFU/PongoOS e cerca de oito minutos de Linux via USB-A, antes da troca para o novo USB-C frontal. O piloto neste último cabo foi iniciado às 11:40:13 UTC, sem carga artificial de CPU. Portanto, a diferença entre as leituras iOS abrange também essas etapas anteriores: não isola o consumo nem o carregamento dos dez minutos no USB-C.

Após a troca, SSH autenticado e HTTP continuaram respondendo, e o operador confirmou novamente aparelho frio/morno e console visível. A checagem Linux continuou sem sensores de bateria e temperatura. O reboot foi solicitado às 11:50:32 UTC (uptime 1147,24 s). Às 11:51:15 UTC, o iOS informou **94%**, `BatteryIsCharging=true` e `ExternalConnected=true`.

A queda de seis pontos confirma consumo no procedimento total, mas não identifica em qual etapa ocorreu nem comprova falta de carregamento no Linux com USB-C. A manutenção da carga durante o Linux continua sem validação. Não encerrar #2 nem iniciar uso prolongado sem supervisão por esse piloto. Para isolar melhor o intervalo, é necessário novo baseline imediatamente antes de um boot com duração registrada e repetir a comparação com o mesmo cabo durante a fase Linux; telemetria de carga específica A9 ou medição física complementar ainda seria preferível.

Em outra consulta, ainda no iOS, a carga informou **90%**, mantendo as duas flags de alimentação/carga verdadeiras. A montagem física naquele instante não foi confirmada, pois a troca para USB-A havia sido solicitada e ainda não confirmada. Não atribuir essa queda ao cabo USB-C ou ao Linux. O serviço de diagnóstico detalhado informou bloqueio por senha; a consulta básica de nível funcionou.

O operador confirmou depois USB-A traseiro, iOS ligado e aparelho frio/morno. Às 12:00:14 UTC, essa montagem informou **94%**, com carga/alimentação externas ativas. O wrapper anterior à remoção do guia completou um novo boot em uma única execução (saída 0, SSH e HTTP 200). Às 12:14:18 UTC foi solicitado reboot, com uptime 734,12 s e snapshot privado salvo. Às 12:15:42 UTC o iOS informou **100%**, ainda com as duas flags verdadeiras.

O segundo procedimento teve montagem USB-A definida e resultado favorável de nível de carga, mas inclui preparação, boot e retorno ao iOS; não mede corrente líquida exclusivamente durante Linux. A oscilação da leitura entre reinicializações e o teto de 100% também limitam a conclusão. É evidência de um intervalo curto, não aprovação de operação contínua nem encerramento de #2.

## Terceiro intervalo supervisionado — USB-A

O novo boot manual, sem página ou contador, iniciou Linux por volta de 12:23:23 UTC. O baseline anterior, às 12:15:42 UTC, era 100%. O operador confirmou console visível e aparelho frio/morno durante a sessão. Pelo novo caminho do CLI, `status` e HTTP passaram às 12:46:40 UTC; um snapshot privado foi salvo às 12:48:08 UTC.

O reboot foi solicitado às **12:48:09 UTC**, com uptime **1485,28 s** (aproximadamente 24 minutos e 45 segundos). Às **12:50:22 UTC**, o iOS informou **90%**, `BatteryIsCharging=true` e `ExternalConnected=true`, no USB-A traseiro mantido durante este intervalo.

A queda de dez pontos inclui o intervalo iOS/DFU anterior e a volta ao iOS, além de possível variação do medidor após reboot. Ela não isola a corrente durante Linux, mas contraria uma conclusão de carga sustentada baseada no segundo teste favorável. **#2 permanece aberta**; operação prolongada sem supervisão continua sem aprovação. Os arquivos foram preservados no Mac antes de retornar ao iOS.

## Inspeção do suporte A9

Revisão pública consultada: `HoolockLinux/linux`, branch `hoolock`, commit `6831bc701a6ce059e71e5aaa9488c9195bea6927`. Foram lidos `s8000-n71.dts`, `s8000.dtsi`, `s800x-6s.dtsi`, `s800-0-3.dtsi`, `s800-0-3-common.dtsi` e `s800-0-3-pmgr.dtsi`. A descrição N71 compartilha um PMIC Antigua em I2C 0x74, com filhos RTC e NVMEM; nessa cadeia consultada não foi encontrada descrição de bateria/carregador. Isso é consistente com a ausência de sensores observada, mas não é auditoria de todo o kernel e não prova que o circuito físico tenha parado de carregar.

O documento `hw/SMC.md` da cópia Hoolock usada pelo build declara aplicação a T8015 (A11), portanto suas chaves de carga não estabelecem uma interface válida para o A9/S8000. Habilitar um driver genérico de bateria na configuração também não fornece, por si só, binding, protocolo ou controle de carga para este aparelho. Não houve escrita de registradores nem tentativa de portar controles de outra geração.

Fontes fixadas: [PMIC no DeviceTree do 6s](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/s800x-6s.dtsi), [SMC com escopo T8015](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/hw/SMC.md).

## Potência declarada pelo gadget USB — investigação

A fonte atual `phone/init/init-server` não atribui `configs/c.1/MaxPower`. No kernel consultado, `configfs.c` inicializa esse atributo com `CONFIG_USB_GADGET_VBUS_DRAW`; o Kconfig tem default de 2 mA, mas isso **não comprova o valor compilado neste APK**. A configuração completa do APK não foi localizada, e a revisão consultada não prova sua proveniência exata. É necessário ler o atributo real no Linux.

`MaxPower` descreve ao host o consumo máximo solicitado do barramento, em mA. Alterá-lo não implementa o carregador da bateria nem comprova corrente líquida. Nesta etapa a decisão é ampliar somente o diagnóstico de leitura: registrar `MaxPower` e `bmAttributes` junto da ausência/presença de sensores. Não mudar registradores de PMIC, não assumir controle de carga A10/A11 e não modificar o descriptor antes da leitura real.

Plano desta etapa (#2):

- [x] Ampliar `phone/diagnostics/power-check.sh` para ler orçamento USB sem escrever sysfs.
- [x] Verificar leituras presentes/ausentes, preservação dos atributos e exclusão de strings identificadoras em `tests/test_power_check.py`.
- [x] Ler o valor real no novo boot e consultar o orçamento no Mac; registrar a indisponibilidade dessa segunda leitura e os limites.

Fontes: [configfs no kernel consultado](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/usb/gadget/configfs.c), [Kconfig do gadget](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/usb/gadget/Kconfig), [ABI dos atributos](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/Documentation/ABI/testing/configfs-usb-gadget), [documentação Linux configfs](https://docs.kernel.org/usb/gadget_configfs.html).

### Valor efetivo obtido — 2026-09-30

O boot com os caminhos reorganizados completou uma única execução, saída 0, SSH/HTTP e console confirmado pelo operador. Baseline iOS às 13:21:47 UTC: 98%, carregamento e alimentação externa ativos. A montagem USB-A traseira foi reafirmada pelo operador e mantida.

A leitura real do configfs retornou **MaxPower=500 mA**, `bmAttributes=0x80`. Portanto, a hipótese de um orçamento de 2 mA causado por default não explícito foi descartada para esta imagem. Nenhuma mudança de descriptor foi feita. A consulta do IORegistry não forneceu propriedades de orçamento para esse gadget; não preencher com números presumidos. Sensores de bateria/temperatura continuam ausentes.

Às 13:27:31 UTC, uptime 291,64 s, load average 0,00/0,00/0,00, governador `schedutil` e frequência reportada 1.512.000 kHz. Backlight: 1526 de 2047; framebuffer em blank 0. Frequência instantânea não comprova consumo, nem ausência de diretórios cpuidle comprova ausência de todo mecanismo de idle da CPU.

O fork A10 foi conferido diretamente em `Pauli1Go/HoolockLinux`, commit `d49ac41cb898881457a97bb3cd44b7d92ff50a8c`. O README limita os aparelhos testados ao iPad 7/J172 e iPhone 7 Plus/D111, A10/T8010; seu suporte de bateria usa BQ27545 via UART/HDQ e carregador SN2400. Isso não fornece binding, GPIO, mux nem prova de compatibilidade para N71/A9. Não foi copiado driver nem escrito registrador. [Fonte primária do fork A10](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/README.md).

### Redução temporária de brilho

O controle padrão do backlight foi reduzido de 1526 para 256 de 2047 no uptime 539,49 s. Ao relatar texto difícil de ver, o operador recebeu ajuste para 512 no uptime 690,27 s; depois esclareceu que não usará o console local, e o brilho voltou a 256 no uptime 780,67 s. O valor anterior foi guardado em `/run/iphone-power-brightness-before`. Essa alteração só vale na sessão em RAM; a imagem não foi reconstruída e o reboot restaura o comportamento original.

**Decisão:** manter brilho baixo na operação pelo Mac e aumentar somente para uma verificação visual necessária. **Alternativa:** apagar o display reduz mais a interface visível, mas exige nova avaliação; não foi feito neste teste. O intervalo tem brilho variável, portanto não é uma comparação controlada que quantifique a economia nem prova isolada de melhora do carregamento.

Reverter nesta sessão Linux:

```bash
# Envie por SSH usando a identidade dedicada do projeto:
cat /run/iphone-power-brightness-before > /sys/class/backlight/20e200080.backlight/brightness
```

### Resultado do intervalo com brilho reduzido

O monitor amostrou SSH/HTTP 11 vezes entre 13:33:02 e 13:38:03 UTC, com todas as respostas SSH válidas e HTTP 200. A última amostra teve uptime 923,76 s. O snapshot final foi salvo antes do reboot solicitado às **13:39:44 UTC**, com uptime **1024,05 s** (17 minutos e 4 segundos). Às **13:40:14 UTC**, iOS informou **100%**, carregamento e alimentação externa ativos; o baseline básico antes do boot era 98%.

A leitura detalhada mostra uma divergência que impede tratar o percentual como prova de carga líquida:

| Campo bruto iOS | 13:19:21 UTC, antes da preparação | 13:42:04 UTC, após o retorno |
|---|---:|---:|
| CurrentCapacity | 98 | 100 |
| AppleRawCurrentCapacity | 873 | 854 |
| AppleRawMaxCapacity | 884 | 877 |
| NominalChargeCapacity | 1146 | 1146 |
| InstantAmperage | 50 | 137 |
| Temperature | 3300 | 3460 |

Esses campos têm nomes/semânticas diferentes; a unidade e o significado exato dos valores AppleRaw, corrente e temperatura não foram validados aqui. O percentual subiu enquanto o valor bruto de carga caiu e o máximo bruto também mudou. A leitura detalhada anterior precede o baseline básico em mais de dois minutos; a posterior inclui tempo já carregando em iOS. A variação do medidor e o teto de 100% limitam a conclusão. Não calcular corrente média, mAh gastos ou economia do display com esses números.

**Conclusão:** um intervalo curto de disponibilidade foi comprovado, com temperatura física fria/morna relatada pelo operador; **carga sustentada segue sem comprovação (#2 aberta)**. A consulta `ioregplane IODeviceTree` não foi disponibilizada pelo serviço de diagnóstico; o binding A9 de carregador/gauge continua desconhecido. Os bindings SN2400 do fork A10 exigem regmap I2C, mux HDQ, parâmetros da bateria e limites de corrente, e o probe programa registradores: não é um módulo seguro para carregar às cegas neste N71.

### Avaliação de manutenção e próxima etapa

Os 1.462 ciclos, a capacidade nominal reduzida e a autonomia previamente relatada justificam avaliação técnica da bateria e do caminho de alimentação antes de uso sem supervisão. Uma bateria nova não acrescenta um driver Linux; o diagnóstico deve distinguir desgaste de corrente insuficiente/controle de carga. O estado físico aparentemente normal relatado pelo operador não resolve essa distinção.

Próximas provas necessárias: identificar chip/topologia e telemetria A9 a partir de fonte verificável ou medição física qualificada de carga líquida; obter uma comparação repetível sem teto de 100% nem troca de cabo; só então liberar #8. Enquanto essa parte depende de suporte/medição adicionais, os testes de recuperação e desenvolvimento de backups podem seguir localmente, sem prolongar o uso do telefone nem declarar #2 encerrada.

### Verificação e encerramento desta entrega parcial

17/17 testes passaram, cinco deles de diagnóstico; a mutação que substituiu a leitura real de MaxPower por `unavailable` foi rejeitada. Syntax/ShellCheck do diagnóstico e AST Python passaram; não há verificador de tipos configurado. Imagens, kernel, identidades e configuração USB permanecem os mesmos; o controle temporário de backlight perdeu efeito ao reboot. O telefone retornou ao iOS e os dados modificados foram guardados no Mac. A entrega amplia a medição e descarta uma hipótese; não encerra a validação de alimentação.

## Checagem reproduzível

Execute pela mesma identidade SSH já usada pelo projeto, a partir da raiz do repositório:

```bash
ssh -F /dev/null -i iphone-linux-tools/keys/iphone_ed25519 \
  -o UserKnownHostsFile=iphone-linux-tools/keys/known_hosts \
  -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
  -o BatchMode=yes -o ConnectTimeout=5 root@172.16.42.1 \
  'sh -s' < iphone-linux-tools/phone/diagnostics/power-check.sh
```

O script só lê sysfs; não instala nada no telefone. `unavailable` significa que não há leitura, nunca bateria vazia ou temperatura zero. Mesmo com sensor, `charging_validation=unverified` permanece: uma amostra isolada não valida o sistema de carga. Valores numéricos são os valores brutos do driver (tipicamente temperatura de zona em milésimos de °C; outros campos dependem da ABI/driver). Não tratar corrente USB externa como corrente líquida da bateria.

## Procedimento físico e critérios de conclusão

1. Observar temperatura da carcaça, elevação da tela, cheiro e desligamentos; registrar hora e estado. A observação anterior à atualização não substitui uma observação no Linux atual.
2. Manter os testes iniciais supervisionados, com ventilação, sem cobrir o aparelho e sem carga artificial de CPU enquanto alimentação estiver desconhecida. A Apple especifica ambiente de uso de 0–35 °C; essa faixa é do ambiente, não uma temperatura máxima genérica da bateria.
3. Interromper o uso/carregamento em caso de tela levantada/inchaço, cheiro, aquecimento anormal ou desligamentos repetidos. Solicitar avaliação física da bateria/conexões; não tentar compensar defeito por software.
4. Com o operador presente e snapshots salvos, registrar nível da bateria em iOS antes de um boot Linux e depois de intervalo supervisionado equivalente. Se não for possível ler o nível com confiança, usar diagnóstico físico qualificado. Uma queda apesar de USB alimentado é falha do requisito de carga sustentada; nível estável no limite de 100% é evidência inconclusiva de corrente líquida.
5. Confirmar repetibilidade e definir limites de uso. Um medidor USB pode demonstrar entrada de energia, mas isoladamente não comprova saúde da bateria, controle térmico ou carga líquida.

Pendente: medição repetível de carga sustentada e decisão de manutenção/substituição se necessária. As comparações antes/depois acima tiveram resultados divergentes. A recuperação da carga em iOS e a observação física inicial foram obtidas, mas não encerram #2. Não concluir por uptime, por ausência de sintomas relatados ou por uma leitura pontual. O teste prolongado #8 depende deste gate.

## Pilotos LAN posteriores — 2026-09-30

No piloto inicial de LAN, iOS informou 100% antes do Linux; após cerca de 28 minutos, snapshot e reboot, o operador confirmou tela de desbloqueio e aparelho sempre frio. O USB precisou de reconexão Lightning antes de ler novamente 100%. A leitura ocorreu depois de algum tempo em iOS; não isola carga durante Linux.

O piloto seguinte foi curto: novo init com loopback, restore, SSH/HTTP Windows e cleanup; uptime de 171,82 s imediatamente antes do snapshot final. Brilho reduzido para 256, sem carga artificial de CPU. iOS voltou a ser detectado por USB e informou 100% e carregamento ativo, partindo de 100%. O operador relatou frio/morno e pediu para cessar perguntas repetidas de temperatura; avisará caso esquente. Continuar supervisionando as etapas necessárias, sem tratar ausência de aviso como telemetria ou prova térmica.

Essas duas comparações no teto de 100% não comprovam corrente líquida nem resolvem a divergência dos campos brutos anteriores. #2/#8 permanecem abertas. Evidência sanitizada de rede: [lan-check.txt](evidence/lan-check.txt).

## Fontes

- [Apple: temperaturas e proteções em iOS](https://support.apple.com/en-ca/118431). A descrição das proteções do iOS não comprova que existam no kernel Linux experimental.
- [Apple: retenção de capacidade e ciclos](https://www.apple.com/br/batteries/service-and-recycling/).
- [Kernel HoolockLinux](https://github.com/HoolockLinux/linux): qualquer port de driver deve ser validado especificamente para N71/A9.

## Piloto da candidata e DNS — 2026-10-01 UTC

Antes do DFU, iOS informou 100%, `ExternalConnected=true` e `BatteryIsCharging=false`; em 100%, essa flag isolada não demonstra defeito de carregamento. O cabo USB-A traseiro foi mantido. No Linux: MaxPower 500 mA, bmAttributes 0x80, sensores de bateria/temperatura indisponíveis.

Após boot, restore, consultas DNS e snapshot verificado, reboot foi solicitado às 00:04:02 UTC, uptime 1128,59 s. O Mac ainda não redetectou iOS nas duas tentativas posteriores de leitura; reconexão Lightning foi solicitada, sem troca de cabo/porta. Medição posterior pendente. Nenhuma conclusão de carga sustentada ou condição térmica deriva deste piloto; #2/#8 permanecem abertas.

Correção do checkpoint: o pedido normal às 00:04:02 UTC não encerrou Linux. Após o operador informar console persistente, SSH e gadget Linux foram redetectados com uptime contínuo. O comando `sync; /bin/busybox reboot -f` foi solicitado às **00:24:02 UTC**, uptime **2327,83 s** (38 min 47 s); em seguida, gadget/SSH desapareceram, sem enumeração iOS. Foi solicitado fallback físico Power + Home até maçã. Assim, 18 min 48 s não é a duração efetiva deste Linux. Bateria posterior continua pendente; usar a duração total e o tempo até leitura, quando disponível. [Investigação #21](https://github.com/djalmajr/iphone6s-linux/issues/21).

Recuperação manual concluída: o operador informou iOS desbloqueado, e ProductType `iPhone8,1` foi confirmado por USB. Às **00:31:38 UTC**, iOS informou **93%**, `BatteryIsCharging=true`, `ExternalConnected=true`. Baseline pré-boot: 100%; Linux até o pedido direto: 2327,83 s; intervalo entre esse pedido e a leitura: aproximadamente 7 min 36 s, incluindo recuperação manual/iOS. A queda de sete pontos não isola corrente líquida durante Linux nem comprova carregamento sustentado; #2/#8 seguem abertas.

## Segundo piloto DNS

Às 00:35:10 UTC, iOS informou **94%**, carregamento/alimentação externos ativos (um ponto acima da leitura anterior), antes do novo DFU no mesmo USB-A traseiro. Durante a candidata restaurada, brilho foi reduzido para 256/2047. Restore, DNS USB/LAN Mac/Windows, parada e snapshot passaram. Última leitura Linux às 00:41:09 UTC: uptime 217,10 s, sync concluído; retorno físico solicitado. Bateria posterior pendente. A última leitura não determina o tempo final em Linux enquanto o retorno manual é aguardado.

Checkpoint final: Linux ainda estava ativo após a espera. Novo sync e reboot direto solicitados às **00:58:24 UTC**, uptime **1252,53 s** (20 min 52 s). iOS confirmado às 00:59:03 UTC; às **00:59:21 UTC**, leitura de **99%**, `BatteryIsCharging=true`, `ExternalConnected=true`. A sessão excedeu os cinco minutos previstos enquanto aguardava retorno. O aumento de 94% para 99% é favorável neste procedimento, mas inclui DFU/reboot e leitura já no iOS, sem medição de corrente; não resolve #2/#8 nem prova economia atribuível ao brilho. Intervenção manual ainda não esclarecida; não atribuir o retorno exclusivamente ao comando.

## Limite do driver Apple MFi — inspeção de fonte

A configuração efetiva da candidata 7.2.0 contém `CONFIG_APPLE_MFI_FASTCHARGE` desabilitado. O nome não identifica um carregador A9: a fonte registra um `usb_device_driver`, reconhece dispositivos Apple externos e envia uma requisição de controle USB para o dispositivo conectado. A interface `power_supply` expõe tipo de carga e escopo `DEVICE`, sem capacidade, tensão ou temperatura da bateria interna do computador onde o driver roda. [Fonte consultada, commit fixado](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/usb/misc/apple-mfi-fastcharge.c).

Inferência dessa inspeção: habilitar esse driver no kernel que roda no iPhone em modo periférico não implementa o lado receptor do protocolo nem o controle do PMIC/bateria A9. Não habilitamos a opção, não enviamos comandos de carga e não alteramos driver ou configuração USB do Mac. A investigação de carga sustentada #2 continua aberta; uma interface chamada `power_supply` ou uma opção chamada `fastcharge` não substitui a identificação do hardware e a medição apropriada.


## Mapa de energia e orçamento USB — 2026-10-02

A referência Apple N71, obtida offline conforme [Wi-Fi](WIFI.md), descreve medidor `gas-gauge,bq27540`/HDQ em UART5, carregador `charger,sn2400` em I2C1/tigris e PMIC `pmu,d2255` em I2C0. Isso identifica o caminho descrito na referência da placa; o compatible `gas-gauge,bq27540` não comprova o chip físico, sua revisão ou register map. Não habilita sensores nem valida calibração. Não assumir o perfil BQ27545 das implementações A10.

O [driver experimental SN2400](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/drivers/power/supply/apple_sn2400_charger.c) requer regmap do pai, mux HDQ, limite de entrada e parâmetros da bateria; o probe programa limites de carga. Inserir apenas um compatible no DT seria insuficiente e poderia acionar escritas com parâmetros indevidos. Próximo gate: validar UART5/HDQ/mux/regmap e parâmetros N71, inicialmente com telemetria somente leitura. Nenhuma escrita I2C/MMIO/PMIC foi feita.

No boot existente `7.2.0-iphone6s-source`, o diagnóstico reportou sensores de bateria/temperatura indisponíveis e **configfs MaxPower=2 mA**, bmAttributes=0x80. Esta leitura pertence a esta imagem; leituras históricas de 500 mA acima pertencem a outros pilotos. É orçamento declarado pelo gadget, não corrente medida, e não confirma o valor recebido pelo host nem a causa da descarga.

As duas fontes de init agora declaram **500 mA e bus-powered 0x80 antes de descobrir/bindar UDC**. A candidata separada altera somente init; preserva identidades e todo o prefixo loader/DTB/kernel. Hashes, testes e limites em [evidência](evidence/n71-board-map.json). Foi preparada offline, sem mudar o perfil ativo, desbindar USB ou reiniciar o telefone. **Não foi carregada no hardware.** Próximo boot agregado deve conferir configfs e descritor recebido pelo Mac; essa correção não controla SN2400 e não comprova carga sustentada.

```sh
export IPHONE_LINUX_PROFILE="$PWD/iphone-linux-tools/runtime/PERFIL-ANTERIOR/deployment.json"
python3 -B iphone-linux-tools/scripts/build/rebuild-usb-budget.py \
  --output-dir "$PWD/iphone-linux-tools/runtime/kernel-usb-budget-NOVO"
python3 -B iphone-linux-tools/tests/run_usb_budget_mutations.py
python3 -B iphone-linux-tools/tests/run_usb_budget_image_mutations.py
```

O builder aceita somente o init anterior conhecido e diretório novo privado; recusa âncoras divergentes ou orçamento já presente. Chaves do perfil são copiadas somente no Mac para a candidata privada, nunca para VM/GitHub. Não é atualizador genérico de qualquer initramfs. Fixtures executaram ambas as fontes de init e observaram valores antes da descoberta UDC: seis mutações por asserção no Mac/VM. Repack: cinco testes e quatro mutações por asserção no Mac/VM, delta exato e arquivos/metadados/identidades preservados. Gate físico #33 permanece aberto junto de #2/#8.


## UART5 preparada, HDQ ainda desativado — 2026-10-02

O incremento N71 descrito em [Wi-Fi](WIFI.md#topologia-n71-compilada--2026-10-02) compila UART5 com endereço/IRQ/provedores próprios e preserva a árvore funcional anterior. `status=disabled`; nenhum filho HDQ/gauge, pinmux ou driver foi ativado. [Evidência offline](evidence/n71-topology.json). Zero reinicializações ou escritas MMIO/I2C/PMIC; sensores/carga seguem sem prova.

A fonte [HDQ via UART do fork A10](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/drivers/w1/masters/w1-uart.c) usa serdev, 57.600 baud, dois stop bits, break e mux de propriedade da linha. Depende de APIs/temporização específicas do fork, não apenas de um nó UART. O [mux SN2400](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/drivers/mux/sn2400.c) seleciona o acesso AP escrevendo registradores e restaura o estado do carregador. Não é um caminho de leitura puramente passivo. A presença de um escravo W1 sintético nesse driver tampouco comprova resposta do gauge físico.

Próximo desenvolvimento: validar a função/pin routing UART5 N71, protocolo de propriedade do HDQ e register map real do gauge antes de integrar telemetria. Não copiar o GPIO173/pinmux A10 nem ativar SN2400 com limites de bateria presumidos. O compatible da referência não autoriza converter BQ27540 em BQ27545 no DT. #2/#8 continuam abertas; a candidata de orçamento USB #33 permanece separada e não foi bootada. Um boot futuro deve reunir provas úteis após revisão offline dos drivers, sem reiniciar apenas para confirmar novamente que não há sensores.

## Handshake HDQ N71 implementado, backend físico pendente

O consumidor Apple guarda `function-battery_swi_request` em+a0. Seu helper
de pedido0068d5568 envia comando1; a liberação0068d560c envia0. O comando2
pertence ao caminho de mudança de modo0068d5684. No provider SN2400,
HDQm1 chama setHDQInterfaceGated(1,0), HDQm0 chama(0,0), HDQm2 chama(0,1).
O caminho1 usa handshake sem escrita final06. A liberação depende também
de modo de software, máscaras em cache, status7 e da presença da função
`function-battery_alert`, armazenada no campo+b0;
não substituir esse fluxo por uma escrita06 universal.

`phone/kernel/n71-hdq-handshake.h` implementa a primitiva selecionada por
callbacks: escreve04 em1d, lê ACKbit5 e, se solicitado, escreve06. Os cem
polls/delays10ms limitam o orçamento nominal de espera a1s; não estabelecem
deadline das operações do backend. Erros interrompem a sequência. Uma
obrigação de cleanup é marcada **antes** da primeira escrita e permanece em
todos os resultados, inclusive sucesso ou escrita parcial; reentrada é
recusada. ACK e escrita aceita não significam restauração nem presença física
do gauge. Flags de sucesso anterior são limpas antes de uma nova tentativa.

Não há backend I2C/UART/PMIC associado ao header, probe de carregador,
alteração DT ou autoload. O caller futuro deverá validar cliente/placa,
serializar posse da linha e implementar liberação/cleanup qualificados e
verificados antes de limpar a pendência. Não executar essa primitiva no
aparelho sem esse adapter; callbacks sintéticos não provam carga ou leitura
de bateria. [Referência selecionada](evidence/n71-hdq-charger-reference.json).

```sh
python3 iphone-linux-tools/tests/run_n71_hdq_handshake_mutations.py
```

Baseline e15 mutações compiladas morreram por SIGABRT/asserção no Mac e
ARM64, incluindo registrador/valores/ACK, orçamento, I/O parcial, byte largo,
reentrada e flags obsoletas. Header também compilou como objeto no contexto
__KERNEL__/Werror da fonte preservada, sem carregar módulo. O CI executa o
runner em Ubuntu/macOS. Telemetria, pinmux UART5, arbitragem SN2400 e carga
sustentada permanecem pendentes; nenhum novo DFU nesta implementação.

A [seleção da liberação](N71_HDQ.md) agora distingue os quatro caminhos
mode/cache/alert/status com testes Mac/ARM64 e objeto kernel/Werror. Ela
calcula um plano sem executar I/O ou limpar a obrigação de cleanup.
O [bundle DART/serdev](N71_KERNEL_BUNDLE.md) prepara uma ABI distinta para
os dois stop bits necessários ao HDQ; sua prova atual é de fonte/objetos,
sem Image linkado ou deployment. Ambos são preparação de suporte, não
telemetria física nem controle de carga habilitado.

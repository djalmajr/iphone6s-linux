# Alimentação e bateria do iPhone 6s

Etapa [#2](https://github.com/djalmajr/iphone6s-linux/issues/2), iniciada em 2026-09-29. **Ainda não há comprovação de carga sustentada ou autorização técnica para uso contínuo sem supervisão.**

## Evidência atual

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

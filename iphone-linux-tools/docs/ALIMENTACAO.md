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

## Fontes

- [Apple: temperaturas e proteções em iOS](https://support.apple.com/en-ca/118431). A descrição das proteções do iOS não comprova que existam no kernel Linux experimental.
- [Apple: retenção de capacidade e ciclos](https://www.apple.com/br/batteries/service-and-recycling/).
- [Kernel HoolockLinux](https://github.com/HoolockLinux/linux): qualquer port de driver deve ser validado especificamente para N71/A9.

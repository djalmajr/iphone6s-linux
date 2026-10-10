# N71 — reserva temporária dos pinos I2C1

## Estado

O módulo `phone/kernel/i2c-pins/n71-i2c-pin-cycle.c` está qualificado offline e passou no aparelho em 2026-10-09, com o Image power2 preservado. Ele prepara o acesso ao controlador de carga, reservando e liberando descriptors GPIO115/114, sem selecionar mux, configurar direção/valor ou ativar I2C1.

Mac e Ubuntu ARM64 executaram o módulo real contra APIs kernel sintéticas: 107 cenários por plataforma e 22 mutações compiladas terminaram por SIGABRT com asserção. O build real produziu um módulo ELF64/AArch64 de 13.720 bytes, SHA256 `95bc260634fe6fa065e00f15553a4059fbc6acf95db2f2079cb4361b7b9a180e`, vermagic `7.2.0-iphone6s-dart-serdev-power2 SMP preempt mod_unload aarch64`. [Prova sanitizada](evidence/n71-i2c-pin-cycles.json), [plano e decisão](../.agents/plans/n71-i2c-pin-cycle.md), [energia/I2C1](N71_HDQ.md#i2c1-driver-existente-aquisição-ainda-não-qualificada).

## Contrato da fonte fixada

A referência usada é `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, com as seis patches já preservadas, SHA256 `6e1fccc1c936ee94c3f921ebe75e6dda4670c647f16b6c864df5475e20764657`.

| Fonte | Caminho relevante | Consequência |
| --- | --- | --- |
| `drivers/gpio/gpiolib.c:2395` | `gpiochip_generic_request` | Só pede o pinctrl quando existe gpio-range; request não seleciona necessariamente um mux. |
| `drivers/gpio/gpiolib.c:3356` e `:4987` | Configuração de flags e persistência antes da direção | ASIS evita a configuração de direção, mas seus outros efeitos precisam ser conferidos no provider. |
| `drivers/pinctrl/pinctrl-apple-gpio.c:191` e `:381` | Callbacks de request/free/set_config | Apple usa request/free genéricos; não fornece request/free de mux nem set_config. Nesse caminho ASIS não programa direção/valor/mux. |
| `drivers/pinctrl/pinctrl-apple-gpio.c:389` | Base GPIO `-1` |115/114 são offsets de hardware, nunca números GPIO globais. |
| `drivers/pinctrl/pinmux.c:145` | Decisão `gpio_ok` pelo mux_setting atual | `strict=true` não equivale a reserva exclusiva de mux em todos os estados. O módulo afirma somente ownership de descriptors gpiolib. |
| `drivers/pinctrl/pinmux.c:516` | Desativação de setting | Release não restaura automaticamente o registro físico antigo. Seleção de mux fica para outro gate. |
| `drivers/base/core.c:4359` | Root device temporário | Permite um consumidor GPIO sem instanciar plataforma/adapter I2C ou mudar propriedades OF. |

Os valores cache/hardware históricos `00076221` são uma observação de outra sessão. O módulo sempre exige leituras novas e coerentes, com máscara periph/input `0x260` igual a `0x220`, e preservação integral das palavras nas fases seguintes. O provider Apple usa REGCACHE_FLAT; por isso cada amostra compara cache, duas leituras bypassed e cache novamente.

Referências gerais: [GPIO consumer](https://docs.kernel.org/driver-api/gpio/consumer.html), [pinctrl](https://docs.kernel.org/driver-api/pin-control.html). A conclusão sobre ausência de programação é específica aos callbacks Apple da fonte fixada.

## Sequência do módulo

1. Exige `run=1`, board N71, I2C1 disabled sem filhos/platform/adapter e recurso exato. Confere GPIO Apple ativo, 208 pinos e recurso `20f100000/100000`.
2. Mantém `device_lock` do provider durante toda a operação. Identifica gpio_device por fwnode, valida label contra o provider e confirma que a resolução por label retorna o mesmo objeto.
3. Obtém amostra inicial dos dois pinos e recusa incoerência/mux fora do alvo. Registra um consumidor root único e uma tabela de lookup própria para offsets 115/114, flags padrão.
4. Pede os dois descriptors via `gpiod_get_index(..., GPIOD_ASIS)`, verifica identidade e offset, compara os registros enquanto a reserva está ativa, libera em ordem inversa e confere o readback posterior. Repete uma vez no mesmo insmod.
5. Remove tabela, consumidor e referências antes de soltar o provider. Em erro conserva o primeiro errno e registra separadamente erro de readback após liberação. Não tenta restaurar registradores inteiros por suposição.

Não há owner retido após o init: a carga serve como ciclo de aquisição/liberação. O mutex nunca é transferido entre tarefas ou comandos SSH. O módulo não fornece uma lease para outro driver.

## Reprodução offline

Na raiz do repositório:

```sh
python3 -B -m unittest discover -s iphone-linux-tools/tests -p test_n71_i2c_pin_cycle.py -v
python3 -m flake8 --select E9,F63,F7,F82 iphone-linux-tools/tests/test_n71_i2c_pin_cycle.py
```

Na VM ARM64, copiar os quatro inputs indicados no JSON para uma pasta dedicada, preservando seus caminhos. Executar o mesmo gate. Para o módulo, usar a fonte/build power2 já qualificada e a pasta copiada como M:

```sh
make -C "$N71_KERNEL_SOURCE" O="$N71_KERNEL_BUILD" \
  M="$N71_PIN_MODULE_DIR" \
  KBUILD_EXTRA_SYMBOLS="$N71_KERNEL_BUILD/vmlinux.symvers" -j2 modules
modinfo -F vermagic "$N71_PIN_MODULE_DIR/n71-i2c-pin-cycle.ko"
readelf -h "$N71_PIN_MODULE_DIR/n71-i2c-pin-cycle.ko"
nm -u "$N71_PIN_MODULE_DIR/n71-i2c-pin-cycle.ko"
```

O build de Image preservado não tem `Module.symvers` agregado, gerando aviso genérico do modpost. `KBUILD_EXTRA_SYMBOLS` forneceu o vmlinux.symvers correto; todos os 39 imports foram conferidos individualmente contra seus exports, sem ausências. Não foi usado KBUILD_MODPOST_WARN. Fonte, patch, configuração, Image e exports permaneceram iguais antes/depois. AST e Flake8 fatal passaram; não há type checker Python configurado.

O gate integra a descoberta `test_*.py` da CI Ubuntu/macOS. As duas execuções do head exato `ba9473c` concluíram com sucesso, com seis jobs aprovados. Os quatro logs de fonte confirmaram a execução do gate novo, 107 cenários/22 mutações por job. [Prova terminal da CI](evidence/n71-i2c-pin-cycles-ci.json). CI verifica software, sem acesso ao iPhone.

## Primeiro teste físico agrupado — 2026-10-09

Um DFU e um boot reuniram restore, diagnóstico IRQ/IOMMU, recuperação dos recursos, ciclos GPIO e serviços. O módulo foi transferido por SSH após a limpeza PCIe/REG_ON, sem outro reboot. Os dois ciclos retornaram `error=0 cleanup-readback-error=0 descriptors-released=1`; o resumo registrou pinos115/114, baseline nova `00076221,00076221` e `unchanged=1`. O unload, ausência do módulo/consumidor e remoção dos arquivos próprios passaram. SSH/Bash/HTTP permaneceram funcionais. [Prova física sanitizada](evidence/n71-iommu-pins-physical.json).

O snapshot e sync passaram antes do reboot. O retorno automático não foi confirmado por USB no prazo; o operador confirmou a tela de bloqueio após reinicialização física, sem PIN. O aparelho permanece no iOS para recarga durante desenvolvimento offline. A associação IOMMU foi recusada com ENODEV antes de publicar PCI; isso não impediu os ciclos GPIO depois da recuperação verificada na mesma sessão.

## Reprodução de uma coleta física

O módulo pode ser transferido por SSH ao Linux power2 existente: não exige Image/DTB novo nem DFU adicional. A sessão agrupada deverá conferir perfil/kernel/módulo por hashes, ausência de módulo/consumidor anterior e I2C1 desativado; colher dmesg somente em log privado; executar um insmod explícito `run=1`; exigir dois registros `N71_I2C_PIN_CYCLE error=0 cleanup-readback-error=0` e um `N71_I2C_PIN_CYCLES_OK`; descarregar e conferir ausência do módulo/consumidor, SSH e HTTP. Em recusa/drift, registrar os dois errnos e preservar a evidência antes da análise.

Reserva GPIO não comprova exclusividade de mux, comportamento elétrico, aquisição do adapter/IRQ/clock, register map SN2400, leitura HDQ/gauge ou corrente líquida de carga. Wi-Fi e carga Linux continuam nas [issues9](https://github.com/djalmajr/iphone6s-linux/issues/9) e [2](https://github.com/djalmajr/iphone6s-linux/issues/2). Durante preparação offline, a recarga depende do iOS.

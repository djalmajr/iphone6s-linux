# Ciclo temporário dos descriptors I2C1 — #2

## Contexto

Demanda contínua já autorizada: Wi-Fi e alimentação N71, com o mínimo de DFUs. O Image power2 e o ciclo genpd já estão preservados. Ainda não há carga Linux ou gauge comprovados. A fonte fixada `958481f`, patch `6e1fccc1…`, confirma GPIO114/115, base dinâmica e callbacks Apple sem request/free de mux ou set_config. `GPIOD_ASIS` passa pelo request e por configuração de persistência; portanto a ausência de escrita depende desse provider, não apenas do nome da flag.

## D1. Reservar descriptors antes de selecionar o mux

- **Decisão:** implementar dois ciclos síncronos de reserva ASIS, leitura e liberação. Não selecionar pinctrl, configurar direção/valor ou ativar I2C1 neste módulo.
- **Por quê:** GPIO ownership e mux ownership seguem caminhos distintos. O pinctrl atual admite sobreposição em estados GPIO/sem mux_setting; este primeiro gate comprovará somente reserva gpiolib e preservação dos registros, sem afirmar exclusividade de mux ou restauração elétrica geral.
- **Alternativas:** selecionar default junto com ASIS exige qualificar outra obrigação de cleanup; `gpiochip_request_own_desc` pertence ao provider e não mantém sua referência de módulo; criar propriedade OF temporária deixa deadprops. Uma tabela de lookup própria usa a API de consumidor e pode ser removida integralmente.
- **Reverter:** baixo; novo módulo externo opt-in, sem alteração do Image, DTB ou módulos existentes.
- **Status:** módulo/fixtures qualificados offline; teste no aparelho pendente.

## Arquivos

- `phone/kernel/i2c-pins/Makefile`: build externo isolado com Werror.
- `phone/kernel/i2c-pins/n71-i2c-pin-cycle.c`: preflight, consumidor root temporário, lookup, reserva, amostragem e cleanup.
- `tests/n71_i2c_pin_cycle.c`: executar o módulo real com contratos sintéticos de OF/device/GPIO/regmap e falhas de aquisição/leitura.
- `tests/test_n71_i2c_pin_cycle.py`: compilar baseline/mutações; somente SIGABRT com asserção conta como kill.

## Contrato

Exigir `run=1`, N71, I2C1 disabled sem filhos/platform/adapter, GPIO Apple ativo com recurso exato, 208 pinos e provider ligado. Manter `device_lock` do provider durante todo o ciclo; nunca atravessar tarefas/SSH com esse mutex retido. Identificar gpio_device pelo fwnode e conferir que seu label resolve ao mesmo objeto antes do lookup. Consumidor root único, sem of_node, bus ou driver; tabela exclusivamente dele com offsets de hardware115/114 e flags padrão. Descriptors recebidos devem ser os objetos esperados, com esses offsets.

Ler cache, hardware duas vezes, cache, de ambos os pinos em cada fase. Antes de reservar, exigir coerência integral e máscara periph/input `0x260` igual a `0x220`. Não presumir que o valor histórico `00076221` permanece atual. Durante a reserva e após liberação, exigir palavras idênticas às iniciais. Liberar descriptors em ordem inversa em qualquer erro; remover lookup, consumidor e referências antes de devolver o controle. Drift/read error é falha observada, sem restauração cega de registradores.

## Tarefas

- [x] Conferir fonte primária, flags, callbacks e exports no build power2 preservado.
- [x] Implementar módulo e fixtures com falhas de escopo, referência, aquisição e leitura.
- [x] Compilar e executar cenários/mutações no Mac e Ubuntu ARM64; compilar módulo real na VM, sem alterar fonte/config/Image/exports.
- [ ] Documentar hashes, comandos, limites e integrar o gate à CI.
- [ ] Carregar por SSH em sessão física agrupada, preservar serviços/snapshot e registrar somente prova sanitizada.

## Verificação

Fixtures executam o código real, mas os providers são sintéticos: não comprovam funcionamento elétrico, pinctrl ownership, I2C, carregador ou corrente líquida. Build real deve terminar sem imports ausentes, sem usar KBUILD_MODPOST_WARN, com vermagic power2 e exports compatíveis. Public tree/diff/JSON/lint antes de publicação na branch autorizada. O módulo pode ser transferido no mesmo boot; nenhuma reinicialização é necessária apenas para preparar/testar sua fonte.

### Resultado offline — 2026-10-07

Mac/Ubuntu ARM64: um gate Python por plataforma executou107 cenários nativos e22 mutações compiladas, todas terminando por SIGABRT com asserção. Falhas iniciais da fixture (errno EUCLEAN ausente no Darwin; descriptor inesperado com offset também inesperado) foram corrigidas antes desta qualificação. O segundo caso agora oferece outro provider com o mesmo offset, distinguindo identidade de número do pino.

Build real Werror/modpost na fonte/build power2 preservados: módulo13.720 bytes, SHA256 `95bc260634fe6fa065e00f15553a4059fbc6acf95db2f2079cb4361b7b9a180e`, vermagic `7.2.0-iphone6s-dart-serdev-power2 SMP preempt mod_unload aarch64`. Quatro inputs idênticos nas duas máquinas; fonte/patch/config/Image/exports conferidos antes/depois. AST e Flake8 fatal passaram; não há type checker Python configurado. Não foi carregado no telefone.

O build de Image não tem `Module.symvers` agregado e modpost emitiu o aviso genérico correspondente. O comando fornece o `vmlinux.symvers` preservado via KBUILD_EXTRA_SYMBOLS;39 imports do ELF64/AArch64 foram conferidos individualmente contra ele, sem ausências. Não foi usado KBUILD_MODPOST_WARN nem criado/copied arquivo no build preservado para ocultar o aviso.

Referências: [GPIO consumer](https://docs.kernel.org/driver-api/gpio/consumer.html), fonte local fixada `drivers/gpio/gpiolib.c`, `drivers/pinctrl/pinmux.c`, `drivers/pinctrl/pinctrl-apple-gpio.c` e `drivers/base/core.c`. A documentação geral não substitui a auditoria dos callbacks Apple.

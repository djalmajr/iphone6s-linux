# Telemetria HDQ do N71 — implementação em curso

Pendência [#2](https://github.com/djalmajr/iphone6s-linux/issues/2).
O codec já tem gates Mac, ARM64 e contexto kernel. UART, mux compartilhado,
identificação do gauge e unidades físicas ainda não foram validados.

## Referência verificável

Usamos o kernel Apple N71 como dados, obtido pelo
[procedimento fixado](N71_REFERENCIA.md). O SHA do binário decodificado foi
recalculado e coincide com o registro anterior. Dumps e disassembly continuam
privados; apenas [fatos selecionados](evidence/n71-hdq-charger-reference.json)
são publicados. Endereços de funções pertencem exclusivamente a essa versão.

`setHDQInterfaceGated` escolhe máscaras 40/60 conforme um campo de software
em object+d4. A rotina `_chargerModeGated` aceita modos 0/1 e escreve esse
campo: ele não é uma leitura de revisão do chip.

`enableEvents` altera três máscaras em cache e as escreve nos registros 1–3
do SN2400. O segundo argumento corresponde ao registro2. Habilitar eventos
limpa bits da máscara; desabilitar os repõe. Portanto, escrever 40/60 no
registro0 como suposto controle de carga não reproduz a sequência observada.
Mesmo uma futura alteração correta de máscara deve preservar o estado herdado
e tratar IRQs e outros donos. Ainda falta confirmar efeitos de leitura de status.

A primitiva HDQ escreve4 no registro1d, espera bit5 com deadline de um segundo
e sleep10ms, e opcionalmente escreve6. Erro de leitura tenta escrever0; o ramo
de timeout e o erro da primeira escrita não restauram diretamente nessa
primitiva. Isso identifica operações da referência, **não** uma sequência
reversível já pronta para o nosso driver. Uma implementação deve contabilizar
escrita parcial e preservar/restaurar o estado conhecido, sem presumir que0
sempre seja o valor correto de retorno.

## Recursos e próximo desenvolvimento

A referência runtime liga o HDQ a UART5 (20a0d4000/IRQ197), GPIO2/flags102 e
ao provider tigris/SN2400 no endereço75. O nome bq27540 no ADT não identifica
por si só a revisão ou o register map da bateria instalada.

Na cadeia DTS Linux fixada, I2C1 (20a111000) está desativado e o include da
placa habilita I2C0. UART5 só existe no fragmento do projeto, desativado.
Habilitar um driver genérico não preenche os bindings e a sequência do mux.

Próximos gates, agrupados com Wi-Fi quando houver sessão física:

1. Inventário somente leitura dos nós/status e donos Linux. Sem varrer I2C,
   ler registradores de status por suposição ou transmitir no UART.
2. Confirmar pinmux GPIO2, clocks e propriedade da linha/cliente SN2400;
   implementar transação limitada e reversível, separada dos limites de carga.
3. Identificar ABI/revisão antes de interpretar tensão, corrente, temperatura
   e capacidade. RespostaFFFF não vale como prova de presença.
4. Obter leituras físicas coerentes/repetíveis e corrente líquida qualificada;
   somente então avaliar carga sustentada e operação contínua.

Atualizações de módulos e userspace devem usar SSH no mesmo boot. Alteração
indispensável de kernel/DT exige candidata separada e pode exigir novo DFU;
agregar esses deltas antes de pedir a ação física. Nenhuma nova leitura de
sensor ou escrita de carregador foi executada para preparar este documento.

## Inventário físico agrupado — 2026-10-02

A leitura do DT no Linux7.2 confirmou status disabled para I2C1 e UART5.
Não houve varredura I2C, acesso ao SN2400, transmissão UART ou gauge read.
O PMIC no I2C0 tem MFD/RTC/NVMEM ativos; isso não qualifica o carregador75 do
outro barramento. power_supply continua vazio. Esses resultados restringem a
próxima candidata; não representam falha do codec nem prova de sensor.
Ver [sessão agrupada](evidence/n71-reg-on-first-physical.json).

## GPIO2/config102 — referência confirmada, sem escrita física

O provider GPIO do N71 usa `AppleS5L8960XGPIOIC`, identificado pelo cstring,
metaclass e vtable do binário fixado. A primeira classe encontrada no kext
pertence a T8006; não foi usada para inferir o comportamento N71.

`AppleARMGPIOFunction` copia o pacote ADT e, na inicialização, chama sua
função com argumentos nulos. Para config102, o byte de modo vale2 e o byte
de polaridade vale1. A chamada escolhe a rotina de modo, sem escrever um
nível de saída como faria para modo1. O modo2 Apple não é o seletor2 Linux.

O setter N71 usa a máscara270 no registrador por pino, com stride4. Para
GPIO2, offset08: valor220 quando a propriedade `glitchless` está ausente ou
zero; valor210 quando ela é nãozero. A referência runtime coletada tem a
propriedade ausente no nó GPIO phandle1e. A escrita preserva os outros bits:
`(old & ~mask) | (value & mask)`. O caminho normal corresponde ao seletor
periférico1 e input-enable; também limpa bit4, que a rotina genérica de
pinmux Linux não inclui em sua máscara. A variante glitchless não deve ser
substituída pelo seletor normal por conveniência.

O [contrato puro](../phone/kernel/n71-hdq-pinmux.h) só calcula offset,
máscara e valor para pin2/config102 e variante conhecida. Não acessa MMIO
nem adquire a linha. Dez mutações compiladas verificam pin/config inválidos,
variante, stride, função, input-enable e bits preservados no Mac e ARM64.
O header também compilou em contexto kernel com Werror na VM isolada.

Antes do adapter físico, ainda faltam aquisição da linha compartilhada,
snapshot/readback/restore da máscara qualificada, coordenação UART/clocks
e cleanup do SN2400. Nenhum GPIO, UART ou carregador foi alterado nesta fase.

Reprodução dos testes:

```sh
python3 tests/run_n71_hdq_pinmux_mutations.py
```

Conferência privada dos trechos da referência (sem executar o firmware):

```sh
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

evidence = json.loads(Path('docs/evidence/n71-hdq-charger-reference.json').read_text())
raw = Path('runtime/n71-driver-reference-20261002/kernelcache.n71.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest() == evidence['decoded_kernel_sha256']
for window in evidence['gpio2_reference']['verification_windows']:
    start, size = window['file_offset'], window['size']
    assert 0 <= start < len(raw) and start + size <= len(raw)
    assert hashlib.sha256(raw[start:start + size]).hexdigest() == window['sha256']
print('N71_GPIO2_REFERENCE_WINDOWS_OK')
PY
```

Os hashes confirmam os trechos analisados; não substituem a análise das
instruções nem comprovam comportamento elétrico no aparelho.

## Redução de reinicializações — recursos já presentes

A configuração preservada7.2 inclui `CONFIG_OF_DYNAMIC=y`,
`CONFIG_OF_OVERLAY=y` e `CONFIG_CONFIGFS_FS=y`. A fonte fixada exporta
`of_overlay_fdt_apply` e `of_overlay_remove` para módulos GPL. A existência
de configfs não comprova um carregador de overlays por arquivos; não foi
encontrada uma opção `CONFIG_OF_CONFIGFS` nessa configuração.

Essas APIs oferecem um caminho a investigar para habilitar recursos no
mesmo boot, por módulo próprio e alvo estritamente qualificado. Remover
um overlay não comprova restauração elétrica: os callbacks de driver e
propriedade dos pinos/clocks ainda precisam ser delimitados. Não foi
aplicado overlay no aparelho. Manter UART5/I2C1 desativados até qualificar
cleanup, em vez de habilitar nós pela presença da API.

Na cadeia `s8000.dtsi` → `s800-0-3.dtsi` → `s800-0-3-pmgr.dtsi`,
`ps_uart5` usa reg80200 e depende de `ps_sio_p`; `ps_i2c1` usa reg801a0
com o mesmo pai. O ADT runtime declara `clock-gates=0x55` para UART5
(**85 decimal**, não55 decimal). O ID do gate não foi convertido em
offset por aritmética presumida. O papel isolado do bit4 na máscara270
também não foi classificado como direção GPIO genérica.

## Adapter serdev 8N2 — compilado, ainda sem integração

A API serdev da fonte fixada não tem operação para selecionar stop bits.
A referência N71 exige57600/8N2. O [patch](../phone/kernel/patches/0002-serdev-stop-bits.patch)
adiciona `serdev_device_set_stop_bits`, um callback de controlador e seu
registro no adapter TTY. `CSTOPB` representa dois stop bits na
[API serial documentada pelo kernel](https://www.kernel.org/doc/html/latest/driver-api/serial/driver.html).
Não há chamada automática, cliente novo ou alteração de porta no probe.

A operação aceita apenas1/2, recusa callback ausente ou TTY fechado e
propaga erro do backend. O adapter copia termios, altera somenteCSTOPB
e confere o estado aceito pelo TTY. O teste verifica os campos e caracteres
de controle explícitos, sem depender de padding da estrutura C. A confirmação
do TTY não é uma medição da forma de onda; em erro, o chamador precisa
tratar estado possivelmente alterado, sem presumir restauração automática.

Os testes compilam as funções e o registro de callback adicionados pelo
patch real, com backend TTY sintético. Mac e ARM64 passaram baseline e12
mutações compiladas por SIGABRT/asserção, incluindo callback não registrado,
contagem encaminhada incorreta, readback rejeitado e erro engolido. Checkpatch
passou com0erros/0avisos; `core.o` e `serdev-ttyport.o` compilaram comWerror
no worktree isolado. [Hashes e escopo](evidence/n71-serdev-stop-bits.json).

```sh
python3 tests/run_n71_serdev_stop_bits_mutations.py
```

A build realizada usa:

- Fonte preservada: `/home/ubuntu/kernel-n71-source-20261001`, commit958481f.
- Worktree próprio: `/home/ubuntu/kernel-n71-serdev-source-20261002`.
- Saída separada: `/home/ubuntu/kernel-n71-serdev-build-20261002`.
- Patch aplicado somente após `git apply --check`; três arquivos exatos
  alterados, hashes publicados e diff vazio na fonte preservada.
- Configuração inicial copiada de `kernel-n71-build-20261001-v2/.config`,
  seguida de `olddefconfig` e compilação dos objetos alterados.

Comando de compilação reproduzível nesse worktree:

```sh
make -C /home/ubuntu/kernel-n71-serdev-source-20261002 \
  O=/home/ubuntu/kernel-n71-serdev-build-20261002 ARCH=arm64 -j2 \
  KCFLAGS=-Werror drivers/tty/serdev/core.o drivers/tty/serdev/serdev-ttyport.o
```

Não houve link de Image, modpost ou boot deste patch. Ele ainda não integra
o helper de patchset DART nem um perfil de deployment. Como muda o layout
das operações serdev, a futura integração exige recompilar kernel e módulos
e usar identificação de kernel distinta. Não carregar esse delta como módulo
na imagem atual. A receita de [build fonte](KERNEL-SOURCE-BUILD.md) continua
como base para preparar a candidata agregada após qualificar mux/clocks e
releaseSN2400. UART5/I2C1 seguem desativados; gauge e carga sem prova física.

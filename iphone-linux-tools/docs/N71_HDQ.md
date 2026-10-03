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

A [candidata DART+serdev](N71_KERNEL_BUNDLE.md) já tem aplicação de fonte e
três objetos verificados num worktree/output próprios, com identidade distinta.
Não houve Image/modpost/perfil ou boot do conjunto; o helper legado permanece
separado. Essa preparação reúne deltas para um futuro teste físico único.

## Liberação HDQ — seleção qualificada, backend pendente

O campo object+b0 da referência guarda o resultado da busca por
`function-battery_alert`, na inicialização005d674ac..005d674bc. O CString
fixado em0054f73a9 confirma o nome; não tratamos esse campo como um
ponteiro de controlador inferido. A presença do resultado também não prova
que uma função física esteja registrada no nosso Linux.

Para o pedido padrão command0/request0, o fluxo seleciona:

| Modo software | Cache+b8 | Alert presente | Status7/bit7 | Ação de referência |
| --- | --- | --- | --- | --- |
| 1 | zero | qualquer | qualquer | Sem handshake |
| 1 | nãozero | qualquer | qualquer | Handshake sem escrita final06 |
| 0 | qualquer | sim | limpo | Handshake com escrita final06 |
| 0 | qualquer | demais casos | demais casos | Escrita00 em1d |

Ao desabilitar os eventos, o fluxo usa o cache+b8 com bit40 removido
quando há resultado da busca `battery_alert`; sem esse resultado, mantém
a máscara. Essa operação usa `enableEvents` e suas máscaras em cache,
não uma escrita direta de uma constante no registrador0 do carregador.
O modo é software, não revisão física do chip.

O [seletor](../phone/kernel/n71-hdq-release-plan.h) calcula somente ação e
bits de eventos, sem callback ou acesso ao aparelho. Exige status marcado
válido, bytes limitados, modo0/1 e presença0/1; uma entrada recusada não
altera a saída. Não executa o plano, não limpa a pendência do handshake e
não afirma restauração. O adapter ainda precisa qualificar efeitos das
leituras de status, propriedade de IRQs/máscaras, mux e cleanup verificado.

```sh
python3 tests/run_n71_hdq_release_plan_mutations.py
```

O teste cobre todas as combinações de modo0/1, máscara0..255, presença0/1
e status0..255. Mac/ARM64 passaram baseline e14 mutações por asserção;
o header compilou em contexto kernel comWerror na VM isolada. Isso não
constitui prova elétrica de HDQ, bateria, carga ou restauração.

Os sete trechos analisados têm offsets/tamanhos/hashes em `release_reference`
dos [fatos selecionados](evidence/n71-hdq-charger-reference.json). Para
reproduzir a conferência, use o comando de janelas acima com
`evidence['release_reference']['verification_windows']`. O binário privado
não é publicado nem executado.

## Observador GPIO2 do bundle — sem escrita física

O provider da fonte fixada usa `REGCACHE_FLAT`: uma leitura normal de regmap
pode vir do cache. Sua operação de mux usa máscara260; a referência N71
para GPIO2 também inclui bit4, com máscara270. Não substituir essas máscaras
por uma escrita MMIO direta: ela contornaria o owner e poderia divergir do
cache. A [documentação pinctrl](https://docs.kernel.org/driver-api/pin-control.html#pin-control-interaction-with-the-gpio-subsystem) distingue aquisição
de GPIO e seleção de função periférica; GPIO solicitado não é autorização
para tomar um mux UART mantido por outro consumidor.

O [observador](../phone/kernel/n71-hdq-gpio-observe.c) é um módulo externo
com `run=1` explícito. Confere N71, caminho do provider, compatible, recurso
MMIO, driver existente e regmap32/stride4. Mantém device_lock durante duas
leituras normais e duas leituras bypassed do offset08 via API regmap. Essa
API preserva/restaura flags de cache sob o lock interno. Não chama request
GPIO, pinctrl, set direction, escreve registrador ou aciona UART/carregador.
Não reconstrói a estrutura privada do driver nem faz rebind.

O log separa os quatro resultados e compara somente a máscara270 entre
as duas amostras físicas e a leitura normal final. `stable=1` descreve
aquelas duas amostras; não mede propriedade da linha, nível elétrico, rail
ou capacidade da bateria. Unload não precisa restaurar mux, pois o módulo
não adquiriu/configurou a linha. Esse observador prepara o próximo backend,
sem substituir os gates de SN2400, UART, cleanup e identificação do gauge.

[Hashes, APIs e build](evidence/n71-hdq-gpio-observer.json): compilou com
Werror/modpost contra os exports do bundle existente, ELF relocável AArch64
e vermagic `7.2.0-iphone6s-dart-serdev1`. O hash foi recalculado no Mac;
Image e configuração foram preservados. O arquivo permanece privado em
`runtime/n71-hdq-gpio-observer-build-20261003/n71-hdq-gpio-observe.ko`.

Para reproduzir, copie as fontes públicas de `phone/kernel` para novo
diretório M na VM dedicada e execute a receita de módulos externos do
[bundle](N71_KERNEL_BUNDLE.md), com seu `vmlinux.symvers`. Não suprimir
erros de símbolos. Depois valide ELF/vermagic/hash e transfira o observador
via SSH para `/run/` no mesmo boot do bundle; confira SHA no destino antes
de `insmod /run/n71-hdq-gpio-observe.ko run=1`. Exigir log
`N71_HDQ_GPIO2` sem erro, executar `rmmod n71_hdq_gpio_observe` e conferir
o marcador `N71_HDQ_GPIO2_UNLOADED` e ausência do módulo em sysfs. Logs
completos e observações do aparelho permanecem privados.

Foi transferido e carregado no mesmo boot do teste PCIe do bundle. As quatro
leituras retornaram00072220; hardware mascarado270=220, stable1/cache-matches1.
Unload e ausência do módulo foram confirmados. [Evidência física selecionada](evidence/n71-bundle-first-physical.json).
Isso qualifica somente aquelas amostras; não demonstra owner, UART, handshake
SN2400 ou sensor. Continua sem autoload no initramfs e sem alterar os dois
módulos selecionados do experimento PCIe.

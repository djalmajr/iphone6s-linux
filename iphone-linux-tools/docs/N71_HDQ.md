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

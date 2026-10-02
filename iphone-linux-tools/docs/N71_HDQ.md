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

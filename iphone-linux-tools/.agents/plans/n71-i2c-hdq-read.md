# Leitura limitada do controle HDQ por I2C1 — #2

## Contexto

Owner/configure qualificados, commits d226603/45a3aa5. Próxima etapa da demanda aprovada: transporte real por polling, antes de UART/gauge. Não acessar o telefone nem pedir confirmações de rotina durante esta preparação. Fonte PASemi preservada958481f, `i2c-pasemi-core.c:91–119,122–190,286–295`: byte-data lê com START75/write, comando, repeated START75/read e READ1/STOP. SMSTA/XEN é uma indicação consumível, limpa por escrita; não inventar restauração desse evento histórico.

## Arquivos e fases

1. Até cinco executáveis: modificar `phone/kernel/n71-i2c-controller.h` e `tests/test_n71_i2c_controller.py`; criar `phone/kernel/n71-i2c-hdq-read.h`, `tests/n71_i2c_hdq_read.c` e `tests/test_n71_i2c_hdq_read.py`. Reusar a fixture OF/clock/MMIO de `tests/n71_i2c_controller.c` sem alterar esse arquivo. Verificar os gates afetados Mac/ARM64 e o build kernel conjunto antes da integração.
2. Caller em fase própria de quatro executáveis: `phone/kernel/n71-i2c-power-diagnostic.c`, fixture e runner existentes, novo `phone/kernel/n71-i2c-configuration.h`. Extrair o lifecycle da configuração para esse header, com objeto de request apontando para os estados existentes; manter o módulo abaixo de300linhas. Novo action `read-hdq-control` deve adquirir pinos/genpd/controlador, ler somente75:1d, limpar transporte→controlador→pinos→genpd. Retenção de módulo em falha, init/default sem transferência. Nenhum scanner, adapter ou cliente de charger.
3. Corrigir a fixture sintética de runtime em `tests/test_n71_driver_runtime_build.py`: conferir os bytes/hash dos inputs copiados no sandbox de teste em vez de reutilizar os hashes históricos da cópia de evidência. Manter guards e evidências de produção intactos. A CIe09bc845 falhou por esse acoplamento depois da evolução do caller I2C; verificar os oito módulos Python afetados, inclusive mutações, Mac/ARM64.
4. Documentação/prova sanitizada separada. Preparar UART5/propriedade HDQ/gauge antes de uma única coleta física agrupada; não pedir DFU apenas para este transporte. Seleção do caller Wi-Fi real continua exigindo seu snapshot qualificado; uma fixture atualizada não autoriza misturar fonte nova e binário antigo.

## Contrato

Objeto de request carrega ownership e controlador já adquirido; função recusa power/clock/MMIO/pinos ou consumer incompatíveis antes de FIFO. Estado de transporte conserva identidade do controlador e obrigação antes da primeira escrita. O controlador recusa release enquanto transfer_pending estiver verdadeiro.

Somente endereço7bit75 e registro1d, sem parâmetros para escolher outro alvo. Sequência de quatro comandos MTXFIFO `1ea,1d,1eb,601`, somente um byte MRXFIFO. Não escrever valor de registro do SN2400, inclusive04/06, nem ler status7/máscaras/revisão por suposição. O comando de seleção1d também é uma escrita no barramento; não apresentar o acesso como passivo ou como identificação do chip/gauge.

Polling nominal de100 esperas1ms, não garantia contra MMIO bloqueado. Detectar allones, NACK, arbitration, timeout, jam/busy e RX vazio/fora da máscara. Saída do chamador só muda depois de leitura e cleanup completos. Preservar erro primário e erro de cleanup separados.

Cleanup mantém clock/pinos/power/MMIO e aguarda XIP/JAM ausentes. Confirmar REV2, IMASK0, XFSTA0 e CTL0f/070f; recusar campos SMSTA estrangeiros. Para erro/dados residuais/TX não vazio, resetar FIFO com CTL070f conforme a fonte, mantendo obrigação até readback. Acknowledge somente flags documentadas XEN/JMD/MTO/MTA/MTN/TOM; não reproduzir evento histórico XEN. A baseline original continua intacta; status_acknowledged registra que o aceite final de SMSTA corresponde à baseline com XEN removido. Sem transferência, release continua exigindo as cinco words exatas. Falha retém obrigação para retry no mesmo boot.

## Tarefas

- [x] Conferir fonte primária, comandos, status consumível e limite do registro1d.
- [x] Implementar leitura/recovery limitada e guard de release no controlador.
- [x] Verificar regressão do controlador e contratos/mutações de transporte no Mac/ARM64; build kernel Werror/imports, AST/lint/checkpatch.
- [x] Integrar action operacional e retenção em cleanup pendente.
- [x] Corrigir o snapshot sintético dos testes de runtime e verificar a matriz afetada.
- [x] Versionar reprodução/evidência sanitizada para publicação na branch; manter issue/goal abertos.
- [ ] Completar UART/gauge e realizar prova física agrupada; nenhum gate offline comprova carga.

## Verificação

Testes executam headers reais com MMIO e APIs kernel sintéticos. Mutação só conta se compilar e falhar por SIGABRT/asserção. Exercitar resposta0/ff, endereço/comando/count/STOP, falhas de owners, timeout/NACK/RX, saída intacta em erro, retry e impossibilidade de release durante cleanup pendente. Reusar gates de pins/genpd inalterados. Conferir inputs iguais, fonte/config/Image/exports preservados e imports reais. Não há type checker Python configurado; AST/fatal lint não substituem um.

## Resultado — 2026-10-10

Transporte3e0a597:38cenários/12mutações por plataforma, mais regressão controlador50/15. Caller93da4be:77/23 por plataforma, módulo operacional51.120bytes/79imports. Werror/modpost/ELF/vermagic/checkpatch0/0/0 e AST/lint fatal passaram; não há type checker Python. Inputs8/14 idênticos nas máquinas e atuais, fonte/config/Image/exports preservados. Gates inalterados de owner/genpd reutilizados.

Fixture1777a93: oito módulos Python,56testes/65mutações únicas por AssertionError em Mac282.041s e ARM248.618s. Nenhum selector ou registro de produção foi alterado. A CIe09bc845 original terminou failure por hash/bytes históricos misturados à fonte atual; não é prova verde. A próxima publicação terá handles próprios, sem cancelar/relançar runs antigos.

[Reprodução](../../docs/N71_I2C_HDQ_READ.md) e [evidência](../../docs/evidence/n71-i2c-hdq-read-qualified.json). [#43](https://github.com/djalmajr/iphone6s-linux/issues/43) registra a necessidade de snapshot/requalificação do caller Wi-Fi real antes da coleta. Priores etapas continuam abertas: UART5/propriedade HDQ, ABI/revisão/unidades do gauge, corrente líquida/carga sustentada e Wi-Fi físico. Sem acesso USB/SSH/DFU/reboot ao telefone nesta preparação. Não adicionar testes opcionais às fases qualificadas nem pedir confirmações de rotina.

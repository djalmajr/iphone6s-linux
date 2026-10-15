# Etapa da recusa HDQ — issue48

## Contexto

A leitura física75:1d retornou EBUSY, valid0 e cleanup0, mas o log não distingue a etapa de falha. O telefone não carrega em Linux; preparar diagnóstico útil antes do próximo DFU e agrupar com a candidata DMA e o cleanup corrigido. Nenhum valor de controle de carga será escrito.

## Decisão D48

- **Decisão:** acrescentar rastreamento de software das etapas já executadas, sem adicionar MMIO, alterar comandos I2C, ownership, timeout ou cleanup. Conservar os logs/status existentes e emitir marcadores separados.
- **Por quê:** permite identificar a recusa no próximo boot mantendo o experimento limitado. O primeiro nível distingue pins, power, controller e transporte; o segundo distingue preflight, baseline, envio/poll, dado e cleanup do HDQ.
- **Alternativas:** repetir o teste antigo não distingue causas; afrouxar guardas sem readback pode esconder falhas e foi descartado.
- **Reverter:** baixo; usar módulo anterior preservado. Kernel/Image e exports não mudam.
- **Status:** em curso.

## Fase A — quatro arquivos executáveis

1. phone/kernel/n71-i2c-configuration.h: acrescentar stage ao result e enum1 pins,2 power,3 controller,4 HDQ,5 operação primária completa. Definir a etapa antes da chamada correspondente; cleanup não sobrescreve etapa nem primeira causa. Stage5 não declara cleanup concluído.
2. phone/kernel/n71-i2c-power-diagnostic.c: emitir N71_I2C_CONFIGURATION_STAGE stage/read/error/cleanup_error antes dos marcadores existentes. read informa modo solicitado; stage4 não prova tráfego no fio. Não expor status HDQ possivelmente antigo nesta fase.
3. tests/n71_i2c_power_diagnostic.c: capturar marcador separado, conferir as cinco etapas em falhas EBUSY/sucesso e manter asserts de chamadas, refs, cleanup e ausência de valor válido em falhas.
4. tests/test_n71_i2c_power_diagnostic.py: preservar as23 mutações existentes e acrescentar mutações reais das cinco atribuições de etapa e omissão do marcador; compilar baseline e exigir SIGABRT/assert, não falha de compilação.

Qualificar Mac/ARM64 com caller real e APIs/hardware em fixtures. Nenhuma instalação de pacote. Os headers reais de pin/controller/transporte mantêm seus gates anteriores enquanto não mudarem.

## Fase B1 — quatro arquivos executáveis

Novo phone/kernel/n71-i2c-hdq-trace.h, phone/kernel/n71-i2c-hdq-read.h, tests/n71_i2c_hdq_read.c e tests/test_n71_i2c_hdq_read.py. Trace opcional no request, separado do estado de ownership e com campos stage/status/sampled e cleanup_stage/cleanup_status/cleanup_sampled. Sem trace, o request legado continua funcional. Reset de tentativa mexe só no trace; retry de cleanup renova apenas seus campos, preservando a etapa/status primários. Flags sampled indicam leitura bruta concluída, não validade de gauge ou sucesso de transporte. Nunca copiar palavras de uma amostra incompleta.

Etapas primárias1 argumentos,2 readiness,3 ownership,4 snapshot,5 idle/baseline,6 ACK anterior,7 submissão,8 poll,9 dado,10 recuperação,11 completo. Cleanup1 argumentos,2 readiness,3 poll,4 snapshot,5 flush,6 ACK,7 verificação,8 readiness final,9 completo. Helpers de trace são apenas atribuições em memória, sem chamadas de hardware. Manter códigos de erro, comandos, contagens e ownership; trace não autoriza I/O. Testar fluxo real com/sem trace, flags/status separados, falhas precoces sem dado antigo e retry sem sobrescrever causa; executar mutações e gates Mac/ARM64 antes de B2.

## Fase B2 — quatro arquivos executáveis, depois de B1

phone/kernel/n71-i2c-configuration.h, phone/kernel/n71-i2c-power-diagnostic.c, tests/n71_i2c_power_diagnostic.c e tests/test_n71_i2c_power_diagnostic.py. Resultado de configuração contém trace de stack novo e request aponta para ele durante a leitura síncrona. Emitir N71_I2C_HDQ_TRACE separado somente em modo read, preservando os logs antigos. Stub reproduz o contrato de dados para testar a integração; o transporte real é provado em B1. Cleanup externo sem trace não apaga o diagnóstico da tentativa original. Sem novo sysfs, relógio, GPIO, barramento ou MMIO.

## Fase C — build e sessão agrupada

Compilar módulo externo novo na VM dedicada com W=1/KCFLAGS=-Werror e KBUILD_EXTRA_SYMBOLS fixado. Conferir imports/ELF/vermagic e hashes de .config/Image/vmlinux.symvers antes/depois; preservar módulo anterior. Planejar inspect → configure → read-hdq-control com status/readback/cleanup/unload e depois Wi-Fi, limite600s e snapshot. Não solicitar DFU antes das fases e candidata agrupada qualificadas.

## Tarefas

- [x] A: instrumento de etapa e caller qualificados Mac/ARM64.
- [x] B: subetapa/status do transporte qualificados sem MMIO adicional.
- [x] C: módulo real, documentação e roteiro agrupado prontos.
- [x] Prova física da etapa de recusa: configure stage 3, CTL 0104 rejeitado pela guarda de baseline; cleanup/unload verificados. Leitura HDQ e correção permanecem na issue48.

## Verificação

Contagens reais e mutações por asserção, AST/lint dos Python e Werror dos C; typechecker Python não configurado. Provar que o fluxo de I/O/cleanup é idêntico ao baseline e não há nova validade de dados. Não transformar build em telemetria/carga física. Logs/provas ficam privados, evidência sanitizada na branch autorizada. Goal permanece ativo.

## Resultado A

Mac/ARM64:81 cenários nativos e29 mutações SIGABRT/assert por plataforma;6 novas, Werror e AST/lint aprovados,661 inputs íntegros. Os marcadores/status anteriores permanecem iguais e não há novo MMIO. Módulo externo/faseB ainda não executados. Sem typechecker Python. Evidência em docs/evidence/n71-i2c-stage-qualified.json.

## Resultado B/C

Transporte Mac/ARM64:42 cenários e24 mutações por plataforma,8 inputs íntegros; caller:82 cenários e39 mutações por plataforma,14 inputs íntegros. Timeout de5s em uma mutação de cada plataforma: retomadas somente as pendentes,3 no Mac e26 no ARM64, todas mortas por SIGABRT/assert; logs originais preservados. AST/lint aprovados, sem typechecker Python. Comparação com/sem trace preservou as oito contagens de I/O; causa e cleanup separados, sem palavra parcial ou dados antigos.

Build externo W=1/KCFLAGS=-Werror concluído na VM dedicada:52456 bytes,79 imports válidos, ELF AArch64 relocável e vermagic fixado. .config/Image/vmlinux.symvers e11 inputs mantiveram hashes; módulo anterior intacto. CLI da candidata DMA passou --check sem hardware. Roteiro privado agrupa HDQ e Wi-Fi num boot limitado600s; nenhuma nova sessão física iniciada. Issue48 e goal permanecem abertos até a prova no aparelho.

## Resultado físico de 15/10

Módulo executado no mesmo boot do teste DMA. Inspect passou; configure recusou na aquisição do controlador, stage 3, erro -16, CTL salvo 0104 e cleanup 0. A guarda de baseline exige CTL dentro de 00ff; 0104 contém CTL_UJM (bit 8 na fonte PASemi fixada). Nenhum comando HDQ foi enviado. Cleanup e unload normal passaram; a guarda não foi relaxada. A sessão também provou reaquisição/atribuição/limpeza de recursos Wi-Fi sem DFU adicional, mantendo a falha DART. Evidência em docs/evidence/n71-grouped-dma-hdq-20261015.json. Issue48 permanece aberta para tratamento seguro da baseline e leitura válida.

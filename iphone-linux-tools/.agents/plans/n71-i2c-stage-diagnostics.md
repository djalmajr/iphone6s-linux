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

## Fase B — até cinco arquivos executáveis, depois de A

phone/kernel/n71-i2c-hdq-read.h, phone/kernel/n71-i2c-power-diagnostic.c, tests/n71_i2c_hdq_read.c, tests/test_n71_i2c_hdq_read.py e o stub correspondente em tests/n71_i2c_power_diagnostic.c. Fechar os códigos de subetapa após ler o gate real do transporte; registrar o estágio e os valores que já foram lidos, sem novos acessos ou alteração de retorno. Resetar apenas metadados de diagnóstico de operação nova qualificada, para não atribuir status antigo a uma tentativa nova. O cleanup conserva a causa original e possui informação de falha separada. Stage não participa da decisão de ownership/clean.

## Fase C — build e sessão agrupada

Compilar módulo externo novo na VM dedicada com W=1/KCFLAGS=-Werror e KBUILD_EXTRA_SYMBOLS fixado. Conferir imports/ELF/vermagic e hashes de .config/Image/vmlinux.symvers antes/depois; preservar módulo anterior. Planejar inspect → configure → read-hdq-control com status/readback/cleanup/unload e depois Wi-Fi, limite600s e snapshot. Não solicitar DFU antes das fases e candidata agrupada qualificadas.

## Tarefas

- [x] A: instrumento de etapa e caller qualificados Mac/ARM64.
- [ ] B: subetapa/status do transporte qualificados sem MMIO adicional.
- [ ] C: módulo real, documentação e roteiro agrupado prontos.
- [ ] Prova física da etapa de recusa; causa e eventual correção serão decididas pelo resultado, sem inventar gauge/ABI ou carga.

## Verificação

Contagens reais e mutações por asserção, AST/lint dos Python e Werror dos C; typechecker Python não configurado. Provar que o fluxo de I/O/cleanup é idêntico ao baseline e não há nova validade de dados. Não transformar build em telemetria/carga física. Logs/provas ficam privados, evidência sanitizada na branch autorizada. Goal permanece ativo.

## Resultado A

Mac/ARM64:81 cenários nativos e29 mutações SIGABRT/assert por plataforma;6 novas, Werror e AST/lint aprovados,661 inputs íntegros. Os marcadores/status anteriores permanecem iguais e não há novo MMIO. Módulo externo/faseB ainda não executados. Sem typechecker Python. Evidência em docs/evidence/n71-i2c-stage-qualified.json.

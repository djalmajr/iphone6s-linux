# Publicar a trace I2C da tentativa atual

## Decisão e contrato

Copiar a trace do controlador para o resultado da configuração imediatamente após acquire, antes de HDQ/cleanup. O resultado começa zerado; falha em pins/power não herda a trace antiga. Zerar a trace do controlador antes de acquire também cobre sua recusa antes do reset. O caller serializado publica N71_I2C_RESET_TRACE com contadores, erro de amostragem, primeiro CTL e cinco últimos words completos. samples=0 significa dados inválidos, não registradores zerados no hardware.

Não ampliar estados aceitos, writes/reads/retries nem contratos de cleanup. A mensagem added_reads=0/added_writes=0 descreve a instrumentação; configure continua executando as operações do controlador já documentadas. Não há leitura de gauge nem prova de carregamento.

## Checklist

- [x] Resultado recebe somente a aquisição atual, antes do cleanup.
- [x] Caller informa dados em configure e read-hdq-control, inclusive falhas.
- [x] Fixture compila caller/configuração reais; testa timeout, erro com último conjunto válido, falha anterior ao controlador e nova aquisição após trace preservada.
- [x] Gate Mac: 85 cenários e 51 mutações compiladas terminando por SIGABRT/assert; AST/lint aprovados. Índice público conferido no commit.

SHA256 do log privado: 925217f6b9ca69d442b81604c2fdf1b681b1e6e1858a58809895bd367494f409. A primeira execução detectou contadores esperados antigos no fixture após acrescentar duas ações; corrigidos os contadores, sem alteração de produção.
- [ ] Novo módulo externo, execução ARM64 e sessão física agrupada com DMA.

Cinco arquivos nesta fase. Os headers/controller têm gate real separado; seu mock nesta fixture delimita a prova do caller. Reverter removendo campo/cópia/mensagem, sem alterar operações do hardware. Sem nova VM, telefone ou DFU nesta fase.

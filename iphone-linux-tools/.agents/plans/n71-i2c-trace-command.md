# Preparar o I2C para o boot conjunto — issue #49

## Contexto e decisão

Reaproveitar o protocolo inspect/configure/read-hdq-control que já foi executado no aparelho, com o novo módulo que inclui RESET_TRACE. Executar antes de adquirir os recursos WLAN. Uma falha de configuração encerra a série I2C; somente limpeza independente comprovada e unload normal permitem prosseguir para WLAN. A captura do dmesg acontece também nas saídas negativas, sem escrita em carregador/gauge ou alteração dos estados de reset aceitos.

## Arquivos

- scripts/host/n71_i2c_trace_command.py: seleção explícita do pacote compilado e shell limitado ao boot/módulo qualificados.
- tests/test_n71_i2c_trace_command.py: executar o shell com dependências locais simuladas, provar recusas e ordem de limpeza.
- docs/N71_OBSERVADORES_DMA_I2C.md: procedimentos de runtime/coleta e limites.
- docs/evidence/n71-observer-runtime-collection-qualified.json: consolidar gates locais e manter a prova física pendente.

## Tarefas

- [x] Gerar comando com boot, ABI, hash/tamanho e exclusão de sessão WLAN concorrente.
- [x] Sete testes/quatro mutações por AssertionError aprovados: sucesso, limpeza necessária, retenção, ação negativa e recusas de boot/hash/WLAN. O primeiro teste usava código de saída 2 específico do shell e shims Python lentos; agora aceita qualquer exit não zero e usa shims de shell para as leituras.
- [x] Seleção real do módulo I2C (52904 bytes, ELF64 ARM64 e SHA conferidos), CLI --check do perfil real, AST/lint aprovados. Corrigida a adaptação do campo path do catálogo para o nome de upload; nenhum pin alterado.
- [ ] Preparar roteiro privado do boot conjunto e verificar fontes/artefatos novamente antes do monitor.
- [ ] Publicar somente código/documentação/provas sanitizadas; atualizar issue #49.
- [ ] Iniciar um único monitor e pedir somente DFU quando a coleta estiver pronta.

## Verificação

Rodar tests/test_n71_i2c_trace_command.py. O shell é real; insmod/rmmod/sysfs/identidades são modelos numa árvore temporária. Reutilizar os gates C/ARM64 do módulo inalterado e a regressão DMA já aprovada. Sem VM nova ou instalação no Mac.

# Primeiro readback da atribuição PCI — issue39

## Contexto

A atribuição física do incremento192 foi negativa: primeira recusa em root0:08, registrador0x30, dword0000ffff, error-5. O valor retornado pela leitura obrigatória após a escrita não foi registrado. As recusas posteriores repetem o erro retido e não constituem medições independentes. O contador `writes` contabiliza somente escritas verificadas; uma escrita com readback negativo pode ter sido executada sem incrementar esse contador.

## Decisão e alternativas

- **Decisão:** conservar a primeira falha da escrita/leitura já realizadas pela política, com pedido, valor anterior, valor retornado válido e erros brutos de I/O. Publicar um registro diagnóstico próprio, integrado ao contrato host, antes de testar novamente.
- **Por quê:** distingue bits não implementados, erro de transporte e valor inesperado sem ampliar permissões nem introduzir outra leitura ou tentativa no hardware.
- **Alternativas:** relaxar o readback sem observar seu valor pode ocultar uma janela incorreta; usar um comando avulso depois da falha não preserva necessariamente a leitura que causou o erro.
- **Reverter:** baixo; o caminho de restauração e a candidata anterior permanecem disponíveis.
- **Status:** em curso; nenhum novo boot nesta preparação offline.

## Arquivos e detalhes

Fase A, quatro arquivos: este plano; `phone/kernel/n71-pcie-resource-write.h` (estado de escrita e chamada de readback); `tests/n71_pcie_resource_write.c` (backend e regressão0x30); `tests/test_n71_pcie_resource_write.py` (mutações compiladas). Capturar somente falha que alcançou a escrita após guards; não fabricar readback quando write/read retornam erro. Preservar normalização de erros positivos, primeiro erro, orçamento, limites, número de operações, ownership e rollback. Cleanup não apaga a evidência.

Fase B: registro do adaptador e contrato host, com fixtures próprias e compatibilidade. Um registro completo e único deve corresponder à primeira recusa/erro, ocorrer antes do resultado e permanecer idêntico até o cleanup. Perfis anteriores sem o registro continuam válidos apenas pelo seletor anterior. Dividir em fases de até cinco arquivos conforme dependências concretas.

Fase C: build real na VM dedicada, prova ELF/ABI/exports e preservação de fonte/config/Image; seleção explícita por evidência qualificada e candidata privada separada. Não substituir o perfil anterior nem publicar binários, firmware, DT, identidades, chaves ou logs físicos.

## Tarefas

- [x] A: conservar primeira falha com readback válido/ausente e erros brutos sem I/O adicional.
- [x] A: executar regressão física sintética0x30, limites/rollback e mutações por assertion no Mac e Ubuntu ARM64; registrar inputs/logs/exit por SHA.
- [ ] B: integrar registro, parser e journal; validar histórico, rejeições e compatibilidade sem reiniciar o telefone.
- [ ] C: qualificar build, seleção e candidata agrupada; manter iOS para recarga durante desenvolvimento.
- [ ] Teste físico único quando candidata e alimentação estiverem prontas: aquisição, atribuição, coleta, cleanup/retry, serviços, snapshot/sync e retorno ao iOS no mesmo boot.
- [ ] Documentar resultados sanitizados e atualizar issue39; Wi-Fi e energia continuam abertos até suas próprias provas.

## Verificação

`python3 -B -m unittest discover -s tests -p test_n71_pcie_resource_write.py -v` compila a política real com warnings como erros. Exigir baseline positiva e mutantes compilados abortando por assertion; erro de compilação/importação/timeout não conta. Requalificar adaptador porque inclui o header alterado. AST, lint de erros fatais, diff e guard público devem passar. Provas anteriores só são reutilizadas com dependências intactas. Não há prova física nova ou licença para ampliar writes nesta preparação.

### Gate A

Mac e Ubuntu ARM64 passaram quatro testes: política194 cenários/36 mutações e adaptador64 cenários/51 mutações, todas compiladas e mortas por SIGABRT/assertion. Cinquenta e um inputs públicos iguais, AST, lint fatal e diff íntegros; logs/resultados privados conservados por SHA. Seis cenários novos distinguem readback0x30 divergente, erro bruto negativo/positivo de escrita/leitura, buffer alterado por callback que falhou, primeiro erro retido sem outra I/O, contagem somente de escritas verificadas e preservação após rollback. Nenhum módulo, Image, boot ou efeito físico novo.

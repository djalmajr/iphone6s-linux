# Observação DMA durante o primeiro comando — #46

## Contexto

A sessão PMD/UJM confirmou NO PMD e timeout de cur_etheraddr. O domínio DMA já é retido por n71_scan_host enquanto o bus PCI existe; getters e remoção são serializados por session_lock. Consultar depois da falha pode encontrar buffers já liberados. Precisamos de duas amostras limitadas, com validade explícita de cada campo e registro parcial de falhas, antes de mudar flags, cache ou janela.

## D1 — contrato somente de leitura

- **Decisão:** criar helper separado, opt-in, sem posse ou API de escrita. Recebe callbacks de guarda de lifetime, relógio, tradução de software e read32. IOVA limitado a 32 bits e ao aperture declarado; PA observado limitado a 36 bits do N71. Preservar o offset do IOVA. Dois snapshots, cada um com relógio, tradução e oito registradores do stream 0: command, TCR, error, error_addr e quatro TTBRs. Máximo de 16 reads MMIO, duas traduções e dois relógios, com guarda antes de cada callback e ao final.
- **Por quê:** os dados separam ausência de mapping de software e configuração de hardware sem trocar kernel, alocar tabelas, publicar dispositivos ou repetir firmware. A consulta não prova tradução física.
- **Alternativas:** alterar coerência ou flags outra vez não discrimina a causa; ler structs privados do apple-dart acopla o diagnóstico à ABI interna; tracing embutido exige rebuild de kernel e só será considerado se a observação externa for insuficiente.
- **Reverter:** baixo; helper novo não é chamado pelos caminhos atuais. Integração será opt-in e qualificada separadamente.
- **Status:** aplicada na Fase A; 100 cenários C nativos e 17 mutações por asserção passaram no Mac. Callbacks, domínio e MMIO são modelados; ainda não há integração no módulo nem prova no aparelho.

## Fase A — até quatro arquivos

1. phone/kernel/n71-dma-observe.h: contrato e amostras parciais. Erro, busy, instabilidade ou relógio reverso impedem stable; conservar campos já obtidos e seus bits de validade. Não converter zero de tradução em presença de mapping.
2. tests/n71_dma_observe.c: cenários nativos com ordens/offsets esperados independentes, limites, offset do IOVA, PA de 36 bits, todos os pontos de erro e amostras incompletas/divergentes.
3. tests/test_n71_dma_observe.py: compilar o helper real, executar contratos e mutações por SIGABRT/assert; falha de compilação não conta como kill. Temporários próprios removidos ao terminar.
4. Este plano. Sem alteração nos inputs PMD/power2 anteriores, seletores, caller ou módulo carregável nesta fase.

## Fase B — integração posterior

Confirmar o contrato/export de iommu_iova_to_phys no kernel fixado. Getter root-only deve verificar escopo N71, domínio/PCI/provider retidos, IOVA/aperture e remoção serializada. Não alocar/ioremap sob spinlock; não reivindicar região já possuída pelo driver. Uma observação MMIO concorrente ao IRQ pode ser instável e deve mostrar isso. Expor timestamp e valor consultado, sem afirmar que uma amostra tardia é o estado no momento do fault. Preparar coleta remota limitada antes de publish. Qualificar caller e build externo novos, preservando fonte/bytes compilados anteriores; não ignorar pins divergentes nem forçar ABI.

A fonte primária fixada de drivers/iommu/iommu.c documenta a validade do domínio durante a vida do driver vinculado e exporta iommu_iova_to_phys como GPL. O empréstimo guardado no host, sozinho, não basta para ampliar esse contrato. A integração precisa serializar também com o bind/unbind do endpoint, exigir driver vinculado, DMA não gerenciada pelo driver e domínio DMA atual idêntico ao esperado. Validar a ordem session_lock → device_lock e liberar todos os locks em falhas; não consultar um domínio inválido durante probe/unbind. Referências locais conferidas: runtime/n71-pmd-postphysical-research-20261015/iommu.c e iommu.h, com hashes em iommu-api-sources-private.json. Nenhum cast de estrutura privada é aceito.

## Fase C — agrupar energia e DMA

Instrumentar as amostras CTL já lidas pelo reset I2C, sem novos I/O, polling, writes ou ampliação de estados aceitos. Reunir as duas candidatas e cleanup antes do próximo DFU. VM dedicada permanece parada até inputs/gates estarem prontos e recursos permitirem. Nenhum worker novo sob pressão de memória.

## Verificação

Gate C nativo no Mac, AST/lint do runner e inputs preservados. A integração posterior exige contexto kernel/modpost e execução ARM64 na VM. Modelos não provam MMIO, tradução, IRQ ou carga no aparelho. Só concluir o goal com Wi-Fi e telemetria físicos e limites de alimentação documentados. Publicar código/provas sanitizadas na branch autorizada, sem main, firmware, chaves ou logs privados.

## Resultado Fase A

Mac: 100 cenários do helper real compilado com C11, Wall/Wextra/Werror/pedantic; 17 mutações compiladas terminaram por SIGABRT/assert. Incluem limites/aperture, offset preservado do IOVA, PA maior que 32 bits, guarda antes de cada callback, todos os pontos de falha, retenção de campos parciais, dois snapshots, busy, instabilidade e relógio reverso. stable indica apenas observações iguais e completas; PA zero continua sendo uma consulta sem mapping, não presença de tradução. O erro do callback é preservado; retorno positivo é normalizado para EIO. Cada campo parcial tem bit de validade explícito.

AST e lint fatal/F401/F841 do runner aprovados; sem typechecker Python configurado. A qualificação atual PMD foi executada novamente e confirmou os inputs antigos intactos; seus gates não afetados foram reutilizados. Não houve VM, SSH/USB, novo DFU ou alteração de caller/kernel/perfil padrão. Temporários do compilador foram removidos pelo próprio gate. Fases B/C continuam pendentes.

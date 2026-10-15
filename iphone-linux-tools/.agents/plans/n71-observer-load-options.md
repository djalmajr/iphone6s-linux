# Ligar o getter DMA no módulo qualificado — #49

## Decisão

Revalidar os bytes/manifestos da Session PMD antes de gerar as opções. Ler a interface do módulo que o seletor já qualificou; somente o catálogo explícito pmd-observers-v1 pode anunciar os três parâmetros novos. Conferir que o SHA ainda corresponde à Session e que dma_observe/dma_iova/dma_observation aparecem uma vez cada. Gerar dma_observe=1 dma_iova=0x3ffff028 junto com driver_runtime=1 no único insmod existente.

Sem interface nova, manter a carga PMD anterior. Não consultar catálogo novo para modos sem runtime ou release anterior. Interface parcial/duplicada e bytes/identidade divergentes são recusados. Não criar outro ciclo de insmod/ownership/cleanup. Os parâmetros do kernel são root-only e não iniciam DMA; o bind/publish permanece ação separada.

## Checklist

- [x] Gerador específico usa qualificação/bytes já existentes, sem mutar a Session ou os registros.
- [x] Integrar no comando real de carga, sem acrescentar efeito ou retry.
- [x] Sete testes/oito mutações por AssertionError aprovados, incluindo captura do comando real. O preflight do telefone é modelado; seus gates anteriores permanecem separados.
- [x] Regressão: 21 métodos não afetados/31 mutações passaram; o único erro foi fixture PMD consultando ROOT ativo, corrigida separadamente. Journal+firmware repetidos: sete métodos/cinco mutações aprovados. AST/lint e prova sanitizada aprovados.
- [x] Perfil real composto com 13 arquivos privados; CLI --check com firmware real passou. Session real gerou exatamente as duas opções; 115 fontes e 13 arquivos do perfil preservados. Nenhum SSH/USB.
- [ ] Preparar a coleta DMA/I2C limitada antes de pedir DFU; validar os dados físicos durante a sessão.

Testes de comando modelam o telefone e não comprovam a execução do getter físico. VM continua parada, sem instalação no Mac, SSH/USB ou novo DFU. Reverter retirando a função e a chamada; perfis/módulos anteriores permanecem intactos.

Reprodução privada: com IPHONE_LINUX_PMD_SOURCE_RECEIPT apontando para runtime/n71-pmd-frozen-inputs-20261015/receipt-private.json e IPHONE_LINUX_PMD_DIAGNOSTICS=pmd-observers-v1, usar compose-n71-diagnostic.py com base PMD, kernel/DTB originais, PCIE do novo pacote (SHA 1e26c51ccc41cca3579be87852b381748ea44c9f3290160ff256a62c432d853d), REG_ON do novo pacote e os cinco WCC preservados do perfil PMD anterior. Destino novo: runtime/n71-observers-runtime-profile-20261015. O argv exato e os logs estão no receipt privado real-compose-observer-private.json. Rodar n71-runtime-session.py --profile desse destino --action acquire --firmware-dir runtime/n71-trusted-firmware-20261010 --check antes de qualquer efeito. A fonte dos binários continua 8b62c9c; nenhum novo kernel/módulo foi compilado nesta fase.

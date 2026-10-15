# Compilar observadores novos sem reconstruir o kernel

## Decisão e escopo

Selar os 64 inputs de 6c682b701f2642ac795fca056354b6c08a238c83 para uma pasta nova da VM iphone6s-kernel-20261001. Reutilizar o checker do build PMD anterior, com hash fixado; conferir fonte, Image/config/exports antes e depois. Make externo com W=1/Werror, um job, sem instalação/carga nem escrita nos perfis/módulos anteriores. Preservar as sete saídas e seus imports/ABI; os novos parâmetros DMA e a mensagem I2C precisam estar nos binários reais.

VM existente: 4 GiB/2 CPUs. A pressão consultada no Mac mostrou 47% de memória livre reportada pelo memory_pressure, mas swap quase cheio; não abrir painéis nem paralelizar builds. Iniciar somente após gates do builder e parar ao fim. Não instalar pacotes/configuração global. A cópia adicional consiste nos inputs e módulos externos, sem novo worktree/kernel completo.

## Checklist

- [x] Manifesto/tar determinísticos dos 64 inputs; nova identidade pmd-observers-v1.
- [x] Builder separado mantém o checker e os pins dos módulos antigos intactos.
- [x] Mac: arquivo real reconstruído do commit fixado, cinco testes e quatro mutações por AssertionError aprovados; AST/lint aprovados.
- [x] Terceiro selo: --check e build ARM64 aprovados, sete ELF/269312 bytes, imports/ABI e kernel preservado. Baselines ARM64: 324 cenários em quatro métodos; 108 mutações Mac reutilizadas, sem repetir crashes na VM.
- [ ] Qualificar novo pacote de runtime e coleta agrupada antes de um DFU.

Até cinco arquivos nesta fase. Registro sanitizado do build virá somente após execução real. Fontes/firmware/chaves/logs privados permanecem em runtime/VM; nenhum resultado nativo/compilação comprova Wi-Fi, bateria ou carregamento no aparelho.

## Primeira execução ARM64

--check passou na VM real. O primeiro build W=1/Werror recusou a chamada io->guard(...), expandida pela macro guard(...) de linux/cleanup.h. O finally confirmou fonte e artefatos do kernel PMD preservados. Nenhum módulo foi instalado/carregado. Renomear esse callback em uma fase explícita e gerar novo selo a partir do commit corrigido; não alterar os pins dos módulos PMD antigos nem atribuir sucesso ao build recusado. A VM está em uso para a correção, sem outros painéis.

A segunda execução usou 4c5d2dbc054d88b0397ad8128cf738da744b9697 e o tar 18a0aca21c6db40e4eb87fd4284242126df1c85b41f247a068fe5aff4e3b0e56. --check passou, mas Werror identificou a variável local current, expandida pela macro get_current do kernel. As mensagens completas ficaram privadas; Image/config/exports/fonte novamente preservados. Corrigir também esse nome e manter ambos os casos no gate nativo antes do terceiro selo.

Terceira execução: fonte 8b62c9cd5c6bd1a1ef1144136ba7deadf94795da, tar 4c83ad67d47cc1e31a0da53868ed22d6daee0c460606d6664f178d6cedb85681 e manifesto c5b5cd6307a6224496f35d975fe0141a933bcffc9330319d83a118b929391d6e. Os sete módulos foram copiados para runtime privado e conferidos localmente. As quatro pastas próprias das tentativas recusadas foram removidas após preservar logs; os dois tars locais obsoletos também. VM confirmada Stopped. A receita e limites completos estão em docs/N71_OBSERVADORES_DMA_I2C.md. A integração de runtime e o teste físico agrupado permanecem pendentes.

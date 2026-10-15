# Compilar observadores novos sem reconstruir o kernel

## Decisão e escopo

Selar os 64 inputs de 6c682b701f2642ac795fca056354b6c08a238c83 para uma pasta nova da VM iphone6s-kernel-20261001. Reutilizar o checker do build PMD anterior, com hash fixado; conferir fonte, Image/config/exports antes e depois. Make externo com W=1/Werror, um job, sem instalação/carga nem escrita nos perfis/módulos anteriores. Preservar as sete saídas e seus imports/ABI; os novos parâmetros DMA e a mensagem I2C precisam estar nos binários reais.

VM existente: 4 GiB/2 CPUs. A pressão consultada no Mac mostrou 47% de memória livre reportada pelo memory_pressure, mas swap quase cheio; não abrir painéis nem paralelizar builds. Iniciar somente após gates do builder e parar ao fim. Não instalar pacotes/configuração global. A cópia adicional consiste nos inputs e módulos externos, sem novo worktree/kernel completo.

## Checklist

- [x] Manifesto/tar determinísticos dos 64 inputs; nova identidade pmd-observers-v1.
- [x] Builder separado mantém o checker e os pins dos módulos antigos intactos.
- [x] Mac: arquivo real reconstruído do commit fixado, cinco testes e quatro mutações por AssertionError aprovados; AST/lint aprovados.
- [ ] Executar --check e build ARM64 na VM; conferir 7 ELF/imports/ABI e preservação do kernel.
- [ ] Qualificar novo pacote de runtime e coleta agrupada antes de um DFU.

Até cinco arquivos nesta fase. Registro sanitizado do build virá somente após execução real. Fontes/firmware/chaves/logs privados permanecem em runtime/VM; nenhum resultado nativo/compilação comprova Wi-Fi, bateria ou carregamento no aparelho.

## Primeira execução ARM64

--check passou na VM real. O primeiro build W=1/Werror recusou a chamada io->guard(...), expandida pela macro guard(...) de linux/cleanup.h. O finally confirmou fonte e artefatos do kernel PMD preservados. Nenhum módulo foi instalado/carregado. Renomear esse callback em uma fase explícita e gerar novo selo a partir do commit corrigido; não alterar os pins dos módulos PMD antigos nem atribuir sucesso ao build recusado. A VM está em uso para a correção, sem outros painéis.

A segunda execução usou 4c5d2dbc054d88b0397ad8128cf738da744b9697 e o tar 18a0aca21c6db40e4eb87fd4284242126df1c85b41f247a068fe5aff4e3b0e56. --check passou, mas Werror identificou a variável local current, expandida pela macro get_current do kernel. As mensagens completas ficaram privadas; Image/config/exports/fonte novamente preservados. Corrigir também esse nome e manter ambos os casos no gate nativo antes do terceiro selo.

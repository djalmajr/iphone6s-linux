# Seleção explícita dos diagnósticos observadores — #49

## Decisão

O kernel PMD/ABI não mudou; os sete diagnósticos têm novas identidades de build. Concluir primeiro a qualificação anterior e seus inputs compilados preservados. Somente se IPHONE_LINUX_PMD_DIAGNOSTICS=pmd-observers-v1, validar o novo manifesto fixado, os 64 fontes reais, os sete registros de módulo, os gates reais e sua ligação com o mesmo kernel/source bundle. Retornar então esses registros para os consumidores existentes. Sem variável, preservar seleção anterior; valor vazio/desconhecido é recusa.

O novo registro é uma prova histórica de build não carregado: não editar seus flags para representar a integração atual. Wi-Fi/telemetria/carga não são demonstrados por esses metadados. O caminho explícito anterior IPHONE_LINUX_PMD_SOURCE_RECEIPT continua necessário quando a árvore atual evoluiu além dos módulos antigos; a sobreposição não ignora sua qualificação.

## Checklist

- [x] Qualificador específico e um ponto de seleção após o base check, sem alterar release, defaults ou pins antigos.
- [x] Fixture real dos registros/arquivos, seleção por IOMMU/resources e recusas de metadata/source/kernel/opt-in; oito testes/oito mutações aprovados no Mac.
- [x] Regressão anterior: 15 testes/19 mutações. AST/lint e prova sanitizada aprovados; até cinco arquivos nesta fase.
- [x] Seleção real via driver runtime: sete diagnósticos e cinco WCC conferidos por module_bytes; runtime escolheu dois diagnósticos + cinco WCC, 1376792 bytes. Os 92 arquivos protegidos ficaram idênticos.
- [ ] Aplicar a seleção a um perfil privado com os binários reais e --check, sem SSH/USB. Nenhum perfil foi composto nesta fase; permanece pendente para a integração das opções/coletor.
- [ ] Opções DMA e coletores limitados, prontos antes de publish, na fase seguinte.

## Alternativas e reversão

Trocar o release exigiria um kernel novo sem necessidade. Atualizar os pins anteriores confundiria binários já preservados. Um script de insmod separado repetiria o ciclo de ownership/cleanup do runtime existente. A seleção explícita reusa esse ciclo e permanece restrita ao pacote compilado conhecido. Reverter removendo o ponto de seleção e o qualificador; nenhum estado do telefone ou perfil padrão é alterado nesta fase. VM permanece parada, sem painel ou DFU novo.

Reprodução da seleção real: usar as duas variáveis apenas no processo: IPHONE_LINUX_PMD_SOURCE_RECEIPT=$PWD/runtime/n71-pmd-frozen-inputs-20261015/receipt-private.json e IPHONE_LINUX_PMD_DIAGNOSTICS=pmd-observers-v1. n71_driver_runtime_build.select recebe o release PMD e o SHA 1e26c51ccc41cca3579be87852b381748ea44c9f3290160ff256a62c432d853d. n71-link-session.module_bytes conferiu os sete .ko em runtime/n71-pmd-observers-artifacts-20261015 e os cinco WCC em runtime/n71-pmd-wifi-modules-20261015, com seus caminhos relativos registrados. Funções de seleção e bytes somente: nenhuma Session, SSH/USB, output de perfil ou firmware carregado. VM permaneceu parada.

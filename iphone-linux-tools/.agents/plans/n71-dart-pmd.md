# PMD do DART S5L — issue #46

## Contexto

O boot agrupado de 15/10 confirmou execução do firmware, mas o primeiro comando expirou e o DART relatou NO PMD. A janela DMA alternativa não corrigiu o erro. O endereço registrado inclui o OR com dma_min; não prova os bits brutos emitidos pelo dispositivo. A referência Apple preservada (SHA256 0a9b98d58c5c606030c394bee37b6ddd58e0d82468203f7de9ab3fe6c63a8b9a) escreve no PMD o endereço físico mascarado em 35:12 com flags 3, em 0xfffffff006060520..52c. O Linux fixado usa flags 1. Largura de 64 bits, índices de 9 bits e codificação TTBR concordam.

## Decisão D1 — candidata limitada ao S5L

- **Decisão:** testar bit 1 em entradas intermediárias somente quando o driver seleciona explicitamente a quirk S5L e o formato é APPLE_DART. Criar bundle e versão distintos; preservar os bundles e artefatos anteriores.
- **Por quê:** reproduz uma diferença observável da referência do mesmo aparelho, sem mudar as tabelas dos DART modernos. A causalidade do fault ainda depende do aparelho.
- **Alternativas:** repetir a janela já falha não oferece diagnóstico novo; alterar todos os DART amplia o escopo; usar o mesmo nome de kernel dificulta distinguir candidatas. Tracing dinâmico não está compilado no kernel atual.
- **Reverter:** baixo, selecionar o perfil/kernel anterior; nenhum flash ou armazenamento interno modificado.
- **Status:** em curso.

## Fase A — fonte e seleção, até cinco executáveis

1. phone/kernel/patches/0009-s5l8960x-dart-pmd.patch: quirk BIT(10) em include/linux/io-pgtable.h; seleção apenas DART_S5L8960X em drivers/iommu/apple-dart.c; bit 1 apenas APPLE_DART com a quirk em drivers/iommu/io-pgtable-dart.c. Preservar PA, barreira, CAS, folhas, TCR, TTBR e janela.
2. scripts/build/kernel_bundle.py: bundle n71-dart-serdev-pmd-v1, versão -iphone6s-dart-serdev-pmd1, patches e blobs completos fixados; perfis anteriores imutáveis.
3. tests/test_kernel_pmd_bundle.py: Git real, seleção, recusas e preservação, aplicação idempotente e mutações com AssertionError.
4. tests/n71_dart_pmd.c e tests/test_n71_dart_pmd.py: compilar os trechos efetivos do patch, exercer publicação PMD, PA, escopo, CAS concorrente e ordenação; mutações precisam falhar por assert, não por compilação.

## Fase B — build isolado e integração

Aplicar somente em worktree novo na VM dedicada, com inputs selados. Manter source/build power2 intactos. Qualificar os trechos contra a fonte completa real e compilar os objetos reais com Werror. Preparar build completo com configuração herdada alterando somente LOCALVERSION; verificar Image, DTB, configuração embutida, exports, serdev e modpost. Não instalar. As permissões de seleção de kernel/módulos/perfil só serão ampliadas por uma fase separada, depois de um registro de build real; nenhum bypass das provas existentes.

## Fase C — um teste físico agrupado

Antes de solicitar DFU, preparar kernel, todos os módulos compatíveis, perfil privado com identidades preservadas, diagnóstico HDQ UJM, restore e coleta/cleanup numa sessão limitada. O aparelho está no iOS bloqueado e recarregando; nenhuma ação necessária agora. Após retorno ao iOS, ausência de USB é tratada como tela bloqueada, sem nova confirmação rotineira.

## Verificação

Gates novos no Mac e ARM64; regressão dos bundles impactados sem repetir gates de módulos que não mudaram. AST/lint Python; não há typechecker Python configurado. Conferir inputs e artefatos protegidos antes/depois. Publicar apenas código e fatos/hash/endereço sanitizados, sem bytes Apple, firmware, identidades ou logs privados. Não encerrar issue #46 sem prova física de DMA/firmware/comando, nem afirmar WLAN, carga ou telemetria por build.

## Tarefas

- [x] Confirmar e registrar a diferença PMD na fonte primária.
- [x] Implementar patch, seleção e contratos nativos; Mac aprovado, ARM64 ainda pendente.
- [ ] Qualificar objetos e build completo isolado.
- [ ] Integrar o novo kernel/módulos em perfil opt-in sem alterar o padrão.
- [ ] Reunir HDQ e Wi-Fi antes de um DFU necessário.
- [ ] Comprovar o comportamento no aparelho e atualizar as issues.

## Andamento e recuperação do build

Mac: 387 cenários do instalador/configuração com 12 mutações compiladas; bundle novo 5 testes/7 mutações; regressão dos três bundles anteriores 15 testes/14 mutações. AST e lint aprovados, sem typechecker Python. As APIs de memória, barreira e CAS são modeladas; não é prova de coerência ou concorrência do DART físico.

O primeiro preparo ARM64 excedeu 180 s no checkout do worktree, antes da aplicação do patch e antes de compilar. Source/config/Image/exports power2 foram novamente conferidos e preservados. O processo filho terminou; não há checkout concorrente. O builder público permite 600 s para um worktree novo e uma retomada explícita --resume-source somente quando inputs selados e checkout exato passam pelas recusas existentes. Não reiniciar um build por timeout de observação. Nenhum reboot ou pedido ao operador foi feito nesta fase.

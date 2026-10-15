# Janela DMA N71 — issue46

## Contexto

A sessão física788a49c iniciou o firmware BCM4350r8 e falhou em DART stream0/NO PMD FOR IOVA0x3ffff028. O DT atual não contém apple,dma-range; a fonte fixada do Linux usa0..ffffffff e mask=~dma_min no S5L. A referência Apple já qualificada registra vm-offset como dois u32 distintos: base80000000 e janela de randomização08000000; vm-size3ffff000. Não copiar o par como u64.

## Decisão D46

- **Decisão:** compor uma candidata privada com apple,dma-range de dois u64 big-endian: start80000000 e length3ffff000, sem randomização. O fim exclusivo é bffff000, preservando a página MSI de referência fora da alocação DMA. A máscara S5L remove o bit de base; a janela mapeada é0..3fffefff.
- **Por quê:** mantém a alocação Linux dentro do espaço descrito pelo mapper Apple, sem ampliar permissões, alterar fonte/kernel ou mapear endereços físicos arbitrários. É hipótese experimental apoiada em fonte e fault; não é causa comprovada nem Wi-Fi funcionando.
- **Alternativas:** instrumentar somente o driver antes da janela exigiria outro ciclo físico sem testar a diferença conhecida; bypass DART perde isolamento e foi descartado. Randomização Apple não é necessária para a semântica Linux e não será reproduzida.
- **Reverter:** baixo; usar o perfil original preservado. Nenhum default será substituído.
- **Onde:** novo scripts/build/compose-n71-dma-window.py, novo tests/test_n71_dma_window.py; dados privados runtime/n71-dma-window-20261015.
- **Status:** em curso.

## Arquivos e detalhes

Compositor: reutilizar parser/serializer e gates runtime atuais; source calibrado de14 arquivos canônicos e privados. Exigir referência Apple com SHA7e71222b78099dbca7b2487dcc4b727f8a922c3b1885fc47f086d518eefef040 e valores/board/stream exatos; DART disabled, IRQ248, reg602008000/4000 e compatibilidades N71. Recusar propriedade já presente, origem errada, mistura de arquivos, hashes/identidades inválidos e output existente/fora de runtime. Aceitar somente o delta da propriedade; preservar integralmente loader/kernel/initramfs/módulos/calibração/chaves/known_hosts. Recalcular apenas hashes DT/payload/deployment e provenance; marcar candidata não testada fisicamente. Gate local antes e depois, sem SSH/USB e com umask/ambiente restaurados em erro.

Testes: fixture calibrada real dos testes existentes, identidade/kernel sintéticos declarados; compositor/DT/arquivos/gates reais. Verificar bytes/endian/range/MSI, preservação, permissões, recusas e erro parcial. Mutações por AssertionError para janela errada, dado desconhecido, delta ampliado, perda de kernel e ambiente/umask.

## Tarefas

- [x] Implementar compositor e gate de regressão/recusas.
- [x] Qualificar Mac/ARM64, AST/lint e mutações; não há typechecker Python configurado.
- [x] Compor/validar candidata com perfil e identidades reais, sem boot; fonte permanece idêntica.
- [ ] Documentar hipótese/provas e atualizar issue46/branch.
- [ ] Antes de outro DFU, reunir correção de stop (#47), diagnóstico HDQ (#48) e os readbacks DART/DMA necessários.
- [ ] Prova física agrupada: sem fault/timeout, WLAN/IRQ/DMA/associação e cleanup; não encerrar issue46 apenas por build/CI.

## Verificação

Reutilizar gates de kernel/módulos/pacote com inputs inalterados. Novo unittest, mutações e execução CLI real --check no Mac; mesma qualificação no Ubuntu ARM64. Conferir SHA/bytes das fontes e outputs. Testes não provam janela real ou associação. Manter snapshot, USB/SSH e limite de sessão física.

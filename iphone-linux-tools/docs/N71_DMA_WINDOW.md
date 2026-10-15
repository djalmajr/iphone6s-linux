# Candidata de janela DMA N71

## Estado

Composição e gates locais qualificados; **não foi iniciada no iPhone**. A falha física permanece na [issue46](https://github.com/djalmajr/iphone6s-linux/issues/46). Não há prova nova de Wi-Fi, DMA, IRQ ou carga. [Evidência sanitizada](evidence/n71-dma-window-qualified.json) e [plano/decisão D46](../.agents/plans/n71-dma-window.md).

## Hipótese apoiada nas fontes

O teste788a49c iniciou o firmware e encontrou NO PMD FOR IOVA0x3ffff028 no stream0. O DT selecionado não tinha apple,dma-range; o Linux usou o intervalo padrão de32 bits. Isso não determina sozinho a causa do fault.

A [referência Apple já qualificada](evidence/n71-dart-apple-stream-reference.json) conserva vm-offset como **dois u32 little-endian independentes**:80000000 é base,08000000 é janela de randomização; vm-size é3ffff000. O par não é um u64 DMA range.

Na fonte fixada do [apple-dart.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/iommu/apple-dart.c), probe lê apple,dma-range como dois u64 (base e tamanho), calcula dma_max=base+size−1 e fixa a geometria do domínio. finalize_domain usa mask=~dma_min no S5L; map/unmap/iova_to_phys aplicam essa máscara. O fault handler recompõe o endereço com addr OR dma_min. O [io-pgtable-dart.c](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/iommu/io-pgtable-dart.c) seleciona tabelas a partir do IOVA recebido. A candidata testa essa diferença conhecida sem alterar o kernel.

| Campo | Candidata |
| --- | --- |
| apple,dma-range | dois u64 big-endian:80000000,3ffff000 |
| Alocação DMA inclusiva |80000000..bfffefff |
| Página MSI excluída |bffff000..bfffffff |
| Offset depois da máscara S5L |0..3fffefff |
| Randomização Apple | não reproduzida |

## Composição reproduzível

```bash
export IPHONE_LINUX_RUNTIME_SOURCE_RECEIPT="$PWD/runtime/n71-runtime-source-be960-current-20261010/receipt.json"
python3 -B scripts/build/compose-n71-dma-window.py \
  --source-profile "$PWD/runtime/n71-pci-calibration-profile-20261010/deployment.json" \
  --output-dir "$PWD/runtime/n71-dma-window-profile-20261015"
```

A pasta de saída deve ser nova. O compositor exige source calibrado privado de14 arquivos, referência Apple fixada por SHA e N71 DART disabled com reg/IRQ/cells exatos. Aceita somente uma propriedade nova; todos os demais nós/propriedades são iguais. Kernel/initramfs/prefixo, sete módulos, calibração e identidades são preservados. Mudam payload.bin, deployment.json e provenance.json; os11 demais arquivos permanecem idênticos. O source original continua intacto. Os gates source/candidate verificam imagem e identidades reais sem SSH/USB. Nada é instalado no Mac ou alterado no perfil default.

Rollback: selecionar o perfil de calibração original. Binários, perfis, calibração, chaves e logs ficam privados; não estão no GitHub.

## Qualificação

Mac/Ubuntu ARM64:5 testes e14 mutações AssertionError por plataforma, AST/lint fatal aprovados. Não há typechecker Python configurado.658 inputs públicos conferidos antes/depois; identidade/kernel sintéticos nos testes, DT/compositor/filesystem/gates reais. A execução CLI com o perfil real confirmou os14 arquivos, modos700/600, delta único e preservação integral do prefixo/kernel/initramfs. Gates inalterados de kernel/módulos foram reutilizados.

Um mutante de guard redundante sobreviveu; a redundância foi removida e não contou como kill. Uma âncora de mutação ambígua foi corrigida antes do gate final. Logs e reprodução privada em runtime/n71-dma-window-20261015 e /home/ubuntu/n71-dma-window-20261015 na VM dedicada.

## Antes do próximo DFU

Concluir a classificação de stop com erro anterior (#47), diagnóstico da etapa HDQ EBUSY (#48) e definir readbacks de tradução/IRQ/firmware no teste. Reunir tudo numa sessão limitada com snapshot, USB/SSH e cleanup. Apenas composição, testes ou CI não encerram a issue46 nem o goal.

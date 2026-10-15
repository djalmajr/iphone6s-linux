# Entrada intermediária do DART S5L

## Motivo da candidata

Na sessão física agrupada de 15/10/2026, a janela DMA alternativa não resolveu o `NO PMD` seguido de timeout do primeiro comando do firmware. O resultado completo está em [N71_SESSAO_DMA_HDQ.md](N71_SESSAO_DMA_HDQ.md). O endereço impresso pelo driver inclui `addr | dma_min`; não demonstra o endereço bruto emitido pelo dispositivo.

A referência Apple do mesmo N71 permite comparar o formato da tabela:

| Propriedade | Apple N71 preservado | Linux fixado |
| --- | --- | --- |
| Entrada | 64 bits | 64 bits |
| Índices com página de 4 KiB | TTBR com 2 bits; níveis com 9 bits | Mesma organização |
| TTBR | PA deslocado 12; válido no bit 31 | Mesma codificação |
| Entrada intermediária PMD | PA[35:12] com flags `3` | PA[35:12] com flags `1` |

O ponto novo é o bit 1 da entrada intermediária. O significado exato desse bit no hardware antigo e sua relação causal com o fault continuam sendo hipóteses. A comparação não prova que o Wi-Fi passará a funcionar.

## Fonte primária e reprodução da análise

[n71-dart-apple-pmd-reference.json](evidence/n71-dart-apple-pmd-reference.json) registra hash, segmento, endereço e hash do trecho verificado. Nenhum byte do kernel Apple é publicado. O registro anterior [n71-dart-apple-stream-reference.json](evidence/n71-dart-apple-stream-reference.json) permanece intacto, pois integra provas históricas fixadas.

1. Reutilizar o kernelcache privado obtido pelo procedimento de [apple-n71-kernel.py](../scripts/research/apple-n71-kernel.py). O SHA256 decodificado deve ser `0a9b98d58c5c606030c394bee37b6ddd58e0d82468203f7de9ab3fe6c63a8b9a`; não executar o binário.
2. Pelos comandos `LC_SEGMENT_64` do Mach-O, localizar o endereço `0xfffffff006060520` em `__PLK_TEXT_EXEC`. O arquivo JSON informa o offset correspondente; conferir o hash dos 16 bytes.
3. Desmontar esse trecho como AArch64 na VM usando o `objdump` já disponível. A sequência mascara o PA retornado pela alocação, combina flags `3`, obtém a raiz virtual e publica uma entrada de 64 bits indexada pelo PMD. Manter bytes e desmontagem em `runtime/`, sem versionar.
4. Comparar com `dart_install_table` em `drivers/iommu/io-pgtable-dart.c`, blob SHA256 `ba8b9e53edb1bbf3ebd2e1881c10a40d3b93284e9f074231f07e0443874be493`, da base Linux `958481f87fee0949ff6a9a4af77f7eb6dac8a149`.

## Escopo do patch

[0009-s5l8960x-dart-pmd.patch](../phone/kernel/patches/0009-s5l8960x-dart-pmd.patch) acrescenta uma quirk explícita:

- Somente `DART_S5L8960X` seleciona `IO_PGTABLE_QUIRK_APPLE_DART_S5L`.
- Somente o formato `APPLE_DART` com essa quirk acrescenta bit 1 ao PMD.
- Endereço físico, folhas, janela DMA, TTBR, TCR, barreira de publicação e CAS permanecem iguais.
- O bundle `n71-dart-serdev-pmd-v1` tem identidade `7.2.0-iphone6s-dart-serdev-pmd1`. Os bundles anteriores mantêm seus hashes, patches e versões.

O nome novo impede que um módulo da candidata anterior seja confundido com um módulo recompilado para este kernel. As permissões dos seletores existentes ainda não foram ampliadas para a candidata; não há override de hash, carga forçada de módulo ou alteração do perfil padrão.

## Qualificação e reprodução do build

O plano está em [.agents/plans/n71-dart-pmd.md](../.agents/plans/n71-dart-pmd.md). Os gates são:

```sh
python3 -B -m unittest discover -s tests -p test_n71_dart_pmd.py -v
python3 -B -m unittest discover -s tests -p test_kernel_pmd_bundle.py -v
```

O primeiro compila os trechos efetivos do patch com APIs modeladas, executa 387 cenários e exige falha por assert em 12 mutações compiladas. Cobre flags/endereço, seleção de hardware/formato/quirk, ordem da barreira e preservação do vencedor de CAS modelado. Não é uma prova de coerência do DART físico ou de concorrência no kernel. `N71_DART_PMD_SOURCE` permite repetir o mesmo gate contra os arquivos completos de um worktree aplicado.

O segundo usa Git real e conteúdo sintético independente: aplicação exata/idempotente, preservação, recusa de upgrade parcial, integridade e sete mutações de seleção. A aplicação dos patches e os hashes dos blobs reais são conferidos separadamente na VM.

[build-n71-pmd-kernel.py](../scripts/build/build-n71-pmd-kernel.py) preserva a reprodução exata desta candidata. Executar somente como usuário sem privilégios na VM ARM64 dedicada `iphone6s-kernel-20261001`:

1. Criar o arquivo tar de 16 inputs abaixo, preservando nomes relativos. Os bytes precisam corresponder ao SHA256 fixado no script; qualquer edição exige nova qualificação e revisão do pin, nunca ignorar a recusa.
2. Transferir o tar para `/home/ubuntu/n71-pmd-qualification-inputs-20261015.tar` e o builder para a VM.
3. Executar `python3 -B build-n71-pmd-kernel.py`. As pastas de source/build/logs devem ser novas; o programa recusa reutilização e não instala os outputs.

Se somente a preparação do checkout for interrompida, esperar o processo Git terminar antes de agir. O modo `--resume-source` reaproveita apenas os inputs idênticos e o worktree da base exata; exige build ainda inexistente e recusa conteúdo incompleto ou alterações alheias. Não relança nem sobrescreve um build em andamento. A tentativa inicial desta sessão excedeu 180 s nessa etapa; o limite do procedimento novo é 600 s.

```text
scripts/build/kernel_bundle.py
scripts/build/kernel_patchset.py
tests/test_kernel_pmd_bundle.py
tests/test_kernel_binding_bundle.py
tests/test_kernel_power_bundle.py
tests/test_kernel_bundle.py
tests/test_n71_dart_pmd.py
tests/n71_dart_pmd.c
phone/kernel/patches/0001-s5l8960x-dart-stream-tcr.patch
phone/kernel/patches/0002-serdev-stop-bits.patch
phone/kernel/patches/0003-apple-gpio-write-errors.patch
phone/kernel/patches/0004-apple-pmgr-errors.patch
phone/kernel/patches/0005-apple-pmgr-probe-errors.patch
phone/kernel/patches/0006-apple-pmgr-provider-cleanup.patch
phone/kernel/patches/0007-apple-pmgr-no-manual-bind.patch
phone/kernel/patches/0009-s5l8960x-dart-pmd.patch
```

O tar usado inicialmente tem 133120 bytes e SHA256 `918c2e5e61933df2d8aea15963b9c80739b985caac5232de94c5614e67461177`. O pacote canônico reproduzível tem os mesmos conteúdos, 112640 bytes e SHA256 `b88de095c1a6d54db51c9926a6ee1609cbbc8404b7b2783d44fb9c9882568806`; ambos são aceitos pelo builder. O [registro de qualificação](evidence/n71-dart-pmd-host-qualified.json) contém os hashes individuais e a ordem dos membros. Para recriar o pacote canônico na raiz de iphone-linux-tools:

```python
from pathlib import Path
import hashlib, io, json, tarfile

proof = json.loads(Path('docs/evidence/n71-dart-pmd-host-qualified.json').read_text())
target = Path('runtime/n71-pmd-inputs-canonical.tar')
with tarfile.open(target, 'x', format=tarfile.USTAR_FORMAT) as archive:
    for name in proof['canonical_tar']['member_order']:
        data = Path(name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == proof['inputs'][name]['sha256']
        member = tarfile.TarInfo(name)
        member.mode = 0o644
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
assert hashlib.sha256(target.read_bytes()).hexdigest() == proof['canonical_tar']['sha256']
```

Nenhum firmware, chave ou conteúdo do telefone entra no pacote de build. A criação usa USTAR, ordem fixa, mtime/uid/gid zero e modo 0644; não depende dos metadados do clone.

O builder mede source e build anteriores para reservar espaço com margem de 2 GiB, aplica todos os oito patches em worktree novo, verifica os oito blobs completos, executa os gates ARM64, herda a configuração alterando somente LOCALVERSION, compila os dois objetos reais com W=1/Werror e depois Image/DTB. Confere configuração embutida, modpost, export serdev, módulos preparados e hashes do kernel anterior antes/depois. Os artefatos existentes permanecem protegidos.

## Aceite no aparelho ainda pendente

Depois do build completo, faltam módulos compatíveis, integração opt-in qualificada e uma sessão física reunindo este diagnóstico com HDQ/UJM. Não solicitar outro DFU para repetir o fault conhecido sem a candidata pronta. Nenhuma ação é necessária no iPhone enquanto isso: ele pode permanecer no iOS bloqueado e carregando.

Wi-Fi nativo, telemetria e carga no Linux continuam sem comprovação. O patch não escreve registradores do carregador nem modifica o armazenamento interno.

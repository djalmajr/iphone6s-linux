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

O nome novo impede que um módulo da candidata anterior seja confundido com um módulo recompilado para este kernel. O gerador de perfis tem uma seleção opt-in separada, descrita abaixo; os seletores de runtime/driver ainda não aceitam a candidata. Não há override de hash, carga forçada de módulo ou alteração do perfil padrão.

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

O [build completo](evidence/kernel-n71-pmd-build.json) terminou com sucesso em 15/10/2026, em 2489 segundos. O Image tem 52070912 bytes e SHA256 `c6c020756b970ebb77d1eb8e7975682385efacdbdefaacc78b70b8b8eb177246`. Os cinco artefatos copiados para o Mac tiveram seus hashes recalculados; Image.gz corresponde ao Image e a configuração só difere de power2 por LOCALVERSION. O DTB mantém o hash anterior. Source/config/Image/exports power2 foram preservados. O registro público usa `commit` para a base identificada por `base_commit` no resultado privado do checker; os oito pares de blobs e os oito patches permanecem iguais.

## Diagnósticos para a ABI nova

[build-n71-pmd-diagnostics.py](../scripts/build/build-n71-pmd-diagnostics.py) reconstrói os seis diagnósticos e o pin-cycle em uma pasta nova da VM. Os [62 inputs selados](evidence/n71-pmd-diagnostic-inputs.json) incluem o diagnóstico I2C com a correção UJM. Nenhum arquivo da ABI power2 é sobrescrito.

Para reproduzir o pacote na raiz de `iphone-linux-tools`:

```python
from pathlib import Path
import hashlib, io, json, tarfile

proof = json.loads(Path('docs/evidence/n71-pmd-diagnostic-inputs.json').read_text())
target = Path('runtime/n71-pmd-diagnostic-inputs.tar')
with tarfile.open(target, 'x', format=tarfile.USTAR_FORMAT) as archive:
    for name, expected in proof['inputs'].items():
        data = Path(name).read_bytes()
        assert len(data) == expected['bytes']
        assert hashlib.sha256(data).hexdigest() == expected['sha256']
        member = tarfile.TarInfo(name)
        member.mode = 0o644
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
assert target.stat().st_size == proof['canonical_tar']['bytes']
assert hashlib.sha256(target.read_bytes()).hexdigest() == proof['canonical_tar']['sha256']
```

O resultado deve ter 389120 bytes e SHA256 `ced3f7ea5957a8baf641a3aff7db03b35c40b8eec45edbd9afc5e3832af71820`. Transferir somente o pacote e o builder para a VM dedicada; não transferir chaves ou perfis privados.

O comando seguinte pressupõe que o build completo anterior já terminou com `build-result-private.json` real e verificado. Executar como `ubuntu`, nunca como root, mantendo as pastas da receita anterior:

```sh
python3 -B /home/ubuntu/build-n71-pmd-diagnostics.py \
  --inputs /home/ubuntu/n71-pmd-diagnostic-inputs-20261015.tar \
  --output-dir /home/ubuntu/n71-pmd-diagnostics-build-20261015 --check
```

`--check` não cria a saída nem compila. Confere pacote, source completo, release, Image/config/exports e fatos do build completo. Após essa verificação, repetir sem `--check` para compilar somente os sete módulos, com `W=1` e `KCFLAGS=-Werror`. O destino precisa continuar inexistente. O resultado privado registra ELF64/AArch64 relocável, ABI, imports resolvidos, parâmetros e hashes; não instala nem carrega os módulos. A fonte e Image/config/exports do kernel são novamente conferidos ao terminar.

Os testes do limite do pacote usam arquivos reais temporários, sem kernel ou telefone:

```sh
python3 -B -m unittest discover -s tests -p test_n71_pmd_diagnostic_inputs.py -v
```

Seis testes e seis mutações passaram no Mac e no ARM64. A primeira tentativa ARM excedeu o prazo externo depois de três testes básicos e duas mutações; uma repetição completa, apenas Python e com prazo total adequado, terminou aprovada. O preflight real depois encontrou uma comparação de tuplas com listas após serialização JSON e recusou a operação antes de criar a saída. A comparação agora normaliza somente os pares de blobs para listas, mantendo a igualdade exata da fonte. Os testes cobrem o roundtrip válido, alteração dos blobs e falta dos fatos de build. O pacote real de 62 fontes foi aceito pelo parser na VM.

Os [sete módulos](evidence/n71-pmd-diagnostics-build.json) foram compilados com W=1/Werror e modpost. A recusa de um pacote real corrompido não criou saída; o temporário foi removido. Os imports foram resolvidos contra os exports do kernel, e ELF, ABI e hashes dos módulos copiados para o Mac foram conferidos. Não houve instalação ou carga no iPhone. A correção do builder reutilizou o Image concluído; não exigiu outro build de kernel.

## Composição opt-in preparada

[integrate-source-kernel.py](../scripts/build/integrate-source-kernel.py) aceita explicitamente `--kernel-patchset n71-dart-serdev-pmd-v1`. Exige o registro público distinto [kernel-n71-pmd-build.json](evidence/kernel-n71-pmd-build.json), produzido do build completo real. A ausência desse registro, um registro power2 cruzado, qualquer divergência dos oito patches/blobs, Image/configuração/release ou export serdev recusa a operação antes de criar o destino.

A seleção PMD mantém GPIO/PMGR incorporados e recusa módulos antigos ou metadados de módulos no initramfs. A migração do NCM incorporado preserva as demais entradas e as identidades SSH. O perfil padrão continua intacto; selecionar PMD neste gerador não libera o carregamento pelos seletores de runtime/driver.

```sh
python3 -B -m unittest discover -s tests -p test_kernel_pmd_integration.py -v
```

O gate usa CLI real e kernels sintéticos não inicializáveis. Seis testes, incluindo cinco mutações, passaram no Mac e no ARM64. No Mac, os cinco testes power2, os 17 testes anteriores de integração e quatro mutações antigas afetadas também passaram. O [registro de preparação](evidence/n71-pmd-preparation-qualified.json) contém os inputs e hashes dos logs. Isso prova os limites do gerador, sem comprovar boot, Wi-Fi, HDQ ou carregamento no aparelho.

A [integração base real](evidence/n71-pmd-base-integration.json) também passou com o Image novo e o initramfs privado validado de power2: identidades SSH preservadas, perfil verificado e padrão intacto. Esse perfil ainda não contém o conjunto de runtime/firmware; não deve ser usado como candidato ao teste agrupado antes das etapas seguintes.

## Aceite no aparelho ainda pendente

O kernel, os sete diagnósticos e a integração base estão qualificados sem uso do telefone. Faltam reconstruir o conjunto Wi-Fi para a ABI PMD, ampliar os gates de runtime explicitamente e montar o perfil completo antes de uma sessão física reunindo DART/firmware com HDQ/UJM. Não solicitar outro DFU para repetir o fault conhecido sem a candidata pronta. Nenhuma ação é necessária no iPhone enquanto isso: ele pode permanecer no iOS bloqueado e carregando.

Wi-Fi nativo, telemetria e carga no Linux continuam sem comprovação. O patch não escreve registradores do carregador nem modifica o armazenamento interno.

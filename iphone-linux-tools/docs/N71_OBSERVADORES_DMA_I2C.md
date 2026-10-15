# Observadores DMA e reset I2C — 15/10/2026

## Resultado e limite

Os sete módulos de `pmd-observers-v1` foram compilados para `7.2.0-iphone6s-dart-serdev-pmd1` com W=1/Werror, um job e modpost. Total: 269312 bytes, com ELF AArch64, imports e ABI conferidos na VM e hashes/tamanhos novamente conferidos no Mac. Os baselines ARM64 executaram 324 cenários; as 108 mutações dos quatro gates Mac foram reutilizadas. As APIs de PCI/IOMMU/MMIO são modeladas nesses cenários. [Registro do build](evidence/n71-pmd-observer-build.json).

Nenhum módulo novo foi carregado no telefone. A integração de seleção/coletores e a prova física de Wi-Fi, bateria e alimentação continuam pendentes. O kernel, o perfil e os módulos PMD anteriores foram preservados. Não houve DFU ou solicitação ao operador nesta etapa.

## O que foi implementado

- **DMA:** opt-in `dma_observe`, IOVA `dma_iova` e getter root-only `dma_observation`. Requer driver_runtime/iommu_parent, sessão/power/provider retidos, brcmfmac vinculado e domínio DMA atual igual ao esperado. O getter serializa sessão e bind/unbind do endpoint, reutiliza o mapping do provider e faz até 16 reads DART. Não aloca, mapeia novamente, inicia DMA ou escreve registradores.
- **Saída DMA:** duas amostras com boottime, PA consultado pela API pública, validade, command/TCR/status/endereço raw de erro e quatro TTBRs do stream 0. `stable=1` indica igualdade das observações; PA zero pode significar ausência de mapping. Uma captura tardia pode ocorrer após liberação dos buffers e não representa necessariamente o instante do fault.
- **I2C:** `N71_I2C_RESET_TRACE` publica primeiro CTL, últimos cinco words completos, tentativas, amostras válidas e erro de amostragem. Usa somente leituras já existentes no reset e preserva dados após cleanup. Falha anterior ao controlador publica validade zero. O estado 0x010f continua recusado; esta etapa prepara a observação da hipótese UJM, sem alterar máscaras, polling, restauração ou controle de carga.

## Fontes e reprodução do pacote

Prerequisito: a VM dedicada `iphone6s-kernel-20261001`, com o kernel PMD e o checker já preparados conforme [N71_DART_PMD.md](N71_DART_PMD.md). Não instalar dependências no Mac. A VM existente tem 4 GiB e 2 CPUs; o builder usa somente um job.

O [manifesto](evidence/n71-pmd-observer-inputs.json) fixa os 64 arquivos do commit `8b62c9cd5c6bd1a1ef1144136ba7deadf94795da`. Para reconstruir o tar, na pasta `iphone-linux-tools` de um checkout que contém este documento e histórico completo:

```python
import hashlib, io, json, subprocess, tarfile
from pathlib import Path

root = Path.cwd()
proof = json.loads((root / 'docs/evidence/n71-pmd-observer-inputs.json').read_text())
prefix = root.name + '/'
raw = subprocess.check_output(['git', 'archive', '--format=tar', proof['source_head'], '--',
    *[prefix + name for name in sorted(proof['inputs'])]], cwd=root.parent)
data = {}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    for member in archive:
        if member.isdir():
            continue
        assert member.isfile() and member.name.startswith(prefix)
        name = member.name.removeprefix(prefix)
        with archive.extractfile(member) as stream:
            data[name] = stream.read()
assert set(data) == set(proof['inputs'])
output = io.BytesIO()
with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as archive:
    for name, value in sorted(data.items()):
        assert len(value) == proof['inputs'][name]['bytes']
        assert hashlib.sha256(value).hexdigest() == proof['inputs'][name]['sha256']
        info = tarfile.TarInfo(name)
        info.mode, info.size = 0o644, len(value)
        archive.addfile(info, io.BytesIO(value))
value = output.getvalue()
assert len(value) == proof['canonical_tar']['bytes']
assert hashlib.sha256(value).hexdigest() == proof['canonical_tar']['sha256']
folder = root / 'runtime/n71-pmd-observers-reproduction'
folder.mkdir(mode=0o700)
path = folder / 'inputs-v3-private.tar'
with path.open('xb') as stream:
    stream.write(value)
path.chmod(0o600)
```

Tar esperado: 399360 bytes, SHA256 `4c83ad67d47cc1e31a0da53868ed22d6daee0c460606d6664f178d6cedb85681`. Os arquivos extraídos são tratados como dados; nenhum Python arquivado é executado.

## Compilação na VM

Na execução registrada, os builders `scripts/build/build-n71-pmd-observers.py` e `build-n71-pmd-diagnostics.py`, mais o tar, foram transferidos por `multipass transfer` para uma pasta nova 0700 `/home/ubuntu/n71-pmd-observer-builder-v3-20261015`. O segundo builder tem hash fixado pelo primeiro e fornece a checagem do kernel preservado. Não reutilizar uma saída já existente.

```sh
multipass start iphone6s-kernel-20261001
multipass exec iphone6s-kernel-20261001 -- mkdir -m 700 \
  /home/ubuntu/n71-pmd-observer-builder-v3-20261015
multipass transfer scripts/build/build-n71-pmd-observers.py \
  scripts/build/build-n71-pmd-diagnostics.py \
  runtime/n71-pmd-observers-reproduction/inputs-v3-private.tar \
  iphone6s-kernel-20261001:/home/ubuntu/n71-pmd-observer-builder-v3-20261015/
multipass exec iphone6s-kernel-20261001 -- python3 -B \
  /home/ubuntu/n71-pmd-observer-builder-v3-20261015/build-n71-pmd-observers.py \
  --inputs /home/ubuntu/n71-pmd-observer-builder-v3-20261015/inputs-v3-private.tar \
  --output-dir /home/ubuntu/n71-pmd-observers-build-v3-20261015 --check
```

Repetir o comando sem `--check` para compilar. Esperados: `N71_OBSERVERS_BUILT modules=7` e `N71_OBSERVER_KERNEL_PRESERVED`. O `build-result-private.json` registra hashes, imports, parâmetros, ABI e fontes. Copiar somente esse registro, os sete `.ko` listados nele e os dois logs de build para `runtime/` privado; conferir os hashes novamente.

Os quatro baselines usaram os pares Python/C `test_n71_dma_observe`, `test_n71_dma_live`, `test_n71_i2c_controller`, `test_n71_i2c_power_diagnostic` e os suportes C `n71_i2c_genpd`/`n71_i2c_controller_observe`, copiados para `sources/tests` da saída nova. No Python da VM, importar esses quatro módulos, atribuir `MUTATIONS=()` somente em memória e executar seus testes via unittest com `PYTHONPATH` apontando para essa pasta. Resultado registrado: 100+58+81+85 cenários, quatro métodos aprovados. Isso executa os baselines, sem repetir crashes esperados das mutações já aprovadas no Mac; os arquivos dos testes não são alterados.

## Falhas preservadas e recursos

As duas primeiras compilações recusaram colisões de nomes com macros Linux: o callback `guard` virou `validate`; o ponteiro local `current` virou `row`. A fixture agora define ambas as macros antes de incluir o helper. Não foram usados undef, supressão de warnings ou pins de módulos antigos alterados. Receitas e hashes de cada tentativa estão no histórico Git; logs permanecem privados.

Após copiar e verificar os artefatos, foram removidas somente as quatro pastas próprias das tentativas recusadas e dois tars locais obsoletos. Os logs de falha, o pacote atual, os artefatos e o build de kernel foram mantidos. A VM foi parada com `multipass stop iphone6s-kernel-20261001` e o estado Stopped foi confirmado. Nenhum painel adicional foi aberto.

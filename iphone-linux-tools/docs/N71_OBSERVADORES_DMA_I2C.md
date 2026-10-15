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

## Seleção e perfil do runtime

O catálogo novo é optativo. Exportar `IPHONE_LINUX_PMD_DIAGNOSTICS=pmd-observers-v1` e apontar `IPHONE_LINUX_PMD_SOURCE_RECEIPT` para o receipt privado dos inputs PMD preservados. O seletor primeiro qualifica a base antiga, depois confere os 64 inputs novos e o mapa dos sete módulos compilados. Os pins antigos continuam válidos para os perfis anteriores.

O perfil privado `runtime/n71-observers-runtime-profile-20261015` contém os dois diagnósticos reais e cinco módulos WCC, além do payload e das identidades preservados. Sua composição manteve os 115 arquivos de origem conferidos. O comando local abaixo valida o perfil/firmware sem SSH, USB ou carga de módulo:

```sh
python3 -B scripts/host/n71-runtime-session.py \
  --profile runtime/n71-observers-runtime-profile-20261015/deployment.json \
  --action acquire --firmware-dir runtime/n71-trusted-firmware-20261010 --check
```

As variáveis acima também devem estar definidas nesse comando. A Session confere bytes e catálogo novamente antes de acrescentar `dma_observe=1 dma_iova=0x3ffff028` ao único insmod existente. A interface anterior mantém suas opções anteriores.

## Captura conjunta em um boot

Preparar o módulo I2C e o roteiro antes do DFU. Com o boot confirmado por SSH, `n71_i2c_trace_command.prepare(root, boot_id)` seleciona o módulo novo do catálogo. Transferir somente esse arquivo para o diretório privado indicado, conferir novamente seu SHA/tamanho e executar o comando gerado. Ele exige boot/ABI corretos e ausência dos diagnósticos WLAN/PCIe. A sequência é inspect, configure e read-hdq-control, interrompida na primeira ação negativa. Os dois getters de limpeza são conferidos antes do unload normal; recurso retido impede prosseguir. O dmesg filtrado inclui RESET_TRACE mesmo em uma saída negativa. Os estados aceitos de reset e os acessos ao carregador permanecem os do módulo compilado.

Depois de comprovar o unload I2C, usar acquire, assign, start e observe com `n71-runtime-session.py`, sempre com um diretório de saída novo e o anterior em `--source`. Não usar reacquire para repetir um resultado já conhecido. No start, o coletor DMA confirma boot, ABI e opções antes de driver-publish. O arquivo bruto e o receipt são privados; a prova `dma-observer-proof-private.log` segue os hashes e cópias do journal em observe, retomada e stop. Um receipt com conteúdo ou boot divergente é recusado antes de outro efeito.

O leitor admite até 100 getters com pausa de 0,1 s, ou 20 com pausa de 1 s se o sleep fracionário não estiver disponível. Cada getter tem duas amostras, no máximo 16 leituras de registradores. O parser aceita até 256 KiB; uma saída maior é recusada e mantida privada, com encerramento do processo próprio. Esse orçamento limita a aceitação dos dados, não é uma quota rígida do arquivo enquanto outra operação está em curso. A prontidão tem prazo de 5 s e o coletor usa prazo absoluto de 50 s. Erros e amostras parciais são preservados. Uma falha da captura não substitui a exceção original da publicação.

O getter usa session_lock/device_lock e pode aguardar o término da publicação. Seus horários são os das leituras efetivas; o fault do dmesg tem seu próprio horário. Uma leitura posterior não prova o mapeamento no instante da falha. PA zero não conta como mapeamento, e iommu_iova_to_phys é uma consulta ao domínio de software, não uma prova de tradução física pelo DART. Ausência de amostras completas também deve ser registrada.

Ao terminar, stop deve comprovar a limpeza independente dos módulos, PCIe e REG_ON. Salvar/verificar snapshot, fazer sync e retornar ao iOS para recarregar dentro do prazo da sessão. A perda de USB após o retorno é tratada operacionalmente como tela de bloqueio; não exige confirmação visual. O console não precisa ser operado.

## Provas e limites atuais

Os testes locais exercitam o shell gerado numa árvore descartável, processos leitores reais, arquivos privados e o ciclo completo do journal com telefone/perfil modelados. As provas do build ARM64 continuam separadas. Não há nova comprovação física de Wi-Fi, bateria ou carregamento nessa integração; os resultados do último boot físico permanecem em `N71_SESSAO_PMD_HDQ.md`. Os registros históricos de build descrevem o instante da compilação e não são reescritos para indicar integração posterior.

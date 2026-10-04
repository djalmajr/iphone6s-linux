# Descoberta PCIe N71 após readback do latch

## Decisão e alcance

O último teste confirmou controle GPIO10 `80→81→80` por máscara1, com
readback e restore. O banco187/bit2 ficou0 e o gate então bloqueou PCIe.
Esses fatos permanecem em [evidência física](evidence/n71-reg-on-latch80-physical.json).

A revisão do getter Apple mostrou um pedido de mode1 antes da leitura;
nosso diagnóstico apenas leu o banco, com controle80/81 classificado como
mode2. Sem a tabela opcional, chamar o setter não garante mudança de modo.
O banco ainda não foi qualificado como monitor da saída dirigida ou do
rail. Portanto, não usar seu zero como prova de falta de alimentação,
nem trocar bits de modo para obter um número esperado.

O próximo experimento faz **uma tentativa delimitada de descoberta de
endpoint**, após readback fresco do latch. A hipótese a testar é se o
endpoint responde quando o controle qualificado está81. Não presume
rail ativo e não habilita DMA, driver de rádio, firmware ou tráfego Wi-Fi.
A prova decisiva será link válido, identidade e COMMAND com bus-master
limpo, pelo caminho já implementado; timeout continua sendo resultado
negativo, sem identificar sozinho a causa.

## Pré-condições antes de um único boot

1. Kernel, módulos, fonte, configuração, hashes e ABI selecionada conferidos.
   Para o bundle, exigir gates reais de [composição](N71_KERNEL_BUNDLE.md);
   não reutilizar módulo da ABI anterior.
2. Perfil separado, snapshot restaurável, init USB preservado e saída SSH
   com identidade estrita. Manter cabo/porta definidos pelo operador.
3. Recursos/clocks/reset/tunables específicos do N71, sem aliases de A10.
   O prefixo anterior confirmou root1004106b, sem endpoint/DMA; isso não
   comprova o comportamento do kernel novo antes de testá-lo.
4. Módulo REG_ON usa o mesmo parent/regmap simple-mfd-i2c; sem rebind,
   mudança de drive/mode, transmissão HDQ ou programação de carga.

## Sequência da sessão

1. Validar release, SSH/HTTP e restore; confirmar UART5/I2C1 desativados.
   Transferir módulos externos privadamente, conferir hash/ABI no destino.
2. Carregar observador REG_ON com `run=1`, sem argumento de ativação no
   insmod. Esta tentativa exige original80, owner exato e nenhuma pendência
   anterior. Estado diferente encerra a tentativa sem forçar configuração.
3. Fazer uma aquisição pela API já qualificada; exigir active1/pending1,
   original80 e getter `control` com `N71_REG_ON_CONTROL_READBACK value=81`.
   O getter só lê914 sob os locks existentes. Registrar o banco187 também,
   deixando explícito que é uma amostra sem qualificação elétrica.
4. Fazer uma tentativa PCIe com `run=1 enumerate=1`. O diagnóstico valida
   mapas/domínios, mantém PERST, prepara clocks/porta, libera reset e espera
   100ms antes do treinamento. Polling de link é limitado; identidade só
   é lida após predicate88/bit0 alto, e COMMAND não pode ter bus-master.
   Nenhum host PCI é registrado para um driver de rádio nessa operação.
5. Conferir `N71_PCIE_RESET_RESTORED asserted=1 readback=1` e
   `N71_PCIE_POWER_RELEASED powered=0 attached=0`. Falha de cleanup deve
   permanecer explícita; não contar apenas exit0 do insmod como prova,
   pois registro de driver não equivale a sucesso do probe.
6. Remover diagnóstico PCIe; liberar REG_ON pela API existente, exigir
   readback80/active0/pending0 antes de remover seu módulo. Não apagar
   pendência se restore falhar, nem repetir treinamento automaticamente.
7. Conferir SSH/HTTP, salvar snapshot/sync e retornar ao iOS para medição.
   Não calcular carga Linux com um baseline anterior à preparação.

Os nomes de arquivos/getters são interfaces para o coletor; o operador não
precisa ler nem digitar no console do iPhone. Só haverá DFU quando candidata
e gates estiverem prontos, agrupando as coletas que couberem nessa sessão.

## Resultados que não encerram a issue

Readback81 não mede tensão. Link/identidade não demonstram firmware, Wi-Fi,
DART/DMA ou carga sustentada. Amostra0 não será rebatizada como1. Ausência
de endpoint mantém a hipótese de alimentação, CLKREQ/PHY/reset ou outra
sequência aberta; não autoriza copiar configuração elétrica de outra placa.
A primeira execução física do bundle está registrada abaixo; a evidência histórica
da baseline permanece separada.

Os getters/registros novos compilaram Werror/modpost para a ABI baseline
em diretório exclusivo; ELF/AArch64/vermagic foram conferidos e a fonte
funcional permaneceu sem diff. Essa prova não permite carregar os mesmos
binários no bundle: o rebuild correspondente ao Image novo ainda é exigido.

## Coletor reproduzível do bundle

O rebuild e a composição real passaram nos [gates do bundle](N71_KERNEL_BUNDLE.md).
`scripts/host/n71-link-session.py` exige a ABI nova e os hashes dos módulos
registrados; não seleciona o perfil padrão nem inicia DFU. Confira primeiro
somente os arquivos locais:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-bundle-diagnostic-profile-20261003/deployment.json" \
  --check
```

Depois de um boot explicitamente selecionado com snapshot restaurado e SSH/HTTP
confirmados, execute em saída nova:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-bundle-diagnostic-profile-20261003/deployment.json" \
  --output-dir "$PWD/runtime/NOVA-SESSAO-N71"
```

O coletor recusa diagnóstico PCIe prévio nesse boot, módulos já carregados,
UART5/I2C1 ativos, ABI divergente e estado original diferente de80. Depois da
aquisição, exige estado ativo/pendente e controle81 fresco; repete esses testes
no aparelho imediatamente antes do único insmod PCIe. Amostra187 continua
observação, sem gate elétrico. Logs são exclusivos e privados; repetir uma
etapa não envia o comando outra vez. Não há autoload ou retry de treinamento.

Falhas e timeout SSH passam por cleanup: reset/domínios PCIe precisam de
registros positivos antes do unload; restore REG_ON precisa de readback80 e
pendência zero antes de unload. Observação recusada não escreve o controle.
O resultado privado distingue endpoint ausente, falha do experimento e cleanup
não comprovado. Exit0 com link `-110` registra um experimento negativo concluído
com restauração; não significa Wi-Fi habilitado. O script não reinicia o
aparelho: depois do cleanup, conferir serviços e usar `return_ios.py`, que
valida snapshot/sync antes do retorno. Se cleanup não passar, preservar logs
e tratar a falha antes de continuar.

Gates sintéticos, sem dispositivo ou dados privados:

```sh
python3 -m unittest discover -s tests -p test_n71_link_session.py
python3 tests/run_n71_link_session_mutations.py
```

## Primeira execução física do bundle — 2026-10-03

Uma sessão com um DFU manual confirmou a release selecionada, restore, Bash e
HTTP. Controle914 foi80→81→80 com máscara1/readbacks e pendência zero ao final.
O banco187 continuou20/bit2=0. Mesmo assim, o link passou: port88=00000005,
error0 em12 leituras; endpoint43a314e4 (vendor14e4/device43a3), COMMAND com
bus-master limpo. Isso confirma que aquela amostra0 não deve bloquear a
descoberta de endpoint. Não mede tensão nem qualifica o banco como power-good.

Reset/readback, liberação dos quatro domínios e unload foram confirmados. No
mesmo boot, GPIO2 foi observado sem escrita; serviços continuaram respondendo.
Snapshot/sync e retorno por software ao iOS passaram. Bateria iOS100→100 nesse
intervalo não mede corrente ou carga sustentada. [Fatos selecionados e hashes
dos logs privados](evidence/n71-bundle-first-physical.json).

O próximo desenvolvimento é o host PCI: recursos/BARs, IRQ e DART precisam de
contrato e cleanup antes de qualquer bus-master/rádio. A configuração atual
tem BRCMFMAC como módulo, mas BRCMFMAC_PCIE está desativado no Image. O
[conjunto externo PCIe/MSGBUF](N71_WIFI_MODULES.md) compilou para a mesma ABI,
preservando configuração e Image; não foi carregado no telefone. Identidade
PCI ainda não seleciona revisão, firmware ou calibração. Agrupar novos gates numa
candidata antes de pedir outro DFU; fazer fonte/builds/testes offline e atualizar
módulos por SSH enquanto uma sessão útil estiver ativa.

## Próxima candidata — inventário de configuração sem escrita

O PCI-ID físico 43a3 é `BRCM_PCIE_4350_DEVICE_ID` na
[fonte fixada dos IDs](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/include/brcm_hw_ids.h).
O [match do driver PCIe](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)
aponta para BCM4350. A seleção de firmware ainda depende do chip e da revisão
internos, obtidos pelo driver após integrar BARs e host. O byte de revisão PCI
não substitui essa identificação. Nada foi carregado no rádio.

`n71-pcie-inventory.h` recebe somente um callback de leitura. Lê revisão,
classe, header tipo 0, seis BARs brutos, subsystem, linha/pino de IRQ e headers
convencionais PCIe/MSI/MSI-X. Não sonda BAR escrevendo FFFFFFFF, deduz tamanho
ou endereço ativo, toca MMIO de BAR ou habilita interrupção. Limita 63 leituras
de configuração, recusa ponteiros inválidos ou cíclicos, capacidades conhecidas
duplicadas e identidade/COMMAND divergentes no final. Bus-master inicial
bloqueia antes das outras leituras. A saída permanece intacta em qualquer recusa.

O adapter é explícito: `config_inventory=1` exige `run=1 enumerate=1`. Depois
do link, verifica port88 fresco antes de cada leitura. O diagnóstico mantém
reset e domínios sob sua responsabilidade e executa cleanup também em falha do
inventário. Ausência de MSI é informação, não autorização para fallback de IRQ.
[O kernel documenta](https://docs.kernel.org/PCI/pci.html#device-initialization-steps)
ativação, recursos, DMA e IRQ como passos próprios da inicialização.

[Build e gates offline](evidence/n71-pcie-config-inventory.json) passaram em
Mac e ARM64: erros em cada leitura, listas malformadas, mudanças tardias,
limite de 63 leituras e dez mutações por asserção. O módulo novo compilou com
Werror/modpost e os exports do bundle; ELF, vermagic e hash foram recalculados
no Mac. Default false; Image, perfis e módulos físicos anteriores preservados.
**O inventário foi confirmado na coleta de 2026-10-04, registrada abaixo.** O modo padrão do coletor
continua fixando o módulo físico anterior. O modo `--config-inventory` seleciona
o hash novo registrado, exige sua procedência no perfil e valida o resultado
completo: endpoint observado, COMMAND sem bus-master, seis BARs ordenados,
headers das capacidades e orçamento de leitura. Saída incompleta ou duplicada
recusa o experimento e executa o mesmo cleanup. Não habilita host, DMA ou rádio.

A candidata privada foi composta mantendo payload, initramfs, DTB e identidades
do perfil físico anterior byte a byte; só o módulo externo selecionado mudou.
O gate local não acessa USB nem SSH:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-inventory-candidate-20261003/deployment.json" \
  --config-inventory --check
```

Depois do próximo boot agrupado, com serviços e restauração confirmados, usar
o mesmo comando substituindo `--check` por `--output-dir` em diretório novo.
Sem uma continuação explicitamente verificada, o coletor recusa diagnóstico prévio.
Os 14 testes do coletor e 12 mutações executadas provam os contratos sintéticos;
não representam uma coleta física do inventário.

Para reproduzir os gates sem aparelho:

```sh
python3 -m unittest discover -s tests -p test_n71_pcie_inventory.py -v
python3 tests/run_n71_pcie_inventory_mutations.py
```

O build externo segue [a receita do bundle](N71_KERNEL_BUNDLE.md), em novo M e
com `vmlinux.symvers` exato; conferir o módulo antes de transferir. Uma futura
coleta deve selecionar manifesto, perfil e coletor compatíveis, com snapshot
e restore verificados, e agrupar inventário com novos gates de host/DART/HDQ.
Não pedir DFU só para confirmar fatos já obtidos.

## Candidata de sizing pelo núcleo PCI — 2026-10-04

O novo `host_scan=1` exige run, enumerate e config_inventory. Depois do
inventário, cria bridge temporário com ECAM fixado, bus0..1 e janelas ADT
selecionadas; chama `pci_scan_root_bus_bridge` sob o lock de rescan. A fonte
fixada só permite bind depois de PCI_DEV_ALLOW_BINDING; esta operação não
chama `pci_bus_add_devices`, `pci_host_probe` ou atribuição de recursos.
Os dispositivos aparecem temporariamente em sysfs. Não há driver de rádio,
DMA, MSI configurado, BAR mapeado ou firmware nesta candidata.

`n71-pcie-scan-config.h` captura IDs/classes, COMMAND, BARs/ROM e
bridge-control antes de escrever. Exige DMA e ROM desativados, bus0/1 e reset
secundário livre. Só permite suspender/restaurar decode, sizing/restauração
de BARs/ROM com decode suspenso e MASTER_ABORT do bridge-control. COMMAND usa
writew para preservar STATUS. Requisições iguais ao valor atual são no-op;
clear de Secondary STATUS só é emulado se não há erro pendente. Outras
mudanças são recusadas, com erro persistente e limite de tentativas.

O adaptador reporta dispositivos/recursos, faz stop/remove do bus e restaura
configuração com readback antes de PERST/power/REG_ON. Erro de configuração
permanece falha mesmo se a função PCI retornar0. A restauração tem caminho
independente do erro e do orçamento de leitura; não reativa decode quando
BAR/ROM não foi restaurado. Endereços reportados pelo núcleo PCI são recursos
descobertos, sem prova de mapeamento ativo, tradução NVMMU ou acesso ao chip.

[Build selecionado](evidence/n71-pcie-host-scan.json): módulo35072 bytes,
SHA256 `1fe1b30800e23b47a02dbc92996ac29326c3e60953abcf04cae2493d6d38f002`,
mesma release7.2.0-iphone6s-dart-serdev1. Werror/modpost/ELF/vermagic e símbolos
PCI scan/walk/stop/remove/free passaram; fonte/Image/config/exports ficaram
iguais. O primeiro build revelou colisão com a macro ARM64 `current`, corrigida
para `observed`; a build válida foi feita em diretório novo. Logs anteriores
foram preservados. Isso ainda é prova de compilação, não sizing físico.

Na VM dedicada, reproduzir após os gates do [bundle](N71_KERNEL_BUNDLE.md),
usando M novo com cópia das fontes públicas `phone/kernel/*.c`, `*.h` e
Makefile. A execução registrada usou o caminho abaixo, que já existe:

```sh
set -eu
umask 077
work_dir=/home/ubuntu/kernel-n71-bundle-source-20261002
build_dir=/home/ubuntu/kernel-n71-bundle-build-20261002
module_dir=/home/ubuntu/n71-scan-inputs-20261004-v2/phone/kernel
python3 scripts/build/kernel_bundle.py check "$work_dir"
env LOCALVERSION= make -C "$work_dir" O="$build_dir" ARCH=arm64 -j2 \
  KCFLAGS=-Werror M="$module_dir" \
  KBUILD_EXTRA_SYMBOLS="$build_dir/vmlinux.symvers" modules
python3 scripts/build/kernel_bundle.py check "$work_dir"
```

Conferir os hashes de config/Image/exports e do módulo contra o registro
antes/depois; não instalar ou forçar símbolos. O módulo externo requer1GiB
livre; isso não altera o gate8GiB para um Image novo. Os testes do contrato
passaram no Mac e ARM64: três testes compilados, 11 cenários de lifecycle,
14 mutações de configuração e seis de lifecycle por asserção. O backend/API
PCI das fixtures é sintético; a build nativa usa headers/exports reais.

```sh
python3 -m unittest discover -s tests -p 'test_n71_pcie_scan_*.py' -v
python3 tests/run_n71_pcie_scan_mutations.py
python3 -m unittest discover -s tests -p test_n71_scan_result.py -v
python3 tests/run_n71_scan_result_mutations.py
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-host-scan-candidate-20261004/deployment.json" \
  --host-scan --check
```

Esse perfil preserva payload/DTB/initramfs/identidades do boot físico anterior
byte a byte, troca somente o módulo externo e não muda o perfil padrão. O
coletor exige proveniência/hash novos, inventário, resultado PCI único,
COMMAND sem bus-master, seis recursos BAR e cleanup comprovado. Sysfs PCI
deve estar vazio antes/depois; falha impede unload sem apagar os logs.
Para executar depois de boot/restore/SSH confirmados, substituir `--check`
por `--output-dir` novo diretamente em runtime. Não repetir no mesmo boot.
O script não reinicia o telefone. A primeira sessão física deve reunir esses
gates com serviços, snapshot e observações sem escrita dos recursos HDQ/DART.

O próximo host funcional ainda precisa de atribuição/restauração de recursos,
NVMMU/DART com identidade de stream e IRQ qualificados, depois identificação
interna do chip, firmware/calibração e testes Wi-Fi. Esse sizing temporário
nunca habilita bus-master para contornar uma dessas etapas.

## Base do host — ECAM e janelas de referência

`n71-pcie-ecam.h` preserva as coordenadas observadas: raiz bus0/devfn08 em
ECAM+8000 e endpoint bus1/devfn00 em ECAM+100000. O contrato limita a leitura
a essas duas funções, com aperture de 16 MiB e tamanhos de 1, 2 ou 4 bytes
naturalmente alinhados e contidos nos 4 KiB da função. Não registra host. O
callback recebe um DWORD alinhado; extração só publica saída após sucesso.
Clock, recurso e link continuam sob responsabilidade do futuro adapter.

[Provas e hashes](evidence/n71-pcie-ecam.json): matriz de 512 coordenadas,
limites de todos os offsets/tamanhos, nove mutações por asserção em Mac/ARM64,
UBSan no Mac e objeto kernel Werror/modpost. Sem novo I/O físico ou reboot.

```sh
python3 -m unittest discover -s tests -p test_n71_pcie_ecam.py -v
python3 tests/run_n71_pcie_ecam_mutations.py
```

A captura Pongo preservada e o ADT oficial têm os mesmos 56 bytes de `ranges`.
O formato Apple é packed little-endian flags32/pci64/cpu64/size64; não copiar
como células FDT. Duas janelas de referência:

| Flags | Base PCI | Base CPU | Tamanho |
| --- | --- | --- | --- |
| 43000000 | 620000000 | 620000000 | 1a0000000 |
| 02000000 | c0000000 | 7c0000000 | 40000000 |

Todos os valores da tabela são hexadecimais. As referências também concordam
com mapper-apcie1/reg0 e DART IRQ248. Isso não qualifica sozinho o mapeamento
Linux RID/SID, roteamento de BAR/IRQ ou DMA. Esses gates continuam obrigatórios.
A primeira tentativa de interpretar endereços como pares high/low de células
FDT produziu valores incoerentes; a leitura packed64 e comparação byte a byte
com o ADT oficial corrigiram o formato antes de qualquer escrita.

Para obter o ADT oficial, use o [leitor público](../scripts/research/apple-n71-map.py),
que fixa o download Apple e salva os dados privadamente, sem executar firmware:

```sh
python3 scripts/research/apple-n71-map.py --output-dir "$PWD/runtime/SUA-REFERENCIA"
```

Se o ADT já estiver salvo, reutilize-o sem download. Confira a janela offline
com `n71-adt-private.bin` já decodificado:

```python
import hashlib, json, struct
from pathlib import Path
e = json.loads(Path('docs/evidence/n71-pcie-ecam.json').read_text())['host_reference']
raw = Path('runtime/SUA-REFERENCIA/n71-adt-private.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == e['official_decoded_sha256']
w = e['official_verification_window']
chunk = raw[w['offset']:w['offset'] + w['bytes']]
assert hashlib.sha256(chunk).hexdigest() == w['sha256']
assert raw[w['offset'] - 36:w['offset'] - 30] == b'ranges'
assert len(list(struct.iter_unpack('<IQQQ', chunk))) == 2
```

A captura bruta, tabelas, logs e firmware continuam privados. Não há changeset
de DT, configuração de IOMMU ou ativação de rádio nesta implementação.

## Inventário físico e sizing direto — 2026-10-04

[A primeira coleta](evidence/n71-inventory-and-scan-first-physical.json)
confirmou link, endpoint14e4:43a3, revisão PCI8, subsystem106b:10fe,
BAR0/2 do tipo64 bits, PCIe/MSI presentes e MSI-X ausente. A revisão PCI
não identifica a revisão interna usada para selecionar firmware.

O núcleo PCI tentou alterar COMMAND0→400(INTx disable) antes do sizing;
o contrato recusou e manteve o primeiro erro. Os dois dispositivos temporários
foram removidos, configuração restaurada com readback, PERST/domínios liberados,
REG_ON80 restabelecido e ambos os módulos removidos. Nenhuma escrita de probe
foi aceita; a restauração fez escritas dos valores capturados. Tamanhos de BAR
não foram comprovados nesse scan. SSH/HTTP e snapshot passaram depois dele.

O próximo modo `bar_sizing=1` mede somente as seis palavras BAR do endpoint,
sem registro de dispositivos PCI. Exige inventário, recusa host_scan simultâneo,
suspende decode por COMMAND de16 bits, mede máscaras FFFFFFFF e restaura os
valores capturados antes de divulgar tamanhos. Pares64, atributos, tamanhos
potência de2 e limites das janelas selecionadas são validados. Em erro,
restauração/readback continua obrigatória; tamanhos não são publicados.
Não atribui endereços, acessa MMIO dos BARs, habilita DMA/IRQ ou carrega firmware.

[Build externo selecionado](evidence/n71-pcie-bar-sizing.json):37824 bytes,
SHA256 `11be3fc8ca8d74d80c9116f9c0133a25a2bfd39365aa3ae8aa6bf0246c73ae38`.
Compilação ARM64/Werror/modpost, ELF/ABI e preservação do kernel passaram.
Harness C no Mac e ARM64 injeta falhas em todas as leituras/escritas; seis
mutações compiladas falham por asserção. Esta evidência ainda é de build.
A seleção e continuação física serão explícitas, mantendo logs históricos.

```sh
python3 -m unittest discover -s tests -p test_n71_pcie_bar_sizing.py -v
# Na receita de módulo externo acima, usar um diretório M novo;
# a execução registrada usou /home/ubuntu/n71-bar-inputs-20261004/phone/kernel.
```

### Resultado físico e continuação no mesmo boot

[A medição direta passou](evidence/n71-bar-sizing-first-physical.json):
BAR0=32KiB(máscaraffff8004/ffffffff), BAR2=4MiB(ffc00004/ffffffff).
BAR4/5 são não implementados. Foram66 leituras,13 pedidos,10 escritas de
probe e zero recusas; restauração completa/readback, reset/domínios, REG_ON80,
unload e PCI sysfs vazio passaram. SSH/HTTP continuaram e novo snapshot foi
salvo. Esse experimento usou o boot já aberto: nenhum DFU/PIN adicional.
Ainda não atribuiu BARs, acessou chip-MMIO ou habilitou DART/DMA/rádio.

O coletor permite continuação somente com `--previous-clean` explícito:
resultado privado com cleanup sem erros e endpoint/ABI exatos, logs finais
positivos e todas as linhas N71 com timestamps iguais ao dmesg fresco, na
mesma ordem. Se a prova anterior contém boot_id, deve coincidir também.
Prova antiga sem boot_id precisa do histórico timestampado completo; nenhum
valor é acrescentado retroativamente. Módulos carregados, PCI ocupado ou
histórico divergente encerram a execução antes da aquisição de REG_ON.

As linhas antigas ficam nos logs completos e são filtradas somente na
interpretação da nova coleta. Não limpar dmesg. Módulos vão a diretório novo
exclusivo em /run, com hashes conferidos, preservando os arquivos anteriores.
Não existe retry automático: cada continuação é uma operação explícita.

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-bar-candidate-20261004/deployment.json" \
  --bar-sizing \
  --previous-clean "$PWD/runtime/n71-host-scan-session-20261004" --check
```

No boot correspondente já ativo, substituir --check por --output-dir em
diretório novo diretamente sob runtime. A sessão anterior precisa pertencer
a esse mesmo boot; não reutilizar a prova depois de retornar ao iOS.
Os modos host_scan e bar_sizing são mutuamente exclusivos e implicam inventário.
Antes de mudar os binários, compor perfil privado preservando payload/DTB/
initramfs e identidades; os modos antigos mantêm seus hashes registrados.

## Identificação interna pelo BAR0 — 2026-10-04

O driver brcmfmac fixado seleciona ChipCommon por configuração80 e lê chipid
no offset0 de18000000. A [referência selecionada](evidence/n71-chip-id-reference.json)
registra fontes, hashes e máscaras. O driver completo habilita bus-master ao
adquirir recursos; não é usado para essa identificação limitada antes do DART.

O modo `chip_id=1` exige inventário e sizing fresco32KiB/64-bit BAR0, sem
decode/master inicial. Reivindica32KiB em CPU7c0000000, rota ADT PCIc0000000,
e recusa região ocupada. Captura root memory-window20 e BAR0_WINDOW80; configura
BAR0c0000004/high0, bridge memory-windowc000c000(1MiB), ChipCommon18000000 e
apenas MEM-enable nos COMMAND de16 bits. Revalida COMMAND e link antes de
uma leitura32. Restaura decode/janelas/BARs/config com readback e libera o mapa.
Não toca BAR2 MMIO, core-reset, watchdog, OTP, IRQ, DMA ou firmware.

[O teste físico passou](evidence/n71-chip-id-first-physical.json):
raw17084350, **BCM4350 revisão interna8**, AXI; uma leitura MMIO e53 de config.
Sizing, restore/readback da rota e config, unmap/release, reset/domínios,
REG_ON80/unload e PCI vazio passaram. SSH/HTTP e snapshot passaram após
cleanup. Foi continuação do mesmo boot, sem DFU/PIN adicional.

[O módulo selecionado](evidence/n71-pcie-chip-id-build.json) tem42008 bytes,
SHA256 `8ade6fd83a47df5e8bbb882fdbb53cd4ef118e3a6185274549f7b4b88b717941`.
Kernel/payload/DTB/initramfs/identidades preservados. Harness C de falhas e seis
mutações passaram no Mac/ARM64; Werror/modpost/ELF/ABI passaram. A leitura de
chip-ID não demonstra EROM, BAR2/TCM, DART/DMA, IRQ, firmware ou associação Wi-Fi.

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-chip-candidate-20261004/deployment.json" \
  --chip-id --previous-clean "$PWD/runtime/n71-bar-session-20261004" --check
python3 -m unittest discover -s tests -p test_n71_pcie_chip_id.py -v
python3 -m unittest discover -s tests -p test_n71_chip_result.py -v
```

No boot correspondente, usar saída nova em vez de --check. `--chip-id`
exclui --bar-sizing/--host-scan, mas valida também o sizing. Cleanup é
conservador: qualquer leitura de config exige registro positivo de restore;
uma falha precoce de captura pode exigir análise antes de unload mesmo que
a captura ainda não tenha escrito. Isso mantém uma recusa segura quando
contagens não bastam para distinguir erro de captura e rota parcialmente alterada.

## DART separado — observação física no mesmo boot

O [DART S5L do bundle fixado](evidence/n71-dart-observe-build.json) tem COMMAND0,
TCRc (quatro bytes/streams), ERROR10 e16TTBRs em40–7c. Na N71, o nó DART é
**602008000**, distinto da NVMMU602004000 do recursoPCI4. O modo
`dart_observe=1` valida endereço/tamanho, compatíveis, IRQ248, status disabled,
domínio de energia e ausência de device/posse antes de mapear. Mantém os quatro
domínios PCI adquiridos; link/IDs/COMMAND sem decode/master são conferidos
antes de cada leitura e novamente ao terminar. Não ativa provider, cria IRQ,
escreve DART, invalida TLB ou limpa ERROR.

[A observação física passou](evidence/n71-dart-first-physical.json), como quarta
experiência do mesmo boot supervisionado:38 leituras/39 gates, duas amostras idênticas,
COMMAND00000f02,TCR00000000,ERROR00000100 (fault flag desativada), quatro
streams com tradução desativada e16/16TTBRs com valid-bit definido. Unmap,
release, reset/domínios, PCI vazio e REG_ON80/unload passaram. SSH, HTTP
`/cgi-bin/status` e snapshot posterior passaram. Nenhum DFU/PIN/reboot adicional.

TCR0 **não significa tabelas vazias**. Os ponteiros completos não foram
publicados. O probe/remove do driver upstream desativa streams, limpa TTBRs e
limpa ERROR; ativá-lo agora apagaria esse estado antes da qualificação de
SID/IRQ e da conservação das tabelas. Este teste confirma acesso estável aos
registros selecionados; não comprova stream routing, DMA, IRQ, rádio ou carga.

Reprodução do módulo externo na mesma VM/kernel/bundle: usar diretório `M=`
novo com Makefile e fontes atuais de `phone/kernel/`, preservar `.config`,
Image e `vmlinux.symvers` pelos hashes registrados e compilar:

```sh
env LOCALVERSION= make -C "$N71_KERNEL_SOURCE" O="$N71_KERNEL_BUILD" \
  ARCH=arm64 -j2 KCFLAGS=-Werror M="$N71_MODULE_SOURCE" \
  KBUILD_EXTRA_SYMBOLS="$N71_KERNEL_BUILD/vmlinux.symvers" modules
python3 -m unittest discover -s tests -p test_n71_dart_observe.py -v
python3 -m unittest discover -s tests -p test_n71_dart_result.py -v
python3 tests/run_n71_link_session_mutations.py
```

Os nomes de variáveis apontam, respectivamente, para a cópia de fonte do
bundle, seu build preservado e a nova pasta externa de fontes. Exige1GiB
livre para esse build de módulos, ABI7.2.0-iphone6s-dart-serdev1 e modpost fatal;
não baixar a reserva8GiB exigida para um Image completo. Werror/ELF/vermagic,
contrato e seis mutantes compilados passaram em ARM64/Mac. O módulo registrado
tem48208bytes, SHA0a91c840…e486; o coletor usa esse registro explícito.

Compor perfil com `compose-n71-diagnostic.py` conforme os perfis anteriores,
selecionando esse módulo e hash completos. Payload/DTB/initramfs/identidades
precisam permanecer idênticos. Copiar o módulo REG_ON já registrado para o
perfil privado, verificar permissões600/700 e executar primeiro:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-dart-candidate-20261004/deployment.json" \
  --dart-observe --previous-clean "$PWD/runtime/n71-chip-session-20261004" --check
```

Só no boot correspondente já ativo, substituir `--check` por `--output-dir`
novo diretamente sob runtime. O modo exclui sizing/chip/core e exige
inventário. Não reutilizar histórico privado após reiniciar.

## Seleção upstream para o BCM4350 revisão8

A [tabela fixada de firmware](evidence/n71-firmware-selection.json) distingue
BCM4350/rev0–7 (máscara000000ff, `brcmfmac4350c2-pcie`) e rev8–31
(máscaraffffff00, `brcmfmac4350-pcie`). A leitura física rev8 pertence ao
segundo ramo. O nome identifica a família escolhida pelo código; não é prova
de firmware/NVRAM/calibração Apple compatíveis. Nenhum firmware foi baixado
ou carregado para essas experiências. SID/IRQ/DMA ainda precisam passar.

## Estado DART integral conservado e SID Apple qualificado

A seleção atual do modo `--dart-observe` é
[n71-dart-state-build.json](evidence/n71-dart-state-build.json): módulo48504bytes,
SHAaf2663a4…5727. A evidência anterior de48208bytes permanece histórica;
seu perfil deixa de passar a seleção corrente. O novo perfil mantém payload,
DTB, initramfs, chaves e pin; somente o módulo externo mudou.

[A coleta integral no mesmo boot passou](evidence/n71-dart-state-first-physical.json).
As16 palavras de40–7c foram guardadas nos logs privados com índices únicos
0–15. O parser confronta valid-bits e calcula SHA256 das16 palavras u32
little-endian. Valores não aparecem no terminal ou JSON público. O orçamento
permanece38 leituras/39 gates; não houve escrita DART, IRQ/provider ou DMA.
SSH/HTTP e snapshot após cleanup passaram. Sete mutantes C e seis do parser,
mais13 do coletor (incluindo exposição de ponteiros), falham por asserção.

Reproduzir com perfil novo, seleção atual e histórico anterior válido:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-dart-state-candidate-20261004/deployment.json" \
  --dart-observe --previous-clean "$PWD/runtime/n71-dart-session-20261004" --check
```

O [ADT e método Apple](evidence/n71-dart-apple-stream-reference.json) associam
WLAN iommu-parent84 ao mapper-apcie1/phandle84/reg0. `_registerMapper` lê
`reg`, conserva-o no campo SID e passa o mesmo valor ao DART emw2. Isso
qualifica SID0 na referência de placa; não comprova ainda o roteamento do
requester Linux0100, isolamento DMA ou entrega de interrupção.

Apple `vm-offset` contém **dois u32 little-endian**,80000000 e08000000. O
primeiro vira offset em páginas após shift12; o segundo é janela de
randomização de128MiB. Não convertê-los em um u64 FDT nem copiar esse par
para `apple,dma-range`. O provider atual reseta TCR/TTBR/ERROR em probe/remove;
a integração deve conservar e restaurar estado integral sob posse/power,
mesmo se probe falhar. Nenhum offset RID2SID/MSI M1 foi adotado no S8000.

## Provider DART — ciclo físico reversível, sem DMA

O [módulo do ciclo](evidence/n71-dart-cycle-build.json) usa
`dart_cycle=1`, exclusivo dos demais modos e desativado por padrão. Foram
compilados Mac/ARM64 o contrato de restauração e seis mutantes, além dos sete
do observer. O módulo externo passou Werror/modpost fatal, ELF e vermagic;
57112bytes, SHAe78a3c86…74ea. Image/DTB/initramfs não foram recompilados.
O primeiro build identificou colisão com a macro kernel `current`; o nome
foi corrigido para `observed` antes do build e da prova física.

O adaptador conserva o nó disabled e cria um platform device temporário com
o mesmo nó/recursos. A IRQ248 é traduzida pelo domain AIC real, sem copiar
número virtual. Mapping anterior é conservado; só um mapping criado pelo
experimento é descartado. O recurso passa do observador ao provider e volta
ao restaurador depois de unregister. Os quatro domínios PCI permanecem
adquiridos até encerrar o ciclo. Nenhum endpoint PCI é registrado/associado
ao IOMMU e bus-master permanece desligado.

[A prova física passou no boot existente](evidence/n71-dart-cycle-first-physical.json):

- Snapshot1: COMMAND00000f02,TCR0,ERROR100,16TTBRs válidos conservados.
- Provider `apple-dart` ligado: pagesize1000,4streams, AS32→36; snapshot2
  confirma16TTBRs zerados e tradução desligada.
- Unregister/removal do novo mapping e readquisição do recurso; snapshot3
  confirma tradução desligada antes de restaurar.
- 16 escritas somente nos TTBRs; snapshot4 confirma todas as palavras iguais
  às originais, hash idêntico, validffff e COMMAND/ERROR preservados.

O observador fez152 leituras com156 gates internos, mais17 gates extras.
Essas contagens excluem as operações próprias de reset do driver em
probe/remove. O adaptador não escreve COMMAND/ERROR; qualquer mudança deles
gera resultado negativo, mesmo se os ponteiros forem restaurados. Falha
parcial do probe também executa unregister e restore; nunca há escrita de
TTBR enquanto a tradução está ativa ou a retirada do provider é incerta.

Após o ciclo passaram ausência de device/handler, reset/power/REG_ON80,
PCI vazio/unload, SSH/HTTP e snapshot. IRQhandler registrado não comprova
entrega física de interrupção; provider inicializado não comprova mapeamento
DMA, isolamento, firmware, rádio ou alimentação sustentada.

Reprodução por módulo externo: usar as fontes atuais de `phone/kernel/` e
as mesmas regras de ABI/hash/.config/Image/exports descritas acima. Compor
perfil privado novo com o módulo/hash do ciclo e o REG_ON fixado. A seleção
exige prova integral privada anterior **do mesmo boot**, recalcada a partir
dos logs e confrontada com o JSON; sem essa prova, o comando é recusado:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-dart-cycle-candidate-20261004/deployment.json" \
  --dart-cycle --previous-clean "$PWD/runtime/n71-dart-state-session-20261004" --check
```

Trocar `--check` por uma nova pasta `--output-dir` sob runtime somente com
esse boot ativo. Se o telefone reiniciar, o histórico anterior deixa de ser
válido e deve ser refeita a captura completa; não basta copiar o JSON antigo.
25 testes do coletor,15 mutações e quatro mutações do parser protegem essa
seleção e o cleanup. Valores/identidades/logs permanecem privados.

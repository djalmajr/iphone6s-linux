# Investigação de Wi-Fi nativo — iPhone 6s A9

Estado atualizado em2026-10-04: **Wi-Fi nativo ainda não habilitado**. No mesmo boot, o projeto comprovou link/identidade PCI, BAR0 de32KiB/BAR2 de4MiB, leitura interna BCM4350/rev8 e observação estável do DART separado. SSH/HTTP e snapshots foram preservados após cada cleanup, sem novo DFU para essas continuações. [Procedimento e provas físicas](N71_LINK_EXPERIMENT.md).

O DART está com tradução desativada nos quatro streams, mas16TTBRs ainda têm valid-bit. **As16 palavras completas já foram conservadas privadamente no mesmo boot**, com duas amostras idênticas e cleanup verificado. A cadeia ADT WLAN→mapper84/reg0 e o método Apple `_registerMapper` qualificam o stream pretendido0; mapeamento Linux RID0100→SID0 e entrega IRQ/DMA ainda exigem prova. [Estado integral preservado](evidence/n71-dart-state-first-physical.json), [referência Apple de stream](evidence/n71-dart-apple-stream-reference.json).

A tabela upstream para a revisão8 seleciona a família `brcmfmac4350-pcie`; firmware/calibração Apple ainda não foram qualificados. [Seleção fixada](evidence/n71-firmware-selection.json). As seções abaixo preservam a pesquisa e suas limitações históricas; build estático não equivale a DMA/rádio funcionando.

## Desenvolvimento contínuo S8000 — 2026-10-02

O goal de implementação segue ativo, com gates físicos agrupados. Foram implementadas em `phone/kernel/n71-pcie-contract.h` primitivas específicas do controlador S8000: índices dos recursos, seis seletores de registradores e atualização de bits que preserva os demais campos. São funções puras; não há acesso MMIO nem controlador operacional neste header. [Proveniência e mapa selecionado](evidence/n71-driver-reference.json).

A referência é o kernelcache N71 da distribuição oficial Apple 15.8.8/19H422. O membro ZIP foi obtido com Range, conferido por SHA/CRC e descomprimido com LZSS/Adler32. Foram lidos metadados e instruções como dados; o firmware não foi executado, enviado ao aparelho ou publicado. A assinatura criptográfica IMG4 não foi verificada. O match `AppleS8000PCIe` → `apcie,s8000` foi confrontado com o ADT N71; presença de outros drivers no mesmo kernel, isoladamente, não identifica a placa.

Para a porta WLAN1, a referência mapeia recursos Apple 0/3/4/9/10: ECAM `0x610000000`, porta `0x602000000`, bloco secundário `0x602004000`, common `0x600000000`, PHY `0x600008000`. O DART `0x602008000` é separado do bloco secundário. Os seis seletores common dessa porta resultam em `0x24`, `0x2c`, `0x180`, `0x194`, `0x1a4`, `0x1ac`; isso impede substituir o mapa por constantes A10. Os nomes funcionais completos dos controles continuam pendentes; a API preserva IDs/bits em vez de atribuir semântica elétrica presumida.

O driver Apple examinado exige `apcie-phy-tunables`, ausente do ADT do IPSW lido. **A coleta física `dt` confirmou sua presença no Device Tree carregado pelo Pongo**, junto de common/config/root-port tunables. A árvore completa fica privada; larguras, máscaras, offsets e sequência ainda precisam ser confrontados com o driver antes de aplicação. A coleta prova presença no runtime, sem identificar por si só qual etapa do boot os inseriu. Não foi adotada tabela A10 como substituta. Também faltam integração do controlador Linux, MSI/streams/DART, firmware adequado após enumeração e associação. O header passou no Mac, ARM64 da VM e compilação `__KERNEL__`/`-Werror`; seis mutações são detectadas por asserção após compilação bem-sucedida. Esses gates não comprovam inicialização física ou Wi-Fi.

O mesmo DFU carregou a candidata de orçamento USB: SSH/HTTP passaram, configfs declarou 500 mA/80 e o host informou `UsbPowerSinkAllocation=500`. Interfaces continuam `lo`/`usb0`, PCI vazio e sensores ausentes. Snapshot/sync e retorno por software ao iOS foram verificados. [Evidência física selecionada](evidence/n71-runtime-reference.json). Próxima fatia: extrair/validar privadamente os tunables e integrar o controlador S8000 na VM; não repetir boot da mesma imagem para confirmar ausência de Wi-Fi.

Reproduzir o contrato sem telefone, com o compilador C já existente:

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -p test_n71_pcie_contract.py -v
python3 iphone-linux-tools/tests/run_n71_pcie_mutations.py
```

O procedimento usa somente diretório temporário e recusa contar falha de compilação como kill de mutação. No Mac não foram instalados pacotes. A candidata e o aparelho não mudaram nesta fatia; nenhuma nova reinicialização foi feita.

## Evidência no aparelho

- Linux 7.0.12 ARM64; interfaces `lo`, `sit0` e `usb0`.
- Não existe `/sys/class/ieee80211`; nenhuma interface wireless registrada.
- Nenhum dispositivo PCI/MMC/SDIO foi encontrado nos caminhos consultados.
- O device tree em execução não contém nós Wi-Fi/WLAN nem controlador PCIe/MMC identificado pelas buscas.
- Logs não mostraram sondagem brcmfmac, rádio wireless ou solicitação de firmware Wi-Fi.
- Não apareceram os símbolos específicos de probe Broadcom PCIe/SDIO ou Apple PCIe pesquisados em `/proc/kallsyms`.
- A listagem do APK de kernel preservado não mostrou módulos brcmfmac/cfg80211 pesquisados. Isso descreve o pacote inspecionado, não prova ausência em qualquer kernel possível.

Nenhum driver, firmware, credencial de rede ou serviço foi instalado para este teste. O Linux e seu acesso por USB permaneceram ativos.

## Upstream consultado

Repositório oficial [HoolockLinux/linux](https://github.com/HoolockLinux/linux), branch `hoolock`, HEAD `6831bc701a6ce059e71e5aaa9488c9195bea6927` observado nesta data.

Foi conferida a cadeia de includes do [s8000-n71.dts](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/s8000-n71.dts):

- `s8000-n71.dts`
- `s800x-6s.dtsi`
- `s800-0-3-common.dtsi`
- `s8000.dtsi`
- `s800-0-3.dtsi`
- `s800-0-3-pmgr.dtsi`

As buscas encontraram domínios de energia PCIe em `s800-0-3-pmgr.dtsi`, mas não um nó operacional do controlador PCIe ou Wi-Fi na cadeia N71. Domínios de energia não bastam para enumerar ou controlar o rádio. Uma busca de commits oficiais por `s8000 pcie` não retornou resultados; essa busca é evidência auxiliar limitada, não uma prova de inexistência de todo trabalho experimental.

O fork [Pauli1Go/HoolockLinux](https://github.com/Pauli1Go/HoolockLinux) documenta Wi-Fi funcionando nos dispositivos testados **A10/T8010**: iPad 7 e iPhone 7 Plus D111. O próprio README delimita a validação a esses aparelhos e descreve controlador PCIe, DART e calibração. Não há validação N71/A9 nessa matriz; não tratar esse kernel ou seus dados de placa como compatíveis com o 6s.

A página postmarketOS do N71 não pôde ser acessada pelo navegador de pesquisa devido ao redirecionamento para outro domínio; ela não foi usada como prova do resultado.

## Conclusão e próximo caminho

**Inferência a partir do aparelho e do código consultado:** a primeira lacuna é suporte do kernel/device tree ao caminho de comunicação do chip, antes de configurar SSID/senha. Instalar apenas firmware ou wpa_supplicant não resolve a ausência de um rádio enumerado.

Habilitar Wi-Fi nativo exigiria trabalho específico para N71/A9: controlador/barramento, sequência de energia/reset, integração com o driver do rádio e firmware/calibração da placa, seguido de testes em uma imagem nova. Não existe nesta investigação uma receita pronta que justifique substituir a imagem funcional. Não foram experimentados drivers A10 no A9 nem alterados registradores de hardware às cegas.

Alternativa para continuar o mini servidor: rede USB ao Mac, com eventual acesso aos serviços pela LAN através do Mac. Isso não ativa o Wi-Fi do iPhone nem o torna independente de um computador. Encaminhamento/NAT, DNS do Mac e configurações do roteador ainda não foram alterados.

## Reavaliação da candidata de fonte — 2026-10-01

Esta atualização examina **artefatos locais**, não uma nova sessão no aparelho: kernel `7.2.0-iphone6s-source`, fonte `hoolock-stable` fixada em `958481f87fee0949ff6a9a4af77f7eb6dac8a149`. A inspeção antiga acima permanece como evidência física do kernel 7.0.12. [Fontes, hashes e resultados estáticos](evidence/wifi-n71-path.json).

### O que falta em cada camada

| Camada | Observação e limite |
|---|---|
| Chip do rádio | BCM4350 é uma hipótese de família; o estudo primário [Reich et al., tabela I](https://doi.org/10.1109/SAM48682.2020.9104399) identifica esse controlador Bluetooth num iPhone 6s. Isso não identifica a revisão Wi-Fi deste N71, seu barramento ou pinos. Nenhum PCI ID foi lido neste aparelho nesta fase. |
| Barramento N71 | A cadeia de seis DTS/DTSI e o DTB compilado (136 nós) não descrevem host PCIe/MMC/SDIO ou rádio wireless correspondentes. Existem domínios PMGR chamados PCIe na fonte; isso não constitui um controlador operacional. |
| Driver host PCIe | A [tabela de matches](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/pci/controller/pcie-apple.c#L880) usa dados T8103 para `apple,pcie` e T602x para `apple,t6020-pcie`; não apresenta match S8000 específico. Não demonstra que o mesmo mapa de registradores sirva para A9. |
| DMA/DART | O driver DART existe e está incorporado, mas o DTB N71 não descreve o caminho de DMA do rádio. Topologia, streams e adequação do driver não foram comprovados; não copiar a DART2 do T8010. |
| Drivers na imagem | `CONFIG_PCIE_APPLE=m`, `CONFIG_CFG80211=m`, `CONFIG_BRCMFMAC=m`; `CONFIG_BRCMFMAC_PCIE` desligado, SDIO habilitado. A imagem tem somente a pasta `lib/modules`, sem arquivos `.ko`. Nenhum desses módulos foi instalado ou carregado. |
| Energia/reset | Não há regulador WLAN/sequência de reset N71 definida na cadeia examinada. GPIOs, tensões, clocks e ordem exatos seguem desconhecidos. Os domínios PMGR não autorizam programar a placa com parâmetros A10. |
| Firmware/calibração | O [driver genérico](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c#L2238) escolhe nomes por chip/revisão e, em plataformas Apple aplicáveis, informações de placa/OTP. `.bin` e possíveis dados NVRAM/CLM/TxCap não têm um par validado para este N71. A calibração privada demonstrada no A10 não prova formato/requisitos A9. |

O [fork A10](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/README.md) fixa sua validação em J172/iPad 7 e D111/iPhone 7 Plus. Suporte naquele chip/placa não é um patch pronto para o S8000. A [tabela oficial A9](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/features/A9.md) não lista Wi-Fi; ausência numa tabela, isoladamente, não prova impossibilidade de desenvolvimento futuro.

**Conclusão:** a candidata atual não vai ganhar Wi-Fi somente com SSID/senha ou uma opção de configuração. O trabalho necessário é uma implementação específica de placa/barramento antes da associação. Viabilidade geral não foi descartada, mas não há receita pronta comprovada nos insumos examinados; #9 continua aberta. Nenhum firmware, credencial ou calibração foi obtido/publicado, e nenhuma imagem foi substituída.

### Sequência de desenvolvimento e prova

1. Dar boot supervisionado na candidata com USB/SSH preservados. Ler `/sys/bus/pci/devices`, `/sys/bus/sdio/devices`, `/sys/class/ieee80211`, os compatibles do DT em execução e logs de probe/firmware. A ausência de diretórios/dispositivos é resultado, não motivo para inserir módulos A10.
2. Identificar privadamente o Apple Device Tree/topologia N71 e a revisão do rádio: ranges, interrupts, clocks, PMGR, reguladores, GPIOs e streams DMA. Firmware/calibração/MAC permanecem privados; no Git guardar somente origem, requisitos e hashes adequados. Não publicar dumps brutos do aparelho.
3. Revisar uma implementação N71 separada de PCIe/PHY/reset/DART e uma configuração com drivers incorporados ou módulos da mesma ABI. Compilar na VM dedicada, preservar os artefatos funcionais e testar enumeração primeiro. Não usar escrita de registradores sem mapa validado.
4. Depois de enumeração e chip/revisão comprovados, selecionar firmware de origem documentada e dados da própria placa. Validar interface wireless, scan, associação e DHCP, com retorno ao enlace USB em caso de falha. Somente então testar serviço pela LAN sem o Mac no caminho.

### Reproduzir a inspeção estática

Conferir hashes do DTB, `.config` e initramfs contra a evidência antes de examinar. Na VM de build com `dtc`, `gzip` e `cpio` já disponíveis, sem montar pastas pessoais do Mac:

```sh
dtc -I dtb -O dts -o n71-inspected.dts /CAMINHO/s8000-n71.dtb
rg -n 'pci|mmc|sdio|wlan|wifi|dart|compatible' n71-inspected.dts
rg '^(CONFIG_(PCI|PCIE_APPLE|APPLE_DART|BRCMFMAC|BRCMFMAC_PCIE|BRCMFMAC_SDIO|CFG80211|FW_LOADER)=|# CONFIG_BRCMFMAC_PCIE)' /CAMINHO/config
gzip -dc /CAMINHO/initramfs.gz | cpio -it 2>/dev/null | rg '\.ko($|\.)'
```

O último comando apenas lista nomes, sem extrair arquivos; sem matches termina com saída 1. Nesta fase a mesma estrutura foi lida com Python padrão: 2.969 entradas newc, zero módulos e somente a pasta `lib/modules`; os 136 nós do DTB foram examinados por path/compatible. Não executamos ferramentas de fonte externa no Mac, instalamos pacotes ou iniciamos VM. As versões/configuração dos artefatos e tabelas de driver são evidência estática; não comprovam enumeração ou Wi-Fi no hardware.


## Inventário físico da candidata — 2026-10-02

Inspeção somente leitura aproveitou o boot já ativo `7.2.0-iphone6s-source`, por SSH estrito, sem novo DFU/reboot: interfaces `lo` e `usb0`; classe ieee80211 ausente; diretórios de dispositivos PCI/SDIO/MMC presentes, porém vazios; zero módulos carregados. Foram lidas 118 propriedades compatible do DT em execução, sem matches PCIe/MMC/SDIO/WLAN/brcm/DART nos termos examinados. O único log correspondente foi a inicialização genérica PCI CLS; não houve probe de rádio nesse inventário. [Evidência física sanitizada](evidence/wifi-runtime.json), separada da evidência estática de 2026-10-01.

Não há fontes de alimentação em power_supply nem propriedade com nome ADT no chosen examinado. Isso não prova que o ADT original seja impossível de obter por outro caminho; apenas não está exportado ali. Nenhum dump bruto, MAC, serial, firmware ou credencial foi publicado.

**Próximo desenvolvimento:** obter a topologia Apple N71 original de fonte identificada e manter o insumo privado. Mapear barramento/PHY/reset/clocks/PMGR/DMA e comparar com a fonte do driver host antes de preparar uma candidata específica do A9. A fase offline não requer reboot do iPhone. Depois de mapa validado e build na VM, uma única sessão deve reunir enumeração, preservação do SSH USB e logs; só testar firmware/associação se o rádio tiver sido identificado. Instalar módulos genéricos não cria os nós/topologia ausentes.

A tabela/fork A10 foi reconsultada; a validação permanece em J172/D111, sem evidência N71 nessa matriz. #9 passa a prioridade de desenvolvimento. DNS53 fica em espera; suporte A10 não será tratado como prova A9. Fluxo de iteração: [desenvolvimento com menos reinicializações](DESENVOLVIMENTO.md).


## Referência Apple N71 obtida — 2026-10-02

Foi lido o membro exato `Firmware/all_flash/DeviceTree.n71ap.im4p` da [distribuição Apple iOS 15.8.8/19H422](https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-77510/5D4563BF-445C-4D8D-AF56-0BAC336265F3/iPhone_4.7_15.8.8_19H422_Restore.ipsw), por HTTP Range: 31.376 bytes transferidos, membro de 25.946 bytes, CRC ZIP conferido. SHA256 `739aeb1b52a76ac9147b2479e86a06b3c49b1e09499377ea73f1329a034b5184`. Decodificação LZFSE usou a biblioteca Compression já presente no macOS; duas extrações independentes produziram os mesmos 142.148 bytes/200 nós. Assinatura criptográfica IMG4 não foi verificada; isso é referência de placa, não imagem autorizada para flash. [Mapa público selecionado e proveniência](evidence/n71-board-map.json).

| Caminho Apple N71 | Informação concreta |
|---|---|
| arm-io/apcie | Host `apcie,s8000` |
| apcie/pci-bridge1/wlan | Família `wlan-pcie,bcm4350`, porta PCIe 1 |
| uart4/wlan | `wlan-pcie-uart,bcm4350` |
| dart-apcie1 | `dart,s8000`, fallback `dart,s5l8960x`, mapper-apcie1 |

Isso substitui a hipótese anterior de família por uma identificação na referência Apple N71; ainda não identifica PCI-ID/revisão/calibração do rádio deste aparelho, nem demonstra enumeração Linux. O caminho do A10 D111 usa porta 2; não copiar essa topologia para a porta 1 do N71.

O [controlador experimental do fork](https://github.com/Pauli1Go/HoolockLinux/blob/d49ac41cb898881457a97bb3cd44b7d92ff50a8c/drivers/pci/controller/pcie-apple-h9p.c) oferece matches J172/T8010, sem match S8000. O [DART da fonte atual](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/drivers/iommu/apple-dart.c) já inclui `apple,s5l8960x-dart`; a lacuna é a integração DT/streams/clocks/reset/dominios e sua validação N71, não ausência total de driver DART.

Próxima implementação: revisar mapa MMIO/PHY e sequência de energia/reset S8000; descrever host porta 1 e DART no DT, compilar com drivers correspondentes na VM e preparar uma única candidata. Nessa próxima sessão necessária, reunir enumeração PCI, DMA, logs, preservação USB/SSH e orçamento USB corrigido. Firmware/associação/DHCP ficam depois da identificação real do rádio. Não foram escritos registradores ou instalados drivers/firmware nesta pesquisa.

### Reproduzir a obtenção privada

Na raiz do repositório, escolha um diretório novo diretamente sob runtime, que deve ser do usuário e ter permissão 700:

```sh
python3 -B iphone-linux-tools/scripts/research/apple-n71-map.py \
  --output-dir "$PWD/iphone-linux-tools/runtime/n71-reference-NOVO"
```

O leitor fixa URL, tamanho, membro e SHA256; limita Range/DER/ADT/LZFSE, valida CRC e recusa outro hash. Não baixa o IPSW inteiro, executa downloads ou instala dependências. Requer macOS pela biblioteca Compression existente. Saídas brutas e nomes/propriedades de placa permanecem privados, modo 600, sob runtime ignorado. Não publicar ADT, calibração, MAC, serial ou firmware. O programa não faz boot/restore/flash, nem converte sozinho o ADT Apple em um DTS Linux operacional.


## Topologia N71 compilada — 2026-10-02

Incremento implementado em [11c6f30](https://github.com/djalmajr/iphone6s-linux/commit/11c6f30): fragmento `phone/kernel/n71-peripherals.dtsi` com UART5 em `0x20a0d4000`/IRQ197, DART PCIe1 em `0x602008000`/IRQ248 e PCIe S8000 com os onze recursos e quatro interrupções da referência Apple. O host mantém a ordem Apple; funções secundárias ainda não confirmadas usam nomes `adt-reg-N`. Não foi inventado o recurso PHY-IP `0x60a000000` encontrado no DT T8010, ausente da lista N71 examinada. AUX/REF do A9 são ligados como domínios de energia existentes, sem fabricar provedores de clock A10.

**Todos os três nós estão desativados.** PCIe tem somente compatible S8000, sem fallback T8010/genérico e sem driver operacional novo. Não foram adicionados mapa de streams/DMA, ranges PCI, MSI ou sequência PHY/reset. A árvore compila, mas não é uma implementação completa do binding PCI nem uma candidata aprovada para boot; Wi-Fi continua não habilitado.

O builder compila primeiro a baseline sobre a fonte estável limpa e fixa seus phandles antes de incluir o fragmento. O primeiro build foi recusado ao detectar renumeração de CPUs; o final conserva cada propriedade anterior e acrescenta somente os três nós, mais identificadores necessários nos provedores antes não referenciados. A baseline reproduziu exatamente o hash do DTB funcional preservado. Endereços/IRQs foram traduzidos a partir dos ranges Apple, não copiados do A10. [Hashes, fontes e gates](evidence/n71-topology.json).

### Reprodução da compilação offline

Use a VM dedicada ARM64 com GCC/dtc já disponíveis e um checkout limpo do commit `958481f87fee0949ff6a9a4af77f7eb6dac8a149`. Copie somente os arquivos públicos do projeto para ela. Não enviar firmware bruto, keys ou snapshots. Os comandos seguintes são executados como usuário normal **dentro da VM**, a partir da raiz do repositório; substitua os dois caminhos de exemplo e escolha saídas novas:

```sh
export N71_SOURCE_DIR=/home/ubuntu/kernel-n71-source-20261001
# Materializa os fatos fixados no código público. Não substitui a verificação
# independente da referência Apple descrita acima.
python3 -B - <<'PYREF'
import json, runpy
from pathlib import Path
facts = runpy.run_path('iphone-linux-tools/scripts/build/prepare-n71-topology.py')['REFERENCE']
with Path('n71-resource-input.json').open('x') as output:
    json.dump(facts, output)
PYREF
python3 -B iphone-linux-tools/scripts/build/prepare-n71-topology.py \
  --source-dir "$N71_SOURCE_DIR" --reference n71-resource-input.json \
  --output-dir /home/ubuntu/n71-topology-build-NOVO
IPHONE_N71_VM_SOURCE="$N71_SOURCE_DIR" \
  python3 -B iphone-linux-tools/tests/run_n71_topology_mutations.py
```

A referência JSON deve coincidir exatamente com hash/ranges/recursos N71 fixados; o input selecionado usado nesta entrega foi conferido contra o ADT privado. A cópia acima reproduz a compilação desses fatos, não reextrai firmware nem verifica assinatura IMG4. Output novo privado (700/600), fonte preservada, comparação limitada do DTB e manifest com `boot_qualified=false`. Recusa links, diretório existente, outra fonte/placa, mudança de propriedades antigas ou nó ativado; não recompõe a imagem de boot nem altera o perfil ativo.

Mac: 13 testes passaram, quatro compilações Linux foram explicitamente ignoradas e sete mutações foram rejeitadas por asserção. VM: 17/17 e oito mutações, incluindo compilação real sem fixação de phandles que falha por diferença nas propriedades anteriores. Flake8 fatal passou; sem typechecker Python configurado. Nenhum pacote instalado no Mac ou VM e nenhum reboot do telefone nesta fase. Logs e DTBs privados ficam em runtime; só hashes/evidência selecionada são públicos.

**Próximo gate da #9:** mapear funções dos blocos MMIO e validar sequência S8000 PHY/energia/reset, porta1 e streams DMA; implementar controlador separado e revisar antes de ativar. Agrupar enumeração/logs e preservação USB/SSH com o descritor USB da #33 no próximo boot necessário. Associação, firmware/calibração e DHCP exigem primeiro PCI-ID/revisão reais; esses critérios continuam abertos.

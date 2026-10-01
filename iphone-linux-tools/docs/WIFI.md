# Investigação de Wi-Fi nativo — iPhone 6s A9

Verificado em 2026-09-29. Resultado: **Wi-Fi nativo não habilitado**. Não foi encontrado um caminho pronto e comprovado para este N71/S8000 com o kernel atual ou o device tree A9 do upstream consultado.

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

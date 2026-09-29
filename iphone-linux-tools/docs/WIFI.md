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

# Inicialização e recuperação sem tela — #11

## Conclusão da cadeia atual

**Linux não inicia somente apertando Power.** O fluxo comprovado depende de entrada física em DFU, Mac conectado e envio de PongoOS/m1n1/kernel/initramfs. Power/reinício físico voltou ao iOS nos pilotos anteriores; o novo kernel com watchdog ainda requer validação de retorno/rollback.

A [Apple descreve](https://support.apple.com/en-gb/guide/security/secb3000f149/web) a cadeia de boot com verificação de assinatura e uma etapa LLB nos processadores A9 ou anteriores. O exploit permite desviar a sessão de boot, mas não substitui por si só essa cadeia em armazenamento. A [FAQ checkra1n](https://checkra.in/index.html) distingue o retorno ao iOS após reboot e a nova entrada DFU pelo computador. Isso contextualiza o método usado; não propõe instalar checkra1n como sistema do servidor.

| Opção | Aplicação e limite para este projeto |
|---|---|
| DFU → PongoOS → m1n1 | Caminho N71 já comprovado; wrapper automatiza envio/conexão/restore depois da ação física. Novo kernel/Pongo ainda sem piloto. |
| iBoot remoto → m1n1 | [Método upstream](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/tutorials/SETUP_iBoot.md) prepara arquivos por modelo e parte de DFU; um computador envia iBSS/iBEC e imagens. Independer dos arquivos no disco do telefone não significa independer do host. N71 não foi testado por esse método. |
| Rootfs em disco interno | Mesmo que #10 forneça filesystem persistente, ainda é preciso uma cadeia que escolha e carregue Linux. A prova A10 continua usando DFU/Pongo/host. |
| Recarregar kernel em RAM | Pesquisa de reinício quente não resolve boot após bateria descarregada. Nenhum caminho desse tipo foi demonstrado neste N71. |
| Apagar iOS/LLB | Não é uma instalação Linux. Segundo a Apple, falha ao carregar LLB pode levar a DFU; falha posterior pode levar a recovery. Não foi feito nem proposto como mecanismo autônomo. |

“Permanente” no contexto de uma vulnerabilidade Boot ROM não quer dizer que um patch Linux permaneça ativo após desligamento. O README antigo [ipwndfu](https://github.com/axi0mX/ipwndfu/blob/0e28932ec6a2a570b10fd77e50bda4216418cd98/README.md) também distingue o exploit checkm8 de outros métodos untethered de gerações diferentes; não usamos a lista histórica de SoCs dele para validar uma ferramenta nova no A9.

## Comportamento de energia e reinício

| Evento | Evidência ou resultado esperado |
|---|---|
| Power com boot normal do aparelho | Retorno ao iOS observado neste projeto; não inicia Linux sozinho. |
| `reboot -f` no Linux anterior | Desaparecimento USB sem retorno automaticamente comprovado; Power + Home restaurou iOS. Helper exige confirmação USB/modelo, não trata silêncio SSH como sucesso. |
| Reinício da candidata com watchdog | Compilado/inspecionado, ainda sem prova física de retorno ou rollback (#12/#21). |
| Mac/cabo desconectados com bateria restante | Pode continuar a sessão em RAM, mas USB/LAN por Mac e snapshots ficam indisponíveis. Carga sustentada ou disponibilidade contínua não estabelecidas. |
| Bateria totalmente descarregada | RAM é volátil; o snapshot no Mac permite recuperar arquivos. Retorno automático ao Linux após recarga não foi demonstrado em piloto controlado. |
| Energia retorna ao carregador | Carregador não fornece o payload/host USB. Não há mecanismo pronto demonstrado que converta esse evento em boot Linux autônomo. |

A queda do serviço causada por descarga já ocorreu durante a investigação; isso não isola o comportamento de um carregador validado nem substitui um teste controlado de recuperação. Não vamos descarregar deliberadamente a bateria para preencher essa lacuna antes de estabelecer o gate de alimentação (#2).

## Uso viável nesta etapa

O servidor experimental pode usar a cadeia assistida que o operador já aceitou: manter o Mac e o enlace USB, entrar em DFU manual quando necessário e recuperar o snapshot. Operação contínua e recuperação sem intervenção permanecem pendentes. O monitor/boot não resolve botões físicos, USB ausente, carga insuficiente ou firmware de rede/storage faltante. Nenhum serviço automático global foi instalado no Mac.

Próxima prova coordenada: boot da nova cadeia, SSH/console/NCM/HTTP, snapshot verificado, comando de retorno com confirmação iOS e rollback para a implantação conhecida. Só depois de alimentação validada testar disponibilidade e recuperação de falhas. Os procedimentos são [EXECUCAO](EXECUCAO.md), [REBOOT](REBOOT.md), [PERSISTENCIA](PERSISTENCIA.md) e [ALIMENTACAO](ALIMENTACAO.md).

A issue #11 continua aberta: opções e dependência do host foram mapeadas, mas recuperação após perda total de energia e inicialização Linux sem intervenção não estão comprovadas. Não foi encontrada cadeia autônoma pronta nas fontes examinadas; isso não é prova de impossibilidade de pesquisa futura. [Evidência/limites](evidence/storage-boot-n71.json).

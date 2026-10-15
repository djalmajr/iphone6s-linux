# brcmfmac: propagar falha MSI antes de registrar IRQ — #9/#40

## Contexto

Na fonte HoolockLinux fixada em `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, `drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c:968` ignora o retorno de `pci_enable_msi`. O N71 exige a associação MSI/DART própria; uma falha MSI não autoriza tentar uma IRQ antiga ou zero. A associação física anterior não comprovou alocação/entrega de IRQ nem DMA/rádio. Este passo corrige o driver de forma isolada e prepara a futura integração; não muda essa classificação.

## Arquivos e detalhes

Fase de implementação, até cinco arquivos: `phone/kernel/patches/0008-brcmfmac-msi-error.patch` contém a função IRQ completa como contexto; `scripts/build/build-n71-wifi-modules.py:127` aplica a correção somente à cópia privada de brcm80211, verificando hashes da fonte, patch, método e resultado; `tests/test_n71_wifi_irq.py` compila o método real representado pelo patch e, na VM, extraído da fonte completa fixada; `tests/n71_wifi_irq.c` injeta falhas e observa chamadas, argumentos e ownership. Fase de gates do builder: `tests/test_n71_wifi_modules.py` e `tests/run_n71_wifi_modules_mutations.py`. Fase documental própria: evidência pública sanitizada, reprodução, status e registro de decisão.

Não modificar fonte/kernel/config/Image/exports preservados. Não carregar módulo, firmware ou rádio nesta fase. Compilar no output novo da VM dedicada, com exports/ABI de `n71-dart-serdev-power-v2`, `KCFLAGS=-Werror`, sem instalação. Preservar a build Wi-Fi original para rollback. Nenhuma ação física do operador é necessária para gates offline.

## Tarefas

- [x] Registrar a fatia pendente em #40 antes de implementar; #9 recebe o resultado conjunto.
- [x] Capturar retorno de MSI, devolver o erro negativo antes de request IRQ e manter o sucesso e rollback upstream.
- [x] Exigir hashes exatos e registrar source/patch/result na procedência da cópia.
- [x] Compilar baseline, regressão original e mutações; somente falhas de asserção contam, nunca erro de compilação/timeout.
- [x] Gates do builder e contrato de patch no Mac e Ubuntu ARM64; AST/lint fatal.
- [x] Compilar os oito módulos na VM, verificar dependências/alias/MSGBUF/ABI e preservação do kernel e build de rollback.
- [ ] Documentar comandos, hashes, limites e atualizar branch/issues autorizadas; acompanhar CI sem integrar main.
- [ ] Prosseguir com política PCI/MSI e ciclo explícito do driver/DMA/firmware; agrupar as provas físicas necessárias em sessão posterior.

## Relatório da implementação offline — agile-status

Fonte: plano acima e issues9/40. Modo: fechamento da correção offline, dentro do goal ainda ativo. Todos os arquivos alterados correspondem a patch/build, contrato/regressão ou documentação previstos; não houve ampliação de escopo. Patch copia a função upstream, sem fallback IRQ novo; as APIs do builder conservam seus argumentos e acrescentam somente procedência da correção.

| Verificação | Resultado |
|---|---|
| C e regressão |16 cenários,13 mutações compiladas e original rejeitados por asserção, Mac/Ubuntu ARM64 |
| Builder |15 testes/24 mutações por asserção em cada plataforma |
| Build ARM64 |Oito módulos, Werror/modpost/alias/MSGBUF/dependências/ABI aprovados |
| Preservação |Fonte/config/Image/exports e rollback intactos; sete módulos novos idênticos aos anteriores |
| Lint |Flake8 fatal E9/F63/F7/F82 aprovado em ambas as plataformas |
| Tipos |Não há typechecker Python configurado; AST aprovado, sem alegar prova de tipos |
| Artefatos |Mac conferiu hashes/tamanhos/ELF/vermagic; privados700/600 |
| Hardware |Nenhum novo DFU/carga/firmware; alocação IRQ/DMA/Wi-Fi não comprovados |
| Documentação |Reprodução, evidência sanitizada, status e decisão D6 registrados |

Dependências/banco: nenhuma instalação, pacote novo ou mudança de banco. Desempenho: somente um branch no erro MSI; nenhuma medição de rádio feita. Limite restante: ciclo PCI/MSI/driver e tradução/entrega reais precisam de integração e prova física; carga/gauge continuam em issue2. Próximo passo observável: callbacks PCI/MSI restritos e attach/quiesce do driver qualificados offline, antes de uma sessão física agrupada. Acompanhar CI da publicação; não encerrar o goal nem integrar main.

O diffcheck normal aprovou código/docs. A representação unified do patch tem prefixos de contexto com espaço antes de tabs/linhas vazias, reconhecidos como whitespace pelo Git ao adicionar o patch inteiro. Conferir somente esse arquivo com opções de whitespace no comando, sem alterar Git config; os métodos original/corrigido não têm trailing whitespace e os hashes da transformação completa foram verificados. Isso não altera hooks ou gates de código.

### Comandos de verificação

`python3 -B -m unittest discover -s tests -p test_n71_wifi_irq.py -v` deve provar falha MSI sem request IRQ/disable/ownership, request IRQ negativo com disable e EIO, sucesso com IRQ/MSI mantidas e argumentos/callbacks upstream. Compilação C com warnings como erros; a função original deve compilar e falhar por asserção. Repetir na VM passando a fonte completa fixada em `N71_BRCMFMAC_PCIE_SOURCE`. Gates existentes do builder e mutações permanecem obrigatórios. A build completa registra oito ELF ARM64 com vermagic e exports exatos; Mac recalcula hashes. Não há typechecker Python configurado: AST/lint não são apresentados como prova de tipos nem hardware.

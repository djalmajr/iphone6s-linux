# Implementação da topologia N71 — preparação offline

## Contexto

Continuação autorizada em 2026-10-02: suporte A9, mínimo de reinicializações, desenvolvimento solo. #32 está concluída; #9/#2 requerem drivers específicos. Referência Apple N71 fixada e DTB estável funcional preservados. A pesquisa confirmou que os recursos PHY/portas S8000 não podem receber automaticamente as constantes T8010; a referência de gauge usa `gas-gauge,bq27540`, sem identificação física de revisão/register map validada para o driver BQ27545.

## Decisão D1 — primeiro integrar recursos verificáveis

- **Decisão:** adicionar fragmento DTS N71 com UART5/HDQ, DART PCIe1 e inventário de recursos PCIe próprios, todos desativados. Compilar contra a fonte estável fixada e verificar o DTB resultante, com preservação de todos os nós/propriedades anteriores.
- **Por quê:** os nós são ausentes hoje e a referência Apple fornece endereços/IRQs. As sequências PHY/HDQ e semântica BQ27540 ainda não estão validadas; registrar recursos não autoriza ativá-los.
- **Alternativas:** reaproveitar init PCIe/charger A10 (compatibilidade não demonstrada e escritas indevidas); ativar UART/gauge já (mux/register map não comprovados); continuar somente documentação (não fornece integração compilável).
- **Reverter:** baixo, remover include do arquivo de desenvolvimento; preservar fontes/builds funcionais.
- **Onde:** arquivos abaixo; #9/#2.
- **Status:** em curso; ativação e probe reais continuam pendentes.

## Arquivos e fases

Primeira fase, cinco arquivos públicos:

1. Este plano.
2. `phone/kernel/n71-peripherals.dtsi`: nós novos, compatible A9 e fallback conhecido somente para UART/DART; inventário PCIe sem fallback T8010/genérico; status disabled em todos os nós novos. Não declarar rádio pronto nem serial alias que renumere console existente.
3. `scripts/build/prepare-n71-topology.py`: validar fonte/commit limpo, fragmento limitado/imutável por contrato e output novo; preparar DTS wrapper e fragmento em pasta separada; compilar DTB com ferramentas Linux já existentes; verificar o DTB com parser Python padrão limitado e comparação binária de propriedades, propriedades baseline conservadas, sem artefato de boot instalado. Entrada Apple privada deve conferir hash do ADT e os recursos usados.
4. `tests/test_n71_topology.py`: contrato de saída compilada, preservação, recusa de fragmento ativado/A10, referência incorreta e saída existente/ligada; fixtures sintéticas não são hardware.
5. `tests/run_n71_topology_mutations.py`: mutações reais em fonte/fragmento; exigir falha por asserção, não erro de compilação.

Fases seguintes, cada uma até cinco arquivos: evidência sanitizada/compilation/runbook/#9/#2 e registro do gate no CI. Fontes externas e logs ficam privados. VM dedicada de kernel retorna a Stopped. Não enviar chaves, firmware ou snapshots para VM; somente dados de recursos selecionados sem calibração.

## Tarefas

- [x] Conferir endereços/IRQs/endian e vínculos contra Apple ADT e fonte estável.
- [x] Implementar fragmento e preparo/compilação de DTB em diretório separado.
- [x] Provar recusas/preservação/contratos e mutações locais/VM.
- [x] Compilar sobre N71 real na VM, verificar baseline e manifest/hashes.
- [ ] Documentar/publicar o incremento e atualizar issues, mantendo Wi-Fi/carga sem prova como abertos.

## Verificação e limites

Nenhum reboot, escrita MMIO/I2C/PMIC, driver de outro gauge, fallback T8010, firmware executado ou pacote no Mac. Não ativar nós ou fabricar binding operacional. A candidata DTB desta fase não está aprovada para boot: faltam implementação/revisão das sequências e mapeamento de DMA/PHY/mux. Compilação só comprova sintaxe/inclusão/topologia e preservação, não enumeração, associação, telemetria ou carga. AST/Flake8 e testes novos; nenhum shell foi alterado; sem typechecker configurado. Reusar CI/gates anteriores que não mudaram.

## Decisões verificadas durante a implementação

### D2 — fixar identificadores do DTB existente

O primeiro build foi recusado porque o DTC renumerou phandles antigos ao receber referências novas. A implementação passou a compilar a baseline primeiro e a fixar todos os phandles antigos explicitamente antes de incluir o fragmento. O build final preserva cada propriedade anterior; uma mutação que remove essa fixação compila, mas falha por asserção na comparação nativa. Alternativa de aceitar renumeração e atualizar outras referências foi descartada porque amplia o delta da plataforma já funcional.

### D3 — respeitar os provedores PMGR do A9

AUX/REF do S8000 fornecem domínios de energia, sem `#clock-cells`. O fragmento usa os quatro domínios existentes para PCIe; não inventa provedores de clock como os do A10. Os nomes secundários de recursos permanecem `adt-reg-N`, pois a função PHY/porta de cada bloco ainda requer revisão. PCIe tem apenas compatible S8000, sem match T8010 ou fallback genérico.

## Resultado da primeira fase

- Mac: 17 testes descobertos, 13 passaram e quatro compilações Linux foram explicitamente ignoradas; sete mutações rejeitadas por asserção.
- VM ARM64: 17/17 passaram; oito mutações rejeitadas por asserção, incluindo remoção da fixação de phandles na compilação N71 real.
- GCC 13.3.0 e DTC 1.7.0 existentes, sem instalação de pacotes. Fonte fixada permaneceu limpa.
- Baseline reproduziu exatamente o DTB funcional preservado; a candidata acrescenta três nós desativados. Hashes e reprodução serão registrados na fase de documentação.
- Nenhum pacote Mac, reboot, probe ou alteração de perfil ativo. Wi-Fi e carga sustentada continuam sem prova.

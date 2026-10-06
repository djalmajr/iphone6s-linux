# Janelas PCI opcionais ausentes — issue39

## Contexto

A sessão física do readback registrou root0:08/0x30: pedido0000ffff, anterior0, leitura válida0, callbacks sem erro. IO1c/30 zerados foram confirmados no mesmo boot. Cleanup/retry, serviços, snapshot44 e retorno iOS passaram. Isso não permite aceitar qualquer retorno zero. A fonte PCI core fixada (commit958481f87fee0949ff6a9a4af77f7eb6dac8a149) detecta IO/prefetch em `drivers/pci/probe.c` e documenta ranges opcionais ausentes como somente leitura zerados em `drivers/pci/setup-bus.c`. Esses ranges não são necessários aos BARs MMIO não prefetch do BCM4350.

## Decisão e alternativas

- **Decisão:** reconhecer somente pedidos de desativação IO/prefetch quando o adaptador provar ausência pelos flags/probes PCI core e recursos vazios, e a política conservar baseline zero e confirmar os registradores vivos zerados. Tratar esses pedidos como no-ops sem escrita física; manter o restante do readback estrito.
- **Por quê:** trata a incompatibilidade medida sem ativar uma janela inexistente nem ampliar permissões de MMIO/BAR/decode/DMA. Preparar ambos os ranges opcionais agrupa falhas previsíveis antes de outro DFU.
- **Alternativas:** ignorar qualquer mismatch pode ocultar recursos incorretos; escrever em todos os registradores e aceitar zero não comprova ausência; alterar o kernel Image amplia o rebuild/rollback sem necessidade.
- **Reverter:** baixo; novos módulos/perfis serão selecionados explicitamente por hash; versões anteriores e defaults permanecem.
- **Status:** em curso offline, telefone no iOS carregando. Sem novo boot até build/integração qualificados.

## Arquivos e detalhes

Fase A (quatro arquivos): plano; `phone/kernel/n71-pcie-resource-write.h` (layout/estado/capture/write); novos `tests/n71_pcie_optional_ranges.c` e `tests/test_n71_pcie_optional_ranges.py`. Flags ficam desativados no layout anterior. Capture rejeita claims contraditórios e não altera o output se falhar. No-op exige root/register/width/value exatos e leituras vivas zero; erros/drift impedem writes, preservam primeiro erro, budgets e ownership. Contadores registram somente os pedidos efetivamente emulados. BARs/MMIO implementados mantêm comparação exata e rollback.

Fase B (até cinco arquivos): adaptador `phone/kernel/n71-pcie-resource-assign.h`, fixtures C do PCI host e seu runner, plano. Derivar flags de `pci_dev.io_window/pref_window` e recursos ausentes; registrar decisão/counters sem fabricar hardware ou readback. Qualificar adaptador real com API sintética, falhas de preflight, ausência contraditória, janelas implementadas, decode/master e restauração.

Fase C (fatias de até cinco arquivos): build externo na VM preservada; registros de qualificação, seletor por hash compatível com os builds anteriores; journal/coletor/composer; candidata privada separada. Executar gates afetados no Mac/Ubuntu ARM64, preservar fonte/config/Image/exports e cinco módulos não alterados. Não publicar binários, firmware, DT, perfis/chaves/snapshots/logs físicos. Confirmar módulos/ABI/contrato antes de carregar.

C1, cinco arquivos: plano; novo `scripts/host/n71_resource_optional.py`; `scripts/host/n71_resource_result.py` (evento preservado); `scripts/host/n71_resource_stage.py` (contrato obrigatório por metadata selecionada); novo `tests/test_n71_resource_optional.py`. Exigir relatório único/completo entre held e readback/result, capture compatível com pending, flags/counters coerentes, contadores limitados às tentativas sem escrita verificada. Preservar evento inteiro em proof/checkpoint/reuso/cleanup. Registros anteriores sem report continuam válidos somente nos builds anteriores.

C2, quatro arquivos: plano, `scripts/host/n71_resource_build.py`, nova `docs/evidence/n71-pci-optional-build.json` e novo `tests/test_n71_optional_build.py`. Selecionar bytes86.304/SHAfba31cb2 somente pela evidência de build/política/adaptador/host qualificada e vinculada à evidência readback anterior por SHA. Require readback e optional windows por metadata, REG_ON/ABI/interface preservados. Hash anterior readback e default resource mantêm contratos anteriores; não substituir evidências históricas ou perfis privados.

## Tarefas

- [x] A: política de no-op restrita, baseline/leituras vivas, contadores e guardas.
- [x] A: regressões de ranges ausentes/implementados, drift/erro, rollback e mutations por assertion no Mac/Ubuntu ARM64.
- [x] B: derivar flags do PCI core e relatar decisão; testar adaptador e restaurar corretamente.
- [ ] C: build, seleção, journal/candidata e reprodução sem novo DFU.
- [ ] Uma sessão física agrupada somente após os gates; conservar diagnóstico/cleanup e serviços. Não habilitar driver/DMA/radio nesta atribuição.
- [ ] Atualizar docs/issues com provas sanitizadas e limites; Wi-Fi/energia seguem abertos até provas próprias.

## Verificação

Rodar a nova fixture real da política e seu mutation runner; baseline deve passar e cada mutante deve compilar com Werror e morrer por SIGABRT/assertion. Import/compilação/timeout não contam. Reexecutar política e adaptador existentes porque incluem o header alterado. AST/lint fatal/diff/guard público; bundle com inputs/hashes e logs privados. Reutilizar gates independentes intactos. Layout legado sem flags continua estrito, inclusive a regressão física0x30 negativa. Nenhuma prova física positiva de atribuição, Wi-Fi ou carregamento está implícita nesses testes.

### Gate A — política qualificada, flags ainda não ativados no adaptador

Cinco arquivos: plano, header da política, fixture/runner próprios e `docs/evidence/n71-pci-optional-policy.json`. Mac e Ubuntu ARM64: 21 cenários/15 mutações novos; política anterior194/36 e adaptador65/57 requalificados, total280/108 por plataforma. Cinquenta e três inputs públicos iguais, AST/lint fatal/diff. A primeira rodada detectou que um mutante não compilava por parâmetro unused; fixture ajustada para conservar o uso do parâmetro sem o guard. Essa falha não contou como kill. Somente o gate final compilado/SIGABRT qualificou a prova. Nenhum build/módulo/boot novo; flags no layout padrão continuam false até a fase B provar suporte/ausência PCI core.

### Gate B — flags PCI core, recursos vazios e relato qualificados

Cinco arquivos: plano, adaptador, backend PCI compartilhado e fixture/runner próprios `tests/n71_pcie_optional_host.c` e `tests/test_n71_pcie_optional_host.py`. Mac/Ubuntu ARM64: 18 cenários/14 mutações novos e adaptador legado65/57 requalificado, total83/71 por plataforma;55 inputs/AST/lint fatal. Política21/15 e194/36 reutilizada com oito inputs relevantes intactos; conjunto C final298 cenários/122 mutações por plataforma. Backend conserva flags true nos casos legados e modela registros readonly nos novos. Ausência não pode ser inferida só do valor zero; flags de suporte e recursos flags/start/end vazios são verificados antes de capture. MMIO/BARs/decode e falhas/retry de restauração continuam estritos. Report único precede readback, conserva flags/counters e não repete após tentativa. Build/seleção/journal e prova física dessa correção ainda são gates separados.

### Gate C1 — contrato/journal opcional qualificado

Cinco arquivos definidos acima. Mac/Ubuntu ARM64:70 testes/119 mutações por AssertionError por plataforma,64 inputs iguais/AST/lint fatal. Nova fixture8/12; readback9/15, resultado9/29, estágio16/26, held21/30 e histórico7/7 requalificados. Registros ausentes/duplos/incompletos/fora da fase, flags/counters incompatíveis, proof alterado e metadata selecionada sem report são recusados. Journal conserva decisão/counters no assign, reuso sem setter e cleanup. Mutante de ordenação inicial produziu uma comparação impossível e erro de baseline; anchor corrigido para remover só o guard pretendido, sem contar essa tentativa. Somente a rodada final positiva qualificou a prova.

Build externo paralelo compilou seis módulos Werror/modpost/ELF/vermagic;PCIe86.304 bytes/SHAfba31cb2. Cinco módulos e fonte/config/Image/exports preservados, incluindo oito fontes PCI e seis fontes patched verificadas antes/depois. Esses bytes ainda não foram selecionados ou carregados no telefone. C2 integra evidência/hash e C3 compõe/checka a candidata agrupada antes de qualquer novo DFU.

### Gate C2 — novo build selecionado explicitamente

Quatro arquivos definidos acima. Mac/Ubuntu ARM64 passaram19 testes/45 mutações por AssertionError por plataforma,66 inputs/AST/lint fatal: novo seletor5/7, seletor readback5/9 e contrato resultado9/29. Exige evidência readback anterior por SHA, booleans exatos de política/adaptador/host, relato opcional compilado, fonte patched preservada e bytes/hash/ABI/REG_ON/interface. Acrescenta `assignment_optional_windows=true` somente ao build novo; hash anterior readback continua com seu report único, default resource mantém o contrato legado. Nenhum novo load/boot; C3 ainda verifica composição/coletor/candidata antes da sessão física.

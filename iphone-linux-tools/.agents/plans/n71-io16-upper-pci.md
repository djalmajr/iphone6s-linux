# Upper de disable em IO16 — issue39

## Contexto

O boot agrupado da candidata fba31cb2 declarou janelas IO/PREF presentes e recusou upper0x30=0000ffff com retorno0. A leitura no mesmo boot confirmou lower1c=0 e upper30=0, tipos base/limit0. Linux fixado958481f87fee0949ff6a9a4af77f7eb6dac8a149 define tipo0 como16 bits, lê upper somente para IO32 (`probe.c:397`) e escreve upper temporário sem condicionar ao tipo (`setup-bus.c:826`). Ausência do range inteiro não foi comprovada; a política anterior preservou corretamente a recusa.

## D1. Tratar somente o pedido temporário upper em IO16

- **Decisão:** opt-in separado `io16_upper_unused` no layout/adaptador. Capture exige IO presente de16 bits, lower e upper baseline0, sem conflito com io_absent. O único pedido emulado é root0:08/0x30/dword0000ffff, observado0, lower vivo0 ou00f0 (baseline ou disable) e upper vivo0. Sem escrita hardware; counter/report próprios. Lower00f0 continua escrito/verificado, junto de BARs/MMIO e restantes registradores.
- **Por quê:** trata o primeiro erro medido e a sequência PCI core sem declarar IO ausente nem ignorar mismatch geral. Decode/master/identidade/budget/rollback continuam exigidos antes da emulação.
- **Alternativas:** forçar flags de ausência contradiz o probe; aceitar upper de qualquer tipo ameaça IO32; mudar o Image amplia o rebuild/rollback. Nova instrumentação antes da mudança é possível, mas tipos/valores já foram coletados no mesmo boot e a fonte primária esclarece a sequência.
- **Reverter:** baixo; novo módulo somente por hash/metadata qualificados, defaults e perfis anteriores conservados.
- **Onde:** política/adapter/host, fases abaixo.
- **Status:** em curso offline; iPhone no iOS carregando. Sem novo DFU até qualificação completa.

## Arquivos e fases

A0 (até cinco arquivos): plano; novo `phone/kernel/n71-pcie-io16-upper.h` com helpers puros sem efeitos; `tests/test_n71_pcie_resource_write.py` e `tests/test_n71_pcie_optional_ranges.py` copiam a nova dependência sem mudar os gates anteriores. Helpers não são chamados nesta fatia. Validar import/AST/lint e compilação da base.

A1 (até cinco): plano, `phone/kernel/n71-pcie-resource-write.h` (layout/estado opt-in, capture e caminho noop), novo `tests/n71_pcie_io16_upper.c`, novo `tests/test_n71_pcie_io16_upper.py`, evidência de política. Fixture exercita sequência upperFFFF/lowerF0/upper0, rollback/sentinelas; default estrito, tipos32/mistos/reservados, baseline/live contraditórios, callbacks positivos/negativos, largura/status, COMMAND/MASTER, orçamento e erro latched. Mutantes compilados morrem por SIGABRT/assertion; compilação/import/timeout não contam.

B (até cinco): plano, `phone/kernel/n71-pcie-resource-assign.h`, backend PCI compartilhado e fixture/runner próprios. Derivar opt-in somente de janela presente padrão4K, tipo IO16/recursos coerentes; report único de captured/enabled/noops entre optional/readback. Testar flags, recursos, negação/repeat/cleanup e evento, sem driver/DMA. Requalificar integrações C afetadas nas duas plataformas.

C1 (até cinco): plano; parser IO16 novo; resultado/event; etapa/journal; teste próprio. Require report por metadata exata, ordenar após optional antes de readback, counters dentro das tentativas sem escrita, capturado coerente e noop positivo quando atribuído/enabled. Conservar evento inteiro até cleanup, faltar proof retém owners. Legados sem novo report continuam iguais.

C2 (até cinco): plano; build externo na VM; evidência sanitizada; seletor/hash; teste próprio. Preservar fonte/config/Image/exports/REG_ON/outros cinco módulos. Novo record exige readback/optional/io16, antigos defaults e bytes intactos.

C3 (até cinco): plano; dependências de cópia de gates se necessário; fixture composer/coletor real; prova da candidata; docs. Compor perfil novo privado, comparar payload/identidades/REG_ON, check antes de efeitos. Documentar/push branch/issues sanitizados; não integrar main/tag/release.

Física (até cinco): somente após A–C qualificados. Um boot agrupa acquire/assign/read-only/cleanup/retry/services/snapshot/sync/retorno iOS, preserva primeiro erro. Sem driver/DMA/radio nesta atribuição. Publicar resultados/limites próprios.

## Tarefas

- [x] A0: helpers separados e dependências dos gates anteriores.
- [x] A1: política opt-in e regressões/mutações Mac/Ubuntu ARM64.
- [x] B: adapter/report/fixtures e qualificação C final.
- [x] C1: contrato/journal estritos e compatibilidade.
- [x] C2: build/ABI/fonte preservados e seleção explícita.
- [x] C3: candidata privada/check qualificados; reprodução/publicação em andamento.
- [ ] Uma sessão física agrupada; atualizar issue39 com resultado/limites.

## Verificação

Reusar provas independentes intactas; gates afetados compilados Werror e assertions, AST/Flake8 fatal/diff/guard público e inputs por SHA. Nova flag false conserva comportamento legado. Fonte PCI primária fixada e provas físicas anteriores permanecem; logs/IDs/DT/firmware/chaves/snapshots não são publicados. Wi-Fi/IRQ/IOMMU/driver e energia/HDQ/carga continuam pendentes até prova física própria. Nenhum pacote/configuração global instalado no Mac.

### Gate A1 — política IO16 qualificada; adapter ainda sem opt-in

Mac/Ubuntu ARM64:49 cenários/20 mutações novos, ranges21/15, política194/36, adapter65/57 e optional host18/14 requalificados, total347 cenários/142 mutações compiladas SIGABRT/assertion em cada plataforma. Cinquenta e oito inputs iguais/preservados, AST e Flake8 fatal. A fixture reutiliza somente o backend de configuração, mantém lower gravável e modela upper sem efeito; sequence lower/status/rollback, drift/erros, scope e budgets foram exercitados. Defaults sem flag continuam estritos. Nenhum build/candidata/load/DFU desta integração; B deve derivar a flag e report próprio antes da seleção física.

### Gate B — derivação e report IO16 qualificados

Mac/Ubuntu ARM64:20 cenários/17 mutações novos, adapter65/57 e optional host18/14 requalificados,103/88 por plataforma,60 inputs/AST/lint fatal. Gate puro A1 de264 cenários/71 mutações reutilizado com11 inputs relevantes idênticos; conjunto C final367/159 por plataforma. Derivação lê ambos os tipos IO e exige janela presente padrão4K, recurso vazio ou IO16 de4K coerente; IO32/mistos/reservados/1K não habilitam o opt-in. Primeiro erro/leitura/cleanup e report único entre optional/readback foram verificados. Backend dos casos legados deixa IO16 fora do escopo; cenários próprios modelam upper readonly com lower gravável. Sem build/load/DFU novo; contrato host ainda é gate C1.

### Gate C1 — evento IO16 obrigatório e conservado no journal

Mac/Ubuntu ARM64:78 testes/131 mutações por AssertionError por plataforma,66 inputs iguais/preservados, AST/lint fatal. Novo contrato8/12; optional8/12, readback9/15, result9/29, stage16/26, held21/30 e history7/7 requalificados. Report único entre optional/readback, captured coerente, ausência/IO16 mutuamente exclusivos, counters combinados limitados às tentativas sem escrita e noop obrigatório quando atribuição positiva/enabled. Journal conserva os campos na ação/checkpoint/reuso/cleanup; faltar o report exigido não salva proof e retém owners. Defaults/resultados antigos sem report ficam iguais. Build externo paralelo passou seis módulos Werror/modpost/ELF/vermagic e preservação de fonte/config/Image/exports/outros cinco;PCIe87.008 bytes/SHAd6188a13. Esses bytes não são selecionados ou carregados até C2/C3.

### Gate C2 — build real e seleção IO16 qualificados

Mac/Ubuntu ARM64:25 testes/54 mutações por AssertionError por plataforma,69 inputs/AST/lint fatal; seletor novo6/9, optional5/7, readback5/9 e resultado9/29. Evidência nova é vinculada às bases optional/readback/assignment por SHA e exige booleans exatos do contrato IO16/report compilado; records requerem os três reports. Hashes anteriores conservam seus requisitos antigos, unknown ou evidence ausente/alias recusam seleção. Seis módulos da VM passaram Werror/modpost/ELF/vermagic,49 inputs, PCIe87.008 bytes/SHAd6188a13; outros cinco e fonte/config/Image/exports preservados. Sem novo Image, load/DFU, pacote/config global. C3 ainda compõe/checka o perfil e requalifica as integrações antes da sessão física.

### Gate C3 — candidata completa qualificada sem outro DFU

Mac/Ubuntu ARM64:82 testes/132 mutações por AssertionError por plataforma,72 inputs/AST/lint fatal. Baseline de composição20 testes/34 mutações mais3 de forwarding do coletor; stage16/26, readback9/15, optional8/12, IO16 8/12 e held21/30 requalificados. Nova fixture compara perfil antigo/novo e exige os três reports no collector --check. Primeira tentativa da fixture usou helper inexistente e terminou AttributeError; corrigida para o argv explícito existente, erro preservado/excluído. Só os gates finais positivos contam.

Candidata real separada passou composer/--check, oito arquivos privados700/600; deployment/payload/DT/kernel/loader/initramfs/identidades/REG_ON iguais ao perfil optional anterior. Somente PCIe e seu SHA na provenance mudaram. Módulo não carrega automaticamente. Nenhum load/boot novo; documentação/publicação do checkpoint precedem a sessão física agrupada.

### Documentação e checkpoint

`docs/STATUS.md` e `docs/N71_PME_ASPM_CANDIDATE.md` registram a fase, receita Multipass/make externa, composição/check/gates, comparação do perfil real e limitações. Evidências históricas offline permanecem como checkpoints; a candidata ainda precisa da sessão física própria. Publicar somente a branch autorizada e atualizar issue39, mantendo merge/tag/release pendentes.

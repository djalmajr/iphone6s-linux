# Disable PREF64 com tipos preservados — issue39

## Contexto

A sessão IO16 publicada em2488b12 avançou até root0:08/0x24: pedido0000fff0, anterior00010001 e retorno0001fff1, callbacks0. Os endereços mudaram e os dois tipos64 continuaram1; uppers0 foram lidos separadamente após a tentativa. A atribuição foi corretamente recusada; cleanup liberou owners, snapshot/sync passaram e o operador confirmou fallback ao iOS, sem bateria posterior pelo USB.

Na fonte fixada958481f87fee0949ff6a9a4af77f7eb6dac8a149, `drivers/pci/probe.c:552–565` exige tipo64 e upper gravável para `pref_64_window`; `probe.c:488–496` representa recurso MEM/PREF/MEM64/tipo1 e0..fffff. `drivers/pci/setup-bus.c:867–889` escreve upper limit0, disable0000fff0, upper base/limit0. `include/uapi/linux/pci_regs.h` define tipo64=1 nos dois campos de quatro bits. A fonte primária local foi consultada; a web upstream confirma os campos, mas não substitui o checkout fixado.

## D1. Comparar o valor completo esperado somente no disable PREF64 comprovado

- **Decisão:** opt-in `pref64_disable` independente dos defaults. Derivar apenas de `pref_window`/`pref_64_window`, ambos os tipos1, recurso exato MEM/PREF/MEM64/tipo1 sem parent/child e range0..fffff. Capture exige lower00010001 e uppers0; `pref_absent` é incompatível. Para root0:08/0x24/dword0000fff0, confirmar lower vivo00010001 ou0001fff1, releitura igual ao observado e uppers0. Manter o pedido hardware0000fff0; comparar readback completo com0001fff1. Nunca ignorar bits de endereço/reservados, transformar enable em disable ou mudar BARs/MMIO.
- **Por quê:** corresponde à primeira falha medida e ao probe PCI, sem inventar ausência nem tolerância genérica. Decode/master/identidade/budget, primeiro erro e rollback permanecem. Repetição de disable já aplicado faz no-op somente depois dos mesmos guards vivos.
- **Alternativas:** alterar o Image/core amplia build/rollback; escrever tipos1 no pedido muda o pedido do core sem necessidade; mascarar qualquer readback aceita corrupção; nova sessão só de instrumentação custaria DFU e não substituiria guards vivos na candidata.
- **Reverter:** baixo; módulo/perfil separados selecionados por SHA, builds/defaults antigos preservados.
- **Onde:** helper/política, adapter/report, host/journal, seletor/build e candidata nas fases abaixo.
- **Status:** em curso offline. Sem novo DFU até qualificação completa.

## Arquivos e fases

### D2. Capturar os tipos uma vez, antes de publicar ownership

- **Decisão:** adapter confere probes e recurso; os dois tipos e uppers são conferidos pela captura exata já qualificada. Remover a releitura preliminar duplicada de lower no adapter. Verificar novamente lower/uppers depois da atribuição antes de sucesso, sem escrita adicional.
- **Por quê:** a captura rejeita qualquer tipo/baseline contraditório antes do claim e não publica estado parcial. O mutante da validação duplicada não mudava nenhum resultado porque a captura já recusava o mesmo caso; uma única prova evita leitura e estado redundantes.
- **Alternativas:** manter duas validações do mesmo lower aumenta IO sem nova garantia; enfraquecer capture elimina a prova da baseline de rollback. Ambos rejeitados.
- **Reverter:** baixo; recolocar a leitura preliminar, mantendo capture como prova obrigatória.
- **Onde:** `n71-pcie-resource-assign.h`, helper/capture e fixture de adapter. Fixtures incluem falha antes de capture e drift depois de assign.
- **Status:** aplicada e qualificada offline.

A0 (até cinco arquivos): plano, novo `phone/kernel/n71-pcie-pref64-disable.h`, fixture/runner `tests/n71_pcie_pref64_disable.c`/`tests/test_n71_pcie_pref64_disable.py` e evidência de política. Helper inicialmente sem caller; provar baseline/live/scope/erros/releituras com mutantes compilados mortos por assertion.

A1 (até cinco): plano e dependências dos três runners C que copiam resource-write. Depois A2 (até cinco): plano, `phone/kernel/n71-pcie-resource-write.h`, fixture/runner próprios e evidência. Flag/capture/comparação completa, counter de escritas tipadas verificadas e primeiro erro com valor esperado explícito; defaults continuam exatos. Requalificar gates C afetados uma vez nas duas plataformas.

B (até cinco): plano, `phone/kernel/n71-pcie-resource-assign.h`, backend PCI compartilhado e fixture/runner de adapter. Derivar opt-in somente das provas acima; report próprio captured/enabled/writes após IO16, antes readback. READBACK legado conservado, campo expected somente na falha tipada; pedido original permanece no report/refusal. Sem enable/bind/DMA/radio.

C1 (até cinco): plano, parser PREF64 novo, parser readback e fixture/runner próprios. Campos/ordem/contradições/counters estritos; expected somente no disable comprovado e somente0001fff1, erro latched/pedido original preservados. C2 (até cinco): plano, resultado/event, stage/journal, dependências de cópia e fixture própria. Report exigido por metadata exata, evento conservado até cleanup; faltar proof retém owners e layouts antigos não mudam.

D (até cinco): plano, evidência/build externo na VM, seletor/hash e teste. Fonte/config/Image/exports/REG_ON/outros cinco módulos preservados; novo SHA exige reports readback/optional/IO16/PREF64. E (até cinco): plano, fixture composer/coletor, evidência da candidata e docs. Compor/checkar perfil privado novo, comparar payload/identidades/REG_ON; publicar apenas branch/issues autorizadas.

Física (até cinco): somente após A–E. Um boot reúne acquire/assign/read-only/cleanup/retry/services/snapshot/sync/retorno iOS. Preservar primeiro erro se negativo; não repetir assign ou scan durante cleanup. Nenhum outro pedido ao operador até candidata pronta.

## Tarefas

- [x] A0: helper sem efeitos e regressões/mutações.
- [x] A1/A2: integração na política, defaults/readback/rollback qualificados.
- [x] B: derivação/report/adapter qualificados.
- [x] C1: parsers de contrato/readback e legados qualificados.
- [x] C2: dispatch, stage/journal e legados qualificados.
- [ ] D: build/ABI preservados e seleção explícita.
- [ ] E: candidata/check/reprodução/publicação.
- [ ] Sessão física agrupada e resultado/limites na issue39.

## Verificação

Mac e Ubuntu ARM64, Werror/assertions, AST/Flake8 fatal, inputs/hashes/logs/exits privados. Erro de compilação/import/timeout não conta como mutação morta. Reusar gates independentes intactos; rerodar somente os afetados. Readback do valor completo esperado e rollback exato da baseline, sentinelas STATUS/COMMAND/BAR/MMIO, perda/troca de tipos e endereços, falhas brutas e ordem/retention do journal precisam de casos observáveis. Nenhum firmware/DT/chave/ID/raw log/snapshot publicado; sem pacote/configuração global do Mac, main/merge/tag/release. Provas offline não habilitam Wi-Fi, carga ou telemetria.

### Gate A0 — helper inativo qualificado

Mac/Ubuntu ARM64:35 cenários/15 mutações compiladas SIGABRT/assertion por plataforma, seis inputs iguais/preservados, AST/Flake8 fatal. Captura exata, tipos/endereço/uppers vivos, releitura, escopo e erros positivos/negativos passaram sem escrita hardware. Gate em cópia descartável conserva logs/exit SHA; teste inicial direto também passou. Nenhum caller, módulo/Image novo ou DFU desta fatia. [Prova](../../docs/evidence/n71-pci-pref64-policy.json).

### Gate A1/A2 — política integrada; opt-in ainda sem derivação no adapter

Fixture/runner novos `tests/n71_pcie_pref64_policy.c`/`tests/test_n71_pcie_pref64_policy.py` exercitam a política real com tipos readonly/endereço gravável e rollback. Mac/Ubuntu ARM64:422 cenários/185 mutações compiladas SIGABRT/assertion por plataforma,58 inputs iguais/preservados, AST/lint fatal. Novos20/11 mais helper35/15; IO16, optional, política/adapter/host legados requalificados. Mutante inicial do counter sobreviveu porque faltava verificar o counter após uma escrita não-PREF; caso corrigido e probe negativo conservado/excluído. Somente a matriz final positiva conta.

O pedido hardware permanece0000fff0, mas readback completo esperado é0001fff1 somente com opt-in capturado e guards vivos. Falha conserva pedido original/expected/antes/depois/callbacks; contador avança só depois de escrita tipada verificada. Defaults, primeiro erro e rollback exato passaram. Sem módulo/Image/build/load/DFU novo; B ainda precisa derivar o opt-in, emitir report e qualificar o adapter.

### Gate B — adapter e formatter único qualificados

Mac/Ubuntu ARM64:123 cenários/102 mutações compiladas por plataforma,60 inputs/AST/lint fatal. Pure A2 de319 cenários/97 mutações reutilizado com42 inputs iguais; C final442/199 por plataforma. Novos20/14 mais adapter65/57, optional host18/14 e IO16 host20/17 requalificados. Probes/recurso, captura exata antes do claim, final lower/uppers, erro original, cleanup/repeat e report único passaram.

Fixtures iniciais omitiram a sentinela MEM e esperavam restauração de upper limit nunca capturado; corrigidas para o ownership real. Check preliminar duplicado de tipos foi removido conforme D2. Três anchors legados ficaram duplicados por duas branches de impressão; consolidado formatter único com sufixo expected e atualizado um anchor. Tentativas negativas preservadas/excluídas; somente os gates finais positivos contam.

Build externo final na VM passou seis módulos Werror/modpost/ELF/vermagic,50 inputs;PCIe88.120 bytes/SHA968e6a06. Fonte/config/Image/exports/REG_ON/outros cinco módulos preservados. O build anterior de88.392 bytes não será selecionado porque precede o formatter final. Ainda sem seleção/candidata/load/DFU; contrato/journal host e seletor por SHA são gates seguintes.

### Gate C1 — parsers PREF64/readback qualificados

Mac/Ubuntu ARM64:84 testes/145 mutações por AssertionError por plataforma,68 inputs iguais/preservados, AST/lint fatal. Novo contrato6/14, mais IO16/optional/readback/result/stage/held/history legados requalificados. Report completo/único/ordenado, capture/ausência/counters, expected0001fff1 somente no disable PREF64 capturado, baseline/pedido/refusal originais e callbacks brutos passaram. Perda de tipos retorna uma falha válida com after igual ao pedido original, mas diferente do expected completo; isso não passa como sucesso. Shapes legados ficam iguais.

Mutante unknown inicialmente sobreviveu porque o caso apenas substituía o report exigido; adicionada linha desconhecida completa ao lado de uma prova válida. Casos de scope e baseline também foram ampliados. Probe negativo preservado/excluído. C2 ainda precisa despachar o novo parser e exigir/conservar os campos no journal; nenhum perfil/load/DFU novo.

### Gate C2 — dispatch e journal qualificados

Mac/Ubuntu ARM64:89 testes/149 mutações por AssertionError por plataforma,69 inputs iguais/preservados, AST/lint fatal. Journal novo5/4 mais contrato6/14 e legados requalificados. Contexto PREF64 é validado antes de interpretar expected; shape/ordem legados do resultado conservados. Metadata exata exige o report; a cópia do compositor inclui o novo parser. Proof ausente retém owners e não salva atribuição; sucesso/reuso/cleanup conserva counter/evento e um setter, falha tipada/cleanup retry conserva pedido0000fff0/expected0001fff1/erro-5, sem repetir assignment.

Kernel/módulos não mudaram nesta etapa; build final88120/SHA968e6a06 permanece. D ainda vincula as provas ao hash selecionado; nenhuma candidata/load/DFU nova.

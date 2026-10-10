# Integração host do runtime brcmfmac N71

## Contexto

Goal autorizado: Wi-Fi nativo e energia, solo e com o mínimo de DFU/reboots. Fase kernel2b em6e1cc9c qualificada com575 cenários/455 mutações por plataforma, caller/actions/getter/cleanup reais e módulo ARM64 completo; nenhum perfil/módulo/firmware ativado. Issue40 permanece aberta. A CI específica desse head terminou com seis jobs verdes; não repetir jobs terminados.

`scripts/host/n71_held_session.py:44` captura o snapshot, `:129` salva o journal e `:306` coordena aquisição/assign/release. `n71_iommu_result.py:39` produz getters, `:72` liga estado ao caller e `:150` valida continuidade. O formato legacy MSI é passivo/opcional e exige igualdade ao retomar. O novo getter runtime tem15 campos ordenados e pode registrar primeira causa assíncrona e contador de reads crescente. Não tratar publicação, probe0 ou insmod0 como firmware/radio pronto.

## Arquivos e fases

### A. Coleta e contrato de observação (até cinco arquivos)

- Novo `scripts/host/n71_driver_runtime_result.py`: getter opcional/passivo, parser canônico de15 campos, vínculo com caller/held/opt-in imutável, continuidade conservadora e parser do resultado nativo de action. `requested` é seleção, `ready` é host, `published` é intenção; não criar flags de firmware/radio proof.
- `scripts/host/n71_iommu_result.py`: incluir coleta opcional no modo IOMMU e validações de snapshot/resume/saved. `driver_runtime` ausente equivale a false, com boolean estrito. Modos anteriores continuam aceitando getter ausente e mantendo os formatos existentes; modo runtime exige o getter.
- Novo `tests/test_n71_driver_runtime_result.py`: fixtures pequenas, protocolo completo, erros/owners parciais, limites e shell realmente executado com sysfs temporário; regressão do coordinator real e mutations AST executadas com AssertionError, sem contar import/compilação/timeout como kill.
- Este plano; um ajuste de fixture existente apenas se um gate real demonstrar necessidade, sem remover cobertura.

**Contrato A:** exatamente um marker/linha completa, integers canônicos, booleans0/1, uint32 reads e errno-4095..0; pending deve corresponder a active/refs/PM/overrides. Host removido conserva somente requested/error/session_error. Getter é read-only e não exige iPhone/PIN/DFU. Snapshot compara scan_pending, held, cleanup_error e primeira causa do caller; quando este ainda não latcheou erro, a causa runtime não pode ser descartada. Retomada permite somente reads crescentes e surgimento de primeira causa assíncrona0→negativa enquanto seleção/owners/publicação permanecem iguais; erros negativos existentes não mudam nem desaparecem. Essa coleta não autoriza reinterpretação dos getters MSI/IOMMU legados nem efeito de hardware.

**Action A:** `N71_PCIE_DRIVER_RESULT` é único no delta depois da intenção, com action prepare/publish/release/cleanup, errno e owners canônicos, operação causal e sufixo de ausência de prova de firmware/radio. Parser recebe a action esperada e recusa outra action/registro incompleto/duplicado. O journal seguinte usará esse contrato, sem fabricar sucesso por getter isolado.

### B. Intenções, provas e recuperação no mesmo boot

Após ler os contratos atuais, fechar uma fatia específica de até cinco arquivos para prepare/publish/release e unload normal. Intent durável antes de cada setter/rmmod; prova nativa e SSH exit depois; refusals conservam owners e erro inicial. Não repetir action com intenção sem prova: reconciliar getters/logs do mesmo boot antes de novo efeito. Firmware pendente não autoriza unbind/unload forçado. Integrar cleanup runtime antes do diagnóstico, mantendo providers quando ainda owned. Retomada com driver ativo precisa verificar mudanças assíncronas comprovadas, sem simplesmente relaxar o histórico legacy.

### C. Seleção, build/composição e entrada explícita

Qualificador da evidência/build runtime e novo opt-in de perfil/CLI; somente o módulo ARM64/hash/ABI/exports qualificados. Não ampliar o selector legacy nem escolher runtime por presença de arquivo. Inputs transitivos novos devem entrar no bundle real. Preservar perfil/image/source/config/exports anteriores; não ativar automaticamente nem solicitar DFU nessa fase.

### D. Firmware/energia e candidata física agrupada

Preparar firmware/calibração privados compatíveis com chip4350/revisão8 e módulos por hash, energia/HDQ/telemetria. Reunir a sessão: firmware concluído, scan/associação/DHCP/SSH, IRQ/DMA e energia; conservar serviços/snapshot/recovery. Só pedir um DFU quando a candidata inteira e o monitor estiverem prontos. Goal completo não termina com gates offline.

## Tarefas

- [x] Implementar e qualificar coleta/parser/coordinator em Mac/Ubuntu ARM64.
- [ ] Integrar intents/actions/unload/release e recuperação comprovável no mesmo boot.
- [ ] Integrar seleção/composição/CLI explícita, com artefatos preservados.
- [ ] Preparar firmware/calibração/energia antes de solicitar a sessão física agrupada.
- [ ] Comprovar Wi-Fi e energia no aparelho; documentar limites e atualizar40/9/2.

## Verificação

Gates novos e de compatibilidade afetados, mutations executadas, AST/lint fatal sem instalação global; não há typechecker Python configurado. Shell bash/sh syntax e execução sem hardware em pasta temporária. VM dedicada usa fonte/build preservados; build C anterior pode ser reutilizado enquanto inputs relevantes não mudarem. CI do head6e1cc9c é acompanhada separadamente; publicação somente da branch autorizada. Logs/firmware/módulos/identidades privados, documentação e evidência sanitizada públicos.

FaseA:80 testes/154 mutações por AssertionError, Mac/Ubuntu ARM64; novo protocolo8/22, IOMMU21/53, MSI7/16, held21/30, resources16/26, histórico7/7.260 inputs finais verificados na VM e no Mac, AST/lint fatal aprovados; schema/frame usam objetos nas chamadas novas. O primeiro mutante de unicidade permitia um registro ausente e causava IndexError; a mutação foi restringida à duplicidade, sem aceitar erro de harness como kill. As rodadas finais comprovam80/154. Os69 inputs C anteriores estão iguais, portanto build/gates kernel575/455 permanecem válidos sem outro build ou boot. CI6e1cc9c concluiu os seis jobs verdes nos dois eventos. Nenhum setter, módulo/perfil/firmware ou DFU ativado.

Próximo requisito: fechar a faseB com intenção/prova/recuperação por action e unload normal antes de release, incluindo o tratamento de erro runtime no cleanup. A coleta A não relaxa a igualdade/histórico MSI/IOMMU legacy nem resolve por si a retomada com driver ativo. Só selecionar/cargar a candidata depois das fasesB/C e preparação firmware/energia.

Prova pública da fase A e reprodução: [evidência](../../docs/evidence/n71-driver-runtime-observation-qualified.json) e [receita](../../docs/N71_BRCMFMAC_RUNTIME.md#observação-host--fase-a). Código3dfa1cb,80/154 por plataforma; fases B/C/D permanecem em execução.

### B1. Journal das actions nativas — contrato fechado

**Arquivos (cinco):** novo scripts/host/n71_driver_runtime_stage.py, scripts/host/n71_held_session.py, novo tests/test_n71_driver_runtime_stage.py, este plano e n71-funcional-goal-decisoes.md. A seleção física continua fechada até B2/C; não inserir chamada automática de prepare/publish ou unload nessa fatia.

**Resultado:** ledger integrado ao journal held, com seleção bool estrita, prepare/publish/release em ordem, intent salvo/fsync antes do setter, prova privada completa e resultado derivado depois. Cada tentativa usa nome exclusivo por índice; refusals e owners parciais permanecem. Nenhuma repetição de intent incompleto; reconcile usa somente snapshot/getter/histórico nativo do mesmo boot, registra observação sem inventar SSH exit e não executa setter. Captura direta exige exit da action/shell/SSH coerentes e getter compatível com resultado nativo. Counter/primeira causa podem progredir, mas owners/publicação/cause existentes não podem desaparecer. Não declarar firmware ou radio readiness.

**Recuperação:** load_source valida seleção, forma/order/limites do ledger, hashes de proofs pelo journal existente, vínculo entre cada before/history e native result/getter. Um proof escrito antes da última atualização do ledger é reaproveitado, não reexecutado. Intenção sem prova/sem registro nativo permanece pendente. Save fsync do arquivo e diretório antes de permitir efeito; log de proof fsync antes de salvar o hash.

**Verificação:** testes de filesystem privado e journal real, interrupção após intent/apos proof, direct/observed e erros de transporte/nativo, primeira causa e owners parciais; mutations executadas exigem AssertionError sem erro de harness. AST/lint fatal Mac/Ubuntu ARM64 e gates held/observação afetados; não repetir C/build preservados. B2 integra execução/normal unload/cleanup/histórico/estado MSI-DMA, C habilita seleção/CLI; só depois firmware/energia e teste físico agrupado.

**B1 qualificada:**90 testes/169 mutações por AssertionError em Mac/Ubuntu ARM64; novo ledger10/15 e os seis gates anteriores80/154.263 inputs finais conservados, AST/lint fatal aprovados, sem typechecker Python. Integração no journal/source loader reais e shell POSIX em filesystem temporário; nenhuma action automática, seleção/perfil ou DFU ativado. A primeira fixture usava proof com baseline completo num validador de delta legacy; a integração distingue somente os novos proofs runtime. O collector real filtra stdout, portanto a action valida o log privado integral. Erros de harness não contam como kills; o gate final completo é o aceito.

**B2 ainda necessária:** integrar actions ao coordenador, unload normal e cleanup; validar MSI/DMA/histórico enquanto driver ativo; reconciliar a janela de crash anterior ao registro do hash de proof e checkpoint antigo/ausente, sem reexecutar setter nem sobrescrever arquivos privados. B1 cobre intent pendente observado e proof cujo hash já foi registrado antes de completion; não declarar todos os pontos de crash recuperáveis nem habilitar C antes dessas condições.

### B2a. Continuidade das observações durante o driver — contrato fechado

**Fases limitadas:** plano/decisão (este arquivo e n71-funcional-goal-decisoes.md); depois cinco arquivos executáveis: scripts/host/n71_driver_runtime_result.py, scripts/host/n71_iommu_result.py, novo tests/test_n71_driver_runtime_continuation.py, tests/test_n71_driver_runtime_result.py e tests/test_n71_iommu_result.py. A fixture antiga do coordinator precisa agora de boot/ledger publicado e seu selector de mutação deve atingir o dispatch runtime real; o gate IOMMU mantém a mutação de retained apontando à expressão atual. Não remover sua cobertura. A CLI/perfil permanece sem ativação nessa fase; não executar setter, insmod ou rmmod para qualificar esses parsers.

**Resultado:** após publicação comprovada no ledger B1 e com os seis owners runtime/held/ready/publicação ainda retidos, a observação aceita o vetor único do brcmfmac: mappings0/1, slotmask0/1 e child0/1. Domínio child nasce antes dos vetores e pode ficar vivo depois de pci_free_irq_vectors; não exigir child=mappings nem apagar domínio manualmente. Child já observado não desaparece enquanto os consumers retidos seguem vivos. Providers e campos MSI/IOMMU estáticos não mudam; a lease MSI manual fica vazia. Contadores/causa efetiva runtime usam o contrato A. Erro novo do getter MSI pode aparecer, mas não desaparecer ou mudar; a exceção é precedência da primeira causa latcheada no caller, validada contra os dois snapshots. Getters são sequenciais e não constituem uma captura atômica, nem prova de entrega IRQ/DMA/radio.

**Escopo:** sem publicação provada, sem owners completos ou com runtime desligado, conservar a continuidade estrita anterior. A flag sozinha nunca autoriza drift. O coordinator obtém a prova do ledger validado; compara boot e snapshots do caller/seleção antes da retomada. Retained passa a aceitar somente essa associação runtime comprovada, preservando a aquisição original e seu nível de prova. Não relaxar n71_held_history, resources, source checkpoint ou cleanup nesta fatia; esses contratos serão ligados ao coordenador B2b antes da seleção C.

**Verificação:** API/coordinator real, sequência domínio0→1, vetor0→1→0 e domínio ainda1 após free; rejeitar grants extras, providers/owners drift, publicação ausente/unprovada, manual lease, causa apagada e boot diferente. Mutations executadas devem causar AssertionError, sem erro de harness; AST/lint Mac/ARM64 e gates host afetados. Os69 inputs C e módulos oficiais/diagnóstico permanecem iguais, sem rebuild/DFU. Referência: fonte fixada drivers/pci/msi/irqdomain.c235–238 e API free_irq_vectors; n71-wlan-msi-native.h22–25 já registra o domínio vivo. O adapter release confere child_mappings0 e permite domínio vazio até consumer removal, portanto não requer mudança de kernel.

**B2a qualificada em c8ab8ee:**98 testes/186 mutações por AssertionError por plataforma no Mac/Ubuntu ARM64,267 inputs finais conferidos, AST/lint fatal; sem typechecker Python. Fixture inicial compartilhava ACTIVE e contaminava o baseline; seus kills foram descartados. Estados clonados e baseline verde obrigatório resolvem a categoria. A âncora do gate IOMMU foi atualizada preservando a mutação.69 inputs C inalterados, build e módulos anteriores reutilizados, nenhum efeito no aparelho. B2b coordenador/histórico/resources/cleanup/unload e recuperação de crash ainda pendentes; C continua sem ativação.

### B2b1. Recuperação read-only de checkpoint/intent — contrato fechado

**Arquivos executáveis (três):** novo scripts/host/n71_driver_runtime_recovery.py, integração localizada em scripts/host/n71_held_session.py e novo tests/test_n71_driver_runtime_recovery.py. Plano/decisão são versionados antes, em fase separada. Sem alterar a fonte/build/kernel, perfil/CLI ou carregar módulos.

**Resultado:** com runtime selecionado e ledger não vazio, validar diretório privado, identidade/ABI/boot, flags, ledger, hashes de proofs registrados e checkpoint existente antes de qualquer leitura SSH. Capturar uma observação completa read-only usando o snapshot real; exigir mesmo boot/módulos/parâmetros, prefixos de baseline/checkpoint/proofs/intent e ausência de action extra. Completion pendente exige um único resultado nativo da action esperada e getter coerente, com mode observed e shell_exit null. Sem resultado nativo completo, recusar sem repetir setter.

**Arquivos de origem:** nunca alterar, sobrescrever ou promover proof sem hash registrado. Um arquivo órfão continua preservado; a prova de recuperação vem exclusivamente da nova observação do mesmo boot. Criar uma cópia privada e exclusiva, contendo somente metadados/proofs validados, completion observada e checkpoint completo novo. O loader held existente revalida essa cópia e o próximo journal registra seus próprios hashes/intents antes de efeitos. Checkpoint ausente é permitido somente nesse caminho runtime com intent comprovável; checkpoint existente inválido nunca é ignorado. Sem ledger runtime, conservar o loader e as recusas legacy.

**Histórico:** entre âncora provada e leitura nova, aceitar somente os REG_ON_READ corretos e o resultado nativo correspondente ao intent pendente. A action já concluída não é reemitida. Completed runtime state conserva owners/publicação/causa e contador monotônico; pending native mantém owners parciais/causa. Não aceitar cleanup/unload/resource action sem seus contratos específicos. Erro de transporte, boot/hash/history drift ou prova ausente não autoriza efeito.

**Verificação:** loader e filesystem/journal reais; crashes antes do hash e completion, checkpoint antigo/ausente, proof órfão preservado byte a byte, partial owners/causa, getters/integridade/boot/extra action recusados. Mutation baseline verde e kills somente por AssertionError; AST/lint Mac/ARM64, gates afetados, inputs C preservados. Integração de unload, histórico de ações do driver em execução, resources/cleanup e seleção C continuam necessárias depois desta fatia; nenhuma ação física do operador agora.

**B2b1 qualificada em4e4177f:**110 testes/196 mutações por AssertionError por plataforma Mac/Ubuntu ARM64,270 inputs íntegros e69 C preservados. Novo gate12/10, snapshot/loader/journal/filesystem reais, origem e órfão byte a byte intactos. A janela do histórico começa no intent, incluindo resultado já presente no checkpoint. O seletor inicial de prefixo era redundante; o teste agora protege timestamp do checkpoint. IndexError de harness descartado; expressão duplicada do allowlist movida para o helper sem retirar cobertura resource. Matriz final completa, AST/lint fatal aprovados, sem typechecker Python. Aviso gRPC do Multipass após exit0 não invalidou arquivos/hashes de resultado. Nenhum setter, perfil/CLI, build, iPhone ou DFU alterado; unload/causalidade resources/cleanup e seleção C ainda pendentes.

### B2b2. Módulos WCC e barreira de unload — contrato fechado

**Fonte conferida:** kernel fixado958481f, pcie.c2735–2736 seleciona WCC para BCM4350; fwvid.c153–175 faz request_module somente se o vendor não está registrado,114–143 remove seus buses no unregister. PCI bus.c345–375 só permite binding na publicação; pci-driver.c1536–1543 recusa binding ainda bloqueado. Firmware main.c1208–1220 retém module/device até o callback terminar. Fluxo recomendado: prepare → módulos rfkill/cfg80211/brcmutil/brcmfmac/WCC → publish. Prepare recusa driver já registrado, por isso nunca pre-carregar core antes dessa action. Não autocarregar BCA/CYW/rfkill-gpio.

**M1 (dois arquivos):** novo scripts/host/n71_driver_modules.py e novo tests/test_n71_driver_modules.py. Selecionar os cinco módulos da evidência pública PCIe qualificada, validar ABI/bytes/SHA/depends; coletar os oito nomes conhecidos, state/refcnt/holders, registro do driver, boot e hashes dos cinco arquivos staged no diretório exclusivo existente. Parser completo/canônico e getter read-only. Loads exigem prepare completo, publicação0 e causas0; unload normal exige target sem refs/holders e, antes de WCC, core com somente o holder WCC/refcnt1. Revalidar os guards no próprio comando remoto antes do efeito, sem force/unbind e sem interpretar unload como prova física DMA.

**Receipt M1:** arquivo exclusivo por índice/action/name dentro do diretório privado da sessão. Intent remoto com boot/SHA e índice antes de insmod/rmmod; exit da operação depois, snapshot completo e receipt no output. Não executar se já existe receipt. Um receipt incompleto nunca autoriza repetir efeito. Load não usa modprobe/autoload e nunca instala pacote no Mac ou altera perfil automaticamente.

**M2 (até quatro arquivos):** novo scripts/host/n71_driver_module_stage.py, novo tests/test_n71_driver_module_stage.py, hooks localizados em n71_held_session.py e n71_driver_runtime_recovery.py. Ledger separado no journal: manifest imutável, load em prefixo fixo, unload em ordem inversa, failed action retry somente com completion comprovada e sem owners divergentes. Intent fsync antes do comando; resultado direto exige concordância operação/SSH e presença; recuperação usa leitura de receipt/presença do mesmo boot e shell_exit null, conservando exit da operação quando o receipt completo o prova. Sem receipt completo, admitir somente transição observada exata do target e manter resultado de operação desconhecido; sem transição, continuar pendente, sem replay. Hash/proof/checkpoint e origem/órfão seguem B2b1; não eliminar recusas legacy.

**Coordenador seguinte:** ligar start/observe/stop explícitos, unload antes de driver-release e cleanup, causalidade resources/IOMMU e histórico. C só habilita perfil/CLI depois desses contratos; firmware/calibração/regdb/energia antes da sessão física agrupada. Não afirmar que M1/M2 isoladas já fornecem Wi-Fi, energia ou todos os pontos de crash recuperáveis.

**Verificação:** metadata real qualificada, POSIX shell/filesystem com insmod/rmmod sintéticos, ref/holder busy antes de efeito, recibo existente recusa replay, boot/hash/manifest/ordem/causa preservados. Mutations reais com baseline verde e AssertionError, AST/lint Mac/ARM64; reutilizar69 C/build intactos. Nenhum DFU ou pedido ao operador nessa etapa.

**M1 qualificada em0a315b9:**9/18 novos por plataforma Mac/Ubuntu ARM64,258 inputs íntegros, AST/lint fatal; sem typechecker Python. Shell/filesystem reais, kernel tools sintéticos.270 inputs host e69 C iguais permitem reutilizar110/196 e575/455 sem repetir; oito módulos byte/SHA revalidados. Receipt/parser preservam operação desconhecida sem inventar SSH exit. Nenhuma instalação, load físico, perfil/CLI, kernel ou DFU alterados. M2 ledger/hooks e coordenador/causalidade/seleção/firmware/energia permanecem pendentes.

**M2 qualificada em4d857bf:**12/16 novos e matriz afetada completa131/230 por plataforma Mac/Ubuntu ARM64,276 inputs íntegros, AST/lint fatal; sem typechecker Python. Journal/source/snapshot reais e dependências kernel/SSH sintéticas. Intenção/proof/completion duráveis, propriedade vazia/prefixo/reverse, publicação nativa intercalada e recuperação de load/unload WCC publicado comprovadas offline. Origem/órfão conservados; resultado observado não inventa SSH exit. Falhas de fixture/seletores da primeira rodada descartadas, somente AssertionError aceito na rodada final. Gates host afetados repetidos;69 C e oito módulos byte/SHA íntegros,575/455/build reutilizados. Nenhum efeito no iPhone, perfil/CLI ou instalação global. Coordenador/causalidade/seleção/firmware/energia e prova física ainda pendentes.

### B2b3a. Primeira causa no cleanup runtime — contrato fechado

**Contexto/fonte:** n71-pcie-brcmfmac-caller.h16–22/62–100 conserva a primeira causa da sessão antes/depois das actions; release pode terminar com retorno0 e causa anterior negativa. n71_resource_result.py108–161 e n71_iommu_result.py299–311 ainda calculam a causa apenas de assignment/provider. Não equiparar cleanup0 a operação runtime bem-sucedida.

**Arquivos executáveis (cinco):** scripts/host/n71_driver_runtime_result.py (helper passivo), scripts/host/n71_resource_result.py (implementação compartilhada de cleanup), scripts/host/n71_resource_stage.py (dispatch localizado), scripts/host/n71_iommu_result.py (precedência do ciclo provider) e novo tests/test_n71_driver_runtime_cleanup.py. Plano/D22 em fase separada antes do código. Não mudar kernel/build/perfil/CLI ou acionar hardware.

**Resultado:** obter a causa runtime somente em seleção explícita com ledger revalidado, última release nativa bem-sucedida e completa, owners/pending vazios, boot/histórico/resultado nativo correspondentes e getter final coerente. Intent pendente ou release recusada não autoriza cleanup dos providers. Erro já latcheado na release precisa sobreviver ao host removido; erro provider posterior com release sem causa continua no caminho provider. Causa efetiva: assignment anterior, depois a causa comprovada na release, depois provider posterior. Preservar assignment_error e provider_operation_error; registrar driver_primary_error separadamente quando presente. Nenhuma mudança nos defaults, assinatura legacy ou recusas de cleanup sem prova runtime.

**Verificação:** parsers e dispatch resource/IOMMU reais com fixtures de release/cleanup completo, sucesso, causa negativa prévia, erro provider posterior e precedência. Rejeitar boot diferente, causa apagada/alterada, owners vivos, completion/resultado/histórico ausentes e release malsucedida. Mutations executadas com baseline verde, somente AssertionError; AST/lint Mac/ARM64 e gates host afetados. Reutilizar gates/build C69 intactos. Coordenador/histórico/source depois; seleção C e firmware/energia ainda fechados, sem DFU nem pergunta ao operador.

- [x] Implementar o helper e os três consumidores sem relaxar o caminho legacy.
- [x] Qualificar causa, precedência e recusas nas duas plataformas; documentar reprodução e limites.
- [ ] Seguir para start/observe/stop, histórico e source antes da seleção física.

**B2b3a qualificada em b8fdd56:**6/11 novos e matriz afetada147/273 por plataforma Mac/Ubuntu ARM64,278 inputs íntegros, AST/lint fatal; sem typechecker Python. API legacy e precedência conservadas. Caso booleano False e âncoras antigas corrigidos, sem retirar cobertura; somente rodada final completa aceita.69 C/build575/455 reutilizados, sem efeito no telefone. Captura held com boot/log integral, continuidade/histórico/source e coordenador ainda pendentes antes de C/firmware/energia. CI d4cd8c6 teve timeouts oficiais15m em Ubuntu PR e Mac push; #41 reaberta sem alterar prazo ou repetir runs.

### B2b3b. Continuidade de lifetime e histórico — contrato fechado

**Arquivos executáveis (cinco):** novo scripts/host/n71_driver_runtime_lifetime.py, novo tests/test_n71_driver_runtime_lifetime.py, scripts/host/n71_driver_module_stage.py (ponte de release), scripts/host/n71_driver_runtime_recovery.py (histórico runtime validado) e scripts/host/n71_resource_stage.py (entrada opcional de retained runtime). Não alterar o caminho legacy ou acionar o telefone.

**Resultado:** continuidade passiva exige boot/manifest, prefixos de proofs e ações nativas completas, recursos/REG_ON/providers retidos e nenhuma lease MSI manual. Comparar o caller mantendo flags/owners e permitindo somente a primeira causa runtime coerente; resource assigned pode cair quando a causa for latcheada, conservando pending/claimed. Getters não autorizam efeitos. Histórico novo admite REG_ON_READ correto e, somente na publicação comprovada com lifetime/stack próprios, refusals ECAM canônicos vinculados à causa negativa do driver; nenhuma action extra, cleanup ou mudança de provider sem intenção/prova. A fonte C emite N71_PCIE_SCAN_WRITE_REFUSED também no caminho runtime; tratar esse caso sem aceitar qualquer linha N71.

**Release e origem:** bridge do ledger de módulos exige release nativa comprovada depois de unload completo. Não exigir owners runtime antigos após uma release legítima nem dispensar a prova. Host removido só é aceito com módulos vazios e proofs de cleanup/unload validados, sem inventar getter ausente. Recuperação continua read-only, fonte/órfão intactos; preservar as janelas pendentes e negar novo efeito sem completion. A CLI/perfil permanece fechado.

**Verificação:** parsers/filesystem/source reais; publicação e release intercaladas, owners/cause/refusal/prefix/boot coerentes e drift recusado; módulos vazios após cleanup e caminho legacy inalterado. Mutations executadas, baseline verde, AssertionError; AST/lint Mac/ARM64 e gates afetados, reuso C69 intacto. Depois fechar a fatia do coordenador (helper/teste/held), incluindo boot/log integral no cleanup e start/observe/stop explícitos, antes de seleção C e candidata física.

**Interfaces fechadas:** helper passivo `verify_history(session, text, context)`, `retained(session, text, context)` e `removed(session, text, context)`. Contexto único com `baseline`, `checkpoint` (texto ou null) e `proofs` (textos cujo registro/hash já foi validado pelo loader/journal). O helper também rederiva completions e sua relação ao histórico; nenhuma chamada SSH/setter. `retained_runtime(session, text, context)` será uma entrada nova e explícita no resource-stage; o retained antigo não terá dispatch automático nem receberá texto transformado. A ponte de `module_stage.resume` recebe contexto opcional, obrigatório para release/host removido. O recovery fornece seu contexto já validado ao helper e não promove arquivos órfãos.

**Limites da entrada:** retained runtime exige assignment completo com proof e providers/REG_ON vivos. A aquisição inicial e uma falha antes desse ponto usam os contratos existentes até o coordenador seguinte. Host removido exige getter fresco de todos os módulos vazio, proof de cleanup e unload quando o diagnóstico já estiver ausente. A coleta M1 fora do bloco PCIe e boot/log integral do cleanup serão ligadas no held na fatia seguinte, antes de C; ausência atual desses campos continua recusada, sem fabricar getter/prova.

**B2b3b qualificada em 18568c5:**13/21 novos e matriz afetada160/294 por plataforma Mac/Ubuntu ARM64,281 inputs íntegros, AST/lint fatal; sem typechecker Python. Source/journal/parsers reais e kernel/SSH sintéticos. Guarda de marker duplo revalidada nos três gates runtime afetados, preservando11 gates inalterados; timeout held10s descartado e só esse gate repetido.69 C/oito módulos preservados, sem rebuild/ação no telefone. Captura/loader integrais do host removido, coordenador e seleção física ainda pendentes.

### B2b3c. Captura integral e origem com host removido — contrato fechado

**Arquivos executáveis (dois):** scripts/host/n71_held_session.py e novo tests/test_n71_runtime_held_capture.py. Plano/D24 antes do código. Coordenador será B2b3d; seleção C, firmware/kernel e hardware permanecem fechados. Conferir imports/helpers mortos antes de alterar held e remover somente se houver evidência de uso ausente.

**Interfaces/resultados:** mover o getter M1 existente para depois do bloco condicional PCIe; parameters/providers continuam dentro dele. Com manifest explícito, observar os oito módulos/boot/hashes/state/refcnt/holders/registro mesmo depois do unload do diagnóstico; não fabricar getter ausente. Novo helper interno `proof_output(session, stage, process)` devolve log privado integral e exige boot único esperado somente no runtime/WCC explícito; legacy conserva process.stdout. Getters não autorizam efeitos adicionais.

**Efeitos:** cleanup, unload PCIe, restore e unload REG_ON explícitos imprimem/verificam boot antes do efeito. Returncode e log integral salvo pelo capture, incluindo stderr, são validados antes do próximo efeito e do registro do proof. Parser/journal recebem histórico completo/causa. Legacy conserva comandos/API/proofs. Falha/pending conserva owners; nenhum force/unbind/reboot automático.

**Origem:** manter assignment delta e proofs legacy. Para os quatro stages held com seleção runtime/WCC, exigir histórico completo como prefixo do checkpoint, hash/boot/protocolo/causa validados e resumo IOMMU igual à prova. Host removido usa lifetime.removed com baseline/checkpoint/proofs registrados e getter M1 fresco vazio. Campos ausentes continuam recusados; origem/órfãos não são sobrescritos nem promovidos, recovery read-only.

**Aceite:** executar `python3 -B -m unittest discover -s tests -p test_n71_runtime_held_capture.py -v` com árvore POSIX temporária, dependências kernel sintéticas e source loader/recovery/filesystem reais. Provar M1 com diagnóstico ausente, stdout filtrado diferente do log integral, boot errado/duplicado, proof alterado, módulo vivo/ledger não vazio, falta de cleanup/unload e origem imutável. Mutations com baseline verde e AssertionError, sem erro de harness/timeout; gates afetados, AST/lint Mac/ARM64,69 C/módulos/builds preservados. Discovery CI inclui o novo teste. Nenhuma CLI/DFU nesta fase.

- [x] Integrar captura/loader de origem removida, conservando legacy.
- [x] Qualificar shell/source/recovery e registrar reprodução/limites.
- [ ] Fechar start/observe/stop em B2b3d antes da candidata física.

**B2b3c qualificada em 78071d1:**11/19 novos e nove gates123/197 por plataforma Mac/Ubuntu ARM64,283 inputs íntegros, AST/lint fatal, sem typechecker Python. Loader/recovery/shell/proofs integrais reais, kernel/SSH sintéticos. Seis gates48/116 inalterados e C69/575/455 preservados; oito módulos iguais. Baselines/âncoras iniciais falhos descartados. Nenhuma ação física, pacote/configuração global ou CLI nova. B2b3d segue para o coordenador, incluindo stop antes de prepare: removed hoje exige names não vazio, lacuna que deve ser resolvida explicitamente antes da seleção C.

### B2b3d1. Encerrar antes de prepare — contrato fechado

**Arquivos executáveis (dois):** scripts/host/n71_driver_runtime_lifetime.py e novo tests/test_n71_runtime_unprepared_stop.py. Plano/decisão antes do código; depois B2b3d2 coordenador. Não alterar CLI, kernel, imagem, módulos ou firmware, nem pedir ação física.

**Resultado:** a entrada removed existente aceita também a sessão explicitamente selecionada que nunca iniciou efeitos nativos/WCC. Exigir ambos os ledgers vazios, getter fresco completo com todos os módulos ausentes, proof de assignment completo e rederivado igual ao resumo salvo, mesmo boot/prefixos, cleanup completo dos providers e unload quando o diagnóstico já estiver ausente. Assignment negativo completo pode ser encerrado conservando sua causa; não transformar isso em sucesso de start.

**Histórico:** sem lifetime registrado, nenhum resultado de action nativa pode aparecer no trecho novo de qualquer proof registrado ou no snapshot. Comparar depois do baseline quando a prova traz prefixo completo, e todo o delta quando ela é anterior no formato assignment. O getter nativo do cleanup deve continuar canônico e sem propriedade/publicação; os parsers resource/IOMMU continuam comprovando causa e liberação. O caminho com lifetime registrado mantém suas verificações atuais. Getters vazios sozinhos não autorizam cleanup/unload nem promoção de órfãos.

**Verificação:** novo gate `python3 -B -m unittest discover -s tests -p test_n71_runtime_unprepared_stop.py -v`, usando resource/IOMMU/lifetime/held loader reais, filesystem privado e kernel/SSH sintéticos. Provar cleanup anterior a prepare, assignment com causa negativa, diagnóstico removido, source loader/recovery sem efeitos e origem intacta. Recusar ledger/proof/boot/stack/prefixo/causa divergentes e resultado nativo não registrado. Mutation baseline verde e kills por AssertionError, AST/lint Mac/ARM64, gates afetados; preservar69 C/módulos/builds e entradas legacy.

- [x] Integrar e qualificar encerramento sem lifetime nativo.
- [x] Fechar o contrato B2b3d2 e implementar start/observe/stop no mesmo boot.

**B2b3d1 qualificada em a5c38c2:**5/4 novos,53/70 nos cinco gates afetados por plataforma Mac/Ubuntu ARM64,285 inputs íntegros, AST/lint fatal. Loader/recovery/parsers reais, kernel/SSH sintéticos; rodadas falhas descartadas. Nenhum acesso ao telefone ou alteração de kernel/build/configuração global.

### B2b3d2. Coordenador no mesmo boot — contrato fechado

**Contexto:** ligar as APIs já qualificadas de native.act, module.act, lifetime e held release. A entrada held.run legacy executa cleanup no resume; não serve para manter o driver vivo entre desenvolvimentos. Não alterar esse caminho.

**Arquivos executáveis (dois):** novo `scripts/host/n71_driver_runtime_session.py` e novo `tests/test_n71_driver_runtime_session.py`. Nenhuma CLI/perfil, kernel, firmware, instalação global ou ação física nesta fatia.

**Interface:** `run(session, request)` com exatamente action (`start`, `observe`, `stop`), root (Path raiz), source (diretório privado runtime) e identity. Exigir seleção explícita runtime/WCC/resource/IOMMU. Carregar/reconciliar a origem pelas APIs existentes e observar o boot corrente; uma origem válida é necessária, sem aquisição inicial implícita. Fonte, órfãos e receipts nunca são sobrescritos. Saída é resumo `{action, phase, primary_error, successful}` e fica no result/journal privado. Isso não prova IRQ/DMA, Wi-Fi ou energia.

**Fonte e journal:** root/output/source protegidos, distintos, dentro do runtime; saída nova/exclusiva. Copiar só proofs registrados e checkpoint, preservando bytes completos e SHA. Quando recovery cria fork comprovado, copiar desse fork e conservar a origem inicial. Hash/boot/history/owners divergentes recusam efeitos. Observação atual valida módulo diagnóstico/REG_ON conforme attempts/proofs, stack, prefixos e resources/providers. Estado removido exige lifetime.removed; estado retido saudável exige lifetime.retained. Assignment negativo anterior a qualquer efeito nativo usa os validadores passivos resource/IOMMU/history e stack vazio, sem autorizar start.

**Start:** assignment saudável e prefixo próprio. Fazer prepare se ainda não houve ação nativa; carregar os cinco módulos em ordem somente onde falta um owner comprovado; publicar após WCC completo. Repetir start em uma publicação já comprovada só observa, sem load/setter. Retomar prefixo de loads completos é permitido pelas preconditions existentes; native prepare/publicação negativa ou release anterior não autoriza novo start. Falha conserva owners/intent e causa; nada de cleanup/reboot automático.

**Observe:** apenas snapshots e validação; salvar checkpoint/journal próprios. Nenhum insmod/rmmod/setter, mesmo no estado removido. Pending só avança pela recuperação qualificada, nunca por replay.

**Stop:** unload normal na ordem inversa somente dos módulos registrados como vivos. Busy/ref/holder ou completion negativa interrompe, conservando providers/REG_ON. Com stack vazio, release nativa se houve preparação e ainda não há release bem-sucedida; release negativa comprovada pode ser tentada novamente pelas APIs existentes. Depois held.release, snapshot final e lifetime.removed, exigindo ausência de diagnóstico/REG_ON/PCI. Stop removido só observa; stop pré-prepare usa B2b3d1. Causa negativa retorna successful=false mesmo com cleanup completo.

**Falhas:** após criar journal, registrar erro privado e tentar checkpoint read-only para preservar evidência. Não esconder a falha nem executar ação compensatória automática. Crash antes da completion continua pendente; próximo processo utiliza recovery. Nenhuma remoção forçada, unbind, replay de receipt ou reboot.

**Verificação:** fixture kernel/SSH sintética, parsers/lifetimes/act/journal/filesystem/loader/recovery reais. Provar start → observe → stop no mesmo boot, start já publicado e stop já removido sem novos efeitos, prefixo parcial retomado, busy/transport conservando owners, negativa pré-prepare, boot/hash/history recusados antes de efeito e origem/órfãos íntegros. Mutations reais após baseline verde, só AssertionError; AST/lint Mac/ARM64 e gates afetados, reuso C/artifacts intactos. C permanece fechada até esse aceite; seleção/composição, firmware/calibração/regdb/energia seguem depois.

- [x] Implementar e qualificar coordenador start/observe/stop.
- [ ] Ligar seleção/composição C após a qualificação, antes do teste físico agrupado.

**B2b3d2 qualificada em 80538d2:**9/11 no Mac e Ubuntu ARM64,288 inputs íntegros, AST/lint fatal.285 inputs anteriores iguais,53/70 e builds C reutilizados. Start/observe/stop e recuperação conservam origem/provas no mesmo boot simulado. CLI/perfil/seleção C, firmware/energia e prova física ainda pendentes; nenhuma intervenção do operador necessária nesta fatia.

### C1. Seleção do caller e WCC com a mesma base — contrato fechado

**Contexto:** o coordenador está qualificado. `n71_resource_build.py:81` ainda seleciona o módulo IOMMU de114.120 bytes; o caller runtime qualificado tem142.232 bytes/SHA b4888de1. Não substituir o diagnóstico implicitamente nem alterar os caminhos legacy. Kernel/Image/exports e políticas de assignment permanecem iguais; WCC foi compilado numa cópia com somente PCIe/MSGBUF habilitados.

**Arquivos executáveis (dois):** novo `scripts/host/n71_driver_runtime_build.py` e novo `tests/test_n71_driver_runtime_build.py`. CLI/perfis, Session, kernel, firmware, iPhone e pacotes globais não mudam nesta fatia. Depois C2 liga Session/staging/coordenador; composição/CLI em fatias seguintes.

**Interfaces:** `qualified(root, request)` e `select(root, request)`, com request exatamente `{release, pcie_sha256}`. O hash explícito deve corresponder ao caller qualificado, jamais fazer fallback para o antigo. qualified devolve `{diagnostic, drivers, kernel_outputs}`: diagnóstico com bytes/SHA/vermagic, manifest WCC de cinco módulos na ordem existente e outputs da Image já validada. select devolve `{diagnostics, drivers, kernel_outputs}`; diagnostics conserva os dois registros existentes e flags de assignment/IOMMU, mudando somente identidade do caller e acrescentando driver_runtime=true.

**Premissas:** usar as evidências públicas caller/WCC e os seletores existentes de IOMMU/kernel/resources. Exigir formato/tipos, qualificação Mac/ARM64, escopo opt-in, nenhuma preparação/carga automática, actions/getter/owners/primeira causa compatíveis com o protocolo existente, módulo ELF/AArch64/ABI/bytes/SHA e origem do build preservada. Revalidar os69 inputs públicos do caller com paths canônicos permitidos sob phone/kernel ou tests, arquivo regular sem link, bytes/SHA e orçamento. Nunca resolver traversal nem ler arquivo fora desse escopo. Não remover recusas de políticas/kernel anteriores.

**Base:** caller source/patch/config/Image/exports devem coincidir com a base IOMMU qualificada e com a Image vinculada. WCC source/patch/config/Image/exports e gzip também devem coincidir, além da configuração variante exatamente PCIe/MSGBUF já validada por driver_modules. WCC não contém rfkill-gpio/BCA/CYW na seleção. Não elevar evidência offline a IRQ/DMA, associação ou carga.

**Verificação:** roots temporárias com cópias das evidências/69 inputs e seletores reais, sem mock das funções sob teste. Provar composição caller+REG_ON+WCC ordenado, flags antigas preservadas, origem imutável, hash explícito/ABI/Base incompatíveis recusados, escopo e causa/defaults divergem recusados, input alterado/omitido/link/traversal/budget inválidos recusados. Executar mutações reais após baseline verde e aceitar somente AssertionError; AST/lint Mac/ARM64, novo gate e reuso dos anteriores com inputs relevantes iguais. Conferir privadamente bytes/SHA dos artefatos aceitos, sem rebuild, SSH, load, perfil ou DFU.

- [x] Implementar e qualificar a seleção explícita do caller/WCC.
- [ ] Integrar Session/staging e depois composição/CLI, mantendo o teste físico agrupado.

**C1 qualificada em 317c89c:**9/14 Mac/ARM64,360 inputs íntegros, AST/lint fatal; sete artefatos/1.371.040 bytes revalidados por SHA/ELF/ABI.288 inputs host e69 C iguais permitem reuso. Nenhuma alteração de Session/CLI/perfis ou ação no iPhone. Próxima fatia deve fechar staging e a sequência de aquisição/assignment antes de integrar o coordenador, incluindo saída pré-assignment sem inventar proof.

### C2. Session e staging explícitos — contrato fechado

**Contexto:** C1 qualifica os registros, mas Session ainda chama o seletor IOMMU antigo e só transfere os dois diagnósticos. Ligar a seleção à instância e transferir WCC antes do getter; a CLI continua fechada nesta fatia. A sequência de aquisição/assignment e sua saída pré-assignment será resolvida antes de expor o fluxo na fatia seguinte.

**Arquivos executáveis (quatro):** novo `scripts/host/n71_driver_runtime_profile.py`, novo `tests/test_n71_driver_runtime_profile.py`, alterações localizadas em `scripts/host/n71-link-session.py` (constructor/preflight/parameters) e `scripts/host/n71_iommu_result.py` (selected). Nenhum outro arquivo executável, kernel/build, CLI/proveniência/firmware ou ação no iPhone.

**Interface:** Session recebe keyword `runtime=None` ou uma lista de cinco pares `(registro WCC, bytes)`. Com None, comportamento/seleção/comandos legacy permanecem. Helper `configure(session, request)` recebe root e modules; `selected(session, root)` valida; `staged(session)` devolve os cinco pares próprios somente no runtime explícito. Driver_runtime/manifest/ledgers são registrados separadamente dos dois diagnósticos. Exigir held/resource/IOMMU power2 e registros exatamente iguais à seleção C1; bytes devem ser imutáveis e coincidir com tamanho/SHA. Não aceitar vendor estrangeiro, manifest incompleto ou mistura de diagnósticos.

**Dispatch:** IOMMU.selected mantém o caminho antigo quando runtime não está selecionado; no explícito usa a validação do helper/C1. O constructor configura os campos antes dessa validação. Preflight revalida os dados runtime antes do primeiro SSH e verifica por leitura que os oito módulos observados e o registro brcmfmac estão ausentes. Transferir e verificar SHA dos dois diagnósticos e cinco WCC no diretório exclusivo, antes de qualquer insmod de diagnóstico/REG_ON e antes do primeiro getter WCC. WCC nunca é carregado por preflight/probe. Probe acrescenta apenas driver_runtime=1 na seleção explícita; prepare/publicação continuam exclusivamente no coordenador.

**Verificação:** constructor/Session/preflight/experiment/selected reais, dados/SSH/kernel sintéticos onde necessário; filesystem e bytes/SHA reais. Provar default inalterado, diagnóstico/manifest/ABI/flags recusados antes de efeito, transferência dos sete arquivos sem WCC insmod, erro de hash sem REG_ON/PCI insmod, getter somente depois dos arquivos e parâmetro runtime somente no opt-in. Mutações reais com baseline verde e AssertionError; AST/lint Mac/ARM64, gates afetados e reuso C/builds inalterados. Não declarar associação/carga/IRQ/DMA a partir desse aceite.

- [x] Implementar e qualificar Session/staging runtime sem alterar a CLI.
- [ ] Fechar aquisição/assignment/saída e composição/CLI antes da candidata física.

**C2 qualificada em 3a6afb8:** 9/16 novos e 135/149 nos dez gates afetados por plataforma Mac/Ubuntu ARM64, 372 inputs íntegros, AST/lint fatal. Construtor real com sete binários/1.371.040 bytes passou sem execução/SSH; 358 dos 360 inputs anteriores e 69 C iguais, builds preservados. Saída pré-assignment/composição/CLI e firmware/energia permanecem pendentes, sem ação no telefone.

### C3. Observe/stop antes de assignment — contrato fechado

**Contexto:** aquisição held e assignment são etapas distintas. O coordenador exige assignment para toda origem retida, e lifetime.removed exige sua prova mesmo quando a etapa nunca foi tentada. Não fabricar assignment para encerrar um host adquirido. Conservar as recusas quando a intenção existe ou a prova está ausente.

**Arquivos executáveis (três):** `scripts/host/n71_driver_runtime_lifetime.py`, `scripts/host/n71_driver_runtime_session.py` e novo `tests/test_n71_runtime_unassigned_stop.py`. Nenhuma CLI/composição, kernel, firmware ou hardware nesta fatia. Retained/start com assignment saudável conservam o contrato anterior.

**Resultado:** reconhecer a origem explicitamente runtime/WCC com resource_attempted=false, assignment=None e nenhuma prova resource-assignment, ambos os ledgers vazios, mesmo boot e stack fresco totalmente ausente. Observe não faz efeitos. Start continua recusado antes de assignment. Stop permite somente o cleanup held já existente e prova seus providers/REG_ON/unloads; o resultado removido exige cleanup rederivado sem evento/causa de assignment, prefixes/checkpoints e nenhum efeito nativo não registrado. Resource intent/prova/summary divergentes, stack vivo, boot/history drift, native owners/MSI manual e falta de cleanup/unload permanecem recusados antes do próximo efeito.

**Histórico:** antes de assignment, usar o checkpoint adquirido validado como âncora do histórico; admitir somente os REG_ON_READ canônicos posteriores e exigir ausência de actions nativas após o baseline. Não tratar a ausência de assignment como autorização de prepare/publish ou remover providers quando existe intento pendente. Origem continua imutável; cópias e recuperação usam os contratos existentes.

**Verificação:** journal/source/coordenador/lifetime/held/resource/IOMMU reais com dependências kernel/SSH sintéticas. Ciclo observe→stop no mesmo boot sem assign/prepare/WCC load; stop removido idempotente, start recusado, origem intacta e source loader aceita cleanup genuíno. Negativas de intenção/prova/resumo, boot/prefixos, native/module owners, MSI, cleanup e unload; mutações reais após baseline verde, somente AssertionError. AST/lint Mac/ARM64, gates diretamente afetados; preservar C/builds e não pedir ação ao operador.

- [x] Implementar e qualificar observe/stop pré-assignment.
- [ ] Integrar composição/CLI e a sequência inicial após esse aceite, antes da candidata física.

**C3 qualificada em a21afce:** 6/9 novos e 33/45 nos quatro gates afetados por plataforma Mac/Ubuntu ARM64, 374 inputs íntegros, AST/lint fatal. Observe→stop→stop pré-assignment preserva origem e boot, start é recusado; coleta herdada inicial corrigida antes do aceite. 370 dos 372 inputs anteriores e 69 C iguais; kernel/builds/binários preservados. Composição/CLI, firmware/energia e prova física seguem pendentes; nenhuma ação no aparelho.

### C4. Composição privada dos sete módulos — contrato fechado

**Contexto:** C1 seleciona os registros, C2 liga Session/staging e C3 fecha a saída sem assignment. `compose-n71-diagnostic.py:108–125` ainda aceita somente os diagnósticos antigos; o perfil precisa conter os sete arquivos sem autoload. Manter kernel/Image, initramfs, SSH e payload/DTB/ASPM qualificados.

**Arquivos executáveis (três):** novo `scripts/host/n71_driver_runtime_compose.py`, novo `tests/test_n71_driver_runtime_compose.py` e hooks localizados em `scripts/build/compose-n71-diagnostic.py`. CLI de sessão/coordenador, kernel, firmware e iPhone ficam para depois. Conferir imports/helpers mortos antes de modificar o compositor.

**Interface:** helper `select(root, request)` com request exatamente release, pcie_sha256 e directory (Path privada contendo os cinco WCC em nomes planos). Retorna diagnostics (dois registros C1) e drivers (cinco pares próprios de registro/bytes). Seletores C1 reais; ler apenas os cinco arquivos selecionados, exigindo proteção privada, arquivo regular sem link, bytes/SHA e ELF64/AArch64/vermagic exatos. Não copiar rfkill-gpio/BCA/CYW ou outros arquivos.

**Compositor:** adicionar `--pcie-driver-runtime` e `--wcc-dir`. O runtime exige explicitamente ASPM off, held, resource-capable, iommu-parent, power2 e REG_ON; diretório WCC sem runtime é recusado. Validar flags antes de ler identidades. Somente no modo explícito, `held_reg_module` usa os diagnostics C1 e main obtém os cinco pares do helper antes de criar output. Copiar os cinco `.ko` com private_write junto aos dois diagnósticos. Provenance explícita inclui pcie_driver_runtime=true e driver_modules com os cinco registros; defaults conservam os campos/arquivos antigos. Nenhum módulo ou firmware é carregado, initramfs/payload não ganha autoload e o perfil ativo não muda.

**Verificação:** seletores/evidência/filesystem reais com ELF sintéticos na fixture, testes do helper e despacho real do compositor; recusar arquivos ausentes, hash/ABI/tipos, link/permissão, base misturada e flags sem escopo antes de output/identidades. Preservar as provas dos perfis anteriores; mutações reais com baseline verde e AssertionError, AST/lint Mac/ARM64. Compor uma candidata privada com artefatos reais no Mac e verificar sete arquivos/provenance/kernel/payload/identidades preservados, sem boot, SSH ou mudança do perfil ativo. A prova física e a CLI de execução seguem depois.

- [x] Integrar e qualificar a composição privada runtime/WCC.
- [ ] Fechar a CLI de sessão, depois firmware/calibração/regdb e energia antes da candidata física.

**C4 qualificada em c5de5df/64f49ad:** 7/15 novos e 30/39 nos seis gates afetados por plataforma Mac/Ubuntu ARM64, 377 inputs íntegros, AST/lint fatal. Composição real no Mac com 13 arquivos/sete módulos/1.371.040 bytes, payload anterior idêntico e initramfs/SSH/inputs preservados. Ajustes de fixture/harness descartados; somente o gate novo/lint foi retomado após o diagnóstico seguro de ambiente. 373 dos 374 inputs anteriores e 69 C iguais; nenhum kernel/firmware/telefone/configuração global alterado.

### C5. CLI explícita de sessão runtime — contrato fechado

**Contexto:** perfil C4 está completo e os handlers C2/C3/coordenador estão qualificados. A CLI legacy seleciona o caller antigo; não ampliar seu modo implicitamente nem encaminhar um start/observe/stop para o resume legacy que libera providers.

**Arquivos executáveis (três):** novo `scripts/host/n71-runtime-session.py`, novo `scripts/host/n71_driver_runtime_cli.py` e novo `tests/test_n71_driver_runtime_cli.py`. Nenhum kernel/firmware/hardware ou mudança na CLI legacy nesta fatia.

**Interface:** entrypoint requer `--profile` e `--action` em acquire/assign/start/observe/stop, admite `--source`, `--output-dir` e `--check`. Helper `run(root, request)` recebe exatamente action, profile (Path), source (Path/None), output (Path/None) e check (bool exato). Root é Path absoluta. Profile é deployment.json de uma pasta privada diretamente sob runtime. Acquire não admite source; demais ações exigem uma origem privada diretamente sob runtime. Efeitos exigem output novo/distinto diretamente sob runtime; --check não cria output nem executa SSH/USB/recovery/setter.

**Gate local:** ler provenance protegida/bounded e exigir flags exatas runtime/held/resource/IOMMU/target/PME/ASPM/power2, opt-in e ausência de autoload antes de acessar identidades. Usar C1/C4 para selecionar/verificar os sete arquivos e manifest correspondente na provenance. Com identidade validada, aplicar selected_release/aspm_payload/payload_image reais e verificar hashes de caller/REG_ON. Criar uma instância própria do módulo link com ROOT da requisição; Session real recebe diagnostics e runtime/WCC separados. Identidade held usa a API existente; Journal continua registrando manifest/ledgers separados. Manter IPHONE_LINUX_PROFILE só durante a operação e restaurá-lo em finally, inclusive em falhas. Não imprimir chaves ou ambiente.

**Dispatch:** acquire usa held.run sem source; assign usa held.run com source e assign=True. Start/observe/stop usam somente runtime_session.run, preservando source/receipts/recovery no mesmo boot. Start requer assignment saudável; observe/stop pré-assignment conservam C3. Traduzir resultado/causa em exit0/1, sem cleanup/reboot compensatório além dos contratos dos handlers. --check valida origem via load_source somente de leitura; pode recusar pending que exija observação física, sem promover arquivo/fabricar completion. CLI sempre emite erro claro para scope/source/output inválidos e não altera perfil ativo ou rede global do Mac.

**Verificação:** testes de contrato CLI/arquivos/seleção e Session reais, dependências SSH/kernel/identidade sintéticas onde necessário e handlers qualificados reutilizados. Provar local check sem output/SSH/USB, recusas antes de identidade/efeito, manifest/ABI/flags/paths/hashes, origem distinta/protegida, dispatch e erro/causa/env restaurados. Mutations reais com baseline verde e AssertionError; AST/lint Mac/ARM64, gates diretamente afetados. Rodar --check real sobre a candidata C4 no Mac com todos os gates de kernel/identidade, sem boot. Firmware/calibração/regdb/energia e prova física seguem depois; nenhum pedido ao operador nesta fase.

- [x] Integrar e qualificar os comandos explícitos e --check real.
- [ ] Preparar firmware/calibração/regdb e energia antes da sessão física agrupada.

**C5 qualificada em 637ba88:** 7 testes/20 mutações AssertionError por plataforma Mac/Ubuntu ARM64,381 inputs íntegros, AST/lint fatal. CLI/seletores/Session/load_source reais; identidade/kernel e respostas dos handlers sintéticos nos contratos. --check real no perfil C4 passou sem output/SSH/USB.377 inputs anteriores e69 C preservados. Firmware/energia e prova física pendentes.

### C5a. Bundle isolado do CI — contrato fechado

**Contexto:** push38072762066 de a1c4e40 falhou por ModuleNotFoundError n71_driver_runtime_build na cópia isolada. PR38072766411 e jobs Mac/Ubuntu excederam15 minutos. Erro de import não conta como kill.

**Arquivo único:** tests/run_n71_diagnostic_payload_mutations.py. Acrescentar a DEPENDENCIES sete imports públicos transitivos existentes sob scripts/host: n71_driver_modules, n71_driver_runtime_build, n71_driver_runtime_compose, n71_driver_runtime_result, n71_driver_runtime_stage, n71_msi_allocation_result e n71_session_history. Preservar subject/mutações/timeouts/política AssertionError. Nenhum workflow, gate, runtime privado, firmware ou identidade muda.

**Verificação:** gate diagnóstico completo Mac/VM ARM64 sobre mesmos inputs públicos, baseline verde e kills AssertionError; AST/lint fatal. Reutilizar C5 e C/builds intactos. Publicar uma vez na branch; não reiniciar CI durante observação.

- [ ] Corrigir e qualificar bundle sem falha de import.

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

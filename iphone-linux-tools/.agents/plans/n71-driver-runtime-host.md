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

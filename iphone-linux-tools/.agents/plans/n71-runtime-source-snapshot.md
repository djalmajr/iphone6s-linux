# Snapshot de fonte qualificada do caller Wi-Fi — #43

## Contexto

Demanda Wi-Fi/energia aprovada, execução solo, mínimo de DFU. A qualificação Wi-Fi cobre69 inputs; somente n71-i2c-power-diagnostic.c difere no working tree atual. O arquivo no commitbe960f14268da56aa928873375200cb10a4e2e88 tem6.910bytes e SHA5dc4d053efd9df7e9a977712a48bc395e23e5e25782567f465b839b6afbfab4b, iguais ao registro histórico. Não editar aquele manifesto nem requalificar o binário antigo por declaração.

## Decisão

Preservar uma árvore Git explícita e privada, com o mesmo manifesto de qualificação; selecionar/preparar os artefatos reais a partir desse root. Não ampliar a API dos selectors nem criar fallback entre source atual e histórico. A fonte I2C nova e seu módulo HDQ mantêm reprodução separada.

## Arquivos e fases

1. Até três executáveis: novo scripts/host/n71-runtime-qualified-source.py, helper scripts/host/n71_runtime_source_snapshot.py e tests/test_n71_runtime_source_snapshot.py. O helper usa git archive local de commit completo explícito; não checkout/reset/fetch. Saída nova sob runtime, sem links/overwrite, dados limitados e modos privados. Validar manifesto histórico idêntico e os69 inputs com o selector de produção. A fase2 substitui a execução histórica inicial pela execução corrente sobre dados congelados. Referenciar todos os owners/arquivos, sem copiar runtime/keys/firmware do working tree.
2. Após os gates: integrar a referência explícita com cinco executáveis: novo scripts/host/n71_runtime_source_reference.py e tests/test_n71_runtime_source_reference.py; alterar n71_driver_runtime_build.py, n71_runtime_source_snapshot.py e test_n71_runtime_source_snapshot.py. Usar IPHONE_LINUX_RUNTIME_SOURCE_RECEIPT somente para resolver os69 inputs históricos; todos os selectors/handlers continuam executando do checkout atual. Recusar receipt fora de runtime, links, modo impróprio, prova diferente ou inputs alterados; sem fallback em erro. O gerador passa a executar selectors atuais com root dos dados históricos, nunca Python da árvore arquivada. Ausência da variável conserva a recusa corrente.
3. Conferir módulos WCC/diagnostics reais e executar o CLI --check com o receipt explícito e o perfil privado original. O CLI exige perfil diretamente sob seu próprio runtime; usar a referência dos inputs evita duplicar credenciais ou enfraquecer esse escopo. Provar recusa de input ausente/alterado em cópias descartáveis, sem editar o snapshot aceito. Nenhum SSH/USB/DFU ou initramfs ativo deve ser alterado.
4. Documentação/evidência sanitizada, issue e CI em fase separada; publicar somente os scripts e os fatos selecionados. Snapshot/payloads/binários/calibração/credenciais continuam privados.

## Detalhes

O commit é obrigatório,40hex e objeto commit local. A prova no snapshot deve ser byte-identical ao registro corrente de n71-brcmfmac-caller-qualified.json;69 entradas devem ter tamanho/SHA iguais. Usar o git root real e prefixo do projeto, validar todos os membros antes de extrair, recusar symlinks/hardlinks/traversal/arquivos fora do prefixo. Rejeitar output existente e parent links; não desfazer alterações do usuário em erro. Registrar o commit/archive SHA e a seleção dos artefatos no receipt privado depois de validação. Não tratar uma cópia sintética como fonte de produção.

## Tarefas

- [x] Confirmar o input histórico exato no Git.
- [x] Implementar e verificar criação privada/rejeições com Git local e selectors.
- [x] Integrar receipt explícito para os inputs, mantendo execução/identidades no checkout corrente.
- [x] Conferir os sete módulos e o perfil reais a partir da fonte aceita; nenhuma recomposição de credenciais necessária.
- [x] Documentar fatos sanitizados; publicar e concluir #43 após o commit da documentação, com aceite local provado.
- [ ] Retomar HDQ/UART5/gauge e preparar coleta física agrupada; o goal funcional continua aberto.

## Verificação

Teste de uso real do helper com repositório Git descartável e conteúdo de arquivo verificável. Guards de path/overwrite/link/commit e manifesto devem falhar antes de aceitar o snapshot; mutações de guard por AssertionError, nunca timeout/compile error como kill. Um único gate afetado Mac/ARM64; reusar gates I2C e runtime anteriores enquanto inalterados. AST/lint fatal e comandos reais de seleção/compostura local. Sem type checker Python configurado. Conferir working tree, source selecionado, artefatos e fonte/config/Image/exports preservados. Nenhuma confirmação de rotina ao operador.

## Resultado da implementação

Helper em7ba3ddf e integração em2406e1f. A matriz afetada de dez módulos passou66testes e70mutações únicas por AssertionError em cada plataforma:291,258s no Mac e269,870s no ARM64. AST e lint fatal passaram; não há typechecker Python. Um snapshot real novo criado pelo gerador corrente verificou69inputs do commitbe960f14268da56aa928873375200cb10a4e2e88. O CLI real --check aceitou perfil/calibração/sete módulos/firmware; cópias descartáveis com input alterado ou ausente foram recusadas com exit1. Os14arquivos do perfil original permaneceram idênticos. Sem SSH/USB/DFU ou execução do Python arquivado. CI do head anteriora080ee0 passou nos três jobs; o novo head terá sua própria execução. Prova física de Wi-Fi/energia continua pendente.

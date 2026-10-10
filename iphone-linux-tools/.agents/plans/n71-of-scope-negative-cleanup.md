# Identidade OF e cleanup de falha antes do scan — #40

## Evidência e escopo

O boot2026-10-09 inicializou Apple DART, mas `n71_dart_host_prepare` retornou ENODEV antes de mudar status/map ou publicar PCI. O helper compara `of_node_full_name` com caminhos absolutos; a fonte kernel fixada usa esse campo como nome do nó. Conferir a fonte `drivers/of/fdt.c`/`include/linux/of.h` e usar igualdade de identidade com lookup pelo caminho absoluto, mantendo todos os guards de provider/parent/driver/data/refs. Os fixtures devem representar nomes de nós reais e recusar um nó de mesmo nome fora do caminho esperado.

O collector negou cleanup apesar de scan/caller-19, owners0, restore TTBR16/reset/power e barramento vazio. Corrigir somente a sequência negativa completa antes de publicação: estado ready0 exige erro coincidente de scan/caller; DART prepare negativo/available0/mapped0 justifica config restaurada antes do cleanup da lease. Nunca aceitar falta de proof, erro divergente, owners ativos ou ordem inválida. Manter os contratos positivos/retidos anteriores.

## Decisão e execução

Manter o iPhone no iOS para recarga durante as correções. Separar fases de no máximo cinco arquivos públicos. Nenhuma nova sequência DFU somente para verificar a fonte ou os parsers.

- [x] Registrar prova física sanitizada e recuperação no mesmo boot.
- [x] Conferir fonte fixada e reproduzir a rejeição de nomes reais no fixture.
- [x] Corrigir lookup OF/fixtures/mutações, verificar Mac e Ubuntu ARM64.
- [x] Corrigir parser negativo com casos de prova incompleta, erro e ordem divergentes; verificar journal e modos anteriores.
- [x] Compilar módulo separado na VM power2, conferir exports/vermagic e preservar fonte/config/Image/artefatos anteriores.
- [x] Registrar evidência sanitizada, atualizar issues e publicar somente a branch autorizada.
- [x] Preparar próxima candidata agrupada, sem boot nesta etapa offline.

## Gates e limites

Somente asserções de programas compilados ou testes que reproduzam o contrato contam como proof; falha de compilação/import/timeout não é kill. Reutilizar gates independentes com inputs intactos. AST/lint fatal, diff/JSON/public tree antes de commit. Guardar logs e módulos privados em runtime; não publicar chaves, firmware, payload/DTB, snapshot IDs ou identificadores do aparelho. Código/build/CI não comprovam Wi-Fi, IRQ entregue, tradução DMA ou carga Linux. A próxima prova física deverá reunir associação, atribuição, cleanup, serviços, snapshot e retorno sem reinícios intermediários.

## Resultado offline — 2026-10-09

OF51 cenários/40 mutações compiladas por SIGABRT/asserção, parser/journal19 testes/45 mutações por AssertionError, por plataforma Mac/Ubuntu ARM64. Build PCIe114.120 bytes/SHA48df330a, ELF64/AArch64/vermagic power2,123 imports conferidos e baseline preservada. Log físico original revalidado sem alterações; módulo novo não selecionado no perfil nem carregado. [Evidência](../../docs/evidence/n71-of-scope-negative-cleanup.json), [procedimento/limites](../../docs/N71_IRQ_IOMMU.md#correções-offline-após-a-coleta--identidade-of-e-cleanup-negativo). AST/lint fatal passaram. Correções não instalaram pacotes ou alteraram configuração global do Mac e não exigiram outro DFU.

### Seleção e candidata seguinte

O registro qualificado foi atualizado para SHA48df330a, mantendo o build anterior e seu histórico. Somente o header OF diverge dos84 inputs anteriores; os gates PCI independentes são reutilizados, e o helper mudou com seu gate específico51/40. Os50 inputs copiados na VM foram conferidos byte a byte por SHA; imports group get/put/id presentes e helpers de alias não exportados ausentes.

Seleção/Image8 testes/24 mutações e perfil/composer8/21 passaram no Mac e Ubuntu ARM64. Composer real e collector `--check` passaram: oito arquivos700/600; payload/DTB/kernel/loader/bootargs/deployment, initramfs/chaves/identidades e REG_ON são idênticos ao D20 anterior. Somente módulo PCIe e seu SHA na provenance mudaram. Defaults e candidata anterior preservados, sem boot. A tentativa agrupada privada está preparada com o último snapshot manual validado; não repetirá o gate GPIO já aprovado. [Prova da candidata](../../docs/evidence/n71-of-scope-profile-qualified.json). CI nova e teste físico seguem pendentes.

Publicado somente em feat/display-console, sem merge/tag/release. Evidências e pendências atualizadas nas issues2/9/38/40. A conferência USB atual voltou vazia por ioreg e idevice_id depois do fallback ao iOS; reconexão somente da ponta Lightning solicitada, sem PIN/botões. Essa observação encerrava a preparação; a candidata corrigida foi posteriormente iniciada em uma coleta agrupada, registrada no plano seguinte. As execuções CI6ad8d7f foram substituídas pelo novo push; conclusão cancelled não conta como aprovação. A decisão local de aguardar CI antes da coleta foi revista com gates relevantes intactos e CI ativa; ver [registro do teste agrupado e erro preservado](n71-dart-cleanup-operation-error.md#decisão-sobre-ci-e-teste-físico). A coleta seguinte foi executada, sem declarar a CI completa verde.

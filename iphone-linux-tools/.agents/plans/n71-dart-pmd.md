# PMD do DART S5L — issue #46

## Contexto

O boot agrupado de 15/10 confirmou execução do firmware, mas o primeiro comando expirou e o DART relatou NO PMD. A janela DMA alternativa não corrigiu o erro. O endereço registrado inclui o OR com dma_min; não prova os bits brutos emitidos pelo dispositivo. A referência Apple preservada (SHA256 0a9b98d58c5c606030c394bee37b6ddd58e0d82468203f7de9ab3fe6c63a8b9a) escreve no PMD o endereço físico mascarado em 35:12 com flags 3, em 0xfffffff006060520..52c. O Linux fixado usa flags 1. Largura de 64 bits, índices de 9 bits e codificação TTBR concordam.

## Decisão D1 — candidata limitada ao S5L

- **Decisão:** testar bit 1 em entradas intermediárias somente quando o driver seleciona explicitamente a quirk S5L e o formato é APPLE_DART. Criar bundle e versão distintos; preservar os bundles e artefatos anteriores.
- **Por quê:** reproduz uma diferença observável da referência do mesmo aparelho, sem mudar as tabelas dos DART modernos. A causalidade do fault ainda depende do aparelho.
- **Alternativas:** repetir a janela já falha não oferece diagnóstico novo; alterar todos os DART amplia o escopo; usar o mesmo nome de kernel dificulta distinguir candidatas. Tracing dinâmico não está compilado no kernel atual.
- **Reverter:** baixo, selecionar o perfil/kernel anterior; nenhum flash ou armazenamento interno modificado.
- **Status:** em curso.

## Fase A — fonte e seleção, até cinco executáveis

1. phone/kernel/patches/0009-s5l8960x-dart-pmd.patch: quirk BIT(10) em include/linux/io-pgtable.h; seleção apenas DART_S5L8960X em drivers/iommu/apple-dart.c; bit 1 apenas APPLE_DART com a quirk em drivers/iommu/io-pgtable-dart.c. Preservar PA, barreira, CAS, folhas, TCR, TTBR e janela.
2. scripts/build/kernel_bundle.py: bundle n71-dart-serdev-pmd-v1, versão -iphone6s-dart-serdev-pmd1, patches e blobs completos fixados; perfis anteriores imutáveis.
3. tests/test_kernel_pmd_bundle.py: Git real, seleção, recusas e preservação, aplicação idempotente e mutações com AssertionError.
4. tests/n71_dart_pmd.c e tests/test_n71_dart_pmd.py: compilar os trechos efetivos do patch, exercer publicação PMD, PA, escopo, CAS concorrente e ordenação; mutações precisam falhar por assert, não por compilação.

## Fase B — build isolado e integração

Aplicar somente em worktree novo na VM dedicada, com inputs selados. Manter source/build power2 intactos. Qualificar os trechos contra a fonte completa real e compilar os objetos reais com Werror. Preparar build completo com configuração herdada alterando somente LOCALVERSION; verificar Image, DTB, configuração embutida, exports, serdev e modpost. Não instalar. As permissões de seleção de kernel/módulos/perfil só serão ampliadas por uma fase separada, depois de um registro de build real; nenhum bypass das provas existentes.

### D2 — reconstrução dos diagnósticos para a ABI PMD

- **Decisão:** preparar scripts/build/build-n71-pmd-diagnostics.py e docs/evidence/n71-pmd-diagnostic-inputs.json para reconstruir os seis diagnósticos e o pin-cycle em pastas novas, somente após um build completo comprovado. O comando --check verifica inputs/estado sem extrair ou compilar; exige Linux ARM64 sem root, arquivo de source fixado, bundle completo e Image/config/exports correspondentes ao resultado real do build. Nenhum seletor de runtime é alterado nesta fatia.
- **Por quê:** a versão distinta exige módulos recompilados; reunir também o diagnóstico HDQ/UJM evita um DFU exclusivo para cada componente. Entre os 69 inputs da qualificação do caller anterior, somente o diagnóstico I2C separado mudou; os inputs PCIe/runtime permanecem iguais. Os gates HDQ/UJM já concluídos são reutilizados com seus inputs intactos; o build novo prova a ABI e os imports.
- **Alternativas:** aceitar módulos de power2 com carregamento forçado é recusado; recompilar no source/build anterior destruiria a separação de artefatos. Esperar sem preparar os inputs atrasaria a sessão agrupada.
- **Reverter:** baixo; os outputs são privados e novos, sem instalação ou carga.
- **Verificação:** AST/lint, --check real na VM e recusa de um tar corrompido sem criação do destino; build W=1/Werror, ELF/ABI/imports/params e hashes dos inputs/kernel antes/depois. A prova no aparelho permanece pendente.
- **Status:** aplicada; compilação/integração base verificadas, aceite físico continua pendente.

### D3 — seleção opt-in no integrador de kernel

- **Decisão:** ampliar scripts/build/integrate-source-kernel.py para o bundle PMD explícito e o registro público separado kernel-n71-pmd-build.json. O registro só será produzido de um build real concluído; sua ausência deve recusar a integração antes de criar saída. Preservar todos os caminhos anteriores, validações completas de source/blobs/patches/Image/configuração e identidades. PMD exige GPIO/PMGR incorporados e initramfs sem módulos da ABI antiga.
- **Por quê:** adianta a composição sem usar hardware ou inventar hashes enquanto a única compilação pesada continua. A nova seleção não altera o payload padrão nem autoriza módulos incompatíveis.
- **Alternativas:** esperar o build sem preparar a composição adia a sessão agrupada; reutilizar o registro power2 cruza ABI e será recusado.
- **Reverter:** baixo; a seleção exige opção explícita, não muda perfis existentes.
- **Onde:** integrador, tests/test_kernel_pmd_integration.py, ajustes mínimos de âncoras em tests/run_kernel_integration_mutations.py e este plano. Nenhum seletor de runtime ou driver é ampliado nesta fatia.
- **Verificação:** CLI real e filesystem temporário com kernels sintéticos não inicializáveis; seleção/identidades/modos, falta de registro, registro power2 cruzado, todos os oito blobs/patches, link/export/release/configuração e módulos antigos; mutações novas por AssertionError, regressão antiga focalizada, AST/lint. A prova física continua pendente.
- **Status:** aplicada; compilação/integração base verificadas, aceite físico continua pendente.

### D4 — conjunto Wi-Fi recompilado para PMD

- **Decisão:** ampliar scripts/build/build-n71-wifi-modules.py com a identidade PMD explícita e os hashes reais de config/Image/exports do build concluído. Preservar os dois perfis anteriores, o perfil padrão, as recusas existentes e o patch MSI aplicado somente na cópia do pacote. Compilar rfkill/cfg80211/Broadcom em pasta nova da mesma VM, sem instalar ou carregar.
- **Por quê:** os módulos power2 não podem ser carregados com a release PMD; a próxima sessão precisa do driver e dos diagnósticos na mesma ABI. O kernel PMD já está pronto e será reutilizado.
- **Alternativas:** forçar vermagic cruza ABI e não será usado; alterar a configuração ou o source preservado desfaz a separação do build. Outro build de kernel não agrega valor nesta etapa.
- **Reverter:** baixo; selecionar o perfil anterior, cujos hashes e artefatos continuam intactos.
- **Onde:** builder Wi-Fi, tests/test_n71_wifi_modules.py (CLI/ELF selecionados), tests/run_n71_wifi_modules_mutations.py (duas âncoras), tests/test_n71_pmd_wifi_modules.py (novo) e este plano. Cinco arquivos; seletores de runtime ficam para a próxima fase.
- **Verificação:** identidade ligada ao registro público compilado; filesystem real e ELF sintético para recusas de hashes/release cruzados; CLI sem build, mutações por AssertionError, regressão dos 24 mutantes antigos, AST/lint no Mac e gates ARM64. Depois, build real com Werror/modpost, oito módulos, alias 14e4:43a3, símbolos PCIe/MSGBUF e imports resolvidos, source/Image/config/exports preservados antes/depois. Nada disso substitui prova física de Wi-Fi.
- **Status:** aplicada; oito módulos auditados na VM/Mac, carregamento físico pendente.

## Fase C — um teste físico agrupado

Antes de solicitar DFU, preparar kernel, todos os módulos compatíveis, perfil privado com identidades preservadas, diagnóstico HDQ UJM, restore e coleta/cleanup numa sessão limitada. O aparelho está no iOS bloqueado e recarregando; nenhuma ação necessária agora. Após retorno ao iOS, ausência de USB é tratada como tela bloqueada, sem nova confirmação rotineira.

## Verificação

Gates novos no Mac e ARM64; regressão dos bundles impactados sem repetir gates de módulos que não mudaram. AST/lint Python; não há typechecker Python configurado. Conferir inputs e artefatos protegidos antes/depois. Publicar apenas código e fatos/hash/endereço sanitizados, sem bytes Apple, firmware, identidades ou logs privados. Não encerrar issue #46 sem prova física de DMA/firmware/comando, nem afirmar WLAN, carga ou telemetria por build.

## Tarefas

- [x] Confirmar e registrar a diferença PMD na fonte primária.
- [x] Implementar patch, seleção e contratos nativos; Mac e ARM64 aprovados (387 cenários/12 mutações em cada).
- [x] Qualificar objetos e build completo isolado (Image PMD e cópias Mac verificados).
- [x] Reconstruir os sete diagnósticos com W=1/Werror e imports/ABI conferidos.
- [x] Qualificar o integrador opt-in e criar o perfil base privado, sem alterar o padrão.
- [x] Reconstruir e auditar os oito módulos Wi-Fi da ABI PMD.
- [ ] Integrar o novo kernel/módulos em perfil opt-in sem alterar o padrão.
- [ ] Reunir HDQ e Wi-Fi antes de um DFU necessário.
- [ ] Comprovar o comportamento no aparelho e atualizar as issues.

## Andamento e recuperação do build

Mac: 387 cenários do instalador/configuração com 12 mutações compiladas; bundle novo 5 testes/7 mutações; regressão dos três bundles anteriores 15 testes/14 mutações. AST e lint aprovados, sem typechecker Python. As APIs de memória, barreira e CAS são modeladas; não é prova de coerência ou concorrência do DART físico.

O primeiro preparo ARM64 excedeu 180 s no checkout do worktree, antes da aplicação do patch e antes de compilar. Source/config/Image/exports power2 foram novamente conferidos e preservados. O processo filho terminou; não há checkout concorrente. O builder público permite 600 s para um worktree novo e uma retomada explícita --resume-source somente quando inputs selados e checkout exato passam pelas recusas existentes. Não reiniciar um build por timeout de observação. Nenhum reboot ou pedido ao operador foi feito nesta fase.

## Checkpoint de 15/10 — ABI e recursos

A fonte ARM64 completa e os dois objetos reais do DART passaram com W=1/KCFLAGS=-Werror; o link completo segue no processo existente, sem reinício. As duas execuções de CI do commit 04a1cb08e54a46567446fbeaa8a3eef1d2a87128 (38769221147 e 38769214197) terminaram com success. Os 62 inputs dos sete diagnósticos estão selados. Após recuperar o timeout externo do primeiro gate ARM e corrigir a comparação JSON de tuplas/listas no preflight, Mac e ARM64 passaram seis testes/seis mutações de inputs/registro e seis testes/cinco mutações de integração. O preflight real, a recusa do pacote corrompido e o build completo dos sete diagnósticos passaram; não houve instalação ou carga no aparelho.

A limpeza autorizada removeu 72 binários locais obsoletos (1.667.619.582 bytes lógicos), mantendo perfis atuais/fallback, snapshots, metadados e o build ativo. Não havia workers próprios para fechar; GC conferido e executado, sem itens elegíveis. Não abrir novos painéis nem iniciar outro build pesado enquanto houver pressão de recursos.

## Resultado desta fatia

O build completo terminou com exit 0 em 2489 s; Image c6c020756b970ebb77d1eb8e7975682385efacdbdefaacc78b70b8b8eb177246, configuração/DTB/exports verificados e kernel anterior preservado. A integração base privada real passou, com identidades SSH e padrão intactos. D2 concluiu o build dos sete módulos; D3 concluiu os gates e a integração base. A comparação JSON corrigida não relaxa os pins da fonte. Os fatos públicos estão em kernel-n71-pmd-build.json, n71-pmd-preparation-qualified.json, n71-pmd-diagnostics-build.json e n71-pmd-base-integration.json sob docs/evidence/.

Próxima fatia: selecionar os hashes reais da ABI PMD no builder Wi-Fi e recompilar o conjunto WCC isolado. Depois, ampliar os gates de runtime em fases e compor um perfil completo, preservando power2. Nenhum DFU ou leitura de PIN nesta fatia. Wi-Fi, HDQ e carregamento físico seguem pendentes.

### D4 — recuperação da varredura global

Os gates Mac e ARM64 da primeira candidata passaram, mas a varredura global de features em Git excedeu o limite genérico de 30 s, antes de criar a saída ou iniciar a compilação. O helper global kernel_patchset.py permanece intacto. Apenas essa consulta completa recebe 180 s no builder Wi-Fi; o teste usa um repositório Git real com feature fora do pacote e uma mutação que limita a busca ao Broadcom, exigindo falha por AssertionError. O arquivo temporário staged do teste é removido explicitamente na pasta descartável, sem tocar no repositório do projeto. Mac: cinco testes PMD/cinco mutações, 15 testes anteriores/24 mutações; AST/lint aprovados. A retomada exige destino ainda inexistente; não reiniciar builds por timeout de observação.

### Resultado D4

Mac e ARM64 aprovaram 20 testes e 29 mutações por plataforma. O conjunto Wi-Fi foi compilado com Werror/modpost; oito módulos com imports resolvidos e ELF/ABI/hashes auditados no Mac. PMD e power2 preservados. O timeout da auditoria Git após a compilação foi recuperado somente com verificações; não se recompilaram os módulos prontos. Os inputs e resultados estão em docs/evidence/n71-pmd-wifi-modules-qualified.json. A comparação de cinco seções executáveis, 135 imports e parâmetros do caller antigo/PMD está em docs/evidence/n71-pmd-caller-reuse.json; só a vermagic mudou em .modinfo. Os 69 inputs antigos diferem apenas no C do módulo I2C separado, sem mudança no caller PCIe/headers ou nos seus testes nativos.

Próxima fase: qualificação explícita da variante PMD nos seletores de IOMMU/recursos, depois manifests WCC/Session/CLI e composição do perfil completo. Preservar caminhos power2, provas históricas e o padrão. Nenhum carregamento físico nesta fase.

### Recursos ao fim de D4

A VM dedicada foi confirmada ociosa (make/cc1/cc1plus/ld.bfd/git = 0) e desligada pelo Multipass; o estado Stopped foi confirmado. A próxima fase usa os artefatos já copiados no Mac. Kernel/source PMD e power2, módulos e tools v2 foram preservados para a próxima necessidade de VM. Somente as duas cópias v1 na VM e o tar v1 local foram removidos, com recibo privado. Nenhum painel/worker novo, nenhuma instalação/configuração global do Mac e nenhuma ação no iPhone nesta fase.

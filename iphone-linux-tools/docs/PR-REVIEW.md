# Revisão da PR #1 — #16

## Escopo e plano

Revisão solo da branch `feat/display-console`, sem merge/tag. Baseline `168b95453d672a1ae862bf608bf39d5a463ec2f8`; primeira revisão no head `8a0a04873baeffe1b7ce18b48f0628a14d29e425`. O diff tem 120 arquivos, incluindo documentação, evidências, fontes, testes e remoções. Não declarar revisão integral antes de conferir todas as áreas e contabilizar a cobertura.

1. Persistência local e proteção do Mac: ler backup/restore, journal, lock, retenção e testes; reproduzir desvios somente em pastas temporárias sintéticas, registrar e corrigir falhas. Até cinco arquivos nesta fase: este documento, `scripts/host/persist.py`, `restore_journal.py`, `snapshot_lock.py` e `tests/test_local_snapshot_paths.py`.
2. Verificação/documentação (cinco arquivos): runner público de caminhos, runner de autosnapshots com a âncora do guard compartilhado, CI, este documento e PERSISTENCIA. Fase documental seguinte (quatro arquivos): este documento, RECUPERACAO, STATUS e `evidence/local-snapshot-paths.json`. Reutilizar evidências não afetadas; executar fixtures VM relevantes quando a correção modificar o restaurador usado neles.
3. Continuar revisão dos demais caminhos de boot, rede/DNS, build e evidências; conferir também fontes removidas no baseline. Atualizar o corpo antigo da PR, que ainda trata wrapper/DNS/CI como inexistentes.
4. Registrar limites/cobertura e critérios da #16. Gates físicos da candidata, energia, estabilidade e autorização de merge não são substituídos pelo CI/revisão.

## D1. Recusar desvios locais antes de leitura/escrita

- **Decisão:** compartilhar a verificação de diretórios/arquivos locais reais e próprios em `snapshot_lock.py`, usá-la na leitura de snapshots e no journal. Não seguir links para corrigir permissões, procurar referências de recuperação ou carregar um backup.
- **Por quê:** o projeto só pode escrever no store privado próprio e o ID normal de um snapshot não garante que seu diretório esteja dentro desse store. A retenção já recusava links, mas os outros consumidores tinham um contrato diferente.
- **Alternativas:** documentar confiança absoluta na árvore local deixa alterações acidentais perigosas; resolver symlinks e aceitar destinos internos amplia a política e dificulta compreender o que pode ser restaurado.
- **Reverter:** baixo; alteração de código na branch, sem migração ou regravação de dados existentes. Os snapshots/journals regulares continuam compatíveis.
- **Status:** aplicada e verificada localmente, na VM e no CI Ubuntu/macOS de `6a7775c`; revisão integral da PR permanece pendente. Não comprova proteção contra um processo malicioso do mesmo usuário alterando a árvore concorrentemente.

## Falha local confirmada — #22

Dados sintéticos: `restore-journal` apontando para uma pasta externa ao store. `prepare` escreveu JSON nessa pasta e mudou seu modo de 755 para 700. Um diretório de snapshot de ID válido apontando para outro diretório também foi carregado fora do store. Nenhum arquivo real do operador foi usado ou alterado. A hipótese foi validada com caminhos canônicos e modos explícitos; a primeira observação tinha umask/comparação de aliases inadequados e não foi usada como prova.

A pasta privada reduz a exposição a outros usuários, mas não torna seguro seguir um link acidental ou uma árvore modificada. Esta é uma falha de escopo local de arquivos; não estamos afirmando uma exploração remota por um cliente DNS/HTTP.

## Critérios desta correção

- [x] Recusar diretório de journal/snapshot symlink, arquivo symlink/hardlink, tipo especial e propriedade incompatível antes de leitura/escrita.
- [x] Preservar conteúdo, modos e arquivos de uma pasta externa sintética quando houver desvio.
- [x] Listagem/default/restore/retorno ao iOS usam os mesmos gates de caminho; retenção continua preservando estruturas inválidas.
- [x] Snapshot/journal regulares continuam funcionando; corrupção continua bloqueando restore.
- [x] Executar mutações, lint/sintaxe e testes afetados; nenhum type checker configurado.
- [x] Preparar evidência sanitizada e procedimentos; sem dados privados, migração ou merge. Publicação/atualização de #22/#16/#17 acompanha esta fase documental.

## Cobertura desta rodada

Leitura completa: `persist.py`, `snapshot_lock.py`, `restore_journal.py`, `snapshot_retention.py`, `scripts/ci/check-public.py`, `tests/test_persistence.py` e os novos `tests/test_local_snapshot_paths.py`/`run_snapshot_path_mutations.py`. Testes de retenção/falha VM e wrapper original parcialmente lidos para seguir chamadas; não contabilizados como revisão completa. Demais áreas da PR continuam pendentes.

## Evidência da correção — fase 1

Nove testes de caminhos locais passaram; 11/11 mutações foram detectadas por asserção em cópias sintéticas. Seis testes de persistência, oito de retenção/lock e seis de agendador passaram. O guard de metadata é compartilhado por caminhos e descritor do lock, incluindo propriedade/tipo/link; sob root na VM, um arquivo sintético com outro UID também foi recusado pelo lock.

VM dedicada existente, sem mounts: nove testes de caminhos locais, dois cenários BusyBox reais de ENOSPC/interrupção e um cenário de agendamento/restore passaram após o compartilhamento final do guard. Duas mutações do restaurador foram rejeitadas na etapa anterior da mesma correção; seus predicados de journal pré-upload/erro remoto não mudaram no ajuste final do guard e essa evidência foi reutilizada. Fontes públicas somente; nenhuma chave, snapshot real ou pacote instalado. Limpeza/estado final da VM e CI serão registrados na fase seguinte.

Lint fatal e diff-check passaram. Não há type checker configurado. A alteração não torna o restore transacional nem protege contra autores concorrentes do mesmo usuário; limita leitura/escrita a nós locais regulares esperados. Ainda não houve operação no iPhone nesta correção.

## Verificação/limpeza — fase 2

Runner de 11 mutações preparado e registrado no CI Ubuntu/macOS: baseline e 11/11 mutações passaram no Mac. O runner anterior de autosnapshots agora mira `not valid_type` no guard compartilhado; a mudança de âncora conserva o teste do FIFO no lock e as 15/15 mutações foram rejeitadas. Flake8 fatal e `git diff --check` passaram após esses ajustes. A VM dedicada foi devolvida a `Stopped`, sem mounts: confirmado nenhum fixture/mount temporário próprio e removida somente a árvore de transferência pública desta rodada. Demais VMs não foram iniciadas ou modificadas.

CI integral passou no commit `6a7775c7884c38b2c2cd9f135a6c8fb140d698bf`: [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/36822619421) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36822616022), ambos terminais. Os quatro logs confirmam 109 testes por plataforma/execução, 100 aprovados e nove skips explícitos; 11 mutações de caminhos, 20 de perfil, nove de retorno, sete de integração kernel, seis de formato Pongo e 11 de seleção Pongo. Guard/lint/sintaxe aprovados e ShellCheck Linux passou. Correção de paths não implica revisão completa da PR ou prova física nova de alimentação/boot.

## Encerramento da correção #22 — fase 3

Fonte: plano acima e issue #22. Modo: encerramento de uma correção dentro da revisão #16, com o goal geral ativo. Resultado: contrato local compartilhado, nove regressões e runner de 11 mutações registrados no CI. Os dois commits de código/verificação são `c5d697a` e `6a7775c`; a evidência final é [local-snapshot-paths.json](evidence/local-snapshot-paths.json).

**Arquivos:** três módulos host, teste e runner novos, runner de autosnapshots, CI, PERSISTENCIA/RECUPERACAO/STATUS e este relatório/evidência, divididos nas fases de até cinco arquivos. **Desvio de escopo:** corrigida também a receita pública da VM, que listava apenas dois módulos e deixava de transferir três imports exigidos pelo restaurador. É correção documental para reproduzir os gates, sem comportamento novo no aparelho. O corpo antigo da PR foi alinhado aos gates de wrapper/snapshots/DNS/CI já realizados, mantendo explícitos os pendentes.

| Verificação | Resultado |
|---|---|
| Testes locais afetados | 9 caminhos, 6 persistência, 8 retenção/lock e 6 agendador aprovados; matriz completa repetida no CI |
| VM com dependência real | 9 caminhos, 2 falhas BusyBox/recuperação e 1 agendamento/restore aprovados após guard final |
| Mutações locais | 11/11 de caminhos e 15/15 de autosnapshots rejeitadas; 2 de restore da mesma correção reutilizadas com predicados inalterados |
| CI | 109 testes por plataforma/execução: 100 aprovados, 9 skips; seis runners de mutações aprovados |
| Tipos | Nenhum type checker configurado; lint/sintaxe não equivalem a tipos |
| Lint/privacidade | Flake8 fatal, sintaxe Bash, ShellCheck Linux, guard público e diff-check aprovados |
| Limpeza | Fixtures/mounts/transferência próprios removidos, VM parada sem mounts; outras VMs não alteradas |
| Banco/dependências | Nenhum banco/pacote novo, nenhuma configuração global no Mac |
| Desempenho | Acrescenta consultas de metadata local; nenhuma alteração de throughput/serviço no telefone medida |

**Mudança observável:** uma árvore privada com links/tipos/propriedade inválidos agora aborta leitura/listagem/default/journal em vez de seguir o desvio. Snapshots regulares permanecem compatíveis e não foram migrados. **Limites:** overlay não transacional, autores concorrentes sem suporte, guard público não é auditoria integral de segredos. **Próximos passos:** #16 mantém leitura das demais áreas; #12/#21 requerem USB detectado e operador no novo piloto, #2/#8 conservam seus gates físicos. Nenhuma operação no iPhone ou merge nesta correção.

## D2. Compartilhar integridade das ferramentas externas — #23

- **Decisão:** conferir metadata, tamanho e SHA de palera1n/pongoterm com um helper comum; monitor direto verifica palera1n antes de USB/estado/filho, wrapper verifica ambas antes de execução. Pins do manifesto preservado; nenhum hash observado é aceito automaticamente.
- **Por quê:** reprodução com ferramentas sintéticas alteradas comprovou execução de palera1n no monitor direto e de pongoterm no wrapper. O fluxo anterior só conferia palera1n dentro do wrapper. Ferramentas reais preservadas continuam coincidindo com os hashes e tamanhos registrados.
- **Alternativas:** duplicar pins em cada consumidor cria divergência; depender de conferência manual permite executar um insumo modificado sem o controle solicitado pelo operador.
- **Reverter:** baixo; código aditivo sem instalação ou troca de binários. Insumos novos exigem proveniência e revisão explícita dos pins.
- **Onde:** fase 1 (cinco arquivos), helper `boot_tools.py`, monitor, wrapper, novo `test_boot_tools.py` e este plano; fase 2 (cinco), fixtures BootWrapper/ProfileBoot/PongoSelection, runner PongoSelection e novo runner de ferramentas; fase 3 (até cinco), CI/procedimentos/evidência. Plano/critério detalhados na #23.
- **Status:** sete regressões novas e 15 testes existentes de monitor/perfil/Pongo aprovados; nove mutações de ferramentas, 11 PongoSelection e 20 de perfil rejeitadas na fase 2. Fase 3 (cinco arquivos) acrescentou assertion/mutação do erro de nome desconhecido: baseline e 10/10 mutações finais passaram; lint fatal/sintaxe/ShellCheck/diff-check e leitura dos dois executáveis preservados também aprovados. Runner registrado no CI; [evidência](evidence/boot-tools-check.json) local com CI explicitamente pendente. O nome desconhecido nunca admitiu ferramenta arbitrária, porque o lookup nos pins continuava recusando a chave; faltava garantir a saída de erro legível, sem traceback. Obter CI terminal antes de encerrar. Não equivale a auditoria do binário ou proteção contra autores concorrentes do mesmo usuário; nenhum boot físico nesta fase.

Atualização da fase 4: correção aplicada e CI terminal aprovado em `f50d44070b5a3492115c93fefab6ef9f839ac5f8`, [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/36825015535) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36825010472). A indicação pendente acima registra o checkpoint anterior; a evidência JSON agora contém o resultado final.

O primeiro fixture de permissões usava setuid; o filesystem do Mac limpou esse bit ao aplicar chmod, de modo que o fixture não representava o caso pretendido. O teste passou a usar o bit especial sticky, com asserção de que o modo foi realmente aplicado, antes de conferir a recusa. Não foi alterado o guard operacional `0o7022`, que recusa todos os bits especiais e escrita por grupo/outros.

## Operação das ferramentas de boot — #23

Os executáveis preservados podem ser conferidos sem executá-los, a partir da raiz do clone: `python3 iphone-linux-tools/scripts/boot/boot_tools.py palera1n-macos-arm64 pongoterm`. Saída zero significa metadata/tamanho/hash conferidos; nenhum contato USB, instalação ou processo de ferramenta é iniciado. O monitor direto confere palera1n antes de publicar estado e iniciar filho. O wrapper confere palera1n/pongoterm antes de iniciar o monitor ou enviar um payload; se Linux já estiver ativo e só houver conexão, não executa as ferramentas externas.

Ao receber `Ferramenta de boot inválida`, preserve o erro e o insumo; não desabilite proteções do Mac nem edite o pin para fazê-lo coincidir com um download desconhecido. A conferência usa os hashes preservados em `docs/artifacts.json`, não um digest fornecido pelo ambiente. Uma versão nova exige conferir origem/build e revisar explicitamente seu pin em uma mudança separada. O snapshot e o retorno físico ao iOS continuam sendo os procedimentos existentes.

Reprodução sintética: `python3 -m unittest discover -s iphone-linux-tools/tests -p test_boot_tools.py -v` e `python3 iphone-linux-tools/tests/run_boot_tool_mutations.py`. Não usam binários reais, dispositivo ou sudo. Ferramentas inválidas agora abortam o boot antes de sua execução, sem troca de binários ou alteração de imagens. Proteção contra substituição concorrente do mesmo usuário e auditoria completa das ferramentas continuam fora desta correção.

Cobertura adicional lida por inteiro: wrapper atual, `dfu_boot.py`, `dfu_state.py`, `pongo_select.py`, `device_profile.py`, diagnóstico `phone/diagnostics/power-check.sh` e testes BootWrapper/DfuState/ProfileBoot/PongoSelection/PowerCheck, além de helper/regressões/runner #23. A leitura local atual encontrou a lacuna de ferramentas e registrou a correção; os restantes arquivos e os removidos do baseline ainda precisam contabilização para #16.

## Encerramento da correção #23 — fase 4

Fonte: decisão D2 e issue #23. Modo: encerramento de uma correção dentro de #16, com o goal geral ativo. Código/fixtures/CI em `3783de6`, `480638f` e `f50d440`. Cinco arquivos documentais nesta fase: este relatório, BOOT-PLAN, STATUS, evidência de ferramentas e inventário de cobertura. Não houve merge, instalação, troca de binário ou boot no aparelho.

**Resultado:** guard de executáveis compartilhado entre wrapper e monitor direto; ferramentas preservadas válidas aceitas por leitura, ferramentas sintéticas modificadas recusadas sem execução. **Desvio de escopo:** o inventário de cobertura foi acrescentado para contabilizar explicitamente inclusões/modificações/remoções no baseline da revisão; ele registra leituras, não uma aprovação integral. São [24 leituras completas em 139 entradas de diff sem renames](evidence/pr-review-coverage.json), fixadas por blob e commit `f50d440`; arquivos removidos antigos ainda não foram revisados por inteiro. A etapa seguinte precisa atualizar essa cobertura e inspecionar áreas restantes.

| Verificação | Resultado |
|---|---|
| Novas regressões | 7/7 passaram, metadata/hash/tamanho e recusa nos pontos reais de entrada com processos sintéticos |
| Fluxos existentes afetados | 2 monitor/wrapper, 5 perfil/boot e 8 seleção Pongo aprovados no Mac |
| Mutações locais | 10/10 ferramentas, 11/11 seleção Pongo e 20/20 perfil rejeitadas; evidência de Pongo/perfil reutilizada após ajuste somente do erro de nome desconhecido |
| CI integral | Quatro jobs terminais em Ubuntu/macOS, cada um com 116 testes: 107 aprovados, 9 skips explícitos |
| Mutações CI | 10 ferramentas, 11 caminhos, 20 perfil, 9 retorno, 7 integração kernel, 6 formato Pongo, 11 seleção Pongo por job |
| Lint/privacidade | Flake8 fatal/sintaxe Bash, guard público e ShellCheck Linux passaram; diff-check local sem erros |
| Tipos | Nenhum type checker configurado |
| Limpeza | Cópias/fixtures descartáveis encerrados; nenhum processo de ferramenta real iniciado ou VM iniciada nesta correção |
| Banco/dependências | Nenhum banco, pacote, sudoers ou configuração global alterados |
| Desempenho | Conferência de bytes/metadata dos dois executáveis antes do boot; nenhuma medição de throughput do telefone foi realizada |

**Riscos/continuidade:** integridade contra insumos preservados não é auditoria completa dos binários; alterações concorrentes do mesmo usuário não são suportadas. Não editar os pins para aceitar um arquivo desconhecido. #23 pode ser encerrada após publicação desta evidência; #16 mantém revisão integral/main/merge, #12/#21 mantêm piloto e rollback físicos e #2/#8 mantêm alimentação/estabilidade. O índice #17 registra as pendências; o telefone continua aguardando disponibilidade USB.

## D3. Conferir o namespace de bibliotecas do bundle DNS — #24

- **Decisão:** validar a lista/records e basenames ASCII canônicos/únicos antes de construir os caminhos permitidos no tar. Digest e checks de tipo/escopo existentes permanecem necessários. Não modificar pacote, imagens ou protocolo de extração remota.
- **Por quê:** o verificador aceitou `../` em um membro quando o mesmo texto era informado pelo manifesto como nome de biblioteca. Correspondência de hash não estabelece um namespace seguro. A reprodução foi sintética, sem extração ou SSH; não demonstra escape no tar do telefone.
- **Alternativas:** confiar implicitamente no manifesto deixa a declaração de escopo expansível; normalizar e aceitar subdiretórios dificulta definir o conjunto permitido e não corresponde ao layout plano do builder.
- **Reverter:** baixo; nenhum bundle é regravado ou biblioteca movida. Os basenames normais do builder permanecem compatíveis.
- **Onde:** fase 1 (cinco arquivos), `dns.py`, novo teste/runner de bundle, CI e este plano. Fase 2 documental (até cinco), este relatório, DNS, STATUS, evidência e cobertura. Executar baselines/mutações/CLI sintéticos, conferir bundles preservados por leitura e revalidar instalador na VM própria quando disponível, com limpeza e sem pacotes/identidades reais. Plano/critério na #24.
- **Status:** seis cenários sintéticos/CLI e 10/10 mutações aprovados; lint fatal e diff-check passaram. Bundles preservado/reproduzido de 4.614.005/4.613.949 bytes passaram por leitura, sem modificar insumos. Revalidação na VM dedicada em curso; CI/publicação pendentes. Não equivale a assinatura do manifesto, parser com limites completos de descompressão ou instalação transacional. Nenhuma extração no Mac nem ação no telefone nesta correção.

O runner inicialmente usou a âncora `or name in names`, que também aparecia dentro do texto do generator `for name in names`; a validação de unicidade recusou a mutação antes de executá-la. O resultado inicial não foi contado como mutação detectada. A âncora passou a incluir o `:` da condição, e o runner final completou dez mutações com falha de assertion; nenhuma validação operacional foi alterada para facilitar o teste.

## Encerramento da correção #24 — fase documental

Fonte: decisão D3 e issue #24. Código/CI em `d9110cd`; até cinco arquivos nesta fase: relatório, DNS, STATUS, evidência e inventário de cobertura. A declaração de nomes no manifesto podia ampliar o escopo permitido; nomes canônicos únicos agora são necessários antes do SSH. A reprodução não extraiu arquivos nem demonstrou escape do tar remoto.

| Verificação | Resultado |
|---|---|
| Regressões locais | 6/6, CLI e bundles sintéticos; transferência positiva com manifesto explícito e recusas sem SSH |
| Mutações locais | 10/10 detectadas após baseline verde; primeira âncora não única não foi contada |
| Insumos preservados | Dois bundles com 22 bibliotecas conferidos por leitura; bytes/hashes na evidência |
| VM Linux | 6/6 novas regressões e 2/2 instalação/restore por SSH e DNS reais; 7/7 mutações existentes recusadas |
| CI Ubuntu/macOS | Quatro jobs terminais aprovados em `d9110cd`: 122 testes por job, 113 aprovados/nove skips; dez mutações DNS por job, demais runners existentes também verdes |
| Lint/tipos | Flake8 fatal/diff-check aprovados; nenhum type checker configurado |
| Limpeza | Transferência própria removida, zero fixtures/montagens restantes, VM dedicada parada sem mounts |
| Banco/dependências | Nenhum banco, pacote ou configuração global do Mac alterado; dependências existentes na VM |
| Desempenho | Uma passagem sobre nomes de bibliotecas; throughput do telefone não medido |

**Compatibilidade:** bundles normais e seleção explícita continuam funcionando; entradas malformadas, duplicadas ou com caminhos passam a abortar. **Limites:** validação de namespace não autentica todo manifesto, não impõe limites completos de descompressão e não torna a instalação transacional. Nenhum boot no aparelho nesta correção. [Evidência](evidence/dns-bundle-scope.json). #16 continua parcial, #12/#21 requerem piloto físico da nova cadeia, #2/#8 conservam seus gates físicos.

CI do código aprovado: [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/36828530652) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36828523923), com Flake8 fatal, sintaxe, guard público e ShellCheck Linux aprovados. Inventário atualizado: 34 leituras completas em 142 entradas do baseline até `d9110cd`; continua parcial, sem aprovação integral ou merge. O estado em curso na decisão D3 registra o checkpoint anterior; esta seção e o JSON contêm a conclusão dos gates.

## D4. Mapear o caminho Wi-Fi da candidata N71 — #9

- **Decisão:** comparar fonte fixada, DTB/configuração/initramfs selecionados e demonstrações específicas por SoC; manter USB e separar identificação provável do chip de enumeração real. Não portar reguladores/endereços A10 nem adicionar firmware sem dados N71.
- **Por quê:** a candidata não contém um caminho Wi-Fi operacional: DTB sem nó de barramento/rádio correspondente, driver host sem entrada S8000 comprovada, transporte PCIe brcmfmac desligado e módulos ausentes. Habilitar uma opção ou copiar firmware não estabelece a topologia.
- **Alternativas:** testar o fork A10 às cegas pode programar controladores incompatíveis; aguardar somente USB não avança os requisitos que já podem ser examinados por leitura.
- **Reverter:** baixo; investigação documental sem trocar imagem/configuração ou executar código externo.
- **Onde:** até quatro arquivos públicos, este plano/relatório, WIFI, STATUS e evidência sanitizada. Ler fontes nos commits exatos, conferir insumos locais por hash/estrutura e registrar critérios pendentes em #9/#17. Nenhuma instalação, VM ou ação no telefone nesta fase.
- **Status:** fontes baixadas como texto; inspeção local concluída; documentação/publicação em curso. A issue #9 permanece aberta para identificação da placa, energia/reset/DMA e enumeração/associação nativas.

## Relatório da investigação Wi-Fi — #9

Quatro arquivos documentais nesta fase: plano/relatório, WIFI, STATUS e evidência. Fonte estável/DTB/configuração/initramfs fixados por SHA; tabelas de driver e matriz A10 consultadas por commit. Inspeção de estrutura local sem executar binários externos ou revelar identidades: 136 nós DTB, 2.969 entradas newc, zero módulos; pasta `lib/modules` apenas. Configuração e topologia impedem tratar a candidata como Wi-Fi pronta.

| Verificação | Resultado |
|---|---|
| Fontes/insumos | Doze textos públicos por commit/blob/hash; três artefatos locais por hash e leitura estruturada |
| Hardware | Nenhuma enumeração nova, associação/DHCP ou firmware enviado; #9 permanece aberta |
| Testes/lint/tipos | Código operacional inalterado; evidência CI anterior reutilizável. JSON, hashes, diff e guard público verificáveis nesta fase; nenhum type checker configurado |
| Banco/dependências | Nenhum banco, pacote, firmware, VM ou configuração do Mac alterado |
| Desempenho/compatibilidade | Nenhum impacto operacional ou substituição de imagem; resultado documental não mede throughput |
| Próximos passos | Boot selecionado, inventário read-only, identificação privada de placa/radio/DMA antes de desenhar o port N71 |

CI da publicação documental #24 também terminou verde: [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/36829031688) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36829026720), quatro jobs Ubuntu/macOS. A investigação não fecha gates de #2/#8/#12/#21, não autoriza parâmetros A10 e não constitui revisão integral #16 ou merge.

## D5. Separar persistência em disco de recuperação do boot — #10/#11

- **Decisão:** documentar o driver/topologia ausentes da candidata N71 e as duas cadeias upstream de boot, separando snapshots no Mac, eventual rootfs interno e capacidade de iniciar após perda de energia. Nenhum particionamento, fakefs, wipe, troca de kernel ou ferramenta externa nova.
- **Por quê:** ANS2 genérico e um tutorial de GPT não demonstram suporte ao controlador A9; iBoot remoto também parte de DFU e computador. Um filesystem persistente, mesmo funcionando, não altera por si só a cadeia de verificação/entrada do boot.
- **Alternativas:** aplicar layout/driver A10 ou A11 conserva um requisito não validado; remover iOS para tentar forçar outro boot pode produzir Recovery/DFU sem criar loader autônomo.
- **Reverter:** baixo; alteração documental, sem estado no aparelho.
- **Onde:** cinco arquivos, este plano/relatório, novos ARMAZENAMENTO e BOOT-AUTONOMO, evidência conjunta e STATUS. Ler fontes fixadas, conferir hashes/DTB/configuração selecionados, registrar inferências e gates pendentes nas issues #10/#11/#17 e manter o goal completo.
- **Status:** pesquisa/inspeção estática concluídas, publicação em curso. USB ausente; nenhum teste nativo novo, driver/firmware executado ou VM iniciada. #10/#11 permanecem abertas para os gates não comprovados.

## Relatório de storage e boot autônomo — #10/#11

Cinco arquivos documentais desta fase: plano/relatório, ARMAZENAMENTO, BOOT-AUTONOMO, evidência e STATUS. Nenhum código operacional ou artefato do telefone alterado. Fontes por commit/blob/hash, tabelas de drivers e docs upstream; inspeção local do mesmo DTB/configuração/initramfs usados em #9. A busca inicial `nvme` incluiu `nvmem`; foram separados os três registros PMIC antes de concluir ausência de controlador do disco.

| Verificação | Resultado |
|---|---|
| Fonte/artefatos | Seis novos textos públicos fixados; DTB e config correspondem aos hashes publicados. Módulos da mesma imagem ausentes, conforme evidência #9 reutilizada |
| Driver/topologia | ANS2 com matches T8015/T8103; adequação/controlador N71 não identificados. Células PMIC não são o disco |
| Boot | Pongo atual depende de DFU/Mac; alternativa iBoot upstream também parte de DFU e envio do host. Nenhuma demonstração autônoma encontrada ou executada |
| Testes/lint/tipos | Código operacional inalterado; CI anterior reutilizável. JSON/hashes/links/diff/guard público conferidos; nenhum type checker configurado |
| Banco/dependências | Nenhum banco, pacote, VM, firmware, partição ou configuração global alterado |
| Impacto | Documental; nenhuma medição de I/O, reboot ou carga nova |
| Próximos passos | Inventário nativo read-only, dados privados de placa/controlador; piloto kernel/Pongo/retorno/rollback e alimentação antes de operação prolongada |

#10/#11 permanecem abertas; critérios de identificação/detecção e recuperação física completos ainda não comprovados. CI da documentação Wi-Fi terminou verde: PR 36830037501 e push 36830033406, quatro jobs Ubuntu/macOS. Goal inteiro ativo, sem merge; não trocar prioridade dos gates de alimentação/boot pela disponibilidade de pesquisa estática.

## Herdr opcional — #13

Plano/decisão e contrato em [HERDR.md](HERDR.md). Fase de cinco arquivos publicada em `5f60dec`: helper host, wrapper, onze regressões, documento e [evidência](evidence/herdr-autostart.json). A inicialização é feita depois do restore pelo boot assistido; não foi adicionada ao init nem implica boot autônomo. Sessão própria `iphone-server` não interfere na sessão manual histórica ou no servidor do Mac. Configuração/processos em `/run`; snapshot conserva apenas marcador declarativo desta automação, junto dos arquivos de trabalho já previstos.

Leitura completa dos dois arquivos de código e do teste novo, com releitura do wrapper antes da edição. Fonte upstream fixada e ajuda 0.9.1 conferidas, digest da release comparado ao binário preservado. Isso não amplia a cobertura antiga da revisão integral para arquivos ainda não lidos; #16 continua parcial.

| Campo de encerramento desta fase | Resultado |
|---|---|
| Plano | Cinco tarefas de implementação/verificação atendidas; boot/reconexão físicos abertos |
| Testes locais | 133 no total: 124 aprovados, oito skips e um socket impedido pelo sandbox; somente esse teste reexecutado com permissão e aprovado |
| Herdr/mutações | 11/11 regressões; doze mutações negativas recusadas em cópias descartáveis |
| VM real | Bash 5.2, painel único preservado entre clientes CLI, restart e namespace novo a partir do marcador comprovados; sessão própria encerrada e fixture removida |
| Lint/sintaxe/tipos | Flake8 fatal, Bash e ShellCheck dos scripts gerados/wrapper passaram; sem typechecker configurado |
| Banco/dependências | Nenhum banco ou pacote instalado; binário Herdr oficial preservado; VM própria devolvida a Stopped/mounts vazios |
| Compatibilidade/impacto | `herdr` agora abre a sessão automatizada; sessão histórica pode ser acessada pelo shell. Um servidor e um Bash consomem RAM/CPU adicionais somente quando iniciados; nenhum benchmark nativo novo |
| Riscos | Lock não cobre edições concorrentes do mesmo usuário; restart fecha os processos dessa sessão. Falha de início requer conferir status antes de repetir |
| Próximos passos | Confirmar applets e novo boot/restauração do marcador com reconexão SSH/TUI no iPhone; alimentação e cadeia kernel/Pongo permanecem pendentes |

Os CIs da pesquisa anterior terminaram verdes, PR 36831163092/push 36831156321 no commit `b2a4844`. CI de `5f60dec` verde: [PR 36834443230](https://github.com/djalmajr/iphone6s-linux/actions/runs/36834443230), [push 36834436922](https://github.com/djalmajr/iphone6s-linux/actions/runs/36834436922), quatro jobs Ubuntu/macOS, cada um com 133 testes (124 aprovados, nove skips); logs também conferidos para as oito famílias de mutações anteriores registradas no workflow. As doze mutações Herdr são prova local, não um novo step de CI. Comentários de teste adicionados no encerramento preservam o AST; nenhum código operacional mudou após a CI. Esta fase de encerramento toca cinco arquivos: teste somente comentários, HERDR, STATUS, relatório e evidência. Nenhum novo boot ou intervenção no iPhone nesta fase: USB/libimobiledevice não detectaram o aparelho, e a pergunta de reconexão permanece pendente. Goal completo ativo, sem merge/tag/release.

## Guard do destino do empacotador — plano da revisão #16

Reprodução sintética confirmou que `compose-payload.py` segue um symlink de saída: alvo existente idêntico teve modo alterado de 755 para 600; um link quebrado criou arquivo fora da árvore escolhida. Nenhum arquivo real do operador foi alterado. A correção pertence à proteção do Mac e será rastreada por issue própria.

Fase de implementação (até cinco arquivos): `scripts/build/compose-payload.py`, `tests/test_compose_payload.py`, runner `tests/run_compose_mutations.py`, `.github/workflows/ci.yml` e este plano. Guard antes de ler/compor: destino ausente ou arquivo regular próprio, sem links/hardlinks/tipos especiais; cadeia de pais literal sem symlinks, com pasta de saída própria e não gravável por outros. Publicar arquivo novo por temporary privado e rename; preservar saídas existentes diferentes, aceitar recomposição idêntica sem regravar conteúdo. Referências atuais permitem outputs privados fora do repo, portanto não restringir a `artifacts/`.

- [x] Recusar links válidos/quebrados, hardlinks, FIFO e pais redirecionados antes de escrita/chmod.
- [x] Publicar blob privado exatamente igual à composição anterior; recomposição idêntica e erro preservam saídas anteriores.
- [x] Verificar falha de publicação/limpeza e controles negativos em testes observáveis; mutações e CI Ubuntu/macOS.
- [x] Registrar evidência, cobertura atualizada e limites; não alterar imagens/chaves/snapshots reais nem declarar revisão integral.

Alternativa rejeitada: resolver symlinks antes da escrita faria o desvio parecer um destino direto. O guard preserva paths literais; em macOS, use um caminho canônico quando o prefixo escolhido for um alias como `/tmp` ou `/var`. Não pretende impedir alterações concorrentes de outro processo do mesmo usuário. Nenhuma compilação upstream ou teste no aparelho é necessário para demonstrar este contrato local.

## Verificação do empacotador — #25

Código em `8a5d2ad`, [evidência sanitizada](evidence/compose-output-paths.json). Fase documental de quatro arquivos: este relatório, STATUS, evidência e inventário de cobertura. Suíte local: 143 testes, 135 aprovados e oito skips; dez regressões novas de filesystem/CLI e 12/12 mutações detectadas. Flake8 fatal e diff-check aprovados; sem typechecker configurado. O fixture usa sticky bit porque o filesystem limpa setuid em arquivo sintético; nenhuma proteção operacional foi removida.

A falha existia porque `exists`/`read_bytes`/`write_bytes`/`chmod` seguiam o link do destino. A validação agora precede composição e publicação, confere metadata literal e publica novas saídas por temporary privado. Arquivo regular idêntico mantém inode/mtime e recebe modo 600; conteúdo diferente permanece intacto. Paths com aliases como `/tmp` requerem diretório canônico. Saídas privadas fora do repo continuam permitidas. Não há proteção contra alterações concorrentes do mesmo usuário nem autenticação completa dos insumos nesta correção.

CI terminal aprovado: [PR 36838539001](https://github.com/djalmajr/iphone6s-linux/actions/runs/36838539001) e [push 36838531797](https://github.com/djalmajr/iphone6s-linux/actions/runs/36838531797), quatro jobs Ubuntu/macOS com 143 testes cada, 134 aprovados e nove skips; 12/12 mutações do empacotador detectadas por job. Guard, lint, sintaxe e ShellCheck Linux passaram; logs terminais conferidos. Nenhum pacote, banco, configuração global, imagem real ou identidade modificada; nenhuma ação USB/VM ou benchmark no telefone. Inventário atualizado por blob no commit do código, preservando como pendentes as remoções do baseline e arquivos não lidos. A revisão #16 continua parcial; boot/retorno/rollback da candidata requerem aparelho detectado e operador.

Inventário desta revisão: 56 leituras completas em 153 entradas de diff até `8a5d2ad`; é inventário de leitura, não parecer integral. As fontes removidas do baseline continuam pendentes. Desvio de escopo documental: atualizar inventário faz parte de #16; não altera os critérios operacionais de #25. Próxima pendência registrada como [#26](https://github.com/djalmajr/iphone6s-linux/issues/26): fixture próprio com `logs` symlink comprovou mudança de modo 755→700 e publicação externa de estado do agendador. Ainda não corrigida; nenhuma árvore real foi alterada. Goal geral ativo, sem merge/tag/release. O USB continuou ausente e o operador foi orientado a reconectar somente a ponta Lightning; nenhum monitor iniciou.

## Plano de proteção do estado do agendador — #26

Contexto: `logs` symlink desviou chmod e publicação; o leitor também segue links válidos/quebrados. Fase de até cinco arquivos: `scripts/host/autosnap.py`, `tests/test_autosnap_paths.py`, `tests/run_autosnap_path_mutations.py`, `.github/workflows/ci.yml` e este plano. Reutilizar `snapshot_lock.check_local_path` sem mudar seu contrato; validar raiz, logs e arquivo de estado antes de leitura, criação/chmod/publicação e antes do job. Logs ausentes no modo leitura retornam estado inicial sem criação. Escrita normal continua por temporary privado/rename, com cleanup em erro; revalidar destino antes do rename.

- [x] Recusar diretório/arquivo symlink, hardlink, tipo especial e propriedade incompatível sem alterar alvos nem iniciar job.
- [x] Preservar estado inicial, CLI normal, estado anterior em falha, publicação 600/700 e cleanup.
- [x] Executar regressões/mutações, lint e CI Ubuntu/macOS; registrar resultados e limites.
- [x] Atualizar documentação/evidência e #26/#16/#17 em fase documental posterior.

Decisão: manter um helper de caminho local no agendador, apoiado no guard compartilhado; não resolver symlinks nem apagar/corrigir estruturas inválidas. Não alterar snapshots/chaves reais ou dependências; sem proteção contra concorrência do mesmo usuário, serialização nova de jobs ou boot no aparelho. O piloto continua aguardando USB detectado; a CI documental anterior permanece em acompanhamento.

Verificação local #26: dez regressões novas aprovadas e 11/11 mutações detectadas; suíte integral 153 cenários, 145 aprovados e oito skips. Flake8 fatal/diff-check aprovados; sem typechecker configurado. A primeira chamada de lint usou paths da raiz com cwd interno e abortou antes de iniciar testes; paths corrigidos, lint e suíte concluíram. Nenhum pacote, VM, dado real ou ação no aparelho. CI documental de `51ade43` terminal verde, PR 36839163526/push 36839155235. Esse parágrafo registra o checkpoint antes da CI; resultado final abaixo.

## Encerramento da correção — #26

Fonte: plano acima e issue #26, correção dentro da revisão #16; goal geral ativo. Código `d5f2af1`. Fase documental de cinco arquivos: este relatório, AUTOSNAPSHOTS, STATUS, evidência e inventário. Mudança observável: estado/diretório com links ou metadata inválida aborta antes do job; estado normal permanece compatível e privado. Dez regressões, 11 mutações e suíte local 153 cenários (145 aprovados/oito skips); lint/diff aprovados, sem typechecker. CI terminal verde: [PR 36840191241](https://github.com/djalmajr/iphone6s-linux/actions/runs/36840191241) e [push 36840185496](https://github.com/djalmajr/iphone6s-linux/actions/runs/36840185496). Os quatro jobs Ubuntu/macOS executaram 153 cenários, 144 aprovados/nove skips e 11/11 mutações novas detectadas; logs conferidos. Guard, lint, sintaxe e ShellCheck Linux aprovados. [Evidência sanitizada](evidence/autosnap-state-paths.json).

Nenhum pacote, VM, banco, imagem real, snapshot real ou configuração global alterado. Acrescenta consultas de metadata locais; sem benchmark no telefone. Não serializa escritores do estado nem impede alterações concorrentes do mesmo usuário. Cleanup dos fixtures/mutações é automático; logs próprios ficam privados para análise. Escopo documental ampliado somente pelo inventário de leitura da revisão #16; nenhum comportamento adicional fora dos critérios de #26.

Inventário até o commit do código: 75 leituras completas/156 entradas. Os 14 arquivos removidos do baseline foram lidos integralmente; seus substitutos estão nas pastas atuais de scripts, phone, docs e evidência. Cinco movimentos de fonte/prova permaneceram idênticos; monitor substitui o guia visual removido a pedido do operador, demais fontes/resumos tiveram ajustes já rastreados. Essa leitura conclui a pendência das remoções, sem declarar revisão integral das fontes/evidências atuais ou autorizar merge. [Inventário por blob](evidence/pr-review-coverage.json).

Plano da correção atendido; #16 permanece parcial e os gates nativos #2/#8/#12/#13/#21 continuam abertos. Próximo passo: continuar revisão das fontes/evidências atuais enquanto o aparelho não enumera; assim que o USB e o operador estiverem disponíveis, realizar piloto curto da candidata e retorno/rollback. Sem merge/tag/release.

## Revisão de provas e testes — #16/#27

Fase documental de três arquivos: este relatório, inventário e [evidência sanitizada](evidence/review-proof-gates.json). Leitura integral de testes de publicação/perfil/transporte, testes e runners DNS de VM, runners LAN/perfil/agendador, requisitos de lint e receita/evidências de autenticação do kernel. Inventário até `e969654`: 89/157 leituras completas; fontes/evidências atuais ainda têm pendências. Índice binário parcialmente inspecionado, com SHA registrado conferido e parsing limitado em memória: dois streams, três arquivos regulares, 1.039 registros e identidade do kernel selecionado coerente. Não extrai nem executa pacote, não repete assinatura e não contabiliza esse parsing como leitura integral do artefato.

Falha confirmada [#27](https://github.com/djalmajr/iphone6s-linux/issues/27): `run_dns_server_mutations.py` aceita qualquer saída não zero sem skip, incluindo unittest ERROR sem asserção de comportamento. Runner original em cópia descartável, baseline sintético aprovado e processo externo com erro de dependência injetado: saída 0 e `Rejected kernel-bind`. Apenas resultados do subprocesso e pré-condições da plataforma foram simulados; nenhum privilégio, processo de fixture, VM ou rede real. Os resultados físicos anteriores não foram reexecutados nesta inspeção.

Próxima implementação (até cinco arquivos): runner DNS servidor, teste novo do contrato de aceitação, runner de mutações desse contrato, workflow e este plano. Exigir baseline válido e asserção correspondente à mutação; rejeitar ERROR, skip, sucesso e falha de outra regra. Preservar opt-in Linux/root e ambiente descartável. Revalidar gate real na VM própria sem mounts/chaves do projeto, com insumo DNS verificado e dependências já existentes; documentação/resultado em outra fase de até cinco arquivos. #27 permanece aberta, sem implementação neste checkpoint.

CI da documentação anterior `e969654` terminal verde, PR 36840944285/push 36840938621. Código operacional e testes inalterados nesta fase; gates anteriores reutilizados. JSON, vínculo dos blobs e guard público serão conferidos ao publicar; sem typechecker configurado. Nenhum pacote, VM, banco, snapshot, imagem real, identidade ou configuração global alterado. USB continuou sem enumeração; o piloto depende da reconexão já solicitada. Sem merge/tag/release; goal completo ativo.

## Implementação do contrato de prova DNS — #27

Fase de cinco arquivos conforme plano: runner real, oito regressões CLI novas, runner de onze mutações do contrato, step CI e este checkpoint. Baseline exige uma execução aprovada; mutante exige falha de asserção correspondente à regra escolhida. ERROR, skip, código zero, texto sem FAIL e falha de outra regra abortam sem publicar `Rejected`. Opt-in Linux/root preservado. Os testes simulam somente os resultados de processos externos e a plataforma, executando o main real em árvores próprias; não executam namespaces ou comandos privilegiados no Mac.

Oito regressões e 11/11 mutações do contrato passaram localmente. A primeira tentativa do runner novo recusou uma falha válida porque procurava a palavra `skipped` em qualquer linha, incluindo o valor sintético impresso no cabeçalho de subtest. Ajustado para reconhecer `skipped=` no resumo; os onze controles concluíram. O serviço DNS e seu fixture nativo permanecem inalterados.

Revalidação real na VM `iphone6s-build`, sem mounts e sem chaves do projeto: bundle padrão conferido antes de transferência e na VM, SHA-256 `8ccb8f30a1a179b02825bda6040bb51a807b4abbcda24f925028481d5c48e72e`, 4.614.005 bytes. Baseline BusyBox/dnsmasq passou e as cinco mutações reais foram detectadas pela asserção esperada; runner saída 0. Fixture transferido removido, nenhum dnsmasq remanescente ou diretório de mutações, VM devolvida a Stopped/mounts vazios. Sem pacote instalado, alteração de dependência, banco, chave, snapshot, imagem real ou configuração global. Acrescenta validação de relatórios nos testes, sem custo operacional no telefone. Sem typechecker configurado; suíte integral e CI serão registradas no encerramento. Nenhum novo boot do iPhone, merge, tag ou release.

Suíte local: 161 cenários executados, 152 aprovados, oito skips e um erro de bind loopback causado pelo sandbox. Somente `test_dns_lan.py` repetido com autorização de socket: dois aprovados e um skip VM; portanto os 153 cenários locais elegíveis passaram combinando essas execuções, sem repetir gates não afetados. Flake8 fatal, diff-check, sintaxe Bash e ShellCheck do wrapper passaram. CI anterior de `5a54a23` terminal verde: PR 36842691940/push 36842686572. O fechamento de #27 aguarda CI do código novo e publicação da evidência sanitizada. Nenhuma confirmação de USB ou monitor DFU nesta rodada; snapshot DNS e perfil privado da nova cadeia conferidos somente localmente.

## Encerramento da correção — #27

Fonte: plano desta revisão e issue #27; goal geral ativo. Fase documental de cinco arquivos: este relatório, DNS, STATUS, evidência e inventário. Código em `929e962`; oito regressões CLI e 11/11 mutações do verificador aprovadas, baseline real e 5/5 mutações do servidor revalidadas na VM isolada. Suíte local combinada com repetição somente do teste bloqueado pelo sandbox: 153 aprovados/oito skips em 161 cenários. Flake8 fatal, Bash, ShellCheck do wrapper e diff passaram; sem typechecker configurado. Nenhum desvio de escopo operacional; inventário e referências pertencem à revisão #16.

CI terminal verde: [PR 36844496273](https://github.com/djalmajr/iphone6s-linux/actions/runs/36844496273) e [push 36844489224](https://github.com/djalmajr/iphone6s-linux/actions/runs/36844489224). Quatro jobs Ubuntu/macOS, cada um com 161 cenários, 152 aprovados/nove skips e 11/11 mutações do contrato detectadas; logs terminais conferidos. Guard, lint, sintaxe e ShellCheck Linux aprovados. [Evidência sanitizada](evidence/review-proof-gates.json) conserva a reprodução anterior como histórica e distingue testes sintéticos/VM de hardware.

Causa: saída não zero era tratada como rejeição, sem distinguir exceção de infraestrutura de asserção de comportamento. Baseline e mensagens de asserção passaram a integrar o contrato do gate; alterações na fixture exigem atualizar mapa e regressões. VM/fixtures próprios limpos, sem mounts/chaves ou pacote novo. Sem banco, identidade real, snapshot real, payload padrão ou configuração global modificados. Nenhum impacto no desempenho do serviço DNS; apenas validação adicional nos testes. A correção não audita todos os runners nem comprova estabilidade/energia do telefone.

Inventário pinado ao código: 102 leituras completas/160 entradas; nesta rodada foram também lidos integralmente runners de kernel/Pongo/restore/reboot e testes de kernel, formato Pongo e falha de restore. Permanecem pendências, sem parecer integral ou autorização de merge. O aparelho continua sem enumeração USB; pergunta de reconexão da ponta Lightning permanece pendente. Snapshot DNS e perfil da nova cadeia passaram na verificação local, sem boot/restore remoto. Próximo gate físico: candidata kernel/Pongo, snapshot/retorno e rollback Linux com operador; #2/#8/#12/#13/#21 continuam abertas. Sem merge, tag ou release.

## Plano do gate de mutações de recuperação — #28

Reprodução confirmou saída 0 com dois relatórios externos ERROR sem asserções; o runner antigo procura apenas fragmentos de texto e não confere baseline. Fase de implementação de até cinco arquivos: `tests/run_restore_mutations.py`, novo `tests/test_restore_mutation_gate.py`, novo `tests/run_restore_mutation_gate_mutations.py`, workflow e este plano. O serviço de restore e seu fixture nativo permanecem inalterados. Baseline deve executar os dois casos e aprovar; cada mutação executará somente o caso correspondente e exigirá seu cabeçalho FAIL, uma única falha e texto exato da asserção. Rejeitar ERROR, skip, sucesso, outra regra/caso e baseline inválido antes de publicar rejeição. Manter opt-in Linux/root e fontes descartáveis; não interpretar `88` isolado como prova.

- [x] Regressões do main CLI e mutações do contrato, com resultados externos sintéticos, comprovam recusa/aceitação e baseline antes de mutações.
- [x] Revalidar baseline e dois controles reais em VM própria, sem mounts/chaves ou dependências novas; limpar fixtures/montagens próprias e parar VM.
- [x] Lint, suíte local e CI Ubuntu/macOS registrados; evidência sanitizada, documentação e issues em fase posterior de até cinco arquivos.

Decisão: vincular cada caso/asserção ao controle existente, sem criar novos cenários de falha ou alterar o restore real. Alternativa rejeitada: um substring mais longo ainda pode aceitar exceções de infraestrutura. Mensagens da fixture são contrato e deverão ser atualizadas junto dos testes quando mudarem. Nenhuma nova prova no aparelho, merge, tag ou release; reconexão USB continua pendente. CI documental de `20e7fc2` está em acompanhamento pelas execuções já iniciadas 36845182743/36845176763.

Verificação da implementação #28: dez regressões CLI e 13/13 mutações do contrato aprovadas; suíte local 171 cenários, 163 aprovados/oito skips, com permissão somente para o socket loopback dos testes já existentes. Ajuste posterior limitou os parâmetros do helper de teste a um objeto de opções; apenas as dez regressões e treze mutações repetidas, com resultados anteriores não afetados reutilizados. Flake8 fatal/diff aprovados; sem typechecker configurado. Baseline real de dois casos e ambas as mutações passaram na VM, usando apenas fontes públicas com SHA de transferência conferido, num namespace de montagem privado. Restore/fixture nativo inalterados; nenhum pacote instalado, identidade real, snapshot real, imagem real, banco ou configuração global alterados.

A checagem inicial de mounts não executou porque `rg` não existe no guest; não foi contada como prova. Diretórios próprios já haviam sido removidos e a VM parada. Repetida somente a auditoria com `findmnt` e `grep` existentes, incluindo ausência da árvore transferida e dos fixtures próprios: `RESTORE_FIXTURE_CLEANUP_OK`. VM novamente Stopped/mounts vazios. CI documental anterior `20e7fc2` terminou verde, PR 36845182743/push 36845176763; CI do código novo e encerramento documental seguem pendentes. Nenhuma ação USB/DFU no telefone nesta rodada.

## Encerramento da correção — #28

Fonte: plano acima/issue #28, parte de #16/#17; goal geral ativo. Fase documental de cinco arquivos: este relatório, RECUPERACAO, STATUS, evidência e inventário. Código em `3df0956`. Runner real exige baseline de dois casos aprovado, seleciona o caso correspondente e aceita somente sua asserção exata com FAIL e resumo de uma falha. O serviço de restore e o fixture nativo permanecem inalterados; nenhum novo comportamento de recuperação ou custo no telefone. Extra baseline e checks de relatório aumentam somente o custo do verificador.

| Verificação | Resultado |
|---|---|
| Regressões/mutações locais | Dez cenários e 13/13 controles do contrato aprovados; main CLI real, somente processos externos/precondições simulados |
| Suíte local | 171 cenários, 163 aprovados/oito skips; após ajuste do helper de teste, somente dez regressões/treze mutações repetidas e evidência não afetada reutilizada |
| VM real | Baseline de dois casos e 2/2 mutações aprovadas em namespace privado com BusyBox/Bash; fontes públicas conferidas, sem imagens/identidades/snapshots reais |
| Lint/tipos/docs | Flake8 fatal/diff aprovados; CI confirmou sintaxe/ShellCheck Linux. Sem typechecker configurado; receita exige unshare para as montagens da fixture |
| Limpeza | Ausência da árvore transferida, fixtures/mounts próprios confirmada com findmnt/grep; VM Stopped/mounts vazios. A tentativa com rg ausente não foi contada |
| Dependências/banco/compatibilidade | Nenhum pacote/banco/configuração global modificado; exige o mesmo opt-in Linux/root e preserva saída final de sucesso |
| Limites | Relatórios/nome do caso integram o contrato. Não acrescenta atomicidade/concurrency ao restore nem prova hardware/energia/retorno ao iOS |

CI terminal verde: [PR 36846983347](https://github.com/djalmajr/iphone6s-linux/actions/runs/36846983347) e [push 36846977041](https://github.com/djalmajr/iphone6s-linux/actions/runs/36846977041). Quatro jobs Ubuntu/macOS com 171 cenários cada, 162 aprovados/nove skips e 13/13 mutações do novo gate detectadas; logs terminais conferidos. Guard/lint/sintaxe/ShellCheck Linux passaram. [Evidência sanitizada](evidence/restore-proof-gates.json) registra reprodução anterior, prova atual e recuperação da checagem de cleanup.

Causa: um fragmento de texto era tratado como detecção, sem baseline ou vínculo com a asserção/caso. O contrato agora exige ambos e as regressões reproduzem o erro sem privilégio real no Mac. Nenhum desvio de escopo operacional; inventário/referências atendem à revisão #16. Checkpoint pinado ao código: 108 leituras completas/162 entradas, todos os testes/runners lidos; documentos/evidências atuais ainda têm pendências, sem parecer integral. #16 continua parcial e nenhum merge/tag/release foi feito. Próximo passo: continuar documentos/evidências e realizar candidata/retorno/rollback quando USB e operador estiverem disponíveis. A orientação de reconexão permanece pendente; não houve DFU nem ação no telefone nesta rodada.

## Revisão documental do estado do DNS — #16

Contexto: o checklist de EXECUCAO ainda apresentava #7 aberta e o checklist DNS deixava a limpeza pendente. Leitura integral da documentação DNS/execução, do registro físico e confirmação GitHub: #7 encerrada em 2026-10-01T01:02:28Z, snapshot com 41 entradas, daemon/proxies próprios encerrados e retorno ao iOS confirmado. A causalidade exclusiva do reboot por software não foi comprovada e permanece na #21. Atualizar somente a conclusão já demonstrada; o novo kernel/Pongo ainda não deu boot físico.

Fase de cinco arquivos: DNS, EXECUCAO, este relatório, STATUS e inventário por blob. Corrigir os dois checklists, distinguir histórico de estado atual e registrar as leituras completas desta rodada. Decisão: conservar os checkpoints anteriores com uma orientação explícita de leitura. Alternativa: reescrever todos os estados anteriores apagaria a cronologia necessária à reprodução/análise. Reversão de baixo custo, somente documentação.

- [x] Ler os dois READMEs, os dois gitignores, DNS, EXECUCAO, KERNEL-INTEGRATION, REBOOT e registros físicos DNS/restore; sem contabilizar trechos truncados como leitura completa.
- [x] Confirmar #7 encerrada e CI documental de `460315b` terminal verde: [PR 36847873931](https://github.com/djalmajr/iphone6s-linux/actions/runs/36847873931) e [push 36847867083](https://github.com/djalmajr/iphone6s-linux/actions/runs/36847867083), quatro jobs Ubuntu/macOS aprovados.
- [x] Verificar JSON/blobs/links, sintaxe dos blocos de operação, diff e guard do índice antes de publicar; registrar encerramento e limites.

O inventário anterior foi corretamente pinado ao commit de código `3df0956`; a evidência restore adicionada no commit documental posterior entra no novo checkpoint `460315b`. Usar diff sem detecção de renames para contabilizar fontes removidas e destinos separadamente. Leitura não é parecer de auditoria; #16 permanece parcial e não autoriza merge. Nenhum teste de código, VM ou build precisa ser repetido nesta alteração documental: seus inputs não mudaram. Nenhum typechecker configurado, pacote instalado no Mac, banco/configuração global alterados ou ação no aparelho. A reconexão USB já solicitada ainda é necessária para o piloto da nova cadeia.

Encerramento desta fase documental: cinco arquivos atualizados; 118 leituras completas/163 entradas no checkpoint `460315b`, sem parecer integral. JSON, contagem e todos os blobs conferidos, 49 links locais válidos e oito blocos Bash/sh passaram por `bash -n`; diff-check e guard público do índice aprovados. Gates de código/VM não afetados reutilizados, CI documental anterior confirmada nos quatro jobs; o novo commit terá sua própria CI automática. Não há mudança de compatibilidade ou desempenho do servidor. O USB continua sem iPhone/Recovery/DFU/Pongo detectado; o monitor não foi iniciado. Próximos passos: documentos/evidências restantes e piloto físico quando a reconexão solicitada permitir. Goal ativo, sem merge/tag/release.

## Plano do início Herdr sem nohup — #29

A candidata contém BusyBox com SHA `52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933`, sem applet nohup e com setsid. Somente esse executável, conferido, foi extraído do initramfs e copiado à VM; não foi executado no Mac. O launcher original, com fontes públicas e peer Bash sintético no PATH limitado aos applets reais, falhou por uma asserção de startup, sem ERROR. A VM anterior usava nohup do guest e não capturava essa dependência ausente. A primeira consulta com argv[0] `phone-busybox` terminou 127; não foi aceita. Repetição estreita com argv[0] `busybox` confirmou os applets.

Fase de cinco arquivos: helper Herdr, teste existente, runner novo de mutações, CI e este plano. Substituir nohup por disposição HUP ignorada no filho antes de exec/setsid; manter redireções e sessão/lock/hash/SSH. Regressão com PATH sem nohup e sinal HUP real no peer. Runner exige baseline aprovado e falha de asserção do caso de startup para ambas as mutações; não aceita ERROR/skip. Não instalar coreutils nem reconstruir a imagem para acrescentar um utilitário.

- [x] Validar regressão, duas mutações, demais contratos Herdr e Bash/ShellCheck/lint; sem typechecker configurado.
- [x] Revalidar servidor Herdr oficial com Bash e applets reais da candidata na VM isolada; reconexão/restart/marker, sem chaves ou dados reais.
- [x] Publicar código e observar CI; atualizar evidência/docs/status/inventário em fase posterior de até cinco arquivos e remover fixtures/processos próprios, devolvendo VM a Stopped/mounts vazios.

Decisão: setsid e HUP herdado no filho dispensam dependência inexistente; incluir nohup/coreutils ampliaria o runtime e exigiria rebuild. Reversão de baixo custo, sem formato persistente novo. A prova VM não conclui boot/reconexão física/TUI #13, alimentação #2, estabilidade #8 ou retorno/rollback #12/#21. USB ausente; nenhum monitor iniciado.

Verificação da implementação: 12 testes Herdr passaram, incluindo startup com PATH sem nohup e SIGHUP real enviado pelo peer antes de confirmar prontidão. As duas mutações foram recusadas pela asserção desse caso; baseline aprovado, fontes temporárias descartadas. Flake8 fatal, sete scripts gerados em Bash/ShellCheck e diff-check passaram. Nenhum typechecker configurado.

Na VM, Herdr oficial `f4ccf4de...` iniciou com o PATH dos applets reais da candidata: Bash 5.2, mesmo painel entre clientes CLI separados, restart e novo namespace volátil recriado pelo marcador passaram. Esse teste usa Bash/bibliotecas do guest e não executa o initramfs completo, SSH/TUI ou hardware. Sessão própria parada; ausência de processos com cwd da fixture confirmada, árvore de transferência removida e VM devolvida a Stopped/mounts vazios. Nenhum pacote/identidade/snapshot real/banco/configuração global alterado. CI documental anterior `6ebe3fd` terminou verde nos quatro jobs, PR 36849274738/push 36849269579; CI desta implementação e fase documental seguem pendentes.

Suíte integral local: 172 cenários, 164 aprovados/oito skips explícitos em 112,909 s; permissão de sockets somente para fixtures loopback existentes. Sem erro ou repetição da suíte. CI sintética executará também as duas mutações novas nas duas plataformas; gates históricos não afetados permanecem válidos enquanto seus inputs não mudarem. Custo operacional: mesmo servidor/session e um processo destacado, sem dependência nohup; não foi feita medição de desempenho no telefone.

## Encerramento da correção — #29

Escopo de cinco arquivos: HERDR, STATUS, este relatório, evidência de detachment e inventário. Atualizar requisitos/runtime e conservar a prova inicial como histórica; registrar reprodução, erro da primeira consulta multicall, resultados locais/VM e CI só depois dos jobs terminais. O checkpoint de leitura inclui nove documentos adicionais de hardware/boot/Herdr/console/organização/CI e a evidência inicial Herdr, além do runner novo, vinculados a seus blobs. As inspeções não substituem o piloto físico nem provam ausência de falhas no restante da PR.

- [x] Confirmar CI do código `d5e4597`, atualizar o resultado e verificar JSON/blobs/links/sintaxe/diff/guard antes de publicar.
- [x] Publicar os cinco documentos e atualizar #29/#13/#16/#17, mantendo os critérios físicos pendentes.

Plano atendido: launcher sem nohup, teste público de HUP real, runner com duas mutações e workflow publicados em `d5e4597`; fase documental de cinco arquivos conserva a evidência inicial como histórica. Nova [evidência sanitizada](evidence/herdr-detachment.json) registra reprodução, erro inicial de argv[0] e limites dos testes. Quebra de compatibilidade: remove dependência ausente, sem formato de marcador/configuração novo. Nenhum banco, pacote no Mac/guest, chave, snapshot/imagem real ou configuração global alterados; scripts/testes adicionam validação, sem custo de serviço medido no telefone.

Verificação local: 12 testes Herdr e 2/2 mutações aprovados; suíte 172 casos, 164 aprovados/oito skips; sete scripts Bash/ShellCheck, Flake8 fatal, YAML e diff aprovados. Sem typechecker configurado. VM com BusyBox da candidata e Herdr oficial aprovou Bash, clientes CLI separados/idempotência, restart e marcador; fixture/processos próprios removidos e VM Stopped/mounts vazios. Não é chroot/boot completo do initramfs, SSH/TUI ou hardware.

CI terminal verde: [PR 36851283400](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851283400) e [push 36851277105](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851277105). Logs dos quatro jobs conferidos: 172 casos, 163 aprovados/nove skips e ambas as mutações de detachment detectadas em cada job. Guard/lint/sintaxe/ShellCheck Linux aprovados. Não repetimos gates de código/VM para a mudança documental; JSON/blobs, 31 links locais e quatro blocos Bash/sh verificados, diff e guard do índice aprovados.

Causa: a fixture VM original herdava utilitários do guest e ocultava um applet ausente do telefone. A nova regressão restringe PATH e testa o sinal antes de aceitar startup. Inventário pinado ao código `d5e4597`: 129 leituras completas/164 entradas, todos os testes/runners do checkpoint lidos; a evidência nova pertence à fase documental posterior. #16 permanece parcial, sem parecer integral ou merge/tag/release. #13 e #2/#8/#12/#21 mantêm os gates físicos; o USB continua sem enumeração, aguardando a reconexão já solicitada. Goal completo ativo.

## Alinhamento da reprodução e leitura documental — #16

Plano desta fase (quatro arquivos): FRESH-BUILD, STATUS, este relatório e inventário. Atualizar o checklist da imagem 7.0.12 a partir dos dois pilotos já registrados, preservar o JSON histórico da etapa VM e separar esses resultados do kernel 7.2.0/Pongo ainda sem boot físico. Acrescentar ao inventário as leituras completas de FRESH-BUILD, PROFILES, M1N1-BUILD, KERNEL-SOURCE-BUILD, proveniência fresh-build, integração do kernel e detachment Herdr, pinadas aos blobs do checkpoint `4813667`.

- [x] Conferir que a candidata fresh-build preservada corresponde ao manifesto: 23.767.750 bytes, SHA-256 `274e632b599ba94efc3b6512402ee15762232a9a34e679d034afd0c04eebf496`; `device_profile.py check` passou sem ação USB/remota.
- [x] Confirmar CI documental de `4813667`: [PR 36852084064](https://github.com/djalmajr/iphone6s-linux/actions/runs/36852084064) e [push 36852076654](https://github.com/djalmajr/iphone6s-linux/actions/runs/36852076654), quatro jobs terminais aprovados.
- [x] Conferir JSON/blobs, links, sintaxe dos blocos documentais e diff. Publicação e atualização #16/#17 seguem o guard público do índice.

Decisão: preservar a cronologia da construção e indicar o avanço posterior no topo/checklist/conclusão. Reescrever o JSON histórico como prova física apagaria seu alcance original; deixar o checklist desatualizado orientaria uma repetição desnecessária do piloto antigo. Reversão de baixo custo, apenas documentação. Sem alteração de código, dependências, banco, desempenho ou configuração global; nenhum typechecker configurado. Gates locais/VM/CI de código inalterado permanecem válidos. Nenhum novo boot iniciado nesta rodada: USB ainda sem enumeração e reconexão já solicitada permanece necessária.

Encerramento local: quatro arquivos documentais atualizados; inventário parcial 136/165 no checkpoint `4813667`, todas as contagens/blobs conferidas. 35 links locais, sete blocos Bash/sh e um bloco Python passaram nas verificações de existência/sintaxe; diff-check aprovado. A cobertura não declara auditoria integral. Nenhum teste de código, VM ou build repetido para esta mudança de texto; CI anterior terminal aprovada, nova revisão sujeita à CI automática. O próximo gate físico é a cadeia 7.2.0/Pongo e rollback; repetir somente o piloto DNS anterior não atende esse gate. Goal ativo, sem merge/tag/release.

## Exemplo de recuperação e evidências restantes — #16

Plano desta fase (quatro arquivos): PERSISTENCIA, STATUS, este relatório e inventário. Corrigir o exemplo de restore interrompido e vincular 14 leituras completas adicionais aos blobs de `9ab24fe`: PERSISTENCIA, PONGO-SOURCE-BUILD e registros autosnap-state-paths, boot-tools-check, compose-output-paths, local-snapshot-paths, kernel-source-build, pongo-source-build, storage-boot-n71, persistence-check, restore-failure-check, linux-boot-proof, linux-http-proof e console-cold-boot. Preservar os resultados históricos e seus limites de VM/hardware.

O bloco original `restore <ID-pre-restore>` falhou em `bash -n` com saída 2, pois os sinais angulares são redirecionamentos na sintaxe do shell. O exemplo agora atribui um ID ilustrativo a `restore_before_id` e passa seu valor entre aspas; o comentário exige substituir pelo ID anterior mostrado pela ferramenta. O CLI não mudou, e o exemplo não foi executado contra snapshots reais.

Decisão: usar variável explícita no bloco copiável. Um placeholder entre aspas seria sintaticamente válido, mas continuaria passando literalmente um ID inválido; um texto fora do bloco ocultaria o comando completo. Reversão de baixo custo, somente documentação. Verificação prevista: sintaxe/links, JSON/blobs, diff e guard público; gates de código/VM inalterados reutilizados, sem novo teste ou instalação. Próximo piloto físico continua dependente da conexão USB já solicitada.

Encerramento local: quatro documentos atualizados, inventário parcial 150/165 no checkpoint `9ab24fe`; contagens e blobs conferidos. 35 links locais e o bloco Bash de persistência passaram nas verificações; `git diff --check` aprovado. Falha do exemplo original preservada no relatório. Não há mudança de compatibilidade, banco, dependência ou desempenho; nenhum typechecker configurado. Publicação segue guard do índice e atualização #16/#17. CI de `9ab24fe` confirmada terminal verde nos quatro jobs: [PR 36853331115](https://github.com/djalmajr/iphone6s-linux/actions/runs/36853331115) e [push 36853325277](https://github.com/djalmajr/iphone6s-linux/actions/runs/36853325277). Nenhum novo boot/monitor do telefone.

## Operação atual e conclusão da leitura textual — #16

Plano desta fase (cinco arquivos): REDE, REPRODUCAO, STATUS, este relatório e inventário. Identificar histórico versus estado atual em REDE, corrigir as afirmações desatualizadas de DNS ainda não instalado/LAN inexistente e o nome/procedimento Herdr antigo no guia principal; registrar as VMs adicionais de kernel/Pongo. O launcher atual fixa `iphone-server` e oferece `start`/`attach`, conforme fonte conferida. Não converter provas históricas Herdr em piloto físico da candidata atual.

Leituras completas adicionais: REDE, REPRODUCAO, artifacts.json e registros autosnapshot-check, dns-bundle-scope, dns-check, dns-provenance, dns-rebuild-provenance, lan-check, m1n1-rebuild, m1n1-source-provenance, power-check e wifi-n71-path. O inventário por blob será pinado a `7a067cf`. O arquivo de cobertura e o índice APK binário conservam ausência de leitura textual completa; conferência programática de schema/blobs ou estrutura/hash não é leitura integral nem parecer de auditoria.

Decisão: corrigir o guia operacional e identificar a cronologia sem reescrever evidências históricas. Reescrever logs apagaria a sequência das falhas/resultados; repetir DNS/LAN fisicamente só para corrigir texto não atenderia os gates atuais. Reversão de baixo custo, apenas documentação. Verificação prevista: JSON/blobs/contagens, links, sintaxe de comandos, diff e guard público; código/builds/VM inalterados não serão repetidos, sem typechecker configurado. Nenhum novo boot/monitor ou alteração de rede global.

Encerramento local desta fase: cinco arquivos documentais atualizados; inventário parcial 163/165 no checkpoint `7a067cf`, com todas as contagens e blobs conferidos. 59 links locais e 20 blocos Bash/sh passaram nas verificações; diff-check aprovado. Os 20 artefatos privados do manifesto foram lidos somente para conferir tamanho/SHA-256 e todos corresponderam, sem substituição ou execução. Nenhum typechecker configurado; nenhum teste/build/VM de código inalterado repetido. Sem mudança de banco, dependência, desempenho ou rede global; instruções atuais alinhadas sem alegar novo piloto da candidata.

CI documental de `7a067cf` terminal verde: [PR 36853966381](https://github.com/djalmajr/iphone6s-linux/actions/runs/36853966381) e [push 36853958825](https://github.com/djalmajr/iphone6s-linux/actions/runs/36853958825), quatro jobs macOS/Ubuntu. Publicação segue guard do índice; revisão nova terá CI própria. #16 continua aberta por seu escopo completo, incluindo integração autorizada; leitura não substitui auditoria exaustiva, gates físicos ou merge. USB ainda sem enumeração nesta rodada, monitor não iniciado; goal ativo.

## Fechamento do inventário e ação independente no Windows — #16/#20

Plano desta fase (quatro arquivos): inventário, STATUS, este relatório e novo DNS-WINDOWS. Ler integralmente o JSON de cobertura, verificar separadamente o índice binário sem confundir parsing com leitura textual e registrar um plano/diagnóstico Windows independente do USB. A leitura de todos os textos está pinada a `8b44b24`: 164/165 entradas; somente o índice binário conserva `read_complete=false`. O plano Windows criado nesta fase pertence à revisão documental posterior, fora desse checkpoint.

Índice inteiro conferido por parsing limitado: 106.022 bytes, dois streams gzip e membros regulares únicos (`.SIGN.RSA.build.postmarketos.org.rsa.pub`, `DESCRIPTION`, `APKINDEX`). Todos os 1.039 registros tiveram formato/campos conferidos; entrada do kernel corresponde ao manifesto público. Hash do índice e da chave pública canônica conferidos; assinatura RSA/SHA-1 válida (saída 0), cópia com bit alterado rejeitada (saída 1). Resultado sanitizado no campo `binary_review` do inventário. Nenhum conteúdo de pacote executado/instalado; assinatura própria do APK e commit `-dirty` continuam lacunas distintas. Arquivo original preservado.

CI de `8b44b24` terminal verde: [PR 36854725212](https://github.com/djalmajr/iphone6s-linux/actions/runs/36854725212) e [push 36854719847](https://github.com/djalmajr/iphone6s-linux/actions/runs/36854719847), quatro jobs. Código/builds/VM inalterados não foram repetidos; sem typechecker configurado. USB permanece sem enumeração, mas há ação independente disponível na #20: workspace Windows dedicado acessível, nslookup Microsoft assinado/versionado e configuração efetiva conferida com stdin fechado/prazo de 15 s. [Plano, parâmetros e limites](DNS-WINDOWS.md). Não é prova de DNS na LAN ou novo boot; nenhum agente, pacote, política ou DNS global alterados.

Decisão: continuar o diagnóstico de cliente em fixture antes de trocar helper/parser. Repetir DFU com USB ausente não fornece prova nova; inferir defeito do nslookup a partir de timeout antigo também não. Reversão baixa, comandos próprios finitos, sem listener/configuração global. Próximas fases: fixture UDP/TCP comparando transporte e controles negativos, enquanto os gates físicos continuam pendentes. Goal ativo; sem merge/tag/release.

Encerramento local: quatro documentos preparados, inventário 164/165 no checkpoint `8b44b24`, contagens/todos os blobs conferidos; 31 links locais válidos e diff-check aprovado. Registro do índice distingue assinatura/parsing de leitura textual. Diagnóstico Windows real confirmou assinatura Microsoft, versão/hash, opções efetivas e término dentro de 15 s, sem stdout pessoal publicado; não é resposta DNS nem hardware. Nenhum código/helper operacional alterado, teste/build/VM inalterado repetido, pacote/banco/configuração global modificados ou typechecker configurado. Impacto do diagnóstico limitado ao processo próprio finito; nenhum serviço permanente criado. Publicação segue guard público do índice; nova CI acompanhará a revisão documental. Próximos passos: fixture de cliente #20 e piloto físico somente quando o USB reaparecer.

## Reprodução do cliente DNS Windows — #20

Fase documental de quatro arquivos: DNS-WINDOWS, STATUS, este relatório e nova evidência `windows-dns-fixture.json`. Seguido o plano aprovado de comparação antes de trocar o helper. Assinatura/hash Microsoft reconferidos; fixture própria finita em bind privado/ACL explícitos, sem upstream/recursão ou mudança global. Resultados Windows nativos separados das provas físicas históricas do iPhone.

Oito casos nslookup reais (argumentos e stdin, UDP/TCP em 15953/1053) na passagem final terminaram dentro do prazo, saída 0; nenhum apresentou nome/endereço esperado ou chegou ao servidor. Interativo mostrou a porta selecionada. A captura original não contava recusas ACL; os casos e seis controles foram repetidos após acrescentar essa contagem. Passagem final sem recusas ACL ou erros; 16 processos nativos no total, todos terminados. Quatro consultas sockets .NET nos mesmos destinos receberam a resposta sintética completa de 54 bytes; fixture registrou os quatro pacotes e dois controles Mac dig, sem erros. Timeout UDP/erro não especificado TCP do cliente não foram aceitos como sucesso nem como prova da causa subjacente. A submissão multilinha inicial falhou no parser antes da consulta; fonte foi repetida em transporte de uma linha com parser PowerShell nativo aprovado.

Decisão D2 em DNS-WINDOWS: comparar fixture em loopback Windows antes de escolher uma correção ou outro cliente com parser completo. Não inferir defeito do aparelho/proxy nem desabilitar proteções. O helper operacional permanece inalterado; controles negativos completos e teste Windows após novo boot/restore continuam pendentes. Nenhum código de serviço, pacote, política, configuração global, banco ou chave alterados; sem typechecker configurado. Testes/gates de código inalterado reutilizados; Flake8 fatal da fixture privada passou.

Limpeza: processo próprio da fixture terminou com saída 0/marcador; listeners TCP/UDP 15953/1053 ausentes, todos os processos nslookup terminados e liberados; nenhum servidor/arquivo novo no Windows. Fontes/logs/resultados ficam na pasta privada ignorada para reprodução. CI de `548094c` confirmou PR 36856892546/push 36856886716 terminais verdes; esta fase terá CI própria. USB ainda sem iPhone/Recovery/DFU/Pongo, monitor não iniciado; reconexão solicitada ao operador antes do próximo piloto kernel/Pongo. Goal ativo, sem merge/tag/release ou conclusão da revisão #16.


## Controle Windows local e decisão de cliente — #20

Fase de quatro documentos: DNS-WINDOWS, STATUS, evidência Windows e este relatório. Comparação D2 executada no próprio Windows: fixture C# autoral compilada pelo Add-Type/.NET existente, binds loopback TCP/UDP 15953/1053 e quatro threads próprias com prazo 120 s. Parser PowerShell/compilação C# passaram; fonte/resultados privados preservados. Oito casos nslookup assinado/hash conferido falharam por argumentos/stdin, saída 0/prazo cumprido, sem resposta ou eventos da fixture; interativo confirmou portas e informou domínio inexistente. Quatro controles sockets compararam integralmente 54 bytes e geraram os únicos quatro eventos.

Dispose fechou sockets/aguardou threads; zero listeners nas portas, marcador final e prompt do painel confirmados. Nenhum pacote/ferramenta instalado, política/proteção/DNS/firewall ou serviço remoto alterado. Compilador pode usar temporários gerenciados pelo .NET; assembly autoral permanece em memória da sessão PowerShell, não é instalação. Código operacional ainda inalterado; testes/mutações do cliente final não foram executados nesta rodada. Nenhum teste de código Mac/VM repetido, seus inputs permanecem iguais.

Decisão D3/contrato em DNS-WINDOWS: implementar cliente de sockets completo e limitado para consultas explícitas A/IN/home.arpa, preservando parâmetros/validação do destino/marcadores, com parser de todas as seções e controles negativos/mutações reais. Fase de até cinco fontes/testes/plano; CI Windows/documentação em fase posterior. Diagnóstico limitado não será promovido a cliente final. Causa específica da falha nativa desconhecida; reprodução LAN/loopback não exige alteração global para escolher a alternativa prevista na #20. Primeiro critério da issue cumprido (reprodução/flags/porta/caminho); helper/negativos/piloto físico continuam abertos.

CI de 433ea04 observada terminal verde nos quatro jobs: PR 36859266727/push 36859260870. Novos documentos terão CI própria. USB ainda sem enumeração de iPhone/Recovery/DFU/Pongo; monitor não iniciado e pergunta de reconexão permanece pendente. Goal ativo, sem merge/tag/release, sem fechar #20/#16 ou os gates de energia/estabilidade/boot da candidata.


## Cliente DNS Windows e CI nativo — #20

Fase 1 concluída em `e3de2d6`, exatamente os cinco arquivos de D3: helper PowerShell, cliente C#, fixture C#, runner e DNS-WINDOWS. Parser/compilação nativos passaram no Windows 5.1; baseline final de 61 casos e 18 mutações reais rejeitadas por asserção, saída 0. O primeiro descritor private-range falhou por compilação e não contou; somente esse caso foi corrigido/repetido primeiro, e o runner final gerou log completo para conservar a prova. Nove invocações do CLI público: dois positivos com UDP/TCP 1053/15953 e sete negativos pelo motivo esperado, sem marcador de sucesso. A fixture LAN recebeu quatro perguntas válidas e terminou com saída 0; zero listeners nas portas. Não é prova física do iPhone.

Fase 2 segue o plano de cinco arquivos: workflow CI, DNS, STATUS, este relatório e evidência Windows. Job Windows isolado executa parser/compilação, transportes reais sintéticos e mutações da fonte; jobs Ubuntu/macOS permanecem. Parâmetros/marcadores preservados; o helper exige a fonte C# ao lado do script e sessão nova quando o hash carregado divergir. Tipos DNS não suportados são recusados; cliente não é resolvedor geral e não muda o DNS do sistema. Nenhum pacote instalado, banco/identidade/configuração global alterado. Compilador .NET pode usar temporários próprios.

Provas de código/builds Mac/VM não afetadas são reutilizadas. Tipagem/sintaxe desta fase: compilação C# e parser PowerShell reais; diff/JSON/links/guard antes de publicar. CI documental de `3a99178` terminal verde nos quatro jobs, PR 36861671697/push 36861666541. CI do novo job ainda não observada. Logs/fontes/endereço real ficam privados em `runtime/windows-dns-client-20261001/`; cleanup exato do diretório conhecido Windows confirmado: cinco arquivos removidos, diretório ausente e variável própria removida. Não foi adivinhada/removida a pasta vazia da transferência inicial. Próximos gates: CI e piloto físico após reconexão USB. Goal ativo, sem merge/tag/release ou fechamento #20.


## Fechamento do cliente Windows — 49d8747

CI correspondente à implementação publicada terminou verde nos seis jobs: [PR 36867261810](https://github.com/djalmajr/iphone6s-linux/actions/runs/36867261810), [push 36867254184](https://github.com/djalmajr/iphone6s-linux/actions/runs/36867254184). Windows executou o novo runner; Ubuntu/macOS conservaram seus gates. Resultado local real: 61 casos, 18 mutações por asserção, dois positivos CLI e sete negativos. Tipagem/sintaxe C#/PowerShell aprovadas; JSON/40 links/diff/guard público aprovados. Sem pacote/banco/configuração global alterado. O helper exige fonte C# ao lado do script e recusa assembly antiga. Impacto limitado a consultas explícitas de até 3 s/protocolo, sem fallback, cache ou recursão.

Inventário atualizado por leitura integral das cinco adições e diffs próprios: 169/170 entradas pinadas a `49d8747`; todos os textos completos e índice binário ainda separado. Blobs removidos conferidos na baseline, presentes no head; `complete_pr_review=false` preservado. Este fechamento documental é posterior ao checkpoint e não declara revisão integral ou prova nativa da candidata. Limpeza do diretório Windows conhecido confirmada; pasta vazia inicial não identificada preservada. #20 mantém aberto o piloto após boot/DNS restore, USB segue ausente e nenhum monitor/DFU foi lançado. Goal ativo; energia/estabilidade/novo kernel/Pongo/rollback/Herdr/hardware e integração continuam seus gates próprios.


## Preflight da porta DNS padrão — #19

Fase de cinco documentos: DNS-STANDARD, evidência dns-standard-port, DNS, STATUS e este fechamento. Plano/decisões precederam a medição de bind. Kernel Mac: sete endpoints TCP e sete UDP 53, incluindo loopback/privado; lsof não root vazio não foi aceito como porta livre. Classificação inicial falhou com IPv6 truncado; -W também não resolveu, e esses quatro registros foram marcados desconhecidos. IPv4 do teste LAN anterior ainda atribuído ao host e sem endpoint exato/wildcard observado; UDP e TCP 53 recusados com EACCES ao processo não root. TCP somente foi medido depois da falha UDP, sem repetir o caso já observado. Zero tráfego/listen TCP/reuse; sockets fechados e zero endpoints no bind escolhido ao final.

Decisões: conservar servidor não recursivo e planejar split DNS somente para FQDNs próprios; no Android, Private DNS por hostname exige DoT ausente no serviço atual. Abrir 53 exigirá helper mínimo de sockets, abandono de privilégios e entrega/validação de FDs ao runtime usuário, em fase posterior. Não iniciar proxy/SSH inteiro como root, alterar serviço existente, instalar pacote ou mudar DNS/PF/sudoers/roteador. Nenhuma regra aplicada; disponibilidade/política real e rollback ainda não testados. A leitura/bind negativo é preflight nativo Mac, não DNS funcional ou prova do iPhone.

CI documental de 35aca7d terminal verde: PR 36868359316/push 36868353330, seis jobs. Testes/compilação de código operacional não alterado continuam válidos; não foram repetidos localmente. JSON/links/diff/guard antes de publicar. Logs/endpoints reais ficam ignorados em runtime/dns-standard-port-20261001. Nenhum banco/dependência alterado; sem impacto persistente. #19 e goal permanecem abertos; próximo passo é implementação testável do bootstrap e piloto nativo acompanhado. USB do iPhone continua sem enumeração, sem monitor/DFU lançado.


## Bootstrap e integração DNS53 — preparação #19

Quatro fases versionadas, cada uma com cinco arquivos: bootstrap `6a03a0c`, modo explícito `a173be4`, correção TCP `770f710` e gates `98e6384`. Porta1053 conserva default; `--standard-port` seleciona53 e exige LAN privada/runtime usuário. Helper stdlib em Python de sistema isolado abre somente sockets, remove grupos/GID/UID antes do IPC e termina; proxy/SSH/chaves permanecem no processo usuário. Sem helper root Mac, pacote novo, sudoers/PF/firewall/política cliente ou alteração do telefone.

Mac: 21 casos IPC reais/15 mutações por asserção, incluindo Python nativo3.9. VM Ubuntu24.04 ARM64: 25 casos/19 mutações bootstrap, baseline DNS/SSH de quatro testes cobrindo modos alto/53 e oito mutações do proxy. Bind/ACL/capacidade/identidade/limites, conflitos UDP/TCP/forward, trust, rebind e cleanup foram exercitados em namespaces/chroots próprios. Compilação/Flake8 fatal, parser YAML, diff/guard público aprovados; sem typechecker configurado.

Falhas tratadas: Darwin SO_ACCEPTCONN substituído por TCP_CONNECTION_INFO; buffer pequeno de ancillary revelou FD excedente perdido, reserva ampliada ao limite XNU e casos até65 FDs passaram; timeout nativo normalizado. Integração inicial falhou com TIME_WAIT; TCP recebe reuseaddr e regressão confirma rebind sem reuseport, preservando listener existente. Darwin lê reuseaddr como bitmask, normalizado para booleano. Mutação isolada de tipo foi mascarada pela política de reuse e não contou; mutação real do bloco de política foi rejeitada por asserção. Nenhum erro/skip/compilação ou falha de infraestrutura foi promovido a aprovação.

Zero processos DNS/SSH e diretórios de fixtures restantes; VM do projeto parada, fontes de reprodução próprias preservadas. CI inicial `6a03a0c`: PR36930558070/push36930548792, terminais verdes. CI do código final `98e6384`: PR36932840328/push36932841357 terminais verdes em Windows/Ubuntu/macOS. Logs confirmaram baseline e 15 mutações por asserção nas duas plataformas de fonte. Índice da revisão integral continua pinado a49d8747 (169/170); novas fases foram lidas no escopo próprio, sem declarar full review ou fechar #16.

Próximos gates: reconexão USB, piloto curto da candidata/restoreDNS, refresh de bind/conflitos e privilege drop Mac acompanhado, cliente Windows com seleção53, Android e splitDNS/rollback. Helper Windows atual só aceita portas altas. #19/goal continuam pendentes de hardware/clientes; nenhum merge/tag/release. [Contrato, receitas e decisões](DNS-STANDARD.md), [evidência sanitizada](evidence/dns-standard-port.json).


## Cadeia compilada — piloto nativo e correção do retorno

Cadeia Pongo/kernel de fonte iniciou no iPhone N71. Wrapper saída0, restore exato de três arquivos DNS, SSH/páginas16kB/Bash/HTTP, console confirmado e DNS USB UDP/TCP5353 aprovados. Driver apple-watchdog vinculado; snapshot antes do pedido e retorno ao iOS USB confirmados, com operador afirmando ausência de botões. CLI antigo saiu1 por confirmação de sync perdida, sem converter isso em sucesso do comando. Comparação100→93% em iOS não valida carga sustentada. Wi-Fi/storage/sensores continuam sem caminho operacional observado.

Correção20695eb separa sync/reboot, exige sync0/marcador sem timeout antes de enviar reboot e continua exigindo USB/modelo/ausência Linux. Regressão nova falhou por assertion antes da correção; baseline19 e11 mutações passaram, lint/AST/links/diff/guard aprovados. Novo CLI ainda sem piloto/CI registrados. Cinco arquivos de código/testes/documentação lidos neste escopo; o inventário integral permanece no checkpoint49d8747 e complete_pr_review=false. [Procedimento](SOURCE-CHAIN-PILOT.md), [registro sanitizado](evidence/source-chain-pilot.json). Nenhum merge/tag/release, pacote no Mac, mudança global de rede ou escrita em NAND.


### Fechamento nativo do CLI de retorno

Segundo boot da mesma cadeia de fonte com restore: wrapper0 e console/SSH/HTTP confirmados. Novo CLI em6386b2b publicou BACKUP_VERIFIED e SYNC_VERIFIED, pediu reboot separado e retornou RETURN_IOS_VERIFIED com saída0: iPhone8,1 USB e ausência do gadget Linux. Nenhuma intervenção física solicitada. Bateria96→94%, sem concluir carga sustentada. CI PR36940701485/push36940697946 terminal verde, três plataformas. Os cinco documentos deste fechamento tiveram JSON/links/diff/guard conferidos; código não alterado. #21 cumpre o gate da cadeia de fonte, enquanto #12 rollback e #16 revisão integral/merge permanecem separados; complete_pr_review=false.


### Rollback nativo após a cadeia de fonte

Pongo/payload conhecidos com hashes preservados e snapshot final verificado. Boot padrão sem seleção explícita terminou0; console/SSH estrito/kernel7.0.12/HTTP e comparação exata de três arquivos DNS aprovados. Snapshot/sync/retorno pelo CLI corrigido terminou0 com iPhone8,1 USB e ausência Linux. Bateria96→100%, sem liberar #2/#8. Cinco documentos desta fase têm JSON/links/diff/guard conferidos; código inalterado, evidência de CI6386b2b reutilizada. Rollback físico cumpriu o critério da #12, que conserva proveniência limitada do legado APK/Pongo; revisão integral/merge #16 continuam pendentes e complete_pr_review=false.


## Herdr — dois pilotos físicos #13

Fase de cinco documentos previamente planejada: HERDR, evidence/herdr-physical.json, STATUS, EXECUCAO e este relatório. Cadeia compilada/kernel7.2 iniciou duas vezes com wrapper0/SSH/HTTP/console. Primeiro enable iniciou sessão própria; Bash gravou arquivo e TUI exibiu marcador. Desconexão/reconexão pelos clientes próprios conservou painel/terminal, start repetido confirmou servidor existente. Snapshot real guardou marcador1/mode600 e arquivo. Segundo wrapper restaurou esses dados e emitiu HERDR_STARTED antes de qualquer attachment/start manual; terminal novo comparado ao primeiro, mais duas conexões TUI sem duplicação. Quatro capturas renderizaram saída Bash, não apenas contagem de bytes.

Sessão própria do telefone e clientes próprios encerrados; snapshot/sync/retorno CLI0 verificados nos dois com iPhone8,1 USB e gadget Linux ausente. Uptime pré-retorno342,35/343,71s; bateria iOS100→92% e92→92%, carga ativa após ambos. Não é prova de alimentação ou estabilidade prolongada. Receita/checkpoints públicos, logs/ANSI/IDs/snapshots privados. Herdr principal Mac intacto, sem agentes/pacotes/configuração global. Código operacional inalterado; evidências locais/VM/CI do launcher preservadas e CI6386b2b reutilizada para o retorno. JSON/links/diff/guard conferidos; nenhum novo teste de código exigido para essa fase documental.

Gate físico da #13 cumprido. #12 proveniência do legado, #19 política/porta53 nativa, #20 cliente Windows contra novo boot e #2/#8/hardware permanecem abertos. Inventário integral continua pinado a49d8747 (169/170), complete_pr_review=false; as cinco alterações foram lidas no escopo próprio sem parecer integral, merge, tag ou release.


## DNS Windows — gate físico #20

Plano prévio de cinco documentos atendido: DNS-WINDOWS, evidence/windows-dns-physical.json, STATUS, EXECUCAO e este relatório. Novo boot da cadeia de fonte com wrapper0/SSH/HTTP/console/restore real; hosts/launcher/dnsmasq comparados exatamente ao snapshot. DNS5353/proxy LAN versionado1053 não root/allowlist de dois clientes. Mac dig UDP/TCP passou. Helper público em cinco filhos PowerShell com assinatura Microsoft verificada: dois positivos UDP/TCP/exit0 e três negativos nome/endereço/porta exit1, sem marcadores, pelo motivo esperado. Negativos abortam em UDP; não contados como negativos TCP físicos. Baseline61/18mutações e CI36867261810/36867254184 reutilizados somente para fontes inalteradas/hash verificadas.

Erro operacional preservado: input codificado excessivo ficou no prompt; não contou como prova. Terminal de teste próprio substituído no mesmo workspace, fontes transmitidas em blocos2048bytes, hashes e parser nativo passaram. Diretório inicial conhecido inexistente ao final; final com exatamente duas fontes removidas/pasta ausente. Proxy próprio0 por SIGTERM, listeners1053 e túnel1054 ausentes; daemon/sessão Herdr do telefone parados. Snapshot/sync/retorno CLI0/iOS USB passaram, uptime pré-retorno261,57s e bateria92→91%, carga ativa após retorno. Não é prova de alimentação contínua.

JSON/links/diff/guard conferidos antes de publicar; nenhuma fonte operacional alterada, pacote, agente, DNS/firewall/política global ou chave adicionados. Receita pública e logs/IDs/endpoints privados. #20 cumpre critérios; nslookup causa desconhecida, #19 porta53/política/IP/Android/rollback permanece separado. Inventário integral continua pinado a49d8747 (169/170), complete_pr_review=false; cinco alterações lidas no escopo próprio, sem parecer integral, merge, tag ou release.

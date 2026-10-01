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

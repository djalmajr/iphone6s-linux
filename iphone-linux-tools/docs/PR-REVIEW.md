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

# Revisão da PR #1 — #16

## Escopo e plano

Revisão solo da branch `feat/display-console`, sem merge/tag. Baseline `168b95453d672a1ae862bf608bf39d5a463ec2f8`; primeira revisão no head `8a0a04873baeffe1b7ce18b48f0628a14d29e425`. O diff tem 120 arquivos, incluindo documentação, evidências, fontes, testes e remoções. Não declarar revisão integral antes de conferir todas as áreas e contabilizar a cobertura.

1. Persistência local e proteção do Mac: ler backup/restore, journal, lock, retenção e testes; reproduzir desvios somente em pastas temporárias sintéticas, registrar e corrigir falhas. Até cinco arquivos nesta fase: este documento, `scripts/host/persist.py`, `restore_journal.py`, `snapshot_lock.py` e `tests/test_local_snapshot_paths.py`.
2. Verificação/documentação (cinco arquivos): runner público de caminhos, runner de autosnapshots com a âncora do guard compartilhado, CI, este documento e PERSISTENCIA. Referência RECUPERACAO será atualizada na fase documental seguinte de até cinco arquivos. Reutilizar evidências não afetadas; executar fixtures VM relevantes quando a correção modificar o restaurador usado neles.
3. Continuar revisão dos demais caminhos de boot, rede/DNS, build e evidências; conferir também fontes removidas no baseline. Atualizar o corpo antigo da PR, que ainda trata wrapper/DNS/CI como inexistentes.
4. Registrar limites/cobertura e critérios da #16. Gates físicos da candidata, energia, estabilidade e autorização de merge não são substituídos pelo CI/revisão.

## D1. Recusar desvios locais antes de leitura/escrita

- **Decisão:** compartilhar a verificação de diretórios/arquivos locais reais e próprios em `snapshot_lock.py`, usá-la na leitura de snapshots e no journal. Não seguir links para corrigir permissões, procurar referências de recuperação ou carregar um backup.
- **Por quê:** o projeto só pode escrever no store privado próprio e o ID normal de um snapshot não garante que seu diretório esteja dentro desse store. A retenção já recusava links, mas os outros consumidores tinham um contrato diferente.
- **Alternativas:** documentar confiança absoluta na árvore local deixa alterações acidentais perigosas; resolver symlinks e aceitar destinos internos amplia a política e dificulta compreender o que pode ser restaurado.
- **Reverter:** baixo; alteração de código na branch, sem migração ou regravação de dados existentes. Os snapshots/journals regulares continuam compatíveis.
- **Status:** correção local/VM aprovada; CI e publicação da fase de verificação pendentes. Não comprova proteção contra um processo malicioso do mesmo usuário alterando a árvore concorrentemente.

## Falha local confirmada — #22

Dados sintéticos: `restore-journal` apontando para uma pasta externa ao store. `prepare` escreveu JSON nessa pasta e mudou seu modo de 755 para 700. Um diretório de snapshot de ID válido apontando para outro diretório também foi carregado fora do store. Nenhum arquivo real do operador foi usado ou alterado. A hipótese foi validada com caminhos canônicos e modos explícitos; a primeira observação tinha umask/comparação de aliases inadequados e não foi usada como prova.

A pasta privada reduz a exposição a outros usuários, mas não torna seguro seguir um link acidental ou uma árvore modificada. Esta é uma falha de escopo local de arquivos; não estamos afirmando uma exploração remota por um cliente DNS/HTTP.

## Critérios desta correção

- [x] Recusar diretório de journal/snapshot symlink, arquivo symlink/hardlink, tipo especial e propriedade incompatível antes de leitura/escrita.
- [x] Preservar conteúdo, modos e arquivos de uma pasta externa sintética quando houver desvio.
- [x] Listagem/default/restore/retorno ao iOS usam os mesmos gates de caminho; retenção continua preservando estruturas inválidas.
- [x] Snapshot/journal regulares continuam funcionando; corrupção continua bloqueando restore.
- [ ] Executar mutações, lint/sintaxe e testes afetados; nenhum type checker configurado.
- [ ] Publicar evidência sanitizada e atualizar as issues; sem dados privados, migração ou merge.

## Cobertura desta rodada

Leitura completa: `persist.py`, `snapshot_lock.py`, `restore_journal.py`, `snapshot_retention.py`, `scripts/ci/check-public.py` e `tests/test_persistence.py`. Testes de retenção/falha VM e wrapper original parcialmente lidos para seguir chamadas; não contabilizados como revisão completa. Demais áreas da PR continuam pendentes.

## Evidência da correção — fase 1

Nove testes de caminhos locais passaram; 11/11 mutações foram detectadas por asserção em cópias sintéticas. Seis testes de persistência, oito de retenção/lock e seis de agendador passaram. O guard de metadata é compartilhado por caminhos e descritor do lock, incluindo propriedade/tipo/link; sob root na VM, um arquivo sintético com outro UID também foi recusado pelo lock.

VM dedicada existente, sem mounts: nove testes de caminhos locais, dois cenários BusyBox reais de ENOSPC/interrupção e um cenário de agendamento/restore passaram após o compartilhamento final do guard. Duas mutações do restaurador foram rejeitadas na etapa anterior da mesma correção; seus predicados de journal pré-upload/erro remoto não mudaram no ajuste final do guard e essa evidência foi reutilizada. Fontes públicas somente; nenhuma chave, snapshot real ou pacote instalado. Limpeza/estado final da VM e CI serão registrados na fase seguinte.

Lint fatal e diff-check passaram. Não há type checker configurado. A alteração não torna o restore transacional nem protege contra autores concorrentes do mesmo usuário; limita leitura/escrita a nós locais regulares esperados. Ainda não houve operação no iPhone nesta correção.

## Verificação/limpeza — fase 2

Runner de 11 mutações preparado e registrado no CI Ubuntu/macOS: baseline e 11/11 mutações passaram no Mac. O runner anterior de autosnapshots agora mira `not valid_type` no guard compartilhado; a mudança de âncora conserva o teste do FIFO no lock e as 15/15 mutações foram rejeitadas. Flake8 fatal e `git diff --check` passaram após esses ajustes. A VM dedicada foi devolvida a `Stopped`, sem mounts: confirmado nenhum fixture/mount temporário próprio e removida somente a árvore de transferência pública desta rodada. Demais VMs não foram iniciadas ou modificadas.

CI integral ainda pendente nesta fase; registrar resultado somente após jobs terminais. Correção de paths não implica revisão completa da PR ou prova física nova de alimentação/boot.

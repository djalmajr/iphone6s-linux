# Persistência com backups no Mac

## Objetivo e plano

O Linux do iPhone roda em RAM. Esta etapa guarda snapshots privados no Mac e permite restaurar arquivos após outro boot, sem depender do armazenamento interno.

Arquivos: `persist.py`, `iphone-linux.sh`, `.gitignore`, `tests/test_persistence.py` e este documento.

- [x] Criar snapshots privados de `/srv/data` e arquivos de trabalho de `/root`.
- [x] Excluir identidade SSH, caches e estado de sessões/processos Herdr.
- [x] Verificar hash, escopo e tipos de arquivo antes de restaurar.
- [x] Fazer snapshot do estado atual antes de sobrescrever arquivos.
- [x] Testar recuperação de conteúdo/permissões e bloqueio de arquivo corrompido, caminho fora de escopo e symlinks.
- [x] Executar o ciclo real no iPhone sem reboot e publicar evidências sem conteúdo privado.
- [x] Restaurar snapshot em um novo boot DFU, verificando conteúdo, modo, arquivos extras e identidade SSH.

## Decisão

Snapshots explícitos por SSH autenticado, salvos em `backups/` no Mac. `/srv/data` será o diretório para serviços e dados. `/root` conserva scripts e configurações de trabalho; `.ssh`, caches e sessões Herdr são excluídos. A restauração sobrepõe arquivos presentes no snapshot, preservando arquivos extras. Não reinicia serviços nem recupera processos. Uma cópia automática anterior à restauração permite recuperar arquivos sobrescritos.

Sincronização contínua e restauração automática no boot ficam para outra etapa, após validar este mecanismo. Para arquivos de bancos de dados, parar o serviço ou usar a exportação nativa antes do snapshot: tar não fornece consistência transacional.

## Comandos

No diretório `iphone-linux-tools`:

```bash
bash iphone-linux.sh backup
bash iphone-linux.sh backups
bash iphone-linux.sh restore
# Ou escolher explicitamente um snapshot listado:
bash iphone-linux.sh restore AAAAMMDDTHHMMSSZ-xxxxxxxx
```

`restore` sem ID usa o snapshot manual mais recente. Snapshots `pre-restore` nunca são escolhidos automaticamente; seu ID pode ser passado explicitamente para recuperar o estado anterior. Cada restauração verifica primeiro a integridade e os caminhos, salva o estado atual e só então transfere/extrai por SSH. O hash é conferido no Mac e novamente no telefone.

Após novo boot: `boot`, seguido de `restore`. O boot ainda exige DFU físico. Não há sincronização contínua: alterações feitas depois do último snapshot são perdidas se faltar energia ou o telefone reiniciar. Antes de reiniciar, executar `backup` e esperar a confirmação.

## O que fica salvo

- `/srv/data`: diretório recomendado para serviços, configurações e arquivos do usuário.
- `/root`: arquivos de trabalho e configurações, incluindo perfil Bash.
- Excluídos: `/root/.ssh`, `/root/.cache`, `/root/.bash_history`, `/root/.config/herdr/sessions` e `/root/.local/state`.
- Links simbólicos, hardlinks e arquivos especiais são omitidos. Configuração de sessões/painéis Herdr, sockets e processos não são recuperados por este mecanismo.
- `/etc`, `/srv/iphone`, binários, kernel e chaves do servidor SSH vêm da imagem de boot e não entram nesses snapshots. Para configurações novas de serviços, usar `/srv/data` e apontá-las explicitamente ao iniciar o serviço.

Cada snapshot fica em `iphone-linux-tools/backups/<ID>/`, com `files.tar.gz` e `manifest.json`. Diretório com permissão 700, arquivos com permissão 600. Não são criptografados: são privados por permissões locais e podem conter informações pessoais/configurações. A pasta inteira está ignorada pelo Git. Não subir backups ao GitHub. Limites atuais: 512 MiB descomprimidos e 50.000 entradas por snapshot. Nomes contendo caracteres de controle não são aceitos.

## Restauração e limites

A restauração sobrepõe os arquivos do snapshot e conserva arquivos extras no destino. Antes da extração, rejeita caminhos fora de escopo, permissões especiais, entradas duplicadas e destinos com symlinks/hardlinks ou tipos incompatíveis. O destino é conferido novamente após o snapshot de segurança. São permitidos somente arquivos regulares e diretórios.

A extração não é transacional: falta de espaço ou interrupção pode deixar arquivos parcialmente restaurados. Nesse caso, preservar a mensagem/ID do snapshot `pre-restore` e usar esse ID para recuperar os arquivos anteriores. Serviços precisam ser parados/exportados antes de salvar bancos de dados ativos; o tar não substitui o mecanismo de backup do banco. Não se recuperam memória de processos, conexões, painéis ativos ou layout de sessões Herdr.

## Verificação em 2026-09-29

- 6 testes locais com `python3 -m unittest discover -s iphone-linux-tools/tests -v`: passaram. Cobrem arquivos de trabalho válidos, escopo/identidade SSH, links/tipos especiais, duplicatas, uso de arquivo como diretório, corrupção e ID com travessia de diretórios.
- Sintaxe Bash e AST Python: sem erros. Não há linter ou verificador de tipos configurados neste projeto.
- No iPhone ativo, snapshot → alteração do conteúdo/modo → restauração recuperou `original-content` e modo 640, preservando um arquivo extra criado depois do snapshot.
- Destinos com symlink e hardlink foram bloqueados antes da extração; arquivo apontado permaneceu intacto.
- Snapshot com bytes alterados foi bloqueado pela checagem de hash.
- Permissões 700/600 e exclusão de SSH/sessões Herdr conferidas nos arquivos reais do Mac.
- HTTP manteve o PID 92; Herdr permaneceu ativo. Não houve reboot nem instalação de pacote.
- Arquivos de teste removidos do telefone; snapshot final do estado operacional salvo no Mac. Os snapshots de teste e a cópia anterior à restauração permanecem locais, sem publicação.

Na rodada de 2026-09-29, a recuperação foi testada na mesma sessão, sem outro DFU/reboot. A validação em novo boot foi obtida posteriormente, conforme registro abaixo.

Registro resumido: [persistence-check.txt](evidence/persistence-check.txt).

## Recuperação após novo boot — 2026-09-30

A sentinela `/srv/data/boot-restore-proof.txt`, com modo 640 e conteúdo conhecido, estava no snapshot privado `20260929T201354Z-f0972c5b`, salvo antes dos reinícios. No novo Linux iniciado pelo wrapper sem contador, a sentinela estava ausente. Foi criado um arquivo extra temporário no destino e executada restauração explícita desse snapshot.

Resultado real: SHA-256 da sentinela `b236202ff49d61b978537415137da685cbf63164a42494dff6e7f004b28e7260`, modo 640, arquivo extra preservado. Os hashes das identidades SSH do servidor/cliente autorizado permaneceram iguais (valores não publicados); o PID HTTP permaneceu igual e o endpoint respondeu 200. O mecanismo criou um snapshot privado anterior à restauração. A fixture extra foi removida, e a sentinela recuperada foi mantida.

Isso conclui #4. Persistência depende dos snapshots no Mac: o teste não demonstrou armazenamento interno nem recuperação de processos. A extração continua não transacional; recuperação de interrupção/falta de espaço é #15.

## Encerramento da etapa

Fonte: plano deste documento e PR #1. Modo: encerramento de uma etapa do mini servidor.

**Entregue:** snapshots privados, listagem, restauração com cópia anterior, validação de integridade/escopo e recuperação em novo boot DFU. **Pendente:** recuperação de interrupção, sincronização automática e serviço DNS.

| Verificação | Resultado |
|---|---|
| Sintaxe | Bash e AST Python sem erros |
| Lint | Não há linter configurado; `git diff --check` passou |
| Tipos | Não há verificador de tipos configurado |
| Testes | 6/6 locais e ciclo real no telefone passaram |
| Documentação | Comandos, escopo, exclusões, evidências e limites registrados |
| Privacidade | Backup e manifesto ignorados; nenhum segredo encontrado nos padrões revisados dos arquivos preparados |

Os serviços atuais permanecem ativos; não foram instaladas dependências. Os comandos novos são aditivos. Captura e extração não fornecem consistência transacional para bancos ativos. Próxima etapa recomendada: serviço DNS limitado ao enlace USB, com configurações guardadas em `/srv/data`; acesso pela LAN depende de uma configuração de rede separada.

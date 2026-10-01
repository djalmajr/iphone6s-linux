# Persistência com backups no Mac

## Objetivo e plano

O Linux do iPhone roda em RAM. Esta etapa guarda snapshots privados no Mac e permite restaurar arquivos após outro boot, sem depender do armazenamento interno.

O procedimento de recuperação após interrupção está em [RECUPERACAO.md](RECUPERACAO.md).

O plano e o contrato dos snapshots automáticos estão em [AUTOSNAPSHOTS.md](AUTOSNAPSHOTS.md).

Arquivos: `scripts/host/persist.py`, `scripts/host/autosnap.py`, `scripts/host/snapshot_lock.py`, `scripts/host/snapshot_retention.py`, `scripts/host/iphone-linux.sh`, `.gitignore`, testes e este documento.

- [x] Criar snapshots privados de `/srv/data` e arquivos de trabalho de `/root`.
- [x] Excluir identidade SSH, caches e estado de sessões/processos Herdr.
- [x] Verificar hash, escopo e tipos de arquivo antes de restaurar.
- [x] Fazer snapshot do estado atual antes de sobrescrever arquivos.
- [x] Testar recuperação de conteúdo/permissões e bloqueio de arquivo corrompido, caminho fora de escopo e symlinks.
- [x] Executar o ciclo real no iPhone sem reboot e publicar evidências sem conteúdo privado.
- [x] Restaurar snapshot em um novo boot DFU, verificando conteúdo, modo, arquivos extras e identidade SSH.
- [x] Implementar e validar captura automática optativa, status privado, lock e retenção segura; mutações críticas rejeitadas em cópias descartáveis.

## Decisão

Snapshots explícitos por SSH autenticado, salvos em `backups/` no Mac. `/srv/data` será o diretório para serviços e dados. `/root` conserva scripts e configurações de trabalho; `.ssh`, caches e sessões Herdr são excluídos. A restauração sobrepõe arquivos presentes no snapshot, preservando arquivos extras. Não reinicia serviços nem recupera processos. Uma cópia automática anterior à restauração permite recuperar arquivos sobrescritos.

Snapshots automáticos são optativos e executados em primeiro plano; não há serviço permanente ou restauração automática implícita no boot. A operação pressupõe um único operador e nenhum backup/restore concorrente escrevendo nos mesmos destinos. Para arquivos de bancos de dados, parar o serviço ou usar a exportação nativa antes do snapshot: tar não fornece consistência transacional.

O lock exclusivo por `flock` no store serializa backup manual, autosnap e restore. O arquivo `.snapshot.lock` não deve ser apagado enquanto houver operação ativa. O diretório `logs/` não é alterado por serviços do macOS: não há instalação de LaunchAgent, pedido de senha ou alias de rede.

## Comandos

No diretório `iphone-linux-tools`:

```bash
bash scripts/host/iphone-linux.sh backup
bash scripts/host/iphone-linux.sh backups
bash scripts/host/iphone-linux.sh restore
# Ou escolher explicitamente um snapshot listado:
bash scripts/host/iphone-linux.sh restore AAAAMMDDTHHMMSSZ-xxxxxxxx
# Se uma restauração for interrompida, use o ID anterior publicado:
# Substitua o valor abaixo pelo ID pre-restore impresso pela ferramenta.
restore_before_id=AAAAMMDDTHHMMSSZ-xxxxxxxx
bash scripts/host/iphone-linux.sh restore "$restore_before_id"

# Captura automática única, acompanhamento e estado privado:
bash scripts/host/iphone-linux.sh autosnap once
bash scripts/host/iphone-linux.sh autosnap watch --interval 300 --keep 12 --timeout 300
bash scripts/host/iphone-linux.sh autosnap status

# Execução finita supervisionada usada no teste físico:
bash scripts/host/iphone-linux.sh autosnap watch --cycles 2 --interval 5 --keep 12 --timeout 60
```

`restore` sem ID usa o snapshot manual mais recente. Snapshots `pre-restore` nunca são escolhidos automaticamente; seu ID pode ser passado explicitamente para recuperar o estado anterior. Cada restauração verifica primeiro a integridade e os caminhos, salva o estado atual e registra no journal privado o ID anterior **antes** de transferir ou aplicar qualquer arquivo. O comando de recuperação é impresso antes da aplicação; o hash é conferido no Mac e novamente no telefone. Após uma aplicação bem-sucedida, o journal marca a recuperação correspondente como concluída.

Após novo boot: `bash scripts/host/iphone-linux.sh boot`, seguido de `bash scripts/host/iphone-linux.sh restore`. O boot ainda exige DFU físico. Não há sincronização contínua: alterações feitas depois do último snapshot são perdidas se faltar energia ou o telefone reiniciar. Antes de reiniciar, executar `backup` e esperar a confirmação.

`autosnap watch` permanece em foreground. `Ctrl+C`, `SIGTERM` e `SIGHUP` cancelam o job em andamento e seu grupo de processos; o watcher não reinicia o job cancelado. `--cycles` limita uma execução supervisionada e `--timeout` limita cada captura, com padrão de 300 segundos. `autosnap status` lê apenas `logs/autosnap-last.json`, com arquivo 600 e diretório `logs/` 700. A captura exige que `connect`/boot já tenham estabelecido SSH; o watcher não restaura snapshots.

`boot --restore ID` é uma opção explícita para um novo boot: valida o snapshot antes do DFU, recusa a operação se o Linux já estiver ativo, confirma SSH depois do novo boot, executa o restore e só então serve o painel. Sem a flag, o boot nunca restaura dados. O watcher nunca chama essa opção.

## O que fica salvo

- `/srv/data`: diretório recomendado para serviços, configurações e arquivos do usuário.
- `/root`: arquivos de trabalho e configurações, incluindo perfil Bash.
- Excluídos: `/root/.ssh`, `/root/.cache`, `/root/.bash_history`, `/root/.config/herdr/sessions` e `/root/.local/state`.
- Links simbólicos, hardlinks e arquivos especiais são omitidos. Configuração de sessões/painéis Herdr, sockets e processos não são recuperados por este mecanismo.
- `/etc`, `/srv/iphone`, binários, kernel e chaves do servidor SSH vêm da imagem de boot e não entram nesses snapshots. Para configurações novas de serviços, usar `/srv/data` e apontá-las explicitamente ao iniciar o serviço.

Cada snapshot fica em `iphone-linux-tools/backups/<ID>/`, com `files.tar.gz` e `manifest.json`. Diretório com permissão 700, arquivos com permissão 600. O journal de recuperação fica em `backups/restore-journal/`, com diretório 700 e registros 600. Não são criptografados: são privados por permissões locais e podem conter informações pessoais/configurações. A pasta inteira está ignorada pelo Git. Não subir backups ou journal ao GitHub. Limites atuais: 512 MiB descomprimidos e 50.000 entradas por snapshot. Nomes contendo caracteres de controle não são aceitos.

`backups` lista os snapshots e também imprime qualquer journal em estado pendente, junto com o comando `restore <ID-pre-restore>` para recuperar os arquivos anteriores. O ID deve ser anotado antes de qualquer nova aplicação; não depender de um rollback automático.

A retenção automática remove somente snapshots automáticos antigos que passaram a validação depois de um backup bem-sucedido. Mantém os últimos `K`, o snapshot atual e referências `source`/`before` de journals pendentes. Snapshots manuais, `pre-restore`, inválidos, links e estruturas com extras ficam protegidos. `K` é o limite da classe automática elegível, não uma quota global; itens inválidos exigem revisão manual.

## Restauração e limites

A restauração sobrepõe os arquivos do snapshot e conserva arquivos extras no destino. Antes da extração, rejeita caminhos fora de escopo, permissões especiais, entradas duplicadas e destinos com symlinks/hardlinks ou tipos incompatíveis. O destino é conferido novamente após o snapshot de segurança. São permitidos somente arquivos regulares e diretórios. Não há rollback automático, restauração da identidade SSH ou recuperação de processos/painéis; a recuperação é um overlay manual do snapshot anterior.

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

Na rodada de 2026-09-29, a recuperação foi testada na mesma sessão, sem outro DFU/reboot. A validação física em novo boot ocorreu em 2026-09-30, primeiro antes da reorganização e depois novamente com a árvore reorganizada, conforme registro abaixo. Os testes de interrupção documentados em #15 são de VM isolada e não alegam uma nova falha física no iPhone.

Registro resumido: [persistence-check.txt](evidence/persistence-check.txt).

## Recuperação após novo boot — 2026-09-30

A sentinela `/srv/data/boot-restore-proof.txt`, com modo 640 e conteúdo conhecido, estava no snapshot privado `20260929T201354Z-f0972c5b`, salvo antes dos reinícios. No novo Linux iniciado pelo wrapper sem contador, a sentinela estava ausente. Foi criado um arquivo extra temporário no destino e executada restauração explícita desse snapshot.

Resultado real: SHA-256 da sentinela `b236202ff49d61b978537415137da685cbf63164a42494dff6e7f004b28e7260`, modo 640, arquivo extra preservado. Os hashes das identidades SSH do servidor/cliente autorizado permaneceram iguais (valores não publicados); o PID HTTP permaneceu igual e o endpoint respondeu 200. O mecanismo criou um snapshot privado anterior à restauração. A fixture extra foi removida, e a sentinela recuperada foi mantida.

Isso concluiu #4 antes da reorganização. Em seguida, o novo CLI da árvore reorganizada repetiu o restore explícito: a sentinela estava ausente antes e voltou com SHA-256 `b236202ff49d61b978537415137da685cbf63164a42494dff6e7f004b28e7260`, modo 640. As identidades SSH foram comparadas e permaneceram intactas, sem publicar seus hashes; HTTP respondeu 200. Uma cópia privada anterior à restauração foi salva no Mac. Persistência depende dos snapshots no Mac: o teste não demonstrou armazenamento interno nem recuperação de processos. A extração continua não transacional; a recuperação de interrupção/falta de espaço é tratada na seção seguinte.

## Recuperação após interrupção — #15

Os testes reais foram executados em dois cenários dentro da VM Ubuntu ARM64 `iphone6s-build`, usando BusyBox 1.36.1 e dados sintéticos. Ambos passaram:

- um `ENOSPC` em tmpfs de 64 KiB interrompeu a aplicação sem ocultar o erro;
- um `SIGKILL` durante o tar, combinado com falha de limpeza remota 77, preservou o erro original 255 e deixou o comando explícito para recuperar o snapshot anterior;
- conteúdo e modos 640/600 foram recuperados, e a identidade SSH sintética permaneceu intacta.

Esses testes validam o journal privado, a publicação antecipada do ID anterior e o overlay manual. Não testam uma nova falha no iPhone, não tornam a extração transacional e não criam rollback automático. Serviços devem permanecer parados ou usar exportação consistente; autores concorrentes não são suportados.

## Snapshots automáticos — #5

A implementação foi exercitada no host e no aparelho com a captura optativa. O wrapper completou uma nova execução DFU com saída 0, restaurou a sentinela com SHA-256 `b236202ff49d61b978537415137da685cbf63164a42494dff6e7f004b28e7260` e modo 640, e o operador confirmou o console. Em seguida, `autosnap watch --cycles 2 --interval 5 --keep 12 --timeout 60` produziu dois snapshots automáticos com sucesso; os arquivos tinham modo 600, nove entradas e a identidade SSH estava excluída. O HTTP respondeu 200.

O guard de restauração em Linux já ativo recusou a execução com saída 1 e a sentinela permaneceu intacta. Foram aprovados 30 de 33 testes locais, com 3 cenários marcados como skip por exigirem VM; o rerun estreito de 8 cenários de retenção após a correção do modo FIFO também passou. Após o ajuste final do código de saída de uma execução limitada, os 6 testes de scheduler locais passaram. Na VM Ubuntu ARM64, os 7 cenários de scheduler/BusyBox passaram; as 2 falhas de restore de #15 também foram revalidadas sob lock em rodada anterior desta etapa. Quinze mutações foram rejeitadas em cópias descartáveis, em lotes de 8 + 6 + 1. Pyflakes, Flake8 fatal, AST Python, Bash e ShellCheck passaram.

A retenção destrutiva foi exercitada somente em fixtures; nenhum autosnapshot real anterior foi removido. Um snapshot manual final foi salvo no Mac. O aparelho retornou ao iOS com 100%, `BatteryIsCharging=true` e `ExternalConnected=true` após aproximadamente 17 minutos, com uptime Linux anterior de 1019,88 s; isso não prova carga sustentada nem operação de 24 horas. Nenhum scheduler permanente foi instalado.

Nenhum pacote foi instalado no Mac, nenhuma imagem foi reconstruída e nenhum serviço do macOS foi configurado. Evidência sanitizada: [autosnapshot-check.txt](evidence/autosnapshot-check.txt).

## Encerramento da etapa #5 — histórico

Fonte: plano deste documento e PR #1. Modo: encerramento de uma etapa do mini servidor.

**Entregue:** snapshots privados, listagem com pendências do journal, restauração com cópia anterior, validação de integridade/escopo, recuperação em novo boot DFU e procedimento de recuperação manual após interrupção. **#5 concluída:** automação, status, lock e retenção validados com testes locais, VM, mutações negativas e teste físico curto; evidência sanitizada registrada. **Pendente naquele checkpoint:** serviço DNS, posteriormente concluído na #7; #2 e #8 continuam abertas por seus próprios gates.

| Verificação | Resultado |
|---|---|
| Sintaxe | Bash e AST Python sem erros |
| Lint | Pyflakes e checagem fatal Flake8 passaram nos arquivos alterados; `git diff --check` passou |
| Tipos | Não há verificador de tipos configurado |
| Testes | 30/33 locais passaram e 3 foram ignorados por exigirem VM; reruns de retenção 8/8 e scheduler 6/6, VM 7/7 mais duas falhas de restore, e mutações 15/15 passaram |
| Documentação | Comandos, escopo, exclusões, evidências e limites registrados |
| Privacidade | Backup e manifesto ignorados; nenhum segredo encontrado nos padrões revisados dos arquivos preparados |

Nesta rodada de #5, não foram instaladas dependências, reconstruídas imagens ou configurados serviços no Mac. Os comandos novos são aditivos. Captura e extração não fornecem consistência transacional para bancos ativos. #2 e #8 continuam abertas; #5 está concluída e o próximo item planejado é #6. A prova física curta não substitui uma medição de carga sustentada ou um teste de 24 horas.

## Caminhos locais de snapshots/journal — #22

A leitura/listagem/default de snapshots e o journal agora conferem nós locais por metadata, antes de ler ou corrigir permissões: store/diretórios reais, arquivos regulares próprios, sem symlinks, hardlinks de arquivos ou modos especiais. O lock usa a mesma validação sobre seu descritor. ID e hash válidos não autorizam um caminho que redireciona para outra pasta. Um journal ausente é permitido; um symlink pendente não é tratado como ausência de referências de recuperação.

Se aparecer `Caminho local de snapshot/journal inválido`, preserve os backups e o erro. Inspecione tipo/propriedade do caminho indicado na sua árvore privada; não apague o journal, altere referências ou force um link para contornar o gate. Corrija somente um desvio que você reconhece e conserva os dados anteriores. Nenhuma migração ou regravação dos snapshots regulares é necessária; arquivos já existentes não foram modificados nesta correção.

A retenção continua preservando estruturas inválidas; a operação de leitura pode recusar a listagem/default quando há um ID de snapshot com desvio local. Não há correção automática de árvore nem proteção contra autores maliciosos do mesmo usuário alterando caminhos concorrentemente. Store privado 700 e arquivos 600 continuam sendo o formato escrito pelo projeto.

Reprodução dos testes sem aparelho: `python3 -m unittest discover -s iphone-linux-tools/tests -p test_local_snapshot_paths.py -v` e `python3 iphone-linux-tools/tests/run_snapshot_path_mutations.py`, a partir da raiz do clone público. Nove cenários sintéticos e 11 mutações; fixtures VM de falha/recuperação continuam separados e exigem o opt-in documentado em [RECUPERACAO.md](RECUPERACAO.md). Resultado e limites em [PR-REVIEW.md](PR-REVIEW.md).

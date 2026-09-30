# Snapshots automáticos — procedimento e encerramento da issue #5

## Contexto

Snapshots/restore e recuperação controlada já foram validados. #2 mantém operação prolongada pendente. A automação foi validada com fixtures, BusyBox em VM ARM64 e teste físico curto; ao final o telefone retornou ao iOS. Nenhum agendador permanente foi instalado no macOS; o comando optativo `autosnap watch` executa em primeiro plano e pode ser encerrado com Ctrl+C.

## Arquivos e fases

1. Até cinco arquivos: novo `scripts/host/snapshot_lock.py`, `scripts/host/snapshot_retention.py`, `scripts/host/persist.py`, novo `tests/test_snapshot_retention.py`, este plano. Verificação de exclusão mútua, integridade e retenção em diretórios sintéticos.
2. Até cinco arquivos: novo `scripts/host/autosnap.py`, `scripts/host/iphone-linux.sh`, novos testes `tests/test_autosnap.py`, `tests/test_autosnap_vm.py`, este documento. Verificação de recorrência, desconexão, timeout e opção de restauração no wrapper.
3. Documentação/evidências e revisão independente delegadas conforme regra de múltiplos arquivos; root conserva autoridade Git, VM e telefone.

## Decisões

### D1. Agendamento optativo em primeiro plano

- **Decisão:** `autosnap once` ou `autosnap watch --interval 300 --keep 12`, com `--cycles` para execução supervisionada limitada e timeout por job. O agendador não pede senha nem configura rede; `connect`/boot precedem seu uso.
- **Por quê:** atende agendamento opcional sem instalar serviços globais ou alterar políticas do Mac. O processo fica ligado à sessão do operador.
- **Alternativas:** LaunchAgent para início automático no login (mudaria configuração fora do projeto); timer na VM (adiciona dependência de VM e acesso às chaves). Retomar após necessidade explícita de sobreviver ao logout.
- **Reverter:** baixo; Ctrl+C e nenhuma mudança no telefone.
- **Onde:** `scripts/host/autosnap.py` e CLI.
- **Status:** aplicada e validada.

### D2. Retenção apenas de snapshots automáticos

- **Decisão:** manter os últimos K automáticos íntegros, com K ≥ 1; preservar todos os manuais, pre-restore, inválidos e referências source/before de journals pendentes. Remover somente snapshots automáticos antigos verificados e sem arquivos extras/links. Falha de captura não executa retenção. Um lock por store serializa comandos manuais e jobs.
- **Por quê:** protege recuperação explícita e o último válido; um erro de transferência não substitui nada. Snapshots continuam publicados por rename após validação.
- **Alternativas:** quota global que também apaga manuais (pode perder pontos de recuperação escolhidos pelo operador); compactação incremental (exige outro formato). K é limite dos automáticos elegíveis, não teto de espaço total.
- **Reverter:** médio; exclusão de snapshot antigo é irreversível, protegidos permanecem. A exclusão foi exercitada em fixtures; a execução física não precisou remover snapshots reais anteriores.
- **Onde:** retenção, lock e comandos de persistência.
- **Status:** aplicada e validada.

### D3. Restauração automática explícita no novo boot

- **Decisão:** `boot --restore ID` valida snapshot antes do DFU e aplica após confirmar SSH de um novo boot. Recusar essa opção quando Linux já estiver ativo. Sem flag, boot nunca restaura dados; watcher nunca restaura.
- **Por quê:** evita restaurar sobre uma sessão de trabalho ativa ou por interpretar um erro de conexão como novo boot. Aproveita o restore já validado e identidade SSH estrita.
- **Alternativas:** detectar boot_id em watcher (uma reconexão pode ser confundida com boot e sobrescrever trabalho); configurar restore permanente (mais estado e política de serviços). O flag é configuração optativa por execução.
- **Reverter:** baixo; omitir flag. A aplicação continua overlay não transacional, com snapshot anterior e journal.
- **Onde:** wrapper/verify e testes.
- **Status:** aplicada e validada em novo DFU físico, com sentinela restaurada antes da verificação final de HTTP.

## Tarefas

- [x] Lock e retenção protegendo o último íntegro, referências pendentes, manuais e inválidos.
- [x] Scheduler opcional e falha/timeout sem substituir o último backup.
- [x] Flag de restore no novo boot, validação antes do DFU, recusa em sessão ativa.
- [x] Testes de filesystem/concorrência, recorrência e dependência real VM; mutações críticas rejeitadas.
- [x] Documentação/revisão, privacidade e prova física curta.

## Uso pelo Mac

Partindo de `iphone-linux-tools/`, com Linux iniciado e `connect`/boot já confirmados:

```sh
bash scripts/host/iphone-linux.sh autosnap once --keep 12 --timeout 300
bash scripts/host/iphone-linux.sh autosnap watch --interval 300 --keep 12 --timeout 300
bash scripts/host/iphone-linux.sh autosnap status
```

O intervalo é a espera entre o fim de uma captura e o início da próxima; cada captura tem seu próprio timeout. Todos os valores devem ser positivos. `--cycles 2` encerra depois de duas tentativas. Uma execução limitada retorna 1 se qualquer captura falhou, mesmo que outra tenha sucesso. O watcher continua tentando em intervalos regulares enquanto estiver ativo.

Ctrl+C, SIGTERM ou SIGHUP encerram o watcher e cancelam seu grupo de processos; saída 130 indica cancelamento. O estado privado `logs/autosnap-last.json` registra o último job concluído e conserva `last_success` após erro. Ele não indica se há um watcher vivo. Interrupção pode deixar estado antigo e diretórios `.partial-*` ignorados pela listagem/retenção; inspecione-os apenas quando não houver captura em andamento.

O store tem diretório 700, arquivos 600 e lock `.snapshot.lock`. Não apague o lock durante uma operação: o inode precisa ser o mesmo para todos os processos. Ao terminar ou morrer o processo, o sistema libera o `flock`; o arquivo permanece. Operações concorrentes são recusadas, sem bloquear indefinidamente.

Retenção mantém os últimos `K` automáticos elegíveis, preservando o snapshot recém-publicado e as referências de journals pendentes. Manuais, `pre-restore`, inválidos, links e estruturas com extras não são removidos. Um journal inválido impede a retenção. Portanto `K` não limita o espaço total do store. A captura valida arquivo e manifesto antes de publicar por rename; isso não é uma garantia de transação durável de todo o filesystem após perda de energia do Mac.

Antes de capturar dados de banco, pare os autores ou gere uma exportação consistente. Um tar de arquivos em alteração não garante consistência transacional. Nesta rodada os serviços eram HTTP de leitura e Bash; nenhum banco foi adicionado.

## Restauração no boot

```sh
bash scripts/host/iphone-linux.sh backups
bash scripts/host/iphone-linux.sh boot --restore ID
```

Substitua `ID` por um identificador validado da listagem. A verificação ocorre antes do DFU; o restore exige um novo boot, SSH com identidade estrita e cria um snapshot `pre-restore`. O wrapper só verifica e informa o HTTP após sucesso. O init integrado já inicia o HTTP de diagnóstico na rede USB; o flag não bloqueia esse servidor durante o restore. Sem `--restore`, nenhum arquivo é restaurado. O scheduler nunca restaura. O comando `restore` sem ID continua escolhendo o último snapshot **manual**, não o último automático.

A aplicação é overlay não transacional, conserva arquivos extras e não regenera chaves SSH. Em caso de interrupção, siga [RECUPERACAO.md](RECUPERACAO.md) e o journal privado. Não restaure sobre autores concorrentes.

## Reprodução dos testes

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -v
python3 iphone-linux-tools/tests/run_autosnap_mutations.py
```

Esses comandos partem da raiz do repositório. Os testes Linux/root são optativos e ficam como skip no Mac. Na VM Ubuntu ARM64 dedicada, copie apenas as fontes públicas de `scripts/host/` e os testes para um diretório temporário pertencente ao projeto; não copie snapshots, `keys/`, imagens ou runtime reais. Execute:

```sh
sudo env IPHONE_RESTORE_VM_TESTS=1 python3 -m unittest discover -s /tmp/iphone6s-autosnap-validation/tests -p 'test_autosnap*.py' -v
sudo env IPHONE_RESTORE_VM_TESTS=1 python3 -m unittest discover -s /tmp/iphone6s-autosnap-validation/tests -p test_restore_failure_vm.py -v
```

Os fixtures usam BusyBox/Bash já disponíveis na VM e dados sintéticos; o transporte é substituído por chroot, a captura/extração real continua sendo executada. Os testes limpam seus mounts e diretórios. Confira a ausência de recursos próprios antes de remover somente o diretório de transferência e devolver a VM a seu estado anterior.

## Resultado e verificações — 2026-09-30

Fonte: este plano, critérios da issue #5 e revisão independente. Três fases concluídas; arquivos de produção, testes e procedimentos versionados. [Evidência sanitizada](evidence/autosnapshot-check.txt).

| Verificação | Resultado |
|---|---|
| Local | Suíte inicial: 30 aprovados e 3 skips em 33; após ajuste final, scheduler 6/6 e retenção 8/8 aprovados em reruns específicos |
| VM | Scheduler/BusyBox 7/7; dois cenários reais de falha de restore de #15 revalidados sob lock em rodada anterior desta etapa |
| Mutações | 15 alterações críticas rejeitadas em cópias descartáveis, em lotes de 8 + 6 + 1 |
| Físico | Novo DFU, `boot --restore ID` saída 0, sentinela SHA/modo 640, console, SSH e HTTP 200; dois automáticos íntegros, identidade SSH excluída, arquivos 600; restore em Linux ativo recusado |
| Lint/sintaxe | Pyflakes, Flake8 fatal, AST Python, Bash e ShellCheck; AST não é typecheck, não há typechecker configurado |
| Dependências/build | Nenhum pacote instalado nesta etapa, nenhuma imagem reconstruída, hashes existentes preservados |
| Dados/performance | Snapshot/restore continuam overlay de arquivos; nenhum banco/migração ou benchmark de performance; execução física curta não prova serviço contínuo |

Um snapshot manual final foi salvo antes de retornar ao iOS. `reboot` comum retornou 0 sem concluir o reboot neste init mínimo. Pelo Bash acessado no Mac, `sync; reboot -f` efetivamente mudou a enumeração USB para iPhone; o cliente pode perder conexão, e essa perda isolada não comprova iOS. Veja o procedimento em [REPRODUCAO.md](REPRODUCAO.md). Após uptime Linux de 1019,88 s, iOS indicou 100%, carregando e energia externa. O teto de 100% e a preparação/reinício impedem concluir carga líquida sustentada. #2 e #8 permanecem abertas.

#5 atende seus critérios. O goal permanece ativo; próximo item #6, conectividade pela LAN. A branch continua candidata na PR #1, sem merge autorizado.

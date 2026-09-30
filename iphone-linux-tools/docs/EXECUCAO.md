# Execução do backlog do mini servidor

Goal autorizado em 2026-09-29. Fonte de trabalho: [issue #17](https://github.com/djalmajr/iphone6s-linux/issues/17). Cada issue conserva seus critérios e só será encerrada com evidência correspondente.

## Contexto e arquivos

O Linux atual roda em RAM, com console, SSH, HTTP e Herdr. A sequência abaixo segue a ordem já aprovada. Scripts, testes e documentos ficam em `iphone-linux-tools/`; snapshots e identidades continuam privados. Estado inicial: branch `feat/display-console`, sem alterações locais.

## Tarefas e verificação

- [ ] #2: validar alimentação/bateria. Arquivos desta etapa: `phone/diagnostics/power-check.sh`, `tests/test_power_check.py`, `docs/ALIMENTACAO.md`, `docs/evidence/power-check.txt`. Verificação: sensores reais por SSH, testes de ausência/leitura parcial e observação física; comprovar carga sustentada antes de uso sem supervisão.
- [x] #3: boot completo do wrapper. DFU manual sem página, envio, SSH/HTTP e console confirmados em uma execução, saída 0, em 2026-09-30.
- [x] #4: snapshot restaurado após novo boot; conteúdo, modo 640, arquivo extra, identidade SSH e HTTP confirmados em 2026-09-30.
- [x] #15: recuperação de restauração interrompida/falta de espaço. Journal privado, publicação antecipada do ID anterior, lista de pendências e overlay manual verificados em dois cenários reais na VM Ubuntu ARM64.
- [x] #5: snapshots automáticos e retenção, sem perder o último íntegro. Concluída com testes locais, VM, mutações negativas e prova física curta; evidência em `docs/evidence/autosnapshot-check.txt`.
- [ ] #6: acesso SSH/HTTP pela LAN via Mac, com teste de outra máquina e reversão. Saída genérica de internet permanece separada e desabilitada; implementação/gates isolados em [REDE.md](REDE.md), prova física pendente.
- [ ] #7: DNS local, começando pelo USB, com configuração restaurável.
- [ ] #8: estabilidade monitorada prolongada, após alimentação validada.
- [ ] #12: proveniência e build independente, com atualização/rollback.
- [ ] #14: CI para testes e privacidade sem dependência do aparelho.
- [ ] #16: revisão e documentação da PR; merge exige autorização explícita.
- [ ] #13: Herdr idempotente no boot e reconexão.
- [ ] #9: pesquisa de Wi-Fi específica N71/A9.
- [ ] #10: pesquisa de armazenamento interno, primeiro somente leitura.
- [ ] #11: pesquisa de boot autônomo e recuperação após energia.

## Decisões e alternativas

### D1. Ausência de sensores não valida alimentação

- **Decisão:** fazer leitura sem alterações de hardware, documentar desconhecidos e exigir observação/medição física para concluir #2.
- **Por quê:** o Linux responde pelo USB, mas bateria e temperatura não aparecem no sysfs. Funcionamento não comprova corrente líquida de carga nem proteção térmica.
- **Alternativas:** portar um driver específico A9 (alto custo e risco de interpretação errada de registradores); comparar estado da bateria antes/depois via iOS (interrompe Linux e exige novo DFU); medição externa (depende de instrumento e mede entrada, não necessariamente carga da bateria).
- **Reverter:** baixo; a checagem apenas lê arquivos de sensores.
- **Onde:** #2 e `docs/ALIMENTACAO.md`.
- **Status:** em curso; validação física pendente.

### D2. Journal de recuperação e overlay manual

- **Decisão:** manter a restauração não transacional, registrar em `backups/restore-journal/` o ID do snapshot anterior antes de aplicar qualquer arquivo, listar pendências em `backups` e recuperar explicitamente com `restore <ID-pre-restore>`. Após sucesso, o journal correspondente é marcado como recuperado.
- **Por quê:** uma interrupção pode deixar arquivos parcialmente sobrepostos; publicar o ID antes da aplicação conserva um caminho verificável mesmo quando a limpeza remota falha. O contrato continua sendo de um operador, sem autores concorrentes, com serviços parados ou bancos exportados de forma consistente.
- **Alternativas:** uma transação de árvore inteira exigiria duas cópias e aproximadamente o dobro de RAM; uma troca atômica de diretórios poderia alterar caminhos usados por processos. Transação arquivo a arquivo exigiria um contrato explícito para autores concorrentes. Essas alternativas ficam para uma etapa futura.
- **Reverter:** recuperação manual pelo snapshot `pre-restore` continua disponível; não há rollback automático, restauração de identidade SSH ou recuperação de processos.
- **Onde:** `docs/RECUPERACAO.md`, `docs/PERSISTENCIA.md`, #15.
- **Prova:** dois cenários reais na VM Ubuntu ARM64 `iphone6s-build`, com BusyBox 1.36.1, passaram: ENOSPC em tmpfs de 64 KiB propagou a falha da extração; SIGKILL durante tar com falha de cleanup 77 preservou o erro original 255; conteúdo/modos 640/600 e identidade SSH sintética foram recuperados.
- **Status:** aplicada; #15 pode ser encerrada com essa prova. Não é uma nova falha física nem um novo boot no iPhone.

### D3. Autosnapshots optativos e retenção protegida

- **Decisão:** oferecer `autosnap once`, `autosnap watch --interval 300 --keep 12 --timeout 300` e `autosnap status` em foreground. `--cycles` limita testes supervisionados; nenhum LaunchAgent, alias de rede ou pedido de senha é configurado.
- **Retenção:** remover somente automáticos antigos íntegros após backup bem-sucedido; manter os últimos `K`, o atual e referências `source`/`before` de journals pendentes. Manuais, `pre-restore`, inválidos, links e estruturas com extras ficam protegidos. `K` não é quota global.
- **Concorrência:** `flock` no store serializa manual, automático e restore; `.snapshot.lock` não deve ser apagado durante operação.
- **Restauração no boot:** `boot --restore ID` valida antes do DFU, recusa Linux já ativo, restaura depois de confirmar SSH e antes de verificar/informar o painel. O init já inicia o HTTP de diagnóstico na rede USB; o flag não impede acesso a ele durante o restore. Sem flag, o boot não restaura; watcher nunca restaura.
- **Prova:** novo DFU com saída 0, console e HTTP 200; dois autos com intervalo de 5 s, `keep 12` e timeout 60 passaram com arquivos 600, nove entradas e identidade SSH excluída; o guard em Linux ativo recusou com saída 1 e preservou a sentinela. Foram aprovados 30/33 testes locais (3 skips por exigirem VM), reruns estreitos de retenção 8/8 e scheduler 6/6, 7/7 cenários VM de scheduler/BusyBox e duas falhas de restore revalidadas sob lock, e 15/15 mutações em cópias descartáveis. Não é prova de 24 horas ou carga sustentada.
- **Onde:** [AUTOSNAPSHOTS.md](AUTOSNAPSHOTS.md), `docs/PERSISTENCIA.md` e evidência sanitizada `docs/evidence/autosnapshot-check.txt`.
- **Status:** concluída; #2 e #8 continuam abertas.

## Checkpoint — 2026-09-30

Goal retomado. iOS informou 100% de carga antes das tentativas; diagnóstico nominal sugere desgaste importante, detalhado em `ALIMENTACAO.md`. O Linux iniciou novamente via USB-A, em duas etapas (aquisição de PongoOS e retomada do wrapper). A troca posterior para um novo cabo USB-C frontal manteve console, SSH e HTTP. O piloto supervisionado durou pouco mais de dez minutos sem carga artificial de CPU; após reboot, iOS informou 94% e carregamento ativo. A comparação inclui também as tentativas anteriores e o Linux via USB-A, portanto não isola o desempenho do cabo novo. Nesse checkpoint inicial, #2 e #3 ainda estavam abertas.

Posteriormente, o procedimento USB-A com baseline 94% e cerca de 12 minutos de Linux retornou ao iOS com 100%; a alimentação contínua ainda não está validada. O contador foi removido a pedido do usuário, e o substituto sem interface web passou em 15 testes locais e em um boot físico completo. #3 e #4 têm critérios atendidos e evidências registradas; #2 continua em investigação e mantém bloqueado o teste prolongado sem supervisão.

## Reorganização solicitada — #18

Scripts agrupados em `scripts/host`, `scripts/boot` e `scripts/build`; fontes do telefone em `phone`; binários, imagens e logs privados em `bin`, `artifacts` e `logs`. Documentos e evidências soltos foram movidos para `docs` e `docs/evidence`. Caminhos no CLI, fixtures e procedimentos foram ajustados. A mudança não reconstruiu imagens nem alterou identidades ou snapshots. Resultados e limites: [ORGANIZACAO.md](ORGANIZACAO.md).

No último intervalo supervisionado, aproximadamente 25 minutos de Linux via USB-A, o retorno ao iOS informou 90% às 12:50:22 UTC, comparado a 100% antes da preparação. Um snapshot foi salvo antes do reboot. O aparelho permaneceu frio/morno, mas carga sustentada continua pendente; a comparação não isola corrente líquida durante Linux. #2 e #8 continuam abertas. #5 está concluída; o próximo item planejado é #6, sem autorização para merge; o goal permanece ativo.

## Leitura real do orçamento USB — #2

O novo boot frio e a restauração usando a árvore reorganizada passaram fisicamente: wrapper saída 0, SSH/HTTP e console; sentinela recuperada com conteúdo/modo 640 e identidade SSH preservada. Essa pendência da reorganização foi atendida.

Diagnóstico ampliado, somente leitura: `MaxPower=500 mA`, `bmAttributes=0x80`, sem sensores de bateria/temperatura. O default de 2 mA da fonte Kconfig não se aplica ao descriptor efetivo desta imagem; não foi alterado o descriptor. O fork SN2400/BQ27545 consultado tem validação A10/D111/J172 e não é prova de suporte N71/A9. Brilho reduzido temporariamente, mantendo os comandos pelo Mac conforme preferência do usuário.

17 testes locais passaram, incluindo atributos ausentes/presentes, preservação de arquivos e exclusão de strings de identificação. Mutação da leitura efetiva foi detectada; syntax/ShellCheck do diagnóstico e AST Python passaram. Não há typechecker configurado. Após 17 minutos de Linux com brilho variável/reduzido, iOS informou 100% a partir de 98%; os campos brutos de carga/máximo caíram, e o teto de 100% e a variação do medidor impedem comprovar carga líquida. Dados salvos antes de retornar ao iOS. #2 segue aberta, com avaliação técnica/topologia A9 e medição repetível pendentes; #8 continua dependente. #5 está concluída com a evidência sanitizada indicada em D3. A prova de #15 é limitada à VM e aos dados sintéticos; não altera o estado de #2 ou #8. O próximo item planejado é #6, sem autorização para merge; o goal permanece ativo.

## Encaminhamento LAN — desenvolvimento da #6

Implementado CLI foreground `lan --bind IP` com destinos TCP fixos, sem configuração global. Gates locais (2 aprovados, 1 skip VM), baseline real OpenSSH/Dropbear/BusyBox em namespace e sete mutações negativas passaram. O parecer do Grok foi incorporado e a investigação prossegue solo conforme preferência atual do usuário. VM limpa/parada; prova com iPhone e Windows alien ainda necessária para encerrar #6. [Procedimento e limites](REDE.md), [evidência sanitizada](evidence/lan-check.txt).

O piloto seguinte recebeu HTTP 200 e SSH autenticado no Windows independente, após corrigir manualmente `lo` DOWN no telefone. Autorização SSH original restaurada com comparação exata, identidade temporária revogada e fixtures dos clientes removidos. Snapshot privado salvo; forwards encerrados. O teste durou cerca de 28 minutos; após reboot o telefone deixou de ser detectado no USB. O operador confirmou depois tela de desbloqueio do iOS e aparelho sempre frio; bateria após retorno ainda não foi lida. #2/#8 permanecem abertas.

Preparada correção de bootstrap em `phone/init/init-server`, reconstruída usando somente ferramentas existentes na VM e preservando a imagem anterior. A comparação de 2.969 entradas permitiu diferença somente no init; alteração extra sintética foi recusada. Payload privado de 23.765.032 bytes, SHA-256 `8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66`; wrapper seleciona a candidata para o próximo teste. Dois testes wrapper e dois testes locais LAN passaram (um skip VM), lint/sintaxe passaram; nenhum typechecker configurado. Não houve pacote novo, alteração de banco, NAND/iOS ou configuração global de rede. #6 só encerra após boot novo e acesso Windows sem correção manual; imagem construída não comprova esse gate.

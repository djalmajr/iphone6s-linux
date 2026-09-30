# Execução do backlog do mini servidor

Goal autorizado em 2026-09-29. Fonte de trabalho: [issue #17](https://github.com/djalmajr/iphone6s-linux/issues/17). Cada issue conserva seus critérios e só será encerrada com evidência correspondente.

## Contexto e arquivos

O Linux atual roda em RAM, com console, SSH, HTTP e Herdr. A sequência abaixo segue a ordem já aprovada. Scripts, testes e documentos ficam em `iphone-linux-tools/`; snapshots e identidades continuam privados. Estado inicial: branch `feat/display-console`, sem alterações locais.

## Tarefas e verificação

- [ ] #2: validar alimentação/bateria. Arquivos desta etapa: `phone/diagnostics/power-check.sh`, `tests/test_power_check.py`, `docs/ALIMENTACAO.md`, `docs/evidence/power-check.txt`. Verificação: sensores reais por SSH, testes de ausência/leitura parcial e observação física; comprovar carga sustentada antes de uso sem supervisão.
- [x] #3: boot completo do wrapper. DFU manual sem página, envio, SSH/HTTP e console confirmados em uma execução, saída 0, em 2026-09-30.
- [x] #4: snapshot restaurado após novo boot; conteúdo, modo 640, arquivo extra, identidade SSH e HTTP confirmados em 2026-09-30.
- [ ] #15: recuperação de restauração interrompida/falta de espaço.
- [ ] #5: snapshots automáticos e retenção, sem perder o último íntegro.
- [ ] #6: LAN/internet pelo Mac, com teste de outra máquina e reversão.
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

## Checkpoint — 2026-09-30

Goal retomado. iOS informou 100% de carga antes das tentativas; diagnóstico nominal sugere desgaste importante, detalhado em `ALIMENTACAO.md`. O Linux iniciou novamente via USB-A, em duas etapas (aquisição de PongoOS e retomada do wrapper). A troca posterior para um novo cabo USB-C frontal manteve console, SSH e HTTP. O piloto supervisionado durou pouco mais de dez minutos sem carga artificial de CPU; após reboot, iOS informou 94% e carregamento ativo. A comparação inclui também as tentativas anteriores e o Linux via USB-A, portanto não isola o desempenho do cabo novo. Nesse checkpoint inicial, #2 e #3 ainda estavam abertas.

Posteriormente, o procedimento USB-A com baseline 94% e cerca de 12 minutos de Linux retornou ao iOS com 100%; a alimentação contínua ainda não está validada. O contador foi removido a pedido do usuário, e o substituto sem interface web passou em 15 testes locais e em um boot físico completo. #3 e #4 têm critérios atendidos e evidências registradas; #2 continua em investigação e mantém bloqueado o teste prolongado sem supervisão.

## Reorganização solicitada — #18

Scripts agrupados em `scripts/host`, `scripts/boot` e `scripts/build`; fontes do telefone em `phone`; binários, imagens e logs privados em `bin`, `artifacts` e `logs`. Documentos e evidências soltos foram movidos para `docs` e `docs/evidence`. Caminhos no CLI, fixtures e procedimentos foram ajustados. A mudança não reconstruiu imagens nem alterou identidades ou snapshots. Resultados e limites: [ORGANIZACAO.md](ORGANIZACAO.md).

No último intervalo supervisionado, aproximadamente 25 minutos de Linux via USB-A, o retorno ao iOS informou 90% às 12:50:22 UTC, comparado a 100% antes da preparação. Um snapshot foi salvo antes do reboot. O aparelho permaneceu frio/morno, mas carga sustentada continua pendente; a comparação não isola corrente líquida durante Linux. Próxima etapa funcional: #2, com medição específica A9 ou comparação repetível; #8 continua bloqueada por esse gate. O goal permanece ativo.

## Leitura real do orçamento USB — #2

O novo boot frio e a restauração usando a árvore reorganizada passaram fisicamente: wrapper saída 0, SSH/HTTP e console; sentinela recuperada com conteúdo/modo 640 e identidade SSH preservada. Essa pendência da reorganização foi atendida.

Diagnóstico ampliado, somente leitura: `MaxPower=500 mA`, `bmAttributes=0x80`, sem sensores de bateria/temperatura. O default de 2 mA da fonte Kconfig não se aplica ao descriptor efetivo desta imagem; não foi alterado o descriptor. O fork SN2400/BQ27545 consultado tem validação A10/D111/J172 e não é prova de suporte N71/A9. Brilho reduzido temporariamente, mantendo os comandos pelo Mac conforme preferência do usuário.

17 testes locais passaram, incluindo atributos ausentes/presentes, preservação de arquivos e exclusão de strings de identificação. Mutação da leitura efetiva foi detectada; syntax/ShellCheck do diagnóstico e AST Python passaram. Não há typechecker configurado. Após 17 minutos de Linux com brilho variável/reduzido, iOS informou 100% a partir de 98%; os campos brutos de carga/máximo caíram, e o teto de 100% e a variação do medidor impedem comprovar carga líquida. Dados salvos antes de retornar ao iOS. #2 segue aberta, com avaliação técnica/topologia A9 e medição repetível pendentes; #8 continua dependente. Desenvolvimento local de recuperação pode seguir sem uso prolongado do telefone.

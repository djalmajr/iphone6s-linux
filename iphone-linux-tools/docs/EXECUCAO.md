# Execução do backlog do mini servidor

Goal autorizado em 2026-09-29. Fonte de trabalho: [issue #17](https://github.com/djalmajr/iphone6s-linux/issues/17). Cada issue conserva seus critérios e só será encerrada com evidência correspondente.

## Contexto e arquivos

O Linux atual roda em RAM, com console, SSH, HTTP e Herdr. A sequência abaixo segue a ordem já aprovada. Scripts, testes e documentos ficam em `iphone-linux-tools/`; snapshots e identidades continuam privados. Estado inicial: branch `feat/display-console`, sem alterações locais.

## Tarefas e verificação

- [ ] #2: validar alimentação/bateria. Arquivos desta etapa: `power-check.sh`, `tests/test_power_check.py`, `docs/ALIMENTACAO.md`, `docs/evidence/power-check.txt`. Verificação: sensores reais por SSH, testes de ausência/leitura parcial e observação física; comprovar carga sustentada antes de uso sem supervisão.
- [ ] #3: boot completo do wrapper. Registrar DFU, envio, SSH, console e HTTP em um novo boot.
- [ ] #4: restaurar snapshot após boot e comprovar conteúdo/permissões.
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

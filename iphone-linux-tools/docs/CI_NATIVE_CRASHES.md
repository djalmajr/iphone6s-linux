# CI Linux: crashes esperados de mutações

[Issue 41](https://github.com/djalmajr/iphone6s-linux/issues/41), [plano](../.agents/plans/ci-native-crash-isolation.md), [prova sanitizada](evidence/ci-native-crash-isolation.json).

## Resultado anterior e decisão

No [run PR de ec09d4f](https://github.com/djalmajr/iphone6s-linux/actions/runs/37562583685), Mac e Windows DNS passaram. Ubuntu foi cancelado na etapa de testes sintéticos; a anotação confirma o limite de 15 minutos excedido. Os logs desse job não estavam disponíveis nas consultas. Isso não comprova falha de um teste específico nem aprovação da suíte Linux.

SIGABRT é esperado nos testes de mutação C. A [fonte Linux fixada](https://github.com/HoolockLinux/linux/blob/958481f87fee0949ff6a9a4af77f7eb6dac8a149/fs/coredump.c#L984) mostra que o limite normal de core não impede handlers por pipe. A VM dedicada usa Apport nesse caminho. Medimos o mesmo gate AIC com três inputs intactos, 61 cenários e 14 mutações compiladas por asserção:

| Configuração temporária na VM | Duração | Resultado |
|---|---:|---|
| Handler original por pipe |19,508 s | passou |
| Nome de arquivo simples `core` |0,717 s | passou |

O handler original foi restaurado exatamente em `finally` e conferido por readback. Testes, asserts e prazos permaneceram iguais. Esse par justifica evitar handlers externos durante crashes esperados; não prova que explique todo o timeout no GitHub.

## Mudança e escopo

O [helper](../scripts/ci/isolate-native-crashes.sh) exige GITHUB_ACTIONS=true, RUNNER_OS=Linux e RUNNER_ENVIRONMENT=github-hosted, sem argumentos. As variáveis são [definidas pelo GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/variables). O workflow o chama somente no job Linux, antes dos testes sintéticos.

O helper lê `kernel.core_pattern`. Se for pipe, usa `sudo -n` para substituir somente o handler da VM de CI por `core`, conferindo o valor escrito. Se já for arquivo, não escreve e exige que o valor permaneça igual. Erros de leitura, escrita ou readback encerram o preflight sem reportar sucesso. Os fixtures já definem RLIMIT_CORE=0; com handler de arquivo, crashes esperados não iniciam Apport. O prazo de 15 minutos e todos os testes/mutações continuam no workflow.

Essa política foi preparada para o runner hospedado do job; não é instrução para configurar o Mac ou um servidor. Testes do helper usam exclusivamente mocks de sysctl/sudo. A medição na VM local usou um runner privado separado com backup e restauração, sem executar o helper público nela. Não houve instalação ou configuração global do Mac, operação no telefone, alteração de cloud/account ou integração em main.

## Verificação e reprodução

Mac e Ubuntu ARM64: 15 cenários e oito mutações por plataforma. Cada mutant passa `bash -n` e quebra um contrato por AssertionError; syntax/import/timeout não contam como kill. Os cenários recusam ambiente local/macOS/Windows/self-hosted/argumentos antes de qualquer comando, verificam leitura/efeito/readback, ausência de efeito, arquivo errado e alteração inesperada do baseline. Três inputs idênticos por SHA; os mocks mantêm o handler real da VM intacto.

```sh
python3 -B -m unittest discover -s tests -p 'test_ci_native_crashes.py' -v
bash -n scripts/ci/isolate-native-crashes.sh
shellcheck scripts/ci/isolate-native-crashes.sh
python3 -m flake8 --select E9,F63,F7,F82 tests/test_ci_native_crashes.py
```

Bash syntax, ShellCheck, AST e lint fatal passaram no Mac; Bash syntax e AST passaram também no ARM64. Não há typechecker Python/shell no projeto. A alteração do workflow acrescenta somente o preflight Linux; seu resultado real pertence à CI do novo head. Logs, manifests e anotação original foram guardados privadamente; nada deles foi publicado integralmente.

## Limites e próximo gate

O patch offline foi qualificado, commit 5a5da7d; a issue permanece aberta até a CI remota completa passar nos três jobs. Outro hotspot pode permanecer. Caso isso ocorra, investigar a etapa concreta, conservando critérios e prazo. A intermitência anterior de retorno ao iOS na issue 38 não foi encerrada. Wi-Fi, carga/gauge e goal principal continuam pendentes; esta rodada não fez novo boot/DFU/PIN.

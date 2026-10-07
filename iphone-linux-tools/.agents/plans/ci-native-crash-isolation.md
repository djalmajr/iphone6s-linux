# CI Linux — isolamento de crashes sintéticos

## Contexto

Headec09d4f: Mac e Windows passaram; Ubuntu foi cancelado na etapa Synthetic tests pela anotação "maximum execution time of15m0s" do run37562583685. A suíte não tem aprovação remota Linux. Logs desse job ainda não disponíveis nas primeiras tentativas; preservar o resultado e investigar, sem aumentar prazos ou aceitar timeout como kill. A intermitência anterior#38 permanece distinta.

Na VM dedicada, RLIMIT_CORE=0 não impediu o handler piped Apport e um mutant teve timeout; PR_SET_DUMPABLE somente no processo corrigiu aquele caller. A fonte Linux explicita que pipes ignoram o limite normal. Isso oferece uma hipótese de custo dos crashes repetidos; não demonstra a causa do timeout GitHub. Medir um gate nativo existente com mesmos inputs, antes/depois de core_pattern simples na VM, restaurando a configuração original em finally.

## Decisão

- **Escolha:** condicionar o isolamento de core dumps à CI GitHub-hosted Linux. Se core_pattern for pipe, trocar para o nome simplescore e verificar readback. As fixtures já configuram RLIMIT_CORE=0; isso passa a impedir crash handlers externos. Fora desse ambiente, recusar antes de ler/escrever. Registrar o handler e manter testes/prazos.
- **Motivo:** cada SIGABRT esperado não deve iniciar ferramenta externa da máquina. Runtime native deve refletir compilation/assertion, sem depender de Apport. Mac e runners self-hosted ficam fora da admissão do script.
- **Alternativas:** aumentar15 minutos oculta custo/espera; mudar todos os fixtures aumenta a fatia; sysctl no Mac ou VM de produção sai do escopo. Rejeitadas. Se a medição não sustentar benefício, instrumentar a etapa e investigar o hotspot antes de alterar runtime.
- **Reversão:** baixo, helper/step só da CI ephemeral; experimento na VM exige restore exato do baseline.
- **Status:** implementação justificada pela medição na VM. Mesmo gate de61 cenários/14 mutações:19,508s com pipe,0,717s com nome simplescore; três inputs idênticos e restore exato do handler confirmados em finally. Essa medição não prova a causa inteira do timeout GitHub. Publicar a correção com os commits MSI locais já qualificados após gates offline para produzir nova prova remota; cancelamento anterior não conta como green.

## Arquivos — fatia de até quatro públicos

- Este plano.
- `.github/workflows/ci.yml`: preflight somente Linux, antes de testes sintéticos;15 minutos permanece.
- `iphone-linux-tools/scripts/ci/isolate-native-crashes.sh`: três guardsGitHub Actions/Linux/github-hosted, leitura/efeito/readback, sem config persistente ou instalação.
- `iphone-linux-tools/tests/test_ci_native_crashes.py`: sysctl/sudo mockados, sem tocar host real; negativos de ambiente, erros, ausência de efeito e caminho sem pipe.

## Tarefas

- [x] Registrar [issue41](https://github.com/djalmajr/iphone6s-linux/issues/41) com run/anotação, sem atribuir causa não medida.
- [x] Conferir GITHUB_ACTIONS/RUNNER_OS/RUNNER_ENVIRONMENT na documentação oficial; medir fixture nativa com inputs intactos na VM e restore obrigatório.
- [x] Implementar helper/step com benefício medido; recusa antes de qualquer efeito fora da admissão GitHub Actions/Linux/github-hosted. Leitura/write/readback obrigatórios; setter usa sudo não interativo.
- [x] Bash syntax/ShellCheck, AST/lint fatal passaram no Mac; fixtures15 cenários/8 mutações por AssertionError passaram no Mac e ARM64. Três inputs idênticos; testes usam somente mocks e mantêm handler real da VM intacto. Não contar import/timeout/syntax como kill.
- [x] Public guard/commit/push na branch e CI remota completa: [run 37566057928](https://github.com/djalmajr/iphone6s-linux/actions/runs/37566057928), head19ffb03, os três jobs passaram em 2026-10-07T03:28:36Z; preflight Ubuntu success/Mac skipped. Prazo de15 minutos intacto. Evidência sanitizada atualizada; issue41 pode ser encerrada.

Código qualificado:5a5da7d. [Reprodução e prova](../../docs/CI_NATIVE_CRASHES.md). Publicação conjunta com os dois commits MSI locais qualificados; só encerrar issue41 com os três jobs remotos passando. Não repetir gates de código/ABI intactos apenas pela mudança da política de CI.

## Verificação

Nenhuma instalação ou configuração global do Mac, telefone, cloud/account ou main. Não usar o helper público na VM local: experimento usa runner privado com backup/finally; testes do helper usam somente mocks. Não reduzir testes, assertions, mutation criteria ou limite de15 minutos. CI pode ainda apresentar outro hotspot; só concluir com três jobs passados no head novo. Wi-Fi/energia e goal principal continuam abertos, sem novo reboot/DFU/PIN.

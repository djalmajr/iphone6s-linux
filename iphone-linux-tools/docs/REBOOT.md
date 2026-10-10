# Retorno verificável ao iOS — #21

## Fechamento do piloto corrigido

Fase de cinco arquivos: este documento, `SOURCE-CHAIN-PILOT.md`, seu registro JSON, `STATUS.md` e `PR-REVIEW.md`. Atualizar o gate físico somente depois de saída0/markers/USB; registrar CI terminal, bateria e limites. Código inalterado nesta fase; testes da correção são reutilizados. Rollback Linux continua exigindo novo boot coordenado.

## Correção após piloto da cadeia de fonte — 2026-10-01

Plano desta fase (cinco arquivos): este documento, `return_ios.py`, `test_return_ios.py`, `run_return_ios_mutations.py` e `SOURCE-CHAIN-PILOT.md`. O Linux 7.2 iniciou no N71, com driver `apple-watchdog` vinculado. O comando antigo publicou um snapshot íntegro e perdeu o enlace antes de confirmar seu marcador de sync; retornou falha, embora o Mac depois tenha confirmado iOS. A causa do marcador perdido ainda não foi isolada. O operador depois confirmou ausência de intervenção física.

Separar sync e reboot em duas chamadas SSH estritas: exigir saída 0, prazo cumprido e marcador exclusivo da primeira chamada antes de enviar reboot. A segunda pode perder o enlace; somente enumeração USB/modelo e ausência do gadget confirmam sucesso. Não acrescentar espera artificial no telefone nem relaxar o gate de sync. Reproduzir retorno rápido sem saída na fixture, falhas de sync sem reboot, resposta perdida com código 255 e ausência de iOS; atualizar mutações para a sequência observável. O piloto do CLI corrigido ficará pendente até nova execução física.

Implementado: `BACKUP_VERIFIED`, depois `SYNC_VERIFIED` numa conexão concluída, então pedido separado de reboot e confirmação USB. O teste novo reproduziu a falha antiga por assertion antes da mudança. Baseline de 19 casos passou; 11/11 mutações rejeitadas por assertions, incluindo sync/reboot combinados e sync desconectado. Runner agora recusa skips, erro de execução e mutantes com erro de sintaxe. AST, Flake8 fatal e links locais passaram; sem typechecker configurado. O shim Python 3.12 não tinha versão selecionada; lint foi executado pelo Python 3.12.6 já instalado, sem mudar configuração nem instalar pacote.

O operador confirmou console e retorno espontâneo, sem Power/Home, e o Mac confirmou iOS `iPhone8,1`; isto comprova reboot da cadeia de fonte, apesar da saída 1 do CLI antigo. Binding `apple-watchdog` observado em N71, sem abrir o dispositivo watchdog. [Piloto e reprodução](SOURCE-CHAIN-PILOT.md). Naquele checkpoint, novo CLI e rollback Linux aguardavam validação física; o fechamento abaixo registra o CLI e CI concluídos. Rollback Linux permanece pendente.

## Contexto e plano

O init mínimo não atende `reboot` comum. O runbook já documenta `sync; reboot -f`; saída SSH, timeout ou desaparecimento do gadget não provam retorno ao iOS. Implementar um comando separado, com a identidade do perfil atual, backup obrigatório e confirmação USB limitada por prazo. Nenhum registrador, driver, NAND ou método novo de reset será alterado.

Arquivos desta fase: `scripts/host/return_ios.py`, `tests/test_return_ios.py`, `tests/run_return_ios_mutations.py`, `.github/workflows/ci.yml` e este documento. A CI descobre os testes Python e executa também as mutações de retorno em ambos os sistemas.

- [x] Confirmar SSH estrito; recusar outros dispositivos iOS USB antes de agir.
- [x] Salvar snapshot pelo restaurador existente, verificar hash/escopo e abortar antes do reboot se falhar.
- [x] Executar sync antes de `reboot -f`; confirmar somente um dispositivo USB `iPhone8,1` e ausência do gadget Linux.
- [x] Limitar espera e encerrar grupos de processos próprios em timeout/interrupção; não imprimir identificadores USB nem saída de dependências.
- [x] Executar testes sintéticos e mutações; lint/parsing; publicar e observar CI.
- [x] Validar o comando em piloto físico coordenado; investigar cadeia N71/A9 sem inferir suporte de outro SoC.

## D1. Verificação pelo resultado observado

- **Decisão:** snapshot obrigatório, SSH do perfil selecionado e `reboot -f` já documentado; confirmação USB depois do pedido.
- **Por quê:** elimina falso sucesso por saída SSH e mantém recuperação dos arquivos em RAM.
- **Alternativas:** comando comum não atende PID 1; forçar outro reset requer suporte de hardware ainda não demonstrado; reinício manual continua fallback.
- **Reverter:** baixo; deixar de usar o comando e seguir o runbook manual.
- **Status:** implementada e comprovada em piloto físico da cadeia de fonte; casos/mutações e CI aprovados.

## Operação

Encerre escritores/sessões e proxies LAN próprios antes de executar. O snapshot não é transacional com autores concorrentes, nem salva estado vivo de processos. Mantenha o perfil correspondente ao Linux que está rodando; selecionar outro perfil não muda a identidade do telefone.

```bash
cd iphone-linux-tools
# IPHONE_LINUX_PROFILE continua selecionado quando se usa a candidata.
python3 scripts/host/return_ios.py --wait 90
```

O comando exige as ferramentas já utilizadas no Mac: OpenSSH, `ioreg`, `idevice_id` e `ideviceinfo`. Enumera somente USB (`idevice_id -l`), não dispositivos da rede. Recusa uma enumeração iOS prévia para evitar confundir outro aparelho com o servidor. Não instala dependências, pede senha, modifica rede ou remove snapshots.

Sucesso exige `RETURN_IOS_VERIFIED`. `RETURN_IOS_FAILED` exige inspecionar o estado; não repetir boot ou descartar dados por timeout. O snapshot já concluído é preservado. Para fallback: Power + Home até maçã, soltar ambos, depois confirmar iOS pelo USB. Não são necessários comandos no display.

A observação confirma iOS após o pedido, sem provar causalidade exclusiva quando alguém usa os botões durante a espera. Não altera a investigação de carregamento #2 nem libera estabilidade prolongada #8. Na rodada anterior, ProductType foi confirmado após o pedido, mas a intervenção manual ainda não havia sido esclarecida. Rollback Linux #12 continua exigindo novo DFU com a outra imagem.

## Verificação local

Python 3.12.6: baseline de **17 testes** passou em cópia pública descartável; **9/9 mutações** rejeitadas por assertions, sem contato com o telefone. Snapshots reais de dados sintéticos exercitam o restaurador existente: conteúdo/modo privado, backup com saída de erro após publicação e arquivo corrompido depois da publicação. SSH/USB são executáveis sintéticos; isso não comprova reboot real.

Também foram executados timeout de processo real e SIGTERM durante backup sintético, verificando encerramento do SSH próprio e ausência de reboot. As mutações cobrem gate de backup, integridade, marcador de sync, modelo iOS, unicidade USB, reaparecimento Linux, perda do `-f`, alias do perfil e cancelamento restrito somente ao pai. O primeiro ensaio revelou dois controles fracos, corrigidos com fixtures específicas; o prazo de um segundo dos executáveis sintéticos no macOS foi ajustado para dez, sem alterar o prazo operacional de 90 segundos.

AST, Flake8 fatal, Pyflakes, YAML e diff-check passaram; `--help` executado. Não há typechecker configurado. Gates anteriores não afetados reutilizados; a CI repetirá a suíte pública e ambos os runners de mutações. Não houve novo pacote no Mac, alteração no telefone, banco, credencial ou configuração global nesta fase. O comando acrescenta um backup manual antes do retorno; esse custo em disco/rede faz parte da proteção dos arquivos em RAM.

Reprodução a partir da raiz:

```bash
python3 iphone-linux-tools/tests/run_return_ios_mutations.py
python3 -m flake8 --select E9,F63,F7,F82 \
  iphone-linux-tools/scripts/host/return_ios.py \
  iphone-linux-tools/tests/test_return_ios.py \
  iphone-linux-tools/tests/run_return_ios_mutations.py
```

## Inspeção estática do N71

O DTB preservado foi lido após conferir SHA-256 `b25b2b748d6f934d3b4ed51d9906ae86ae5e031756bfe9009073a4dea7537f58`. As duas CPUs usam `spin-table`; há PMGR S8000 e PMU Twister, sem um nó PSCI observado nesse DTB de entrada. Isso não identifica o método efetivo depois dos ajustes do bootloader. O kernel conferiu o SHA-256 registrado em [KERNEL-VERIFY.md](KERNEL-VERIFY.md); a busca estática por `IKCFG_ST` não encontrou configuração embutida. Seu metadado de origem continua `-dirty`: não vincular um driver específico a esse binário sem prova adicional.

As fontes `kboot.c`, `pmgr.c` e `smp.c` foram lidas diretamente do commit m1n1 fixado no build, sem execução. Reset de periférico PMGR e reset de núcleo secundário não devem ser tratados como reinício completo do aparelho. Essa inspeção é parcial; não encerra o critério de cadeia N71 da #21. [Fonte kboot](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/kboot.c), [PMGR](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/pmgr.c), [SMP](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/smp.c).

Uma busca adicional no mesmo DTB identificou `/soc/watchdog@2102b0000`, compatibles `apple,s8000-wdt` e `apple,wdt`. O m1n1 fixado ajusta `cpu-release-addr`; o ajuste SMC de reboot lido é condicionado a outro compatible, `apple,t8015-smc-reboot`. No fork oficial do kernel, commit consultado `6831bc701a6ce059e71e5aaa9488c9195bea6927`, o driver `apple_wdt.c` corresponde a `apple,wdt`, fornece callback de restart e registra prioridade 128. Essa correspondência é uma hipótese para o caminho efetivo, não prova de driver compilado/carregado no APK preservado. [Driver consultado](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/watchdog/apple_wdt.c).

Próxima prova física: ler somente identidade/driver do watchdog em sysfs, logs pertinentes e DT efetivo; relacionar ao kernel selecionado. Não abrir `/dev/watchdog` nem escrever controles durante a investigação. O comando operacional usa o reboot de kernel já documentado, sem introduzir outro reset de hardware.

## Prova remota e gate nativo parcial

[CI da PR em acdb28b](https://github.com/djalmajr/iphone6s-linux/actions/runs/36800979276) e [CI do push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36800976716) passaram. Cada sistema executou 79 testes: 70 aprovados e nove skips explícitos de VM/artefatos privados. As 20 mutações de perfil e nove de reboot foram rejeitadas nos dois sistemas; guard, lint/sintaxe e ShellCheck Linux passaram. Logs privados preservados, sem publicar imagens/chaves.

No Mac, com ProductType iOS confirmado, o CLI novo foi executado com o perfil privado correto e recusou a operação antes de SSH/backup/reboot: saída 1, gate de iOS pré-existente confirmado. Esse teste é nativo, mas comprova apenas a recusa segura. Nenhum reboot Linux pelo novo comando foi realizado nesta fase. #21 continua aberta para cadeia N71 e piloto físico completo; #12 conserva rollback Linux pendente. Goal ativo, sem merge ou nova instalação no Mac.


## Resultado do CLI corrigido — 2026-10-01

Novo boot da mesma cadeia explícita terminou com saída0, restore e console confirmado. SSH estrito confirmou kernel7.2.0 e binding apple-watchdog; HTTP respondeu. Uptime antes do comando:116,23s, não duração final da sessão. O CLI corrigido salvou/verificou snapshot, recebeu sync com marcador e saída0 numa conexão separada, pediu reboot e confirmou iOS iPhone8,1 USB sem gadget Linux. Saída final0 e markers BACKUP_VERIFIED/SYNC_VERIFIED/RETURN_IOS_VERIFIED; nenhuma intervenção física solicitada durante o retorno.

Bateria iOS96% antes e94% depois, carregamento ativo na leitura posterior. Comparação inclui DFU/boot/reboot e não libera #2/#8. Driver vinculado e resultado do reboot são observações do N71; não comprovam recuperação de travamento, boot autônomo ou segurança da alimentação. Fallback Power+Home permanece documentado para falhas.

CI em6386b2b: [PR](https://github.com/djalmajr/iphone6s-linux/actions/runs/36940701485) e [push](https://github.com/djalmajr/iphone6s-linux/actions/runs/36940697946) terminais verdes. Gates da correção:19 casos locais/11 mutações, além da matriz pública em Ubuntu/macOS e cliente DNS Windows. Nenhum novo pacote/configuração global/NAND/merge; snapshots privados preservados. Critérios da #21 cumpridos para a cadeia de fonte testada; rollback Linux #12 continua separado. [Evidência](evidence/source-chain-pilot.json).

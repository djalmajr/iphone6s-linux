# Herdr opcional no mini servidor — #13

## Plano dos pilotos físicos

Fase de até cinco documentos: este contrato, `docs/evidence/herdr-physical.json`, `STATUS.md`, `EXECUCAO.md` e `PR-REVIEW.md`. Reutilizar código/testes/CI do launcher sem nohup; não instalar ou atualizar Herdr no Mac. O operador não precisa ler nem operar o console.

Primeiro boot curto da cadeia de fonte com snapshot final: conferir SSH/HTTP e versão/hash Herdr, iniciar/habilitar a sessão dedicada, aprender CLI do binário instalado e obter IDs reais. Testar Bash pelo painel, início repetido sem duplicação e TUI por SSH num PTY próprio do Mac; desconectar/reconectar somente esses clientes e conferir mesmo painel/dados. Salvar snapshot real com o marcador declarativo e retornar ao iOS pelo comando comprovado.

Segundo boot curto com restore desse snapshot: exigir autostart do wrapper, novo servidor efêmero sem restauração de processos/sockets, marcador válido e reconexão TUI pelo Mac. Salvar snapshot e encerrar somente sessão/clientes próprios antes do retorno ao iOS. Se houver falha, preservar logs/snapshot e não marcar o critério físico. Não abrir agentes nem alterar a sessão principal do Herdr no Mac. Alimentação/24h, perfis de clientes LAN e hardware permanecem gates separados.

## Plano e contrato

Automação autorizada dentro do backlog #17. A implementação usa Herdr 0.9.1 já preservado, sem instalar ou atualizar software no Mac. Arquivos: `scripts/host/herdr.py`, integração em `scripts/host/iphone-linux.sh`, regressões em `tests/test_herdr_start.py` e este documento.

- [x] Oferecer `herdr start`, `status`, `enable`, `disable`, `restart --confirm-stop` e attachment pelo wrapper.
- [x] Serializar início/reinício por lock efêmero; tentativas repetidas conservam o servidor e os painéis existentes.
- [x] Iniciar Bash em `/srv/data` numa sessão própria `iphone-server`, sem agentes ou comandos restaurados.
- [x] Restaurar apenas a opção de iniciar, sem copiar credenciais, sockets, histórico ou estado de processos.
- [x] Validar duplicação, seleção SSH, opt-in e restart em testes; conferir servidor real na VM dedicada.
- [x] Validar novo boot e reconexão física pelo macOS: dois boots com quatro attachments TUI, marcador restaurado e autostart comprovados; evidência abaixo.

## D1. Sessão separada e configuração fixa

- **Decisão:** sessão `iphone-server`, com configuração/estado em `/run/iphone-herdr`; persistência somente do marcador `/srv/data/herdr/autostart`, contendo `1`.
- **Por quê:** evita usar a sessão manual histórica `iphone-linux` e impede restaurar comandos de agentes, plugins, máquinas SSH ou credenciais através da configuração desta automação. O wrapper inicia a sessão após autenticar SSH e restaurar os arquivos, somente se o marcador estiver presente.
- **Alternativas:** restaurar TOML/layout completo permitiria executar configurações adicionais; inserir o servidor no init obrigaria reconstruir a imagem e ocorreria antes do restore. Ambas têm custo e escopo maiores.
- **Reverter:** baixo; `disable` desativa o próximo início automático. Encerrar a sessão requer o comando explícito documentado, sem parar o Herdr do Mac.
- **Onde:** #13, os arquivos do plano acima.
- **Status:** implementada, validada localmente/na VM e em dois pilotos físicos com SSH/TUI pelo Mac. Iniciar no boot assistido do wrapper não torna o aparelho independente do Mac/DFU.

## Proveniência

Binário ARM64 preservado: release oficial [v0.9.1](https://github.com/herdrdev/herdr/releases/tag/v0.9.1), SHA-256 `f4ccf4de745f2cb9a39a983e9ba3703dad50ec2a58dea83026ceab721bbd8d9e`. Fonte do tag: commit `065ef9d6a531c49fb8bee7e818ef837065b21ee9`. A ajuda instalada e o código confirmam `herdr --session NOME server` e `HERDR_STARTUP_CWD`, que cria workspace apenas quando vazio: [bootstrap](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/server/headless/bootstrap.rs), [sessões](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/session.rs).

A versão do Mac também foi conferida como 0.9.1 nesta rodada. Conferir compatibilidade antes de atualizar qualquer cliente; não parar servidores alheios para resolver incompatibilidade.

## Uso pelo macOS

Com Linux ativo e a seleção `IPHONE_LINUX_PROFILE` correspondente, execute da pasta de ferramentas:

```bash
bash scripts/host/iphone-linux.sh herdr start
bash scripts/host/iphone-linux.sh herdr status
bash scripts/host/iphone-linux.sh herdr
```

`start` cria servidor/painel quando ausente; chamadas repetidas mantêm a sessão. O último comando abre a interface pelo SSH e deixa o Bash disponível após desconectar. Os testes observaram clientes CLI separados na VM e quatro attachments TUI pelo SSH no telefone em dois boots, com Bash e reconexão comprovados. A sessão manual histórica `iphone-linux` continua separada; pode ser acessada explicitamente pelo shell do telefone.

Para iniciar automaticamente após os próximos boots assistidos:

```bash
bash scripts/host/iphone-linux.sh herdr enable
bash scripts/host/iphone-linux.sh backup
bash scripts/host/iphone-linux.sh boot --restore ID_DO_SNAPSHOT
```

O último comando é executado após retornar ao iOS e fazer novo DFU. Sem restore, o marcador em RAM desaparece e o início automático permanece desabilitado. O wrapper usa SSH estrito, restaura arquivos, verifica HTTP e depois consulta o marcador. A opção não inicia Herdr sozinho ao apertar Power, não instala serviço no Mac e não exige ler o console do iPhone. Esta implementação não reconstrói kernel/initramfs nem troca identidades.

```bash
bash scripts/host/iphone-linux.sh herdr disable
bash scripts/host/iphone-linux.sh herdr restart --confirm-stop
```

`disable` remove a opção para o próximo boot e preserva o trabalho em execução. Para conservar essa mudança após reboot, salve outro snapshot. `restart --confirm-stop` encerra os processos da sessão `iphone-server` e abre um novo servidor, conservando o layout volátil; comandos/agentes não são retomados pela configuração gerada. Nenhum servidor do Mac ou a sessão manual histórica é parado. PID/socket/locks não são restaurados do snapshot.

## Falhas e recuperação

Herdr precisa do binário fixado, Bash, `setsid` e do enlace SSH autenticado. O filho ignora HUP antes de executar setsid, com stdin em `/dev/null` e saída no log privado; não depende de `nohup`, ausente no BusyBox da candidata. Os applets e o início foram conferidos na VM com esse BusyBox; os dois pilotos físicos abaixo também comprovaram novo boot/reconexão pelo SSH/TUI. Hash inesperado aborta antes de executar o binário. Erro ou formato desconhecido de status não autoriza outro servidor. Um início sem confirmação retorna erro e deixa logs privados em `/run/iphone-herdr/start.log`; consulte `herdr status` antes de repetir.

Lock ativo/interrompido recusa outra operação. Não apagar o lock enquanto a operação estiver viva. Uma sessão Linux nova recria `/run` e elimina o lock; os arquivos de trabalho e a opção são recuperados pelo snapshot. Links ou marcadores fora do formato aceito são recusados. Alterações concorrentes do mesmo usuário na árvore não são suportadas; o lock serializa apenas este helper. Herdr mantém os próprios sockets para impedir servidores simultâneos da mesma sessão.

## Verificação da implementação inicial — histórica

- Onze regressões locais passaram: opt-in, duplicação, restart explícito, disable, links/lock, hash, erro de status, transporte SSH e limpeza antes de attachment.
- Doze mutações em cópias descartáveis foram recusadas: hash, marcador, lock, duplicação, opt-in, confirmação, escopo de stop, lock de attachment, stop indevido no disable, erro de status tratado como ausência, hardlink do marcador e erro SSH ignorado.
- VM Ubuntu ARM64: Herdr oficial iniciou com um painel Bash; a saída incluiu a versão Bash 5.2; novos clientes CLI conservaram o ID do painel; restart voltou a responder em Bash; `/run` sintético removido e marcador conservado recriaram um painel.
- Sessão própria encerrada, fixture removida e VM devolvida a `Stopped`, sem mounts. Nenhum pacote instalado, alteração de banco, credenciais novas ou mudança global de rede.
- Flake8 fatal, sintaxe Bash e ShellCheck dos scripts gerados passaram. Não há typechecker configurado. CI do código `5f60dec`: quatro jobs Ubuntu/macOS, cada um com 133 testes (124 aprovados, nove skips); comentários de mutação posteriores preservam o AST do teste. CI e suíte geral estão registrados na [evidência](evidence/herdr-autostart.json).

Naquele checkpoint, a VM não comprovava novo boot no iPhone ou reconexão TUI por SSH. Esses gates da #13 foram cumpridos depois, conforme o piloto abaixo; carga sustentada/estabilidade e proveniência do legado continuam separadas.

## Correção do runtime sem nohup — #29

O BusyBox da candidata tem SHA-256 `52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933`, sem applet nohup e com setsid. A inspeção leu somente arquivos do initramfs protegido; BusyBox e Herdr conferidos foram executados somente na VM. O launcher original falhou com os applets reais no PATH, por uma asserção de startup. O teste VM anterior usava nohup do guest, portanto não cobria essa dependência. Nenhuma instalação ou rebuild foi usado para ocultar a falta do utilitário.

Código corrigido em `d5e4597`: filho com HUP ignorado e exec/setsid, preservando redireções, sessão, lock e critérios de prontidão. Regressão sem nohup envia SIGHUP real pelo peer antes de confirmar startup; remover a proteção ou reintroduzir nohup causa falha de asserção. Doze testes Herdr e 2/2 mutações passaram no Mac, assim como a suíte completa de 172 casos (164 aprovados/oito skips), Flake8 fatal, sete scripts Bash/ShellCheck, YAML/diff e guard público. Sem typechecker configurado.

VM com Herdr oficial e PATH do BusyBox da candidata: painel Bash 5.2, mesmo painel entre clientes CLI separados, restart e recriação pelo marcador passaram. Usa Bash/bibliotecas do guest, não executa o initramfs completo nem comprova SSH/TUI no telefone. Sessão própria encerrada, fixture/processos próprios ausentes e VM parada sem mounts. Nenhuma chave, snapshot, dado real ou imagem completa foi transferido; nenhum pacote instalado no Mac/guest.

[Evidência e limites](evidence/herdr-detachment.json). CI do código terminal verde: [PR 36851283400](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851283400) e [push 36851277105](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851277105). Os quatro jobs Ubuntu/macOS executaram 172 casos (163 aprovados/nove skips) e detectaram ambas as mutações de detachment; logs conferidos. Naquele checkpoint o gate físico da #13 permanecia aberto; o piloto abaixo o cumpriu posteriormente. Reproduzir o contrato local sem aparelho:

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -p test_herdr_start.py -v
python3 iphone-linux-tools/tests/run_herdr_detach_mutations.py
```


## Piloto físico concluído — 2026-10-01 (America/Maceio)

Dois boots assistidos com Pongo de fonte e kernel `7.2.0-iphone6s-source`, USB-A traseiro, wrapper saída 0, SSH estrito/HTTP e console confirmado. Herdr ARM64 oficial 0.9.1/hash fixado, Bash e sessão própria `iphone-server`. [Registro sanitizado](evidence/herdr-physical.json). Os logs/ANSI, snapshots e IDs reais permanecem privados em `runtime/herdr-physical-20261001/`.

Primeiro boot: sem autostart inicialmente; `enable` iniciou a sessão e gravou marcador. Um único painel Bash em `/srv/data` executou comando com saída `HERDR_NATIVE_BASH_OK` e salvou arquivo `herdr/reconnect-proof.txt`. Um PTY próprio do Mac anexou a TUI via SSH, capturou essa saída e foi desconectado; novo attachment exibiu a mesma saída com o mesmo painel/terminal. `start` respondeu `HERDR_ALREADY_RUNNING`, sem duplicar painéis. Snapshot real preservou arquivo e marcador `1\n`, modo 600.

Segundo boot: restore do snapshot, `HERDR_STARTED` emitido pelo wrapper antes de attachment/start manual. Arquivo e marcador conferidos por SSH; terminal novo comparado ao primeiro boot, confirmando recriação do servidor efêmero. Duas novas conexões TUI comprovaram Bash/arquivo, desconexão/reconexão com identidade do terminal conservada dentro deste boot e ausência de duplicação. Não se restauraram processos ou sockets.

Nos dois pilotos, somente clientes próprios e a sessão do telefone foram encerrados. Snapshot/sync/retorno ao iOS pelo CLI terminaram 0, com USB `iPhone8,1` e gadget Linux ausente. Uptime observado antes do retorno: 342,35 s e 343,71 s; não são durações totais do piloto. Leituras iOS: 100→92% e 92→92%, carregamento ativo ao final de ambos; preparação/reboots e variação do indicador impedem inferir carga sustentada. Brilho reduzido a 256/2047, sem operação exigida no console. Herdr principal do Mac intacto, sem instalação, agentes ou alterações globais.

Código operacional não mudou nesta fase. Gates do launcher sem nohup e CI já registrados continuam válidos; CI do código de retorno em `6386b2b` passou nos runs PR36940701485/push36940697946. Essa CI não representa prova física ou CI deste documento. #2/#8, hardware, política DNS/clientes e revisão integral #16 continuam pendentes.

### Reproduzir Bash, reconexão e restore

Execute da pasta `iphone-linux-tools`, com perfil privado e Pongo selecionados conforme [PROFILES.md](PROFILES.md). Não copie IDs deste piloto. Faça boot com o wrapper/DFU manual e restore de um snapshot real verificado; use `herdr enable`, `backup` e `boot --restore ID_DO_SNAPSHOT` como acima para o segundo boot.

1. Abra `bash scripts/host/iphone-linux.sh herdr` num terminal próprio do Mac. No Bash da TUI, execute:

   ```bash
   umask 077
   printf '%s%s\n' 'HERDR_' 'NATIVE_BASH_OK' > /srv/data/herdr/reconnect-proof.txt
   cat /srv/data/herdr/reconnect-proof.txt
   uname -r
   pwd
   ```

2. Em outro terminal próprio, obtenha os IDs reais do telefone e salve a resposta num arquivo privado. A preamble fixa/verifica binário e sessão; não use IDs do Herdr do Mac:

   ```bash
   python3 - <<'PYCODE'
   import sys, subprocess
   sys.path.insert(0, 'scripts/host')
   import device_profile, herdr
   command = device_profile.ssh_options() + ['root@172.16.42.1', '/bin/bash -se']
   result = subprocess.run(command, input=herdr.PREAMBLE + 'phone_herdr pane list\n',
                           text=True, capture_output=True, timeout=12, check=True)
   print(result.stdout)
   PYCODE
   ```

3. Desconecte somente o cliente SSH/TUI aberto para esse teste, fechando seu terminal dedicado. Rode `herdr start`: deve responder `HERDR_ALREADY_RUNNING`. Abra a TUI novamente e confira a saída/arquivo. Repita a consulta de IDs: deve existir um painel com os mesmos `pane_id`/`terminal_id` dentro do boot.
4. Salve `backup`, retorne com `python3 scripts/host/return_ios.py --wait 60` e faça novo boot/restore. Confirme `HERDR_STARTED` no wrapper antes de iniciar manualmente. Confira arquivo/marker e novo `terminal_id`; repita attachment/desconexão. O terminal deve ser conservado entre clientes desse boot, diferente do boot anterior.
5. Salve snapshot final e retorne ao iOS pelo helper. O helper exige backup/sync/USB verificados. Não copie logs/ANSI brutos para Git: podem conter dados de terminal. Nenhum comando desta receita controla ou para o servidor principal Herdr do Mac.

A captura automatizada usou quatro PTYs próprios de 30×110, janela de 8 s por attachment e término somente do grupo criado por cada cliente. A prova exige saída Bash renderizada e leitura independente do arquivo; contar bytes ANSI sozinho não indica sucesso. Os resultados são os registrados no JSON. A receita interativa acima reproduz os mesmos checkpoints sem depender do console do iPhone.

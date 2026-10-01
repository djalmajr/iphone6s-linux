# Herdr opcional no mini servidor — #13

## Plano e contrato

Automação autorizada dentro do backlog #17. A implementação usa Herdr 0.9.1 já preservado, sem instalar ou atualizar software no Mac. Arquivos: `scripts/host/herdr.py`, integração em `scripts/host/iphone-linux.sh`, regressões em `tests/test_herdr_start.py` e este documento.

- [x] Oferecer `herdr start`, `status`, `enable`, `disable`, `restart --confirm-stop` e attachment pelo wrapper.
- [x] Serializar início/reinício por lock efêmero; tentativas repetidas conservam o servidor e os painéis existentes.
- [x] Iniciar Bash em `/srv/data` numa sessão própria `iphone-server`, sem agentes ou comandos restaurados.
- [x] Restaurar apenas a opção de iniciar, sem copiar credenciais, sockets, histórico ou estado de processos.
- [x] Validar duplicação, seleção SSH, opt-in e restart em testes; conferir servidor real na VM dedicada.
- [ ] Validar novo boot e reconexão física pelo macOS antes de concluir #13.

## D1. Sessão separada e configuração fixa

- **Decisão:** sessão `iphone-server`, com configuração/estado em `/run/iphone-herdr`; persistência somente do marcador `/srv/data/herdr/autostart`, contendo `1`.
- **Por quê:** evita usar a sessão manual histórica `iphone-linux` e impede restaurar comandos de agentes, plugins, máquinas SSH ou credenciais através da configuração desta automação. O wrapper inicia a sessão após autenticar SSH e restaurar os arquivos, somente se o marcador estiver presente.
- **Alternativas:** restaurar TOML/layout completo permitiria executar configurações adicionais; inserir o servidor no init obrigaria reconstruir a imagem e ocorreria antes do restore. Ambas têm custo e escopo maiores.
- **Reverter:** baixo; `disable` desativa o próximo início automático. Encerrar a sessão requer o comando explícito documentado, sem parar o Herdr do Mac.
- **Onde:** #13, os arquivos do plano acima.
- **Status:** implementada, validada localmente/na VM; piloto físico pendente. Iniciar no boot assistido do wrapper não torna o aparelho independente do Mac/DFU.

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

`start` cria servidor/painel quando ausente; chamadas repetidas mantêm a sessão. O último comando abre a interface pelo SSH e deixa o Bash disponível após desconectar. Os testes desta automação observaram clientes CLI separados na VM; a reconexão SSH/TUI no telefone ainda precisa do piloto físico. A sessão manual histórica `iphone-linux` continua separada; pode ser acessada explicitamente pelo shell do telefone.

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

Herdr precisa do binário fixado, Bash, `setsid` e do enlace SSH autenticado. O filho ignora HUP antes de executar setsid, com stdin em `/dev/null` e saída no log privado; não depende de `nohup`, ausente no BusyBox da candidata. Os applets e o início foram conferidos na VM com esse BusyBox; novo boot/reconexão física continuam pendentes. Hash inesperado aborta antes de executar o binário. Erro ou formato desconhecido de status não autoriza outro servidor. Um início sem confirmação retorna erro e deixa logs privados em `/run/iphone-herdr/start.log`; consulte `herdr status` antes de repetir.

Lock ativo/interrompido recusa outra operação. Não apagar o lock enquanto a operação estiver viva. Uma sessão Linux nova recria `/run` e elimina o lock; os arquivos de trabalho e a opção são recuperados pelo snapshot. Links ou marcadores fora do formato aceito são recusados. Alterações concorrentes do mesmo usuário na árvore não são suportadas; o lock serializa apenas este helper. Herdr mantém os próprios sockets para impedir servidores simultâneos da mesma sessão.

## Verificação da implementação inicial — histórica

- Onze regressões locais passaram: opt-in, duplicação, restart explícito, disable, links/lock, hash, erro de status, transporte SSH e limpeza antes de attachment.
- Doze mutações em cópias descartáveis foram recusadas: hash, marcador, lock, duplicação, opt-in, confirmação, escopo de stop, lock de attachment, stop indevido no disable, erro de status tratado como ausência, hardlink do marcador e erro SSH ignorado.
- VM Ubuntu ARM64: Herdr oficial iniciou com um painel Bash; a saída incluiu a versão Bash 5.2; novos clientes CLI conservaram o ID do painel; restart voltou a responder em Bash; `/run` sintético removido e marcador conservado recriaram um painel.
- Sessão própria encerrada, fixture removida e VM devolvida a `Stopped`, sem mounts. Nenhum pacote instalado, alteração de banco, credenciais novas ou mudança global de rede.
- Flake8 fatal, sintaxe Bash e ShellCheck dos scripts gerados passaram. Não há typechecker configurado. CI do código `5f60dec`: quatro jobs Ubuntu/macOS, cada um com 133 testes (124 aprovados, nove skips); comentários de mutação posteriores preservam o AST do teste. CI e suíte geral estão registrados na [evidência](evidence/herdr-autostart.json).

VM não comprova novo boot no iPhone, carga sustentada ou reconexão TUI por SSH. #13 conserva esse último gate aberto; #2/#8/#12/#21 mantêm suas pendências físicas.

## Correção do runtime sem nohup — #29

O BusyBox da candidata tem SHA-256 `52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933`, sem applet nohup e com setsid. A inspeção leu somente arquivos do initramfs protegido; BusyBox e Herdr conferidos foram executados somente na VM. O launcher original falhou com os applets reais no PATH, por uma asserção de startup. O teste VM anterior usava nohup do guest, portanto não cobria essa dependência. Nenhuma instalação ou rebuild foi usado para ocultar a falta do utilitário.

Código corrigido em `d5e4597`: filho com HUP ignorado e exec/setsid, preservando redireções, sessão, lock e critérios de prontidão. Regressão sem nohup envia SIGHUP real pelo peer antes de confirmar startup; remover a proteção ou reintroduzir nohup causa falha de asserção. Doze testes Herdr e 2/2 mutações passaram no Mac, assim como a suíte completa de 172 casos (164 aprovados/oito skips), Flake8 fatal, sete scripts Bash/ShellCheck, YAML/diff e guard público. Sem typechecker configurado.

VM com Herdr oficial e PATH do BusyBox da candidata: painel Bash 5.2, mesmo painel entre clientes CLI separados, restart e recriação pelo marcador passaram. Usa Bash/bibliotecas do guest, não executa o initramfs completo nem comprova SSH/TUI no telefone. Sessão própria encerrada, fixture/processos próprios ausentes e VM parada sem mounts. Nenhuma chave, snapshot, dado real ou imagem completa foi transferido; nenhum pacote instalado no Mac/guest.

[Evidência e limites](evidence/herdr-detachment.json). CI do código terminal verde: [PR 36851283400](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851283400) e [push 36851277105](https://github.com/djalmajr/iphone6s-linux/actions/runs/36851277105). Os quatro jobs Ubuntu/macOS executaram 172 casos (163 aprovados/nove skips) e detectaram ambas as mutações de detachment; logs conferidos. O gate físico da #13 permanece aberto. Reproduzir o contrato local sem aparelho:

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -p test_herdr_start.py -v
python3 iphone-linux-tools/tests/run_herdr_detach_mutations.py
```

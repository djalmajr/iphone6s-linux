# Ferramentas locais

Linux 7.0.12 ARM64 foi iniciado no iPhone 6s em 2026-09-29. Bash, SSH por chave, HTTP e Herdr 0.9.1 foram verificados no próprio telefone.

## Sessão já preparada

```bash
cd ~/iphone6s-linux/iphone-linux-tools
bash scripts/host/iphone-linux.sh status
bash scripts/host/iphone-linux.sh shell
bash scripts/host/iphone-linux.sh console
bash scripts/host/iphone-linux.sh herdr
```

`console` mostra no display do iPhone o Bash digitado no Mac. Veja [procedimento e evidências](docs/CONSOLE.md).

HTTP: http://172.16.42.1:8080/cgi-bin/status. Sair do Bash: `exit`. O Herdr mantém a sessão após fechar SSH; reiniciar o telefone perde tudo que estiver somente em RAM.

`bash scripts/host/iphone-linux.sh boot` seleciona a imagem integrada com console, SSH, HTTP e loopback automáticos, revalidada fisicamente com restauração e cliente Windows na LAN. `boot-probe` conserva o payload original e restaura seu runtime pelo Mac. Um clone novo precisa primeiro obter os binários e construir imagens/chaves conforme o [procedimento completo](docs/REPRODUCAO.md).

Não há storage interno, Wi-Fi, boot autônomo ou carga sustentada comprovados. O Mac fornece o enlace USB; conectar somente a um carregador não fornece essa rede. SSH usa chaves locais dedicadas; Telnet do bootstrap é encerrado depois de verificar SSH.

## Salvar arquivos em RAM

Use `/srv/data` para os dados dos serviços. No Mac:

```bash
bash scripts/host/iphone-linux.sh backup
bash scripts/host/iphone-linux.sh backups
bash scripts/host/iphone-linux.sh restore
```

`restore` aplica o snapshot manual mais recente e cria uma cópia do estado atual antes de sobrescrever arquivos. Backups ficam privados no Mac, fora do Git. Veja [escopo, exclusões e testes](docs/PERSISTENCIA.md). Execute `backup` antes de reiniciar ou use o scheduler optativo `autosnap watch`; [opções e limites](docs/AUTOSNAPSHOTS.md). Para restaurar no boot, escolha explicitamente `boot --restore ID`.

## Acesso de outro computador na LAN

Após boot/connect, execute no Mac `bash scripts/host/iphone-linux.sh lan --bind IP_DA_LAN_DO_MAC`. O processo foreground expõe SSH 2222 e HTTP 8086 somente nesse IPv4 privado; Ctrl+C fecha os listeners. SSH exige chave própria autorizada no iPhone e host key confiável; HTTP não tem autenticação. [Procedimento completo e prova Windows](docs/REDE.md). Esse comando não configura DNS nem fornece saída geral para internet.

Veja [estado e histórico](docs/STATUS.md), [plano](docs/BOOT-PLAN.md) e [manifesto de artefatos](docs/artifacts.json).

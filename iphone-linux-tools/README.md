# Ferramentas locais

Linux 7.0.12 ARM64 foi iniciado no iPhone 6s em 2026-09-29. Bash, SSH por chave, HTTP e Herdr 0.9.1 foram verificados no próprio telefone.

## Sessão já preparada

```bash
cd ~/iphone6s-linux/iphone-linux-tools
bash iphone-linux.sh status
bash iphone-linux.sh shell
bash iphone-linux.sh console
bash iphone-linux.sh herdr
```

`console` mostra no display do iPhone o Bash digitado no Mac. Veja [procedimento e evidências](docs/CONSOLE.md).

HTTP: http://172.16.42.1:8080/cgi-bin/status. Sair do Bash: `exit`. O Herdr mantém a sessão após fechar SSH; reiniciar o telefone perde tudo que estiver somente em RAM.

`bash iphone-linux.sh boot` seleciona a imagem integrada que deu boot com console, SSH e HTTP automáticos. `boot-probe` conserva o payload original e restaura seu runtime pelo Mac. O wrapper completo ainda não foi retestado desde um reinício. Um clone novo precisa primeiro obter os binários e construir imagens/chaves conforme o [procedimento completo](docs/REPRODUCAO.md).

Não há storage interno, Wi-Fi, boot autônomo ou carga sustentada comprovados. O Mac fornece o enlace USB; conectar somente a um carregador não fornece essa rede. SSH usa chaves locais dedicadas; Telnet do bootstrap é encerrado depois de verificar SSH.

## Salvar arquivos em RAM

Use `/srv/data` para os dados dos serviços. No Mac:

```bash
bash iphone-linux.sh backup
bash iphone-linux.sh backups
bash iphone-linux.sh restore
```

`restore` aplica o snapshot manual mais recente e cria uma cópia do estado atual antes de sobrescrever arquivos. Backups ficam privados no Mac, fora do Git. Veja [escopo, exclusões e testes](docs/PERSISTENCIA.md). Execute `backup` antes de reiniciar; ainda não há sincronização automática.

Veja [estado e histórico](STATUS.md), [plano](BOOT-PLAN.md) e [manifesto de artefatos](docs/artifacts.json).

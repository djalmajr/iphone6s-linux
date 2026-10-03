# Acesso pela LAN — plano da issue #6

**Estado atual:** #6 concluída com SSH/HTTP por um Windows independente após novo boot com loopback automático; resultado e cleanup em “Conclusão física” abaixo. Os planos, estados “em curso” e pilotos pendentes anteriores preservam a cronologia; não são novas pendências. DNS UDP/TCP foi validado depois na [#7](DNS.md). Carga sustentada, estabilidade e a cadeia posterior com kernel/Pongo compilados continuam gates separados.

## Contexto

A imagem atual oferece SSH por chave e HTTP na rede USB `172.16.42.0/24`. #5 está concluída; #2/#8 ainda impedem alegar operação prolongada. O telefone retornou ao iOS. Prepararemos o encaminhamento antes de pedir um novo boot curto. DNS do Mac/roteador, contas remotas, firewall global e Internet Sharing não serão alterados.

## Arquivos e detalhes

Fase de até cinco arquivos:

1. Novo `scripts/host/lan.py`: comando foreground que valida IPv4 privado específico e portas não privilegiadas distintas, verifica SSH estrito e executa o OpenSSH existente com dois forwards TCP fixos (SSH/HTTP), `ExitOnForwardFailure`, keepalive e sem agent forwarding.
2. `scripts/host/iphone-linux.sh`, case CLI: `lan --bind IP [--ssh-port 2222] [--http-port 8086]`, exigindo `connect`/boot prévios; não pede autenticação nem configura alias durante o comando LAN.
3. Novo `tests/test_lan.py`: recusa de wildcard/endereço público/portas conflitantes antes de listeners; interpretação pelo OpenSSH real das restrições; integração optativa de forwards HTTP/SSH e fechamento dos listeners com OpenSSH/Dropbear em namespace Linux isolado.
4. Este documento: decisões, comandos, reversão e limites/provas.
Fase seguinte (documentação e gates, até cinco arquivos): `tests/run_lan_mutations.py`, este documento, `docs/evidence/lan-check.txt`, README da raiz e `docs/EXECUCAO.md`. O runner exige baseline verde antes de aceitar mutações rejeitadas.

O arquivo de teste separará fixtures de prova local e cenário root/VM explícito. Copiar somente fontes públicas e gerar identidades sintéticas. Não usar segredos do Mac/iPhone nos testes da VM.

## Decisões

### D1. Encaminhamento TCP pelo OpenSSH existente

- **Decisão:** dois forwards foreground, bind no IPv4 privado explícito do Mac, portas padrão 2222/8086, destino fixo USB 22/8080. Sem auto-detecção/publicação em todas as interfaces. O endereço USB é recusado; 127.0.0.1 serve apenas para teste no Mac e não conclui o gate de LAN.
- **Por quê:** evita regras PF/NAT e daemon próprio; encerrar o processo remove os listeners. SSH do cliente remoto ainda autentica no próprio iPhone.
- **Alternativas:** proxy Python com allowlist (mais implementação de transporte); compartilhamento de internet/roteamento (muda configuração global e exige auditoria separada); bind wildcard (amplia exposição a outras interfaces). Escolha não habilita saída genérica para internet.
- **Reverter:** baixo, Ctrl+C ou SIGTERM no processo desta sessão; a rede USB e identidade do telefone permanecem.
- **Onde:** `lan.py`, CLI e testes.
- **Status:** em curso.

### D2. LAN confiável e internet separada

- **Decisão:** SSH somente por chave; HTTP de diagnóstico sem autenticação disponível a quem alcança IP/porta escolhidos na LAN. Não habilitar saída, DNS ou NAT implicitamente. A aplicação não oferece filtro por cliente.
- **Por quê:** entrega acesso local com comportamento explícito. Acesso de saída requer outra decisão e teste; não equivale a Wi-Fi nativo.
- **Alternativas:** ACL por IP com proxy próprio; túnel somente loopback para acesso apenas do Mac; TLS/autenticação HTTP em etapa de serviço. Cada opção tem escopo diferente e pode ser retomada.
- **Reverter:** baixo, encerrar encaminhamento.
- **Onde:** procedimentos e critérios da issue #6.
- **Status:** em curso; acesso físico por outro cliente da LAN ainda pendente.

## Tarefas

- [x] Implementar CLI e validação antes de executar listeners.
- [x] Verificar restrições efetivas com OpenSSH real e mutações críticas.
- [x] Testar SSH/HTTP e cleanup em namespace VM com serviços reais.
- [x] Novo boot curto e forwards com o iPhone real, mantendo USB-A traseiro.
- [x] Validar SSH e HTTP por outro cliente da LAN; registrar limites e reversão.

## Verificação

Pyflakes, Flake8 fatal, AST Python (não é typecheck), Bash/ShellCheck e `git diff --check`. Nenhum typechecker configurado. Testes sem imagens/rebuild/pacotes novos; VM volta ao estado anterior após remover fixtures próprios. #6 só encerra com prova real de outra máquina da LAN; testes de loopback/VM não substituem essa prova.

Fontes primárias: [OpenSSH: opções `-L`, `-g`, `-N`](https://man.openbsd.org/ssh). Consulte também o manual `man ssh` da versão instalada; a configuração efetiva pode ser inspecionada sem conexão com `ssh -G`.

## Parecer do Grok — incorporado em 2026-09-30

Revisão somente leitura, sem executar testes ou acessar dados privados: abordagem sem bloqueador. Ajustes incorporados: (1) recusar USB e distinguir loopback de LAN; (2) provar endereço efetivo do listener, pois `ssh -G` não mostra sockets do kernel; (3) exigir cliente físico independente, IP de origem, SSH autenticado com chave de host presa/HostKeyAlias e corpo HTTP do telefone; (4) separar esses dois forwards de saída genérica para internet. `ExitOnForwardFailure` trata criação dos listeners, não garante que cada serviço de destino responderá depois. Fontes oficiais: [ssh_config](https://man.openbsd.org/ssh_config.5) e [Dropbear](https://github.com/mkj/dropbear/blob/main/manpages/dropbear.8).

## Procedimento preparado (prova física ainda pendente)

No Mac, partindo de `iphone-linux-tools/`, inicie o Linux e confirme SSH/HTTP com o wrapper. A partir daí, um terminal dedicado executa:

```sh
bash scripts/host/iphone-linux.sh lan --bind IP_DA_LAN_DO_MAC
```

Substitua pelo IPv4 privado da interface alcançável pelo cliente. O comando não chama `connect` nem pede senha administrativa; exige o enlace USB já configurado. As portas padrão são SSH 2222 e HTTP 8086; `--ssh-port`/`--http-port` permitem outras portas distintas entre 1024 e 65535. Não use portas que outro serviço já ocupa. O processo permanece em primeiro plano; mensagens de início não substituem a prova de que cada destino responde.

No outro computador da LAN, HTTP de diagnóstico é `http://IP_DA_LAN_DO_MAC:8086/cgi-bin/status`. O corpo deve mostrar o kernel/modelo/uptime do telefone. SSH é `root@IP_DA_LAN_DO_MAC` na porta 2222; o cliente precisa de uma chave pública autorizada no telefone e da chave de host obtida pela construção confiável do projeto. Não copie a chave privada do Mac nem aceite uma chave de host diferente silenciosamente.

Com uma cópia **pública** do `keys/known_hosts` confiável e uma identidade do próprio cliente, o OpenSSH usa `HostKeyAlias=172.16.42.1` para verificar a mesma identidade atrás do encaminhamento:

```sh
ssh -F /dev/null -i CHAVE_DO_CLIENTE -p 2222 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=KNOWN_HOSTS_CONFIAVEL -o HostKeyAlias=172.16.42.1 root@IP_DA_LAN_DO_MAC 'uname -r'
```

No Windows use `-F NUL` em lugar de `/dev/null`. A autorização de uma nova chave pública no telefone é uma ação explícita no Linux em RAM, feita pelo Mac confiável; não está embutida no encaminhamento. Ela se perde no próximo boot e os snapshots excluem `authorized_keys`. Esta etapa não adiciona chaves permanentes na imagem nem mexe nas contas remotas.

Para desfazer, Ctrl+C no terminal do Mac ou SIGTERM **somente no PID desse encaminhamento**. Confira que as duas portas fecharam; SSH/HTTP continuam disponíveis no USB. Se o cliente LAN não alcança as portas, diagnostique IP/interfaces/firewall/isolamento do AP existentes; não altere regras globais ou o roteador automaticamente.

## Reprodução dos gates

Da raiz do repositório:

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -p test_lan.py -v
python3 iphone-linux-tools/tests/run_lan_mutations.py public-bind usb-bind privileged-port
```

Na VM dedicada já preparada, copie somente `scripts/host/lan.py`, `tests/test_lan.py` e `tests/run_lan_mutations.py`, conservando sua estrutura, para `/tmp/iphone6s-lan-validation`. Nenhuma chave real ou artefato precisa ser transferido:

```sh
sudo env IPHONE_LAN_VM_TESTS=1 python3 -m unittest discover -s /tmp/iphone6s-lan-validation/tests -p test_lan.py -v
sudo env IPHONE_LAN_VM_TESTS=1 python3 /tmp/iphone6s-lan-validation/tests/run_lan_mutations.py strict-trust listen-failure omitted-bind wildcard-bind
```

Os testes geram identidades sintéticas, executam Dropbear/BusyBox num chroot e adicionam endereços somente num namespace de rede novo. O runner exige baseline verde antes de interpretar falhas como rejeição de mutantes. Dependências já disponíveis: Python, OpenSSH, Dropbear/Dropbearkey, BusyBox estático, ip, unshare e chroot. Não instale pacotes automaticamente; esta rodada reutilizou o ambiente existente. Os fixtures próprios foram removidos e a VM devolvida a Stopped.

## Encerramento parcial desta fatia

Implementação, revisão da abordagem e gates isolados concluídos. Local: dois testes aprovados e um skip VM; baseline real VM aprovado; sete mutações rejeitadas (3 locais + 4 VM), após corrigir fixtures/gates descritos na [evidência](evidence/lan-check.txt). Pyflakes/Flake8 fatal, AST Python, Bash/ShellCheck e diff-check; nenhum typechecker configurado. Não há banco/migração, pacote novo, rebuild ou benchmark nesta fatia. Interfaces reais do Mac, iPhone e Windows ainda exigem validação conjunta; #6 permanece aberta, #2/#8 não mudam e o goal permanece ativo.

## Piloto físico e correção do início da rede

O Windows independente recebeu HTTP 200 com modelo/kernel/uptime do iPhone e executou `uname -r` por SSH estrito através dos forwards. O Mac confirmou listeners somente no IPv4 privado escolhido. A requisição Windows usou o endereço LAN explícito e proxy desativado; o canal Herdr de controle é separado desse tráfego. Nenhuma chave privada do Mac foi copiada. A identidade temporária do Windows foi revogada no telefone, a autorização original foi restaurada com comparação exata e os arquivos temporários dos clientes foram removidos. O snapshot final permaneceu privado.

O primeiro acesso encaminhado falhou porque `lo` estava DOWN no telefone. Ativar `lo` em RAM fez os mesmos serviços responderem; adicionar novamente `127.0.0.1/8` retornou `File exists`. O fixture VM já ativava `lo`, portanto não cobria o início da rede no aparelho. O piloto comprova os forwards após essa correção manual, mas não conclui #6 para um boot novo.

### D3. Ativar loopback no init

- **Decisão:** executar `ip link set lo up` antes de iniciar SSH/HTTP em `phone/init/init-server`; reconstruir uma candidata privada a partir do initramfs com console já testado, substituindo somente `/init`.
- **Por quê:** corrige a configuração ausente na origem. O comando LAN permanece dedicado aos forwards e não modifica silenciosamente o telefone.
- **Alternativas:** ativação manual após cada boot (não reproduzível); alteração no preflight LAN (oculta a falha de bootstrap). Endereço adicional é desnecessário na observação física atual.
- **Reverter:** baixo, selecionar a imagem anterior preservada e seu hash; nenhuma mudança na NAND/iOS.
- **Onde:** `phone/init/init-server`, candidata ignorada em `artifacts/`, seleção/hash do wrapper somente após validação.
- **Status:** em curso.

### Plano da correção

Contexto: SSH/HTTP diretos funcionavam, mas conexões encaminhadas pelo próprio Dropbear ficavam sem resposta com loopback desligado. Arquivos desta fase: este documento e `phone/init/init-server`; candidata privada e relatório de comparação fora do Git. Fase seguinte: seleção explícita no wrapper, manifest de hashes, evidência e execução, após inspeção da candidata.

- [x] Ativar `lo` no init antes dos serviços e verificar sintaxe/ShellCheck.
- [x] Confirmar o hash da imagem original e usar somente ferramentas já presentes na VM dedicada.
- [x] Extrair o initramfs original em diretório novo; comparar conteúdo/metadados de todos os arquivos e exigir que somente `/init` tenha mudado.
- [x] Compor payload sem sobrescrever a imagem anterior e registrar hash/tamanho.
- [x] Validar boot físico sem ativação manual de loopback e repetir HTTP/SSH pelo Windows com identidade temporária nova.
- [x] Revogar identidade, salvar snapshot, encerrar forwards e confirmar retorno ao iOS.

O piloto anterior durou cerca de 28 minutos por problemas no harness PowerShell. Após snapshot/reboot, o USB deixou de detectar o telefone; o operador confirmou posteriormente tela de desbloqueio do iOS e aparelho sempre frio. A leitura USB de bateria após retorno continua indisponível. Isso não comprova carga nem estabilidade prolongada. No próximo piloto, preparar comandos Windows antes do boot e reduzir o tempo de diagnóstico.

No PowerShell, enviar blocos completos em uma única linha pelo `pane run`; comandos multilinha ficaram no editor PSReadLine. Variáveis dentro de `& { ... }` não persistem no próximo comando: cada bloco deve resolver seus próprios caminhos e usar `$ErrorActionPreference='Stop'`. Marcadores devem distinguir saída real do texto ecoado do comando. Não alterar ExecutionPolicy nem instalar pacotes.

### Reprodução da candidata de loopback

Da pasta `iphone-linux-tools`, com a VM dedicada e suas ferramentas existentes:

```sh
multipass start iphone6s-build
multipass exec iphone6s-build -- sh -c 'umask 077; mkdir /home/ubuntu/iphone6s-loopback-input'
multipass transfer artifacts/iphone6s-console-server-initramfs.gz iphone6s-build:/home/ubuntu/iphone6s-loopback-input/original.gz
multipass transfer phone/init/init-server iphone6s-build:/home/ubuntu/iphone6s-loopback-input/init
multipass transfer scripts/build/rebuild-loopback-initramfs.py iphone6s-build:/home/ubuntu/iphone6s-loopback-input/repack.py
multipass exec iphone6s-build -- sudo sh -ec 'umask 077; python3 /home/ubuntu/iphone6s-loopback-input/repack.py; chown ubuntu:ubuntu /home/ubuntu/iphone6s-loopback-input/candidate.gz /home/ubuntu/iphone6s-loopback-input/report.json'
multipass transfer iphone6s-build:/home/ubuntu/iphone6s-loopback-input/candidate.gz artifacts/iphone6s-loopback-server-initramfs.gz
multipass transfer iphone6s-build:/home/ubuntu/iphone6s-loopback-input/report.json runtime/loopback-build-report.json
python3 scripts/build/compose-payload.py artifacts/iphone6s-loopback-server-initramfs.gz artifacts/m1n1-linux-iphone6s-loopback-server.bin
```

Execute cada linha somente se a anterior tiver saída 0. Antes da composição, compare SHA-256/tamanho recebidos com `report.json` e confira os hashes de m1n1/kernel/DTB no manifest. O diretório de entrada precisa ser novo; se já existir, inspecione sua origem, sem sobrescrever trabalho anterior. Os diretórios `iphone6s-loopback.*` gerados são privados e pertencem a esta reconstrução; remova somente os próprios diretórios depois de conferir/copiar os outputs. Os outputs contêm a chave privada do servidor e permanecem fora do Git.

O script exige o initramfs histórico de hash `b51e78b9acafea87685f3e09c9329a46929e288c582a91deb76593979480844e` e exatamente a inserção de `ip link set lo up` no init. É uma receita limitada a esta correção, não um atualizador genérico. Comparou 2.969 entradas, nomes, conteúdo, links, donos, modos e timestamps de arquivos; timestamps de diretórios são ignorados porque o cpio os modifica durante extração. Uma alteração adicional sintética no init foi recusada antes de produzir a candidata. Nenhuma chave foi regenerada.

Candidata recebida: initramfs SHA-256 `fdfceea110c1bd75f1c30c7ebcccd9a6baebc4207d5dbef63356d0e1c4d644fe`, 13.084.080 bytes; payload SHA-256 `8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66`, 23.765.032 bytes. A comparação confirma equivalência dos arquivos preservados; empacotamento cpio depende de metadados do filesystem, portanto não é promessa de builds idênticos byte a byte (#12). Boot físico da candidata ainda pendente.

O wrapper foi preparado para selecionar essa candidata em `boot`; a imagem anterior continua preservada e sua identidade SSH é a mesma. A seleção é preparação para o teste, não prova física. Dois testes do wrapper passaram, incluindo interrupção antes de upload após falha DFU e limpeza do monitor; dois testes locais LAN passaram, com um skip VM explícito. A prova isolada de forwards/mutações anterior permanece válida para o código LAN inalterado. Pyflakes/Flake8 fatal e Bash/ShellCheck passaram; o init tem apenas o aviso informativo preexistente SC2012, sem warnings/erros. Nenhum typechecker configurado. Diretórios privados próprios de rebuild removidos da VM, que voltou a Stopped. Para retornar à seleção anterior, restaurar no wrapper o caminho `m1n1-linux-iphone6s-console-server.bin` e hash `c49e03822e164767424d1ac786c3b00eec731de66acec497915c2cc83a39ee4a` em uma alteração revisável.

## Conclusão física — #6

O boot seguinte completou DFU → PongoOS → upload de 23.765.032 bytes → Linux, restore e HTTP, com saída 0. O operador confirmou o console. Antes de qualquer comando de configuração de rede no telefone, SSH mostrou `lo: <LOOPBACK,UP,LOWER_UP>`, endereço `127.0.0.1/8` e hash esperado do `/init`. Não houve ativação manual do loopback.

O Windows recebeu `IPHONE_HTTP2_STATUS=200`, validou corpo contendo iPhone/kernel, autenticou por SSH com chave própria e confiança estrita, recebeu `WINDOWS_LAN_SSH2_OK`, kernel 7.0.12 e loopback UP. O comando terminou com `IPHONE_PHYSICAL2_DONE`. Enquanto a conexão estava ativa, os sockets reais do Mac mostraram listeners somente no IPv4 LAN escolhido e conexão estabelecida desse IPv4:2222 para o IPv4 LAN do Windows; endereços pessoais não são publicados. Isso conclui o teste independente de SSH/HTTP pela LAN.

Autorização original restaurada e comparada, chave temporária revogada, arquivos privados do fixture Windows/Mac removidos. Snapshot final privado concluído, forwards encerrados e ausência de listeners confirmada. O iPhone retornou ao iOS, novamente detectado pelo USB, com 100% e `BatteryIsCharging=true`; baseline era 100%. O operador relatou frio/morno e prefere avisar espontaneamente se houver aquecimento, sem perguntas repetidas de temperatura. A amostra no teto de 100% continua inconclusiva para carga sustentada (#2/#8).

### Relatório desta entrega

- **Arquivos:** `lan.py`, CLI, testes/mutações LAN, init, receita privada de rebuild reproduzível por fonte pública, manifest e documentação/evidências. Imagens e identidades fora do Git.
- **Plano:** tarefas de #6 e correção de bootstrap concluídas; próxima #7, DNS inicialmente pelo USB.
- **Compatibilidade:** `boot` agora seleciona a imagem com loopback; a anterior está preservada. CLI LAN permanece optativo/foreground.
- **Testes:** wrapper 2/2 e LAN local 2 aprovados/1 skip VM rerodados; VM real e sete mutações LAN anteriores reutilizados para código LAN inalterado; build comparou 2.969 entradas e rejeitou delta extra; novo boot/restore/SSH/HTTP/cleanup comprovados fisicamente.
- **Tipos/lint:** nenhum typechecker configurado; Pyflakes/Flake8 fatal, sintaxe Bash/ShellCheck e diff-check passaram. Aviso informativo preexistente SC2012 no init.
- **Banco/dependências:** nenhuma migração, instalação de pacote ou alteração global de configuração no Mac/Windows; VM limpa/parada.
- **Desempenho:** piloto curto sem carga artificial de CPU; nenhum benchmark ou prova prolongada.
- **Limites:** HTTP sem autenticação acessível na LAN escolhida; SSH exige chave autorizada. Não habilita Wi-Fi nativo, UDP, DNS ou saída geral para internet. #2/#8 continuam abertas; merge não autorizado.

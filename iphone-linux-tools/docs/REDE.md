# Acesso pela LAN — plano da issue #6

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
- [ ] Novo boot curto e forwards com o iPhone real, mantendo USB-A traseiro.
- [ ] Validar SSH e HTTP por outro cliente da LAN; registrar limites e reversão.

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

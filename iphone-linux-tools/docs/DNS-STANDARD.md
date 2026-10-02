# DNS na porta padrão — plano #19

## Escopo e estado

A #7 comprovou DNS local não recursivo no telefone e proxy Mac em 1053. A #20 comprovou cliente Windows de sockets com parser/negativos/CI e piloto físico contra novo boot/restore; a prova explícita1053 não configura o resolvedor nem comprova53. A #19 trata exposição em 53 e uso pelo resolvedor dos clientes. Nenhuma configuração de DNS, firewall, PF, roteador ou serviço existente foi alterada.

Leitura real da tabela do kernel do Mac encontrou sete endpoints TCP e sete UDP em 53, incluindo IPv4 loopback e privado. O `lsof` sem privilégios não os mostrou; sua saída vazia não prova porta livre. Dois endereços IPv6 por protocolo vieram truncados mesmo com `netstat -W`, portanto não foram classificados. Esse inventário não identifica o dono nem autoriza parar serviços. Endereços brutos ficam privados em `runtime/dns-standard-port-20261001/`.

## D1. DNS local dividido, com validação explícita antes de política do cliente

- **Decisão:** conservar o DNS não recursivo do iPhone e preparar um endpoint 53 específico para os clientes autorizados. No Windows, avaliar regras NRPT para os dois FQDNs `iphone-usb.home.arpa` e `iphone-lan.home.arpa`, somente após consultas explícitas ao endpoint e teste de rollback. Não capturar todo `home.arpa` ou o namespace padrão.
- **Por quê:** o servidor atende registros locais e não pode substituir sozinho a resolução pública. A [NRPT](https://learn.microsoft.com/en-us/windows-server/networking/dns/name-resolution-policy-table) permite escopo FQDN e processa normalmente consultas fora das regras; configurações existentes/GPO podem afetar precedência e precisam ser verificadas antes de qualquer mudança. A disponibilidade contínua depende das #2/#8.
- **Alternativas:** encaminhar consultas públicas exige upstream/saída autorizados e expande o serviço; trocar DNS da interface ou roteador pode interromper a internet; uma zona local mais ampla pode interferir com outro serviço residencial. Portas explícitas 1053 conservam o modo de diagnóstico atual, mas não concluem o uso padrão da #19.
- **Reverter:** baixo antes de configurar clientes; na fase acompanhada, remover somente IDs de regras criados pelo projeto e encerrar somente listeners próprios, conservando a política anterior.
- **Onde:** este plano, futura alteração optativa do proxy e acompanhamento na #19.
- **Status:** preparação; sem regra NRPT aplicada, upstream escolhido ou listener 53 lançado.

O [cmdlet NRPT](https://learn.microsoft.com/en-us/powershell/module/dnsclient/add-dnsclientnrptrule?view=windowsserver2025-ps) aceita namespace e servidores explícitos. Isso é alternativa de implementação, não prova de funcionamento no Windows do operador. Browser/app pode usar resolvedor próprio; o teste deve distinguir consulta explícita de resolução do sistema/aplicação.

Android requer teste separado e acompanhado. O modo [Private DNS por hostname](https://developer.android.com/reference/android/app/admin/DevicePolicyManager#setGlobalPrivateDnsModeSpecifiedHost(android.content.ComponentName,java.lang.String)) exige servidor DNS-over-TLS; o DNS UDP/TCP atual não oferece esse protocolo. Não preencher esse ajuste com o IP do Mac ou afirmar que ele configura split DNS. Primeiro gate Android será consulta explícita com ferramenta já disponível; sua disponibilidade/modelo e a estratégia de integração ainda precisam ser observados. Nenhum aplicativo ou certificado será instalado nessa preparação.

## D2. Medir privilégio e conflitos antes de construir o launcher

- **Decisão:** identificar um IPv4 LAN do Mac previamente testado e ainda atribuído ao host; comparar seus binds exatos com a tabela do kernel. Se o IPv4 não estiver ocupado nem coberto por wildcard, testar somente bind UDP/TCP 53 por processo próprio não root, sem listen TCP, tráfego, reuseport ou serviço persistente, e fechar ambos imediatamente.
- **Por quê:** loopback 53 já tem binds; iniciar ali ou assumir necessidade de root não serve ao endpoint LAN. A medição concreta decide se basta launcher não privilegiado ou se será necessário bootstrap mínimo de sockets com entrega de FDs e abandono de privilégios. O runtime Python/SSH completo não deve executar como administrador.
- **Alternativas:** parar/alterar o DNS existente interfere com outro serviço; PF/NAT, aliases de interface e daemon de sistema modificam o host; adotar root para todo o proxy amplia acesso às chaves/configuração sem necessidade comprovada.
- **Reverter:** baixo, sockets de preflight fechados no próprio processo; se houver conflito ou privilégio insuficiente, nenhuma exposição será iniciada.
- **Onde:** evidência sanitizada e artefatos privados desta fase; nenhuma alteração operacional ainda.
- **Status:** IPv4 LAN previamente testado confirmado atribuído ao Mac e sem endpoint IPv4 exato/wildcard na leitura do kernel. UDP e TCP 53 foram recusados ao processo não root com errno 13 (EACCES); sockets fechados e zero endpoints no IPv4 selecionado depois. Nenhuma consulta ou listener TCP iniciado. Bootstrap mínimo precisa ser implementado/testado antes do piloto.

## Fases e verificações

1. **Preparação, até cinco arquivos:** este plano, nova evidência `evidence/dns-standard-port.json`, DNS, STATUS e PR-REVIEW. Registrar inventário/medição, decisões, limites de clientes, endereços estáveis a confirmar, allowlist e comportamento sem telefone. Sem serviço/política implantados.
2. **Implementação, nova fase de até cinco arquivos:** somente depois do preflight, definir alterações exatas do proxy/CLI e seus testes. Porta 1053 conserva default; 53 deve ser opção explícita com bind privado e allowlist individual. Testar conflitos UDP/TCP, recusa de wildcard/cliente alheio, upstream ausente, deadlines e cleanup; executar mutações reais após baseline verde. Não contar teste de bind como consulta DNS.
3. **Piloto acompanhado:** novo boot/DNS restore e consulta UDP/TCP explícita Windows/Android em 53. Política Windows somente após inventariar regras existentes e salvar IDs/estado anterior privadamente; teste de nome local, nome externo por caminho anterior e interrupção do telefone. Não mudar interface/roteador ou regra de outro projeto.
4. **Rollback:** remover somente política/listeners próprios, conferir resolução anterior e ausência dos sockets próprios. Documentar IP estável/renovação DHCP, mudanças da allowlist, sequência de boot e falhas. Não afirmar serviço contínuo antes das #2/#8.

Falha de boot, túnel ou energia deve encerrar o proxy próprio; nomes locais ficam indisponíveis. Com split DNS corretamente limitado, nomes externos seguem a configuração anterior. Isso é requisito para testar, não resultado já observado. Se não houver endereço LAN estável, o launcher deve exigir novo IP explícito e testes da allowlist antes de publicar; nenhuma reserva DHCP foi criada.


## Contrato seguinte após a medição

A medição elimina a alternativa de abrir 53 diretamente como usuário neste Mac. A etapa privilegiada deve ser um helper local auditável que importe apenas biblioteca padrão em intérprete isolado e abra exatamente dois sockets IPv4 (UDP/TCP), porta fixa 53, no bind privado informado. Não ler perfil, chave SSH, configuração DNS ou dados do iPhone enquanto privilegiado. Não executar SSH, instalar serviço, alterar sudoers/PF ou adicionar endereço de rede. O helper abandona grupos/UID/GID privilegiados antes de comunicar-se com o processo usuário; entrega somente os dois descritores por socket Unix privado, fecha suas cópias e termina.

O processo usuário deve conferir identidade do canal, quantidade/tipos/endereços/portas dos FDs e ownership do diretório/socket, recusar socket alheio ou mensagem truncada, impor prazo e fechar os FDs próprios em qualquer falha. Apenas depois da validação e da prontidão do túnel SSH ele inicia o atendimento. Privilege drop, peer/FD validation e ausência de tráfego para fora da allowlist são gates críticos: testes com sockets reais em ambiente isolado e mutações por asserção, além de teste nativo Mac acompanhado antes de afirmar funcionamento em 53.

O bootstrap foi implementado e testado isoladamente na fase 2A abaixo; sua integração ao proxy continua pendente. A integração optativa deve preservar 1053, não abrir 53 implicitamente ao iniciar Linux e não colocar todo o runtime sob sudo. Se o bootstrap falhar, encerrar os sockets próprios, conservar a política dos clientes e exibir erro; nunca tentar mudar um serviço existente para fazer o bind passar.

## Fase 2A — abertura e entrega de sockets

Cinco arquivos: novos `scripts/host/dns_privileged.py`, `scripts/host/dns_activation.py`, `tests/test_dns_activation.py`, `tests/run_dns_activation_mutations.py` e este plano. O proxy/CLI atual não será alterado nesta fase: a próxima fatia adotará a API validada e habilitará uma opção explícita de porta 53.

Contrato original da fase 2A (`6a03a0c`): o helper recebe bind, socket Unix e UID/GID não root explícitos, conferidos com a identidade original informada pelo sudo. Executa `/usr/bin/python3 -I -S`, importa somente biblioteca padrão, abre UDP/TCP IPv4 53 sem reuse/listen, remove grupos suplementares e troca GID/UID permanentemente. Confere a identidade resultante antes de conectar ao socket privado do usuário. Nonce de 32 bytes chega por stdin limitado/prazo, sem senha ou nonce em argumentos. A resposta tem framing fixo, identidade/grupos resultantes, nonce e exatamente dois FDs via SCM_RIGHTS; o helper fecha suas cópias e termina. Nenhum perfil/chave/SSH é lido ou executado no processo privilegiado. A fase 2C altera somente a política de rebind TCP descrita abaixo.

O módulo usuário exige processo não root, diretório privado próprio e fonte do helper regular/sem escrita por terceiros. Lança somente sudo nativo não interativo e Python de sistema isolado; falta de autorização existente deve falhar, sem mudar sudoers ou pedir senha via stdin. Valida peer UID/GID (SO_PEERCRED Linux; libc getpeereid Darwin), payload completo/nonce, ausência de grupos suplementares, quantidade/família/tipo/protocolo e endereço/porta dos FDs, ausência de listener TCP prematuro e deadline. Fecha descritores recebidos em qualquer recusa. Só retorna o par após sucesso e término do helper. A API retorna sockets bound; atender DNS/validar túnel permanece responsabilidade do proxy na fase seguinte.

Verificação: Mac não privilegiado testa IPC real em sockets privados, mensagens fragmentadas, nonce/peer/contagem/tipo/endereço/porta/truncamento/EOF/prazo e fechamento dos FDs rejeitados. VM `iphone6s-repro-20260930` testa o helper real via sudo em namespace de rede próprio, com controller usuário normal, binds 53, UID/GID/grupos, conflito TCP após bind UDP, dados UDP/TCP pelos FDs adotados e cleanup. Mutações reais devem falhar por asserção após baseline aprovado, sem aceitar erro de compilação, skip, falta de sudo ou conflito externo como prova. Nenhum comando root será executado no Mac nesta fatia. Gates: Flake8 fatal, compilação Python, testes focados Mac/VM, mutações e guard público; CI documentado separadamente. Piloto Mac privilegiado/integração DNS/Windows/Android não são declarados concluídos por esses testes.

### Resultado da fase 2A

- Python de sistema do Mac: 21 casos reais de IPC/FDs e 15 mutações de fonte rejeitadas por asserção. A descoberta `unittest` inclui somente a classe não privilegiada; a classe da VM deve ser selecionada explicitamente.
- Ubuntu 24.04 ARM64, VM do projeto: baseline dos mesmos 21 casos mais três casos privilegiados em namespace de rede próprio; 18 mutações rejeitadas por asserção. Incluem remoção de grupos/UID, identidade original sudo, limpeza de FDs adotados/brutos, peer/nonce, tipos/binds/reuse e permissões do canal.
- O helper real abriu 53, saiu de root antes da conexão Unix e transferiu UDP/TCP com dados verificáveis. Após fechar os FDs, ambos os binds ficaram livres; um conflito TCP encerrou o helper e também fechou o UDP aberto primeiro. Diretórios de ativação e descritores do controller voltaram ao estado anterior.
- Compilação dos quatro módulos e Flake8 fatal passaram. Isso não prova DNS do iPhone em 53, política NRPT, integração do proxy ou privilege drop nativo Darwin. Nenhum helper root foi executado no Mac.

Os testes nativos corrigiram duas diferenças Darwin: `SO_ACCEPTCONN` não funcionou como consulta de estado neste host, portanto o TCP é validado por `TCP_CONNECTION_INFO`/estado CLOSED, conforme os headers [tcp.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp.h) e [tcp_fsm.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp_fsm.h). Um buffer de controle inicialmente pequeno revelou vazamento no caso de 17 FDs; o receptor agora reserva espaço para o limite de 512 FDs do [XNU](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/uipc_usrreq.c), recusa excesso e fecha os FDs retornados. Casos de 0/1/3/17/65 descritores passaram sem aumento de FDs. Não considerar truncamento arbitrário de controle em todo kernel/Python como universalmente provado; a [documentação Python](https://docs.python.org/3/library/socket.html#socket.socket.recvmsg) alerta sobre controle parcialmente recebido. Python 3.9 nativo também exigiu normalizar `socket.timeout` para `TimeoutError`.

### Reprodução sem instalar ferramentas no Mac

Mac, sem sudo, usando portas altas loopback e IPC Unix:

```sh
/usr/bin/python3 -m unittest discover -s iphone-linux-tools/tests -p test_dns_activation.py -v
/usr/bin/python3 iphone-linux-tools/tests/run_dns_activation_mutations.py
```

Na VM Linux exclusiva do projeto, copie somente `scripts/host/*.py` e os dois testes novos para um diretório próprio do usuário `ubuntu`, com fontes regulares sem escrita por grupo/outros. Nenhum perfil, chave ou runtime privado é necessário. O cenário seguinte cria somente um namespace efêmero; não altera rede, DNS ou sysctl fora dele. Execute dentro da VM, ajustando `project` para o caminho copiado:

```sh
sudo -n unshare --net -- /usr/bin/python3 -I -S - /home/ubuntu/activation-final-phase2a-20261001/project <<'PY'
import pathlib
import subprocess
import sys
project = pathlib.Path(sys.argv[1])
subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
subprocess.run(['ip', 'address', 'add', '10.231.0.1/32', 'dev', 'lo'], check=True)
pathlib.Path('/proc/sys/net/ipv4/ip_unprivileged_port_start').write_text('1024')
result = subprocess.run(['sudo', '-u', 'ubuntu', '--', 'env',
    'IPHONE_ACTIVATION_TEST_BIND=10.231.0.1',
    'IPHONE_ACTIVATION_MUTATIONS_PRIVILEGED=1', '/usr/bin/python3',
    str(project / 'tests/run_dns_activation_mutations.py')])
raise SystemExit(result.returncode)
PY
```

O opt-in privilegiado exige controller Linux não root, bind de fixture e namespace distinto do PID 1 da VM. Baseline com erro/skip, sintaxe inválida, falha de infraestrutura ou mutação sem `AssertionError` nunca contam como aprovação. Nenhuma regra sudoers ou serviço persistente deve ser criado. A fase seguinte precisa integrar a API de sockets ao proxy, conservar 1053 como padrão e testar allowlist, perda do túnel e cleanup antes do piloto acompanhado.

## Fase 2B — integração optativa ao proxy

Cinco arquivos: `scripts/host/dns.py`, `scripts/host/dns_lan.py`, `tests/test_dns_lan.py`, novo `tests/test_dns_standard.py` e este plano. Adicionar `dns lan --standard-port` como seleção explícita de 53, incompatível com `--port`; sem flag conserva 1053 ou a porta alta informada. Recusar loopback em modo padrão e runtime privilegiado antes de ler o perfil. Confirmar SSH antes de adquirir sockets e iniciar atendimento somente depois da validação 2A. Conservar allowlist, prazos e encerramento com perda do túnel.

Testes do CLI verificam encaminhamento dos argumentos e recusas antes de rede/identidade. A fixture DNS/SSH real existente será estendida para rodar o proxy como usuário `ubuntu` em 53 dentro de namespace próprio, conservando o caso de porta alta. Exercitar UDP/TCP, cliente recusado, nome externo NXDOMAIN, capacidade, falha de túnel, conflito UDP/TCP/forward e trust inválido; conferir listeners e UID do runtime/SSH. Sem novo pacote, política cliente ou helper root Mac. CI/mutações adicionais serão a fatia seguinte; não afirmar piloto físico por fixture.

Resultado intermediário: três testes do CLI e dois testes wire Mac passaram. A fixture VM em 53 passou consultas UDP/TCP, ACL/NXDOMAIN/capacidade, identidade não root do proxy/SSH e perda do túnel, mas falhou no cenário seguinte de conflito: `EADDRINUSE` ao tentar reservar o endereço TCP encerrado. A fase 2A usa TCP sem reuse; sockets em TIME_WAIT impedem reinício rápido. A fixture não chegou ao marcador final, portanto não é aprovação da integração completa. Próxima fase corrigirá o contrato de rebind e repetirá o cenário real antes de concluir #19. A porta 1053 permanece o padrão.

## Fase 2C — reinício após TCP TIME_WAIT

Cinco arquivos: `scripts/host/dns_privileged.py`, `scripts/host/dns_activation.py`, `tests/test_dns_activation.py`, `tests/run_dns_activation_mutations.py` e este plano. Abrir TCP com `SO_REUSEADDR=1` para permitir rebind após conexões próprias em TIME_WAIT; UDP continua `SO_REUSEADDR=0`, e `SO_REUSEPORT=0` permanece obrigatório em ambos. Validar exatamente esses valores no receptor. Nenhum listen TCP antecipado, mudança de serviço alheio ou reuseport. Listener TCP existente, inclusive com reuseaddr, deve continuar impedindo startup próprio.

Adicionar regressão real de active close/TIME_WAIT seguido de nova aquisição 53, na VM privada. Conservar testes/mutações de ACL, abandono de privilégios, FD cleanup e da política de reuse. Após baseline, repetir a fixture real da fase 2B com DNS/SSH e conflitos; não executar helper root Mac nesta etapa.

Resultado: baseline final de 21 casos Mac e 15 mutações por asserção; VM com 25 casos (21 IPC + quatro privilegiados) e 19 mutações por asserção. A regressão confirmou TIME_WAIT na tabela TCP e aquisição seguinte bem-sucedida. Listener TCP existente com reuseaddr continuou recusando o bootstrap; UDP aberto primeiro foi fechado e o listener existente permaneceu preservado. A leitura de reuseaddr no Darwin retorna bitmask, portanto o receptor normaliza para booleano em vez de exigir inteiro 1. A mutação de tipo isolada passou a ser mascarada pela política oposta de reuse UDP/TCP; não foi contada como kill. Foi substituída pela remoção real do bloco de política de sockets, rejeitada por asserção no cenário de tipos incorretos.

A fixture DNS/SSH completa em 53 chegou ao marcador `DNS_STANDARD_NONROOT_UDP_TCP_ACL_FAILURE_CLEANUP_OK`: consultas UDP/TCP, ACL individual, NXDOMAIN externo, capacidade, bind do kernel, UID não root de proxy/SSH, perda do túnel, conflitos TCP/forward e trust inválido passaram. Sockets/SSH/chroot/mounts próprios foram encerrados. TIME_WAIT pode permanecer no kernel; não é listener ativo nem descritor/processo sobrevivente. Conflito UDP do proxy completo, prova automática em CI e o piloto físico ainda serão fechados separadamente. Não houve helper root Mac, política NRPT, mudança de DNS/firewall, instalação de pacote ou boot do iPhone nesta fase.

## Fase 2D — gates permanentes de integração

Cinco arquivos: `.github/workflows/ci.yml`, `tests/test_dns_lan.py`, `tests/run_dns_lan_mutations.py`, este plano e `docs/STATUS.md`. Incluir as 15 mutações não privilegiadas do bootstrap na CI Ubuntu/macOS. Estender a fixture real com conflito UDP, verificação de ausência de UDP próprio após falhas e caso VM explícito de porta53; o runner das oito mutações DNS/SSH deve executar os modos alto e padrão. Preservar skips dos casos privilegiados na CI comum e não declarar piloto iPhone por esses testes.

Resultado VM: baseline final de quatro testes, cobrindo dois casos wire e duas integrações reais (porta alta/53), sem skips. Todas as oito mutações foram rejeitadas: allowlists UDP/TCP, bind, capacidade, fail-on-forward, host trust, identidade e tamanho da resposta. Conflitos UDP/TCP/forward preservaram sockets existentes; startup inválido encerrou somente SSH/listeners próprios. Tabela UDP confirmou ausência dos sockets próprios após falhas. Parser YAML, Flake8 fatal, testes CLI e diff-check passaram. CI do bootstrap `6a03a0c` terminou verde em [PR 36930558070](https://github.com/djalmajr/iphone6s-linux/actions/runs/36930558070) e [push 36930548792](https://github.com/djalmajr/iphone6s-linux/actions/runs/36930548792), três jobs por run. CI do código final `98e6384` terminou verde na PR36932840328/push36932841357, três jobs por run.

## Fechamento documental desta preparação

Cinco arquivos: este plano, `docs/DNS.md`, `docs/STATUS.md`, `docs/PR-REVIEW.md` e `docs/evidence/dns-standard-port.json`. Registrar head de código/CI, hashes dos módulos, provas separadas Mac/VM, falha TIME_WAIT/mutação sobrevivente corrigidas, cleanup/VM parada e procedimentos do modo explícito. Conservar gates nativos Mac/iPhone/Windows/Android/NRPT e a revisão integral #16 abertos; não alterar a política dos clientes nessa fase.

CI final de código: [PR 36932840328](https://github.com/djalmajr/iphone6s-linux/actions/runs/36932840328) e [push 36932841357](https://github.com/djalmajr/iphone6s-linux/actions/runs/36932841357), três jobs terminais verdes por run. Logs confirmaram baseline e 15 mutações por asserção em Ubuntu/macOS. VM confirmada Stopped após zero processos DNS/SSH/diretórios de fixtures. O inventário da revisão integral permanece no checkpoint anterior; esta fase não fecha #16.


## D3. Consulta Windows explícita à porta53

- **Decisão:** aceitar `-Port 53` no helper público, conservando default1053 e intervalo alto1024–65535; nenhuma outra porta baixa. O argumento explícito já indica o destino da consulta, sem novo switch ou alteração do resolvedor.
- **Por quê:** o gate físico da #20 passou em1053, mas o contrato atual recusa53 antes do transporte e impede validar a exposição padrão da #19 com o mesmo parser.
- **Alternativas:** outro cliente duplicaria parsing/validação; liberar todo intervalo baixo ampliaria escopo sem necessidade. Native Resolve-DnsName será apropriado ao futuro teste de política, separado da consulta UDP/TCP explícita.
- **Reverter:** baixo; mudança do helper/fonte local, sem migração/instalação ou estado persistente.
- **Onde:** cinco arquivos desta fase: `scripts/host/dns-check-windows.ps1`, `scripts/host/dns_windows.cs`, `tests/dns_windows_fixture.cs`, `tests/test_dns_windows.ps1` e este plano.
- **Status:** implementada/validada no Windows real; nenhum DNS53 funcional, política cliente ou helper root Mac executados nesta fase.

Adicionar regressões observáveis ao método público:53 e portas altas1024/1053/65535 passam a guarda de porta e continuam recusando endereço público antes de rede;54/1023 e limites recusados pela guarda de porta. Usar endereço inválido em todos esses casos para impedir tráfego mesmo quando uma mutação remove a guarda. Primeiro executar regressão53 contra fonte antiga e exigir AssertionError, não compilação/infraestrutura. Depois alterar validação PS/C# e comprovar baseline completo/duas mutações de política novas junto das18existentes, em PowerShell assinado nativo. Verificar helper público em processo novo,53/endereço público deve falhar por endereço;54/1023 devem falhar por porta, nenhum marcador.

Esses testes provam aceitação/restrição do cliente, não DNS53 funcional. O futuro piloto continua exigindo bootstrap mínimo/privilege drop Darwin, telefone/ACL, cliente real e cleanup; Android/NRPT/IP estável dependem de acompanhamento do operador. Não alterar DNS/firewall, pacotes, contas, políticas ou executar proxy inteiro como administrador. CI/documentação de fechamento em fase posterior, sem ampliar os cinco arquivos.


### Verificação da extensão Windows

Regressão nova falhou por DNS_TEST_ASSERTION standard-port na fonte antiga, compilação válida. Fonte corrigida passou 64 casos e 20 mutações reais por asserção (18 anteriores + standard-port-denied/reserved-port-open), saída0. Caso standard-port cobre53/1024/1053/65535 nas duas seleções de transporte com endereço inválido; reserved-port cobre54/1023 e port-bounds cobre0/52/65536. Não houve tráfego nesses novos casos mesmo nas mutações, pois a guarda de endereço permanece. Fixtures antigas exercitam transportes loopback/parser reais; erro/skip/compilação não são aprovação.

Sete invocações do helper público em filhos PowerShell novos/assinados confirmaram recusa por endereço em 53/default/65535 e recusa por porta em 54/1023/52/65536, sem marcadores UDP/TCP. Parser nativo/compilação C# passaram; não há typechecker separado. Quatro fontes transferidas foram conferidas por SHA256 conjuntamente antes de executar. Default literal 1053 permaneceu inalterado; aceitar 53 exige argumento explícito. Nenhum pacote, agente, configuração global, chave ou estado do telefone alterados nesta fase.

Os testes 64/20 e controles CLI são prova do cliente; não indicam servidor53 ativo. Preflight sudo não interativo no Mac retornou senha necessária e nenhum bootstrap privilegiado foi executado. O piloto futuro exigirá autenticação local do operador no terminal dedicado, mantendo helper mínimo53/abandono de privilégios e proxy/SSH como usuário. Fontes/logs privados no Mac em runtime/windows-dns53-client-20261001. No Windows, quatro arquivos de testes/logs foram removidos e o diretório tests apagado; os dois arquivos cliente foram preservados intencionalmente na pasta exclusiva para o próximo piloto, com hashes conferidos. Filhos próprios concluíram; nenhum fixture servidor permaneceu ativo. CI desta extensão ainda será observada após publicar. O teste Android continua pendente; o avanço atual usa Mac/Windows. NRPT/política/IP estável/rollback e energia continuam gates separados.

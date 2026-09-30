# DNS local — plano da issue #7

## Contexto

#6 concluiu SSH/HTTP pela LAN, mas os forwards OpenSSH transportam TCP; DNS também precisa de UDP. O telefone continua sem saída geral para internet. O próximo serviço atenderá nomes locais; não mudará automaticamente o DNS do Mac, Windows, Android ou roteador. O iPhone está em iOS enquanto preparamos/verificamos a implementação; testes físicos continuam curtos, sem perguntas repetidas de temperatura.

## Decisões

### D1. dnsmasq do Ubuntu, inicialmente sem recursão externa

- **Decisão:** obter `dnsmasq-base` ARM64 do repositório Ubuntu 24.04 assinado, extrair executável/bibliotecas em pacote isolado e guardar o runtime e configuração em `/srv/data/dns`, dentro do escopo de snapshots. Usar a versão corrigida de `noble-security`; a versão 2.91 em `noble-updates` aparece atualmente com rollout de 0%, portanto não será forçada.
- **Por quê:** serviço conhecido, com origem verificável e sem necessidade de instalar um gerenciador de pacotes no telefone. Os arquivos sobreviverão por backup/restore no Mac. Não depende de acesso externo no Linux.
- **Alternativas:** compilar upstream (mais cadeia de build/proveniência); resolvedor próprio (protocolo e segurança desnecessários); encaminhar consultas públicas (exige saída de internet e política separada).
- **Reverter:** baixo, parar somente o processo DNS próprio e recuperar snapshot/configuração anteriores. Imagem/NAND e contas remotas preservadas.
- **Status:** em curso; pacote ainda não transferido ao telefone.

### D2. Rede explícita e clientes permitidos

- **Decisão:** DNS no iPhone somente em `172.16.42.1:5353` UDP/TCP, sem DHCP/TFTP/RA, sem upstream e sem ler resolv.conf/hosts globais. Registros privados explícitos em `home.arpa`; `iphone-usb.home.arpa` aponta para o enlace USB. Um alias LAN usará IP de serviço informado pelo operador, sem dados pessoais no Git.
- **Por quê:** nomes úteis e comportamento previsível para a fase sem internet. DNS não carrega portas HTTP/SSH; clientes ainda usarão as portas encaminhadas documentadas.
- **Alternativas:** porta 53 no Mac (exige privilégios/conflitos/configuração global); somente DNS/TCP (não cobre clientes UDP); wildcard ou recursão pública (amplia exposição).
- **Reverter:** baixo, encerrar launcher/forward. Configurar o DNS global de clientes fica fora desta entrega; consultas explícitas não alteram suas configurações.
- **Status:** em curso.

### D3. Transporte UDP da LAN por TCP autenticado

- **Decisão:** proxy foreground no Mac em IPv4 privado e porta não privilegiada explícitos, com allowlist de IPv4 individuais obrigatória. Transportar mensagens DNS por conexão TCP com framing DNS através de forward SSH loopback dedicado até o telefone. Atender UDP e TCP de clientes permitidos, com tamanho/timeout/concorrência limitados, sem encaminhamento genérico.
- **Por quê:** atende clientes DNS reais sem regras PF/NAT ou daemon instalado no Mac. Allowlist também vale no protocolo TCP; o servidor de destino não fará recursão externa.
- **Alternativas:** roteamento/Internet Sharing (mudança global); proxy UDP sem allowlist (exposição ampla); só `ssh -L` (não entrega UDP).
- **Reverter:** baixo, Ctrl+C remove somente listeners/processo filhos deste proxy.
- **Status:** na fila, depois da validação USB/VM do servidor.

## Arquivos e fases

Cada fase terá no máximo cinco arquivos e será verificada antes da seguinte.

1. Pacote/configuração do telefone: fonte de build em `scripts/build`, launcher em `phone/dns`, teste de servidor real na VM e este documento. Extrair somente executável/dependências necessários; nenhuma chave real nos fixtures. Launcher validará configuração e identidade do processo, iniciará/parará somente sua instância e manterá dados persistíveis em `/srv/data/dns`. Usar conta sem privilégios criada somente no telefone em RAM, se necessária para o drop de privilégios.
2. Instalação/operação pelo Mac: helper `scripts/host`, case CLI no wrapper, testes e documentação. Transferência por SSH estrito com hash verificado; portas e PID/logs do serviço explícitos. Restore recupera arquivos, não processos; início do DNS após restore será explícito.
3. Proxy LAN: transporte DNS isolado, CLI e testes locais/VM reais. Allowlist, bind específico, framing/tamanhos/timeout, upstream inválido, porta ocupada e cleanup devem ser observáveis. Testes críticos terão mutações executadas após baseline verde.
4. Dois boots físicos curtos: validar DNS UDP/TCP pelo Mac e Windows, snapshot, retorno ao iOS e novo boot/restore/configuração/serviço. Revogar fixtures temporários e registrar reversão/limites antes de encerrar #7.

## Tarefas

- [x] Conferir repositórios/keyrings, versão e hash do pacote oficial e dependências; preparar bundle isolado.
- [x] Validar configuração/local-only e consultas positivas/negativas UDP/TCP com dnsmasq real na VM isolada.
- [ ] Implementar transferência/launcher e recuperação de configuração pelo snapshot existente.
- [ ] Implementar proxy LAN com allowlist e gates/mutações.
- [ ] Validar consultas físicas USB/LAN e recuperação em novo boot.
- [ ] Limpar fixtures, salvar evidência sanitizada, atualizar issues e versionar sem dados pessoais.

## Verificação

Pyflakes/Flake8 fatal, sintaxe Bash/ShellCheck, AST Python, diff/privacidade; não há typechecker configurado. Usar o `dig` já existente na VM/Mac e OpenSSH real; Windows tem nslookup nativo. Testar consultas negativas fora da zona e ausência de encaminhamento externo, respostas UDP/TCP, rejeição de clientes fora da allowlist, falha de startup/porta ocupada e fechamento de sockets. Gates físicos não serão substituídos pela VM.

## Fontes primárias

- [Manual dnsmasq](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html): bind, teste de configuração, arquivos locais e desativação de upstream.
- [Pacotes oficiais Ubuntu](https://packages.ubuntu.com/en/dnsmasq-base): versões publicadas; conferir índices assinados reais da VM na execução.
- [RFC 8375](https://www.rfc-editor.org/rfc/rfc8375.html): uso residencial de `home.arpa`.
- [Microsoft nslookup](https://learn.microsoft.com/windows-server/administration/windows-commands/nslookup) e [porta de consulta](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup-set-port).

#2/#8 seguem abertas; disponibilidade curta e ausência de aviso de calor não comprovam carga/estabilidade prolongadas.

## Pacote e primeiro gate concluídos

Os índices APT da VM falharam duas vezes ao resolver o domínio Ubuntu. HTTPS também foi intermitente; a consulta DNS direta recuperou endereços públicos. O download final usou HTTPS com `--resolve` para um desses endereços, conservando validação TLS do hostname. Nenhum resolver, source list, keyring ou pacote instalado foi alterado. A verificação ocorreu depois na VM com seu keyring Ubuntu existente: assinatura válida pelo fingerprint `F6ECB3762474EDA9D21B7022871920D1991BC93C`, release `noble-security` de 2026-09-30, hash/tamanho de `main/binary-arm64/Packages.xz` conferidos, então hash/tamanho do `.deb` da entrada `dnsmasq-base` ARM64. Não foi usado índice APT antigo como prova de autenticidade do download novo.

Selecionado `dnsmasq-base` 2.90-2ubuntu0.4. O `.deb` foi extraído com `dpkg-deb -x`, sem scripts de instalação. Executável e 22 bibliotecas existentes da VM foram copiados como arquivos regulares em bundle de 4.614.005 bytes, SHA-256 `8ccb8f30a1a179b02825bda6040bb51a807b4abbcda24f925028481d5c48e72e`. A origem do executável é autenticada pelo índice assinado; as bibliotecas vêm do ambiente Ubuntu existente e seus hashes são registrados, sem alegar uma auditoria completa da VM. [Proveniência](evidence/dns-provenance.json). Cópias com release adulterado e pacote com byte modificado foram recusadas antes de output.

`scripts/build/build-dns-runtime.py INPUTS OUTPUT` espera `InRelease`, `Packages.xz` e `dnsmasq.deb` no diretório de entrada. Valida assinatura, origem/suite, índice e pacote antes de extrair/usar `ldd`; recusa biblioteca ausente e output existente. O bundle não contém identidade SSH ou informação pessoal. `COPYRIGHT` do Ubuntu/dnsmasq é incluído. O pacote permanece privado em `runtime/`; um clone precisa obter e validar seus próprios inputs. Builds não são declarados idênticos byte a byte.

`phone/dns/manage-dns.sh` usa a daemonização nativa do dnsmasq, sem depender de `nohup`, indisponível no BusyBox desta imagem. A configuração é fixa e local-only; registros ficam em `/srv/data/dns/hosts`. A conta `nobody` UID/GID 65534 é criada apenas no telefone em RAM após verificar conflitos de ambas as identidades. O estado em `/run/iphone-dns/state` contém PID e ticks de início; parar exige executável e ticks correspondentes. Registros/PID/logs nunca entram em configuração global do Mac. O usuário do daemon observado na VM foi 65534; ele não permaneceu root.

O teste real em chroot e namespaces de rede/mount aprovou consultas positivas/negativas UDP/TCP, zero pacotes no upstream sintético, bind do kernel somente USB IPv4, nenhum listener IPv6, início idempotente, recusa de PID antigo/executável alheio, porta ocupada sem listener parcial e encerramento da instância. Cinco mutações rejeitadas após baseline verde: bind wildcard, usuário root, recursão externa, ticks de PID ignorados e executável alheio aceito. No Mac há um skip VM explícito, não prova do aparelho. Pyflakes/Flake8 fatal, ShellCheck/sintaxe e diff-check passaram; nenhum typechecker configurado.

O fixture inicial precisou de `/dev/urandom`, que já existe no devtmpfs do telefone; em seguida revelou a ausência real do applet `nohup`, corrigida no launcher pela daemonização nativa. Resultados desses dois gates falhos não foram aceitos como validação. Após os testes/mutações, zero processos dnsmasq e zero diretórios de fixture próprios na VM. Instalação/operação pelo Mac, proxy LAN, persistência após boot e provas físicas ainda estão pendentes.

### Reprodução dos testes de servidor

Copiar para uma árvore nova na VM dedicada, conservando caminhos relativos: `phone/dns/manage-dns.sh`, `tests/test_dns_server_vm.py` e `tests/run_dns_server_mutations.py`. O bundle autenticado pode ficar fora da árvore de fontes:

```sh
sudo env IPHONE_DNS_VM_TESTS=1 IPHONE_DNS_BUNDLE=/CAMINHO/iphone6s-dns-runtime.tar.gz python3 -m unittest discover -s /CAMINHO/ARVORE/tests -p test_dns_server_vm.py -v
sudo env IPHONE_DNS_VM_TESTS=1 IPHONE_DNS_BUNDLE=/CAMINHO/iphone6s-dns-runtime.tar.gz python3 /CAMINHO/ARVORE/tests/run_dns_server_mutations.py
```

Somente namespace VM root explicitamente autorizado; não execute o fixture com privilégios no Mac/servidores reais. Bibliotecas/executáveis já disponíveis: BusyBox estático, loader ARM64, Python, dig, ip, mount, chroot e unshare. O fixture monta proc somente em seu namespace, usa endereços sintéticos e remove seus processos/arquivos. O runner recusa baseline falha/skips antes de interpretar rejeições de mutantes.

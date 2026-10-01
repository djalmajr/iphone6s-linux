# Perfis privados de implantação — #12

## Contexto

A candidata da VM nova tem imagem e identidades diferentes da implantação conhecida. Boot, snapshots, LAN e DNS selecionam essas identidades por `IPHONE_LINUX_PROFILE`. Sem a variável, permanecem os caminhos da implantação conhecida. A integração foi validada no Mac, em VM e no iPhone. O primeiro boot físico da candidata passou; o retorno à imagem Linux conhecida e o restore DNS em outro boot continuam pendentes.

## Contrato e arquivos

- Perfil JSON privado, formato 1, modo 600, dentro de uma pasta privada modo 700. Campos exatos: `format`, `payload`, `sha256`, `initramfs`, `initramfs_sha256`, `client_key`, `known_hosts`, `host_key_alias`.
- Os quatro caminhos são relativos à pasta do perfil, sem symlinks/hardlinks, escapes ou caracteres de controle; arquivos privados pertencem ao usuário atual. A seleção explícita inválida falha; não retorna às chaves ou imagem padrão.
- Endereço do telefone fixo em `172.16.42.1`; não permitir escolher destinos remotos pelo perfil. SSH sem config pessoal, por chave explícita e pin estrito, sem agent forwarding.
- Na verificação de boot: conferir os hashes do payload/initramfs, vínculo do initramfs com o fim do payload, permissões CPIO das identidades, cliente público derivado com `ssh-keygen -y -P ''` contra authorized_keys e pin contra o campo público da chave Ed25519 Dropbear embutida. Leitura de arquivo, sem extrair ou executar a imagem. O campo público não comprova sozinho a matemática da chave privada; a imagem real passou em SSH na VM e no iPhone.
- Sem perfil: conservar imagem, caminhos e comportamento já comprovados. Perfil explícito só para a imagem integrada; `boot-probe` e `install-terminal` recusam essa combinação para não misturar runtimes.
- Snapshots mantêm o armazenamento privado existente do mesmo projeto/aparelho. O perfil seleciona transporte e imagem, não muda o escopo dos arquivos restaurados.

## Fases

1. `scripts/host/device_profile.py`, `profile_image.py`, `tests/test_device_profile.py`, `tests/run_profile_mutations.py`, este documento: loader/preflight/CLI, fixtures com chaves sintéticas, controles negativos e perfil privado real da candidata. Cinco arquivos públicos.
2. Seleção compartilhada em rodadas de até cinco arquivos:
   - Preparação: `tests/test_lan.py`, `test_autosnap.py`, `test_autosnap_vm.py`, `run_autosnap_mutations.py`, `run_lan_mutations.py` passam a copiar/importar o helper. Cinco arquivos.
   - Transporte: `scripts/host/persist.py`, `lan.py`, `dns_lan.py`, `tests/test_profile_transport.py`, `run_dns_lan_mutations.py`. Os fixtures DNS já copiam todos os módulos host e não precisaram de alteração. Cinco arquivos.
   - Wrapper: `scripts/host/iphone-linux.sh`, `tests/test_profile_boot.py`, `run_profile_mutations.py`, `test_lan.py`, este documento. Perfil inválido falha antes de USB/listener; `boot-probe` e `install-terminal` recusam perfil explícito. Cinco arquivos.
3. Documentar operação/rollback, publicar evidências e atualizar #12/#17. Primeiro boot físico e restauração de arquivos concluídos; rollback Linux e restore DNS após reboot continuam pendentes.

## Verificação

- Baseline do perfil sintético e da candidata real, sem rede ou exploração USB.
- Rejeitar imagem alterada, initramfs trocado, chave cliente diferente, pin diferente, arquivo público, link/escape e formato inválido; remover checks deliberadamente e comprovar que os testes falham.
- Inspecionar configuração efetiva OpenSSH com `ssh -G`, incluindo chave, pin/alias, destino e ausência de encaminhamento de agente.
- Testar integração do wrapper com ferramentas USB falsas e sentinela de envio; nenhum aparelho real ou chave privada real entra nos testes versionados.
- ShellCheck/Bash, lint Python disponível e parsing; não há typechecker configurado neste repositório.
- Reutilizar gates não afetados; testes de integração que dependem de transportes alterados precisam ser repetidos.

## D1. Seleção explícita compartilhada

- **Decisão:** variável `IPHONE_LINUX_PROFILE` aponta para JSON privado; helper único compõe os dados de identidade e valida a candidata antes do boot.
- **Por quê:** wrappers e processos filhos recebem a mesma seleção sem copiar código ou trocar arquivos da implantação anterior. Um caminho inválido interrompe o comando.
- **Alternativas:** editar hashes/chaves fixos a cada teste multiplica pontos de erro; copiar o projeto para outra implantação duplica a lógica; um alias SSH global depende da configuração pessoal do Mac.
- **Reverter:** baixo; deixar de passar a variável volta à implantação conhecida. Dados privados da candidata continuam preservados.
- **Onde:** helpers, wrapper e consumidores listados acima; #12.
- **Status:** aplicada e comprovada em boot físico; rollback Linux ainda pendente.

## D2. Autenticação e compatibilidade de recuperação

- **Decisão:** transportar snapshots pelo helper em cada operação; manter a injeção de transporte dos testes de restauração. Com perfil explícito, o wrapper exige SSH selecionado antes de aceitar HTTP ou usar comandos remotos; não usa o terminal de recuperação nesse caso.
- **Por quê:** alterar o perfil não pode deixar uma lista SSH antiga em memória nem executar um comando por outra identidade depois que a autenticação falha. O fluxo de recuperação da imagem probe padrão permanece disponível.
- **Alternativas:** fixar o transporte no import ignora mudanças posteriores da seleção; permitir fallback após falha de pin elimina a garantia da identidade; remover toda recuperação impediria o fluxo probe existente.
- **Reverter:** baixo; `unset IPHONE_LINUX_PROFILE` seleciona os defaults. Os controles de isolamento do perfil podem ser revertidos na branch, com perda das garantias documentadas.
- **Onde:** `persist.py`, `iphone-linux.sh`, testes de transporte/boot e #12.
- **Status:** aplicada e validada localmente/em VM.

## Tarefas

- [x] Loader, preflight e perfil privado real verificados.
- [x] Seleção compartilhada integrada em todos os consumidores.
- [x] Baselines, controles negativos, mutações e lint publicados.
- [x] Primeiro boot físico da candidata, SSH/HTTP e restauração de arquivos comprovados.
- [ ] Rollback para a imagem Linux conhecida e restore DNS em novo boot comprovados.

## Evidência da fase 1

O runner `python3 tests/run_profile_mutations.py` executou baseline de **8 testes** com chaves temporárias sintéticas e rejeitou **11/11 mutações** por falha de asserção, incluindo pin SSH estrito, seleção vazia, formato booleano, permissões privadas, hash, vínculo payload/initramfs, identidade cliente/servidor, permissões embutidas, arquivo CPIO extra e Telnet. As cópias temporárias excluem artefatos, chaves, backups e runtime privados.

O perfil privado da candidata real retornou `PROFILE_IMAGE_IDENTITIES_OK` por `device_profile.py check`. Isso comprova coerência local entre os arquivos selecionados; não houve acesso ao USB, boot ou conexão de rede nesse comando. Na primeira fase, os consumidores ainda não estavam integrados; a fase 2 abaixo concluiu essa integração.

O formato de chave Dropbear foi conferido na [implementação Ed25519 da versão 2022.83](https://github.com/mkj/dropbear/blob/DROPBEAR_2022.83/ed25519.c), correspondente ao userspace selecionado. A comparação usa o campo público serializado; o teste de autenticação real na VM e o boot físico são provas distintas.

Lint Python (`pyflakes`, `flake8 --select E9,F63,F7,F82`) e parsing passaram nos quatro arquivos Python. Não há typechecker configurado. Imagens e identidades permanecem privadas; nenhum segredo faz parte dos testes versionados.

## Evidência da fase 2

- `python3 tests/run_profile_mutations.py`: **15 testes de baseline** (8 loader/imagem, 2 transporte, 5 wrapper), **20/20 mutações rejeitadas por asserção**. O wrapper selecionou o payload/SSH da fixture e recusou seleção inválida, imagem ou identidade incompatível antes do USB, fallback de recuperação e HTTP sem autenticação. Os insumos USB, SSH, curl, ifconfig e palera são sintéticos nesses testes; isso não prova boot físico.
- macOS: **6 testes de snapshots**, **6 do agendador**, **2 do wrapper DFU existente** passaram. Os testes de LAN/OpenSSH e DNS local passaram; o listener temporário do teste DNS foi limitado a `127.0.0.1` e precisou de execução fora do sandbox. Os testes de VM foram explicitamente separados dos skips locais.
- VM dedicada: **4 testes LAN** passaram, incluindo um perfil privado com cliente/alias diferentes dos defaults e autenticação real OpenSSH/Dropbear; **3 testes DNS** passaram, incluindo UDP/TCP, allowlist, escopo de bind, perda de túnel e limpeza; **1 teste de snapshots/restore BusyBox** passou. O fixture LAN de perfil usa arquivos de imagem opacos, não bootáveis: prova o transporte selecionado, não o preflight/boot.
- Controles negativos reais na VM: **4/4 mutações LAN** rejeitadas (pin, falha de listener, bind omitido/wildcard); mutação de confiança no DNS rejeitada; trocar o alias do perfil também impediu a publicação de sessão/listener e o helper foi restaurado exatamente. Os **3 controles LAN locais** passaram na preparação. Gates anteriores não afetados foram reutilizados.
- Bash syntax/ShellCheck, pyflakes, flake8 E9/F63/F7/F82 e parsing passaram. Não há typechecker configurado. Nenhum pacote foi instalado no Mac ou na VM nesta etapa; foram usados os fixtures existentes, com hash do bundle DNS comparado ao local.

Durante a construção do simulador, dois erros de fixture foram corrigidos: o USB falso ficava pronto antes de o sender receber os dados, e `source ... backups` encerrava o shell por `exec` antes de testar `remote`. A fixture agora só apresenta USB após o envio e usa `connect` antes de exercitar o fallback. A baseline completa e as mutações passaram após as correções.

## Operação e retorno aos defaults

Na pasta `iphone-linux-tools`, selecione um JSON privado validado; não copie identidades para `keys/` nem publique seu conteúdo:

```bash
export IPHONE_LINUX_PROFILE="/CAMINHO/PRIVADO/deployment.json"
python3 scripts/host/device_profile.py check
./scripts/host/iphone-linux.sh boot --restore ID
./scripts/host/iphone-linux.sh shell
./scripts/host/iphone-linux.sh backup
./scripts/host/iphone-linux.sh lan --bind IP_PRIVADO_DO_MAC
./scripts/host/iphone-linux.sh dns status
```

O boot continua dependente de DFU manual e Mac; o preflight não faz exploração USB. Cada processo filho herda a seleção, inclusive o agendador de snapshots. Use `boot` sem `--restore` quando não houver snapshot a aplicar. Os comandos LAN/DNS mantêm o mesmo escopo de rede e não alteram DNS de clientes/roteador.

Para retornar à implantação conhecida: salve um snapshot; confirme o retorno ao iOS pelo USB (reinício de software em investigação na [#21](https://github.com/djalmajr/iphone6s-linux/issues/21)); depois, execute `unset IPHONE_LINUX_PROFILE` no Mac e faça o boot padrão com novo DFU manual. Isso é o procedimento de rollback planejado; a execução física com a candidata ainda precisa ser comprovada. Excluir a variável não troca a identidade de um Linux já rodando: antes do reboot, mantenha o perfil correspondente para SSH/backups.

## Primeiro boot físico — 2026-09-30 / 2026-10-01 UTC

O perfil privado selecionou a candidata reconstruída na VM nova. A execução de `boot` terminou com saída 0 depois do envio, configuração do enlace USB, autenticação SSH estrita e HTTP. No iPhone: kernel 7.0.12, páginas de 16 kB, Bash 5.2.21, Herdr 0.9.1 e loopback UP. Herdr foi verificado por versão nesta rodada; isso não comprova ainda seu bootstrap/reconexão da #13.

Um snapshot anterior foi restaurado pelo transporte do perfil. A comparação exata dos hashes privados de authorized_keys e da chave de host confirmou preservação das duas identidades. DNS foi instalado em RAM, executado como UID/GID 65534, consultado por UDP/TCP pelo Mac e por sockets .NET de um Windows independente através do proxy versionado. O cliente nslookup falhou e não foi aceito como prova positiva.

Snapshot final validado com 41 entradas; daemon DNS próprio e listeners temporários encerrados. Reboot solicitado no uptime 1128,59 s (18 min 48 s); esse pedido normal não reiniciou o init mínimo. SSH/gadget e uptime contínuo foram confirmados depois. Às 00:24:02 UTC, no uptime 2327,83 s, `sync; /bin/busybox reboot -f` derrubou o enlace, mas iOS não reapareceu no USB. Recuperação Power + Home até maçã foi solicitada; medição posterior de bateria pendente. Não foi usado `boot --restore` nesta candidata: o restore ocorreu depois do boot. O retorno à imagem Linux conhecida exige outro DFU e permanece pendente. [Evidência sanitizada](evidence/dns-physical-check.json).

### Retorno ao iOS: limite observado

Não interpretar saída SSH 0, timeout ou console congelado como prova de reboot. O pedido normal do BusyBox depende de PID 1 tratar shutdown; este init é um shell mínimo. `-f` contorna o init, mas o teste só comprovou perda do enlace Linux, não retorno ao iOS. Até resolver #21, após salvar os arquivos, o fallback é Power + Home até maçã, soltando ambos e confirmando iOS no USB. A variável de perfil só deve ser removida após encerrar o Linux correspondente.

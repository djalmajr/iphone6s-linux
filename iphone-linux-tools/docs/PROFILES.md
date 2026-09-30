# Perfis privados de implantação — #12

## Contexto

A candidata da VM nova tem imagem e identidades diferentes da implantação conhecida. Os scripts de boot, snapshots e rede ainda usam caminhos fixos. Esta etapa centraliza a seleção por `IPHONE_LINUX_PROFILE`, sem mudar a seleção padrão nem carregar uma imagem no telefone durante a implementação.

## Contrato e arquivos

- Perfil JSON privado, formato 1, modo 600, dentro de uma pasta privada modo 700. Campos exatos: `format`, `payload`, `sha256`, `initramfs`, `initramfs_sha256`, `client_key`, `known_hosts`, `host_key_alias`.
- Os quatro caminhos são relativos à pasta do perfil, sem symlinks/hardlinks, escapes ou caracteres de controle; arquivos privados pertencem ao usuário atual. A seleção explícita inválida falha; não retorna às chaves ou imagem padrão.
- Endereço do telefone fixo em `172.16.42.1`; não permitir escolher destinos remotos pelo perfil. SSH sem config pessoal, por chave explícita e pin estrito, sem agent forwarding.
- Na verificação de boot: conferir os hashes do payload/initramfs, vínculo do initramfs com o fim do payload, permissões CPIO das identidades, cliente público derivado com `ssh-keygen -y -P ''` contra authorized_keys e pin contra o campo público da chave Ed25519 Dropbear embutida. Leitura de arquivo, sem extrair ou executar a imagem. O campo público não comprova sozinho a matemática da chave privada; a imagem real já passou em SSH na VM e ainda precisa do teste físico.
- Sem perfil: conservar imagem, caminhos e comportamento já comprovados. Perfil explícito só para a imagem integrada; `boot-probe` e `install-terminal` recusam essa combinação para não misturar runtimes.
- Snapshots mantêm o armazenamento privado existente do mesmo projeto/aparelho. O perfil seleciona transporte e imagem, não muda o escopo dos arquivos restaurados.

## Fases

1. `scripts/host/device_profile.py`, `profile_image.py`, `tests/test_device_profile.py`, `tests/run_profile_mutations.py`, este documento: loader/preflight/CLI, fixtures com chaves sintéticas, controles negativos e perfil privado real da candidata. Cinco arquivos públicos.
2. Seleção compartilhada em rodadas de até cinco arquivos:
   - `scripts/host/persist.py`, `lan.py`, `dns_lan.py`, `tests/test_lan.py`, `tests/test_dns_lan.py`: transporte e fixtures devem usar o helper único, preservando defaults.
   - Adaptar os runners de mutação e fixtures afetados pela nova dependência; conferir todos os pontos que copiam scripts para projetos temporários.
   - `scripts/host/iphone-linux.sh`, `tests/test_boot_wrapper.py` e testes dedicados: boot e comandos devem usar a mesma seleção; falhar antes de exploração USB/listener quando o perfil é inválido. `boot-probe` e `install-terminal` recusam perfil explícito.
3. Documentar operação/rollback, publicar evidências e atualizar #12/#17. Boot físico segue pendente da disponibilidade já solicitada para DFU manual.

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
- **Status:** em curso.

## Tarefas

- [x] Loader, preflight e perfil privado real verificados.
- [ ] Seleção compartilhada integrada em todos os consumidores.
- [ ] Baselines, controles negativos, mutações e lint publicados.
- [ ] Boot físico da candidata e rollback comprovados.

## Evidência da fase 1

O runner `python3 tests/run_profile_mutations.py` executou baseline de **8 testes** com chaves temporárias sintéticas e rejeitou **11/11 mutações** por falha de asserção, incluindo pin SSH estrito, seleção vazia, formato booleano, permissões privadas, hash, vínculo payload/initramfs, identidade cliente/servidor, permissões embutidas, arquivo CPIO extra e Telnet. As cópias temporárias excluem artefatos, chaves, backups e runtime privados.

O perfil privado da candidata real retornou `PROFILE_IMAGE_IDENTITIES_OK` por `device_profile.py check`. Isso comprova coerência local entre os arquivos selecionados; não houve acesso ao USB, boot ou conexão de rede nesse comando. Os consumidores ainda precisam da fase 2; definir a variável nesta etapa não muda o wrapper existente.

O formato de chave Dropbear foi conferido na [implementação Ed25519 da versão 2022.83](https://github.com/mkj/dropbear/blob/DROPBEAR_2022.83/ed25519.c), correspondente ao userspace selecionado. A comparação usa o campo público serializado; o teste de autenticação real na VM e o futuro boot físico são provas distintas.

Lint Python (`pyflakes`, `flake8 --select E9,F63,F7,F82`) e parsing passaram nos quatro arquivos Python. Não há typechecker configurado. Imagens e identidades permanecem privadas; nenhum segredo faz parte dos testes versionados.

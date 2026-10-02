# Desenvolver mantendo o Linux ativo

Direção atual em 2026-10-02: reduzir DFU/reinicializações e priorizar a infraestrutura que facilita várias entregas. [Plano e decisões](../.agents/plans/desenvolvimento-sem-reboots.md).

## Ordem de trabalho

1. **Wi-Fi N71/A9 (#9):** identificar o caminho específico de barramento, energia, DMA e firmware. O inventário físico da candidata já passou; ainda não existe rádio enumerado. A referência Apple N71 foi obtida e analisada offline: PCIe S8000, porta 1, família BCM4350 e DART S5L8960X. Próximo trabalho é suporte específico ao controlador/PHY e sua integração no DT. [Resultados](WIFI.md).
2. **Sessão de desenvolvimento (#32):** editar/versionar no Mac, verificar localmente/na VM e enviar somente arquivos necessários por SSH. Atualizar/reiniciar apenas o serviço afetado, mantendo Bash/Herdr e conectividade USB. O updater DNS já implementa destinos fixos, SHA256, checkpoint verificado, recusa quando o Linux está ausente e rollback, com prova no mesmo boot real.
3. **Energia/telemetria (#2):** dar suporte a sessões mais longas. A candidata não apresentou power_supply; carregar no iOS não demonstra carga sustentada no Linux. #8 depende desse gate.
4. **Storage/boot (#10/#11):** mapear suporte N71 para reduzir a dependência do Mac, sem presumir compatibilidade A10.
5. **DNS53/política (#19):** retomar na mesma sessão Linux disponível quando as prioridades anteriores permitirem. Helpers/testes já aprovados permanecem válidos enquanto suas fontes/ambiente relevantes não mudarem.

## O que exige um novo boot

| Alteração ou prova | Ação |
|---|---|
| Arquivos de serviço, configuração, scripts Bash, dados, HTTP/DNS/Herdr | Enviar por SSH e reiniciar somente o serviço afetado; não executar boot --restore |
| Investigação de sysfs, logs, interfaces ou drivers já presentes | Ler no boot atual |
| Código do Mac, cliente Windows, testes de transporte | Validar no host/VM; usar o Linux existente para integração |
| Kernel, DTB ou initramfs integrado usados no início | Preparar uma candidata offline e agrupar os gates em um novo boot |
| Prova de restore/autostart/retorno ao iOS | Reiniciar deliberadamente uma vez por conjunto de critérios |
| USB/SSH recuperável sem novo boot | Reconectar/diagnosticar o enlace primeiro |
| Kernel travado ou falha de hardware | Usar recuperação documentada, preservando o último snapshot |

## Roteiro de sessão

1. Conferir as issues a resolver juntas, a candidata e o snapshot de recuperação. Fazer checagens locais e builds na VM antes de envolver o telefone. Pedir autenticação do host antes do DFU; um timeout de senha não obriga a reiniciar o Linux.
2. Se o SSH do Linux atual responde, continuar nele. Caso a mudança exija nova imagem, executar o wrapper com o perfil explícito e restore do snapshot verificado. Ver [perfis](PROFILES.md).
3. Guardar um checkpoint antes de trocar arquivos importantes. Usar os comandos de [persistência](PERSISTENCIA.md); os backups são privados. Bash/SSH já estão presentes; não reinstalá-los a cada mudança.
4. Transferir apenas o conjunto necessário para o destino previsto, conferir SHA256 e testar o comportamento real. Não enviar credenciais nos logs ou para o GitHub. Não sobrescrever a imagem funcional para um teste de userspace.
5. Repetir somente o teste que depende da alteração; agrupar SSH, HTTP, DNS e Herdr no mesmo boot. Não confundir testes de fixtures com funcionamento no telefone.
6. Salvar um novo snapshot ao concluir a fatia. Só executar o [retorno ao iOS](REBOOT.md) quando a sessão tiver terminado, o teste precisar dele ou a condição de energia exigir. Não deixar uma sessão prolongada sem gate de alimentação aprovado.

**Limites:** o updater abaixo implementa o serviço DNS declarado; outros serviços ainda exigem definir destinos e lifecycle específicos. Persistência interna, Wi-Fi e carga sustentada continuam pendentes. O acesso por USB permanece necessário nesta candidata. Apenas os diretórios configurados em [persistência](PERSISTENCIA.md) entram nos snapshots; mudanças fora deles exigem reprodução pela construção ou registro explícito.


## Atualização DNS sem DFU — implementada e comprovada

A partir da raiz do repositório, use o perfil privado da imagem em execução. O comando `check` só lê estado; sua saída contém boot_id e deve ficar privada.

```sh
export IPHONE_LINUX_PROFILE="$PWD/iphone-linux-tools/runtime/SEU-PERFIL/deployment.json"
python3 -B iphone-linux-tools/scripts/host/dev.py check
python3 -B iphone-linux-tools/scripts/host/dev.py dns --hosts /CAMINHO/PRIVADO/hosts
python3 -B iphone-linux-tools/scripts/host/dev.py rollback ID_DA_TRANSACAO
```

O arquivo de hosts precisa ser regular, sem links/hardlinks, sem escrita por grupo/outros, limitado a 64 KiB. Cada linha tem um IPv4 privado e um nome home.arpa; preserve `172.16.42.1 iphone-usb.home.arpa`. Não use nomes duplicados. O manager enviado é a fonte versionada `phone/dns/manage-dns.sh`.

Destinos únicos: `/srv/data/dns/manage-dns.sh` e `/srv/data/dns/hosts`. O envio não aceita paths arbitrários. Confere hashes antigos/novos e do transporte, recusa links e lock concorrente, salva o estado anterior e reinicia somente DNS5353. O host confirma todos os registros por UDP e TCP, kernel, boot_id e progressão de uptime. Não inicia DFU, não altera a rede do Mac e não fornece endpoint DNS53.

O checkpoint anterior e posterior usa a persistência existente: `/srv/data` e arquivos de trabalho em `/root`, com exclusões documentadas em [persistência](PERSISTENCIA.md). A reversão lê somente os dois membros DNS do checkpoint anterior; não restaura outros serviços nem identidades. A transação de rollback também cria seus próprios checkpoints. Logs/IDs/receipts ficam privados em `runtime/dev/ID/result.json`.

Se falhar aplicação ou health check, tenta recuperar somente os arquivos DNS. `recovery-required` significa que a recuperação não foi comprovada: preserve o journal e use [recuperação](RECUPERACAO.md). Uma falha do snapshot final pode ocorrer depois de o serviço já estar aplicado; confira `state=applied` no journal, em vez de presumir ausência de mudanças. A transação deve pertencer à mesma identidade SSH do perfil.

### Provas em 2026-10-02

Deploy de registro temporário e rollback passaram no telefone `7.2.0-iphone6s-source`: DNS UDP/TCP, hashes originais recuperados e quatro checkpoints verificados. Uptime 6328,17 → 6442,06 s, boot_id igual e SSH estrito preservado. **Zero reinicializações.** [Evidência sanitizada](evidence/dev-session.json).

Mac: 15 testes, dez passaram e cinco fixtures privilegiadas explicitamente puladas; sete mutações rejeitadas por asserção. VM Ubuntu dedicada: 15 testes passaram, incluindo falha de start com restauração de bytes/modos/estado, divergência de hash sem parar serviço, links/lock/destino inválidos; 12 mutações rejeitadas por asserção. A VM recebe somente fontes públicas e fixtures, nunca chaves, firmware ou snapshots do Mac. Nenhuma instalação no Mac.

Reprodução dos gates:

```sh
python3 -B iphone-linux-tools/tests/run_dev_mutations.py
# Somente dentro da VM dedicada, com BusyBox estático já disponível:
sudo env IPHONE_DEV_VM_TESTS=1 python3 -B /CAMINHO/DO/PROJETO/tests/run_dev_mutations.py
```

O opt-in privilegiado cria chroots temporários, sem mounts; fixtures não provam hardware. Mudanças de kernel/DTB/initramfs continuam exigindo uma candidata offline e um boot agregado. Não reexecutar restore/boot para atualizar somente os arquivos DNS.

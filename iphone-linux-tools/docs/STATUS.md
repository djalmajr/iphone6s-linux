# iPhone 6s Linux — atualizado em 2026-10-02

## Direção de desenvolvimento — 2026-10-02

Prioridade do operador: Wi-Fi e recursos que facilitem a iteração, com o mínimo de reinicializações. [Fluxo de sessões e ordem](DESENVOLVIMENTO.md). DNS53 deixa de ser a próxima entrega; seus gates aprovados são preservados e o piloto funcional continua pendente.

Inventário físico por SSH no boot já ativo 7.2.0-iphone6s-source: somente lo/usb0, ieee80211 ausente, PCI/SDIO/MMC sem dispositivos, nenhum módulo e nenhum compatible correspondente entre 118 propriedades examinadas. Sem power_supply ou ADT original no chosen consultado. Nenhum reboot, firmware, driver ou política de rede nesta fase. [Wi-Fi](WIFI.md), [evidência](evidence/wifi-runtime.json). Próximo gate é identificação offline da topologia N71 para implementação específica A9; associação/DHCP ainda não podem ser testados.

O boot imediatamente anterior desta rodada restaurou os três arquivos DNS com hashes/tamanhos exatos, SSH/kernel/HTTP e Herdr confirmados. Roteiro privado de preflight errou ao chamar dns.start inexistente; não é prova de DNS5353. Controlador DNS53 expirou esperando prontidão e não abriu o endpoint. Nenhuma consulta DNS53 Mac/Windows executada. A nova prioridade não transforma esse piloto em sucesso.

## Estado atual e gates pendentes

As provas abaixo são de sessões já concluídas, não indicam um servidor ativo agora. O telefone executou Linux 7.0.12 em RAM, console automático, Bash/SSH/HTTP por USB e serviços encaminhados para a LAN. A cadeia compilada (kernel 7.2.0 e Pongo de fonte) iniciou no aparelho, com console/SSH/HTTP, restore e DNS USB UDP/TCP. Driver apple-watchdog vinculado; retorno espontâneo ao iOS confirmado pelo operador e USB. O CLI antigo perdeu a confirmação de sync e retornou falha; correção passou em novo piloto com snapshot/sync/retorno verificados e CI aprovada. Rollback Linux7.0.12 também passou com restore/SSH/HTTP/retorno; limite de proveniência do legado permanece na #12. [Evidência física](SOURCE-CHAIN-PILOT.md).

DNS padrão #19: diferenças Darwin de grupos (#30) e adoção/fechamento de sockets (#31) corrigidas. Fonte32c39d4 passou33 casos/26 mutações Mac,37/31 na VM isolada e CI terminal com seis jobs. Helper nativo da fonte exata passou UID/GID/grupos/peer/nonce, dados UDP/TCP depois de sua saída e cleanup de FDs/diretório/endpoints53. Isso é teste de sockets, sem consulta ao telefone: piloto DNS53 do iPhone/Windows e política dos clientes continuam pendentes. Retorno físico ao iOS confirmado por USB após fallback,98% e carga ativa; retornoCLI1 anterior preservado. Sem serviço53 do projeto ativo ou política global alterada. [Contrato e reprodução](DNS-STANDARD.md), [evidência](evidence/dns-standard-port.json).

| Área | Evidência e limite atual |
|---|---|
| Boot e recuperação de arquivos (#3/#4) | Wrapper com DFU manual e restore comprovados no aparelho; [operação](EXECUCAO.md) e [perfil](PROFILES.md) |
| Snapshots e falhas (#5/#15) | Agendador/retenção com prova física curta; recuperação explícita de ENOSPC/interrupção em VM. Correção #22 recusa desvios locais por links, validada em Mac/VM/CI; [procedimentos](RECUPERACAO.md) e [evidência](evidence/local-snapshot-paths.json) |
| LAN e DNS (#6/#7) | Correção #24 valida nomes do bundle antes do SSH, com prova local/VM; SSH/HTTP e DNS UDP/TCP pelo Mac/Windows; DNS recuperado em segundo boot. Não configura DNS global ou saída geral de internet; porta 53 e política de resolvedores continuam na #19. Fixture LAN independente reproduziu falha do nslookup por argumentos/stdin sem perguntas recebidas, enquanto quatro consultas de sockets Windows UDP/TCP passaram nas mesmas portas 15953/1053; controle em loopback Windows também reproduziu oito falhas nativas enquanto quatro consultas sockets passaram, com listeners encerrados. Cliente de sockets completo implementado: 61 casos e 18 mutações passaram no Windows real; CLI UDP/TCP passou em fixture LAN nas duas portas e recusou sete entradas inválidas. Cliente público passou contra o iPhone em novo boot/restore: dois positivos UDP/TCP e três negativos nome/endereço/porta, controle Mac e cleanup/retorno CLI0; [evidência física](evidence/windows-dns-physical.json). Causa específica do nslookup desconhecida. [Diagnóstico Windows](DNS-WINDOWS.md) e [DNS](DNS.md) |
| DNS padrão (#19) | [Preparação](DNS-STANDARD.md): inventário do kernel mostrou binds 53 existentes; endpoint LAN selecionado sem bind IPv4 observado, mas UDP/TCP não root recusados por EACCES. Bootstrap mínimo implementado e validado em testes Mac/VM/CI; helper nativo com ACK/dados/cleanup aprovado; piloto DNS53 do telefone e política dos clientes pendentes. Sem listener 53 do projeto no Mac, upstream ou alteração global. [Evidência](evidence/dns-standard-port.json) |
| Reprodução (#12) | m1n1 reproduzido, imagem userspace validada em VM nova e dois boots curtos. Kernel/Pongo de fonte compilados, empacotamento/seleção com hashes fixos; nova cadeia com boot/restore/DNS USB comprovados; rollback Linux conhecido comprovado; proveniência do legado ainda limitada; [Pongo](PONGO-SOURCE-BUILD.md) |
| CI (#14) | Matriz pública Ubuntu/macOS e novo job Windows de DNS, sem chaves/imagens reais; job DNS Windows aprovado. Tests/skips/mutações associados ao commit no [manifesto Pongo](evidence/pongo-source-build.json); CI não prova hardware |
| Alimentação/estabilidade (#2/#8) | Carga sustentada e estabilidade prolongada não estabelecidas; sem sensores Linux validados; [alimentação](ALIMENTACAO.md) |
| Retorno ao iOS (#21) | Helper salva/verifica snapshot e confirma USB/modelo; novo kernel com watchdog vinculado e retorno espontâneo comprovados. CLI corrigido passou com snapshot/sync/retorno USB, saída0 e CI aprovada; fallback físico preservado; [recuperação](REBOOT.md) |
| Herdr/hardware (#13/#9/#10/#11) | [Herdr optativo](HERDR.md) implementado com Bash, lock, restart explícito e marcador restaurável; testes locais/VM passaram; correção #29 dispensa nohup ausente no runtime, com regressão/mutações, VM real e CI aprovados. Dois boots da cadeia de fonte passaram com Bash/TUI SSH pelo Mac, reconexão sem duplicação e autostart após restore de marcador/arquivo; [prova física](evidence/herdr-physical.json). [Storage N71](ARMAZENAMENTO.md) sem controlador/driver comprovado e [boot autônomo](BOOT-AUTONOMO.md) sem cadeia pronta; [Wi-Fi N71](WIFI.md) sem caminho operacional na candidata, com requisitos de barramento/energia/firmware ainda abertos |
| Integração (#16) | Branch/PR #1 abertas; descrição alinhada aos gates realizados, revisão parcial de persistência/boot/DNS/build com correções #22/#23/#24 e proteção de saída #25 verificada em Mac/CI; proteção do estado do agendador #26 verificada em Mac/CI. Contratos de provas DNS #27 e restore #28 corrigidos e verificados em Mac, VM isolada e CI; inventário de 169/170 leituras no checkpoint `49d8747`, todos os textos conferidos; índice APK binário verificado separadamente por estrutura/assinatura, sem leitura textual declarada; checklists DNS/execução/fresh-build alinhados aos pilotos concluídos e histórico identificado. [Cobertura e limites](PR-REVIEW.md); revisão completa e autorização de merge pendentes |

Nenhum pacote instalado no Mac nesta evolução. Downloads, fontes externas, artefatos, chaves e snapshots ficam privados; builds externos somente em VMs dedicadas. Para trocar Pongo ou perfil de Linux, confirmar primeiro o fim da sessão anterior; retirar uma variável não altera uma sessão já iniciada.


## Checkpoint histórico — reprodução de m1n1 (#12)

Dois clones novos da fonte oficial foram compilados offline na VM existente. O clone com profundidade 1 e sem tags reproduziu o componente preservado byte por byte: 1.196.032 bytes, SHA-256 `13d49ab42c6e071857ca05c8414f30dca70699df8a3f472b9c70e4f1233a092b`. O clone completo gerou uma versão diferente via `git describe`; a profundidade foi incorporada à receita, sem override manual de versão. Ambos terminaram com saída 0 e dois avisos upstream. Quatro arquivos crate e 131 fontes em cache foram conferidos; fontes e payload conhecido preservados. Nenhum pacote foi instalado, nem candidato carregado no telefone. A VM dedicada foi parada após confirmar ausência de processos de build. [Receita, decisão e limites](M1N1-BUILD.md), [evidência](evidence/m1n1-rebuild.json).

Naquele checkpoint, #12 ainda aguardava autenticidade do pacote/reprodução em VM nova e #7 aguardava o piloto DNS. Esses gates avançaram depois, conforme o estado atual e os documentos acima. A assinatura própria do APK original/commit `-dirty` mantém limites específicos; a candidata de kernel de fonte é separada. #8 continua dependente de alimentação validada (#2). Nenhuma dessas pendências é resolvida pela igualdade do componente m1n1. Nenhum typechecker do projeto foi configurado; esta etapa alterou apenas documentação e executou builds upstream. JSON, identidade dos artefatos e links locais foram verificados; testes de código inalterado permanecem válidos.

## Validated capabilities: Linux, Bash, SSH, HTTP and Herdr

Bash 5.2.21, key-only Dropbear SSH and Herdr 0.9.1/protocol 22 were verified on the phone. The Herdr pane survived disconnecting the SSH client. Bootstrap Telnet is now stopped. The runtime and candidate image contain a private SSH server key and remain local. Before the folder reorganization on 2026-09-30, the manual-DFU wrapper completed a full boot with exit 0, integrated SSH/HTTP and operator-confirmed console (#3). The dedicated build VM was stopped after recording package versions. See `REPRODUCAO.md` for the full chronology and public evidence.

## File persistence — verified 2026-09-29

Private snapshots on the Mac cover `/srv/data` and work files in `/root`. Restore checks integrity/scope and captures a pre-restore snapshot before overwriting. Tests recovered contents/modes, retained extras and blocked invalid links. On 2026-09-30, recovery after a fresh DFU also passed: sentinela/hash, mode 640, extra file, SSH identities and HTTP verified (#4). Snapshots exclude SSH identity and live Herdr state. Opt-in automatic snapshots/retention and boot restore later passed a short physical pilot (#5); explicit interrupted-restore recovery passed ENOSPC/process-interruption fixtures in the dedicated VM (#15). See `PERSISTENCIA.md`, `AUTOSNAPSHOTS.md` and `RECUPERACAO.md`.

## Display console — verified 2026-09-29

`simpledrm` exposed fb0 at 750 × 1334. Unblanking, writing tty1 and switching VT activated fbcon. The user confirmed both the initial console text and commands typed through an SSH Bash mirrored by util-linux `script`. The `console` helper is tested. The integrated image booted and the user confirmed the console appeared automatically; see `CONSOLE.md`.

## Folder organization and power checks — 2026-09-30

Scripts now live in `scripts/host`, `scripts/boot` and `scripts/build`; phone sources in `phone`; ignored binaries/images/logs in `bin`, `artifacts` and `logs`. Run `bash scripts/host/iphone-linux.sh ...` from the tools directory. Reorganization preserves all 18 artifact hashes; warm status/HTTP and snapshot creation passed using the new paths. A subsequent cold boot and restore using the relocated CLI also passed: wrapper exit 0, operator-confirmed console, strict SSH/HTTP and sentinel content/mode restored with SSH identities unchanged.

Sustained charging remains open (#2). A roughly 12-minute USB-A interval returned iOS charge 100% from a 94% baseline; a later roughly 25-minute Linux interval returned 90% after an earlier 100% reading. Both include preparation/reboot and possible gauge variation. A later 17-minute interval with reduced/variable brightness returned iOS 100% from 98%, but raw current-capacity decreased (873 to 854) and raw maximum changed (884 to 877); units and semantics of those fields remain unvalidated. The percentage ceiling and conflicting gauge fields prevent a sustained-charge claim. Effective gadget MaxPower was 500 mA; no descriptor was changed. The operator reported cold/lukewarm and visible console. No Linux battery/temperature sensors were available. See `ALIMENTACAO.md`.


### Cliente Windows53 — evidência e CI publicados

Extensão b4fe9e4: seleção explícita53 adicionada, default1053 conservado;54–1023 continuam recusadas. Regressão nova contra fonte antiga terminou1 por DNS_TEST_ASSERTION standard-port, com compilação válida. Fonte corrigida passou64 casos/20 mutações reais por asserção e sete invocações públicas novas sem marcador nos negativos. Parser PowerShell/compilação C# nativos passaram; quatro fontes conferidas conjuntamente por SHA256. [Evidência sanitizada](evidence/windows-dns53-client.json).

CI exato b4fe9e4 concluído: [PR36949215659](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949215659) e [push36949211094](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949211094), seis jobs aprovados (Windows/Ubuntu/macOS). Log Windows confirmou baseline64 e o passo de mutações terminou verde. CI valida fonte/fixtures; não executa o telefone nem DNS53 nativo no Mac. Nenhuma suíte local foi repetida para esta fase documental.

Quatro arquivos próprios de testes/logs e diretório tests do Windows removidos; dois arquivos cliente verificados preservados para o próximo piloto. Filhos próprios concluíram e nenhuma fixture permanece ativa. Sudo não interativo Mac exigiu autenticação; nenhum bootstrap privilegiado Mac ou DNS53 funcional executados. Android fica pendente; Mac/Windows são os clientes da rodada atual. Não houve instalação, agente, chave, DNS/firewall/política global ou mudança do telefone. #19 conserva os gates nativos/NRPT/IP estável/rollback; #2/#8 e revisão integral #16 continuam separados.


## DNS53 — correção Darwin #30 e limite nativo

Primeiro piloto com wrapper0, restore exato de três arquivos DNS, SSH estrito/HTTP/kernel7.2.0-iphone6s-source e DNS5353 UDP/TCP passou. Bootstrap Mac53 recusou antes de handoff: leitura Python17 grupos da conta, versus kernel com um único grupo primário e zero não primários; UID/GID reais/efetivos do usuário conferidos em filho isolado. Nenhum DNS53 Mac/Windows foi executado; sockets53/túnel1054 ausentes após erro. Não é prova de serviço funcional.

Correção f969696 usa getgroups da libc/ctypes stdlib no Darwin, limita contagem/errno e exclui somente o GID primário já conferido; Linux conserva os.getgroups/lista vazia. Regra de UID/GID/sudo original/nonce/peer/FDs e frame suplementar0 mantida. Regressão antiga falhou por asserção. Mac27 casos/21 mutações; VM31 casos/25 mutações em namespace próprio, fonte/hash conferidos. AST/Flake8 fatal do Python3.12.6 já instalado, JSON/links/diff/guard passaram. [Plano e procedimento](DNS-STANDARD.md), [evidência sanitizada](evidence/dns-standard-port.json), [issue30](https://github.com/djalmajr/iphone6s-linux/issues/30).

CI exato f969696 terminal aprovado: [PR36953017204](https://github.com/djalmajr/iphone6s-linux/actions/runs/36953017204) e [push36953013523](https://github.com/djalmajr/iphone6s-linux/actions/runs/36953013523), seis jobs Windows/Ubuntu/macOS. A fonte/fixtures foram testadas; helper Darwin corrigido e consultas DNS53 reais do telefone continuam pendentes. Prova standalone privada preparada com pins/TTY/sockets/dados/cleanup, mas cache local expirou. Não iniciar silenciosamente sem autenticação.

Cleanup do episódio: daemon DNS próprio parou, bootstrap/túnel/sockets Mac ausentes e VM devolvida ao estado parado. Snapshot/sync passaram; CLI de retorno saiu1, Linux deixou o USB, porém iOS não reapareceu até a última observação. Fallback físico Power+Home até maçã foi solicitado e ainda aguarda confirmação. Tentativa herdr.py stop era inválida e não foi contada como parada; reboot encerrou o runtime, sem comprovar iOS. Logs/IDs/endpoints privados em runtime/dns53-physical-20261001. Dois arquivos cliente verificados permanecem intencionalmente na pasta exclusiva Windows para próximo piloto; sem teste/servidor próprio ativo lá.

Nenhum pacote no Mac, agente novo, configuração de DNS/NRPT/PF/sudoers/firewall/roteador/conta ou merge/tag/release. #30/#19 continuam abertas para prova nativa/piloto/clientes/política; Android pendente, rodada atual Mac/Windows. #2/#8/proveniência e revisão integral #16 continuam separados; complete_pr_review=false e inventário integral49d8747 preservados. Esta fase documental não repete gates de código inalterado nem declara serviço ativo/contínuo.

## Historical snapshot: first Linux and USB HTTP session — 2026-09-29

The following observations describe the first probe session, before the later console, SSH and full-wrapper validations above. Its active-session statements are historical.

- On 2026-09-29 the user replaced the cable with a genuine **USB-A-to-Lightning** cable connected to a rear Mac port. The first guided attempt with that cable succeeded: palera1n reported `Device entered DFU mode successfully`, `Checkmate!`, and `Booting PongoOS...`. `ioreg` confirmed `PongoOS USB Device`.
- `pongoterm` uploaded the verified 11,700,549-byte combined payload and ran `bootm`. The Mac subsequently detected `iPhone 6s Linux probe` and its NCM network interface `en12`.
- A temporary `172.16.42.2/24` alias was added only to `en12`, using the macOS administrator dialog. The phone is `172.16.42.1`; `route -n get 172.16.42.1` confirmed `en12`.
- A real shell returned `Linux (none) 7.0.12 #1-postmarketOS SMP PREEMPT Fri Jun 12 10:53:24 UTC 2026 aarch64 GNU/Linux`, model `Apple iPhone 6s (Samsung)`, two processors, and 1,973 MiB RAM. The interactive shell was also tested with `uname -a` and `exit`. Evidence: `evidence/linux-boot-proof.txt`.
- BusyBox HTTP serves a live status page at **http://172.16.42.1:8080/cgi-bin/status**, bound to the USB address only. The real HTTP response was saved to `evidence/linux-http-proof.html`. Repeated `serve` completed successfully without launching another HTTP server.
- `/sys/block` exposed only loop devices and zram; no internal-storage block device appeared. `/sys/class/power_supply` was empty. Persistent internal storage and battery/charging monitoring are therefore **not established** in this session.
- The screen is black, as reported by the user; the shell and HTTP service work independently of it. This is an experimental **RAM session**, requiring Mac-assisted boot and physical DFU buttons after a restart. It is not an autonomous or unattended server installation.
- `iphone-linux.sh` provides `status`, `shell`, `serve`, `connect`, `disconnect`, and a prepared `boot` wrapper. `status`, interactive `shell`, and repeated `serve` were verified against the phone. The assembled `boot` wrapper has not been rerun from a fresh restart; its individual DFU/Pongo/upload stages were used successfully in this session.
- The visual guide and pongoterm processes were stopped after use. The phone's Linux/HTTP session and the dedicated Mac USB IP alias remain intentionally active. No Mac package was installed and no remote account/service was changed.

## Earlier diagnostics and preparation

## Device and findings

- iPhone 6s (`iPhone8,1`, `N71AP`, Samsung A9 S8000), 32 GB. The official Finder recovery-mode **Update** completed on 2026-09-27; `ideviceinfo -k ProductVersion` confirmed **iOS 15.8.8** after reboot. It was previously on iOS 15.7.5.
- Mac USB pairing validates. After the update, the phone requested a PIN to continue installation; the user entered it, and iOS finished setup before the Linux boot test.
- Battery reported 1,462 cycles in an earlier diagnostic; its runtime is poor.
- The touch panel generates phantom touches even with Lightning disconnected. A video shows calculator keys activating without contact and a row of display artifacts near the bottom of the 0 key. This points to the screen assembly or its connection, but does not isolate the exact component.
- Home responds to a long press by opening Siri. Siri did not execute a spoken command, and Wi-Fi connectivity is uncertain.
- Recovery mode worked. Multiple DFU attempts with a direct USB-C-to-Lightning cable ended in an Apple logo followed by Recovery, and palera1n reported `Whoops, device did not enter DFU mode`.
- The USB-C-to-Lightning cable was moved from the Mac Studio M2 Max front USB-C port to a rear USB-C port. `ioreg -p IOUSB -w0` then showed the iPhone directly under `AppleT8112USBXHCI@03000000`, instead of behind the front path's ASMedia USB2 hub. `ideviceinfo -k ProductVersion` still returned 15.8.8.
- A synchronized visual DFU attempt on the rear USB-C port ran through palera1n's 4-second Power+Home and 10-second Home stages. The tool reported `Whoops, device did not enter DFU mode`; `ioreg` showed `Apple Mobile Device (Recovery Mode)`, not DFU. The guide process was stopped, the browser page closed, and `palera1n -n` exited recovery. `ioreg` then showed a normal `iPhone`, and `ideviceinfo -k ProductVersion` returned 15.8.8. No Linux payload was uploaded.
- The user confirmed that phantom touches still occur after the official iOS 15.8.8 update. Whether display artifacts also recur after the update is awaiting observation. The artifacts were absent on black screens and during the Apple logo before the update; this does not alone identify a software or hardware cause.

## Preserved local inputs (current paths)

- `bin/palera1n-macos-arm64`: official v2.4 binary; SHA-256 `950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9` matched the official GitHub release digest. CleanMyMac classified it as jailbreak riskware. It was executed locally on the Mac; its present path is under `bin/`.
- `artifacts/Pongo.bin`, `bin/pongoterm`, `artifacts/m1n1.bin`, `artifacts/vmlinuz-apple-16k`, `artifacts/s8000-n71.dtb`, and `artifacts/iphone6s-initramfs.gz` are staged for an experimental RAM boot.
- `artifacts/m1n1-linux-iphone6s.bin` is the combined boot payload (SHA-256 `7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520`). It **booted successfully on 2026-09-29**.
- The local DFU countdown prototype was removed at the operator's request on 2026-09-30. `scripts/boot/dfu_boot.py` monitors manual DFU without opening a browser or HTTP listener; local simulated tests and a physical full-wrapper boot passed before the folder reorganization.
- The isolated Multipass VM `iphone6s-build` was used to build arm64 components and is stopped. Existing VMs were not modified.

## Practical limits and next test

HoolockLinux supports experimental A9 boots, but documents internal storage support only for A11. For this A9 phone, a Linux boot would be tethered and RAM based; autonomous boot after a restart is not established. The original probe initramfs exposes a temporary unauthenticated Telnet shell on the dedicated USB link for boot proof. The default integrated image starts key-only SSH directly. Sustained power and production operation remain unverified.

Ghost touches did return after the official update. The user chose Linux rather than any iOS-based server and asked to stop repeating the failed DFU timing approach. A full Restore has not been done. Both documented HoolockLinux methods, PongoOS and iBoot, require hardware DFU. The materially different USB-A-to-Lightning cable test **succeeded on 2026-09-29**; palera1n documents that USB-C-to-Lightning may prevent DFU. Do not use fakefs or the A11 partitioning tools on this A9. The worn battery and absence of battery-monitoring data remain limits for unattended use.

An iOS-based route using Dopamine/TrollStore avoids DFU, but installation and initial launch require working on-device interaction. TrollRestore's backup method also requires Find My disabled, which would change remote account state if currently enabled; that was not attempted. No remote accounts or services were modified.

Sources: [HoolockLinux setup](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP_pongoOS.md), [HoolockLinux storage status](https://github.com/HoolockLinux/docs/blob/master/tools/README.md), [palera1n guide](https://ios.cfw.guide/installing-palera1n/), [Dopamine](https://github.com/opa334/Dopamine), [TrollRestore](https://github.com/JJTech0130/TrollRestore).

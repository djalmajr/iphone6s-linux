# iPhone 6s Linux — atualizado em 2026-10-05

## Checkpoint atual — alimentação priorizada

Coletor PME `4cea1ce` pronto para perfil separado:39 testes/53 mutações Mac/ARM64,26 inputs e dez comandos bash-n; check real de payload/initramfs/identidades/SHA/ELF/vermagic sem SSH/USB. Seleção explícita `--host-scan --scan-link-target --scan-pme-noop`, provenance booleano exato e contratos no-write/evento/root/releitura obrigatórios. Seis arquivos anteriores preservados, somente PCIe/provenance novos, default intacto. [Receita e continuação sem outro boot](N71_LINK_EXPERIMENT.md#coletor-pme--perfil-separado-e-continuação-no-mesmo-boot), [prova selecionada](evidence/n71-pme-scan-session.json). Candidata ainda não carregada; CI do head publicado e gates USB/carga frescos precedem próximo boot agrupado.

PME inativo qualificado offline (`5bc966e`): pedido root044/word8008 sobre PMCSR8 recebe no-op sem W1C/escrita no hardware, com identidade/capability/COMMAND/releitura verificadas. Evento ativo/enable/D-state e controles do endpoint continuam recusados. Seis suítes/8 testes compiladores,36 mutações config e scan21/13 passaram Mac/ARM64; seis módulos Werror/modpost/ELF/vermagic, kernel/fonte preservados. PCIe70424 bytes; REG_ON intacto, nenhum Image/perfil/default substituído ou novo DFU. [Reprodução e limites](N71_LINK_EXPERIMENT.md#pme-já-inativo--candidata-sem-escrita-w1c), [prova selecionada](evidence/n71-pcie-pme-noop-build.json). Candidata ainda não carregada; próxima fatia integra sua seleção/provenance no coletor antes de outra sessão agrupada.

CI7adc PR falhou em dois testes antigos de retorno/backup; push cancelado, Mac/Windows aprovados. Diagnóstico `402943a` passou20/20 Mac/ARM64 e expõe fase/erro da fixture sem ampliar timeouts. [Issue38](https://github.com/djalmajr/iphone6s-linux/issues/38) continua aberta; essa CI não cobre a correção PME nova. Telefone mantido no iOS para recarga, Wi-Fi e telemetria/carga Linux ainda pendentes.

Sessão física da candidata: um DFU/um scan/zero reinícios intermediários. TLS1→2→1 passou com readback/link qualificados; scan continuou negativo pela primeira recusa root044/word8008, correspondente à limpeza PME W1C. Driver removeu bus/config/TLS/reset/power e ficou ready0 após probe negativo. O coletor conservou REG_ON por não reconhecer esse caso; correção `d1cee21` passou37 testes/47 mutações Mac/ARM64 e concluiu unload/restore normal no mesmo boot, sem outro scan. SSH/HTTP/Herdr finais, snapshot44/sync e retorno ao iOS por software passaram. iOS100→90 inclui transições, carregando após retorno; gadget500mA e zero power_supply não comprovam carga. [Resultado e próximos gates](N71_LINK_EXPERIMENT.md#sessão-física-do-target--um-boot-correção-do-coletor-sem-reiniciar), [prova selecionada](evidence/n71-scan-target-physical.json). Próximo desenvolvimento offline: qualificar PMECSR/lifecycle; Wi-Fi, IRQ/DMA/firmware e energia/telemetria continuam abertos.

CI d045d24 terminou success em PR37330736713/push37330728149, seis jobs; push passou no segundo attempt após retry do único job Ubuntu que falhou em testes antigos de return_ios. Rechecks sem mudanças passaram; a intermitência será investigada separadamente. Essa CI não cobre d1cee21; os gates Mac/ARM64 e físicos dessa correção estão registrados acima.

### Preparação e checkpoints anteriores

Coletor `e1a4835` e perfil separado estão qualificados:36 testes/45 mutações por AssertionError passaram Mac/Ubuntu ARM64,25 inputs conferidos e10 comandos bash-n. O perfil real passou payload/initramfs/identidades/módulos sem USB/SSH. Seleção explícita `--host-scan --scan-link-target`; uma tentativa de cleanup no mesmo boot, REG_ON/staging conservados quando a restauração PCIe não é comprovada. Gates C/build anteriores reutilizados com inputs iguais. Ainda não carregado no iPhone; próximo gate é uma sessão física agrupada, sem reinícios intermediários para os passos que puderem ocorrer por SSH. [Receita e limites](N71_LINK_EXPERIMENT.md#coletor-com-retenção-reg_on--candidata-pronta-para-sessão-agrupada), [prova selecionada](evidence/n71-scan-target-session.json). Wi-Fi, telemetria e carga continuam abertos; nenhum Image, firmware, pacote/configuração global ou default alterado.

Scan `e03bdc9` e caller `cae5955` integram TLS1→2→1 com ownership persistente: bridge/config/target e energia/reset/módulo ficam retidos se o rollback falhar; ação `cleanup` tenta restaurar sem outro scan. Readback real do GPIO, bind/unbind suprimidos e put de uso não duplicado. Scan21 cenários/13 mutações e caller67/18 passaram Mac/Ubuntu ARM64; seis módulos operacionais Werror/modpost/ELF/vermagic, Image/config/exports intactos. Naquele checkpoint, o coletor ainda precisava conservar REG_ON/staging sob retenção; essa preparação avançou acima. Módulo ainda não carregado no iPhone. [Reprodução e limites](N71_LINK_EXPERIMENT.md#scan-e-caller-integrados--cleanup-sem-novo-boot), [prova selecionada](evidence/n71-pcie-scan-target-build.json). Sem novo DFU, firmware ou pacote/configuração global no Mac; Wi-Fi e carga continuam pendentes.

CI `096d69a` concluiu success em PR37326642354/push37326631225, seis jobs, cobrindo a integração e documentação anteriores. A preparação do coletor acima tem prova local/ARM64 própria; sua CI será vinculada ao novo head publicado. Os registros seguintes conservam a cronologia.

Primeira sessão física power2 no head `70d4736`: boot/restore/SSH/HTTP/Herdr passaram, assim como proteção de binding PMGR, dois ciclos genpd e inspeção I2C1 estável/idle (`REV=2`, `SMSTA=08010100`, `XFSTA=0`). No mesmo boot, sem reinicializações intermediárias, PCIe identificou `14e4:43a3`, BCM4350rev8, BAR0 de32KiB/BAR2 de4MiB e ciclo DART com16 words restaurados. Scan PCI permaneceu negativo: primeira recusa root0:08/0a0/word/value2; demais recusas são latched. Cleanup, snapshot/sync e retorno por software ao iOS passaram; iOS91→81% incluindo transições, carga ativa no retorno. Não comprova corrente, saúde/carga Linux ou Wi-Fi. [Prova selecionada](evidence/n71-power2-first-physical.json), [energia e próximos gates](N71_HDQ.md#primeira-sessão-física-power2--ciclos-e-inspeção-verificados), [recusa PCIe](N71_LINK_EXPERIMENT.md#primeira-sessão-power2--link-chip-dart-e-scan-agrupados). Desenvolvimento seguinte é offline; não exige outro DFU para registrar a coleta.

CI do head `70d4736` concluiu success em PR37266850654/push37266847052, seis jobs. Logs Mac/Ubuntu confirmam os testes do coletor e26 mutações por asserção. Código, perfis e módulos não mudaram para a coleta física; esses gates foram reutilizados. Os registros abaixo conservam a cronologia da preparação e das sessões anteriores.

Coletor Wi-Fi `dfad0ff`: qualifica os pares legados/power2 e propaga a release para módulo, preflight, resultado e histórico de continuação.31 testes/26 mutações passaram Mac/Ubuntu ARM64; perfil privado power2 com PCIe/REG_ON passou seis checks reais sem SSH/USB e recusou dart-cycle sem histórico. Payload/initramfs/identidades e perfil anterior intactos, nenhum Image/módulo recompilado ou DFU. [Reprodução e continuação](N71_LINK_EXPERIMENT.md#coletor-de-link-na-abi-power2--continuação-no-mesmo-boot), [prova selecionada](evidence/n71-link-binding-session.json). Teste físico aguarda USB; preparação não habilita rádio, telemetria ou carga.

Módulos Wi-Fi `3ce8aaf`: seleção explícita `n71-dart-serdev-power-v2`, com release e hashes power2 conferidos; default e artefatos legados preservados. Oito módulos passaram build nativo ARM64/Werror/modpost e verificação independente SHA/ELF/vermagic/dependências no Mac. Os12 testes e17 mutações por asserção passaram nas duas plataformas. Preparação aproveita o Image existente, sem recompilar ou reiniciar o telefone; nenhum módulo/firmware foi instalado ou carregado. PCIe/DART/IRQ/chip/firmware, Wi-Fi, carga e telemetria continuam pendentes. [Reprodução](N71_LINK_EXPERIMENT.md#módulos-wi-fi-para-power2--preparados-sem-novo-image), [prova selecionada](evidence/n71-wifi-binding-modules.json).

CI `38c5df6` do builder142/documentação143 terminou success em PR37265593416/push37265590595, três jobs cada. Esse head antecede a correção144 do coletor; CI nova deve ser vinculada ao seu próprio commit.

CI anterior `6e37876` terminou success em PR37263273839/push37263270142, seis jobs. Logs reais Ubuntu/macOS do PR confirmam observador I2C37/18 e caller52/14. Esse resultado cobre a preparação I2C139–141; não prova hardware nem o builder Wi-Fi142, cuja evidência local/ARM64 está registrada acima.

Nova preparação `14117a4`: ação explícita `inspect` integrada ao caller power2. Reserva MMIO e lê REV/SMSTA/XFSTA duas vezes, sem reset, FIFO ou comandos ao carregador; sempre tenta encerrar genpd e conserva referências em cleanup pendente. Observador37 cenários/18 mutações e caller52/14 passaram Mac/Ubuntu ARM64; módulo real Werror/modpost/ELF/vermagic conferido. Coletor agrupa dois cycles e uma inspeção no mesmo boot, com guards/fixtures locais. Nenhum desses ciclos ou leituras foi executado no telefone; carga, telemetria e Wi-Fi continuam pendentes. [Reprodução e próximos gates](N71_HDQ.md#inspeção-do-controlador-i2c1--preparada-sem-reset), [prova selecionada](evidence/n71-i2c-controller-inspection.json).

iPhone no iOS para recarga depois de uma sessão curta power1. Um DFU
manual reuniu restore, SSH/HTTP/Herdr e os dois observadores I2C1/GPIO/PMGR;
módulos/staging removidos, snapshot/sync e retorno por software verificados.
Leituras iOS100→99% em160s incluindo DFU/reboot/iOS; carregamento ativo
no retorno às00:56:31UTC de2026-10-05. Isso não prova carga no Linux.
Linux não está online; desenvolvimento segue no Mac/VM para implementar
aquisição/restauração I2C1 e carga/telemetria N71, sem repetir esse DFU.
[Evidência e limites](ALIMENTACAO.md), [issue P0](https://github.com/djalmajr/iphone6s-linux/issues/2).

Image separado `7.2.0-iphone6s-dart-serdev-power1` compilou com as patches
DART/serdev/GPIO/PMGR001→006, em12min41s. Config só difere na identidade;
config embutida, modpost, export serdev, objetos builtin e DTB preservado
conferidos. Fonte/config/Image/exports do rollback intactos; artefatos no Mac
passaram por SHA e pelo integrador real. [Reprodução e limites](N71_KERNEL_BUNDLE.md#image-completo-da-candidata-gpiopmgr--2026-10-04).
Os cinco módulos também passaram rebuild Werror/modpost/ELF/vermagic.
Perfis base e diagnóstico foram compostos/validados separadamente no Mac,
com initramfs/identidades preservados e snapshot local de44 entradas validado.
Boot/restore/SSH/HTTP na ABI nova e observadores passivos passaram;
acesso físico ao carregador continua pendente.
[Prova de composição](evidence/n71-power-profile.json),
[sessão física](evidence/n71-power-session-gate.json).
O Image novo ainda não habilita carga, telemetria ou Wi-Fi.

Lifecycle runtime PM `29e61ec`:12 cenários/13 mutações compiladas por asserção
Mac/ARM64 e objeto kernel/Werror passaram. Contrato retém cleanup pendente,
preserva erro primário e impede novo put após uma falha que já consumiu uso.
O backend genpd e o caller operacional agora estão compilados no checkpoint
acima; ativação/inspeção físicas e acesso a pinos/carregador seguem pendentes.
[Reprodução e limites](N71_HDQ.md#lifecycle-runtime-pm-i2c1--sequência-testada-backend-pendente).
Nenhum novo DFU nessa implementação. O passo novo passou Ubuntu/macOS
em ambos os runs do código29e61ec. O run
push falhou depois por PID vazio numa fixture antiga de cancelamento do
reboot. Publicação atômica corrigida somente no teste, com regressão de
escrita incompleta e mutação por asserção Mac/ARM64; gate afetado passou
20 testes/11 mutações em ambas as plataformas. CI8974389 terminou success
em PR37251729490/push37251726729, seis jobs; issue37 concluída.

Acesso PMGR compartilhado `152e07b`:97 cenários/22 mutações por asserção
Mac/ARM64 e módulo Werror/modpost/ELF/vermagic power1 passaram. Mantém
validação N71/caminhos/metadata/provider sob lock e limpa o handle no unlock.
Não foi carregado no aparelho nem implementa backend genpd ou carga.
[Contrato e reprodução](N71_HDQ.md#acesso-pmgr-compartilhado--qualificado-sem-ativação),
[prova selecionada](evidence/n71-pmgr-access.json).

Backend genpd `1cdfa72`:87 cenários/20 mutações Mac/ARM64, callbacks reais
linkados Werror/modpost e patch007 aplicada/compilada em cópia do provider.
Proteção suppress_bind_attrs obrigatória: power1 atual recusa esse backend;
Image power2 e caller operacional passaram build separado; teste físico ainda pendente. Suspend
com domínio ligado mantém cleanup pendente, sem detach nem outro put.
[Contrato/reprodução](N71_HDQ.md#backend-genpd-i2c1--compilado-proteção-de-binding-pendente-no-image),
[prova selecionada](evidence/n71-i2c-genpd.json). CI da primeira versão
`a476729` terminou verde nos seis jobs; guard e seletor power2 passaram nos seis jobs de `a684a93`.
Nenhum DFU, acesso ao carregador ou configuração global do Mac nesta rodada.

Image separado `7.2.0-iphone6s-dart-serdev-power2` compilou em19min06s com001→007. Patch007 integra a proteção de binding exigida pelo backend. Image/config/gzip/DTB/logs passaram SHA no Mac; config só difere de power1 na identidade e fonte/config/Image/exports anteriores ficaram intactos. Nenhum boot ou perfil default alterado. Integração real, seis módulos e controles operacionais passaram; falta a sessão física agrupada. [Reprodução](N71_KERNEL_BUNDLE.md#image-power2-e-proteção-de-binding--2026-10-05), [prova de link](evidence/kernel-n71-binding-build.json). Ausência física de bind/unbind, carga, telemetria e Wi-Fi continuam sem comprovação.

Perfis power2 base/diagnóstico preparados: initramfs e identidades byte a byte iguais, fonte preservada,700/600 e nenhum autoload. Integrador22 testes/25 mutações; compositor6/8; caller genpd39 cenários/11 mutações, todos Mac/ARM64. Seis módulos W=1/Werror/modpost/ELF/vermagic e hashes conferidos no Mac. Caller permite cycle explícito e cleanup retido, preservando módulo/referências se a restauração falhar. CI5fa e CI6a66ff5 terminaram success nos seis jobs cada, cobrindo integração e caller/compositor. Nenhum novo DFU ou I/O do carregador. [Prova selecionada](evidence/n71-binding-profile.json), [procedimento da próxima sessão](N71_HDQ.md#próxima-sessão-física-uma-entrada-dfu-operação-pelo-mac).

Transporte da próxima sessão preparado: coletor passivo power2 conserva o corpo testado e passou três fixtures; coletor de dois ciclos genpd passou sintaxe, oito contratos de resultado e guards de unload em Bash temporário, incluindo duas mutações por asserção. Nenhum comando no telefone ou prova do transporte ativo completo. Na consulta USB atual o Mac não detectou iPhone/iOS; reconexão foi solicitada antes de iniciar qualquer monitor/DFU. Goal permanece ativo e o aparelho não foi reiniciado nesta preparação. [Detalhes e limites](N71_HDQ.md#transporte-da-sessão-power2--preparado-sem-ação-no-telefone).

No boot anterior, DART provider/INTx/probes de ponte tiveram cleanup verificado
e SSH/HTTP/snapshot preservados. Scan PCI ainda negativo; primeira recusa
seguinte é SERR. A candidata controls/SERR compilada não foi carregada por
causa da bateria; Wi-Fi/DMA/IRQdelivery continuam pendentes. O último snapshot
válido é posterior ao scan de ponte. [Estado e reprodução](N71_LINK_EXPERIMENT.md).

Novo cálculo SN2400 específico N71 passou Mac/ARM64/oito mutações e contexto
kernelWerror. É aritmética sem I/O, não um driver de carga. I2C1/HDQ/revisão,
cleanup e corrente líquida continuam na #2; teste prolongado #8 não começou.
CI da correção das fixtures PCI aprovado no SHA85aa0f5 (PR37226272040 e
push37226267211). Gates dos novos arquivos são registrados por SHA nas issues.

Observador I2C1/GPIO114/115 preparado no código `98bc26b`: 86 casos e 15 mutações
Mac/ARM64, módulo de 15.768 bytes Werror/modpost contra o bundle preservado, oito leituras
via provider existente e nenhuma ativação ou escrita. O rebuild power1 foi
carregado/descarregado: GPIO114/115 estáveis/cache coerente, controller disabled
sem adapter. [Reprodução e limites](N71_HDQ.md#coleta-agrupada-de-energia-na-abi-power--verificada),
[prova selecionada](evidence/n71-i2c-topology-observer.json). Continua pendente
aquisição/restauração ativa do I2C1, HDQ e corrente líquida; #2 permanece aberta.
CI do head `c683145`, que contém o código `98bc26b`, aprovado nas duas
execuções PR 37230516183/push 37230513184, seis jobs Ubuntu/macOS/Windows.
Referência Apple I2C1 confrontada: SCL 115/SDA 114 coincidem com o grupo Linux;
descriptor de 12 bytes usa modo 2 e role `AP`, não phandle. Init/reset/unjam são
operações ativas; ownership/idle/restauração e carga continuam pendentes.
[Fatos e reprodução](N71_HDQ.md#i2c1-pinos-apple-e-abi-do-descriptor-confrontados).

Correção GPIO `19f6129`: 816 cenários, 11 mutações e regressão compilada da
fonte original aprovados no Mac/ARM64. CI desse head aprovado nos seis jobs
PR 37233188196/push 37233183384. Integração no bundle permanece na
[issue #35](https://github.com/djalmajr/iphone6s-linux/issues/35); erro propagado
não comprova rollback ou carga funcional.

Observador PMGR `80b3fe0` preparado: 88 cenários/16 mutações Mac/ARM64,
build externo Werror, seis leituras de I2C1/sio_p/sio_busif via syscon existente
qualificado pelo binding sob lock. Rebuild power1 passou load/unload no mesmo
boot dos pinos; seis amostras estáveis, sem ativação ou ownership da cadeia.
[Reprodução e limites](N71_HDQ.md#observador-pmgr--i2c1-e-domínios-pais),
[prova e checkpoint iOS](evidence/n71-pmgr-power-observer.json).

Correção dos callbacks PMGR `301a61f`: 492 casos/14 mutações Mac/ARM64,
regressão da fonte original detectada e arquivo completo compilado Werror
como objeto embutido. Modpost externo recusou esse provider embutido;
erros preservados; a sequência004→006 agora passou integração/link/boot na
[issue #36](https://github.com/djalmajr/iphone6s-linux/issues/36).
Essa patch004 isolada não corrige probe/is_active ou rollback de efeitos parciais.
CI desse código aprovado em PR37236898569/push37236896067, seis jobs.
[Reprodução e limites](N71_HDQ.md#erros-dos-callbacks-pmgr--correção-preparada).

Correção inicial do probe PMGR `21a786c`, patch005 após004: 3.138 cenários,
12 mutações Mac/ARM64 e arquivo completo obj-y/Werror. Primeiro erro de I/O
chega ao caller antes de registrar domínio/provider/reset; bool de estado
só muda após leitura válida. Integração/link/boot passou com004→006;
cleanup após registro, efeitos parciais e ownership/idle seguem na issue #36.
CI21a786c aprovado em PR37238520733/push37238517260, seis jobs.

Cleanup PMGR006 `f728099`: 3.258 casos/seis mutações Mac/ARM64 e objeto
completo004+005+006 obj-y/Werror. Falha de add_provider remove domínio sem
apagar provider alheio; primeiro erro preservado. Integração/link/boot passou;
pós-publicação/iterator e efeitos parciais continuam na #36. Não habilita
carga no Linux e não motivou DFU. [Reprodução](N71_HDQ.md#falha-de-publicação-do-provider-pmgr--cleanup-preparado).
[Reprodução e limites](N71_HDQ.md#erros-iniciais-do-probe-pmgr--correção-preparada).

As seções anteriores abaixo são checkpoints históricos; afirmações sobre
serviços ativos ou VM parada descrevem a data indicada em cada uma.

## Direção de desenvolvimento — 2026-10-02

Prioridade do operador: Wi-Fi e recursos que facilitem a iteração, com o mínimo de reinicializações. [Fluxo de sessões e ordem](DESENVOLVIMENTO.md). DNS53 deixa de ser a próxima entrega; seus gates aprovados são preservados e o piloto funcional continua pendente.

Inventário físico por SSH no boot já ativo 7.2.0-iphone6s-source: somente lo/usb0, ieee80211 ausente, PCI/SDIO/MMC sem dispositivos, nenhum módulo e nenhum compatible correspondente entre 118 propriedades examinadas. Sem power_supply ou ADT original no chosen consultado. Nenhum reboot, firmware, driver ou política de rede nesta fase. [Wi-Fi](WIFI.md), [evidência](evidence/wifi-runtime.json). A topologia foi identificada e a preparação compilável avançou depois, no fechamento N71 abaixo; controlador/PHY e associação/DHCP continuam pendentes.

O boot imediatamente anterior desta rodada restaurou os três arquivos DNS com hashes/tamanhos exatos, SSH/kernel/HTTP e Herdr confirmados. Roteiro privado de preflight errou ao chamar dns.start inexistente; não é prova de DNS5353. Controlador DNS53 expirou esperando prontidão e não abriu o endpoint. Nenhuma consulta DNS53 Mac/Windows executada. A nova prioridade não transforma esse piloto em sucesso.

## Entrega Wi-Fi, sessão e energia — 2026-10-02

**Zero reinicializações nesta entrega.** Updater DNS específico implementado e provado no mesmo Linux: SHA256, quatro checkpoints verificados, UDP/TCP, rollback exato e SSH preservado; Herdr ainda respondeu `running` na conferência final, uptime 8441,32 s no mesmo boot. [Procedimento](DESENVOLVIMENTO.md), [evidência](evidence/dev-session.json). Mac 15 testes (cinco skips VM explícitos)/sete mutações; VM 15 testes/12 mutações. Os demais relatos abaixo permanecem históricos e não representam garantia de continuidade após este checkpoint.

Topologia Apple N71 extraída/reproduzida privadamente: BCM4350/PCIe S8000 porta 1, DART S5L8960X, referência `gas-gauge,bq27540` em UART5/HDQ (não identifica revisão física/register map) e SN2400 em I2C1. Não habilita rádio, sensores ou carga. [Wi-Fi](WIFI.md), [mapa sanitizado](evidence/n71-board-map.json). #9/#2 seguem abertas; próximo desenvolvimento é controlador/PHY/DT S8000 e HDQ/mux/regmap específico da placa.

Configfs da imagem atual anunciou 2 mA. Fontes corrigidas e candidata privada separada declaram 500 mA antes do bind; seis mutações de ordem e quatro de repack passaram no Mac/VM, preservando arquivos/metadados/identidades. Candidata não carregada; orçamento não equivale a corrente/carga e host ainda não confirmou o descritor. #33 conserva esse gate para próximo boot agregado. DNS53 fica em espera; nenhum pacote no Mac ou política global alterada.

## Fechamento da preparação N71 — 2026-10-02

**Fonte:** [plano de topologia](../.agents/plans/n71-topologia.md), #9/#2. **Modo:** fechamento desta etapa offline; o projeto e as issues de Wi-Fi/carga permanecem abertos.

### Resultado

Fragmento N71 e builder separados compilam UART5, DART PCIe1 e recursos PCIe S8000, todos desativados. A baseline reproduz exatamente o DTB funcional preservado; a candidata mantém todas as propriedades anteriores e os phandles antigos. O primeiro build detectou e recusou renumeração de CPUs; a fixação e a regressão nativa agora cobrem esse defeito. [Procedimento/reprodução](WIFI.md#topologia-n71-compilada--2026-10-02), [hashes e evidência](evidence/n71-topology.json).

O diff foi conferido contra o plano: fragmento, builder, testes/mutações, documentação e gate CI correspondem ao escopo aprovado. Sem mudança adicional de comportamento. Ajustes de implementação registrados no plano: parser Python limitado em lugar de fdtget, fixação de phandles e domínios AUX/REF próprios do A9. Nenhum driver PCIe/HDQ operacional foi acrescentado; não há candidata aprovada para boot, firmware/calibração ou nova imagem instalada.

### Verificação executada

| Gate | Resultado |
|---|---|
| Testes Mac | 13 passaram; quatro compilações Linux explicitamente ignoradas; sete mutações rejeitadas por asserção |
| VM ARM64 nativa | 17/17 passaram, oito mutações por asserção; GCC13.3.0/DTC1.7.0 existentes; fonte limpa preservada |
| Lint | AST/Flake8 fatal aprovados; nenhuma fonte shell alterada |
| Typecheck | Não configurado para Python; compilação DTS não é typecheck Python |
| Artefatos/privacidade | Hashes Mac/VM iguais; DTBs/logs privados; guard público e diff aprovados |
| Hardware | Nenhum novo boot/probe/ativação; não fornece prova de Wi-Fi, sensores ou carga |
| CI | Gate portátil incorporado; resultados do SHA final publicados na [PR #1](https://github.com/djalmajr/iphone6s-linux/pull/1) e nos checkpoints das issues |

### Pendências, responsáveis e próximo passo

| Pendência | Impacto | Responsável | Próxima prova |
|---|---|---|---|
| #9: sequência PCIe/PHY S8000, porta1 e DMA | Rádio não enumera | Desenvolvimento do projeto | Mapear recursos/sequência verificáveis, implementar controlador separado e revisar offline antes da enumeração |
| #2: UART5/pin routing/mux HDQ/register map | Sem telemetria ou carga sustentada comprovada | Desenvolvimento do projeto; medição física se necessária | Validar ABI/topologia, integrar leitura do gauge sem limites de carga presumidos |
| #33: orçamento USB | Candidata500mA não bootada | Desenvolvimento e operador no futuro teste físico | Conferir configfs/descritor recebido pelo host em sessão agregada necessária |

A VM dedicada de kernel retornou a **Stopped**, com fonte/builds preservados. DTBs finais foram copiados para runtime privado no Mac. Zero reinicializações, instalação de pacotes ou mudança de perfil/política global nesta etapa. Entrega registrada nas issues existentes, sem criar duplicatas ou encerrar critérios físicos pendentes. Próxima fatia: controlador/PHY e HDQ específicos; sem novo DFU apenas para repetir inventário já conhecido.

## Estado atual e gates pendentes

As provas abaixo resumem os pilotos históricos; o estado verificado na sessão de desenvolvimento está no checkpoint acima. O telefone executou Linux 7.0.12 em RAM, console automático, Bash/SSH/HTTP por USB e serviços encaminhados para a LAN. A cadeia compilada (kernel 7.2.0 e Pongo de fonte) iniciou no aparelho, com console/SSH/HTTP, restore e DNS USB UDP/TCP. Driver apple-watchdog vinculado; retorno espontâneo ao iOS confirmado pelo operador e USB. O CLI antigo perdeu a confirmação de sync e retornou falha; correção passou em novo piloto com snapshot/sync/retorno verificados e CI aprovada. Rollback Linux7.0.12 também passou com restore/SSH/HTTP/retorno; limite de proveniência do legado permanece na #12. [Evidência física](SOURCE-CHAIN-PILOT.md).

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

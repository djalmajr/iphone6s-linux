# Goal contínuo — Wi-Fi e energia N71/A9

## Contexto e autorização

Em 2026-10-02 o operador pediu novo goal e execução contínua, sem paradas ao fim de cada incremento. Branch `feat/display-console`, repo público djalmajr/iphone6s-linux, #9/#2/#33/#17. UART5/DART/PCIe já compilam desativados; não há Wi-Fi ou sensores operacionais. Serviços/snapshots por SSH estão comprovados. Desenvolvimento solo, sem AGY; Grok apenas se uma segunda opinião acrescentar informação concreta. Cabo USB-A traseiro preservado; sem contador, perguntas de temperatura ou nova aprovação de decisões rotineiras.

## Objetivo e aceite

1. Enumerar PCIe/radio N71, preservar USB/SSH e obter interface wireless; identificar PCI-ID/revisão antes de firmware/calibração, manter insumos privados; provar scan/associação/DHCP e acesso SSH por Wi-Fi.
2. Validar protocolo/mux/ABI do gauge N71 e obter telemetria utilizável. Medir alimentação sem tratar orçamento USB ou percentual isolado como corrente líquida; documentar limites e resolver #2 quando carga sustentada for realmente comprovada.
3. Integrar mudanças numa candidata separada; preservar rollback e snapshots, reproduzir build, registrar provas/falhas no GitHub.
4. Reunir os gates físicos em sessões necessárias: enumeração/DMA/radio, sensores, descritor USB500mA recebido no host, serviços/recuperação. Não marcar o goal completo por documentação, compilação ou ausência de receita pronta.

## Decisões

### D1 — continuar pela implementação específica, usando referência Apple

- **Decisão:** investigar dados/driver S8000 da distribuição oficial Apple como referência somente leitura, e confrontar os controladores Linux existentes. Downloads privados limitados, sem executar código/firmware ou publicar dumps.
- **Por quê:** A10/H9P e M1 têm topologias/tunables diferentes; match artificial não implementa PHY A9. A leitura pode revelar funções/mapas/sequências para um controlador separado.
- **Alternativas:** ativar recursos com constantes A10 (escritas não validadas); encerrar na topologia desativada (não atende ao objetivo); repetir boots para observar ausência (sem informação nova).
- **Reverter:** baixo, sem alteração de hardware; conservar hashes/insumos privados.
- **Onde:** scripts/research, runtime privado, #9/#2.
- **Status:** em curso.

### D2 — executar fatias sem encerrar o goal

- **Decisão:** cada fatia altera até cinco arquivos públicos, verifica o delta e continua para a primeira tarefa aberta. Código que depende de kernel vai à VM; userspace vai por SSH. Publicação no branch autorizado; sem merge/main/tag/release.
- **Por quê:** continuidade solicitada e redução de intervenções/reboots.
- **Alternativas:** pedir aprovação/DFU por entrega pequena (interrompe desnecessariamente); grande patch sem gate intermediário (mais risco de regressão).
- **Reverter:** baixo, commits pequenos e candidatos separados.
- **Onde:** este plano e #17.
- **Status:** aplicada.

### D3 — preparar target temporário sem liberar retrain

- **Decisão:** qualificar um helper separado TLS1→2→1 para um link Gen1 já ativo, antes do scan, sem escrever LNKCTL/retrain. Integrar somente depois de definir retenção/cleanup do caller e gates de fonte/fixture/build; não carregar o helper isolado no aparelho.
- **Por quê:** a primeira recusa física pertence ao quirk de levantar o limite de velocidade; liberar apenas0a0 aciona outra sequência que ainda não tem rollback qualificado. TLS2 temporário permite preparar um scan que conserva o link negociado e confere o readback real.
- **Alternativas:** permitir TLS+retrain do core exige qualificar todas as mudanças de link/status/cleanup; falsificar a leitura de TLS esconderia o estado real; alterar o kernel para um quirk de plataforma exigiria outro Image/boot.
- **Reverter:** baixo na preparação offline, com helper independente e artefatos anteriores preservados; falha física futura precisará de ownership retido até restauração comprovada.
- **Onde:** incrementos147/148, phone/kernel/n71-pcie-scan-link-target.h, docs/N71_LINK_EXPERIMENT.md, issue#9.
- **Status:** preparada; integração e carga física pendentes.

### D4 — reter o scan quando o rollback falhar

- **Decisão:** manter o bridge, snapshots e MMIO no estado persistente, impedir um novo scan e oferecer cleanup explícito no mesmo boot. O caller mantém energia/reset/módulo até confirmar a restauração; bind/unbind e unload forçado ficam fora do procedimento.
- **Por quê:** devolver erro sem reter esses recursos deixa a obrigação de rollback sem um dono e impede retry seguro por SSH.
- **Alternativas:** liberar incondicionalmente exigiria novo boot mesmo numa falha transitória e abandonaria o rollback; fazer retries ilimitados bloquearia o caller; implementar um driver operacional completo agora ampliaria o escopo para IRQ/DMA ainda não qualificados.
- **Reverter:** baixo na preparação; preservar módulo/perfis anteriores e não mudar Image/default. Uma sessão pendente exige cleanup confirmado antes de unload.
- **Onde:** incrementos149/150, scan e caller PCIe, issue#9.
- **Status:** em implementação; nenhum teste físico desta mudança.

## Arquivos, fases e tarefas sequenciais

Cada item é uma fase com no máximo cinco arquivos públicos; scripts auxiliares de pesquisa/dumps/logs temporários ficam em runtime privado. Antes de editar fonte, leitura integral e revisão das referências; artefatos externos fixados por commit/hash.

- [ ] Identificar no kernel/ADT oficial N71 as funções/recursos e sequências PCIe S8000 e HDQ/gauge; registrar apenas mapa selecionado/proveniência. Conclui com insumos verificáveis para implementação, não por inferência A10.
- [ ] Implementar controlador/DT PCIe/DART porta1 separado e gates de recursos/sequência. Compilar fonte fixada na VM dedicada, preservar baseline e USB; definir escrituras e rollback antes de hardware.
- [ ] Implementar UART5/HDQ/mux/gauge N71, inicialmente leitura validada, sem probe de carregador com parâmetros presumidos. Compilar APIs e fixtures reais de protocolo; distinguir escravo sintético de resposta física.
- [ ] Integrar candidata única e orçamento USB preparado, verificar config/initramfs/DTB/identidades/rollback. Criar checkpoint antes de qualquer boot necessário.
- [ ] Executar sessão física agregada com DFU manual: USB/SSH, enumeração/IDs/DMA/logs e sensores/descritor. Continuar correções por SSH sempre possível; reboot somente quando imagem/kernel/DTB exigirem.
- [ ] Selecionar firmware/calibração privados adequados ao radio identificado; validar interface, scan/associação/DHCP/SSH Wi-Fi e recuperação pelo USB. Credenciais não entram no chat, argv, VM de build ou GitHub.
- [ ] Provar alimentação/telemetria repetível e limites de operação; validar restore/serviços/Herdr na candidata, documentar reprodução e fechar somente os critérios realmente comprovados.

## Verificação

### Incremento 1 — primitivas PCIe confirmadas

- Kernelcache oficial N71 obtido por Range (aproximadamente 20 MB), CRC ZIP e Adler32 LZSS conferidos; metadados/prelink/disassembly privados examinados como dados, sem execução de firmware ou reboot.
- Match `AppleS8000PCIe` → `apcie,s8000` confirmado. Mapeados ECAM/Port1/NVMMU/common/PHY e seis seletores/controles RMW específicos de S8000; `n71-pcie-contract.h` calcula recursos, offsets e valores sem acessar MMIO. Testes compilam C nativo e verificam mapa de referência, preservação de bits e recusa sem alteração de saída.
- Gates desta fatia: teste C nativo no Mac e ARM64 na VM passaram; objeto compilou com `__KERNEL__` e `-Werror` na fonte fixada, sem carregar módulo. Seis mutações locais morreram por asserção; nenhuma contou erro de compilação como kill. Fonte da VM preservada limpa.
- A primeira tarefa permanece aberta: ainda falta confirmar tunables do runtime e o ABI HDQ. O ADT do IPSW não contém `apcie-phy-tunables`, exigido pela configuração Apple; origem/injeção ainda não provada. Não substituir por tabelas A10.
- Arquivos desta fatia: plano, header, teste C, runner Python, JSON selecionado. Sem integração no kernel ou prova física; continuar implementação/pesquisa após os gates.

### Incremento 2 — gate contínuo das primitivas

- Commit `caca7d7` publicado no branch autorizado. Runner de mutações exige compilação bem-sucedida e término SIGABRT por asserção; inclui índices, offset A10 incorreto, stride, preservação, polaridade e limites. Core dumps desativados somente no processo do teste.
- CI Ubuntu/macOS recebe o runner; documentação Wi-Fi delimita prova de software e lacuna de tunables. Quatro arquivos nesta fatia: runner, workflow, WIFI e plano. O goal continua, sem solicitar reboot nesta publicação.

### Incremento 3 — reprodução dos insumos de driver

- Leitor público fixa membro/CRC/SHA/tamanhos da distribuição Apple; decoder DER/LZSS próprio com limites, fixtures sintéticas e dados sempre privados. Reutilização `--input` evita download repetido e não declara CRC novo.
- Cinco fixtures do decoder passaram; redecodificação do membro privado real pelo leitor público conferiu os hashes fixados, 42827776 bytes e Adler32, sem rede. Novos artefatos e relatório têm modo600 em pasta700.
- Cinco arquivos nesta fatia: leitor, módulo de formato, testes, N71_REFERENCIA e plano. Busca no XML prelinkado não encontrou propriedades tunables; presença/injeção no runtime continua aberta. Prosseguir pela origem dos parâmetros e HDQ sem encerrar na documentação.

### Incremento 4 — coleta sem novo boot de ferramenta

- Preparado leitor de `dt` do Pongo já existente: cliente fixado, um dispositivo exigido, somente comando `dt`, limites e marcador completo, saída privada. Não recompilar Pongo nem enviar operações MMIO para colher ADT.
- A intervenção futura agrupa ADT do bootloader e boot da candidata USB500mA já preparada; não adicionar outro reboot só para coleta. Quatro arquivos: coletor, testes, N71_REFERENCIA e plano. Prova física continua pendente.

### Incremento 5 — codec HDQ específico N71

- Referência Apple confirma TX C0/FE LSB-first e RX um somente acima de F8; difere do limiar F0 do fork A10. Cabeçalhos oficiais IOSerialFamily fixados confirmam unidades em meio-bit: configuração serial corresponde a 57.600, 8 bits, sem paridade e dois stop bits.
- Codec próprio sem I/O; echo estrito opcional, junção high/low/high somente estável. FFFF não comprova presença; leitura de registros e ABI ainda não integrados. Pin2/config102 e função HDQm no provider tigris são referências ADT, sem escrita de mux.
- Cinco arquivos: header, teste C, runner Python, ALIMENTACAO e plano. C nativo no Mac e ARM64 na VM passou; objeto `__KERNEL__`/Werror também passou, sem carregar módulo ou alterar fonte funcional. Gate de mutações será registrado na próxima fatia. O goal continua pela propriedade da linha e tunables; não declarar telemetria por codec.

### Incremento 6 — coleta física agregada concluída

- Um DFU: `dt` Pongo completo confirmou PHY/common/config/root-port tunables no runtime; dados brutos privados. Mesmo DFU carregou candidata USB500mA; diagnóstico efetivo500/80 e host UsbPowerSinkAllocation500. SSH/HTTP passaram, sem novo driver/firmware, sensores ou Wi-Fi.
- Snapshot/sync e retorno por software ao iOS passaram. Comparação100→92 inclui DFU/reboot/iOS e não mede corrente líquida; #2/#8 permanecem abertas. Brilho temporário256. Próximo DFU somente quando candidata nova agregar prova útil.
- Cinco arquivos documentais: evidência selecionada, WIFI, ALIMENTACAO, N71_REFERENCIA e plano. Continuar parser privado dos parâmetros, sequência S8000 e mux HDQ na VM, sem encerrar o goal.

### Incremento 7 — gate de regressão HDQ

- Runner exige build C bem-sucedido e SIGABRT/asserção: limiar A10, bit order, símbolo TX, frame excessivo, palavra instável e byte order. Sem core dumps. CI Ubuntu/macOS recebe o gate; evidência selecionada fixa codec/configuração serial e distingue echo estrito e presença física.
- Quatro arquivos: runner, workflow, JSON e plano. Continuar integração e parser dos tunables sem novo DFU; headers/testes não habilitam sensor.

### Incremento 8 — parâmetros runtime privados delimitados

- Parser por hierarquia exige host S8000 e porta1, quatro tabelas, framing24 LE, largura4/alinhamento/aperture/32 bits; preserva ordem e offsets repetidos, mascara valor como rotina Apple. Resultado privado; nenhum MMIO ou firmware executado.
- Extração física preservada passou: common34/PHY41/porta1seis/config1dois registros. Testes sintéticos verificam recusas e isolamento; significado dos registros/sequência ainda requer integração específica. Cinco arquivos: parser, testes, N71_REFERENCIA, evidência e plano.
- Próxima fatia integra consumidores/sequência na VM com baseline preservada; não solicitar boot somente para parser e não encerrar goal por contagens.

### Incremento 9 — sequência global S8000 implementada

- Consumidor C dos tunables privados e sequência common4→pollcommon2c bit0→common38→PHY/common. Valida ambas tabelas antes de qualquer I/O, preserva bits/ordem e ignora valores já iguais. Polls limitados100ms, propagação de erros e recusa de statusFFFFFFFF; não reproduzir loops infinitos Apple.
- I/O por backend do caller, permitindo gate nativo com registradores sintéticos; adapter kernel/recursos/energia/reset da porta ainda pendentes antes de hardware. Quatro arquivos: implementação, teste C, runner e plano. Continuar pela porta1/adapter na VM; sequência não equivale a PCI/Wi-Fi comprovado.
- Gates desta fatia passaram: C nativo no Mac e ARM64 na VM, objeto `__KERNEL__`/Werror na fonte fixada. Injeção de erro em cada operação interrompe a sequência; timeout e status inválido não aplicam tabelas. Fonte funcional da VM continua limpa, sem carga de módulo.

### Incremento 10 — preparação da porta WLAN1

- Referência confirma prefixo da porta: controles common1a4/194/180, polls common2c bit4 e common1ac bit0, common4060=3, read/writeback port210 e common194 bit8 invertido. Duas esperas distintas100us; propriedades opcionais ausentes no runtime N71 são recusadas nesta implementação.
- Header executa somente por backend do caller, mantendo PERST/energia/cleanup sob responsabilidade do adapter. Não aplicar tabelas da porta/config, iniciar LTSSM ou habilitar DMA por este prefixo. Referência também distingue port80,84,88; ainda não inferir todos os estados do link por offset de A10.
- Gates passaram no Mac, ARM64 e objeto `__KERNEL__`/Werror; teste verifica ordem/valores, bits preservados, cada falha de I/O, dois timeouts e ausência de writeback quando zero. Fonte funcional da VM limpa. Cinco arquivos: header, teste C, runner, evidência selecionada e plano.
- CI exato9405d20 passou nos dois runs37036594878/37036588887. Continuar adapter/consumo privado; sem novo DFU nesta fatia.

### Incremento 11 — adapter modular e configuração privada

- Gerador DTB fixa hashes da baseline/topologia/coleta física, transforma somente o nó PCIe em binding diagnóstico próprio e injeta quatro tabelas BE privadas. Reserva de memória/CPU de boot e demais dispositivos preservados por round-trip. GPIO161 ativo-baixo pertence ao provider20f100000, conferido entre ADT e Linux. UART/DART continuam desabilitados.
- Módulo exige `run=1` e placa N71; valida os onze recursos, todas as tabelas e PERST antes das operações. Liga os quatro domínios por APIs do kernel, executa global/prefixo, recusa leiturasFFFFFFFF/zero e balanceia energia, mantendo endpoint em reset. Não registra host PCI, carrega rádio ou habilita DMA. Próxima fatia completa configuração/link e gates antes de um teste físico útil.
- Cinco testes sintéticos do gerador passaram; preparação privada real passou, arquivos600/pasta700. Objeto ARM64/Werror compilou. Link modular precisou `modules_prepare` porque `scripts/module.lds` não existia no build Image-only; símbolos usados são os `vmlinux.symvers` do mesmo build, sem suprimir undefined symbols. `LOCALVERSION=` explícito evita sufixo+ incompatível com a imagem preservada. Imagem manteve SHA065d539414dfcbcfba0caccf747c37d798d3989de2b1beceb056125bdcb06044; fonte limpa.
- Cinco arquivos: adapter, Makefile, gerador, testes e plano. Ainda sem carga física; módulos poderão ser atualizados por SSH no mesmo boot quando a candidata passar nos gates, reduzindo reinícios. Prosseguir pelo link/ECAM e controle de DMA antes do boot.

### Incremento 12 — sequência de link/identificação sem DMA

- Referência confirma slot6f8→port80 bit0 (LTSSM), slot5d8→port88 bit0 (predicado do link), slot610→port140 bit31 e configuração MSI8/base8 nos registradores124/128. Header experimental segue essas primitivas e mantém IRQs mascaradas; não copiar status208 de A10.
- PCI capability walk convencional limitado/sem ciclos; Gen1, barramento secundário1 e espera conservadora100ms após PERST são escolhas do experimento. Tabelas não podem escrever COMMAND/status, bus windows, IRQ mask ou LTSSM; tabela que contradiz Gen1 é recusada antes de soltar reset. Espera de link limitada1s; identidade só entregue com vendor válido e bus-master desabilitado. Falha após tentativa de liberação reasserta reset.
- C nativo Mac/ARM64 e objeto kernel/Werror passaram. Testes usam identidade sintética, verificam cada erro de I/O, ordem/valores, timeout10000 leituras, ciclos, tabela perigosa e endpoint inválido/DMA inesperado. Fonte funcional limpa; nenhuma enumeração física declarada. Cinco arquivos: header, teste C, runner, evidência e plano.
- Próxima fatia liga este consumidor ao módulo e compõe payload privado preservando kernel/initramfs; só então agrupar diagnóstico/link numa sessão física.

### Incremento 13 — candidata modular pronta para sessão agregada

- Backend kernel separado do protocolo, validando apertures e traduzindo reset lógico ativo-baixo. `run=1` executa clocks; `enumerate=1` acrescenta identificação. Cleanup reasserta PERST e balanceia todos os domínios, inclusive em falha. Esperas têm número de iterações limitado e orçamento nominal de delays; não constituem deadline de MMIO/scheduling.
- Módulo completo linkou com símbolos do mesmo vmlinux/ABI7.2.0-iphone6s-source, sem suprimir erros de símbolos. SHA8d62aebade3e122d350a6510b88270be0e0291cb40a3b5e74b7244f16c2883ec; imagem original manteve hash e fonte limpa. Gerador compõe DT privado com loader/kernel/initramfs/identidades intactos, módulo separado e nenhuma carga automática.
- Quatro testes sintéticos passaram: delta exato, proteção USB/UART/reset, tabelas inválidas e ELF/ABI incorretos. Composição privada real verificou imagem/identidades/perfil. Cinco arquivos: adapter, backend, compositor, testes e plano. Perfil em runtime/n71-pcie-profile-20261002; não mudar perfil default.
- Mac não enumerou o iPhone na última leitura; solicitado somente reconectar Lightning e informar tela, sem repetir perguntas de calor ou prontidão. Enquanto isso, registrar reprodução, gate de regressão e pendências. Próxima sessão reúne clocks e link, permitindo troca de módulo por SSH no mesmo boot.

Gates relevantes: lint/AST e compilação C/DTS, tests observáveis e mutações por asserção, fontes/hashes/guard público, native VM, CI exato e prova física separada. Não repetir suítes aprovadas sem mudança relevante. Não há typechecker Python configurado. Falha de build/probe não conta como teste negativo aprovado. Compilação não comprova segurança elétrica ou rádio.

### Incremento 14 — sessão física modular e gate de mutações

- Um DFU: SSH/HTTP, restore44 entradas DNS/Herdr e Herdr iniciado. Clocks/prefixo passaram com driver bound e root106b:1004; port88=0c. Enumeração falhou ETIMEDOUT sem endpoint lido.
- Diagnóstico de status compilado com Werror/ABI preservado e substituído por SSH no mesmo boot. Último port88=0c após10000 leituras; sem novo DFU, DMA ou rádio. Módulo final descarregado, SSH preservado; snapshot/sync/retorno iOS por software verificados. Bateria100→92 inclui DFU/Linux/reboot/iOS, não mede corrente de carga.
- Runner de seis mutações do link passou no Mac com compilação bem-sucedida e SIGABRT/asserção; incorporado ao CI. Runbook modular publicado em fatia anterior de três arquivos. Instrumentação/evidência nesta fatia: adapter, backend, JSON sanitizado, runbook e plano (cinco). Provas dos protocolos inalterados reutilizadas; sem repetir gate amplo.
- Continuar pela ativação do endpoint/CLKREQ na referência N71 antes de novas escrituras; não repetir sequência idêntica esperando resultado diferente. Wi-Fi e gauge/carga ainda pendentes; goal ativo.

### Incremento 15 — alimentação do endpoint WLAN identificada

- Captura N71 contém function-reg_on no providerPMU4d/GPIO10, separado do device_wake73 do SoC. Provider é pmu,d2255 em i2c0/endereço74. Referência AppleD2255PMU confirma mapper8c0+6*pin abaixo17, portanto registro8fc; AppleDialogPMU usa endereçoBE de dois bytes sem paginação.
- Header puro delimita packet/address e planejamento de bit0, recusando outro registro, valor fora de byte e modos herdados não reconhecidos. Não força modo/direção/drive, não acessa I2C ou implementa carregador. A relação entre flags/polaridade e ativação física continua gate separado.
- Cinco arquivos: header, testeC, runner, referência selecionada e plano. Próxima fatia prepara observação PMIC somente leitura e build modular, para combinar com diagnóstico PCIe numa sessão futura útil. Não solicitar DFU só para investigar semântica; goal ativo.
- Gates passaram: C nativo Mac e ARM64, objeto __KERNEL__/Werror; seis mutações morreram por SIGABRT/asserção. Primeira tentativa de mutação excedeu timeout5s no Mac e não contou como kill; repetição com prazo20s passou. Harness privado kernel precisou de protótipo explícito; o gate foi repetido sem suprimir missing-prototypes. Código de hardware continua sem nova carga física.

### Incremento 16 — observação PMIC modular preparada

- Módulo separado exige run1/apple,n71 e valida caminho PMIC, bus20a110000/endereço74, cliente Linux existente, adapter correto e suporte I2C; recusa driver PMIC já bound. Usa API do kernel, duas mensagens para selecionar8fc e ler um byte, sem value write, modo/direção/charger alterados ou probe de endereços.
- Lookup moderno conferido na fonte7.2: of_find_i2c_device_by_node é wrapper inline de i2c_find_device_by_fwnode; referência liberada com put_device. Mensagem curta não comprova leitura. Gate de seis mutações REG_ON incorporado ao CI com prazo20s para mortes por asserção no Mac, sem contar timeout/erro de build.
- Cinco arquivos: módulo, Makefile, runner, workflow e plano. Próximo gate é build modular completo na VM, sem nova imagem/DT/DFU; planejar sessão agrupada quando a observação adicionar informação útil sobre ativação do endpoint. Não declarar PMIC ou Wi-Fi comprovado por build.
- Build ARM64/Werror/modpost passou com símbolos do mesmo vmlinux, fonte funcional limpa e vermagic preservado. Artefato privado SHAe31aa9671b32e54ddf4214cd7be1aef4b988c82feb5e2b233de9fdaea5ef5832. Runner público passou baseline e seis mortes por SIGABRT/asserção no Mac. Ainda sem observação física; preparar ativação reversível e seus gates para evitar um DFU apenas para leitura.

### Incremento 17 — sequência reversível REG_ON sem I/O físico

- Função AppleD2255PMUGPIOFunction usa byte12/13 do packet como modo/polaridade; flags101 dão modo1/polaridade1, sem inversão do booleano no bit0 do writer. Campo/pointer e rotina foram confrontados estaticamente; não equivale a observar sinal físico.
- Sequência por callbacks lê/valida byte herdado, salva original e marca restore_pending antes da escrita (falha pode ser parcial). Confirma leitura após ativação; erro tenta restore. Cleanup recusa modo/bits de outro dono alterados, mantém pendência em falha e verifica restauração; valor já ativo não gera escrita/reversão desnecessária.
- Cinco arquivos: header, testeC, runner, referência selecionada e plano. Preparar adapter que reivindique temporariamente o cliente PMIC somente quando livre, usando APIs I2C e evitando conflito com futuro MFD. Somente depois dos gates reunir observação, ativação reversível e identidade PCIe num DFU útil.

- Gates passaram: C nativo Mac/ARM64 e objeto kernel/Werror; sete mutações compiladas morreram por SIGABRT/asserção (cleanup, pending antes de write, original, posse, duas verificações, guard de pending). Falha inicial do objeto revelou macro reservada current; renomeada para readback e gate kernel repetido sem supressões. Cobertos erro de ativação+cleanup simultâneos, retry e write de restore ignorado. Ainda nenhum acesso físico nesta fatia.

### Incremento 18 — adapter I2C reversível e gate contínuo

- Módulo de observação agora reivindica o cliente PMIC com driver core/I2C, validando exatamente placa/nó/adapter/bus/endereço e recusando dono existente. Não autoload, probe de endereços ou ativação em insmod. Reader/writer únicos usam APIs I2C; ativação posterior pelo parâmetro power e estado público bound/active/restore_pending/original, serializados por mutex.
- Controle restaura/verifica original por power0 antes do unload; callback remove não pode devolver erro, portanto registra errno/pendência e não vale como prova de cleanup. Runbook descreve recusa e retry, sem declarar hardware validado. Fonte I2C fixada confirma adapter.dev.of_node do controller e probe/remove modernos.
- Cinco arquivos: adapter, runner de sete mutações, CI, runbook e plano. Build ARM64/Werror/modpost passou com símbolos da ABI preservada. Nova imagem, firmware e DFU não necessários para preparar este módulo. Conferir ELF/hash privado e completar gate antes de uma sessão física agrupada.
- ELF/ABI/hash privado conferidos: SHA7684577acc5de5578acce47ae99d0955188cdcdecb0c0ed48e423fc5d3557279. Runner público passou baseline e sete mortes por SIGABRT/asserção; AST e PUBLIC_TREE_OK passaram. Transferência Multipass demorou e primeira verificação local ocorreu antes de terminar; conferência repetida depois da conclusão, sem contar a falha de arquivo ausente como gate.

### Incremento 19 — regressão do writer DART antes de DMA

- Monitor REG_ON esgotou prazo sem DFU/Pongo; nenhum payload Linux enviado. Operador ainda não confirmou nova etapa física. Não repetir boots automaticamente. Candidata7f43463 passou os dois CIs exatos37049743664/37049739909; continuar trabalho independente.
- Fonte DART fixada escreve TCR S5L de quatro streams com máscara invertida e sem shift do valor; read/helper/callers confirmam campos de oito bits. Patch corrige cálculo e recusa SID>=4/valor>ff antes de MMIO. Não implica que layout/SID S5L foi comprovado no N71, nem habilita DMA. Lock/concurrency do registrador compartilhado permanece validação futura.
- Cinco arquivos: patch, harnessC, runnerPython, evidência e plano. Hunk antigo confrontado exatamente com fonte fixada (SHAec7576ce878cc5b92c419eeab81f7a4141e816a8657fbfe33162e87d62a4a5ad). Mac passou versão corrigida e cinco falhas por SIGABRT/asserção (original/máscara/shift/boundary/valor); ARM64 confirmou original falha e corrigido passa. Build objeto kernel/Werror em cópia externa, preservando árvore/imagem funcional, em curso. Ainda sem evidência física REG_ON/DART/Wi-Fi.
- Objeto kernel/Werror passou em cópia externa e git diff --exit-code confirmou fonte funcional intacta. Mensagem tardia grpc_wait_for_shutdown do transporte não alterou o exit0 nem o resultado do compilador; gate relevante não repetido. Patch deve passar apply --check na árvore fixada antes de commit. Ativação de DMA depende de layout/SID/posse/IOMMU, não somente deste fix.

### Incremento 20 — patchset reproduzível sem substituir baseline

- Decisão: aplicar o patch DART exclusivamente em checkout vinculado separado da VM, fixando SHA do patch/base e validando o conteúdo completo do único arquivo alterado antes/depois do build. Baseline continua exigindo árvore limpa; novo modo explícito n71-dart-tcr-v1 registra hashes de patch/blob na proveniência e recusa deltas extras. Sem mudar default/payload/DT ou integrar main.
- Cinco arquivos previstos: helper de patchset, receita de build, testes reais de Git/filesystem, documentação do kernel e plano. Exigir recusa de patch adulterado, outro commit, árvore divergente, symlink e arquivo alheio; aplicação idempotente sem sobrescrever trabalho. Validar numa worktree real separada da VM e reutilizar gate de objeto/Werror sem reconstruir Image apenas para este patch.
- Objetivo segue sendo Wi-Fi/telemetria físicos; esta preparação garante que o fix não se perca nos builds agregados seguintes. DFU continua dependência física não atendida; não renovar monitor sem modo DFU confirmado.

- Gates: cinco testes reais de Git/filesystem Mac/ARM64, sete mutações compiladas com falha por AssertionError (hash/base/worktree/delta/index/prova física/alias), AST, Bash e ShellCheck passaram. Duas lacunas detectadas pelo mutation gate foram corrigidas: adulteração agora mantém hunk/framing válidos; teste de alias restaura target antes de testar outra fronteira. Worktree real aplicada/conferida duas vezes; blob completo059546b68b266a5fb30c230a4d805572b2f601076cf04f06dfb41250312c67cc igual à cópia já compilada/Werror, gate reutilizado. Negativas reais da receita recusaram baseline/patchset desconhecido sem criar output. CIfde6940 passou nos runs37051485476/37051477957. Nenhuma imagem nova ou ação física nesta fatia.

### Incremento 21 — imagem separada e gate contínuo de patchset

- Runner público executa baseline/sete mutações apenas em repos Git temporários, exigindo AssertionError e recusando erro de import/sintaxe/timeout como kill. Acrescentado ao CI Ubuntu/macOS. Três arquivos desta preparação: runner, workflow e plano; reproduzir runner antes de commit.
- Build completo iniciado na VM com receita publicada a47ce2c, worktree kernel-n71-dart-source-20261002 e output novo kernel-n71-dart-build-20261002, no modo n71-dart-tcr-v1. Nenhum pacote/configuração global/instalação no Mac, novo DT, firmware ou reboot do iPhone. Baseline e imagem funcional preservados; candidato somente poderá integrar perfil após outputs/config embutida/proveniência conferidos.
- Aguardar handle do processo confirmado vivo; não reiniciar build por expiração de uma leitura. Fonte/status e outputs finais determinarão conclusão. Goal Wi-Fi/telemetria permanece ativo e não é substituído por build/CI.

- Runner público passou baseline e sete kills por AssertionError; 47 opções Kconfig verificadas e KERNEL_COMPILE_STARTED no processo real da VM. Não reutilizar um log/state file como prova de processo vivo; acompanhar handle retornado pelo exec. Guard de tree e sourcepatch antes/depois permanecem gates do build completo.

### Incremento 22 — build DART concluído e propriedade HDQ delimitada

- Build separado exit0;47 opções Kconfig, patchset exato antes/depois, header ARM64/16KiB, configuração embutida/cmp e gzip/Image conferidos. Artefatos privados copiados ao Mac com hashes recalculados; DTB permanece baseline. Ainda sem integração no perfil ou boot físico do novo Image. CIab26ffe passou nos dois runs37054380503/37054374211.
- Referência SN2400 corrigiu uma hipótese: object+d4 é modo de software0/1;40/60 são máscaras de eventos do segundo registro de um write1–3, não controle direto no registro0. Handshake1d/4/ACKbit5/6 foi delimitado; timeout/erro inicial não restauram diretamente na primitiva. Mux/posse/restauração/unidades continuam gates antes de I/O.
- Cinco arquivos documentais: evidências build/HDQ, guia HDQ, receita kernel e plano. Não repetir suíte de código inalterado; conferir JSON/hashes/referências/guard. iPhone voltou ao iOS e SSH indisponível; tentativas locais de abrir Ajustes/espelhar abandonadas a pedido do operador. Nenhuma nova ação DFU nesta fatia. Continuar integração separada e inventário somente leitura, agrupando a próxima validação física.

### Incremento 23 — integração explicitamente fixada ao patchset

- Cinco arquivos: integrador, testes reais filesystem/perfil, runner de mutações, receita kernel e plano. Opção explícita n71-dart-tcr-v1 seleciona somente o registro novo, verifica base/patch e DART builtin, conservando os gates de artefatos/identidades e o modo baseline inalterado. Proveniência mantém a escolha; sem USB, instalação ou troca de default.
- Critérios: recusar Image novo no modo baseline, base/patch divergentes e DART modular antes de criar output; sucesso explícito preserva chaves/registro antigo/prova física false. Rodar dez testes de integração e onze mutações compiladas por AssertionError; depois compor perfil privado real separado. Perfil PCIe requer adaptação posterior do layout, sem trocar hashes baseline nem repetir DFU apenas para esta preparação.

- Gates concluídos: dez testes Mac/ARM64, onze mutações compiladas com AssertionError e sem ERROR/import/sintaxe aceitos, AST e quatro regressões do compositor diagnóstico passaram. Aplicação real recusou a imagem nova no modo padrão antes de criar output; seleção explícita compôs perfil privado separado, verificando payload/identidades e mantendo initramfs sem delta. Nenhum novo boot ou default alterado. Hash privado do payload49bcd3226adc9a17bc06270c08669faba9fd943bbcdf455558afd7f9c6b098fd; não é prova de funcionamento físico.

### Incremento 24 — PMIC compartilhado no mesmo boot

- Sessão agrupada chegou ao Linux pelo Pongo já ativo, restaurou44 entradas e SSH/HTTP/Herdr. Inventário confirmou I2C1/UART5 desativados. Módulo original recusou EBUSY porque simple-mfd-i2c controla PMIC74; nenhuma leitura REG_ON ou value write ocorreu. Não desassociar o MFD/RTC/NVMEM para contornar a recusa.
- Decisão: substituir somente o adapter por acesso ao regmap16r/8v sem cache do MFD fixado, mantendo driver/filhos/DT/kernel. Validar placa/nó/bus/endereço/compatibles/driver/mapa e revalidar posse sob device_lock em cada operação, antes de usar memória devm. Escritura limita máscara1 por regmap_update_bits; sequência de rollback e verificações permanece centralizada no header anterior.
- Build/Werror/modpost com símbolos do vmlinux preservado, teste de sequência/mutações relevante e verificação de hash/ABI precedem transferência por SSH neste mesmo boot. Não é prova de rádio/carga ou aprovação de modos desconhecidos. Se a leitura recusar modo, registrar sem ativar. Manter logs privados e publicar somente resultados selecionados.

- Gates concluídos: contrato C Mac/ARM64, nove mutações compiladas por SIGABRT/asserção (incluindo divergência de posse/request largo/output somente bit0), sequência centralizada e sete mutações; módulo Werror/modpost com ABI exata e hash fdf7ba25cc5b5a74f4ca581530780596b0237c57d6f613e73831be2135b7fb8d. Fonte/kernel funcional intactos. Transferência/hash no iPhone, leitura física control00/bit0=0/compatible-plan=0: não ativar modo desconhecido.
- Mesmo boot: adapter substituído por SSH, sem nova imagem/DFU, MFD/filhos mantidos. power0 mostrou active0/pending0, módulo descarregado, MFD e HTTP confirmados. Snapshot/sync concluídos; retorno ao iOS não confirmado em60s e solicitado fallback físico. Não declarar reboot por software aprovado neste caso. Wi-Fi/telemetria/carga permanecem pendentes; próximo passo é reproduzir inicialização do GPIO10 a partir da referência N71.

### Incremento 25 — corrigir classificação do modo REG_ON

- Leitura física00 expôs guard incorreto: referência AppleD2255PMU set-mode006933d8c compara byte com40 em006933e08/e0c, classifica valor<40 como1 e >=40 como2; modo solicitado1 retorna sem write se já abaixo40. PacketGPIO10 usa mode1/polarity1. Writer006933eb0 usa booleano/polaridade e não exige bit6=1. Portanto guard anterior01 nos bits7:6 não correspondia a mode1.
- Correção restrita: aceitar somente bits7:6=00 e bits4:3=00, preservando bits5/2/1 e alterando apenas bit0. Nenhuma escrita física deste incremento, configuração de direção/drive ou carregador. Regressão usa leitura00, ativa01/restaura00 em callbacks sintéticos, rejeita40 e mantém falhas parciais/pendência/posse.
- Cinco arquivos: contrato, dois testesC, runner e plano. Dez mutações do contrato (incluindo inversão anterior do modo) e sete de sequência, C Mac/ARM64 e novo módulo/Werror/hash antes de qualquer próxima carga. Usar somente o mesmo backend regmap, preservando o MFD. Não solicitar novo DFU até reunir candidata e coleta úteis.

- Gates concluídos: dois contratos C Mac/ARM64, dez mutações do planejamento e sete da sequência compiladas com morte por SIGABRT/asserção; módulo Werror/modpost ABI7.2.0-iphone6s-source SHA92aefccc9c5992f50abb4df350c181d7a2eab71ba4413d5089c3b435f5c3dcca, header ARM64 igual ao host. Leituras/regmap/MFD/PCIe no hardware ainda se referem ao artefato anterior; ativação corrigida não foi feita.
- Operador confirmou tela de bloqueio após fallback físico. Mac ainda sem enumeração USB e leitura de bateria não disponível; solicitada apenas reconexão Lightning. Não interpretar tela de bloqueio como prova de carga nem trocar cabo/porta automaticamente.

### Incremento 26 — registrar sessão e corrigir runbook

- Cinco arquivos documentais: referência REG_ON corrigida, evidência física selecionada, runbook modular, inventário HDQ e plano. Separar módulo observado fdf7... de correção compilada92aef... ainda não aplicada; não promover teste sintético a ativação física. Preservar resultados históricos e explicar guard errado explicitamente.
- Sessão única agrupou inventário/recusa inicial/update regmap/read00/cleanup/HTTP/snapshot; PCIe não repetido sem ativação qualificada. Nenhum raw/disassembly/calibração/chave/serial publicado. Registrar retorno software inconclusivo e fallback físico; não atribuir carga ou capacidade a leitura ausente. Prosseguir pela candidata corrigida antes de solicitar nova sequência física.

### Incremento 27 — distinguir transporte e readback no mesmo boot

- Candidata corrigida bootou/restaurou44 entradas/SSH/HTTP/Herdr. Leitura00 agora compatible-plan1. Ativação única retornou EIO e sequência confirmou active0/pending0; power0/unload passaram. PCIe não executado sem ativação comprovada. Não repetir escrita idêntica sem informação nova.
- Instrumentar somente callbacks regmap: leitura com error/value_valid e write com requested/prior/error, sem outro registro ou mudança de sequência. Preservar raw0 inicializado em falha para evitar saída de stack. Build modular separado/Werror/hash e atualização por SSH no mesmo boot; registro específico determinará se o transporte recusou a escrita ou readback não mudou. Gates dos headers/rollback intactos reutilizados.

- Trace no mesmo boot: escrita solicitada01/prior00 retornou0; readback válido00 manteve EIO. Cleanup/unload anterior e pendência0 confirmados; não repetir ativação com a mesma hipótese. Referência GPIO read00693401c lê banco0x180+((0x600+pin*32)>>8), bit(pin&7); GPIO10=187/bit2. Acrescentar getter somente leitura desse registro fixado, sem chamada Apple set-mode nem dump/scan, para separar control byte e nível físico. Getter serializa controle e valida owner/mapa sob device_lock. Módulo separado/ABI/hash antes da atualização por SSH.

- Gates/resultado: trace e getter nível linkaram Werror/modpost/ABI exatos, hashes host/guest695322.../0eda013... conferidos. Getter leu187 raw20/bit2=0, sem set-mode ou novo write. Duas atualizações de módulo no mesmo boot; todos removidos com active0/pending0; PCIe/DMA não executados. Fonte PASEMI fixada localiza o controlador pelo CONFIG_I2C_APPLE (i2c-pasemi-core/platform), não por arquivo i2c-apple.c. Prosseguir pelo GPIO/mux/control sem remover checks de readback.

- Snapshot/sync e retorno iOS USB por software passaram nesta sessão; bateria97→91 no conjunto DFU/Linux/reboot/iOS, carga iOS ativa. Não interpretar como corrente líquida ou qualificação de alimentação Linux. Continuar pesquisa no Mac/VM enquanto o aparelho recarrega em iOS; buscar gpio-pin-config por diagnóstico somente leitura antes de novo DFU.

## Limites e continuidade

Não instalar pacotes no Mac, modificar política/rede global/sudoers/PF/firewall/DNS, contas remotas ou recursos fora do projeto. Não publicar firmware/calibração/serial/MAC/chaves/snapshots. VM dedicada e artefatos privados, preservando fonte/build funcional. Não prolongar operação não supervisionada antes de carga validada. Pedir apenas DFU/ações físicas indispensáveis; ausência de informação crítica para registrar escrita não autoriza inventá-la. Bloqueios concretos entram nas issues e no goal somente segundo o limiar de três turnos; continuar pesquisa/implementação independente enquanto houver avanço possível.

### Incremento 30 — corrigir seleção CSEL do registrador PMIC

- A conferência dos 11 opcodes do mapper006933a88 no Mach-O fixado revelou inversão dos operandos no entendimento anterior: `csel w9,w9,w10,lo` escolhe w9 quando pin<17. GPIO10 usa900+2*10=914; 8c0+6*pin aplica-se apenas aos pinos17..20. O endereço8fc usado nos testes anteriores não foi o controle REG_ON mapeado. Preservar os registros físicos históricos como fatos desse endereço, sem inferir falha do GPIO10 ou segurança elétrica.
- Corrigir contrato e endereçamento; testar todos os pinos0..20, recusar21/unsigned máximo sem alterar saída, verificar fronteira16/17 e rejeitar explicitamente o endereço anterior8fc. Adicionar mutações de CSEL, limite e stride; preservar guard de modo/bit0 e ownership MFD. Cinco arquivos nesta fase: contrato, teste, runner, referência selecionada e plano.
- Próxima prova física deve observar914 antes de qualquer ativação. Sem remover guard de modo/direção, sem repetir escrita8fc, sem novo boot só para verificar a correção. Configurações GPIO opcionais não apareceram nas duas consultas iOS selecionadas (serviço e provider); isso não prova ausência em todos os planos.
- Gates da correção: baseline C e 14 mutações compiladas morreram por SIGABRT/asserção no Mac e ARM64; sequência e sete mutações também passaram em ambos. Módulo ARM64/Werror/modpost compilou usando os símbolos do vmlinux preservado; validação do artefato/ABI e próxima observação914 permanecem gates distintos. O runner recusou inicialmente um anchor duplicado, corrigido sem contar essa recusa como kill.

### Incremento 31 — corrigir interpretação das provas históricas

- Runbook atualizado e os dois JSON físicos anotados sem apagar fatos: leitura/tentativa8fc não foi controleGPIO10, logo não qualifica seu modo ou falha. Referência de status187/bit2 permanece separada. Queries iOS de serviço/provider não apresentaram as quatro propriedades opcionais de GPIO; não extrapolar para toda a IORegistry.
- ABI7.2.0-iphone6s-source SMP preempt mod_unload aarch64, ELF64/AArch64 e hash02cb9f6b6c9395addcca5c98f90f7657bf12c20c97d6c8a6b56aaf71ad41d1c7 conferidos no guest/host. Fonte funcional gitdiff limpa; nenhuma nova imagem ou driver carregado no hardware. Quatro arquivos documentais nesta fase.
- Decisão: observar914 antes de escrita e exigir também nível187/bit2 alto antes de PCIe. Agrupar novas leituras/ativação qualificada/PCIe em uma sessão, com módulos atualizáveis por SSH. Não repetir diagnóstico com módulo antigo ou afrouxar guard de modo.

### Incremento 32 — reprodução da conferência binária GPIO

- Documentado comando Python padrão somente leitura, fixando tamanho/hash/offset e11 opcodes do mapper. Verifica campos CSEL e referência Arm primária para seleção/LO; comando executado no insumo privado real. Dois arquivos nesta fase: N71_REFERENCIA e plano. Nenhum reboot adicional ou execução de firmware.
- Candidata/coletores privados e snapshot44entradas verificados; iOS informou100%/FullyCharged/ExternalConnected. Aguardando disponibilidade física do operador para um único boot curto; não iniciar recuperação sem quem possa fazer o DFU. CI da correção em execução em handles37083135609/37083133659.

### Incremento 33 — handshake HDQ N71 com pendência explícita

- Novo confronto consumidor/provider: AppleHDQGasGaugeControl guarda function-battery_swi_request em+a0; helper0068d5568 transmite1,0068d560c transmite0. Provider SN2400 HDQm em005d67a90..005d67c34 mapeia1→gated(1,0),0→gated(0,0),2→gated(0,1). Pedido1 usa handshake sem escrita final06; não tratar comando2 como pedido padrão do medidor.
- Implementar primitiva de handshake selecionada: escrever04 em1d, ler ackbit5, opcionalmente escrever06, erros propagados e polling limitado100 com delays10ms. Backend externo/caller deve validar N71/cliente/mux e coordenar cleanup; marcar pendência antes da primeira escrita, inclusive quando retorna erro, sem declarar restauração por callback falho. Não fornecer backend I2C/charger, autoload, alteração DT ou operação física nesta fase.
- Cinco arquivos públicos: header, C de contrato, runner de mutações, evidência HDQ selecionada e este plano. Verificar referência/registros/ordem, bytes inválidos, limites, todos os erros de I/O e recusa de reentrada, com compilação Mac/ARM64/kernel e mutações que compilem. Cleanup físico e integração UART/mux continuam tarefas abertas, não substituir telemetria real por este gate.
- Gates: baseline/15 mutações C compiladas morreram por SIGABRT/asserção no Mac e ARM64; objeto do header no contexto __KERNEL__/Werror passou na fonte preservada. A primeira compilação do harness recusou falta de protótipo; corrigido somente o harness e repetido só esse gate. Erro de compilação de um mutante inicial também foi corrigido, sem contar como kill. Runner AST/JSON/diff-check passaram. Sem typechecker Python configurado, sem sensor físico ou charge proof. CI anterior8f977a5 concluiu sucesso nos dois runs37083451664/37083447466.

### Incremento 34 — gates contínuos e integração HDQ delimitada

- CI recebe runner dedicado do handshake no mesmo job Ubuntu/macOS; documentação registra comandos consumidor/provider, obrigação de cleanup e ausência de backend de hardware. Três arquivos nesta fase: workflow, ALIMENTACAO e plano. Suíte anterior8f977a5 preservada verde; gate novo compõe próximo CI, sem instalar ferramentas no Mac nem reiniciar o aparelho.
- Próxima implementação HDQ: confrontar GPIO2/config102 com o driver Apple SoC GPIO; definir snapshot/ownership das máscaras/controlador SN2400 e cleanup antes de adapter I2C/UART. Não rebatizar BQ27540 como BQ27545, programar limites de carga ou tratar ACK sintético como medição física. Sessão física Wi-Fi continua aguardando disponibilidade do operador na pergunta já enviada, sem repeti-la.

### Incremento 35 — tradução GPIO2 específica do N71

- Confirmada classe AppleS5L8960XGPIOIC pelo cstring/metaclass/vtable; primeira classe do kext é T8006 e não serve como substituta. AppleARMGPIOFunction copia pacote, chama sem argumentos e escolhe mode2 de config102. Slot5e8 aponta00611929c; tabela fixa mode2→006119380, máscara270, valor220 quando glitchless ausente/zero ou210 quando presente/nãozero. O GPIO runtime phandle1e não contém glitchless. Não confundir modo2 Apple com seletor periférico2 Linux: caminho normal equivale a seletor1/entrada habilitada e ainda limpa bit4.
- Cinco arquivos: contrato puro, teste C, runner de mutações, fatos HDQ selecionados e plano. Nenhum MMIO, driver, DT, clock, UART ou carregador alterado. Testar pin/config/variante inválidos, máscara/direção, preservação de bits e compilação Mac/ARM64/kernel. Backend precisa ownership/snapshot/readback/restore; cálculo não prova operação física.
- Operador informou console disponível, mas SSH/USB não apareceram; nenhum módulo carregado. Solicitada somente reconexão Lightning, sem novo DFU. Continuar pesquisa enquanto aguarda.
- Gates Mac/ARM64: baseline e dez mutações compiladas morreram por SIGABRT/asserção. Conferência privada dos seis trechos binários, SHA integral e ausência de glitchless no nó runtime passou; hashes/offsets publicados permitem reprodução sem publicar firmware. AST/JSON/public-tree/diff-check passaram. Nenhum typechecker Python configurado; lint remoto fica no CI existente.
- Objeto probe.o compilou em contexto __KERNEL__ com Werror na VM preservada; fonte funcional manteve diff vazio. Sem módulo carregável ou teste físico de GPIO2 nesta fase.

### Incremento 36 — gate contínuo e reprodução GPIO2

- Três arquivos: CI, guia HDQ e plano. Runner GPIO2 entra nos jobs fonte Ubuntu/macOS; guia explica classes, bytes config102, ramificação glitchless, máscara270/valor220 e diferença do seletor Linux. Conferência por hashes de trechos reproduzível, firmware privado.
- Validação nativa Mac/ARM64/kernel e referência integral já passou na fase35; reutilizar enquanto entradas preservadas. Rodar reprodução documental/AST/JSON/guard/diff e aguardar lint/testes remotos. Typechecker Python não configurado. Não solicitar novo DFU nem senha para esta publicação.

### Incremento 37 — esclarecer limites da configuração dinâmica

- Três arquivos: comentário do contrato GPIO2, guia HDQ e plano. Não chamar bit4 de direção GPIO sem qualificação: preservar descrição apenas como bit da máscara do setter N71. Nenhuma expressão executável alterada; reutilizar gates Mac/ARM64/kernel/10 mutações do incremento35.
- Configuração7.2 contém OF_DYNAMIC/OF_OVERLAY/CONFIGFS, API overlay apply/remove exportadaGPL; configfs não prova carregador por arquivos. Não houve overlay/clock/UART/I2C1 no aparelho. Estudar loader com alvo/ownership/cleanup qualificados para reduzir DFUs.
- Cadeia específica s800-0-3-pmgr confirma ps_uart5@80200 e ps_i2c1@801a0, pai ps_sio_p. ADT clock-gates UART5 é55 hexadecimal (85decimal); não presumir conversão ID→offset. SSH/USB ainda indisponível; solicitação de reconexão permanece pendente, sem nova pergunta.

### Incremento 38 — adapter serdev para dois stop bits

- Lacuna real: referência UART N71 requer57600/8N2; kernel958481f não expõe set_stop_bits no serdev. Implementar API que aceita somente1/2, retorna unsupported quando falta callback, propaga erro; adapterTTY preserva demais campos, muda apenasCSTOPB, verifica readback e recusa porta fechada. Sem autoload/chamada em probe, nó habilitado ou I/O físico.
- Cinco arquivos públicos: patch de três fontes kernel, harness C exercitando funções adicionadas reais, runner de mutações, evidência JSON e plano. Aplicação apenas em worktree VM isolado; manter baseline e DART separados. Compilar Mac/ARM64/harness e os objetos kernel alterados comWerror. Não integrar candidata antes dos próximos gates de mux/ownership/releaseSN2400.
- Gates finais: Mac/ARM64 baseline e12 mutações compiladas morreram por SIGABRT/asserção, incluindo registro real do callback extraído do patch e contagem encaminhada. Parser inicial confundiu protótipo/definição; corrigido para localizar corpo, sem contar erro de harness como kill. Checkpatch inicial recusou tabs/nomeação; corrigido, final0erros/0avisos. Dois objetos AArch64 compilaram comWerror; símbolo exportado no objeto e hashes dos três arquivos conferidos. Worktree tem exatamente três fontes alteradas; baseline manteve diff vazio. Não houve linkImage/modpost, imagem nova ou boot físico; API modifica layoutops, exige rebuild kernel/módulos/versão distinta antes de integrar.

### Incremento 39 — integração e gates serdev delimitados

- Três arquivos: workflow, guia HDQ e plano. CI Mac/Ubuntu compila as rotinas e callback adicionados no patch real e exige12 mutações por asserção. Guia registraCSTOPB com fonte primária oficial, caminhos de build e limites: objetos não sãoImage/modpost/boot, TTYreadback não é forma de onda, erro não é cleanup automático.
- Layoutops serdev mudou; precisa rebuild kernel/módulos e identidade distinta. Não reutilizar ABI/identidade da imagem atual nem integrar silenciosamente no patchsetDART. Próxima fatia precisa empacotar patchset agregado e qualificar propriedade/release doHDQ, com o mínimo de novosDFUs. Reutilizar provas de objetos e Mac/ARM64 porque código executável não mudou nesta fase. AST/JSON/publictree/diff-check; gates remotos no branch autorizado.

### Incremento 40 — seleção da liberação HDQ pela referência N71

- Cinco arquivos: contrato puro de seleção, teste C, runner de mutações, JSON de referência e plano. Confirmar campo+b0 pela string function-battery_alert e ponto único de armazenamento005d674bc. Pedido padrão de liberação command0/request0 depende de modo software0/1, máscara cache+b8 e status7/bit7; não chamar esse campo de ponteiro de controlador por suposição.
- Selecionar apenas plano sem callbacks ou I/O: modo1/cache0 sem handshake; modo1/cache nãozero handshake sem06; modo0/alert presente/statusbit7 limpo handshake com06; demais casos modo0 escrevem0 em1d. Máscara de disable é cache sembit40 quando alert presente. Recusar status inválido, byte largo, modo desconhecido e flag não booleana sem modificar saída. Seleção não prova reversibilidade elétrica, restore de máscaras nem efeito de leitura de status.
- Verificar instruções e hashes em janelas limitadas do Mach-O fixado; publicar somente fatos/hashes, sem bytes/disassembly. Compilar contrato Mac/ARM64 e objeto kernel/Werror; mutações compiladas devem falhar por asserção. Não modificar módulo/perfil do boot físico Wi-Fi enquanto o monitor aguarda DFU.
- Gates: Mac/ARM64 baseline e14 mutações compiladas detectadas por SIGABRT/asserção; objeto kernel compilado comWerror na VM preservada e gitdiff funcional vazio. Sete janelas da referência qualificadas porSHA, incluindo CString completo com terminador. AST/JSON/publictree/diff-check passaram. Nenhum callback, leitura/escritaSN2400, envioUART ou medição física executado. CI serdev anterioreb7a304 passou nos dois runs37087818576/37087815586; comentário#2 atualizado. Monitor Wi-Fi expirou semDFU/Pongo, não enviou payload; pergunta física permanece pendente. Não reiniciar o monitor sem resposta do operador.

### Incremento 41 — gate contínuo da liberação HDQ

- Três arquivos: workflow, guiaHDQ e plano. Documentar a tabela mode/cache/alert/status sem transformá-la em receita elétrica. CI executa o runner Mac/Ubuntu; preservar testes nativos/kernel da fase40 enquanto entradas não mudam.
- AST/JSON/publictree/diff-check locais; lint Python não disponível no Mac, sem instalar pacote. Aguardar lint remoto da branch autorizada. Próxima integração deve empacotar as alterações kernel com identidade distinta e continuar ownership GPIO2/clocks/SN2400 antes de habilitar I2C1/UART5 ou transmitir HDQ.

### Incremento 42 — empacotar DART e serdev como candidata única

- Cinco arquivos: helperkernel_bundle, teste de integração Git real, runner de mutações, evidência do bundle e plano. Novo nome n71-dart-serdev-v1 e identificação futura distinta -iphone6s-dart-serdev1; manter helperDART legado e baseline intactos. Validar patches fixados e hashes inteiros dos quatro blobs, HEAD, worktree isolado e ausência de trabalho externo/flags de índice ocultas; aplicar o conjunto numa única chamada gitapply apóscheck.
- Exercitar aplicação exata/idempotente, baseline preservada, recusa de mistura parcial, conteúdo/patch divergente, mudanças externas/staging/index oculto/symlinks. Mutações reais precisam provocar falha dos testes. Depois confirmar o mesmo helper na fonte pública real da VM, worktree e output separados; não criar perfil ou carregar o bundle antes de buildImage/modpost/ABI distinta e recursosHDQ restantes qualificados.
- Gates: três testes Git reais e11 mutações detectadas por AssertionError no Mac/ARM64. A prova de hash original foi ajustada para distinguir blob HEAD de blob candidato jápatched; validação direta do patch evita confundir recusa tardia com o guard de integridade. Worktree real da fonte fixada recebeu ambos os patches e exatamente quatro blobs foram conferidos; baseline manteve diff vazio. Três objetos AArch64 compilaramWerror em output separado e kernel.release confirmou7.2.0-iphone6s-dart-serdev1. SemImage/modpost/perfil/boot. AST/JSON/publictree/diff-check locais; lint remoto segue próximoCI.

### Incremento 43 — reprodução e gate do bundle agregado

- Cinco arquivos: CI, guia de bundle, referênciaHDQ, evidência do bundle e plano. Config comparada integralmente: única linha alterada éLOCALVERSION. Documentar comandos executados, versão/configuração, hashes, aplicação exclusiva/idempotente e limites de objetos versusImage/modpost/boot. Receita/integrador legado não aceita o bundle; próximo desenvolvimento deve integrar a build completa com identidade explícita, sem trocar o perfil atual.
- CI Mac/Ubuntu executa mutações do helper, além do unittest descoberto. Reutilizar gates Mac/ARM64/fontes/objetos da fase42; nenhum código executável muda nesta fase. AST/JSON/publictree/diff-check locais, lint remoto pendente. Sem novo monitorDFU, módulo ou hardwareI/O enquanto a resposta física continua pendente.

### Incremento 44 — qualificar somente latch80/81 observado no GPIO10

- Cinco arquivos: contratoREG_ON, teste, runner, referência selecionada e plano. Sessão correta914 observou80/nível187bit2=0 e recusou ativação; cleanup/unload passaram sem valor escrito. Referência writer006933eb0 admite bytes altos quando polarity1 do packet101: com tabela ausente, limpa apenasbits0/3/4 e ajusta bit0; não muda bits7:6. gpio-pin-config ausente no DT runtime completoSHAfixado, consultas iOS selecionadas e chaves do XMLprelinkado fixado. Não inventar mask/value de tabela ou mudar modo para00.
- Acrescentar apenas bytes exatos80/81 à seleção existente, preservando todo estado exceto bit0 porregmap_update_bits(mask1). Não aceitar valores82..ff por essa exceção; permitir rollback81→80. Classifier Apple continua mode2 para80; admissão pelo writer com polarity1 não declara mode1 nem comprova nível elétrico. Exigir gates Mac/ARM64/sequence/kernelWerror/modpost/ABI/hash antes de nova tentativa no mesmoboot. Manter ownerMFD/readback/level/restorepending e PCIe condicionado a nível alto.
- Gates: contratoMac/ARM64 baseline e16 mutações por asserção; sequênciaMac/ARM64 sete mutações; harness80/81 sintético de erros/rollback passou em ambos. MóduloWerror/modpost/ELF64AArch64/ABI/hash383b85... conferidos. Primeira build esqueceuKBUILD_EXTRA_SYMBOLS e modpost recusou símbolos indefinidos; corrigida pela receita existente/vmlinux.symvers, repetindo somente gatefalho, semsuprimirerros. Fonte funcional permaneceu limpa. Nenhum firmware/calibração/chave foi paraVM. Resultado físico fica registrado em fatia documental seguinte.

### Incremento 45 — resultado físico e regressão de rollback80

- Cinco arquivos: teste da sequência, evidência física, referênciaGPIO, runbook modular e plano. Num único boot, módulo antigo leu914=80 e recusou; atualizado porSSH apósgates, novo módulo escreveu81 com mask1/readback81. Amostra187/raw20/bit2=0 bloqueouPCIe. Restaurou80/readback80, pending0, unload confirmado. Não declarar alimentação WLAN pela escrita; não repetirtentativaidêntica sem informação nova.
- Acrescentar casos80→81→80, falhas e retries de restauração, estado81 previamente ativo semescrita e recusa de mudança externa parac1. Mac/ARM64 baseline e sete mutações por asserção passaram; contrato16/modpost/hash/objeto dafase44 reutilizados porque não houve mudança executável.
- Snapshot/sync e retorno softwareiOS passaram; bateria iOS85%/chargingtrue/externaltrue. Baseline100 foi anterior ao primeiro monitor expirado/espera, sem medição imediatamente antes do boot bem-sucedido; não atribuir diferença inteira15 ao Linux nem calcular corrente líquida. Continuar pesquisa/builds enquanto iOS recarrega, sem pedir outroDFU só para confirmar estado. CIbundlefc19d52 passou37089973729/37089971443.

### Incremento 46 — consolidar alimentação e limites do último boot

- Dois arquivos documentais: ALIMENTACAO e plano. Registrar85%/chargingtrue/externaltrue às02:49:22UTC e a ausência de baseline imediatamente anterior ao boot. Corrigir a hipótese antiga de ponteiro de controlador: campo+b0 foi qualificado como function-battery_alert na fase40. Ligar seleçãoHDQ e bundle sem tratar fonte/objetos como recurso físico.
- Reutilizar gates executáveis das fases40–45; validar somente delta documental/publictree/diff. Publicar no branch autorizado e atualizar as issues existentes de WLAN/alimentação, mantendo-as abertas. Próximo avanço precisa explicar latch81 com sample0 ou qualificar backendHDQ; não repetir boot/escrita idênticos sem informação nova.

### Incremento 47 — qualificar a amostragem GPIO sem novo boot

- Três arquivos documentais previstos: referênciaGPIO, runbook modular e plano. Conferir getter00693401c, flag de configuração e caminhoAppleGPIOFunction; publicar apenas offsets/hashes/fatos. O getter normal solicita mode1 antes de amostrar; nosso getter lê187/bit2 sem setter e80/81 classifica como mode2. Não inferir alimentação ausente nem alta a partir dessa amostra isolada. Manter o gate físico anterior até definir uma alternativa delimitada e verificável; não forçar configuração de outra placa.
- Fonte simple-mfd-i2c fixada configura16bits de endereço/8bits de valor sem cache; conferir isso pela fonte real. Driver D2333 público usa latch para saída e banco para entrada, mas não qualifica D2255 por analogia. CIcc926e2 passou37091710685/37091708676. Atualizar#9 com resultado parcial/limites, mantendo aberta.

### Próxima fatia — linkar a candidata agregada na VM

- Reutilizar worktree/output exclusivos já validados do bundle; logs/artefatos em subpasta nova privada e sem concorrência. Conferir fonte/configuração exatas antes/depois, ImageARM64/16KiB, config embutida/gzip/DTB, símbolo serdev e identidade distinta. Rebuild dos diagnósticos fica separado após o link; sem perfil ou boot novo até gates completos.
- Baselineoutput completo ocupa1082716KiB; output agregado configurado5456KiB; VM tem6989992KiB livres e Mac76494108KiB. Para esta conclusão de output existente, exigir margem de pelo menos tamanho completo anterior mais2GiB, não reduzir o requisito8GiB do builder para diretório novo. Preservar builds anteriores e registrar duração/saída reais; parar somente esta build se espaço ficar insuficiente. Publicar receita/manifesto/plano em até cinco arquivos após prova do link.

### Incremento 48 — preparar integração explícita da ABI agregada

- Quatro arquivos: integrador, testes, runner de mutações e plano. Aceitar bundle somente com novo manifesto de build completo verificado, base/patches/quatro blobs fixados, release/config LOCALVERSION distinta, DART/serdev incorporados e export serdev conferido. Manifesto ainda ausente impede uso real até terminar build/validação.
- Recusar módulos extras da ABI anterior no initramfs antes de criar saída; NCM legado conhecido pode ser retirado pela migração para builtin. Manter baseline/DART legados, layout/usuários/identidades e perfil padrão. Testar seleção explícita, manifests/config/exports inconsistentes e módulos antigos com fixtures não bootáveis; mutações devem falhar por asserção em Mac/ARM64. Sem USB ou boot nesta fase.
- Mac:14 testes e19 mutações por asserção passaram. ARM64 passou baseline e três mutações, mas a quarta excedeu60s competindo com buildImage; timeout não conta como kill. Adicionar seleção explícita de mutações ao runner e repetir apenas as16 restantes após reduzir prioridade somente da build própria na VM. Atualizar guia na quinta/última alteração pública da fase; código de integração não muda nesse retry.
- RetryARM64 acrescentou dez kills por asserção (13/19 totais) e expirou em bundle-identity; RAM disponível3210MiB, sem swap. Acrescentar timeout por suíte com escolhas limitadas60/120/180s, mantendo60 padrão; repetir apenas os seis casos restantes com180s. Não contar expiração como prova, ampliar recursos globais ou repetir os13 casos já comprovados. Build permanece única e nice10.
- Gates finais:14 testes e19 kills por asserção Mac; ARM64 baseline passou,13 kills anteriores e seis restantes passaram com180s. Opções de seleção/timeout do runner exercitadas no Mac por casos únicos, sem repetir gates anteriores. AST/publictree/diff passaram; lint não instalado no Mac, fica no CI. Cinco arquivos públicos nesta fase, sem integração real porque manifesto completo/artefatos ainda não estão disponíveis.

### Incremento 49 — composição diagnóstica com ABI selecionada

- Cinco arquivos previstos: compositor, teste do payload, runner de mutações, guia de bundle e plano. Encaminhar seleção explícita ao validador de kernel e exigir vermagic da release conferida no manifesto. Manter baseline como padrão e recusar release desconhecida/cross-ABI; não carregar módulo, alterar prefixo/userspace/identidades ou escolher perfil padrão.
- Exercitar ELF/ABI, preservação exata do payload e limites de DT com fixtures sintéticas; confirmar mutações por asserção e build real dos diagnósticos depois que Image/vmlinux.symvers estiverem prontos. Sem execução de firmware na VM ou no Mac, sem DFU novo nesta preparação.
- Gates: cinco testes e cinco mutações por asserção passaram no Mac/ARM64. Runner usa cópias descartáveis de nove fontes públicas, sem diretório runtime, chaves ou firmware. Guia registra seleção/ABI/cópia de módulo externo e ausência de autoload. AST/publictree/diff locais; CI da fase48 em andamento, sem nova build ou boot iniciado por esta fase.

### Incremento 50 — preparar descoberta PCIe delimitada após latch conferido

- Cinco arquivos: diagnósticoREG_ON, diagnósticoPCIe, CI, novo runbook de experimento e plano. Novo getter somente leitura do controle atual, sob os locks/owner existentes. Registrar reset conferido e release dos domínios no diagnósticoPCIe, sem alterar sua sequência ou habilitarDMA. CI executa o runner de composição da fase49.
- Decisão técnica: a amostra187 não foi qualificada como monitor de saída/rail no mode2 observado. Mantê-la como observação, sem chamá-la de power-good. Preparar tentativa única de treinamento/identificação semDMA após latch81 fresco, owner/readback/mode exatos e clocks/reset/mapas já qualificados; isso é descoberta de endpoint, não prova antecipada de alimentação. Nenhuma escrita adicional de modoPMIC, IRQ/DMA/firmware/rádio; sempre verificar cleanupPCIe e restore80/unload.
- Compilar C/modpost no baseline para verificar o delta, sem substituir módulo/perfil; rebuild com ABI nova apósImage. Reutilizar gates dos headers porque expressão/sequência não muda. Publicar limites e preservar evidência histórica de amostra0/bloqueio; não solicitarDFU antes de candidata/artefatos/gates completos. CIcb33c6a passou37093468348/37093466296.
- Gates: ambos C passaramWerror/modpost comKBUILD_EXTRA_SYMBOLS do vmlinux baseline preservado, semKBUILD_MODPOST_WARN. ELF64AArch64/reloc/vermagic conferidos: PCIe21632B/SHA351fb85641147e84a353cb2ba9ecee4f89783f8d41c0e1eb48fa40d06488575c; REG_ON17680B/SHAdbf95475e8e17deffa9a8cb0f80e09159cc2dd87cf36da6b7f19d31314deb31c. Fonte baseline gitdiff vazio; módulos não transferidos ao aparelho. Header/link/rollback gates anteriores reutilizados; source/publictree/diff passaram. Runner de composição passouMac/ARM64 na fase49 e entra no próximoCI.

### Incremento 51 — registrar Image agregado e ABI real

- Quatro arquivos previstos: manifesto de build completo separado, guia de bundle, link no runbook modular e plano. Build única terminou com exit0/2352s (39min12s), incluindo verificações/cópias/compressão; source/config e perfil atual preservados. Conferir Image16KiB, gzip/config embutida/DTB, export realserdev e hashes antes de liberar manifesto compilado.
- Rebuild dos dois diagnósticos com vmlinux.symvers do bundle, em novo diretórioM; não reutilizar binários baseline. Transferir só artefatos públicos selecionados para nova pasta privada Mac e recalcular hashes. Publicar manifesto depois dessas conferências; nenhuma imagem/módulo/chave no GitHub, nenhum novo boot nesta fase. Integração/composição real e sessão física continuam gates separados.
- Gates completos: Image52.070.912B/SHA dd03169..., gzip/config embutida/DTB/exportGPL conferidos; cinco artefatos recalculados no Mac. Primeiro link de módulos parou por ausência scripts/module.lds; modules_prepare gerou o pré-requisito, somente link externo repetido. SemWARNbypass. Novos módulosABI7.2.0-iphone6s-dart-serdev1: PCIe21640B/SHA0eba4038ace98b52ed3b935ca9942f8aec2047922b4d3405a155b0ee8daa468f, REG_ON17680B/SHA839c206ab1fd456dc265e7cf75977155156bfb5436e6c6acfcf3c39576831e37. ELF/vermagic/hash Mac/guest passaram. Fonte/bundle, Image e config preservados apósmodules_prepare. Manifesto completo separado habilita o próximo gate offline de integração; antigo registro de objetos permanece histórico. CI28cbb7f verde37094254366/37094251615.

### Incremento 52 — compor perfis reais sem novo boot

- Três arquivos públicos: registro sanitizado da candidata, guia de bundle e plano. Integrador selecionou n71-dart-serdev-v1, seguido do compositor com DTB diagnóstico e módulo da ABI nova. Saídas privadas novas; perfil padrão preservado.
- Gates reais passaram: fonte e payload completos, cinco artefatos do kernel, delta DTB limitado, identidades, cinco entradas do initramfs idênticas, MaxPower 500, nenhum módulo embutido/autoload. PCIe/REG_ON externos conferidos por ELF/vermagic/hash; arquivos 600 e diretórios 700. Snapshot local de 44 entradas validado. Sem USB/restore físico nesta composição.
- SSH tentou consultar a sessão relatada pelo operador, mas retornou 255; inventário USB selecionado não mostrou iPhone. Não pedir DFU ainda: preparar coletor com gate fresco e cleanup obrigatório, depois solicitar apenas a intervenção física indispensável. CI do manifesto em andamento.

### Incremento 53 — coletor físico agrupado e recuperação verificável

- Cinco arquivos públicos: coletor host, testes, mutações, runbook e plano. Exigir perfil/ABI/hash selecionados, UART5/I2C1 desativados, módulos ausentes e nenhum diagnóstico PCIe anterior nesse boot. Original80 antes de aquisição; estado e getter81 fresco antes de treinamento, incluindo nova conferência remota imediatamente antes do único insmod.
- Logs exclusivos impedem repetição da etapa antes de enviar comando. Timeout/erro/interrupt passam por cleanup: reset/domínios positivos antes de unload PCIe; restore/readback80/pending0 antes de unload REG_ON. Estado observado desconhecido não escreve; diagnóstico somente leitura pode ser descarregado sem aquisição. Endpoint/COMMAND/predicate/budget têm gates próprios; negativo de link é registrado sem alegar Wi-Fi.
- Exercitar caminhos de falha com SSH sintético e mutações por asserção; conferir perfil real em --check sem USB. Não solicitar PIN/temperatura nem reiniciar como parte do coletor. Após uma sessão comprovada, salvar snapshot/sync e medir iOS com o retorno existente.
- Gates finais: 10 testes sintéticos e sete mutações por asserção passaram no Mac; AST e --check do perfil real passaram. Primeiro runner recusou cleanup-finally porque um teste produziu KeyError ao acessar etapa ausente; corrigida a asserção de presença antes de consultar o comando. Repetição resultou em sete kills por AssertionError, sem ERROR. CI do Image passou37095524530/37095521628; gates da composição estão em andamento. Sem I/O no telefone nesta fase.

### Incremento 54 — automatizar os gates do coletor

- Dois arquivos: CI e plano. Os dez testes entram na descoberta já existente; acrescentar execução do runner de sete mutações em Linux/macOS para detectar relaxamentos de latch fresco, restore pendente, cleanup obrigatório, orçamento de polling, endpoint e predicado de link. Não instala ferramentas no Mac nem executa SSH/USB no runner.
- Gates locais da fase53 reutilizados, diff e árvore pública conferidos. Candidata/perfis/artefatos preservados; nenhuma nova build ou boot. Issues #12/#34 atualizadas com evidência de Image/composição, mantendo DMA/Wi-Fi/HDQ físicos pendentes. Aguardando apenas reconexão/estado do aparelho, porque o último inventário USB não o detectou.

### Incremento 55 — observador físico GPIO2 sem alteração de estado

- Até cinco arquivos: módulo, Makefile, guia HDQ, evidência selecionada e plano. Fonte fixada do provider usa REGCACHE_FLAT; leitura regmap pode vir do cache. Preparar um módulo externo para comparar cache com duas leituras bypassed do offset08, usando exclusivamente o regmap do provider exato N71, sob device_lock. Sem gpio_request, mux/direção, MMIO direto, UART, I2C1 ou carregador.
- Recusar placa/nó/compatible/recurso/driver/regmap divergentes. run=1 explícito, observação única, nenhum parâmetro de escrita ou autoload. Bypass deve usar a API existente, que preserva flags de cache sob o lock interno; não reconstruir estrutura privada do driver. Resultados são amostras, sem propriedade da linha, rail ou telemetria de bateria.
- Compilar e conferir modpost/ELF/ABI contra o bundle existente em novo diretórioM; transferir somente código público à VM, preservar Image/perfis/módulos selecionados. Esse observador poderá ser transferido via SSH no mesmo boot. CIe645715 passou37096238436/37096242452; o bloqueio físico segue sendo a ausência do iPhone no USB sem resposta de reconexão.
- Gates: observador compilou Werror/modpost e checkpatch 0 erros/0 avisos (96 linhas). ELF64 little-endian relocatable AArch64/vermagic exato e SHA a243e094265871ec6bd5bc4743029e06aaed9d9925262f99ac29a8c891b6f4fa, 9240 bytes, conferidos na VM e no Mac. Fonte baseline sem diff; bundle checker passou; Image/config mantiveram SHA publicados. Sem carga do módulo no aparelho.
- USB reapareceu durante a build: iPhone8,1/iOS15.8.8, bateria100%, chargingfalse/externaltrue/fullychargedtrue. Não é baseline imediatamente anterior ao boot ou prova de carga Linux. Pergunta de disponibilidade física atualizada, sem iniciar monitor antes da resposta.

### Incremento 56 — primeiro link PCIe do bundle e GPIO2 no mesmo boot

- Cinco arquivos documentais: evidência física agregada, evidência do observador,
  runbooks LINK/HDQ e plano. Um DFU manual; kernel7.2.0-iphone6s-dart-serdev1,
  restore44 entradas/Bash/HTTP passaram. REG_ON80→81→80/readbacks/owner e
  pending0. Linkerror0/port88=5/12 leituras; endpoint43a314e4, bus-master limpo.
  Reset/readback/domínios/unload passaram; sem hostPCI/DMA/firmware/rádio.
- GPIO2 cache/hardware/hardware/cache=00072220, máscara270→220, sem escrita ou
  aquisição. Todos os módulos ausentes e serviços respondendo ao fim. Snapshot,
  sync e retorno softwareiOS passaram; percentual100→100 não comprova carga.
- CI7735a1e passou37097188096/37097190542; execução do coletor e observador
  terminouexit0. Reutilizar gates de código inalterado e verificar o delta
  documental. Manter#9/#2/#34 abertos: hostPCI/BAR/IRQ/DART, firmware/scan e
  UART/SN2400/gauge permanecem pendentes.
- DecisãoD3: preparar contratos/host/driver e compilações offline; próximoDFU
  somente para uma candidata que reúna novos gates de hardware. Porquê:
  operador pediu mínimo de desbloqueios/reboots; link já tem prova suficiente.
  Alternativa: repetir diagnóstico idêntico não acrescenta informação. Reverter
  baixo, mantendo módulos externos/perfis separados e rollback. Em curso.

### Incremento 57 — inventário de configuração PCI sem I/O de escrita

- Cinco arquivos no máximo: header de leitura, harnessC, unittestPython, runner
  de mutações e plano. PCI-ID medido43a314e4; ler revisão/class/header, seis
  BARs brutos, subsystem, linha/pinoIRQ e lista convencional de capacidades.
  Exigir headerendpoint, identidade estável e COMMAND sembus-master antes/depois;
  offsets/alinhamento/lista semciclos e orçamento limitado. Não sondar tamanho
  deBAR comFFFFFFFF, tocar MMIO deBAR, habilitarMSI/DMA ou escolherfirmware.
- Saída somente quando todas as leituras/gates passarem; injeção de erro em
  cada leitura, ciclos/offsets inválidos, listas duplicadas e mudanças tardias
  precisam recusar sem alterar resultado. CompilarMac/ARM64 e headerkernel
  Werror offline. Integração modular e coleta física ficam na fatia seguinte;
  nenhumDFU adicional para esta implementação.

- Gate57: harnessMac/ARM64 passou; dez mutações morreram por SIGABRT/asserção
  em ambos. Uma mutação inicial revelou falta de teste de recusa imediata:
  o teste aceitava recusa tardia de bus-master; acrescentada contagem2 antes
  de qualquer outra leitura. Reexecução deu dezkills reais. Header compilou
  Werror/modpost contraABIbundle, Image/config conservaram os hashes fixados.
  Lint inicialmente apontou dois alinhamentos; correção somente de espaços,
  com novo gate de compilação/lint. Nenhuma execução no telefone nesta fatia.

### Incremento 58 — adapter opt-in do inventário e CI contínuo

- Até cinco arquivos: diagnósticoC, CI, runbookLINK, evidência selecionada de
  build e plano. config_inventory=1 somente comenumerate=1/run=1; apóslink
  válido, gateport88 fresco antes de cada leitura de configuração. SemESCRITA
  deconfig/BAR, sizing, MSIenable ouMMIOdoendpoint. CleanupPCIe existente
  sempre executado depois do inventário; falha não publica campos parciais.
- Default permanecefalse; Image/perfis/módulos já selecionados preservados.
  Compilar módulo externo novo contraexportsbundlereais e conferirELF/ABI/SHA.
  Registrar match4350 paraPCI-ID43a3 nafontefixada, seminferirrevisão/gauge
  ouescolherfirmware. CI recebeasdezmutações. Coleta desseadapter aguardará
  candidata queagrupe maisgates; nenhumDFUouPINsolicitadonestafatia.

- Gate58: móduloexterno passouWerror/modpost, ELF64LE/REL/AArch64/vermagicbundle,
  25216bytes/SHAbc960499519542d2016ed69726f8005660362cf3009f8785cfcbc97720f597e5.
  Mac conferiuhash/ELF/ABI; collector --check confirma perfil antigo intacto.
  Header e deltaadapter: checkpatch0erros/0warnings/0checks. MatchBCM4350
  confirmado viafonte eSHAfixados, seminferirchiprev. Imagem/config preservados.
  Ainda semtransferência oucarga física; próximo gate écoletores/host/DART e
  preparar candidata agregada, não repetirDFU para esta entregaoffline.

### Incremento 59 — configuração ECAM para o futuro host PCI

- Até cinco arquivos: contrato de leitura ECAM, harness C, unittest Python,
  runner de mutações e plano. Preservar a topologia física: porta raiz em
  bus0/devfn08 (offset8000), endpoint bus1/devfn00 (offset100000), observados
  no diagnóstico. Não criar alias de slot0 para a raiz, habilitar outras portas
  ou percorrer funções desconhecidas. Aperture exata16MiB já qualificada.
- Ler1/2/4bytes alinhados dentro dos4KiB da função; callback recebe apenas
  DWORD alinhado. Extrair bytes/words sem shifts inválidos e publicar saída
  somente após sucesso. Matriz debus/devfn/tamanhos e offsets, falhas do
  callback e mutações devem recusar sem I/O ou saída alterada. Sem escrita,
  scan/registro dehost, sizingBAR, IRQ/DART oufirmware. CompilarMac/ARM64 e
  objeto kernel contra o bundle; não alterar Image/perfis ou solicitarDFU.

- Gate59: harness passou no Mac e ARM64, matriz de 512 coordenadasbus/devfn
  e todos os offsets1/2/4bytes (inclusive recusas) em ambas as funções; nove
  mutações morreram por SIGABRT/asserção em ambos. UBSan no Mac passou sem
  comportamento indefinido. Header compilouWerror/modpost no bundle e
  checkpatch0erros/0warnings/0checks. A API não registra PCIhost ou aplica
  topologia/DART/IRQ; não houve I/O físico ou reinicialização nesta fatia.

### Incremento 60 — CI do ECAM e referência das janelas do host

- Quatro arquivos: CI, guiaLINK, evidênciaECAM e plano. Registrar os gates da
  fase59 e adicionar as nove mutações à matriz Linux/macOS. Correlacionar
  somente ranges/mapper/IRQ entre a captura Pongo já fixada e ADT oficial
  decodificado/hash fixado; sem coleta nova. Publicar janela de verificação
  poroffset/SHA e campos de hardware selecionados, não dumps ou artefatos.
- Duas janelas packedLE32/64/64/64, byte a byte iguais nos dois insumos.
  Uma interpretação inicial como high/low de célulasFDT foi recusada por
  valores incoerentes; corrigida antes de qualquer escritura. Parent PCI
  address-cells3/size-cells2, mapperreg0 e DARTIRQ248 conferidos nas duas
  referências. LinuxRID/SID, BARs, IRQ, DMA e host continuam sem qualificação
  física. CI2f07194 passou37123788259; fonte/kernel/perfis preservados.

### Incremento 61 — coletor explícito do inventário e candidata privada

- Até cinco arquivos públicos: coletor `scripts/host/n71-link-session.py`,
  testes e mutações correspondentes, guia `docs/N71_LINK_EXPERIMENT.md` e plano.
  Acrescentar modo `--config-inventory` que exige o módulo novo registrado e
  mantém os gates de perfil, ABI, REG_ON, reset e restauração existentes.
- Validar resultado único, seis BARs ordenados, identidade PCI observada,
  COMMAND sem bus-master e limites de leituras/capacidades antes de publicar
  inventário privado. Falhas de parsing também precisam passar pelo cleanup.
  O modo padrão conserva os artefatos anteriores.
- Verificação: testes de contrato, injeção de resultados incompletos e mutações
  reais; gate local dos dois perfis. Compor uma candidata privada com o módulo
  novo, sem trocar Image, initramfs, DTB ou perfil padrão. Nenhum DFU nessa fase.
- Decisão D4: continuar com preparação e builds offline; pedir intervenção
  física somente quando a próxima candidata reunir inventário e novos gates
  úteis. Alternativa: boot isolado só para o inventário aumentaria o trabalho
  manual. Reversão baixa, por seleção explícita de perfil/módulo. Em curso.

- Gate61: 14 testes passaram e as 12 mutações foram recusadas por asserção.
  A primeira execução do runner revelou que o teste de manifesto buscava os
  dados junto da cópia temporária; fixado o caminho da fixture, preservando a
  função sob teste. Os gates locais dos perfis antigo e novo passaram. Payload,
  initramfs e identidades permanecem idênticos; nenhuma ação no iPhone.

### Incremento 62 — driver Wi-Fi PCIe como conjunto externo reproduzível

- Até cinco arquivos: builder Python em `scripts/build/`, seu teste, runner
  de mutações, evidência selecionada de build e este plano. Auditar na fonte
  fixada todos os usos das opções PCIe/MSGBUF; recusar uso fora do pacote
  brcmfmac ou divergência da configuração/Image/exports do bundle.
- Copiar rfkill, cfg80211 e brcm80211 para saída exclusiva da VM ARM64;
  compilar nessa ordem com Werror e modpost fatal, transmitindo exports das
  dependências. Habilitar PCIe/MSGBUF somente no Kbuild e nas unidades do
  pacote Broadcom copiado, mantendo SDIO e a configuração do kernel.
- Exigir ELF AArch64/ABI exata, alias PCI 14e4:43a3, dependências resolvidas e
  transporte PCIe/MSGBUF realmente ligado. Recalcular hashes no Mac; conferir
  fonte, Image e configuração ao fim. Não instalar ou carregar módulos.
- Verificação: recusas de configuração/escopo e mutações em cópias descartáveis,
  build nativa real na VM e gates de artefatos. Sem nova instalação no macOS,
  sem DFU. Firmware, host PCI, BAR/IRQ e DMA continuam gates físicos futuros.
- Decisão D5: módulos externos do mesmo bundle, pois os dois símbolos novos
  aparecem apenas nos headers internos do brcmfmac e em seu Makefile/Kconfig.
  Alternativa: novo Image exigiria mais armazenamento e reinicialização sem
  necessidade para esta compilação. Reversão baixa: artefatos ficam privados
  e não são selecionados automaticamente. Em curso, sujeita ao modpost real.

- Gate62: receita nativa terminou exit0; oito módulos passaram Werror/modpost,
  ELF/ABI e dependências completas. PCIe/MSGBUF têm símbolos T ligados e alias
  14e4:43a3/classe02:80. Hashes/ELF/ABI recalculados no Mac; fonte, Image,
  configuração e exports conservaram os hashes fixados. Sem instalação/carga.
- Oito testes e 13 mutações passaram em Mac e ARM64. A primeira build recusou
  o alias esperado amplo demais; confirmado o filtro de classe upstream e
  corrigido o gate, sem mudar a tabela. A primeira rodada ARM de mutações
  revelou que um diretório de fixture criado com umask002 escondia a mutação
  de escopo; fixado modo700 e repetidos os gates, todos por asserção.
- Coletor61: CI push37145008066 e PR37145010530 passaram. Não há type checker
  Python configurado; AST passou. Os gates de lint do novo builder entram no
  CI da próxima fatia documental; não representar esta compilação como Wi-Fi.

### Incremento 63 — reprodução, estado atual e CI dos módulos Wi-Fi

- Cinco arquivos: novo guia `docs/N71_WIFI_MODULES.md`, referências em LINK
  e KERNEL_BUNDLE, CI e plano. Documentar a receita real, dependências/ABI,
  artefatos privados e gates ainda necessários ao hardware. Corrigir os
  resumos antigos que ainda diziam não existir perfil ou boot do bundle,
  preservando o escopo histórico das provas anteriores.
- Acrescentar as 13 mutações à matriz Linux/macOS. Reutilizar as provas nativas
  de build e os testes que não mudaram; validar diff/árvore pública e CI final.
  Atualizar issues9/12 com links e escopo, sem criar pendências duplicadas.
- Não pedir DFU nesta fatia. A candidata do inventário e os drivers externos
  ficam preparados; host PCI, BAR/IRQ e DART seguem o próximo desenvolvimento.

### Incremento 64 — contrato de escrita para varredura pelo núcleo PCI

- Cinco arquivos: `phone/kernel/n71-pcie-scan-config.h`, teste C, wrapper
  Python, mutações e plano. Capturar IDs, classes, COMMAND, BARs, ROM e
  bridge-control dos dois dispositivos; exigir bus0/1, DMA desativado e ROM
  desativada antes de qualquer escrita. Falha de captura não altera a saída.
- Autorizar somente suspensão/restauração de decode, sizing/restauração dos
  BARs/ROM com decode suspenso e o bit MASTER_ABORT do bridge-control.
  Escritas iguais ao valor atual ficam sem I/O; outras mudanças, inclusive
  bus-master, status W1C e reconfiguração de barramento, são recusadas e
  registradas. Aplicar limite de tentativas e falha persistente.
- Remover o barramento antes da restauração final; restauração independe da
  falha persistente e verifica cada valor por readback, com COMMAND por
  escrita de 16 bits para preservar STATUS. Testar falhas em cada etapa,
  recusas e mutações reais, sem acesso ao aparelho.
- Decisão D6: usar `pci_scan_root_bus_bridge`, sem `pci_bus_add_devices` ou
  atribuição de recursos, no próximo incremento. A fonte fixada impede bind
  antes de PCI_DEV_ALLOW_BINDING; a varredura publica dispositivos temporários
  em sysfs e pode tentar alterações adicionais, por isso precisa do contrato
  e de cleanup. Alternativa: sizing próprio não exercitaria a integração do
  host PCI. Reversão baixa: parâmetro explícito, perfil privado separado.

- Gate64: harness C compilado com Wall/Wextra/Werror/pedantic passou no Mac;
  14 mutações morreram por SIGABRT/asserção. Injeção cobre todas as leituras
  de captura e escritas de restauração. A mutação de bus-master inicialmente
  sobreviveu por recusa redundante; acrescentado o caso de valor perigoso
  igual ao atual, que comprova a recusa antes da emulação de no-op. Não houve
  I/O no aparelho. Prova ARM64 será agrupada com a compilação do adaptador.

### Incremento 65 — adaptador real de host PCI para sizing temporário

- Até cinco arquivos: `phone/kernel/n71-pcie-scan.h`, integração no módulo
  diagnóstico, testes C/Python de integração e plano. Criar
  bridge privado com callbacks ECAM fixados, janelas ADT traduzidas e faixa
  bus0..1; recusar dispositivos/classe/cabos ABI divergentes no preflight.
- Parâmetro `host_scan` exige run/enumerate/config_inventory. Executar somente
  `pci_scan_root_bus_bridge` sob o lock de rescan; não habilitar bind, DMA,
  MSI, MMIO dos BARs ou atribuição de recursos. Auditar a fonte PCI fixada e
  manter todas as escritas adicionais atrás do contrato do incremento64.
- Reportar os dois dispositivos, recursos BAR do endpoint, COMMAND e
  refusals. Sempre stop/remove/free do bridge, depois restauração de config
  com readback, antes de PERST/power/REG_ON. Erro de varredura continua sendo
  erro mesmo que o núcleo PCI retorne sucesso. Compilar módulo externo na VM
  preservando configuração/Image/exports; não alterar o perfil padrão.
- Após os gates, compor e selecionar explicitamente uma candidata privada
  para uma sessão física agregada. Não afirmar BAR/host/DART/radio funcionais
  com base somente na compilação. Não solicitar DFU enquanto houver trabalho
  independente útil para preparar esta candidata.

- Gate65: três testes passam no Mac e ARM64, incluindo 11 cenários do
  adaptador e seis mutações de lifecycle por asserção. Detectados e corrigidos
  a sobrescrita do primeiro erro de leitura e o orçamento que poderia impedir
  o readback no cleanup. Mutações de política64 continuam14/14.
- O primeiro build do kernel detectou colisão do identificador `current` com
  macro ARM64; renomeado para `observed` em fatia corretiva de dois arquivos,
  sem alterar a política. Novo diretório M compilou Werror/modpost fatal,
  módulo AArch64/ABI exata35072 bytes, SHA1fe1b308…d38f002. Símbolos PCI scan,
  walk, stop, remove e free estão ligados; enable/bind/DMA ausentes. Hash,
  ELF e vermagic recalculados no Mac. Fonte/Image/config/exports preservados.
- As provas são de software e build: adaptador ainda não foi carregado no
  telefone. Seleção explícita no coletor e registro reproduzível continuam
  no próximo incremento, sem necessidade de recompilar o Image ou pedir PIN.

### Incremento 66 — seleção e cleanup físicos do adaptador de sizing

- Cinco arquivos: coletor, testes do coletor, parser de scan, evidência
  selecionada de build e plano. `--host-scan` implica inventário e fixa o
  módulo novo/proveniência; modos anteriores mantêm os hashes selecionados.
- Validar resultado único, dois dispositivos, seis recursos BAR ordenados,
  COMMAND sem DMA, orçamento e ausência de refusals. Exigir remoção do bus e
  restauração de config antes de permitir unload; confirmar sysfs PCI vazio.
  Resultado falho também passa por cleanup REG_ON/reset/power já existente.
- Compor perfil privado idêntico ao payload/DTB/initramfs/identidades físicos,
  somente trocando o módulo externo. Verificar CLI local dos três modos e
  recusas/cleanup dos testes; CI e mutações entram na fatia documental seguinte.
- A próxima sessão agrupa inventário, sizing pelo PCI core, DART/HDQ somente
  leitura, serviços e snapshot. Firmware/calibração, atribuição de recursos,
  IRQ e DMA não são ativados nesta varredura temporária.

- Gate66: 17 testes do coletor passaram; 12 mutações anteriores continuam
  recusadas por asserção. Fixture nova recebeu ROOT explícito para funcionar
  nas cópias descartáveis; runner teve ajuste de anchor em fatia de um arquivo.
  Os três modos passaram seus gates locais. Perfil novo preservou payload,
  DTB, initramfs e identidades byte a byte; somente módulo externo mudou.
  Nenhuma ação USB/DFU. Logs e artefatos privados, registro público só hashes.

### Incremento 67 — reprodução e gates contínuos do host temporário

- Até cinco arquivos: guia LINK, CI, teste/mutações do parser de scan e plano.
  Registrar receita de módulo externo, hash/ABI e limites reais de prova;
  manter o Image anterior e modos padrão. Acrescentar as mutações de política
  à matriz Linux/macOS e recusas de cleanup/topologia/BAR do parser.
- Publicar no branch autorizado, conferir CI e atualizar #9/#34 com os fatos
  selecionados. Depois iniciar um único boot para os novos gates físicos,
  sem contador ou novo PIN; confirmar DFU USB antes de enviar a candidata.

- Gate67 local: seis testes de aceitação de resultados e oito mutações por
  asserção passaram. CI recebe também as14 mutações de política; as seis de
  lifecycle fazem parte da suíte de testes. Recipe e prova nativa são públicas;
  binários, payload, chaves e logs continuam privados. Não há type checker
  Python configurado; validar AST/lint no CI e conferir a árvore pública.

### Incremento 68 — sizing direto após a recusa física do PCI core

- Inventário físico comprovou 14e4:43a3, revisão PCI8, BAR0/2 de64 bits.
  O scan recusou a primeira alteração COMMAND/INTx(0→400); houve dois
  dispositivos temporários, sem bind. Remoção, restauração/readback e unload
  passaram. Não houve sizing aceito; SSH/HTTP continuam e snapshot foi salvo.
- Decisão: medir somente BARs do endpoint via contrato já validado. O PCI
  core também tenta IRQ, bridge windows, PM e AER; não ampliar a whitelist
  para satisfazer essas tentativas sem qualificação. Alternativa: auditar e
  restaurar cada alteração do core antes de repetir a integração completa.
  Reversão baixa: modos separados e sem alterar o Image. Status: em curso.
- Até cinco arquivos por fatia. Header puro, harness C, wrapper com mutações,
  este plano e evidência física selecionada. Suspender decode, medir seis
  palavras BAR, validar pares64/máscaras/tamanhos, restaurar toda a captura
  com readback inclusive em erro. Publicar resultado só após restore aprovado.
- Próximas fatias: integração externa/build Werror; seleção e continuidade
  explícita após cleanup privado verificado, sem limpar dmesg ou reutilizar
  registros históricos como sucesso. Carregar módulo no mesmo boot por SSH.
  Continuar sem DMA, BAR MMIO, firmware ou rádio. Não pedir DFU adicional.

- Gate68: harness C passou no Mac com Wall/Wextra/Werror/pedantic; seis
  mutações compiladas falharam por asserção, incluindo erro de restore e
  publicação prematura. Falhas são injetadas em todas as leituras/escritas
  do caminho completo; tamanhos32/64 e palavras superiores são verificados.

### Incremento 69 — integração do sizing no módulo externo

- Até cinco arquivos: adaptador, módulo, registro selecionado de build,
  guia LINK e plano. Modo explícito bar_sizing exige inventário e exclui
  host_scan. Reusar ECAM com link fresco e limite de leituras; medir somente
  endpoint sem registrar bus. Reportar máscaras/tamanhos e restore separado.
- Compilar em novo diretório M na VM dedicada, executar harness ARM64 com
  mutações, verificar ELF/vermagic/modpost e preservar Image/config/exports.
  Compor perfil privado com os mesmos payload/DTB/initramfs e identidades.

- Gate69: módulo37824 bytes SHA11be3fc8…73ae38 compilou ARM64/Werror/modpost
  em M novo; ELF/vermagic/hash recalculados no Mac. Harness e seis mutações
  passaram também na VM. Image/config/exports e fonte do bundle preservados.
  Os dois testes anteriores do adaptador continuam passando (seis mutações).
  Guia distingue inventário físico aprovado, scan recusado e sizing ainda
  não carregado. O telefone continua acessível sem nova intervenção física.

### Incremento 70 — continuar no mesmo boot após cleanup comprovado

- Cinco arquivos: contrato de histórico privado, testes, coletor, testes do
  coletor e plano. `--previous-clean` é opt-in, exige diretório próprio privado,
  resultado com cleanup sem erros e logs finais positivos. Conferir todas as
  linhas N71 com timestamp do kernel, na mesma ordem, contra dmesg fresco.
  Se disponível, boot_id também deve coincidir; a primeira prova anterior não
  o possui e não receberá valor retroativo inventado.
- Recusar histórico faltante, truncado ou diferente, módulo carregado, PCI
  ocupado e HDQ ativo. Manter logs completos privados; filtrar somente linhas
  históricas exatas na interpretação dos resultados seguintes. Não limpar dmesg.
  Transferir módulos a diretório novo/exclusivo em /run, sem sobrescrever o
  módulo antigo. Gates de hash/ABI e REG_ON fresco permanecem obrigatórios.

- Gate70: 24 testes passaram (cinco do histórico,19 do coletor), quatro
  mutações de histórico falharam por asserção e12 mutações do coletor passaram.
  A leitura física confirmou as108 linhas históricas exatas e módulos/PCI
  ausentes, sem qualquer escrita de hardware ou novo boot. Logs históricos
  continuam privados e intactos; ainda não foi repetido o experimento.

### Incremento 71 — seleção e validação da medição física de BARs

- Cinco arquivos: parser de sizing, testes, coletor, testes e plano. Selecionar
  `--bar-sizing` com registro público exato; modo implica inventário e exclui
  host_scan. Validar seis linhas únicas, máscaras/atributos/pares64 e tamanhos
  recalculados, não somente texto de sucesso. Exigir restore/readback antes
  do unload e PCI sysfs vazio. Testar erros e mutações de aceitação/cleanup.
- Compor perfil privado com módulo novo e kernel/identidades preservados.
  Executar continuação física explícita com prova70, mantendo o mesmo boot.
  Guardar logs/resultados, verificar SSH/HTTP e snapshot após o cleanup.

- Gate71: 24 testes passaram (quatro do parser com quatro mutações por
  asserção,20 do coletor); perfil/hash/ABI e histórico passaram localmente.
  A continuação física no mesmo boot passou:66 leituras,13 pedidos,10 escritas
  de probe, zero refusals; BAR0=32KiB, BAR2=4MiB, superiores não são recursos
  separados. Config/REG_ON/reset/power/unload e PCI vazio comprovados. Não
  habilitou MMIO de BAR, DMA, DART ou rádio e não pediu outro DFU.

### Incremento 72 — documentação e CI da continuação física

- Até cinco arquivos: evidência selecionada física, guia LINK e plano.
  Registrar sizing real, cleanup, SSH/HTTP e snapshot, sem boot_id, chaves,
  firmware ou logs brutos. Incluir receita --previous-clean e diferença entre
  sizing e acesso MMIO. Publicar no branch autorizado e acompanhar CI.
- Atualizar #9/#34 com avanço e pendências; não encerrar Wi-Fi/DMA/gauge.
  Preparar o contrato de roteamento/MMIO e chip-ID sem pedir outro DFU.

### Incremento 73 — leitura limitada de chip-ID pelo BAR0

- Até cinco arquivos: contrato puro, harness C, wrapper/mutações, registro
  de referência selecionada e plano. A fonte brcmfmac fixada usa BAR0_WINDOW80
  e offset0 de18000000 para chip-ID; pci_enable_device/set_master do driver
  completo impede usá-lo só como identificador antes da qualificação DMA.
- Decisão: rota temporária somente BAR0, PCIc0000000→CPU7c0000000 da ADT
  oficial já correlacionada. Exigir sizing fresco32KiB, identidade/classe,
  decode/master inicialmente limpos, BAR0/upper4/0. Capturar também a janela
  root20 e BAR0_WINDOW80. Preservar IRQ/PM/ROM/BAR2 e não tocar core resets/OTP.
- Escrever valores fixos com readback: BAR0c0000004/high0, bridge memory
  c000c000(1MiB) e chip-window18000000; somente MEM-enable nos dois COMMAND.
  Revalidar COMMAND antes de uma leitura32 de chip-ID. Nunca bus-master.
  Desabilitar decode e restaurar janelas/BARs/config com readback em todo erro;
  falha de restore deixa decode desligado e impede publicação/unload.
- Inferência a testar: a janela CPU fornecida pelo ADT roteia a transação
  após config PCI. Tamanho confirmado não prova esse roteamento. Mapear e
  reivindicar somente32KiB com APIs kernel, recusar região ocupada. Próximas
  fatias: adaptador/build e coletor/prova física no mesmo boot, após gates.
  Alternativa: finalizar o host/DART/IRQ primeiro; ampliaria o experimento.
  Reversão baixa: opt-in separado, valores restaurados, Image preservado.

- Gate73: harness C Mac/Werror passou com falhas em todas as leituras e
  escritas, saída intacta em erro, uma única leitura de ID e config restaurada.
  Seis mutações compiladas falharam por asserção (rota, DMA, janela, restore,
  revisão, publicação). Fonte e constantes foram conferidas no commit fixado.
  Ainda não há acesso MMIO físico. CI do head8865ea1 passou testes/lint mas
  falhou numa âncora antiga de seleção do coletor; corrigir em fatia própria.

- Correção CI: runner passou a localizar a seleção com bar_sizing;12 mutações
  foram executadas de novo e falharam por asserção. Sem mudança executável do
  coletor/hardware. A CI remota permanece obrigatória no próximo head.

### Incremento 74 — adaptador e build da leitura MMIO limitada

- Cinco arquivos: header de adaptação MMIO, coletor BAR do módulo, integração
  do parâmetro chip_id, registro de build e plano. Reivindicar32KiB de
  7c0000000 via request_mem_region e mapear somente após sizing fresco.
  Ler no máximo um dword em offset0, com predicate88 fresco e sem DMA.
  Restaurar config antes de iounmap/release; emitir prova de cleanup mesmo
  em falha de map/probe. Modo chip_id exclui host_scan/bar_sizing simultâneos.
- Build externo em novo M da VM, harness C/mutações ARM64, modpost/Werror,
  hash/ELF/ABI e Image/config/exports preservados. Firmware e BAR2 MMIO não
  entram no experimento. Não selecionar binário sem proveniência e coletor.

- Gate74: harness e seis mutações também passaram ARM64; módulo42008 bytes,
  SHA8ade6fd8…b717941, compilou Werror/modpost com kernel preservado. ELF,
  ABI e SHA recalculados no Mac. Testes anteriores do adaptador PCI passaram
  após a assinatura BAR receber saída opcional. Ainda não carregou o módulo.

### Incremento 75 — seleção e prova da identificação interna

- Cinco arquivos: parser CHIP, testes, coletor, testes e plano. `--chip-id`
  implica inventário e sizing fresco, escolhe hash separado e exclui outros
  modos. Uma linha de ID, chip4350/tipoAXI, revisão calculada do raw, uma
  leitura MMIO e restore de config/route/map precisam concordar.
- Cleanup conservador: qualquer leitura de config exige restore positivo;
  falha antes da captura pode impedir unload até análise mesmo sem escrita.
  Isso evita presumir ausência de mudanças a partir de contagens incompletas.
- Compor perfil privado preservando Image/payload/identidades; conferir gates
  locais. Executar uma continuação explícita após a prova71 e confirmar
  serviços/snapshot. Não iniciar driver completo, DMA ou firmware.

- Gate75: 25 testes passaram (quatro do parser com quatro mutações por
  asserção,21 do coletor). No mesmo boot, identificação física passou:
  raw17084350, BCM4350 revisão interna8, uma leitura MMIO e53 de config.
  Sizing fresco também passou. Route/window/config readback, unmap/release,
  reset/power/REG_ON/unload e PCI vazio passaram; SSH/HTTP preservados.
  Sem DMA/firmware/rádio e sem intervenção/DFU/PIN adicional.

### Incremento 76 — evidência física e continuidade dos gates

- Até cinco arquivos: guia LINK, evidência física CHIP, runner de mutações e
  plano. Registrar chip/revisão real, sizing, cleanup e limites sem publicar
  boot_id/logs/firmware. Tornar âncora da mutação de seleção independente do
  número de modos, verificar12 mortes por asserção e publicar no branch.
- Conferir CI e atualizar #9/#34. Próximas dependências: associação de
  SID/porta1/DART, IRQ/MSI e firmware/calibração adequados ao4350/rev8;
  identificar essas referências sem habilitar DMA prematuramente.

- Gate76: snapshot posterior concluído;12 mutações do coletor passaram com
  âncora estável de substituição do módulo. Evidência pública distingue
  chip-ID e sizing físicos de rádio/DMA ainda ausentes. Arquivos privados
  e histórico preservados; branch segue sem merge/main/release.

### Incremento 77 — contrato de observação do DART separado

- Até quatro arquivos: plano, contrato puro, teste C e executor de testes.
  Coletar duas amostras dos19 registros S5L documentados (COMMAND,TCR,ERROR,
  16TTBRs). Sem callback de escrita; publicar somente após igualdade das
  amostras, COMMAND não ocupado e endpoint quieto antes de cada leitura.
- Decisão: o DART é602008000, separado da NVMMU602004000 do recursoPCI4.
  O resumo anterior confundia esses blocos; código/ADT/referência Apple
  concordam que não são intercambiáveis. Não mapear o recurso4 como DART.
  Alternativa: ativar imediatamente o provider; descartada porque probe/remove
  resetam TCR/TTBR e limpam ERROR, antes de conhecer estado/posse/SID.
- Verificar leitura/falha em cada posição, instabilidade, busy/all-ones e
  gates do endpoint. Compilar original e seis mutantes; exigir falha por
  asserção. Não há firmware, mapeamento DMA, interrupção nova ou reboot.

- Gate77: contrato compilou no Mac com C11/Werror/pedantic; falhas em38
  leituras e39 gates,19 instabilidades,19 all-ones e busy recusadas sem saída.
  Seis mutantes compilados morreram por asserção; diff-check passou.

### Incremento 78 — adaptador físico DART sem ativar provider

- Até quatro arquivos: plano, adaptador kernel, seleção no diagnóstico e
  evidência de build. Validar nó602008000/4000, compatíveis S8000/S5L,
  IRQ248 level-high, domínio igual ao PCI e status literalmente disabled.
  Recusar device existente/posse do recurso; mapear somente enquanto os quatro
  domínios PCI estão adquiridos. Guardar link/IDs/COMMAND quietos em39 gates.
- `dart_observe=1` exige run/enumerate/inventário e exclui sizing/chip/core.
  Unmap/release antes do cleanup externo já comprovado. Sem alteração DT,
  request_irq, DART reset/invalidate/escrita ou provider novo.
- Build externo na VM dedicada com ABI/exposições/config/Image preservados,
  Werror/modpost fatal e contrato compilado ARM64. Nenhum pacote no Mac.

- Gate78: build externo e seis mutantes ARM64 passaram; módulo48208bytes,
  SHA0a91c840…e486, ABI/ELF/hashes recalculados no Mac. Config/Image/exports
  e quatro blobs do bundle preservados. Não carregado no iPhone nesta etapa.

### Incremento 79 — coleta DART por continuação no mesmo boot

- Cinco arquivos: plano, parser DART/testes, coletor/testes. Selecionar hash
  explícito por `--dart-observe`, sem combinar com sizing/chip/core. Exigir
  fonte602008000/4000, estado estável,38 leituras/39 gates e unmap/release
  únicos. Calcular máscara enable do TCR e validar os limites independentemente.
- Usar prova de cleanup anterior CHIP, conferir mesmo boot/histórico privado,
  transferir módulo em diretório novo e repetir inventário/REG_ON fresco.
  Cleanup exige reset/power/map/PCI vazio/REG_ON/unload positivos. Nenhuma
  nova autenticação, DFU, alteração do DT ou limpeza do dmesg.
- Verificar parser por quatro mutações reais e gates do coletor antes do
  insmod. Registrar resultado físico separado de build; salvar snapshot
  mantendo Linux ligado. TTBRs completos/endereços não são publicados.

- Gate79: quatro testes/parser (quatro mutações por asserção),23 testes do
  coletor e12 mutações do coletor passaram. Build/perfil/histórico privado
  validaram seleção antes do insmod. Coleta física no mesmo boot passou:
  COMMAND00000f02,TCR0,ERROR00000100, enable0/4,16/16TTBRs válidos. Duas
  amostras idênticas,38 leituras/39 gates; fonte separada/posse/status
  confirmados. Unmap/release/reset/power/PCI vazio/REG_ON/unload passaram.
  SSH e HTTP `/cgi-bin/status` preservados; nenhum DFU/PIN adicional.
- Não presumir tabelas vazias pelo TCR0: os16TTBRs continuam válidos e
  desconhecidos. Antes de ativar provider, qualificar SID/IRQ e conservar
  estado completo. A família upstream para4350/rev8 é4350-pcie (revisão8
  pertence à máscaraFFFFFF00), sem prova de firmware/calibração compatível.

### Incremento 80 — documentar DART físico e seleção correta de firmware

- Cinco arquivos: plano, LINK, WIFI, evidência física DART e seleção upstream
  por revisão. Preservar logs/boot_id/tabelas/identidades privadamente; publicar
  valores de controle/máscaras/contagens e hashes, distinguindo fontes/builds
  de recursos físicos ainda ausentes. Snapshot posterior passou.
- Registrar que4350/rev8 seleciona `brcmfmac4350-pcie`, não o ramo4350c2
  destinado a revisões0–7. Isso identifica família de nomes; compatibilidade
  Apple/calibração não foi comprovada. Não obter firmware antes desses gates.
- CI novo deve incluir lint/testes Mac/Linux/Windows, sem instalar lint no
  Mac. Não há typechecker configurado; C/Werror e parsers compilados/testados.
  Atualizar #9/#34 com provas e próximos passos; continuar análise SID/IRQ
  no mesmo boot, preservando tabelas válidas antes de ativar um provider.

- Gate80: CI push37217289672 e PR37217292953 concluídos com sucesso no
  commit228582a; lint/testes Linux/macOS/Windows preservados. Não há
  typechecker separado configurado; builds C/ARM64 e parsers são os gates.

### Incremento 81 — conservar os 16 TTBRs estáveis antes de ativar DART

- Quatro arquivos: plano, contrato puro, teste C e executor de mutações.
  A observação atual publica somente valid-bits. Preservar todas as palavras
  no resultado atômico, sem aumentar38 leituras/39 gates nem expor escrita.
- O teste exige conteúdo/ordem integral, inclusive palavras sem valid-bit;
  cada falha conserva a saída sentinela. Acrescentar mutante de truncamento
  do ponteiro; compilação C11/Werror e morte por asserção obrigatórias.
- Decisão: capturar antes do provider, pois probe/remove zeram as tabelas.
  SID0 é qualificado pela cadeia ADT WLAN→mapper84/reg0 e pelo método
  IODARTMapper::_registerMapper que passa reg como SID. DMA físico/IRQ
  continuam pendentes; vm-offset Apple é par u32, não endereço FDT u64.
  Alternativa: ativação imediata; descartada por perder estado não conservado.

- Gate81: C11/Werror e sete mutantes compilados passaram; cada mutante morreu
  por asserção.38 leituras/39 gates preservados; saída integral atômica nos
  cenários de falha. SSH/HTTP confirmados novamente no endereço USB; o HTTP
  não está vinculado a127.0.0.1, portanto essa sondagem inicial foi corrigida.

### Incremento 82 — captura privada integral e resumo público sanitizado

- Cinco arquivos: plano, adaptador MMIO, parser/testes e coletor. Emitir16
  palavras estáveis sem leituras novas. Guardar os registros somente nos
  logs privados; retirar ponteiros da saída do terminal e do JSON sanitizado.
- Parser exige índices0–15 únicos/ordenados, palavras não all-ones e máscara
  valid consistente. Retorna contagem e SHA256 das16 palavras little-endian,
  nunca seus endereços. Recusar ausência/duplicação/reordenação/truncamento.
- O módulo atual e evidência histórica continuam intactos; após gates locais,
  compilar nova seleção ABI na VM e aplicar por SSH com histórico de cleanup.
  Provider/IRQ/DMA continuam desligados; nenhuma reinicialização requerida.

- Gate82: cinco testes do parser passaram, com seis mutações de aceitação
  rejeitadas por asserção;23 testes do coletor passaram. A primeira mutação
  de índice usava ausência total e ainda era barrada pela máscara; corrigida
  para duplicação de índice com máscara íntegra, comprovando o gate próprio.
  Falhas do experimento continuam exigindo release; logs retêm palavras,
  saída pública omite-as. Diff-check passou; build físico é o próximo gate.

### Incremento 83 — build ARM64 da captura integral, com seleção explícita

- Até quatro arquivos públicos: plano, nova evidência de build, seletor do
  coletor e teste do isolamento dos logs. Preservar build/evidência anteriores;
  nova seleção `n71-dart-state-build.json` fixa ABI, hash e fontes completas.
- VM dedicada: arquivo público fixado, inspeção do bundle/hashes antes/depois,
  sete mutantes ARM64, build externo Werror/modpost fatal, ELF e vermagic.
  Sem rebuild de Image/DTB/initramfs; não instalar pacotes no Mac.
- Teste real do capture mantém TTBR no arquivo privado e retira-o do stdout,
  conserva estado do parser e detecta mutação de exposição. Perfil composto
  novo deve manter payload/chaves/pin byte a byte antes de qualquer insmod.

- Gate83: sete mutantes ARM64 e módulo Werror/modpost fatal passaram. Módulo
 48504bytes, SHAaf2663a4…5727; .config/Image/exports/blobs preservados.
  ELF/vermagic/hashes conferidos no Mac; perfil mantém payload/initramfs/chaves
  e pin byte a byte. Gate local/histórico passou;13 mutantes do coletor
  morreram por asserção, incluindo exposição de TTBR. PUBLIC_TREE_OK.

### Incremento 84 — preservar estado físico completo no boot existente

- Até cinco arquivos: plano, evidência física nova, evidência Apple de SID,
  LINK e WIFI. Usar seleção integral com cleanup anterior;38 leituras/39gates
  sob posse dos quatro domínios, quieto antes de toda leitura e sem escrita.
- Confirmar16 palavras privadas/contagem/hash e cleanup/unload/PCI vazio,
  SSH/HTTP e snapshot. SID0/reg e vm-offset par u32 são provas de referência,
  não DMA/IRQ físicos. Não copiar RID2SID de M1 nem tratar NVMMU como DART.
- Após preservação, avançar na enumeração PCI (INTx disable recusado na
  primeira tentativa) e no ciclo reversível do provider; não pedir novo DFU.

- Gate84: captura física integral passou no mesmo boot:16 palavras conservadas
  privadamente, duas amostras estáveis/38 leituras/39 gates. COMMAND00000f02,
  TCR0,ERROR100,16valid; unmap/release/reset/power/REG_ON80/unload/PCI vazio
  passaram; SSH/HTTP e snapshot posterior passaram. SID0 qualificado por
  ADT e método Apple; nenhuma prova DMA/IRQ/rádio ainda. Sem novo DFU/PIN.
- Preparação do perfil tentou copiar HDQ, ausente/não selecionado no perfil
  anterior; arquivo vazio criado somente nesta operação foi removido após
  conferir tamanho/tipo. Os módulos selecionados e identidades passaram o gate.

### Incremento 85 — contrato reversível de teste do provider DART

- Quatro arquivos: plano, contrato puro, teste C e runner. Preservar16TTBRs,
  exigir TCR0 e ausência de fault/busy, iniciar provider somente quieto e
  removê-lo em todo caminho após tentativa. Antes de restaurar, comprovar
  provider removido e tradução desligada; verificar todas as palavras depois.
- Não há attach de endpoint, domínio DMA ou bus-master. Snapshot observa
  COMMAND/ERROR também, mas não escreve registros de comando/W1C; mudanças
  nesses valores são relatadas, sem alegar restauração deles por TTBR.
- Alternativas: mutar status DT e deixar provider ativo; usar platform device
  temporário com nó original/recursos qualificados evita notifier/changeset e
  permite unregister antes do restore. IRQmapping novo só é descartado após
  remover o device; mappings anteriores permanecem. Power PCI fica adquirido.
- Testar start parcial, stop/fault/busy, todas falhas de snapshot/write/gate,
  restore incorreto e saída/publicação; mutantes reais por asserção.

- Gate85: C11/Werror e seis mutantes compilados passaram; todos morreram
  por asserção. Start parcial sempre chama stop e conserva16 palavras; stop
  falho/tradução ativa impede escrita. Falhas nos quatro snapshots,17 gates e
  16 escritas cobertas; erro após escrita efetiva também impede sucesso falso.
  EUCLEAN específico Linux foi substituído por EIO +flag control_changed para
  portabilidade Mac; não altera os registradores tratados no experimento.

### Incremento 86 — platform device temporário com recursos originais

- Três arquivos: plano, adaptador de provider e seleção opt-in no diagnóstico.
  Reutilizar qualificador DART disabled/sem device, capturar antes do probe e
  manter ioremap apenas para observação/restauração. Transferir a posse do
  recurso ao platform device e readquirir depois de unregister.
- Traduzir IRQ pelo domain AIC real; conservar mapping anterior e descartar
  somente mapping criado nesta tentativa, após unregister. Nó original fica
  disabled; não usar changeset, alterar DT global ou registrar endpoint PCI.
- Exigir driver apple-dart e drvdata; sempre retirar device mesmo se probe
  falhar. Quatro snapshots estáveis,152 leituras do observador e16 escritas
  somente de TTBR, após comprovar remoção/tradução desligada. Registrar
  mudanças COMMAND/ERROR sem escrever W1C. DMA/firmware/radio proibidos.

- Gate86: ARM64/Werror/modpost fatal passou; módulo57112bytes,
  SHAe78a3c86…74ea, ELF/vermagic e hashes da imagem preservados. Sete mutantes
  do observer e seis do ciclo passaram na VM. Primeiro build revelou colisão
  com macro kernel `current`; renomeado para `observed`, gates C e build
  repetidos em diretório novo. Falha/log/archive anteriores conservados.
- API platform release confirma of_node_put; IRQ traduzido pelo domain real,
  wrappers/símbolos exportados conferidos. Sem segunda chamada device_attach:
  platform add já executa probe síncrono, evitando repetir probe parcial.
  CI do commit1236c98 passou; provider ainda não carregado no iPhone.

### Incremento 87 — coletor do ciclo com prova prévia integral

- Cinco arquivos: plano, evidência de build, parser/testes e coletor. Seleção
  explícita `--dart-cycle` exclui outros modos e exige histórico do mesmo boot
  com16 palavras conferidas novamente nos logs privados e digest do JSON.
- Sucesso exige provider apple-dart ligado, quatro snapshots estáveis,
  152 leituras/156 gates internos/17 gates extras,16 escritas de restore,
  device/novo IRQmapping retirados e comparação integral restaurada. Nenhuma
  mudança COMMAND/ERROR pode receber sucesso. Parser nunca publica palavras.
- Cleanup negativo exige retirada e restore quando tentou start; gates de
  power/reset/REG_ON/PCI vazio/unload permanecem. Testar evidência incompleta,
  fault/busy/TCR, contagens/índices e estado privado inconsistente.

- Gate87: cinco testes do parser/ciclo passaram, com quatro mutações reais
  rejeitadas por asserção; validação dos logs/digest privados passou.13mutantes
  existentes do coletor passaram; build/ELF/hashes novamente conferidos no Mac.
  PUBLIC_TREE_OK e diff-check passaram. Gate do novo modo será adicionado antes
  do insmod; nenhuma ativação física do provider nesta etapa.

### Incremento 88 — gate do modo e sessão física do provider

- Até quatro arquivos: plano, testes do coletor, runner de mutações e
  evidência física. Exigir seleção diferente do observer, parâmetro exclusivo,
  sucesso sanitizado e recusar falta de restore/remoção/PCI vazio antes de unload.
- Compor perfil privado novo preservando payload/DTB/initramfs/chaves/pin,
  conferir --check com captura integral anterior e repetir teste por SSH no
  mesmo boot. Nenhum endpoint é registrado, nenhum DMA/firmware é habilitado.
- Confirmar provider bound, quatro snapshots/restauração/controle estável,
  recurso/IRQmapping retirados, reset/power/REG_ON/unload/PCI vazio e serviços.
  Salvar snapshot mantendo Linux ligado; publicar somente prova sanitizada.

- Gate88:25 testes do coletor e15 mutações por asserção passaram. Perfil mantém
  payload/initramfs/DTB/identidades; logs/digest integral anterior e --check
  passaram. **Ciclo físico no mesmo boot passou**: provider apple-dart ligado,
  pagesize1000/4streams/AS32→36;152 leituras/156gates internos/17 extras,
  16 escrituras TTBR restauradas, controles iguais e hash integral anterior
  idêntico. Device/IRQmapping novos retirados, recurso/map liberados e
  reset/power/REG_ON80/PCI vazio/unload passaram.
- SSH/HTTP, ausência posterior de device/handler e snapshot passaram.
  Não houve endpoint attach, DMA, firmware, IRQdelivery ou novo DFU/PIN.
  Prova física sanitizada separada do build; goal de Wi-Fi continua pendente.

### Incremento 89 — documentação do ciclo e publicação dos gates

- Até quatro arquivos: plano, LINK, WIFI e registro da próxima decisão PCI.
  Corrigir estado atual para provider fisicamente inicializado/retirado,
  preservando história do observer e limites DMA/IRQ/calibração.
- Documentar seleção/compile/perfil/histórico e ciclo sem alterar DT; publicar
  branch/CI e atualizar #9/#34. Próxima correção é COMMAND INTx-disable
  rejeitado pelo guard no core scan; permissões continuam delimitadas ao
  bit10, sem BAR assignment/IRQrouting/bus-master ou caps não qualificadas.

- Gate89: documentação registra ciclo físico e limites, incluindo operações
  do provider fora das contagens do observador. Histórico/identidades privados
  preservados; publicação seguirá no branch. Primeira chamada PUBLIC_TREE
  usou cwd da raiz com caminho relativo errado; repetida no diretório do
  projeto antes de publicar. Nenhum pacote/configuração global foi alterado.

### Incremento 90 — COMMAND INTx-disable do core scan, sem ampliar capacidades

- Quatro arquivos: plano, contrato de config-scan, teste C e runner. A prova
  física anterior recusou primeiro COMMAND004/size2/value400. Permitir somente
  alternância do bit10 com os estados decode originais ou decode desligado;
  preservar todos os outros bits e manter master4 proibido.
- Captura/restauração continuam de COMMAND16bits, sem tocar STATUS W1C;
  restore final devolve exatamente o comando original. Testar root/endpoint,
  original bit10 ligado/desligado, falsos bits8/11, decode novo e master.
- Alternativa: liberar todas as escritas do core; descartada porque windows,
  PM/PCIe/AER e roteamento precisam de qualificação própria. Próxima recusa
  deve ser medida e documentada como negativa, sem declará-la enumeração pronta.

- Gate90: contrato C e16 mutantes compilados morreram por asserção; harness
  de lifecycle passou seus11 cenários e6 mutações. COMMAND/STATUS, restore
  e recusas de novo decode/master/bits não autorizados foram exercitados.
  Diff-check passou. A correção de espaçamento de um bullet LINK é incluída
  como quinto arquivo desta fatia; nenhuma escrita física nova nesta etapa.

### Incremento 91 — módulo externo do scan INTx e seleção reproduzível

- Até cinco arquivos: plano, registro novo de build, seleção do coletor,
  teste de seleção e documentação LINK. Preservar evidência do primeiro
  scan recusado; selecionar explicitamente artefato novo somente no host-scan.
- Compilar em diretório M novo na VM, com contratos/mutações ARM64, Werror,
  modpost fatal, ELF/vermagic exatos e hashes do kernel/payload preservados.
  Sem rebuild de Image, instalação global ou novo boot do iPhone.
- Compor perfil privado novo e exigir cleanup anterior do mesmo boot;
  próximo teste físico será delimitado a enumeração sem bind/DMA/IRQrouting.

- Gate91: build externo ARM64 passou contrato,16 mutações de configuração,
  11 cenários/6 mutações de lifecycle, Werror/modpost/ELF/vermagic. Kernel e
  REG_ON módulo mantêm hashes anteriores.25 testes/15 mutações do coletor
  passaram; seleção nova, perfil/proveniência e --check foram conferidos.
- SSH confirmou o mesmo boot/PCI vazio/módulo ausente. A checagem inicial
  tentou interpretar o status HTTP como JSON; o CGI responde HTML. O corpo
  real foi retido e conferido com a release correta, sem mudar o servidor.
  Payload/initramfs/chaves/pin permaneceram idênticos. Nenhum novo DFU.

### Incremento 92 — prova física do core scan INTx no boot atual

- Até quatro arquivos: plano, evidência sanitizada, LINK e WIFI. Executar
  --host-scan com novo perfil e cleanup privado do ciclo DART anterior.
  Qualificar sucesso somente com dois devices, nenhuma recusa, sizing,
  remoção do bus e restauração/readback; uma nova recusa é prova negativa.
- Confirmar PCI vazio, módulos removidos, REG_ON80, reset/power/serviços;
  salvar snapshot sem reiniciar. Logs/payload/chaves permanecem privados.
  Publicar no branch/CI e atualizar issues; manter Wi-Fi/DMA pendentes.

- Gate92: teste físico no mesmo boot passou INTx e5 writes/9 tentativas;
  primeira recusa agora é ponte1c/size2/e0f0. Scan permaneceu negativo, com
  dois devices mas nenhuma prova completa de sizing/core. Bus removido,
  config/readback/PCI vazio/reset/power/REG_ON/unload passaram. SSH/HTTP e
  snapshot passaram; Linux continua ligado, zero novos boots/PIN/DFU.
- Logs completos retêm história anterior; prova nova foi extraída pelo
  History.fresh do cleanup anterior, evitando tratar recusas antigas como
  atuais. Somente contagens/offsets/digests sanitizados são publicados.

### Incremento 93 — qualificar probes de janelas da ponte no PCI core

- Até cinco arquivos: plano, contrato config, teste C, runner e registro de
  fonte/referência. Ler pci_read_bridge_windows/pci_scan_bridge_extend na
  fonte fixada; qualificar três probes com decode desligado, captura prévia,
  readback e restauração até em erro. Nenhuma atribuição ou BAR MMIO.
- Não liberar PM/PCIe/AER por similaridade. O primeiro erro após os probes
  deve ser medido por nova continuação hot, sem novo DFU. Testar STATUS W1C,
  valores/campos proibidos, decode ligado e todas as falhas de restauração.

- Gate93: fonte probe.c/UAPI fixados conferem os três offsets/probes. Contrato
  passou no Mac e ARM64,20 mutações de configuração e6 de lifecycle/11 casos.
  Capture/readback/STATUS W1C/decode ligado/valores estranhos/falhas de cada
  restore foram exercitados. Build externo Werror/modpost/ELF/vermagic passou,
  com hashes de config/Image/exports e módulos REG_ON/HDQ preservados.
  Nenhum dos novos probes foi aplicado fisicamente nesta fatia.

### Incremento 94 — seleção/build e continuação física da ponte

- Até cinco arquivos: plano, build novo, seleção, teste de seleção e mutações.
  Preservar INTx como histórico; compor perfil novo com artefato qualificado,
  conferir --check e executar --host-scan com cleanup anterior no mesmo boot.
- Uma recusa de capability/controle continua negativa; não ampliá-la durante
  a execução. Confirmar remoção/restore/PCI vazio/serviços e snapshot antes
  de publicar prova sanitizada em fatia própria. Sem reboot/PIN/DFU.

- Gate94a: build57888 bytes/hash82228fa7… transferido e conferido.25 testes
  do coletor e16 mutações passaram, incluindo seleção antiga recusada por
  asserção. Perfil/proveniência/ELF/hash/--check e histórico de cleanup atual
  passaram; payload/initramfs/identidades iguais. Teste físico segue abaixo.

### Incremento 95 — evidência física/limites da ponte e reprodução

- Até quatro arquivos: plano, prova sanitizada nova, LINK e WIFI. Separar
  avanço em probes da ponte de eventual recusa posterior; exigir remoção
  do bus/config/PCI vazio/módulos/serviços/snapshot. Fonte/build permanecem
  identificados por digests, e caminhos de logs/ponteiros privados excluídos.
- Documentar perfil e diretório M atuais e próximo controle exigido, sem
  afirmar Wi-Fi/DMA/IRQdelivery. Publicar branch/issues/CI mantendo Linux ligado.

- Gate94b/95: continuação física no mesmo boot passou IO/upper-prefetch;
  prefetch24 não foi solicitado.9 writes/13 tentativas; próxima recusa3e/2
  é SERR forwarding. Scan continua negativo, com bus removido, três campos
  de ponte/config/readback/restauração/PCI vazio/módulos ausentes confirmados.
  SSH/HTTP/snapshot passaram; Linux permanece ligado, zero novo DFU/PIN/boot.
- Pedidos após a primeira recusa permanecem latched: sua presença no log
  não é prova de que cada write seja necessário. Próxima coleta deve revelar
  capabilities/controles reais antes de qualificar novos estados.

### Incremento 96 — referência read-only de controles antes do core scan

- Cinco arquivos: plano, contrato read-only, teste C, teste/mutações nativo
  e integração no scan. Capturar campos PM/MSI/MSI-X/PCIe/AER/PTM selecionados,
  com identidade/COMMAND master off, ciclos/alinhamento/limites/erro positivos
  recusados. Nunca ler BAR/VPD/address payload nem executar write pelo helper.
- Publicar output somente após leitura completa. Cada função tem limites
  de128 reads/16 capabilities/32 controles; root/endpoint separados. A prova
  é referência de um instante, não estabilidade/qualificação de nova escrita.
- Integrar antes do registro PCI, sem novos modos/DFU. Falha usa restore
  existente e mantém scan negativo. Testar backend real do adapter novamente.

- Gate96: contrato C no Mac passou7 mutações/identidade/master/larguras,
  todos os read faults de root/endpoint, callbacks positivos, cadeias cíclicas,
  limites/capacity e output parcial. Uma mutação de alinhamento sobreviveu
  inicialmente porque faltava ponteiro42; caso adicionou prova de recusa
  antes do backend e a mutação passou a morrer por asserção. Logs preservados.
- Link Capability DWORD foi incluído para confrontar speed/retraining na
  fonte fixada. Harness real do adapter passou11 casos/6 mutações no Mac.
  Não é prova ARM64/física ainda; nenhuma nova escrita foi permitida.

### Incremento 97 — SERR forwarding delimitado e build agrupado com referência

- Cinco arquivos: plano, contrato config, Ctest, runner e referência primária.
  Qualificar somente set do bit1 de BRIDGE_CONTROL da raiz, combinado com
  original/master-abort-clear já permitidos. Preservar parity/VGA/ISA/reset
  e todos os demais bits; restore devolve o controle capturado, sem routing
  de IRQ, bind, DMA ou novo decode.
- Agrupar esta permissão com a coleta read-only de controls num módulo novo.
  Testar valores capturados com SERR ligado/desligado, bits extras/reset
  recusados e restauração exata. Compilar/selecionar em fatia seguinte.

- Gate97: fonte probe.c/UAPI confirmou SERR=2 e port.mask104 escrito0 pelo
  init existente. Contrato no Mac passou22 mutações de configuração,
  combinações originais/SERR/master-abort e todos os bits extras recusados;
  controle e interrupt line adjacente restaurados exatamente. Uma primeira
  busca de macros não encontrou linhas por espaços duplos; parsing por
  tokens confirmou os valores, sem assumir a ausência dos símbolos.
- Archive46 fontes v2 reúne reference/SERR, com hashes e diretório M novos;
  build ARM64 segue em andamento. Não há nova permissão de DMA/IRQrouting
  ou novo decode; nenhuma nova escrita física nesta fatia.

### Incremento 98 — build externo agrupado, seleção e sessão do mesmo boot

- Cinco arquivos: plano, build novo, seleção, teste de seleção e mutações.
  Exigir contratos ARM64/reference/config/lifecycle, Werror/modpost/ELF/ABI
  e hashes do kernel preservados. Novo perfil mantém payload/identidades.
- Executar uma continuação --host-scan com último cleanup; salvar controls
  reais antes de core/SERR. Qualificar avanço e eventuais recusas posteriores
  separadamente, com cleanup/serviços/snapshot e sem reboot/PIN/DFU.

- Gate98: módulo60528 bytes/hash29e29fcd… passou Werror/modpost/ELF/ABI,
  contratos ARM64 e22/7/6 mutações config/reference/lifecycle. Kernel e
  módulos auxiliares mantiveram hashes.25 testes/16 mutações do coletor
  passaram; uma execução inicial precedeu término da transferência/registro
  e teve FileNotFoundError. Após conclusão, repetição em log v2 passou.
- Perfil/local --check/identidades/histórico de cleanup passaram. **Não foi
  carregado no iPhone:** operador informou quase descarga e retorno ao iOS.
  SSH já ausente; tentativa de novo snapshot/reboot parou antes de execução.
  Último snapshot válido é o do teste de ponte; nenhuma mudança posterior
  no Linux foi realizada. Código/artefatos novos estão só no Mac/VM.

### Incremento 99 — alimentação P0 e registro de descarga, sem novo boot

- Até cinco arquivos: plano, ALIMENTACAO, WIFI, prova sanitizada de bateria
  e documentação LINK. iOS foi confirmado pelo operador; leitura local sem
  PIN informa5%/charging=true/external=true. Registrar timestamp/hash privados
  e limites: não é leitura de corrente Linux nem prova de causa única.
- Manter iOS carregando; desenvolvimento offline passa ao carregador SN2400
  específico N71 e gauge/HDQ. Não prolongar Linux/forçar novo DFU para Wi-Fi
  enquanto alimentação sustentada estiver pendente. Não pausar o goal;
  continuar trabalho independente e registrar #2/#8 e progresso #9/#34.

- Gate99: leitura iOS local confirmou5% e carga externa ativa, sem PIN.
  IORegistry SN2400 retornou somente metadados de serviço; não fornece
  corrente/limites. Prova sanitizada conserva digest do log privado, sem
  identificadores. Documentação distingue descarga operacional de causa
  ainda não isolada, mantém candidato PCI não carregado e último snapshot.
  Nenhuma escrita de carregador/gauge ou novo DFU foi realizada.

### Incremento 100 — corrigir fixtures dos consumidores de restore PCI

- Três arquivos: plano e fixtures C de BAR sizing/chip-id. CI do SHA d8e7422
  revelou recusa dos novos restores de janela pelo backend sintético antigo.
  Manter contrato/código de hardware e candidata intactos; fixtures aceitam
  somente as três janelas da raiz, largura exata, valor original e decode off.
- Inicializar valores distintos e STATUS secundário nãozero para comprovar
  preservação, repetir apenas os dois gates com suas12 mutações compiladas.
  Publicar e conferir CI final. Nenhuma execução no iPhone.

- Gate100: os dois testes C passaram com as12 mutações executadas e
  recusadas por asserção. Fixtures delimitam janelas/root/width/valor/decode;
  memcmp integral comprova preservação do STATUS secundário e demais campos.
  Só fixtures/plano mudaram; hash do módulo físico continua válido.

### Incremento 101 — aritmética N71 de limite USB sem I/O

- Cinco arquivos: plano, header puro SN2400, fixture C, runner de testes
  e prova primária selecionada. Conferir kernel Apple fixado, funções/cstrings
  e digests dos trechos; separar encoder sem calibração do setter com I/O.
- Reproduzir clamp90..2000mA e quantização10mA da referência, com pedido0
  marcado como suspend separado do código0. Recusar calibração não modelada,
  entrada ausente e output parcial. Não gerar sequência de registradores.
- Testes de fronteira, intervalo16bit, valores u32 extremos e mutações
  compiladas no Mac/ARM64. Só cálculo: não valida limites físicos, efeito de
  leitura, ownership I2C1/HDQ ou corrente de carga. Documentar em fatia seguinte.

- Gate101: referência Apple e fonte A10 fixadas/hashes conferidos; encoder
  N71 sem calibração passou domínio16bit/u32 extremos e8 mutações por
  asserção no Mac/ARM64. Header compilou em objeto kernel ARM64 comWerror;
  .config/Image/exports preservados. Não foi criado/carregado driver físico.
- Setter N71 usa ordem diferente da fonte A10 ao suspender e cache de
  software, não snapshot vivo; primeiro erro de write não é propagado.
  Timer usa setTimeout(interval,1e9), default8s, após software_mode1;
  isso não comprova watchdog físico nem a causa da descarga. Oito trechos
  selecionados têm digests para reprodução; nenhum charger I/O executado.
- CI da correção100 aprovado no SHA85aa0f5: PR37226272040 e push37226267211,
  seis jobs Ubuntu/macOS/Windows. Novos arquivos101 ainda precisam de CI.

### Incremento 102 — documentação de carga, limites e recarga iOS

- Cinco arquivos: plano, ALIMENTACAO, HDQ, STATUS e prova de bateria.
  Registrar follow-up17%/charging ativo com digest/timestamp; manter separada
  da medição de carga Linux. Atualizar estado físico atual e candidato não usado.
- Documentar encoder N71, divergência de ordem A10, erros do setter/cache,
  timer software e gates restantes. Incluir reprodução privada dos trechos e
  testes nativos; não apresentar matemática como driver/carga funcional.
- Validar JSON/links/diff/árvore pública e CI do head publicado, atualizar #2
  com implementação sem I/O. Sem instalação, DFU ou mudança do aparelho.

- Gate102: JSON/AST/links locais e diff passaram. Follow-up confirma recarga
  iOS5%→17%, sem PIN. Documentação distingue cálculo, timer de software,
  limites não qualificados e driver ainda pendente. Checkpoint STATUS atual
  marca Linux offline e identifica seções anteriores como históricas.
  O primeiro patch documental foi recusado por contexto divergente, sem
  alterar o plano; leitura e aplicação com contexto atual passaram.

### Incremento 103 — qualificar aquisição I2C1 offline para o próximo adapter

- Três arquivos: plano, HDQ e referência selecionada I2C. Conferir fonte
  fixada/limpa de platform/core e DTS, driver/config existentes, recursos e
  writes do probe. Não executar bind, scanI2C, MMIO ou transmissão.
- Registrar devres de adapter/clock/IRQ separadamente de restauração elétrica:
  remove vazio não restaura CTL/IMASK/pinos. Planejar primeiro inventário
  passivo/ownership/idle; depois ciclo de plataforma temporária no mesmo boot,
  somente quando recurso/pinos/cleanup forem qualificados.
- Não assumir pin114/115 Linux como pinmux Apple runtime validado nem que
  enabled config prova funcionamento. Conservar a candidata PCI sem carga.

- Gate103: hashes das duas fontes e DTS conferidos, diff desses arquivos
  contra HEAD958481f vazio. Probe/reset/adapterdevres/IRQfallback observados;
  nenhuma restauração explícita CTL/IMASK. HandlerIRQ devres é distinto da
  propriedade/disposal do mapping AIC; este gate permanece pendente.
  JSON/links/diff aprovados; nenhum bind, MMIO, overlay ou cliente novo.
- CI do código+documentação102 no SHA47c0611 terminal aprovado: PR37227269013
  e push37227266273, seis jobs Ubuntu/macOS/Windows. A mudança103 é documental
  e reutiliza esses gates de código, sem afirmar prova física ou CI do novo head.
- Logs ARM64/contexto e unidade de compilação foram preservados no Mac,
  digests conferidos. Primeira leitura local precedeu conclusão dos quatro
  transfers assíncronos e falhou por arquivo ausente; esperar todos os exits0
  e repetir somente o gate de hashes resolveu. Nenhum teste/hardware repetido.

### Incremento 104 — observador passivo da topologia I2C1 e GPIO114/115

- Contexto: o aparelho está recarregando no iOS; Linux ainda não tem carga
  sustentada comprovada. Preparar a coleta do carregador sem novo boot,
  ativação do controlador, solicitação de pinos ou transmissão I2C.
- Cinco arquivos: este plano, `phone/kernel/n71-i2c-topology-observe.c`,
  `phone/kernel/Makefile`, `tests/n71_i2c_topology_observe.c` e
  `tests/test_n71_i2c_topology_observe.py`.
- Módulo explícito `run=1`, board N71, nó I2C1 desabilitado, sem filhos,
  plataforma ou adapter existente. Validar apenas metadados DT de recurso,
  IRQ bruto, clock fixo, domínio e grupo pinctrl; não criar IRQ nem clock.
- GPIO114/115: usar somente o regmap do provider atual, com device lock,
  quatro leituras por pino (cache, hardware duas vezes, cache). Emitir dados
  completos apenas se todas passarem. Não interpretar estabilidade como
  ownership nem como pinmux Apple fisicamente qualificado.
- Verificação: compilar o módulo real dentro de harness C com falhas de
  metadados, referências, locking e cada leitura; executar mutações reais.
  Repetir no ARM64 e compilar módulo externo no kernel preservado com Werror.
  Publicar prova/build/documentação em incremento separado; sem carregar no
  telefone enquanto está no iOS. CI anterior54179b4 aprovado no PR37228026232.

- Gate104: o módulo real passou83 casos e14 mutações compiladas por asserção
  no Mac e ARM64. Build externo ARM64 comWerror/modpost passou; ELF64LE/REL
  AArch64 e vermagic7.2.0-iphone6s-dart-serdev1 conferidos. Image/config/exports
  permaneceram iguais. Módulo15696B, SHAe740e8dca37cc0e689a8d5877a8be3c16a17176be480ef21cb93c6e137c0a96f.
- Primeira execução das mutações parou porque remover board check deixou
  função mock sem referência eWerror impediu compilar. Corrigida a mutação
  para manter referência sem validar; o mutant executou e morreu por asserção.
  Log inicial preservado, sem tratar erro de compilação como prova de mutation.
  Artefatos/logs transferidos somente após exits0; hashes locais iguais.
  Nenhum módulo foi carregado e nenhum boot físico ocorreu nesta fatia.

### Incremento 105 — reprodução e limites do observador passivo I2C1

- Cinco arquivos: plano, HDQ, ALIMENTACAO, STATUS e
  `docs/evidence/n71-i2c-topology-observer.json`. Registrar código4436af0,
  hashes de fontes/artefato/logs, kernel preservado e gates83casos/14mutações.
- Documentar build externo separado e futura coleta SSH/unload no mesmo
  boot, sem autoload, scanI2C, ativação de controlador ou novo kernel/DFU.
  Distinguir declaração DT, amostras GPIO e ausência momentânea de adapter
  de ownership, pin routing qualificado, corrente e carregamento funcional.
- Atualizar checkpoint51% iOS de leitura já verificada, sem apresentá-la
  como nova medição. Conferir JSON/hashes/links/diff/guard e publicar na
  branch/issue2. Reutilizar testes104 inalterados; conferir CI do head final.

### Incremento 106 — corrigir identidade OF antes de concluir a documentação105

- Quatro arquivos: plano, módulo I2C1, harnessC e runner. Revisão da fonte
  OF fixada mostrou quefdt_get_name fornece nome local efull_name não é
  contrato de caminho absoluto. A comparação de string em104 recusaria
  nós válidos. Código4436af0 não foi publicado nem carregado no aparelho.
- Usarof_find_node_by_path e identidade de ponteiro, liberando a referência
  adicional. Harness deve reproduzir nomes locais e recusar nó homônimo
  de outra hierarquia e lookup ausente; mutação real recupera a comparação
  de string equivocada e deve morrer por asserção.
- Reexecutar apenas testes alterados Mac/ARM64 e novo build externo M-v2;
  preservar kernel/artefato antigo/logs. Atualizar hashes/contagens/doc105
  após a correção, sem DFU. Essa correção precede a publicação do candidato.

- Gate106: código corrigido passou86 casos e15 mutações por asserção Mac e
  ARM64; nomes locais e três lookups ausentes estão cobertos. A fonte antiga
  4436af0, compilada com o harness corrigido, morreu por asserção, não por
  erro de build. Módulo v2 externo15768B compilouWerror/modpost no mesmo ABI;
  SHA32b7e481c08a7dab1df7075b4a3079397c2c78d1bd8685b7949bee70f2cfd39c.
  Image/config/exports preservados; fonteOFfdt.c limpa contraHEAD958481f.
  Nenhum load/ativação/DFU; documentação105 deve selecionar apenasv2.

- Gate105, concluído após106: documentação/prova selecionam o código98bc26b
  e módulo v2,86 casos/15mutações e o contrato OF real. Hashes de inputs/logs
  e transfer iguais; JSON/links/AST/sintaxe shell/diff aprovados. Nenhum teste
  anterior inalterado foi repetido por causa das mudanças documentais.
- Novo checkpoint iOS:79% às19:58:58UTC, charging/external true, sem PIN.
  Primeira leitura foi recusada pelo socket usbmux no sandbox; IORegistry
  já viaiPhone. Repetição somente da leitura local com acesso ao socket
  passou; não foi solicitada troca/reconexão de cabo. Apenas campos de
  bateria e digest sanitizado publicados; corrente Linux continua pendente.
  O primeiro patch documental foi recusado por contexto divergente, sem
  alterações; leitura atualizada e reaplicação passaram.

### Incremento 107 — pin routing Apple I2C1 e sequência de referência

- Contexto: o turno anterior alterou código e produziu prova nova, portanto
  foi progresso. Confirmar os CI existentes por seus IDs, sem reiniciá-los.
  O iPhone continua no iOS; este incremento é análise de dados já fixados.
- Cinco arquivos: plano, `docs/N71_HDQ.md`, `docs/ALIMENTACAO.md`,
  `docs/evidence/n71-i2c-acquisition-reference.json` e `docs/STATUS.md`.
  Registrar SCL115/SDA114, descriptor12 bytes, papelAP, modo2, IRQ207,
  clock-gate71 e janela do driver N71; não inferir estado físico da placa.
- Conferir hashes IM4P/ADT/kernel, janelas de código/cstrings e cadeia de
  factory GPIO: descriptor por role, init com modo2 e encaminhamento ao
  slot5e8 do provider. Separar número de pino de ownership/drive/pull/idle.
- Descrever init/unjam Apple como referência, sem replay: CTL/SMSTA/IMASK,
  sequência GPIO e reset são operações ativas, não um read-only probe.
- Verificação: digests/limites de janelas, metadados selecionados, JSON/links
  e diff/guard. Código106 permanece inalterado; reutilizar seus gates e CI
  exato. Nada de varredura I2C, transação, mux, firmware novo ou DFU.

- Gate107: a reprodução documental conferiu dez janelas, bytes únicos dos
  dois descriptors e hashes IM4P/ADT/kernel. JSON, links locais, diff e
  fronteira pública passaram. CI c683145 aprovado em PR37230516183 e
  push37230513184; seis jobs terminais. Código106 não mudou; seus gates
  foram reutilizados, sem repetir suíte ou build por mudanças documentais.
- Leitura local iOS sem PIN: 89% às 20:29:05 UTC, carregamento/alimentação
  externos ativos; log privado preservado separado dos checkpoints anteriores.
  Nenhuma ativação I2C, load, novo kernel ou DFU. Número/formato dos pinos
  agora têm referência Apple; aquisição/restauração e corrente seguem pendentes.

### Incremento 108 — propagar falhas de escrita do provider GPIO

- Contexto: o helper apple_gpio_set_reg ignora regmap_update_bits na fonte
  preservada; set_mux/set/direction e irq_set_type retornam sucesso mesmo
  quando a escrita falha. O futuro acesso I2C1 não pode confiar nesse retorno.
- Cinco arquivos: plano, phone/kernel/patches/0003-apple-gpio-write-errors.patch,
  tests/test_n71_gpio_write_errors.py, tests/n71_gpio_write_errors.c e
  docs/evidence/n71-gpio-write-errors.json. Não integrar automaticamente no
  bundle nem modificar Image/fonte/output preservados ou pedir DFU.
- Patch restrito ao helper e callbacks que retornam int: set_mux, set,
  direction_input, direction_output e irq_set_type. Retornar o erro real;
  irq_set_type só troca handler após escrita bem-sucedida. Callbacks IRQ
  void/startup e leituras têm contratos distintos e permanecem fora desta fatia.
- Gates: compilar rotinas reais reconstruídas do patch; testar retorno e
  estado para sucesso, falha sem efeito e erro após efeito parcial, máscara,
  pin/offset e handler. Mutações devem compilar e morrer por asserção.
  Repetir Mac/ARM64; aplicar patch em cópia descartável completa do provider,
  compilar objeto externo ARM64 Werror contra ABI preservado e conferir hashes.
- Limites: erro propagado não prova rollback; o adapter ainda precisa snapshot,
  readback e restauração verificada. Nenhum regmap do aparelho será acessado.

- Gate108: Mac e ARM64 passaram 816 cenários, 11 mutações compiladas e
  regressão da fonte original por asserção. Patch aplicado em cópia isolada;
  build externo completo do provider passou Werror/modpost e ABI selecionado.
  Fonte original, config, Image e exports preservados. Módulo serve somente
  para verificação; não carregar duplicata do provider embutido.
- Dois erros de preparação do harness foram corrigidos antes do gate: contexto
  do patch não continha a rotina IRQ inteira e faltava typedef u32 na fixture.
  Logs iniciais preservados, sem contar erro de compilação como mutation kill.
  O marcador de aprovação agora só é emitido após todos os subtestes passarem.
- Integração no patchset/novo Image e teste físico permanecem pendentes;
  não foi habilitado I2C1 nem carregador. Não pedir DFU para esse objeto de ABI.
- Pendência de integração registrada na issue35. Lint Python passou com
  pyflakes já instalado e seleção de versão apenas no comando; o shim sem
  versão havia recusado executar. Nenhum pacote ou configuração global mudou.
- Check de diff aplicado normalmente a código/docs e ao source transformado.
  No arquivo unified patch, prefixes de contexto produzem falso positivo de
  whitespace; somente essa representação foi conferida com a opção de comando
  correspondente, sem alterar configuração Git. Patch real aplicou limpo na VM.

### Incremento 109 — observador PMGR para o acesso I2C1

- Turno anterior foi progresso: patch GPIO, gates nativos/build ARM64 e issue35
  publicados. CI19f6129 segue em processos confirmados; não reiniciar jobs.
  Nova leitura iOS: 93% às 20:48:17 UTC, carregamento externo ativo.
- Cinco arquivos: plano, phone/kernel/n71-pmgr-power-observe.c,
  phone/kernel/Makefile, tests/n71_pmgr_power_observe.c e
  tests/test_n71_pmgr_power_observe.py. Módulo separado atualizado por SSH,
  sem kernel novo, autoload, reserva/ativação, reset, IRQ ou writes.
- Limitar ao PMGR20e000000/8c000 e cadeia i2c1@801a0 → sio_p@80158 →
  sio_busif@80150, com metadados/phandles/labels exatos. Não criar regmap
  por conveniência: só chamar syscon após confirmar, sob device lock, um
  domain ligado ao driver apple-pmgr-pwrstate; esse probe fixado só retorna
  sucesso após criar/obter o map do mesmo parent. Rejeitar clocks/resets
  no parent para evitar ativações implícitas na leitura regmap.
- Ler duas amostras bypass por domain; liberar referências/lock em todos os
  caminhos e emitir linhas completas só após as seis leituras passarem.
  Estado alvo/real e flags são referências Linux, não medição de corrente,
  frequência ou captura atômica/ownership da cadeia.
- Gates: executar módulo real em harness C, erros de todos os metadados,
  mapping, refs, locks e cada leitura; mutações compiladas por asserção.
  Repetir Mac/ARM64 e build externo Werror no bundle preservado. Documentação
  e prova selecionada em incremento separado antes de qualquer load físico.

- Gate109: módulo real passou 88 cenários e 16 mutações por asserção no Mac
  e ARM64. Build externo Werror/modpost passou; ELF64 LE/REL AArch64, ABI
  preservado, módulo11672B e SHAbdf1afa5d631192716443c9c9595bab018706e2c657563b016a27e3d4bdcf257.
  Fonte syscon/PMGR/DTS limpa contra HEAD958481f; config/Image/exports iguais.
  Inputs, logs e módulo transferidos somente após exit0 e digests iguais.
- Primeira rodada de mutações parou porque remover o único put_device
  deixou o mock sem referência e Werror recusou compilar. O mutant corrigido
  conserva referência à função sem chamá-la e morre por asserção de refs;
  erro de compilação inicial não foi contado como prova. Lint Python passou.
- CI19f6129 terminou aprovado nas duas execuções PR37233188196 e
  push37233183384, seis jobs. Novo observador ainda não foi carregado;
  inferência de syscon existente depende do binding do driver fixado sob lock,
  não de tratar a API get-or-create como lookup sem efeitos em qualquer nó.
- A primeira transferência PMGR reutilizou nomes genéricos de três logs/
  metadados GPIO. Os originais continuavam preservados na VM: foram restaurados
  e seus digests conferidos contra a prova pública108. O PMGR agora tem pasta
  privada dedicada runtime/n71-pmgr-observer-20261004; nenhum log ficou perdido.

### Incremento 110 — reprodução e limites da coleta PMGR agrupada

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/ALIMENTACAO.md, docs/STATUS.md
  e docs/evidence/n71-pmgr-power-observer.json. Registrar source80b3fe0,
  inputs/ABI/artifact/logs, syscon bound-guard e seis leituras restritas.
- Separar estado PMGR de ownership/idle/corrente de bateria e de ativação I2C1.
  A API syscon pode criar map no caso geral; qualificação do driver fixado
  sob lock é precondição, não supor lookup sem efeitos em outros devices.
- Documentar build separado e load/unload junto do observador GPIO98bc26b
  no mesmo boot necessário; nenhum Image novo/DFU para cada módulo.
  Selecionar logs só desse load; comparar SHA no destino e confirmar serviços.
- Verificação: hashes/ELF/imports/links/JSON e sintaxe dos snippets; reutilizar
  código109/gates inalterados. CI19f6129 aprovado; observar CI de80b3fe0 sem
  atribuir prova anterior ao novo código. Sem nova ação física nesta fatia.

- Gate110: JSON/inputs/logs/artifact, links locais e sintaxe dos dois snippets
  shell aprovados. Quatro fontes selecionadas conferidas byte a byte contra
  blobs HEAD958481f, não apenas status/diff. Código109 e gates inalterados
  reutilizados. CI80b3fe0 observado em PR37234471571/push37234468352 ainda ativo.
- Coleta física proposta somente após artefatos/gates/documentação preparados:
  um DFU manual, observadores GPIO/PMGR juntos, snapshot e retorno em sessão
  curta. Disponibilidade do operador perguntada; boot ainda não foi iniciado.
- CI80b3fe0 terminou aprovado em PR37234471571 e push37234468352, seis
  jobs. Checkpoint documental só foi publicado após esses jobs terminarem,
  para não cancelá-los por concorrência cancel-in-progress. Ambos os módulos
  passivos têm gates nativos/build e podem compor a mesma coleta física.

### Incremento 111 — propagar falhas dos callbacks PMGR antes do I2C ativo

- Contexto: recarga iOS confirmou100% às21:23:03UTC, alimentação externa
  conectada/capaz, sem nova solicitação de PIN. CIdecbe2d aprovado nos runs
  PR37235115907/push37235111965. Disponibilidade para o DFU único ainda
  pendente; não iniciar monitor ou reboot só porque a bateria está cheia.
- Driver fixado drivers/pmdomain/apple/pmgr-pwrstate.c foi relido inteiro
  e conferido byte a byte contra HEAD958481f. Callbacks de mudança de estado,
  assert/deassert/reset e status descartam erros regmap. Corrigir somente
  esses callbacks numa patch separada antes de acesso ativo I2C1.
- Cinco arquivos: este plano, phone/kernel/patches/0004-apple-pmgr-errors.patch,
  tests/n71_pmgr_errors.c, tests/test_n71_pmgr_errors.py e
  docs/evidence/n71-pmgr-errors.json. Abrir issue de integração antes do código.
- Preservar bits, ordem de sucesso, máscaras e lock IRQ-safe. Propagar primeiro
  erro e interromper operações seguintes; não executar auto-enable após poll
  falho. Garantir unlock em falhas, reset sem delay/deassert após assert falho,
  status retorna erro de leitura. Não prometer rollback de escrita parcial.
- Probe/is_active continuam fora desta patch; documentar essa lacuna antes de
  uso ativo. Não trocar provider embutido por módulo duplicado. Integração
  futura em candidata separada, com GPIO/DART e rollback, sem novo DFU por fix.
- Gates: fixture C compila callbacks reais extraídos de patch com contexto
  completo, injeta falhas e efeitos parciais, verifica palavras/ordem/locks;
  baseline original deve falhar por asserção. Mutações devem compilar e morrer
  por SIGABRT. Mac/Ubuntu ARM64, lint, AST e compilação completa Werror na VM.
  Modpost externo é diagnóstico, não prova aplicável a um provider embutido;
  não forçar exports/licença para contornar a fronteira. Preservar os insumos.
- Depois: selecionar hashes/logs e documentar reprodução; coleta passiva
  GPIO/PMGR segue agrupada e sem ativações ou I/O do carregador.

- Gate111: 492 casos e 14 mutações compiladas morreram por asserção no Mac
  e ARM64; fonte original também morreu por asserção. Primeira tentativa
  do runner recusou anchor de mutação repetido antes de compilar; corrigido
  para incluir início de linha. Não contou erro de harness como kill.
- O arquivo completo compilou Werror como objeto embutido ARM64, sem
  -DMODULE, com initcall e sem __this_module. Objeto11328B,
  SHA0b75d8804d432558f4648f91974ed66bc23f19a508295ef21d81d611c3e1049d.
  Fonte fixada, config/Image/exports preservados. Inputs/logs conferidos
  após transferência, AST e pyflakes passaram. Issue36 aberta.
- Modpost externo falhou: fonte embutida sem MODULE_LICENSE e referência
  of_phandle_iterator_args não exportada. Erros preservados sem supressão.
  Decisão: gate correto é objeto embutido; não fabricar módulo instalável
  nem alterar exports/licença só para tornar verde um teste inadequado.
  Full link/Image e integração/boot continuam explicitamente pendentes.
- Probe/is_active ainda descartam erros; escrita parcial exige cleanup do
  caller. Esta patch sozinha não qualifica aquisição ativa de I2C1 nem carga.
  Zero DFU/reboot/I/O no aparelho; aguardar a disponibilidade física já pedida.

### Incremento 112 — reprodução do objeto PMGR e limites de integração

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/ALIMENTACAO.md,
  docs/STATUS.md e docs/evidence/n71-pmgr-errors.json. Código301a61f já
  publicado; observar seu CI terminal antes de publicar docs, evitando cancel.
- Documentar callbacks cobertos, primeiro erro/lock preservados, ausência de
  rollback de efeito parcial e lacunas de probe/is_active. Registrar receita
  obj-y/target direto, arquitetura e ausência de MODULE como prova de build
  embutido. Não prescrever insmod do provider ou tratar modpost externo como
  sucesso; full link/Image e qualificação permanecem na issue36.
- Atualizar checkpoint100% iOS sem confundir percentual/charge-capable com
  corrente ou saúde da bateria. Coleta passiva já preparada continua única;
  nenhum DFU por incremento ou por patch.
- Verificar JSON/identidades/digests, links locais e bash -n do snippet novo;
  reutilizar gates111 porque patch/testes/config/artefato não mudaram.

- Gate112 documental: JSON/digests dos inputs e links locais conferidos,
  snippet novo passou bash -n. Código/testes111 inalterados, evidências
  Mac/ARM64/Werror reutilizadas. CI301a61f em PR37236898569/push37236896067
  ainda em execução; não publicar docs enquanto isso cancelaria o gate.
- Roteiro privado de coleta agrupada preparado, sem autoiniciar boot/reboot.
  Transporte falso em processo separado validou os comandos com bash -n,
  transferiu os bytes selecionados dentro da fixture e detectou observação
  ausente/ring truncado; três cenários com cleanup de staging. Não houve
  SSH real, I/O do aparelho ou prova física. Logs/fixtures permanecem privados.

- CI301a61f concluiu aprovado nos dois runs PR37236898569 e
  push37236896067, seis jobs Ubuntu/macOS/Windows. Docs112 serão publicados
  depois desses gates terminais, sem cancelamento das execuções de código.

### Incremento 113 — falhas de leitura/escrita no probe PMGR

- Próxima dependência da issue36: helper is_active e probe descartam erros
  antes de registrar genpd. Disponibilidade física continua pendente; tratar
  estes erros offline preservando os dois observadores já preparados.
- Cinco arquivos: plano, phone/kernel/patches/0005-apple-pmgr-probe-errors.patch,
  tests/n71_pmgr_probe.c, tests/test_n71_pmgr_probe.py e
  docs/evidence/n71-pmgr-probe-errors.json. Patch005 aplica depois de004;
  baseSHA cc65bad1b788c4fa1d6e374b236f1b27c840797b727a600035294f17b71433e9.
- Converter is_active em retorno de erro e bool de saída escrito apenas
  no sucesso. Probe propaga min-state update, leitura do estado, power_on
  always-on e auto-PM update antes de registrar domínio/provider/reset.
  Preservar semântica de propriedade min-state ausente/fora do limite,
  masks/flags e caminho de sucesso. Não tentar rollback cego de efeito parcial.
- Lifecycle genpd após registro não pertence a esta fatia; examinar cleanup
  e erros de iterator/provider numa próxima fatia da mesma issue antes da
  candidata ativa. Não afirmar segurança do I2C1 por estas patches isoladas.
- Fixture C compila funções reais da patch004+005 e probe; verificar estados
  de registro e palavras/ordem de I/O, leitura falha com efeitos parciais,
  estado ativo/auto-PM e always-on. Baseline004 deve ser detectada por asserção.
  Mutações precisam compilar e terminar por SIGABRT, Mac/ARM64.
- Gates: AST/lint, C nativo, compilação completa obj-y ARM64/Werror na VM,
  sem MODULE/insmod; original/config/Image/exports preservados. Fonte/gates
  callbacks111 reutilizados quando bytes das funções permanecerem iguais.
  Documentar metadados/reprodução em fatia seguinte e aguardar CI anterior
  terminal antes de novo push. Nenhum DFU só para publicar o incremento.

- Gate113: 3138 casos e 12 mutações compiladas por asserção passaram Mac e
  ARM64. Predecessor004 também morreu por asserção, não erro de build.
  Primeira fixture não definia EPROBE_DEFER: corrigida com errno Linux517;
  compilação falha inicial preservada e não contada. Mutation de offset
  foi movido após leitura da propriedade, pois o primeiro anchor seria
  sobrescrito antes do I/O; não foi declarado como kill nessa forma.
- Arquivo completo004+005 compilou obj-y ARM64/Werror, sem MODULE, com
  initcall/sem __this_module. Objeto11424B,
  SHA2becaff2ea85b73f4542c5cbde22157864dbe95ac7a8b633cc1bc1e6b347f8ea.
  Callbacks111 conferidos byte a byte inalterados, gate correspondente
  reutilizado; source/config/Image/exports preservados. Inputs/logs/objeto
  conferidos após transferência. AST/lint aprovados; sem full link/Image.
- Referência genpd está em drivers/pmdomain/core.c nesta árvore, não no
  caminho antigo drivers/base/power/domain.c. Arquivo SHA32e2f6b0 conferido
  contra HEAD. Remoção pode recusar provider/children/devices; falha de
  add_provider no driver não remove domínio já inicializado. Metadata do
  iterator e cleanup após publicação precisam de próxima análise, sem
  prometer rollback cego ou reserva de ownership por esta patch.
- CI8ad5091 aprovado em PR37237523350/push37237521125, seis jobs. Zero
  reinicializações/carga/firmware no iPhone neste incremento; disponibilidade
  física continua sendo a única dependência da coleta passiva pronta.

### Incremento 114 — reprodução das patches PMGR004+005

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/ALIMENTACAO.md,
  docs/STATUS.md e docs/evidence/n71-pmgr-probe-errors.json. Código21a786c
  publicado; observar seu CI terminal antes de publicar este checkpoint.
- Atualizar receita canonical obj-y para aplicar004 e005 numa cópia do
  provider fixado, conferindo os digests intermediário/final. Preservar a
  prova histórica004 e explicar o delta do probe, sem repetir todo o build.
- Separar I/O inicial corrigido de cleanup após registro, ownership/idle,
  efeito parcial e carga/telemetria físicos ainda pendentes. Módulo duplicado
  continua proibido; nenhum novo DFU por patch/commit.
- Verificar JSON/inputs/logs/artefato e links locais, bash -n da receita.
  Reutilizar gates113 e callbacks111 bytes inalterados, sem nova suíte local
  apenas por documentação. CI8ad5091 terminal aprovado e preservado.

- Gate114: JSON/digests e links locais aprovados; receita canonical004+005
  passou bash -n e ordem das duas patches foi conferida. Código113/artefato
  inalterados, gates nativos/ARM64/Werror reutilizados. CI21a786c confirmado
  ativo nos handles PR37238520733/push37238517260; watchers específicos
  iniciados sem refazer testes ou publicar docs antes do resultado terminal.

- CI21a786c terminou aprovado em PR37238520733/push37238517260, seis
  jobs Ubuntu/macOS/Windows; watchers encerraram exit0 e JSON terminal foi
  conferido por job. Não se reiniciou gate nem cancelou CI por novo push.
- Semântica child/parent confirmada no core fixado: parent_node fica na
  lista parent_links do domínio pai, child_node na child_links do subdomain.
  Assim a recusa de genpd_remove por parent_links não vazio é por filhos.
  Esta leitura não prova exclusão de concorrência/cleanup no hardware.

### Incremento 115 — cleanup do domínio antes de publicar o provider

- A fonte genpd fixada só marca has_provider após sucesso completo de
  of_genpd_add_provider_simple; caminhos de erro desfazem device_add/OPP.
  No PMGR, erro de add_provider retorna sem remover domínio inicializado.
  Corrigir esse vazamento sem apagar outro provider do mesmo nó.
- Cinco arquivos: plano, phone/kernel/patches/0006-apple-pmgr-provider-cleanup.patch,
  tests/n71_pmgr_provider_failure.c, tests/test_n71_pmgr_provider_failure.py e
  docs/evidence/n71-pmgr-provider-cleanup.json. Patch006 aplica após004+005,
  baseSHA7ad9c93264edbf3e42400ff7d654e0c143db68f4500b196a8ae6ee260e43b5a4.
- Add-provider falho vai ao label de remoção do domínio sem chamar del-provider.
  Erros posteriores já removem provider antes desse mesmo label. Preservar o
  primeiro erro. Não declarar cleanup de concorrência/pós-publicação, refusal
  de genpd_remove ou rollback de registradores como resolvidos por esta fatia.
- Reutilizar API/fixture do probe113 sem editar os insumos históricos: fixture
  composta renomeia apenas backends Kernel API e main; fonte real do probe
  vem das patches005+006 aplicadas por Git em pasta descartável. Injetar
  ENOMEM/EIO/EINVAL/EEXIST/EPROBE_DEFER, conferir domínio removido, reset ausente,
  primeiro erro e provider alheio preservado. Predecessor005 deve morrer por
  asserção; mutações compiladas de bypass/goto/ret/cleanup detectadas.
- Gates Mac/ARM64, AST/lint e objeto completo obj-y/Werror, sem MODULE/load.
  Preservar fonte/config/Image/exports; verificar todos os inputs compartilhados
  por SHA. VM com5,49GiB disponíveis: integração futura usa worktree/output
  separados e confere espaço antes do build; não remover baseline/rollback.
- Depois: documentar reprodução e integrar GPIO/PMGR/DART/serdev numa candidata
  separada. Coleta passiva mantém um DFU e depende de disponibilidade física.

- Gate115: 3258 casos, seis mutações compiladas por asserção e predecessor005
  aprovados Mac/ARM64. GCC detectou indentação ambígua num mutante de teste;
  usar bloco explícito corrigiu a fixture, sem contar erro de compilação como kill.
  Log da falha foi preservado; apenas gate afetado foi repetido.
- Objeto completo obj-y ARM64/Werror11424B,
  SHA4a07d023225611fc6045a18e2cfba627d44c2a7502a692c4173deaa289d38db4;
  initcall presente, sem MODULE/__this_module. Insumos e logs transferidos
  conferidos por SHA; fonte/config/Image/exports preservados. AST/lint aprovados.
  Nenhuma carga/DFU/reinicialização do iPhone; iOS mantido para recarga.

### Incremento 116 — reprodução do cleanup PMGR006

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/ALIMENTACAO.md, docs/STATUS.md
  e docs/evidence/n71-pmgr-provider-cleanup.json. Registrar commitf728099,
  recipe004→005→006, gate Mac/ARM64 e limites ainda sem teste físico.
- Reutilizar gates115; validar JSON/digests, links e bash -n da receita.
  Esperar CI115 terminal antes do push116; não pedir DFU por documentação.
- Próxima integração em worktree/output próprios requer espaço. VM20GiB
  tem5,49GiB livres, abaixo do guard8GiB para output novo; aumentar apenas
  seu disco para32GiB pelo Multipass oficial. Mac215GiB disponíveis.
  Preservar versões/config/imagens e não instalar pacote ou mudar config global.

- Gate116: JSON/digests, links e receita004→005→006 bash -n aprovados.
  Gates115 de código reutilizados; nenhum teste físico por documentação.
- Disco da VM ampliado de20 para32GiB pelo CLI oficial, sem processo make
  ativo. Guest expandiu automaticamente:18360807424 bytes livres, guard8GiB
  atendido. Config/Image/exports do rollback mantêm digests originais.
  Mac tem215GiB livres; nenhum pacote ou configuração global alterado.

### Incremento 117 — bundle separado DART/serdev/GPIO/PMGR

- Objetivo: preparar fonte candidata com patches001→006 e identidade
  n71-dart-serdev-power-v1/-iphone6s-dart-serdev-power1, preservando o default
  legado. Não habilitar DT I2C1/HDQ/charger. Até cinco arquivos: plano,
  scripts/build/kernel_bundle.py, tests/test_kernel_power_bundle.py,
  docs/N71_KERNEL_BUNDLE.md e docs/evidence/kernel-n71-power-bundle.json.
- Seleção explícita por profile; hashes de seis patches e seis blobs completos,
  base958481f. Reutilizar guards do helper, recusar mistura parcial/legacy.
  Git --check conjunto antes de apply; patch tardia incompatível deve deixar
  candidato intacto. Git real/mutações por asserção Mac/ARM64 e gates legados.
- Preparar worktree/output novos na VM32GiB, que agora tem17GiB livres,
  conferir blobs reais/config preservada e LOCALVERSION única. Guard8GiB
  antes de Image/DTB/Werror; perfis/artefatos físicos separados em próximas
  fatias. Não alterar iPhone até disponibilidade física e gates apropriados.
- O preflight Mac tentou reconstruir arquivo completo pela patch004; hash
  divergiu antes de executar Git. Não declarar layering qualificado por esse
  caminho; usar fonte real fixada na VM e inspecionar framing antes de repetir.

- Gate117: quatro testes/oito mutações do profile power aprovados Mac/ARM64;
  três testes/11 mutações legadas seguem aprovados. AST/lint/recipe bash -n
  e todos os inputs/logs transferidos conferidos por SHA. Worktree real novo
  aplicado com Git --check conjunto e seis blobs corretos;15GiB livres depois
  do checkout. Source/config/Image/exports legados preservados.
- Patch004 contém somente as255 linhas iniciais no hunk, não arquivo inteiro;
  duas reconstruções tentadas no preflight Mac recusaram antes de Git.
  Fonte real completa fixada na VM qualificou layering004→006 no apply117.
  Não usar seleção de hunk para inventar blob completo em futuros preflights.
- CIf728099 terminal aprovado PR37240507287/push37240503704, seis jobs;
  depois foi publicado checkpoint5438ba9. #36 atualizada sem fechamento.

### Incremento 118 — Image completo do bundle separado

- Compilar em output novo kernel-n71-power-build-20261004 com fonte117,
  config do bundle preservado e somente LOCALVERSION diferente. Guard8GiB,
  metadata fixa de build, Image/DTB/Werror/modpost com logs privados.
- Conferir config embutida, release sem +, símbolos/exports serdev e objetos
  incorporados GPIO/PMGR. Hashes do legado intactos antes/depois e source
  selecionado sem mutações. Preparar modules_prepare sem suprimir erros.
- Até cinco arquivos públicos: plano, docs/N71_KERNEL_BUNDLE.md,
  docs/evidence/kernel-n71-power-bundle-build.json, docs/STATUS.md e
  docs/evidence/kernel-n71-power-bundle.json. Reutilizar gates117 de código.
  Logs/artefatos/config privados; record público só digests/gates/resultados.
- Full link não qualifica energia/Wi-Fi; não selecionar default/boot do iPhone.
  Rebuild módulos/integração de perfil em fatias seguintes antes do boot.

- Pré-Image118: olddefconfig passou e delta de config contém só LOCALVERSION,
  mas kernel.release ainda não existe nesse estágio novo. Script v1 parou
  antes de Image por FileNotFoundError; rollback conferido no finally.
  Retomar output próprio (sem Image/vmlinux) com config exata, executar
  prepare antes da leitura de release e guardar logs novos v2; não repetir
  gate de config nem apagar diretório para esconder erro.

### Incremento 119 — preparar seleção de integração durante o link118

- Trabalho de código independente do resultado da build118: adaptar o
  integrador para profile power explícito, exigindo record completo separado
  kernel-n71-power-bundle-build.json, seis patches/blobs, nova release,
  GPIO/PMGR incorporados e initramfs sem módulos de ABI anterior. Defaults
  e records legados preservados. Composição real depende do gate118.
- Até cinco arquivos: plano, scripts/build/integrate-source-kernel.py,
  tests/test_kernel_integration.py, tests/run_kernel_integration_mutations.py
  e docs/evidence/n71-power-integration-gate.json. Fixture sintética independente
  usa filesystem/processos reais, SSH keys descartáveis; jamais chaves reais.
- Provar seleção explícita, integridade/pins/config/release e recusa de
  módulos antigos antes de criar destino; preservar identidade/source.
  Atualizar três anchors de mutação para predicate selecionado e testar
  guards novos por asserção. Mac/ARM64 com espera limitada, evitando
  repetir Image ou realizar DFU. Nenhuma composição real antes do record118.

- Gate119:17 testes e22 mutações de fonte por asserção aprovados Mac/ARM64,
  com fixtures filesystem/CLI/SSH descartáveis e sem chaves reais. AST/lint
  aprovados, inputs/digests conferidos e logs preservados. Whitelist de
  profile power exige registro de full Image separado; fonte117/objetos não
  substituem essa prova. Composição real continua bloqueada pelo link118
  ainda em andamento, sem acionar o iPhone.

### Incremento 120 — compositor com ABI power explícita

- Até cinco arquivos: plano, scripts/build/compose-n71-diagnostic.py,
  tests/test_n71_diagnostic_payload.py, tests/run_n71_diagnostic_payload_mutations.py
  e docs/evidence/n71-power-diagnostic-gate.json. Somente reconhecer release
 7.2.0-iphone6s-dart-serdev-power1 e seleção explícita do record119; defaults
  e delta DT limitado preservados. Não preparar perfil físico enquanto118
  estiver em build ou usar módulos da ABI anterior.
- Teste positivo das três ABIs registradas e recusa de todos os cruzamentos,
  release com + e desconhecida; arquitetura/vermagic/delta DT permanecem gates.
  Mutação que remove power da whitelist deve falhar por asserção, sem
  mascarar import/syntax/runtime errors. Mac/ARM64 e AST/lint; composição
  real/SSH/snapshot/charger continuam gates físicos separados.

- Primeiro transporte120 omitiu test_n71_runtime_tunables, import transitivo
  da fixture PCI. ARM64 recusou antes de rodar testes; nenhum ERROR contado
  como mutação detectada. Bundle v2 inclui esse arquivo público e preserva
  folder/log v1. Repetir só gate ARM64; gate Mac já cobre dependência local
  inalterada. Não repetir compilação Image por falha de transporte de testes.

- Gate120: cinco testes/seis mutações por asserção aprovados Mac/ARM64;
  três ABIs aceitas e todos os cruzamentos recusados. Payload/delta DT
  preservados; AST/lint e SHA dos inputs/logs aprovados. Falha de transporte
  v1 não contou como kill; só ARM64 foi repetido após fixture completa.
  Perfil real/default/telefone não foram alterados. Link118 continua em curso.
- CI274ae00 aprovado PR37241800486/push37241797831, seis jobs, antes de
  publicar integradorf80e27e. CI desse integrador em acompanhamento.

- Gate118 completo: Image ARM64/16KiB52.070.912B,
  SHA278feceeffcd552dadc23a165f62d3f420199d63d453d457e06d54a36667798e,
  release7.2.0-iphone6s-dart-serdev-power1. Full make/Werror/modpost terminou0
  em761s (12m41s), partindo da configuração preparada após falha v1.
  Fonte intacta, config delta somente LOCALVERSION e config embutida exata.
- Serdev T/export GPL e objetos GPIO/PMGR builtin conferidos; DTB permaneceu
  SHA b25b2b74 igual ao legado. modules_prepare passou sem mudar Image/config/
  exports. Rollback source/config/Image/exports mantido. Tar/outputs/logs
  transferidos conferidos por SHA no Mac e kernel_inputs(power) real aprovado.
  Módulos/perfil/boot físicos continuam pendentes; carga/Wi-Fi não habilitados.

### Incremento 121 — módulos e perfil privado da ABI power

- Até cinco arquivos públicos: plano, docs/N71_KERNEL_BUNDLE.md,
  docs/evidence/n71-power-profile.json, docs/evidence/n71-power-integration-gate.json
  e docs/STATUS.md. Rebuild dos cinco módulos
  públicos existentes em M novo contra source/output118 e exports reais;
  fonte/body inalterados, reutilizar gates de lógica e verificar Werror/
  modpost/ELF/vermagic/SHA novos. Sem provider duplicado, firmware/keys na VM.
- Validar Image/record118, compor perfil base privado novo a partir do
  bundle funcional; preservar initramfs e todas as identidades, não selecionar
  default. Somente o delta DT diagnóstico existente será composto em outro
  perfil com módulo PCIe da nova ABI e run explícito. Conferir digests/
  proveniência/ausência de módulos no initramfs e snapshot local preservado.
- Publicar somente campos selecionados. Nenhum USB, DFU ou ação do iPhone;
  boot/restore/SSH/HTTP e observação I2C1/PMGR dependem de disponibilidade
  física. Charger/Wi-Fi continuam sem qualificação, issues abertas.

- Gate121: cinco módulos da fonte inalterada reconstruídos Werror/modpost
  contra118; ELF/vermagic/SHA conferidos na VM e após transferência. Source/
  Image/config/exports da candidata preservados. Perfil base e diagnóstico
  reais compostos/validados no Mac, todos com modos700/600 e sem USB.
- Initramfs/cliente/known_hosts byte a byte iguais entre legado/base/diag;
  cinco entradas protegidas idênticas, módulo PCIe fora do initramfs sem
  autoload. Snapshot local44 entradas/digest conferido sob lock; restore
  na ABI nova não foi testado. Nenhuma chave/firmware enviado à VM.
- Destino documental do quinto arquivo ajustado de proof diagnóstico para
  STATUS, pois precisa remover a indicação antiga de rebuild/perfil pendentes.
  CI f80e27e aprovado PR37242336144/push37242333300, seis jobs; antes do
  pushc79e0a8. Esse head contém compositor70fc160 e está em acompanhamento.

- CI c79e0a8 aprovado PR37243059356/push37243056409, seis jobs.
  Reprodução de módulos/composição registrada; gates121 de artefatos reais
  continuam separados dos gates físicos ainda não realizados.

### Incremento 122 — preparar uma coleta curta na ABI power

- Até três arquivos públicos: plano, docs/N71_HDQ.md e
  docs/evidence/n71-power-session-gate.json. Adaptar a cópia privada do
  coletor já qualificado apenas nas constantes de release/perfil/hash dos
  dois observadores; preservar o anterior e provar corpo idêntico.
- Selecionar base power sem DT PCIe ativo; observar I2C1/GPIO e PMGR no
  mesmo boot, identidade/boot_id/SSH/HTTP antes/depois, módulos ausentes,
  SHA do stream, load explícito/run e unload/cleanup dentro de120s.
  Snapshot e retorno ao iOS serão etapas subsequentes, sem novo DFU.
- Refazer somente fixtures de transporte externas sucesso, observação
  ausente e ring rotacionado; bash-n dos comandos, nenhuma execução SSH.
  Verificar perfil real e snapshot local sob lock, sem expor identidades.
  Não iniciar boot ou pedir desbloqueio enquanto o aparelho carrega.
- Integrar o registro de full Image/módulos já pronto na documentação
  histórica PMGR; não apresentar preparação como carga física validada.

- Gate122: delta de seis constantes conferido por inversão byte a byte;
  três fixtures externas com bash-n aprovadas, cleanup confirmado e nenhuma
  conexão SSH real. A primeira execução compartilhou namespace entre os
  cenários paralelos e falhou na contagem dos outputs. Runner novo isola
  cada cenário; tentativas v2 preservadas, corpo do coletor inalterado.
- Perfil base real/módulos/SHA/snapshot44 sob lock conferidos; AST/lint
  passaram. Preparação não iniciou boot/USB nem acessou carregador.
  Leitura iOS separada em2026-10-04T23:29:04Z:100%, fonte externa conectada
  e capaz de carregar, BatteryIsCharging=false. Não é leitura de saúde
  nem prova de carga no Linux; nenhum PIN solicitado.

### Incremento 123 — checkpoint físico iOS e CI terminal

- Até quatro arquivos públicos: plano, docs/ALIMENTACAO.md,
  docs/evidence/n71-ios-battery-checkpoint-20261004.json e
  docs/evidence/n71-power-session-gate.json. Registrar somente escalares
  selecionados de GasGauge/AppleARMPMUCharger; logs/identificadores privados.
- Ambas as leituras iOS passaram sem PIN ou escrita:1465 ciclos,
  DesignCapacity1690 e NominalChargeCapacity1130. Razão nominal/projeto
  é estimativa, não saúde oficial nem unidade validada de todos os campos.
  Não atribuir variação/ciclos exclusivamente ao Linux ou ao último boot.
- Conferir SHA da resposta privada, seleção explícita, JSON/links/diff e
  publicguard. Sem teste de código novo; reutilizar CIe0dc355 terminal com
  seis jobs aprovados. Nenhum boot/DFU ou driver físico iniciado.

- Gate123: GasGauge/PMU escalares selecionados, digests da resposta real
  privados conferidos e sem publicação de identidade/raw logs. CIe0dc355
  PR37244353678/push37244350765 terminal success, seis jobs; watchers
  locais22406/32380 terminaram0. Pronto para a sessão única já solicitada;
  disponibilidade física continua pendente, sem repetir pergunta ou boot.

### Incremento 124 — sessão física agrupada da ABI power

- Até cinco arquivos: plano, docs/evidence/n71-power-session-gate.json,
  docs/N71_HDQ.md, docs/ALIMENTACAO.md e docs/STATUS.md. Publicar somente
  amostras GPIO/PMGR e resultados selecionados; logs, boot_id, identidades
  e snapshots continuam privados. Gates de software inalterados reutilizados.
- Um DFU manual com USB-A traseiro: wrapper terminou0, restore44 entradas,
  SSH/HTTP/Herdr passaram na release power1. Ambos os observadores passaram
  SHA remoto/load/unload e mesmo boot/SSH/HTTP antes/depois; staging removido.
  GPIO114/115 estáveis e cache coerente; seis amostras PMGR estáveis.
- Snapshot final verificado, sync e retorno ao iOS por software terminaram0.
  Leituras iOS100% às00:53:51UTC e99% às00:56:31UTC, carga ativa no retorno.
  O intervalo total entre essas leituras foi160s, incluindo DFU/reboot/iOS;
  não mede corrente ou tempo exclusivamente em Linux. Nenhuma escrita
  GPIO/PMGR/I2C/carregador foi executada pelos dois observadores.
- Boot físico das correções builtin qualificado, sem injeção de falha física.
  Próximo avanço: aquisição/restauração do domínio I2C1 e controlador com
  APIs do kernel, antes de acessar SN2400; desenvolver no Mac/VM enquanto
  o aparelho recarrega. Nenhum segundo DFU para repetir observações aprovadas.

### Incremento 125 — ciclo de ownership runtime PM antes do adapter I2C1

- Cinco arquivos: plano, phone/kernel/n71-i2c-power-lifecycle.h,
  tests/n71_i2c_power_lifecycle.c, tests/run_n71_i2c_power_lifecycle_mutations.py
  e .github/workflows/ci.yml. Gate contínuo entra no mesmo incremento de código;
  o JSON público e o procedimento serão registrados na fatia documental126.
  Implementar sequência por
  callbacks qualificados; nenhum controller, pin, domínio ou charger ligado
  por esse header. O backend kernel é uma etapa seguinte.
- Fonte fixada: attach_by_id cria dispositivo virtual sem power_on;
  runtime resume_and_get retorna0 com referência ou erro sem referência.
  Suspend aceita resultado positivo; put_sync_suspend consome uso inclusive
  em erro, logo retry usa suspend
  sem novo decremento. Detach é void, pode falhar e enfileira poweroff;
  callback de detach deve verificar remoção mantendo referência própria.
- Contrato: verificar energia após resume, quiescência antes de detach;
  cleanup pendente desde antes do resume, release de uso exatamente uma vez,
  retry sem reentrada/reattach e erro primário preservado com cleanup_error
  separado. Não liberar objeto/module enquanto ownership pendente.
- Gate C Mac/ARM64, mutações compiladas mortas somente por SIGABRT/asserção,
  objeto __KERNEL__/Werror na ABI power e hashes dos inputs/fontes/provas.
  Não refazer full Image, gates124 ou DFU. Prova física/backend seguem abertos.

- Gate125:12 cenários e13 mutações compiladas morreram por SIGABRT/asserção
  no Mac/ARM64; objeto __KERNEL__/Werror passou na ABI power. Inputs/fontes/
  Image/config/exports preservados e logs transferidos com SHA conferido.
  O transporte local v1 falhou ao concatenar Path/string depois do sucesso
  dos gates; somente a cópia dos três resultados foi repetida, sem novo teste.
  Header não implementa backend genpd, pinctrl ou controller/charger I/O.
- Decisão de arquivo: CI é o quinto arquivo público para que o novo gate
  execute em Ubuntu/macOS; a evidência detalhada fica na próxima fase.

### Incremento 126 — reprodução I2C1 e corrigir corrida de fixture no CI

- Até cinco arquivos: plano, docs/N71_HDQ.md,
  docs/evidence/n71-i2c-power-lifecycle.json, docs/STATUS.md e
  tests/test_return_ios.py. Registrar
  fontes/pins, contrato do backend, comandos e provas125; não implementar
  driver ou mudar critérios físicos pela publicação do header.
- Validar SHA dos inputs/logs reais, JSON/links/diff/publicguard. Reutilizar
  C/mutações Mac/ARM64 e objeto kernel/Werror125. Lint Python local passou
  com ASDF_PYTHON_VERSION=3.12.6 só no processo; path Frameworks não existia
  e shim python3.12 não tinha versão selecionada. Sem instalar ou mudar config.
- CI9d122a7 terminal success PR37249701527/push37249698819, seis jobs.
  CI29e61ec: passo novo lifecycle passou Ubuntu/macOS em ambos os runs;
  PR terminou success, push falhou no baseline antigo de reboot Ubuntu.
  ValueError na leitura de owned.pid vazio revelou publicação não atômica
  da fixture, sem alteração/erro do runtime real. Não registrar push verde.
- Corrigir somente publicação do PID sintético via tmp/close/replace;
  regressão pausa o produtor com o arquivo ainda vazio para verificar que
  o PID final só aparece completo. Mutação que escreve direto no destino
  deve morrer por AssertionError. Rodar regressão/cancelamento no Mac/ARM64
  e gate de reboot afetado; sem novo teste de telefone ou full Image.
- Próximo backend deve manter referências/serialização, verificar domínio
  e remoção apesar de detach void, e reter ownership quando a API não
  comprovar cleanup. Retry do contrato não promete recuperar genpd após erro
  físico. Controller/pinctrl/HDQ/SN2400 ainda não são implementados por ele.

- Gate126: regressão com barreira de escrita e mutação direct-final-path
  morreram por AssertionError no Mac/ARM64; baseline20 testes e11 mutações
  compiladas de reboot passaram em ambas as plataformas. Só a fixture/teste
  mudou; fontes de runtime intactas. Digests/inputs/logs transferidos conferidos.
  Novo CI precisa provar o fix; falha anterior permanece no histórico.

### Incremento 127 — acesso PMGR qualificado compartilhado

- Até cinco arquivos: plano, phone/kernel/n71-pmgr-access.h,
  phone/kernel/n71-pmgr-power-observe.c, tests/n71_pmgr_power_observe.c e
  tests/test_n71_pmgr_power_observe.py. Extrair validação/root/domínio/lock/mapa
  já qualificados para o futuro backend genpd; observador conserva seis
  leituras, logs após sucesso completo e nenhum write/activation.
- API por reference/access: índice e caminhos exatos antes de dereference,
  metadata da cadeia e provider bound sob device_lock; referência própria
  mantém device, lock mantém devm map durante a operação. Unlock limpa
  handle/mapa e é idempotente; handle aberto recusa reentrada. Não guardar
  lock entre tarefas/sysfs calls ou usar mapa depois de unlock.
- Runner compila fonte real do header+observador em conjunto; preservar
  88 cenários/16 mutações existentes e adicionar fronteiras dos handles,
  caminhos/índice, lock simultâneo de providers distintos e cleanup sem
  referências residuais. Mac/ARM64 e novo módulo Werror/modpost da ABI power.
- Helper não reserva domínio/clock, não ativa I2C nem é backend genpd.
  Nenhum novo boot/DFU; artefatos físico124 e source/input históricos intactos.

- Gate127:97 cenários e22 mutações compiladas detectadas por SIGABRT/asserção
  no Mac e Ubuntu ARM64. Módulo W=1/KCFLAGS=-Werror/modpost passou na ABI
  power1; ELF AArch64/vermagic e SHA f420639720001871735879057be41909492983631ea14da8a224c019fe131056 conferidos.
  Image/config/exports e inputs intactos; digests dos logs transferidos
  conferidos. AST/fatal-flake8 e diff passaram; sem typechecker Python
  configurado. O novo helper não foi carregado no telefone.
- CI8974389: PR37251729490/push37251726729 terminaram success, seis jobs
  Ubuntu/macOS/Windows. Issue37 concluída; a falha anterior permanece
  no histórico. Próxima fatia registra evidência e reprodução do helper.


### Incremento 128 — reprodução do acesso PMGR e CI corrigido

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/STATUS.md,
  docs/evidence/n71-pmgr-access.json e docs/evidence/n71-i2c-power-lifecycle.json.
- Registrar gates127/hashes/reprodução, corrigir comando para incluir o
  header compartilhado e manter separadas as provas físicas históricas.
  CI8974389 terminal success nos seis jobs; issue37 concluída. CI152e07b
  em acompanhamento; não afirmar genpd/carga/Wi-Fi pelo build do helper.
- Validar JSON/hash/links/diff/publicguard; reutilizar gates127 inalterados.
  Próxima implementação: backend kernel qualificado de attach/runtime PM/
  detach verificado, ainda sem controlador I2C ou charger I/O.


### Incremento 129 — backend genpd com remoção comprovada

- Quatro arquivos públicos: plano, phone/kernel/n71-i2c-genpd.h,
  tests/n71_i2c_genpd.c e tests/test_n71_i2c_genpd.py. Header implementa os
  callbacks reais do lifecycle125 sobre um consumidor root do caller e
  providers PMGR127. Não cria platform/controller, adapter, pinctrl ou
  cliente I2C e não será carregado no telefone nesta etapa.
- Validar board/consumer I2C1 disabled sem filhos, recurso exato e domínio
  único, referências/metadata da cadeia e providers bound. Locks temporários
  em ordem única protegem cada chamada genpd/runtime PM; nunca retê-los
  entre callbacks. Caller conserva referências/serializa/retém módulo.
- Attach virtual sem power_on; guardar referência própria antes de detach
  void, conferir domínio removido e device unregistered antes de put/limpar.
  Checar estado runtime sob power.lock. Resume/put/suspend preservam contrato
  de uso; detach falho conserva objeto e estado pendente, retry não decrementa
  uso novamente e só admite status suspended real, sem set_status artificial.
- Verificação física pelo regmap bypassed: cadeia tem target active com
  actual active ou auto-PM depois de resume; release exige leaf target/actual
  powergate e auto desativado. Pais podem ser compartilhados: não forçar
  desligamento nem afirmar restauração elétrica por retorno runtime PM.
- Native Mac/ARM64/mutações de guards/referência/uso/detach/estado e objeto
  kernel Werror/modpost contra Image power preservado. AST/fatal-flake8,
  diff/publicguard e CI. Nenhum DFU ou acesso ao carregador nesta fatia.

#### D129. Separar ownership do domínio e controlador

- Decisão: backend em header, consumidor root e referências pertencem ao
  caller; callbacks reais runtime PM/genpd e qualificações N71 testados
  antes do módulo de controller. Pinos/IRQ/clock/I2C permanecem numa etapa
  posterior, antes de qualquer SN2400.
- Por quê: evita autoprobe e permite testar falhas/ownership sem gastar
  bateria ou pedir DFU para validar somente ABI.
- Alternativas: platform I2C desde já poderia acionar controlador/clients;
  writes PMGR diretos ignorariam genpd e consumers compartilhados.
- Reverter: baixo, interface isolada e sem mudança na candidata de boot.
- Onde: incremento129, issue2, backend acima.
- Status: em curso; validação física conjunta posterior.

- Gate129:84 cenários e19 mutações compiladas por SIGABRT/asserção passaram
  Mac/ARM64. Regressão genpd suspend-success/live-leaf mantém pending e
  recusa detach em retry; perda do provider consome o uso por put_noidle
  sem ativação e mantém o domínio para cleanup qualificado posterior.
  Header real/callbacks linkados no gate externo W=1/Werror/modpost;
  ELF/vermagic power1/SHA e11af59c4e8f006a47be5cafa7284c1105c002bd195d74e6077f18326df82fdd conferidos.
  Image/config/exports/inputs preservados, SHA dos logs transferidos iguais.
- Falhas durante desenvolvimento: colisão puts na fixture Mac e warning
  misleading-indentation GCC na fixture ARM64 corrigidos. Gates v1 falhos
  permanecem privados; somente v4 Mac/v2 ARM64 são a prova final. O primeiro
  transporte procurou log de build inexistente após native falhar; v2 copia
  somente logs efetivamente registrados. Nenhuma falha contou como mutation kill.
- AST/fatal-flake8/diff passaram; sem typechecker Python configurado.
  Sem novo boot, sysfs control, hardware activation ou SN2400/charger I/O.
  Backend em header não é módulo operacional de diagnóstico; caller ainda
  deve implementar lifetime/mutex/module retention e operações físicas reunidas.


### Incremento 130 — binding PMGR estável antes de ownership genpd

- Cinco arquivos: plano, phone/kernel/patches/0007-apple-pmgr-no-manual-bind.patch,
  phone/kernel/n71-i2c-genpd.h, tests/n71_i2c_genpd.c e tests/test_n71_i2c_genpd.py.
- A fonte PMGR fixada não tem remove nem suppress_bind_attrs. Device reference
  mantém o device, não seus recursos devm depois de unbind. Locks por callback
  protegem só a chamada; não afirmar que excluem unbind entre acquire/release.
- Patch007 marca suppress_bind_attrs no driver desde o registro, impedindo
  bind/unbind manual via sysfs. Backend recusa provider que não declare essa
  proteção antes de qualquer attach/energia. Providers são builtin no Image
  dedicado; driver_unregister arbitrário por outro código kernel fica fora
  do contrato e não é tratado como recuperação automática.
- Native verifica recusa de provider desprotegido em qualquer uma das três
  posições, sem attach, read ou referência perdida. Mutação retira o guard e
  precisa falhar por asserção. Mac/ARM64; callback/backend kernel Werror;
  patch007 aplica só em cópia do provider006 e arquivo completo obj-y/Werror.
  Profile/power2/Image físico serão integrados depois; não alterar power1.
- Nenhum novo DFU; driver/config/binding do Mac intactos. Não criar módulo
  operacional enquanto o Image carregado não contiver007 e tiver sysfs
  bind/unbind ausentes comprovados na sessão física agrupada.

#### D130. Proteger o lifetime dos providers entre callbacks

- Decisão: suppress_bind_attrs estático e exigido pelo backend; Image power2
  separado antes da operação física. A auto-probe normal permanece possível.
- Por quê: o driver PMGR fixa genpd callbacks em memória devm e não tem
  remoção. Só get_device/device_lock por operação não reserva esse binding
  para todo o lifetime do consumidor virtual.
- Alternativas: um worker mantendo todos os locks seria mais complexo e
  poderia bloquear unbind indefinidamente; confiar só na ausência de ação
  manual deixaria o diagnóstico acessível com um lifetime não protegido.
- Reverter: baixo antes do boot; manter power1/rollback intactos.
- Onde: incremento130, patch007, próxima integração do Image, issue36.
- Status: em curso; proteção runtime ainda não instalada no telefone.

- Gate130:87 cenários/20 mutações compiladas por SIGABRT/asserção passaram
  Mac/ARM64; inclui três recusas de binding não protegido. Backend completo
  linkou W=1/Werror/modpost/ELF/vermagic power1. Patch007 aplicou em cópia
  do provider006 e arquivo inteiro compilou obj-y/Werror, SHA fonte final
  0d84693ae4f5a24df9f8c9499ecd0f8f6725566223428dfe7af686cf7a21f5b2.
  Image/config/exports/provider006 e inputs preservados; logs transferidos
  com SHA conferido. Provider007 não foi integrado ao Image nem carregado.
- CIa476729 PR37253810597/push37253807827 terminal success. Backend130
  exige flag007, portanto deliberadamente recusa operar sobre power1 atual.
  Novo Image/power2 e ausência física de bind/unbind continuam pendentes.


### Incremento 131 — reprodução do backend e condição de binding

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/STATUS.md,
  docs/evidence/n71-i2c-genpd.json e docs/evidence/n71-pmgr-access.json.
- Registrar gates129/130, código/hashes/CI, distinção entre fixture/kernel
  linkage e operação física, erro power-off ignorado por genpd, uso consumido
  em provider loss e lifetime/binding estável exigido. Não afirmar funcionamento
  sobre power1 ou integração007. Cópia de compilação do provider documentada.
- Whitespace da patch007: git --check padrão apontou marcadores de contexto
  unified diff (space+tab e linha vazia), não C gerado. Conferência estrita
  dos demais arquivos passou; check da patch usa configuração só no processo
  excluindo essas regras de formatação de contexto. Nenhuma config Git global.
- Validar JSON/hash/links/diff/publicguard; reutilizar os gates130 sem repetir.
  Próxima fatia: novo profile/power2 preservando001→006/power1 e rollback.


### Incremento 132 — profile power2 sem reaproveitar worktree power1

- Três arquivos: plano, scripts/build/kernel_bundle.py e
  tests/test_kernel_binding_bundle.py. Novo profile n71-dart-serdev-power-v2
  com LOCALVERSION -iphone6s-dart-serdev-power2, patches001→007 e full blob
  PMGR007 fixado. Default e power-v1 permanecem com identidades/hashes antigos.
- Aplicar somente em worktree novo do BASE limpo; não completar uma fonte
  power1 já patchada. Preflight consolidado das sete patches antes de writes;
  SHA/HEAD/files/aliases/staging/external work continuam obrigatórios.
- Testar Git real: conteúdo exato/identidade/report/idempotência, fonte/power1
  preservados, patch007 alterada/late-apply inválido e profile misto recusados,
  CLI reconhece seleção. Mutações compiladas por AssertionError, Mac/ARM64.
- Testar fonte real na VM com worktree/output novos e preparar Image power2
  depois dos gates; não sobrescrever base/power1/bundle/rollback. Sem DFU.

- Gate132:8 testes e6 mutações por AssertionError passaram Mac/ARM64. Helper
  real aplicou sete patches em worktree novo da VM e conferiu full blobs;
  configuração power2 só difere de power1 no LOCALVERSION. Power1 source/
  config/Image/exports e inputs intactos, hashes dos logs transferidos iguais.
- Mutação inicial que transformava preflight em writer também acionou erro
  não tratado num teste legado; não contou como kill válido. Runner agora
  seleciona o contrato correspondente por mutação, exige FAIL/AssertionError
  sem ERROR e nomeia a mudança corretamente como duplicate-apply. Gate final
  completo passou; não afirmar detecção de remoção pura de preflight.
- AST/fatal-flake8/diff passaram; Image power2 ainda não compilado nem físico.


### Incremento 133 — Image completo power2 separado

- Até cinco arquivos públicos de prova/reprodução após sucesso: plano,
  docs/evidence/kernel-n71-binding-build.json, docs/N71_KERNEL_BUNDLE.md,
  docs/STATUS.md e docs/evidence/n71-i2c-genpd.json. Builds/logs/binários privados.
- Usar worktree novo validado132 e output novo power2, sete patches, config
  só com LOCALVERSION diferente. Metadata reproduzível, provider builtin,
  Image/DTB completos Werror/modpost, config embutida/16KiB/serdev export/ELF,
  DTB base igual e modules_prepare. Preservar power1 source/config/Image/exports.
- Transferir artifacts públicos de kernel sem firmware/calibração/chaves,
  conferir SHA e manter700/600. Não selecionar como default, carregar no
  telefone ou afirmar ausência física de sysfs bind/unbind pelo link.
- Somente depois: integrações do profile e módulos/caller de diagnóstico,
  permitindo reunir gates num DFU. Nenhuma intervenção do operador agora.

- Gate133: Image completo power2 terminal0 em1146s, Werror/modpost, ARM64/16KiB, config embutida, GPIO/PMGR builtin, export serdev e DTB preservado; modules_prepare não mudou config/Image/exports. Artefatos/logs transferidos com SHA recalculado no Mac,700/600. Power1 source/config/Image/exports intactos. CIa684 PR37255423107/push37255420563 terminal success, seis jobs. Patch007 está no Image separado; não foi bootado, não há prova física de ausência bind/unbind nem carga/telemetria/Wi-Fi.


### Incremento 134 — integração explícita do Image power2

- Quatro arquivos: plano, scripts/build/integrate-source-kernel.py, tests/test_kernel_binding_integration.py e tests/run_kernel_integration_mutations.py. Selecionar registro kernel-n71-binding-build.json e ABI power2 mantendo os seletores/defaults anteriores.
- Reutilizar todas as validações de hashes/tamanhos/ARM64/config/serdev/base/patches/full blobs; exigir GPIO/PMGR builtin para power2 e recusar módulos de ABI antiga antes de criar output. Preservar initramfs/m1n1/SSH/inputs,700/600, sem USB ou default.
- Cinco contratos adicionais reais de filesystem/CLI com artefatos sintéticos não bootáveis. Runner amplia descoberta para ambos os arquivos e acrescenta três mutações específicas: seletor do registro, providers e módulos antigos de power2. Mantém as22 mutações anteriores; nenhuma compile/import/infra error conta como kill.
- Cópia privada passou22 testes/25 mutações no Mac durante a build. Publicar os mesmos bytes, verificar igualdade e repetir a plataforma ARM64 na VM com inputs públicos. Integrar artefatos reais só depois desses gates; não enviar chaves à VM.

- Gate134:22 testes/25 mutações por AssertionError passaram Mac/ARM64; cópia publicada idêntica à preview testada. AST/fatal-flake8/diff passaram. Primeira chamada flake8 selecionou Python Homebrew sem módulo; resolvido com shim asdf absoluto por processo, sem instalar ou alterar configuração global. Fonte/config/Image/exports power1 e power2 intactos. Integrador real compôs perfil base power2 com initramfs/chave/known_hosts byte a byte iguais ao power1, source preservada e700/600. Nenhum USB/default/boot, firmware ou chave enviada à VM.


### Incremento 135 — controle operacional do ciclo genpd, preparado sem autoload

- Cinco arquivos: plano, phone/kernel/Makefile, novo n71-i2c-power-diagnostic.c, harness C e teste Python. Inicialização só qualifica providers/controller disabled e observa quiescência. Ação explícita cycle liga/verifica/desliga/verifica/detach no mesmo callback; cleanup permite repetir restauração pendente sem novo put. Sem controller/clock/pinctrl/IRQ/adapter/charger I/O.
- Caller possui root consumer e todas as referências OF, mutex por ação, pin de módulo enquanto attached/cleanup_pending. Falha mantém objetos/pin e erro primário; não permite novo cycle até limpar. Remoção forçada não suportada. Parâmetros de ação antes do init são recusados; nenhum ciclo automático ao carregar.
- Refinamento da disposição130: preparar/compilar o módulo antes do boot é necessário para agrupar gates. Não carregar ou executar até a sessão física confirmar o Image power2 e ausência de bind/unbind PMGR; guard exige suppress_bind_attrs no runtime. A candidata permanece arquivo privado fora do initramfs, sem autoload.
- Harness compila o caller real com fixtures das APIs kernel, reutiliza backend real/testado, cobre init/qualificação/referências, comando antecipado/inválido, ciclo íntegro, falhas com cleanup íntegro, cleanup pendente/repetido/detach, refcount e status. Mutações compiladas têm que abortar por asserção, Mac/ARM64; build Werror/modpost/ELF/vermagic contra power2 e fonte/config/Image/exports preservados.

- Gate135:39 cenários/11 mutações compiladas por SIGABRT/asserção passaram Mac/ARM64. Harness inicial reutilizava disable_depth do virtual device já detached no segundo ciclo; fixture agora modela alocação nova com power state limpo por attach. Caller real completo e seis módulos passaram W=1/Werror/modpost/ELF/vermagic power2; source/config/Image/exports preservados. SHA/ELF/vermagic dos módulos e logs recalculados no Mac,700/600. AST/fatal-flake8/diff passaram; nenhum load/USB/DFU ou charger I/O.


### Incremento 136 — compositor diagnóstico aceita somente a ABI power2 selecionada

- Cinco arquivos: plano, scripts/build/compose-n71-diagnostic.py, tests/test_n71_diagnostic_payload.py, runner de mutações e registro n71-i2c-genpd.json. Acrescentar power2 às releases conhecidas/CLI mantendo delta DT/payload/loader/initramfs/identidades e vermagic exatos.
- Teste verifica seleção das quatro releases, todas as combinações cruzadas recusadas e help real da CLI. Oito mutações: seis existentes mais omissão power2 e seletor CLI. Mac/ARM64; composição real só usa DT/módulos privados já compilados, sem autoload/USB/default.
- Registro genpd identifica o novo caller preparado e o gate power1 anterior como histórico; carga/ciclo físico continuam pendentes. Nada de key/firmware/calibração no público ou na VM.

- Gate136:6 testes/8 mutações por AssertionError passaram Mac/ARM64; quatro releases selecionáveis e12 pares cruzados recusados, help real da CLI conferido. AST/fatal-flake8/diff passaram; inputs e fontes/config/Image/exports power1/power2 intactos. Empacotador privado inicialmente tentou literal_eval de Name SUBJECT e a transferência seguinte encontrou arquivo ausente; corrigida resolução literal explícita e etapas dependentes agora têm gate de exit0. Isso não é falha ou kill dos testes; logs/inputs finais transferidos por SHA. Nenhuma ação USB/default ou boot.


### Incremento 137 — reprodução power2 e sessão operacional agrupada

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/N71_KERNEL_BUNDLE.md, docs/STATUS.md e novo docs/evidence/n71-binding-profile.json. Registrar gates134/135/136, hashes/input commits, seis módulos, integração real e perfis separados700/600.
- Documentar comandos de build/integração e cycle/cleanup somente após confirmar release power2 e bind/unbind PMGR ausentes. Não registrar hardware funcional sem coletas físicas; não remover módulo retido com força. Preservar snapshot/mínimo DFU, nenhuma operação do console.
- Atualizar estado: power2 completo/preparado, caller operacional testado e compositor aprovado, ainda não bootado. CI5fa PR37257225731/push37257222417 terminalsuccess seis jobs para integração; caller/compositor aguardam próximo run. Verificar todos os digests/protected modes/JSON/links/publicguard/diff e publicar somente prova/código sanitizados.

- Gate137: composição real do perfil diagnóstico power2 passou; base/diagnóstico mantêm kernel/initramfs/identidades, source e700/600. JSON/provenances,37 inputs e seis módulos conferidos por SHA; links locais e diff estrito passaram. Prova distingue gates sintéticos/build/composição de hardware ainda não testado. Nenhum binário/key/firmware ou dado pessoal incluído no público.


### Incremento 138 — transporte agrupado qualificado e CI concluída

- Cinco arquivos: plano, docs/STATUS.md, docs/N71_HDQ.md, registros n71-binding-profile.json e n71-i2c-genpd.json. Nenhum código de kernel novo. CI6a66ff5 terminou success em PR37258928814/push37258925978, seis jobs; registrar head real, sem atribuir esse run à futura documentação.
- Coletor passivo privado power2 preserva corpo legado após desfazer constantes. Três fixtures SSH (sucesso, marcador ausente, ring rotacionado) passaram;23/12/12 comandos bash-n, estágio próprio removido e nenhuma chamada no telefone.
- Coletor ativo privado qualifica release/placa/boot/SSH/HTTP, ausência bind/unbind e módulos, SHA antes do load; executa dois cycles, recusa conclusão com erro/estado pendente, exige logs novos/unload/consumer ausente. Retry/cleanup limitado; nunca forçar rmmod ou apagar staging sob retenção/boot diferente.
- Gate do coletor: dois comandos bash-n, oito contratos do parser, três guards de unload executados em filesystem Bash temporário e duas mutações mortas por AssertionError. Fixtures não validam todo transporte ou hardware; esse é gate físico pendente. Corrigido guard de boot/state para retorno explícito; não depender apenas de set-e dentro de trap.
- Mac não detectou alvo no IOUSB nem único iOS em libimobiledevice na leitura atual. Consulta inicial ioreg no sandbox falhou; leitura autorizada fora dele executou sem escrita/identificadores e confirmou ausência. Pergunta de reconexão enviada ao operador; nenhum monitor/recovery/DFU iniciado. Não marcar goal completo ou carga/Wi-Fi funcionais.

### Incremento 139 — inspeção I2C1 com reserva MMIO, sem reset/FIFO

- Quatro arquivos: plano, novo phone/kernel/n71-i2c-controller-observe.h, harness C e teste Python. Ler somente REV28, SMSTA14 e XFSTA0c, duas amostras ordenadas, após lifecycle indicar active/attached/usage_held/cleanup_pending e backend ter qualificado o consumer. Reservar exclusivamente20a111000/1000 antes de mapear; liberar mapping/region na ordem inversa em todas as saídas.
- Não habilitar DT, adapter, clock, IRQ ou pinctrl; não ler FIFO04 nem escrever CTL1c/IMASK18/SMSTA14/FIFO00. A fonte fixada usa REV no probe, SMSTA em polling e XFSTA no diagnóstico; isso justifica os três offsets. Ligar genpd continua sendo ação ativa e o resultado não qualifica ownership dos pinos, restauração de CTL/IMASK, I/O SN2400 ou carga.
- Recusar argumentos/power state incorretos, recurso diferente, region ocupada, mapping ausente e leituras all-ones. Classificar stable/idle como observação apenas: estabilidade dos três words e ausência dos flags de erro/busy/FIFO RX, com MTE presente, nas duas amostras. Não tratar idle como permissão para reset ou transação.
- Fixtures exercitam header real com APIs kernel limitadas e verificam ausência de reads antes da reserva/power, somente seis reads nos offsets permitidos e limpeza observável. Mutações compiladas devem morrer por SIGABRT/asserção, nunca por erro de compilação. Em fatia seguinte integrar ação explícita inspect ao caller já existente, com cleanup genpd obrigatório mesmo se a inspeção falhar.
- CI30d2b568 terminou success: PR37260217267 e push37260212842; três jobs cada. USB novamente sem alvo/iOS. Parser inicial supôs raiz plist em lista e falhou antes de concluir; versão corrigida aceita dict/list e a leitura real confirmou ausência. Nenhuma intervenção física executada.

- Gate139 local:37 cenários/18 mutações compiladas morreram por SIGABRT/asserção no Mac; AST/fatal-flake8 passaram. Primeiro fixture deslocava start sem end, permitindo que o guard de size mascarasse a mutação de base; corrigido deslocamento do intervalo inteiro. Mutação de type inicialmente falhou na compilação por helper da fixture sem uso: anotado unused, recompilado e exigido SIGABRT. Nenhum desses resultados iniciais foi contabilizado como kill. Ubuntu ARM64/build operacional pertencem à próxima integração; nada executado no aparelho.

### Incremento 140 — ação inspect no caller operacional

- Cinco arquivos: plano, n71-i2c-power-diagnostic.c, harness C e runner Python existentes e fixture139. Acrescentar inspect explícito, sem autoload, sob o mesmo mutex/refcount/ciclo de energia. Exigir genpd adquirido e verificado antes da reserva/leitura MMIO; executar release genpd mesmo quando inspeção falhar, mantendo o erro primário e cleanup_error independente. Corrigir somente a disposição de ifs da fixture139 para GCC Werror: ARM64 detectou misleading-indentation em cinco linhas antes de executar a baseline; separar os ifs, preservando asserções e lógica.
- Preservar cycle/cleanup/status; nova coleta identifica amostras/complete/stable/idle_status/error sem declarar adapter/pinos/carga prontos. Ocupação MMIO, mapping falho, all-ones, instabilidade e falha de cleanup são exercitados pelo caller/header/backend reais juntos.
- Reusar fixture139 de MMIO e backend genpd existente, somente os stubs de APIs kernel. Todos os mutants devem compilar e abortar por asserção; Mac/Ubuntu ARM64 e módulo real W=1/Werror/modpost/ELF/vermagic power2. Preservar fonte/config/Image/exports e o módulo anterior para rollback. Não executar inspect no telefone antes de boot/release/binding e cycle físicos passarem no mesmo boot.

- Gate140:52 cenários/14 mutações do caller e37/18 do observador passaram no Mac/Ubuntu ARM64, com SIGABRT/asserção e compilação Werror. Seis módulos passaram W=1/KCFLAGS-Werror/modpost/ELF/vermagic power2, fonte/config/Image/exports intactos; hashes/ELF/vermagic recalculados no Mac,700/600. Log de sucesso do wrapper VM herdou a palavra mutations=11; JSON e log nativo conferidos independentemente provam14, não reutilizar esse resumo textual como contagem. Fix ARM64 foi apenas layout de ifs da fixture; nova cópia v2 conserva log da falha v1. Empacotador privado inicialmente recusou count de substituição v1 porque incluía o import do bundle preservado; corrigidas apenas as três identidades da coleta, sem trocar a referência do bundle. AST/lint/diff passaram; nenhum boot/load/MMIO no aparelho.

### Incremento 141 — reprodução e coleta conjunta sem novo DFU

- Cinco arquivos: plano, docs/N71_HDQ.md, docs/STATUS.md, novo registro n71-i2c-controller-inspection.json e registro genpd existente. Fixar commits186f73e/14117a4, hashes40 inputs/six modules/logs e provas37/18+52/14 Mac/ARM64. Não confundir código/build/fixtures com operação física.
- Coletor privado atual seleciona o módulo novo, roda dois cycles íntegros antes de inspect no mesmo boot e confere registro fresco/estado/release/boot/cleanup. Parser recalcula stable/idle_status pelas seis words; somente observação, sem autorização de I/O. O corpo do guard de unload anterior é idêntico; mantém erro/retention e staging se incompleto.
- Qualificação limitada:16 contratos de resultado, dois comandos bash-n, cinco cenários Bash em filesystem temporário (íntegro, ciclo recusado/pendente e inspeção recusada/pendente), duas mutações do guard por AssertionError. Fixture inicial não criava o pai da pasta simulada do módulo; mkdir-p restrito ao tempfile corrigiu o preparo, sem alterar o coletor. Nenhum SSH/hardware/privilegiamento do Mac nessa verificação; transporte completo segue gate físico.
- Documentar reprodução nativa e kernel e os comandos futuros da ação inspect pelo Mac, incluindo necessidade de cycle/quiescência/binding físicos antes dela. Preservar o módulo e coletor anteriores; não alterar perfil default/initramfs. Gates JSON/hash/links/publictree/diff, commit/push da branch já autorizada e comentário #2/#36 com limites; não fechar issues, merge/tag/release ou goal.

- Gate141: JSON/provenance/40 inputs/6 módulos/coletores conferidos por SHA; physical false, caminhos de documentos e AST/lint/diff passaram. Coletores e dados de perfil permanecem privados; comandos de reprodução e fontes/provas sanitizadas públicos. Nenhum novo pacote/configuração global, nova senha/PIN, monitor/DFU, reboot ou I/O físico nesta rodada. CI novo seguirá a publicação; os seis jobs de30d2 foram verificados como evidência anterior, sem atribuição às alterações139/140.

### Incremento 142 — módulos Wi-Fi na ABI power2, sem trocar Image

- Até cinco arquivos: plano, scripts/build/build-n71-wifi-modules.py, tests/test_n71_wifi_modules.py, runner de mutações e registro público de build em fatia seguinte. Builder atual só aceita n71-dart-serdev-v1/7.2.0-iphone6s-dart-serdev1; módulos dessa ABI não podem ser carregados em power2. Acrescentar seleção explícita de n71-dart-serdev-power-v2, com a release e os três hashes reais fixados pela prova do Image power2. Default legado e seus hashes permanecem iguais; não aceitar perfil desconhecido nem relaxar checks.
- Propagar o perfil para inspeção da fonte, checks antes/depois, ELF/vermagic e provenance; preservar escopo das macros PCIe/MSGBUF, dependências, modpost fatal, owned/new paths, orçamento1GiB e nenhum install/load/firmware. Testes exigem identidade independente, pares ABI cruzados recusados, hashes por perfil, CLI real/help e recusa de perfil desconhecido; mutações têm que falhar por AssertionError, nunca import/compile errors.
- Rodar gates Mac/Ubuntu ARM64 na VM dedicada, compilar oito módulos em pasta nova somente contra o output power2 preservado, conferir símbolos/alias/class/dependências/hashes/ELF/vermagic e trazer artefatos privados ao Mac700/600. O Image e os módulos Wi-Fi anteriores ficam intactos. Sem USB, DFU ou firmware. Documentar gates/evidência/publicação após o build; Wi-Fi funcional continua dependente dos gates físicos PCIe/DART/IRQ/firmware.
- CI6e37876 concluiu success em PR37263273839/push37263270142, seis jobs. Logs Mac/Ubuntu dos jobs111614767146/111614767257 confirmaram observador37/18 e caller52/14; registros/hashes privados salvos. USB continua sem iPhone/DFU/Recovery/Pongo/Linux, mas a lacuna real de ABI Wi-Fi permite este avanço offline; não marcar goal blocked enquanto há trabalho alinhado disponível.

- Gate142:12 testes/17 mutações por AssertionError passaram Mac/Ubuntu ARM64, sem import/compile errors usados como kills. Seleção literal dos hashes/releases, pares ABI cruzados, CLI real e default legado conferidos. Oito módulos rfkill/cfg80211/Broadcom passaram Werror/modpost/ELF/vermagic power2, símbolo PCIe/MSGBUF e alias14e4:43a3 class02:80, dependências completas e SHA; artefatos recalculados no Mac700/600. Fonte/config/Image/exports power2 e legado preservados,12 inputs íntegros. AST/fatal-flake8/diff passaram. Nenhum firmware, load/install, USB, DFU ou reboot; prova pública/runbook serão registrados na próxima fatia.

### Incremento 143 — reprodução e prova dos módulos Wi-Fi power2

- Quatro arquivos: plano, docs/evidence/n71-wifi-binding-modules.json, docs/N71_LINK_EXPERIMENT.md e docs/STATUS.md. Publicar somente metadata/hashes sanitizados do build real142; manter registro legado separado. Fixar commit3ce8aaf, perfil/release/Image,12 inputs, oito módulos/dependências, logs/gates Mac/ARM64 e preservação dos dois kernels. Binários, logs brutos, firmware e identidades permanecem privados.
- Documentar CLI explícita power2 com output novo, ordem de dependências e ausência de autoload; não transformar ABI/alias compilados em prova de PCIe/DART/IRQ/chip/firmware/Wi-Fi. Fonte/config/Image/exports devem permanecer iguais e default legado não muda. Acrescentar CI6e37876 terminal como prova anterior do I2C, sem atribuí-la ao builder142.
- Conferir JSON contra artefatos/inputs por SHA, ELF/vermagic/dependências e links; reusar12/17 Mac/ARM64 válidos, sem repetir compilação. Publictree/diff, commit/push da branch autorizada e comentários #9/#2/#36; nenhum merge/tag/release. Novo DFU apenas quando o USB reaparecer e houver coleta agrupada pronta; sem PIN, temperatura ou contagem repetida.

- Gate143: JSON comparado ao provenance privado,12 inputs/tamanhos/SHA e oito módulos ELF/vermagic/dependências conferidos, links/AST/publictree/diff íntegros. Reutilizados os12/17 Mac/ARM64 e build142, sem alterações em suas dependências; documentação distingue evidência offline e física. ioreg e system_profiler não encontraram nome/modo do alvo; libimobiledevice zero iOS. Nenhum monitor, recovery, DFU ou I/O no aparelho foi iniciado nesta rodada; reconexão física segue pendente.

### Incremento 144 — coletor Wi-Fi qualifica a ABI power2 antes do DFU

- Quatro arquivos: plano, scripts/host/n71-link-session.py, tests/test_n71_link_session.py e runner de mutações existente. O coletor exige atualmente release/patchset legados, portanto recusaria o perfil power2 mesmo com módulos corretos. Qualificar exatamente os dois pares patchset/release/payload; propagar release para ELF, preflight, resultado e histórico de continuação. Não aceitar power1/perfil desconhecido nem histórico da outra ABI.
- Para power2, usar somente os dois hashes/sizes/vermagic PCIe/REG_ON compilados no registro n71-binding-profile.json, conferindo flags Werror/modpost e a identidade do perfil diagnóstico. O mesmo módulo PCIe atual contém os modos já existentes; conservar exclusividade, seleção explícita, fresh logs, limites e cleanup. Módulos Broadcom de142 permanecem fora do coletor e não serão carregados. Default e registros legados seguem iguais.
- Testar pares de identidade cruzados, provenance/payload divergentes, módulo ABI errado, seleção de registros/modos, preflight real com transporte simulado e CLI check/continuação sem SSH. Mutantes precisam morrer por AssertionError, sem import/compile errors. Reutilizar build kernel/módulos idênticos; conferir capacidades/modos dos dois binários power2 e preparar perfil privado novo com mesmos payload/initramfs/keys e o módulo REG_ON adicional. Gate check local/AST/lint/publictree e Mac/Ubuntu ARM64; nenhum boot/USB/DFU para esta correção.

- Gate144:31 testes/26 mutações por AssertionError passaram Mac/Ubuntu ARM64;23 inputs preservados. CLI check real selecionou seis modos sem SSH/USB; dart-cycle sem histórico do mesmo boot foi recusado. Perfil privado novo preserva byte a byte os sete arquivos anteriores e adiciona apenas REG_ON qualificado; hashes e parâmetros de oito modos PCIe conferidos nos binários compilados. Primeiro teste de seleção tinha keyword config_inventory duplicada no fixture; corrigida a composição do dict antes de contabilizar sucesso. Módulos sintéticos do teste CLI agora têm hashes distintos para exigir a ligação ao PCIe certo. AST/fatal-flake8/diff íntegros; nenhum kernel/módulo recompilado e nenhum comando no aparelho. CI38c5df6 anterior terminou success em PR37265593416/push37265590595, seis jobs; não atribuí-la a144.

### Incremento 145 — runbook da continuação power2 sem novo boot

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e docs/evidence/n71-link-binding-session.json. Registrar commitdfad0ff,23 inputs,31/26 Mac/ARM64 e os gates reais do perfil privado; nenhuma chave, módulo ou log bruto publicado. Referenciar módulo PCIe/REG_ON power2 já compilado e registrar que payload/initramfs/identidades e perfil anterior foram preservados.
- Explicar a seleção automática pela provenance de um perfil explicitamente passado, cópia do módulo REG_ON adicional e comandos check antes do DFU. Documentar continuação por histórico fresco/mesmo boot, ABI antiga recusada e os gates específicos de cada modo, sem prometer rádio/DMA/carga funcionais. Nenhum módulo Broadcom carregado pelo coletor.
- Reusar testes/build idênticos; validar JSON/SHA/provenance/links/AST/lint/publictree/diff, commit/push autorizado e #9. CI38c5df6 concluída é evidência anterior; acompanhar CI do novo head. Se USB continuar ausente após todas as preparações necessárias e gates finais, registrar o bloqueio externo do goal; não inventar prova física nem repetir DFU/PIN/temperatura.

- Gate145: prova pública bate com23 inputs, logs e perfis privados;31/26 Mac/ARM64 reutilizados pois fontes/dependências/artefatos não mudaram. Seis checks locais e recusa de ciclo sem histórico documentados, limites físicos false e links/AST/fatal-flake8/diff íntegros. Registro e runbook não publicam binários/logs brutos/identidades. CI anterior38c5df6 confirmada por head e seis jobs success. Nenhuma ação no telefone; a coleta power2 preparada depende de reconexão USB.

### Incremento 146 — primeira sessão física power2 agrupada

- Cinco arquivos: plano, docs/STATUS.md, docs/N71_HDQ.md, docs/N71_LINK_EXPERIMENT.md e docs/evidence/n71-power2-first-physical.json. Registrar o boot/restore real do head70d4736, observadores passivos, ausência de bind/unbind PMGR, dois ciclos genpd e inspeção estável/idle do controlador, com limpeza e mesmo boot comprovados. Publicar apenas seleção sanitizada e hashes; logs integrais, UUID, perfis/identidades e snapshots permanecem privados.
- Continuar sem novo boot entre descoberta PCIe, chip/BARs, observação/ciclo DART e scan PCI. Endpoint43a314e4, BCM4350rev8 e restauração dos16 words DART passaram. O scan permaneceu negativo: primeira recusa root0:08/0a0/word/value2; as recusas posteriores são latched, não uma lista de permissões necessárias. Capturar controles medidos, contagens, restauração, módulos/PCI ausentes e SSH/HTTP/Herdr finais.
- Snapshot validado, sync e retorno ao iOS por software passaram; leitura iOS91→81% e carga ativa no retorno. Percentual inclui transições e não mede saúde, corrente líquida nem carga Linux. Nenhum driver Broadcom, firmware, IRQdelivery, DMA, transferência I2C ou comando SN2400 nesta sessão. Próximo desenvolvimento offline qualifica a primeira recusa real; nenhum DFU para apenas registrar a evidência.
- Reusar gates de código/artefatos inalterados e CI70d4736 success em seis jobs. Conferir SHA dos resultados/logs/módulos, igualdade de boot, JSON, links, publictree/diff; commit/push autorizado e comentários #2/#9/#34/#36, mantendo critérios funcionais abertos. Não merge/tag/release nem marcar goal completo.

- Gate146: cinco modos PCIe tiveram boot SHA idêntico aos observadores/caller/final; todos cleanup íntegro, scan negativo preservado. Prova gerada dos resultados privados, contagens e primeira recusa conferidas, snapshot44 entradas/SHA validado sob lock. JSON/links/diff passaram; fontes/builds não mudaram, portanto gates nativos/CI70d4736 foram reutilizados. O primeiro gerador privado tratou o retorno de load_snapshot como manifesto; corrigido para archive/members e leitura do manifesto sob o mesmo lock, sem modificar snapshot ou telefone. Nenhum dado privado/firmware/binário incluído na árvore pública; próxima correção será offline, mantendo iOS em recarga.

### Incremento 147 — contrato temporário do target PCIe, sem retrain

- Quatro arquivos: plano, novo phone/kernel/n71-pcie-scan-link-target.h, tests/n71_pcie_scan_link_target.c e tests/test_n71_pcie_scan_link_target.py. A fonte fixada comprova pci_device_add → pcie_failed_link_retrain → pcie_set_target_speed → alteração TLS + retrain. Não liberar apenas o primeiro pedido0a0 nem emular valores de hardware. Preparar helper separado, ainda sem integrar/carregar, para ajustar temporariamente TLS1→2 antes do scan; com DLLLA ativo e TLS2, o quirk não solicita levantar o limite1. O helper não escreve LNKCTL/retrain, status W1C ou capabilities.
- Exigir root Apple1004, class/header/buses, COMMAND decode/master off, PCIe v2/root-port na capability70 alcançável/única em lista limitada, LNKCAP max2/reporting, LNKCTL0, LNKSTA DLLLA/Gen1 sem training e LNKCTL2 original1. Conferir snapshot fresco antes da única escrita word2 em0a0 e readback/estado de link iguais depois. Uma falha de escrita pode ter efeito: marcar restauração pendente antes da tentativa, manter erro e obrigar cleanup explícito.
- Cleanup só altera TLS2→original1 em root/estado ainda qualificados, confere readback e preserva obrigação em erro. Não restaura por uma identidade/região desconhecida. O caller futuro precisa remover PCI/core antes desse cleanup e conservar ownership se ele falhar; este helper não registra barramento, cria provider ou promete operação física. Testes reais de I/O simulado exigem bytes vizinhos preservados, falta de retrain, limite/loop/capability/board/scoping, falhas de reads/writes/readback e retry sem nova escrita se já restaurado.
- Gates nativos Mac/Ubuntu ARM64 e mutações compiladas por SIGABRT/asserção; objeto/módulo de contrato na ABI power2, sem novo Image/instalação/load. Registrar fontes primárias/hashes e limites em fatia documental seguinte. A decisão é temporária e reversível; alternativa de permitir o retrain do core exigiria controlar mais operações, link e rollback ainda não qualificados. Wi-Fi e carga continuam abertos; nenhum DFU nesta implementação.

- Gate147: dois testes nativos e21 mutações compiladas por SIGABRT/asserção passaram Mac/Ubuntu ARM64. Regressões exercitam a word TLS, estado de link, capability/vector (6 ou fallback0), cada falha de leitura antes/depois da escrita/restauração, erro com efeito físico, obrigação retida e retry sem duplicar escrita. Módulo de contrato6432 bytes passou W=1/KCFLAGS-Werror/modpost/ELF/vermagic power2; inputs/logs/ELF recalculados no Mac. Image/config/exports e fontes PCI preservados. AST/fatal-flake8/diff íntegros. Helper não foi integrado ao scan, carregado no iPhone nem contado como correção física; mudanças posteriores do core continuam recusadas. Publicação documental/hash em fatia seguinte.

### Incremento 148 — prova e reprodução do helper separado

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e docs/evidence/n71-pcie-scan-link-target.json. Registrar commita548fda, cinco inputs idênticos Mac/VM, dois testes/21 mutações, módulo de contrato e fontes PCI fixadas por SHA/linhas. Preservar a sessão física146 como prova distinta; helper separado não resolve por si só o scan, IRQ, DMA ou firmware.
- Documentar reprodução nativa/compilação, a razão para target temporário e os gates de integração: callbacks/devices removidos antes de restore, root/decode qualificados e ownership/MMIO/energia/módulo retidos quando pending. Não inserir um helper com cleanup pendente em caller que libera incondicionalmente seus recursos. LNKCAP2/vector/headers/estado frescos ainda precisarão de prova no aparelho.
- Reusar gates147 inalterados, conferir JSON/inputs/logs/ELF/links/publictree/diff e registrar avisos modpost do módulo de contrato (Module.symvers global ausente com vmlinux.symvers fornecido; MODULE_DESCRIPTION ausente). Não são falhas de compilação/mutação nem um módulo operacional. Commit/push e comentário#9 já autorizados, sem novo DFU ou instalação/configuração global. CI vinculada ao novo head será acompanhada separadamente.

- Gate148: JSON bate com cinco inputs, logs nativos/compilação e ELF/vermagic/SHA reais; todos os limites físicos/integrados false. Referências locais e dois blocos do runbook passaram links/bash-n/diff. Reutilizados dois testes/21 mutações de147 nas duas plataformas, com código e inputs idênticos; nenhum build/load/reboot novo para documentação. A receita mostra a translation unit exata e checagem before/after de config/Image/exports, sem install. Integração com retenção do caller e scan completo continuam próximos passos, sem confundir contrato compilado com Wi-Fi funcional.

### Incremento 149 — target temporário no scan com cleanup retido

- Cinco arquivos: plano, phone/kernel/n71-pcie-scan.h, n71-pcie-mmio.h, tests/n71_pcie_scan_host.c e test_n71_pcie_scan_host.py. Integrar o helper147 sem alterar sua política: target real1→2 antes do PCI core e2→1 somente depois de stop/remove. Manter acesso PCI genérico restrito e nenhuma escrita LNKCTL/retrain.
- Guardar bridge/config/target no estado persistente; cleanup só libera o bridge quando config e TLS tiverem readback íntegro. Falha mantém ponteiro/obrigação para retry explícito, recusa outro scan e conserva erro primário. Remover também bus parcialmente registrado numa falha do core. Esta fatia ainda não qualifica o caller externo: não carregar o módulo antes de150.
- Fixture executa os headers reais e modela MMIO/PCI core: target2 observado pelo core, vizinhos preservados, restauração depois da remoção, falhas de prepare/restore/config, retry sem novo scan e retenção de allocation. Cada mutante precisa compilar e morrer por SIGABRT/asserção; Mac/ARM64. Caller externo e build operacional seguem150; nenhum DFU agora.

- Gate149 Mac:21 cenários e13 mutações compiladas por SIGABRT/asserção passaram; bridge/config/TLS permanecem retidos em falha e cleanup posterior libera sem novo scan. AST/fatal-flake8/diff passaram. Ubuntu ARM64 e build conjunto seguem150; caller externo ainda não qualificado, sem load/DFU. O resultado final conserva erro primário; contagens são amostradas antes do cleanup e identificadas no log.

### Incremento 150 — ownership persistente no caller operacional

- Cinco arquivos: plano, phone/kernel/n71-pcie-diagnostic.c, n71-pcie-mmio.h, tests/n71_pcie_diagnostic_caller.c e test_n71_pcie_diagnostic_caller.py. Executar o caller real com dependências kernel/scan simuladas e backend MMIO real; o scan real é qualificado separadamente149. Estado não pode ficar na stack do probe. Desabilitar bind/unbind, serializar ações e conservar módulo/devres/energia/reset enquanto o scan estiver pendente; ação cleanup não executa novo scan.
- Só liberar o pin após cleanup completo; status deve distinguir erro primário e erro de limpeza. Recusar ação precoce/concorrente e outro dispositivo. Gates do caller real/lifecycle, mutações compiladas, módulos Werror/modpost/ARM64/vermagic power2 em output privado separado, Image/config/exports preservados.
- Documentar/pin/compor coletor numa fatia posterior, ainda sem autoload/default. Candidata física apenas após gates completos e coleta agrupada pronta. Wi-Fi/carga seguem pendentes.

- Gate150: caller real67 cenários/18 mutações compiladas por SIGABRT/asserção e scan real21/13 passaram no Mac e Ubuntu ARM64. Módulo operacional PCIe69976 bytes e seis módulos passaram W=1/KCFLAGS-Werror/modpost/ELF/vermagic power2;40 inputs e fonte/config/Image/exports preservados, SHA/ELF/vermagic recalculados no Mac700/600. Mutation inicialmente sobreviveu porque erro negativo e status ativo tinham o mesmo resultado; acrescentado caso put negativo após suspender, que prova preservação do erro e retry sem segundo put. Erros iniciais de compilação dos mutantes por funções não referenciadas/parentheses não foram kills. Caller guarda estado em devres, bloqueia bind/unbind/segundo dispositivo e mantém pin/energia/reset em cleanup pendente. AST/fatal-flake8/diff passaram; nenhuma ação no telefone. Coletor precisa impedir também release do REG_ON sob retenção antes de carregar esta candidata.

### Incremento 151 — prova/reprodução da integração operacional

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e docs/evidence/n71-pcie-scan-target-build.json. Fixar commits149/150,40 inputs, logs/SHA, seis módulos e módulos selecionados PCIe novo/REG_ON preservado. Distinguir scan/caller simulados complementares, build real e ausência de load físico.
- Documentar action/status/retention, referência de uso não duplicada, GPIO readback e ciclo sem novo Image/DFU. Manter snapshots/perfis anteriores/default; nenhum firmware/key/dump/log bruto no público. CI fcee anterior passou seis jobs, sem atribuição à integração nova.
- Reusar gates149/150 idênticos, JSON/SHA/ELF/vermagic/links/diff/publictree e bash-n das receitas. O coletor antigo libera REG_ON após erro PCIe: corrigir antes de selecionar/carregar esta candidata; obrigação no mesmo boot, sem force unload. Publicação na branch autorizada; sem main/merge/tag/release.

### Incremento 152 — coletor respeita a retenção no mesmo boot

- Cinco arquivos: plano, scripts/host/n71-link-session.py, novo n71_scan_target_result.py, tests/test_n71_link_session.py e runner de mutações. Seleção explícita --scan-link-target exige host-scan/power2, registro151 e provenance correspondente; defaults/módulos anteriores preservados. Nenhum driver Broadcom/firmware, DT/Image ou autoload novo.
- Novo contrato valida status vivo único, logs de prepare/restore/cleanup e a anotação de contagens antes do cleanup, sem alterar leituras/config. Retry máximo de um action=cleanup, com release/boot iguais e bind/unbind ausentes; recusar unload/REG_ON release se limpeza não comprovada. Guard REG_ON aplica-se também aos modos antigos quando PCIe cleanup falha. Logs/staging ficam conservados, erro primário não vira sucesso.
- Fixtures exercitam seleção/ABI/provenance e CLI check reais sem SSH; transporte simulado cobre sucesso, pending/retry/timeout/status errado/boot trocado, falha PCI/REG_ON e ausência de release sob retenção. Mutações só contam AssertionError; preparar perfil privado novo com módulo151, mesmos payload/DT/initramfs/identidades e700/600 após Mac/Ubuntu ARM64/lint. Nenhum novo DFU até a candidata/coleta estarem qualificadas.

- Gate152:36 testes e45 mutações por AssertionError, sem ERROR de import/compilação, passaram Mac/Ubuntu ARM64;25 inputs idênticos antes/depois,10 comandos gerados passaram bash-n e config/Image/exports da VM preservados. A mutation final-config inicialmente sobreviveu porque o parser de sucesso recusava por outro guard; a regressão agora prova que o fluxo de cleanup também conserva REG_ON sob config/TLS/bus removal incompletos. AST/fatal-flake8/diff passaram. Perfil privado separado com PCIe69976 bytes e REG_ON17688 preservado passou CLI --host-scan --scan-link-target --check real, incluindo payload/initramfs/identidades; default não alterado, nenhuma ação USB/SSH. Reutilizados gates C149/150 com inputs inalterados; ainda sem scan físico/Wi-Fi/carga comprovados. Documentação/prova pública seguem153.

### Incremento 153 — reprodução do coletor e candidata selecionada

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e novo docs/evidence/n71-scan-target-session.json. Fixar commit152/25 inputs,36 testes/45 mutações nas duas plataformas, hashes de logs,10 comandos bash-n e preflight real do perfil separado. Reusar C/build151 sem recompilar; nenhuma seleção default/firmware/instalação global ou novo Image.
- Receita documenta opt-in --host-scan --scan-link-target e provenance, conservando identidades/REG_ON e delimitando uma ação cleanup no mesmo boot. Publicar só contratos/hashes/booleanos; logs, chaves, perfis e dados do telefone seguem privados. CI096d69a passou seis jobs e cobre151, não152/153; vincular nova CI ao head publicado depois. Issues#2/#9 continuam funcionais abertas.
- Gates JSON/inputs/logs/provenance, receitas bash-n/Python AST, links/diff/publictree; publicação branch autorizada. Só depois reconfirmar USB/bateria para sessão física agrupada. Capability/link real, scan completo, IRQ/DMA/firmware/Wi-Fi e carga continuam pendentes até medição física; não fechar issue por gate offline.

- Gate153: JSON25 inputs e logs Mac/ARM64/preflight conferidos por SHA; três receitas passaram bash-n e Python embutido passou AST, links locais dos dois documentos e diff íntegros. Novo perfil e artefatos continuam privados700/600; registro só inclui contratos/hashes/limites, sem UUID/key/log bruto. Gates152 e C/build151 reutilizados, sem recompilar/DFU/SSH. CI anterior096d69a success explicitamente separada do coletor novo; CI do head final será acompanhada e publicada na issue. Próximo gate físico exige USB/bateria reconfirmados, com sessão agrupada e sem reinícios intermediários quando cleanup passar.

### Incremento 154 — sessão física única da candidata de scan

- Operação delimitada, sem mudança de driver: um boot do perfil privado153 com restore do snapshot44, SSH/HTTP/Herdr e coleta inicial de energia/estado; em seguida um scan com --host-scan --scan-link-target, retry/cleanup integrado e provas frescas do mesmo boot. Preservar o boot para próximos passos já qualificados quando cleanup passar; não repetir DFU para coleções por SSH. Limite de sessão e snapshot/sync antes do retorno para recarga enquanto carga Linux não estiver comprovada.
- Pré-condições: CI PR37330736713 do headd045d24 passou os três jobs; job push Ubuntu falhou em dois testes antigos de return_ios (timeout/backup ausente), ambos passaram isoladamente na VM e20 testes passaram no Mac sem mudanças. Repetido somente o job que falhou, com prova distinta/pêndencia de intermitência; não atribuir esse erro ao coletor novo nem ocultá-lo. USB/modelo/bateria devem ser reconfirmados imediatamente antes do boot. Operador confirmou disponibilidade; manter USB-A traseiro, sem PIN/contador/temperatura.
- Até quatro arquivos públicos depois da coleta: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e prova sanitizada própria. Registros brutos/UUID/perfis/snapshot ficam privados. Falha conserva primary error, ownership/REG_ON/staging e logs; não repetir scan, não force unload/driver bind/retrain/rádio/DMA/firmware. Registrar campos realmente medidos, limites e pendências nas issues; implementação do próximo gate continua com base na observação.

### Incremento 155 — cleanup de probe negativo já desvinculado

- Quatro arquivos: plano, scripts/host/n71_scan_target_result.py, tests/test_n71_link_session.py e runner de mutações. O scan físico preparou/restaurou TLS, removeu bus/config, reset/power e caller sem retenção; primary=-1 pela primeira recusa root044/word8008. Probe retorna erro somente após cleanup completo e deixa status ready0. O coletor conservou REG_ON porque confundia esse caso negativo limpo com scan bem-sucedido sem owner.
- Aceitar ready0 com scan apenas quando resultado estritamente negativo, erro primário do último cleanup igual ao scan e todos os campos/provas finais limpos. Continuar recusando sucesso ready0, erro incoerente, logs incompletos ou retenção. Não apagar o erro do experimento. Fixture reproduz o estado físico e comprova liberação somente depois dessas provas; mutações por AssertionError. Mac/ARM64, inputs e logs privados; módulos/Image/gates C preservados.
- Aplicar a classificação qualificada à recuperação explícita do mesmo boot: conferir release/UUID/status vivo, logs frescos e pci vazio, unload normal, depois restore/unload REG_ON. Nenhum outro scan, permissão PCI, escrita TLS/W1C/charger/rádio/IRQ/DMA ou DFU. Guardar resultado original recusado e recuperação separados; retornar ao iOS só após snapshot/sync e término da coleta delimitada.

- Gate155:37 testes/47 mutações por AssertionError passaram Mac/Ubuntu ARM64,25 inputs/logs conferidos por SHA, AST/fatal-flake8/diff e comandos bash-n íntegros. A mutation unbound-success inicialmente ficou mascarada pelo erro primário incompatível; fixture agora inclui sucesso ready0 com primary0 coerente, que precisa ser recusado por si. Recuperação física usou somente cleanup do coletor corrigido, sem novo scan: status ready0 vivo, resultado=-1/session primary=-1 com bus/config/TLS/reset/power limpos, PCI vazio e unload normal; REG_ON80/readback/restore_pending0 e unload comprovados. Original resultado recusado preservado separado; erro PCI não virou sucesso. SSH/HTTP/Herdr finais passaram no mesmo boot, budget500mA e zero power_supply; não são prova de carga. Módulos/Image/DT/identidades/gates C inalterados. Snapshot/sync/retorno e publicação da prova seguem154/156.

### Incremento 156 — prova da sessão e pendências delimitadas

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e novo docs/evidence/n71-scan-target-physical.json. Registrar um boot/um scan/zero reinícios intermediários, TLS prepare/restore físicos, scan negativo579 reads/14 attempts/10 writes/1 refusal e primeira root044/word8008. Caller/probe negativo limpo e retenção conservadora do coletor original, recuperação155 no mesmo boot, SSH/HTTP/Herdr, snapshot44/sync e retorno por software ao iOS. Leituras iOS100→90 incluem transições; carga ativa no retorno, zero power_supply e budget500mA não comprovam carga Linux.
- Fixar gates15537/47 Mac/ARM64 e25 inputs, reutilizar C/build151 sem mudanças, separar CI d045 (PR success; push success após retry de job Ubuntu) da correção155/156. Fontes PCI exatas locais confirmam PMCSR8000=PME_STATUS W1C e8=NO_SOFT_RESET; não autorizar essa escrita nem outras recusas latched sem próximo contrato/testes/lifecycle. Código/publicação na branch, sem main/tag/release/firmware/pacotes Mac.
- JSON/inputs/logs/snapshot/provenance/ELF/links/diff/publictree e receita do coletor; atualizar #9/#2 e criar pendência CI intermitente distinta da #37 fechada. Próximo desenvolvimento offline deverá qualificar PMECSR/ownership antes de outro scan; energia I2C1/HDQ/gauge permanece aberta. Não pedir outro DFU apenas para publicar/analisar esta prova.

- Gate156: prova JSON correlaciona um boot/um scan/zero reboots intermediários, logs/25 inputs por SHA, classifier37/47 Mac/ARM64 e cleanup/serviços/snapshot44/retorno físicos. Resultado original e recuperação são registros separados; scan=-1 não foi contado como sucesso, PME/W1C não foi permitido. Campos primários constantes/função PCI confrontados na fonte exata local e hashes registrados; a atribuição de call site é inferência, não trace. Links locais/diff válidos, snapshot verificado sob lock, perfis/identidades e fontes do módulo preservados. iOS detectado90% com carga ativa após retorno; zero power_supply/budget500mA continuam limites. CI d045 terminal success nos dois eventos, first attempt push falho conservado; issue38 aberta para intermitência, sem mascarar pela ampliação cega de timeouts. CI do head156 será acompanhada separadamente; sem novo DFU para análise/publicação.

### Incremento 157 — PME inativo reconhecido sem escrita no hardware

- Quatro arquivos: plano, phone/kernel/n71-pcie-scan-config.h, tests/n71_pcie_scan_config.c e tests/run_n71_pcie_scan_mutations.py. A fonte PCI fixada chama pci_pme_active(false) em pci_pm_init; a forma8008 sobre o PMCSR8 físico corresponde ao pedido de limpar PME_STATUS já zero, mantendo D0 e PME_ENABLE desligado. Atribuição ao call site permanece inferência sem trace. Escolha: reconhecer somente esse efeito já satisfeito como no-op; alternativa W1C real apagaria eventos e exigiria contrato adicional, portanto fica fora desta fatia.
- Guard antes do no-op genérico para root044/word com PME_STATUS solicitado: somente observed8/value8008, identidade root medida, COMMAND sem master, STATUS com capabilities, primeiro pointer40, header PM id1/version1..3 e releitura PMCSR8. Nenhum io.write, contador de writes ou estado config alterado; refusals/errors/read budget permanecem latched. PME ativo, enable, D-state, outros bits, capability/identidade/pointer divergente ou falha de leitura devem ser recusados. Caso observed8008/value8008 não pode cair no no-op genérico e ocultar evento W1C ativo.
- Testes compilados reais no Mac/Ubuntu ARM64: reprodução8→8008, repetição/restore, todas as alterações de bits de pedido/observação, larguras/função/offset, capacidades/identidade/master, falha em cada leitura e mudança de estado na releitura. Mutantes devem compilar e morrer por SIGABRT/assertion, não por import/compile/timeout. Reusar testes inalterados só quando dependências também inalteradas; executar consumidores que incluem o header modificado e seis módulos W1/KCFLAGS-Werror/modpost na VM com config/Image/exports preservados. Nenhuma escrita/DFU/boot/firmware ou instalação Mac.
- Registrar source/hashes/gates/proveniência num incremento documental seguinte; profile/default anteriores permanecem preservados. CI7adc anterior cobre o classifier e será acompanhada por head separado. #9/#2 atualizadas com a sessão física e #38 aberta; não fechar pendências por teste sintético. Preparar a candidata offline antes de solicitar uma próxima sessão física agrupada.

- Gate157: seis suítes nativas consumidoras passaram Mac/Ubuntu ARM64 com51 inputs SHA conferidos; config36 mutações SIGABRT/assertion e scan21 cenários/13 mutações. Caller67/18 reutilizado porque caller/MMIO/harness não mudaram e a fixture caller substitui o scan; módulo real inteiro recompilado. Seis módulos passaram W1/KCFLAGS-Werror/modpost/ELF/vermagic, fonte/config/Image/exports preservados. PCIe novo70424 bytes/SHA63ee7d460bf9161a2105108a98667cf5966a8b31fd02460559fadd762da25e07; módulo REG_ON igual ao anterior. Primeira compilação recusou variável current pelo macro kernel get_current; renomeada pmcsr_now e build em outputv2 passou, mantendo falha original privada. Runner teve âncora antiga após rename; erro de âncora não contado como kill; mutações36 rodadas novamente passaram. Seis suítes Mac v2 já passaram com o header final e foram reutilizadas após corrigir apenas nomes de âncoras no runner. AST/fatal-flake8/diff íntegros; nenhum telefone/DFU, W1C real, Image novo ou pacote Mac. CI7adc PR falhou em duas contagens de snapshot antigas; push cancelado com Mac/Windows aprovados, sem atribuir aprovação ao Ubuntu. Issue38 recebeu reprodução; diagnóstico segue separado.

### Incremento 158 — expor a fase real da intermitência de retorno na CI

- Dois arquivos: plano e tests/test_return_ios.py. Issue38 reproduziu PR7adc/Ubuntu em linux-stays e bad-plist: CLI recusado, mas snapshot0 em vez de1, sem stdout/stderr na asserção atual. Ambos passaram isoladamente no Mac com fonte inalterada. Não há causa provada; nenhum timeout ou código operacional será alterado com base somente nesse resultado.
- Fortalecer a fixture que espera falha após backup: exigir o marcador BACKUP_VERIFIED e incluir modo/eventos sintéticos/stdout/stderr nas falhas de marcador/arquivo. Isso revela uma recusa em enumeração/SSH/backup em vez de reportar apenas0!=1. Não mudar a produção, não converter timeouts/import/compile em AssertionError nem contabilizá-los como mutation kills. Nenhuma informação real de aparelho/conta aparece na fixture.
- Gate20 testes da suíte afetada no Mac/Ubuntu ARM64; conferir os mesmos oito inputs/AST/fatal-flake8/diff e prova diagnóstica em cópia descartável com preflight SSH deliberadamente recusado. Nova CI do head composto continua necessária, sem reatribuir CI anterior; issue38 permanece aberta até entender a intermitência. Zero ações no iPhone e não repetir suítes kernel/PME inalteradas.

- Gate158:20 testes completos passaram Mac/Ubuntu ARM64, oito inputs SHA preservados, AST/fatal-flake8/diff íntegros. Cópia descartável com pin-error recusado reproduziu diagnóstico de fase: modo, dois eventos idevice_id/ssh e erro SSH Linux não confirmado aparecem na AssertionError por marcador ausente. Nenhum timeout/erro de execução contado como mutation kill; lógica operacional/timeouts intactos e intermitência remota ainda não diagnosticada. Gates PME157 preservados/reutilizados; nenhum reboot/telefone ou dependência nova.

### Incremento 159 — reprodução e prova da candidata PME sem W1C

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e novo docs/evidence/n71-pcie-pme-noop-build.json. Preservar registros físicos/builds antigos; fixar código5bc966e,51 inputs e logs verificados, seis suítes/8 testes compiladores,36 mutações config e scan21/13 nas duas plataformas. Caller67/18 reutilizado com quatro inputs exatos intactos; módulo real completo recompilado e seis módulos Werror/modpost/ELF/vermagic, kernel/fonte preservados.
- Documentar no-op somente root044/word8008 sobre8 com identidade/capability/COMMAND/STATUS/pointer/version/releitura; evento PME ativo não é descartado nem conta como sucesso, nenhuma escrita raw/W1C/endpoint/enable/D-state. Modificar apenas o novo módulo PCIe; REG_ON igual ao anterior. Não substituir default/perfil ativo ou prometer scan/Wi-Fi/carga. Nova provenance/seleção explícita no coletor ainda precisa de integração antes de um próximo load por SSH.
- Separar CI7adc PR failure/push cancelled da prova local e diagnóstico15820/20 Mac/ARM64. Fontes primárias fixadas/hash e atribuição pci_pm_init por inferência, não trace físico. Gates JSON/inputs/logs/links/receita/AST/bash-n/diff/publictree e commit na branch; push final agrupar com a seleção do coletor, evitando CI redundante. Sem DFU/boot/firmware/pacote Mac; #2/#9/#38 permanecem abertas.

- Gate159: JSON51 inputs, logs Mac/ARM64, módulo PCIe/SHA/vermagic, oito testes nas seis suítes e36 mutações correlacionados aos resultados; quatro inputs caller intactos e REG_ON igual ao anterior. Receita das seis suítes/build passou bash-n e links locais íntegros; registro físico/artefatos anteriores preservados. No-op sem write, ativo/endpoint recusados e prova somente offline explícitos. Diagnóstico15820/20 logs conservados; CI7adc PR failure/push cancelled não convertido em sucesso. Nenhuma suíte inalterada repetida para documentação nem ação no telefone; seleção explícita do coletor segue160.

### Incremento 160 — seleção explícita da candidata PME no coletor

- Quatro arquivos: plano, scripts/host/n71-link-session.py, tests/test_n71_link_session.py e runner de mutações existente. Acrescentar --scan-pme-noop, válido somente com --host-scan --scan-link-target na ABI power2; provenance pcie_scan_pme_noop precisa ser booleano exato igual ao opt-in. Selecionar o novo registro159 somente nesse modo; hashes/ELF/vermagic/REG_ON e guards de cleanup continuam os mesmos mecanismos, sem fallback silencioso ao módulo antigo.
- Exigir no registro PME os contratos no-op sem write, evento ativo recusado, root-only e releitura da word; defaults e modos anteriores preservados. O Session continua sendo o mesmo target scan delimitado e sem outro scan na recuperação. Não adicionar novo estado duplicado de hardware nem liberar REG_ON sob retenção.
- Testar seleção/scope/build flags/contratos/ABI e CLI filesystem com módulos sintéticos de hashes distintos, provenance cruzada/não booleana/opção ausente e pin/tamper: check tem de passar sem SSH/USB. Mutantes precisam morrer por AssertionError sem ERROR/import/compile/timeout. Mac/Ubuntu ARM64, inputs/logs/AST/fatal-flake8/bash-n/publictree. Reusar módulos/Gates157/159 porque fontes C/config/artefatos não mudam; preparar perfil separado preservando os seis arquivos inalterados do perfil anterior e somente trocando PCIe/provenance. Documentação e prova do perfil seguem161; nenhum novo DFU para integração offline.

- Gate160:39 testes/53 mutações por AssertionError passaram Mac/Ubuntu ARM64,26 inputs preservados; dez comandos bash-n, AST/fatal-flake8/diff íntegros. Opt-in/scope/provenance booleanos exatos e quatro contratos PME requeridos, defaults/REG_ON preservados. Mutation de seleção de registro tentou produzir KeyError em vez de AssertionError: explicitamente excluída da prova;53 kills aceitos têm somente asserção e zero ERROR. Perfil real separado passou payload/initramfs/identidades/SHA/ELF/vermagic sem SSH/USB; ausência de --scan-pme-noop foi recusada. Seis arquivos anteriores preservados byte a byte e somente PCIe/provenance novos; physical flags da antiga sessão ficaram em prior_profile, candidata não testada. Kernel C/gates157/159 reaproveitados, sem módulo/Image recompilado ou reboot. Prova/documentação/cohort/profileSHA final seguem161.

### Incremento 161 — runbook da seleção PME e checkpoint reproduzível

- Quatro arquivos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e novo docs/evidence/n71-pme-scan-session.json. Fixar coletor4cea1ce/26 inputs,39 testes/53 mutações nas duas plataformas, dez comandos bash-n e check real do perfil privado separado sem SSH/USB. Código/module/profile inputs continuam iguais; nenhuma suíte kernel/host inalterada repetida para esta documentação.
- Receita inclui --host-scan --scan-link-target --scan-pme-noop e profile próprio; ausência/crossed/nonbool flags ou module tamper recusados. Preservar release/payload/initramfs/identidades/REG_ON/default; source/artefatos do target anterior ficam disponíveis para rollback. Uma tentativa scan, cleanup/status normal e história fresca no mesmo boot permitem próxima continuação qualificada via --previous-clean; não dar novo DFU só para uma coleta por SSH.
- Gates JSON/inputs/logs/provenance/links/receitas/bash-n/publictree; commit/push autorizado de157→161 na mesma branch e atualizar #9/#38/#2 com os limites reais. Nova CI vai ao head final; PR7adc failure/push cancelled não será usado como aprovação. Nenhum auto-load/firmware/chaves publicadas, Image novo ou operação no telefone; próximo boot só após gates e leitura USB/carga frescas.

- Gate161: JSON26 inputs e logs39/53 Mac/ARM64 conferidos por SHA, record do módulo/ABI e real profile check correlacionados. As duas receitas passaram bash-n e links locais íntegros. Perfil conserva seis arquivos anteriores, somente PCIe/provenance diferentes; collector commit4cea1ce fixado, check no-op missing recusado sem SSH/USB. Prova C/build157/159 e host160 reutilizada, nada recompilado/reiniciado para documentação. CI antiga failure/cancelled explícita; próximo gate remoto corresponde ao head final. #9/#2/#38 continuam abertas, firmware/chaves/logs privados; candidato ainda não carregado.

### Incremento 162 — comandos sintéticos de retorno sem startup Python

- Três arquivos: plano, tests/test_return_ios.py e novo tests/fixtures/return-ios-stub.sh. Diagnóstico novo c08c/push Ubuntu falhou em linux-returns com events=[], stdout vazio e Enumeração USB indisponível: recusa na primeira enumeração antes do corpo STUB. Isso não distingue exit/timeout nem comprova causa última do runner; remove-se uma dependência evitável do teste, startup/imports Python para cada chamada USB/SSH, sem ampliar prazos ou modificar produção.
- Extrair a fixture para POSIX /bin/sh, com somente argumentos/eventos/sync/reboot/plists constantes e arquivo tar real. A execução via subprocess e o snapshot/CLI reais continuam sob teste. Conservar validação StrictHostKeyChecking/IdentitiesOnly/alias, modo/perfil, PID temporário/rename atômico e barreiras/cancelamento do processo próprio. Slow-backup usa exec sleep para que o PID publicado corresponda ao processo controlado; nenhuma chamada USB/SSH real ou segredo. Remover STUB Python agora substituído, sem import/variável morta.
- Gate bash-n/ShellCheck disponível,20 testes Mac/Ubuntu ARM64 e11 mutações de produção já existentes por AssertionError (nenhum timeout/compile/import kill). Gate da nova fixture com PATH deliberadamente sem Python em cópia temporária, incluindo tar bytes e processo/PID. Atualizar manifest para dez inputs (nove da suíte e runner de mutações) e registros/hash/logs privados, CI do head novo deve confirmar a intermitência; não fechar #38 por sucesso local nem atribuir a falha ao iPhone. Kernels/coletores/gates inalterados reutilizados; nenhum reboot/DFU.

- Gate162:20 testes e11 mutações por AssertionError passaram Mac/Ubuntu ARM64; quatro fluxos reais de snapshot/perfil/PID/cancelamento passaram com PATH contendo somente os comandos sintéticos, sem Python. Dez inputs e logs SHA conferidos; sh-n/ShellCheck/AST/fatal-flake8/diff íntegros. Fixture shell publica PID via temporário/rename e exec sleep, preservando cancelamento do grupo; produção/timeouts/kernel/coletores intactos. CI c08c PR terminal success nos três jobs; push failure somente Ubuntu na primeira enumeração sintética, antes de eventos, não convertido em sucesso nem atribuído ao telefone. Issue38 permanece aberta; novo head terá CI própria. Candidata PME e seus gates kernel/collector inalterados reutilizados, snapshot44 válido e iOS100% observado novamente16:51UTC.

### Incremento 163 — uma sessão física PME com CI e retorno preservados

- Quatro arquivos públicos: plano, docs/N71_LINK_EXPERIMENT.md, docs/STATUS.md e nova prova física sanitizada. Seleção/profile PME160/161/kernel/gates157 não mudaram; PRc08c passou integralmente nas três plataformas, pushc08c teve falha sintética pré-enumeração registrada na #38. Fixture16220/11/4 Mac/ARM64 não muda a produção nem a candidata; nova CI será registrada separadamente, sem ocultar o evento falho.
- iOS100%/external/fully charged observado16:51UTC, snapshot44 verificado, ferramentas locais e profile/check/SHA/ABI íntegros. Um monitor/um DFU manual/restore, SSH/HTTP/Herdr; scan explícito --host-scan --scan-link-target --scan-pme-noop em output privado novo. Uma tentativa, nenhum rádio/firmware/DMA/IRQ/HDQ/charger/I2C; conservar primeiro erro e obrigações de cleanup. Continuação no mesmo boot somente para candidata adicional já qualificada com história íntegra; não repetir scan nem force unload.
- Coletar logs completos, counters, primeira recusa e status/normal unload/REG_ON/pci/sysfs; manter erro primário negativo como negativo. Conferir serviços, snapshot/sync/retorno por software e leitura de bateria iOS fresca. Não manter Linux para desenvolvimento offline demorado sem telemetria de carga. Registrar prova de hardware distinta da síntese/CI, atualizar #9/#2/#38 no GitHub autorizado; sem main/tag/release, pacotes/config global Mac, perguntas de temperatura/PIN/contador ou novo DFU só para publicar.

### Incremento 164 — lifecycle PME do endpoint preparado offline

- Quatro arquivos: plano, novo phone/kernel/n71-pcie-pme-control.h, tests/n71_pcie_pme_control.c e tests/test_n71_pcie_pme_control.py (runner nativo e mutações). A coleta163 teve primeira recusa endpoint1:00/04c/wordc008 sobre4108; root044 já não recusou. A fonte fixada __pci_pme_active(false) corresponde ao pedido de desativar PME_ENABLE e limpar PME_STATUS, atribuição por inferência sem trace. Decisão: helper separado, ainda não integrado/carregado, para desativar/restaurar somente PME_ENABLE0100 sem jamais escrever PME_STATUS8000 ou mudar D-state/outros controles. Não emular disable mantendo o bit ligado nem permitir W1C por igualdade.
- Reutilizar captura bounded de capabilities já existente: endpoint43a314e4, COMMAND master0, uma capability PM exatamente48/version1..3/PMCSR4c, observado inicial4108, releitura antes da escrita. Estado público do helper permanece intacto antes de qualquer efeito; ownership/pending passa antes de write, conserva em erro parcial/readback/retry e só libera após restauração com leitura fresca. Bit8000 sempre zero no valor escrito; evento recém-chegado sobrevive e impede contabilizar preparação como sucesso. Cleanup restaura somente bit0100 por máscara, preservando outros bits atuais e evento W1C; recusa identidade/capability/COMMAND divergentes e retém owner em falha.
- Testes C reais: prova de disable/restore, bits/capability/escopo, todos os erros de leitura/write/readback, efeitos parciais e evento após observação, nenhuma escrita root/outra word/largura e restauração preservando eventos/outros bits. Mutantes compilados precisam falhar por SIGABRT/assertion; nenhum import/compile/timeout conta. Mac/Ubuntu ARM64; manifests/logs privados/AST/fatal-flake8/ShellCheck relevante/diff/publictree. Não mudar scan/caller/módulos/kernel/DT/profile/default nesta etapa, não realizar USB/DFU/radio/charger ou liberar a candidata física nova sem integração/ownership qualificados.

- Gate164:helper novo compilado C11/pedantic/Werror com baseline real e14 mutações compiladas mortas por SIGABRT/assertion no Mac/Ubuntu ARM64; sete inputs e logs SHA conferidos, nomes dos kills registrados. Cobriu os16 bits da word, versões0..7, capability/identidade/master, cada erro de leitura, write parcial/positivo, readback/eventos e restauração por máscara com owner retido em falha. Primeira mutation fresh-word gerou unused-but-set-variable e não foi contada; substituída por relaxamento compilável do bit de evento, e14/14 passaram. AST/fatal-flake8/diff íntegros. Helper independente ainda não integrado no scan/caller, módulo/Image/profile intactos e nenhum load físico desse helper. Sessão163 voltou ao iOS por fallback manual, confirmado99%/carregamento ativo17:13UTC; CLI preservou snapshot44/sync e recusou sucesso após ausência USB. A documentação/prova dessa sessão será concluída após este commit isolado.

- Gate163 documental:registro sanitizado correlaciona um boot/scan, SHA de logs/módulo/collector,613/33/23/1, primeira endpoint04c/c008 e cleanup positivo sem retenção; serviços, snapshot44/sync e fallback iOS99% ativos conferidos. CLI90 segundos recusou retorno não confirmado; issue21 será reaberta sem atribuir causalidade ao comando ou writes PCI. GasGauge1465/Design1690/Full100 não foi convertido em saúde. Helper0098def1/14 Mac/ARM64/seven inputs é prova offline distinta e ainda não integrado. CI d5eadPR success/pushcancelled explícita; #2/#9/#21/#38 continuam pendentes. JSON/links/receita/diff/publictree precedem publicação, sem novo DFU.

### Incremento 165 — pedido PCI de PME já desativado sob ownership

- Quatro arquivos: plano, helper PME, fixture C e runner Python existentes. Antes da integração do adapter, qualificar wrapper que mantém a política config existente e reconhece somente endpoint04c/wordc008 quando helper tem original4108/pending/prepared e uma observação fresca4008 sem evento. Traduz apenas esse pedido para no-op4008 na política genérica, que revalida a word antes de não escrever. Evento novo/ativo, owner ausente, outro valor/largura ou erro latched bloqueiam, sem escrever W1C ou inventar desativação.
- As demais requisições usam a política original; requests PME_STATUS de endpoint nunca podem cair na igualdade genérica sem o contrato próprio. Refusal conserva primeiro erro e impede leituras novas quando latched. Testar prepare/core-noop/restore, bits/larguras/ownership, evento ativo antes/depois da observação e erro latched; mutantes C compilados por SIGABRT/assertion. Gates anteriores14 devem continuar executados com fonte final, Mac/Ubuntu ARM64 e mesmos sete inputs atualizados. Nada integrado/carregado no telefone nesta fatia.
- Reunir depois adapter/caller e controles PCI adicionais em candidata única: não pedir DFU só para passar individualmente cada recusa. Telefone fica no iOS99% carregando; fallback/pendências físicos163 registrados nas issues. Sem hardware/reset extra, novo kernel/firmware ou mudança global Mac.

- Gate165 Mac: baseline C e19 mutações compiladas por SIGABRT/assertion passaram. A mutation core-active-event inicialmente sobreviveu porque a leitura genérica adicional também recusava um evento ainda ativo; fixture agora cobre evento conhecido que desaparece só na leitura seguinte, garantindo recusa da observação ativa sem confundi-la com no-op. Word/byte/larguras,16 bits de pedido, original/pending/prepared e erro latched foram exercitados. Não contou sobrevivente nem falha de compilação; prova ARM64 e sete inputs seguem antes do commit. Produção/caller/default ainda sem integração ou hardware.

- Gate165 final: baseline/19 mutações compiladas SIGABRT/assertion passaram também Ubuntu ARM64; sete inputs/logs SHA conferidos, AST/fatal-flake8/diff íntegros. Wrapper preserva erro latched e bloqueia todas as outras larguras da PMCSR, owner ausente e evento ativo/novo; pedido exato é mapeado para no-op pela política existente com releitura adicional. Header/kernel consumer anterior inalterado, nenhum módulo/profile/telefone mudado; integração do adapter segue166 sem DFU.

### Incremento 166 — adapter com PME retido e cleanup sem novo scan

- Quatro arquivos: plano, n71-pcie-scan.h e fixture/runner scan_host existentes. Incluir helper qualificado165; armazenar seu estado no host bridge persistente, preparar PME somente no modo explícito da nova função n71_pcie_scan_with_pme. Wrapper legado n71_pcie_scan mantém false; caller/param/default atuais permanecem sem ativação nesta fatia. Política de escrita do callback usa fronteira PME, com erro latched/W1C e releitura preservados.
- Sob rescan lock, TLS prepara antes de PME e nenhuma PCI callback ocorre até ambos passarem. Remover bus primeiro; restaurar config, depois PME e TLS; qualquer falha conserva bridge/link/ownership para cleanup posterior, sem repetir scan ou perder owner em write parcial. Logs PME de prepare/restore descrevem pending/prepared e não inferem rádio/carga. Nenhum rawwrite alargado ou reset novo.
- Manter21 cenários/13 mutações anteriores e acrescentar oito cenários PME (sucesso, prepare/restore drop, eventos, capability, refusal latched e link perdido) e mutações de integração compiladas SIGABRT/assertion. Conferir CSR, eventos, ordem real remove/restore, retenção/retry e ausência de novo scan; Mac/Ubuntu ARM64 e inputs/logs por SHA. Helpers165 com inputs iguais reutilizados; C caller/módulos/profile/default não alterados nem carregados. Depois expor opt-in no caller, builds reais e juntar demais controles PCI antes de outro DFU.

- Gate166: dois testes nativos com29 cenários e18 mutações C compiladas SIGABRT/assertion passaram no Mac/Ubuntu ARM64, dez inputs por SHA. A primeira baseline revelou somente fixture STATUS esperada sem o bit capability-list acrescentado no modo PME; corrigida para conferir preservação dos dois estados, baseline e mutações foram reexecutadas com a fonte final. Sete inputs helper165 inalterados/19 provas reutilizadas. Adapter conserva bus removido, config/PME/TLS nessa ordem e bridge/ownership em falha para retry sem scan. Caller/default/profile/módulo ainda não ativam PME; nenhum novo DFU.

### Incremento 167 — opt-in PME no caller, sem mudar o caminho padrão

- Quatro arquivos: plano, caller C e fixture/runner nativos existentes. Expor scan_pme_disable somente leitura, false por padrão, exigindo host_scan e as validações existentes de run/N71/enumerate/config_inventory/modos exclusivos. Selecionar a função qualificada com PME apenas quando explicitamente habilitada; demais chamadas continuam no wrapper legado.
- Manter os67 cenários/18 mutações do caller e adicionar ativação válida, combinações inválidas e ownership retido/retry no modo PME. Provar dispatch real, ausência de scan/registro nas rejeições e cleanup sem nova enumeração/scan, com refs de módulo/power preservadas. Adicionar mutações compiláveis de dispatch e da validação; Mac/Ubuntu ARM64, manifesto e logs por SHA. Gate do adapter166 reutilizado se seus dez inputs forem iguais.
- Sem carregar o módulo nem pedir DFU nesta fatia. Build ARM64 real, collector/profile opt-in e controles seguintes serão preparados separadamente e reunidos para uma sessão física, mantendo o iPhone carregando no iOS.

- Gate167: caller nativo com73 cenários e21 mutações C compiladas SIGABRT/assertion passou Mac/Ubuntu ARM64; cinco inputs por SHA. Novo opt-in não registra driver com host_scan ausente ou flags incompatíveis, default permanece legado, estado/ref/power retidos em falha e action=cleanup não repete scan/enumeração. Adapter166 continua com dez inputs idênticos e helper165 com sete; prova de simulação não implica load/kernel build ou Wi-Fi. CI6f7cd02 anterior: PR37347973014 success, push37347965151 cancelled; não cobre167.

### Incremento 168 — opção de boot ASPM off para agrupar os próximos obstáculos

- Quatro arquivos: plano, composer do perfil diagnóstico e fixture/runner de payload existentes. Fonte PCIe fixada confirma que pcie_aspm=off coloca aspm_support_enabled=false; init_link_state sai antes de common-clock/retrain/L1SS/configuração, e exit_link_state sai sem link_state. pcie_no_aspm sozinho não é equivalente. Requests latched bc/40 e80/40 são coerentes com CCC, não RCB (bit8); atribuição por inferência, sem trace independente.
- Novo --pcie-aspm-off explícito somente no composer diagnóstico. Compose aceita apenas bool e mantém a validação do layout original; altera apenas a linha bootargs na saída, preservando loader/kernel/userspace/identidades e a validação DT existente. Perfil padrão/compose genérico/integrador inalterados. Registrar opção e hash de bootargs na provenance privada para posterior verificação estrita pelo collector.
- Testar payload final literal com/sem opção, entradas adulteradas e tipo inválido, CLI e mutações por AssertionError reais; Mac/Ubuntu ARM64 com inputs/hash. Nenhum build novo de Image/DFU; reunir esta opção com PME/caller e qualificar módulo/collector/perfil antes do único teste físico. ASPM off não comprova carga nem baixo consumo.

- Gate168: sete testes/13 mutações por AssertionError passaram Mac/Ubuntu ARM64 com14 inputs e hashes de logs conferidos. Payload literal confirma apenas bootargs opt-in e delta DT permitido; tipos não bool e fonte já alterada recusados, CLI/default/ABI/identidades mantidos. Não contou import/compile/timeout. Fonte fixa aspm.c35868f5c confirma init1163/guard1168 e parse1791..1805; configure_aspm_l1ss70 só descobre capability/aloca save buffer, sem writes, e exit1324 retorna sem link_state. Hipótese de reduzir as recusas CCC/retrain/L1SS ainda depende de boot físico novo; nenhuma nova sessão foi pedida.

### Incremento 169 — build real e registro da candidata PME/ASPM agrupada

- Até quatro arquivos públicos: plano, nova prova JSON, nova receita PME/ASPM e atualização do checkpoint STATUS. Build de todos os seis módulos em diretório novo na VM ARM64 existente usando kernel power2 fixado, W=1/KCFLAGS=-Werror/modpost e verificação ELF/vermagic. Inputs module/Makefile/patches/verificadores por SHA; source bundle/.config/Image/vmlinux.symvers devem ser idênticos antes/depois. Não recompilar Image nem copiar chaves para a VM.
- Reutilizar provas nativas165/166/167/168 somente com inputs idênticos: helper1/19, adapter29/18, caller73/21, composer7/13; preservar logs de erros de desenvolvimento sem contá-los como gates aprovados. Registrar hashes dos seis módulos e fonte primária do ASPM, no-write/W1C/ownership e opt-ins reais. Documentar reprodução em cópia descartável e distinguir módulo qualificado, payload opt-in e ausência de load físico/collector.
- Após esse checkpoint, integrar collector estrito para PME e bootargs off, verificar perfil privado e reunir testes físicos úteis num boot. Nenhum DFU agora nem fechamento de Wi-Fi/carga/retorno a partir desta prova offline.

- Gate169: seis módulos reais W=1/KCFLAGS-Werror/modpost/ELF/vermagic passaram na VM ARM64,46 inputs conferidos no Mac. PCIe73576 bytes/SHA828b1ae2, REG_ON idêntico; fonte/bundle/.config/Image/vmlinux.symvers preservados antes/depois. Provas helper165, adapter166, caller167 e composer168 reaproveitadas somente após hashes iguais; provas antigas dos demais helpers/config36 mantidas com inputs intactos. Registro JSON/receita/STATUS distinguem build e hipótese ASPM de ausência de load/collector/perfil físicos. Sem DFU, firmware, chave na VM ou configuração global no Mac.

### Incremento 170 — coletor PME/ASPM com seleção e cleanup estritos

- Cinco arquivos: plano, coletor, novo parser PME e fixture/runner existentes. Novo --scan-pme-disable seleciona somente o build169, exige host-scan/target/power2 e não se combina com --scan-pme-noop anterior. Validar contratos enable-only/no-W1C/readback/owner/ASPM e flags booleanas exatas no perfil; ABI/hash/ELF/provenance obrigatórios. Default e candidatas anteriores permanecem selecionados por seus próprios inputs.
- Antes de transferência/insmod, nova etapa verifica no telefone um único pcie_aspm=off no cmdline e mensagem kernel de suporte desativado; não permite conflito/duplicata. Adicionar scan_pme_disable=1 somente nesse modo, usar parser PME para sucesso/cleanup e manter retry uma vez sem scan. Parser delega provas TLS/caller/config existentes e exige preparação PME consistente, final restore pending0, sem restore antes de bus/config nem TLS antes de PME. Negativos anteriores à preparação permitem cleanup somente com provas anteriores completas; erro original permanece negativo.
- Estender39 testes/53 mutações anteriores com seleção/flags/contratos, comando real gerado, preflight antes de efeito, logs PME malformados/ausentes/duplicados/evento/retention/retry. Mutações por AssertionError, sem import/compile/timeout; Mac/Ubuntu ARM64, inputs/logs/hash e sintaxe Bash dos comandos. Build169 intacto/reutilizado. Depois verificar perfil privado real e CI antes do único DFU; nenhuma operação física nesta fatia.

- Gate170:45 testes e81 mutações por AssertionError passaram Mac/Ubuntu ARM64 com29 inputs e hashes de logs conferidos; dez comandos gerados e cinco do preflight novo passaram bash-n. A primeira execução identificou sobrescrita da observação preflight pela etapa ASPM; corrigida antes de qualquer transferência física. Um mutante revelou falta de cenário de restore antes de prepare quando falha de registro não produz device reports; fixture cobre esse caminho isoladamente. Erros de infraestrutura e mutantes sobreviventes não foram contados. AST/fatal-flake8/diff íntegros, Image/config/exports preservados, build169 intacto. Nenhum novo DFU ou claim de Wi-Fi/carga.

### Incremento 171 — perfil privado real e prova reproduzível do coletor

- Até quatro arquivos públicos: plano, prova JSON nova, receita PME/ASPM e checkpoint STATUS. Registrar45/81 Mac/ARM64 com29 inputs/hash, sintaxe Bash, source/module169 preservados e CI do head correspondente, sem confundir simulação com hardware.
- Criar perfil privado novo a partir da candidata anterior verificada; conferir layout loader/bootargs/DT/kernel/initramfs por SHA e tamanho. Alterar somente bootargs opt-in, módulo PCIe, deployment SHA e provenance; manter identidades, initramfs, DT, kernel e REG_ON. Reutilizar a função pública de composição/bootargs qualificada168; registrar recipe/hash do script local sem chaves/alias/logs em público. Checks de identidade, boot tools, snapshot e coletor devem passar sem SSH/USB antes do próximo DFU agrupado.
- Perfil padrão e fonte anterior intactos; nenhuma instalação/configuração global Mac nem firmware/contas/remotos alterados. Wifi, carga, IRQ/DMA/firmware e retorno automático continuam pendentes. Após publicar, conferir CI e USB/carga frescos, preparar um monitor único e pedir somente DFU físico indispensável.

- Gate171: perfil real composto pelo CLI público168 a partir do base power2, sem adaptação manual do payload. Verificados loader/DT/Image.gz/Image/initramfs/identidades/REG_ON e layout, delta de14 bytes de bootargs; fonte e default preservados. Coletor opt-in, ferramentas e snapshot44 passaram checks sem SSH/USB. Registro sanitizado liga29 inputs e logs45/81 Mac/ARM64 ao commit7708a5c e ao build169; paths/alias/chaves/binários privados omitidos. CI120352c pushsuccess/PRfailure explicitamente distinta: Ubuntu registrou timeouts de fixtures antigas e SIGTERM de deadlines Pongo, Mac/Windows success, causa não confirmada e issue38 aberta. Links/JSON/diff/publictree precedem publicação; nenhuma nova sessão física.

### Incremento 172 — sessão física única PME/ASPM após gates

- Até quatro arquivos públicos: plano, prova física JSON nova, receita PME/ASPM e STATUS. Nenhuma nova implementação em módulo/coletor entre os gates171 e o load. Conferir todos29 inputs e módulo/build/perfil; CI completa do mesmo código em Mac/Ubuntu/Windows, distinguindo eventos e preservando falha de timeout independente na issue38. USB/iOS/carga devem ser verificados novamente imediatamente antes do monitor.
- Um boot via perfil explícito/restore44 e um DFU manual, sem contador ou PIN. Esperar SSH/HTTP/Bash/Herdr e restore comprovados; cmdline+marcador ASPM devem passar antes de transferência. Uma execução host-scan/target/PME com logs privados; qualquer recusa limita a conclusão. Cleanup/retry sem novo scan, não remover módulo nem REG_ON sem prova. Reunir observações adicionais compatíveis por SSH se forem úteis e os gates de owner/bateria permitirem; evitar probes repetidos sem hipótese nova.
- Confirmar serviços, PCI vazio/módulos ausentes somente quando cleanup passar; snapshot/sync e retorno curto ao iOS para recarga. Se retorno USB não confirmar, registrar negative e pedir somente fallback Power+Home indispensável. Não solicitar leitura/ação no console, temperatura ou desbloqueio. Publicar somente contagens/hashes/estados selecionados; Wi-Fi/carga/telemetria não são inferidos da enumeração PCI ou consumo iOS.

- Gate172: um DFU manual/um boot/quatro etapas físicas/zero reinícios intermediários; primeiro monitor expirou antes do payload e segundo reutilizou DFU. Scan PME/ASPM error0,2 devices/1 endpoint,660/40/23/0, prepare/restore completos; BAR32KiB/4MiB e BCM4350rev8, DART38 reads/16 words e ciclo provider4 snapshots/152 reads/16 words restauradas passaram. Continuação por módulo anterior qualificado, kernel/DT/initramfs/identidades/REG_ON iguais e payload anterior não bootado; ASPM live preservado, same-boot/history/cleanup conferidos em cada etapa. Serviços finais uptime506,59s, snapshot44/sync e retorno automático USB ao iOS passaram; iOS100→100/charging19:00:58UTC não prova carga Linux. PRdd2b0da success3jobs/81 kills Mac/Ubuntu; pushfailure Ubuntu por timeout PMGR10s após baseline, #38 aberta sem causalidade inferida. Prova sanitizada nova preserva hashes/contagens e não publica rawTTBR/chaves/identidades. Próximo gate é desenvolvimento offline de lifecycle/recursos PCI e IRQ/IOMMU, sem outro DFU agora.

### Incremento 173 — retenção explícita do bus PCI, sem bind ou DMA

- Quatro arquivos públicos: plano, adapter scan e fixture/runner nativos existentes. Issue39 acompanha o host persistente. Fonte PCI fixada confirma scan_root_bridge/device_add sem ALLOW_BINDING, stop/remove sob rescan lock e bridge->bus=NULL após remoção. Preparar API interna hold somente com PME e scan completamente positivo: manter bridge/bus/config/PME/TLS e callbacks válidos entre chamadas. Wrappers/caller atuais continuam removendo imediatamente; nenhum parâmetro físico exposto nesta fatia.
- Cleanup de bus retido deve fazer stop/remove sob lock antes de restore config/PME/TLS/free; erro de restore conserva bridge/owner e retry não repete scan. Recusa nova durante stop continua negativa mesmo após rollback completo, sem fingir falha de restauração. Não chamar pci_bus_add_devices/pci_host_probe, atribuir BARs, liberar enable_device, IRQ/DMA/firmware ou energia. Caller/collector/build/perfil ainda precisam de integração antes de qualquer load.
- Exercitar callbacks depois do retorno hold, bloqueio de novo scan, scan negativo/parcial, stop-refusal, todos os três restores e link perdido no teardown, owner retido/retry sem scan. Mutantes C compilados precisam morrer por SIGABRT/assertion, não timeout/import/compile. Mac e VM Ubuntu ARM64 com mesmos inputs/manifest/logs, AST/fatal-flake8/diff/publictree. Telefone fica no iOS carregando, sem DFU/PIN/console. Reunir integração e build com próximos gates antes de um boot agrupado.

- Gate173: dois testes C/45 cenários (29 anteriores+16 hold) e26 mutações compiladas SIGABRT/assertion passaram Mac/Ubuntu ARM64 em cópias isoladas, com dez inputs/logs SHA idênticos e preservados. Bind guard confirmado em pci-driver.c1536/1542, bus.c371 e pci.h799/804; fonte remove.c restaura bridge->bus=NULL. Cleanup de bus retido ocorre sob rescan lock antes de qualquer restore; refusals de stop persistem também após retry de restore, sem novo scan. Caller/collector/perfil não expõem hold e nenhum módulo foi carregado: essa prova é nativa/sintética, não hardware ou build kernel. AST/fatal-flake8/diff íntegros; build real e documentação seguem174, sem outro DFU.

### Incremento 174 — build e reprodução do lifecycle PCI retido

- Até quatro arquivos públicos: plano, JSON novo de prova, receita PME/ASPM e checkpoint STATUS. Build real dos seis módulos em M novo na VM dedicada, com46 inputs; somente o header scan difere do build169. Conferir Werror/modpost/ELF/vermagic e hashes no Mac, preservando fonte/config/Image/exports/REG_ON; não substituir perfil/módulo funcional ou recompilar Image.
- Registrar45 cenários/26 mutações C das duas plataformas, dez inputs idênticos e fontes PCI fixadas que delimitam bind, recurso e remoção. Receita reproduz native gates/build em cópia descartável; API hold é interna, ainda não selecionada por caller/coletor/parâmetro. Não transferir o módulo para o telefone nem chamar o coletor com metadata antiga.
- Documentar erro de stop preservado após rollback/retry, retenção de owner somente durante pending restore e remoção sob lock antes de energia. Próximo passo integra caller/collector/perfil e assignment/IRQ/IOMMU qualificados em candidatas agrupadas. JSON/links/Bash/diff/guard público, commit/push branch e issue39/9 com limites; CI nova não herda resultado do código físico anterior. Zero novos DFU/PIN/console, dados e remotos alheios intactos.

- Gate174: seis módulos reais W=1/KCFLAGS-Werror/modpost/ELF/vermagic passaram;46 inputs, somente scan header alterado desde169, PCIe74008 bytes/SHA22862d7f, REG_ON igual. Fonte/config/Image/exports intactos antes/depois; PCIe/REG_ON copiados e hashes/ELF/vermagic conferidos no Mac. Registro sanitizado liga código b0c0933, dez inputs/45 cenários/26 kills das duas plataformas e oito fontes PCI/hash; links/JSON/Bash/diff íntegros. Caller/coletor/perfil continuam sem seleção hold, prova física distinta do módulo828b1ae2 anterior; novo head CI pendente sem reutilizar PRdd2b0da. Próxima fatia integra ownership no caller e seleção/cleanup no coletor antes de qualquer teste físico, sem outro DFU agora.

### Incremento 175 — caller com retenção explícita e leitura de estado

- Cinco arquivos públicos: este plano, phone/kernel/n71-pcie-diagnostic.c, tests/n71_pcie_diagnostic_caller.c, tests/test_n71_pcie_diagnostic_caller.py e novo .agents/plans/n71-funcional-goal-decisoes.md. Contexto: adapter173/174 já mantém bus; caller atual354/380 chama cleanup sempre. Adicionar scan_hold bool0400/defaultfalse, exigindo host_scan+scan_pme_disable e os guards run/N71/enumerate/inventory/modos exclusivos existentes.
- Selecionar n71_pcie_scan_hold somente nesse opt-in. Após scan positivo, conferir bus e ownership reais pelo bridge/host, conservar referências módulo/MMIO/driver/reset/energia já adquiridas e retornar bound sem cleanup imediato. Sem flag espelhada no estado diagnóstico. Novo getter held0400 sob session_lock lê a fonte única; status anterior conserva formato. action=cleanup existente remove bus antes de restore/reset/energia e libera pin somente após tudo comprovado; scan negativo nunca fica em modo held positivo.
- Verificar callbacks MMIO após probe, held/status/owners vivos, segundo probe recusado, flags inválidas antes de registro, backend sucesso sem bus/owner, scan negativo/pending e falhas durante cleanup/stop/restores com retry sem scan nem put duplicado. Reutilizar73 cenários/21 mutações anteriores e acrescentar regressões e mutações compiladas SIGABRT/assertion; Mac/Ubuntu ARM64, mesmos cinco inputs do caller, AST/fatal-flake8/diff/guard público. Adapter173/174 conserva dez inputs e suas45/26 provas, sem repetição opcional. Depois rebuild real e integração do coletor/provenance/perfil antes de qualquer load; telefone no iOS para recarga, zero DFU/PIN adicional.
- CI fa53768 foi terminal cancelled nos dois eventos, não sucesso/falha funcional; registrar jobs individualmente quando retornarem. Isso não invalida os gates locais/VM já verificados e não autoriza atribuir causa ou ampliar timeouts. Decisão D1 registra getter separado e fonte de ownership no adapter.

- Gate175: caller real e MMIO qualificaram73 cenários anteriores+21 de hold e30 mutações compiladas SIGABRT/assertion no Mac e Ubuntu ARM64, em cópias isoladas com cinco inputs/logs SHA conferidos e preservados. Provas cobrem MMIO após probe/owners vivos, getters sob lock, flags antes de registro, sucesso sem bus recusado, scan negativo/pending, cleanup/stop/restore/reset/energia e retry sem rescan/put duplicado. Dez inputs do adapter173 continuam iguais:45/26 reutilizados. AST/fatal-flake8/diff íntegros; nenhum módulo/DFU/PIN solicitado. CI fa53768 terminou cancelled: Mac e Windows success, Ubuntu cancelled nos dois eventos, sem causalidade inferida. Build da integração segue176; seleção/coletor/perfil e hardware ainda pendentes.

### Incremento 176 — build do caller retido e reprodução sanitizada

- Até cinco arquivos públicos: este plano, decisões D1, novo JSON de prova caller/build, receita PME/ASPM e STATUS. Build em M novo da VM dedicada,46 inputs com somente caller C alterado desde174; conferir W=1/KCFLAGS-Werror/modpost/ELF/vermagic e SHA dos módulos no Mac. Preservar bundle/fonte/config/Image/exports e REG_ON; não trocar perfis funcionais ou transferir o módulo ao telefone.
- Registrar caller175 com cinco inputs/94 cenários/30 kills e adapter173 reaproveitado por seus dez inputs iguais. Receita delimita o novo parâmetro scan_hold explícito/defaultfalse, getter held separado e status legado; prova de build não habilita Wi-Fi, recursos, IRQ/DMA ou carga. Histórico do build174 permanece íntegro, com hash de código e limites próprios.
- Links/JSON/Bash/diff/guard público, commit/push branch e checkpoint issues39/9 com provas selecionadas; CI anterior cancelled não é aprovação desta integração. Próxima fatia seleciona build/provenance e conserva REG_ON/staging sob hold no coletor antes de load físico agrupado. Telefone permanece no iOS para recarga; zero novos DFU/PIN/console ou configuração global Mac.

- Gate176: build real seis módulos W=1/KCFLAGS-Werror/modpost/ELF/vermagic passou em M novo;46 inputs iguais ao174 exceto caller175. PCIe76.112 bytes/SHA b7e51d4d e REG_ON idêntico, com hashes/ELF/vermagic conferidos no Mac; fonte/bundle/config/Image/exports preservados antes/depois. Registro separado liga código3d410c7, cinco inputs/94 cenários/30 kills das duas plataformas e adapter45/26 reutilizado por dez hashes iguais. Documentação mantém histórico174, delimita held versus bridge pending e ausência de seleção/coletor/perfil/hardware; CI fa53768 cancelled explicitamente registrada. Nenhum módulo transferido ao telefone, Image ou DFU/PIN adicional. Próxima etapa é seleção/provenance/cleanup no coletor, antes de recursos/IRQ/IOMMU e prova física agrupada.

### Incremento 177 — contrato do resultado retido e seleção do build

- Preparação em dois arquivos: plano e decisões D2. Implementação em até cinco: plano, scripts/host/n71_scan_result.py, scripts/host/n71_scan_pme_result.py, novo scripts/host/n71_scan_held_result.py e novo tests/test_n71_scan_held_result.py. O caminho positivo do adapter retorna no SCAN_HELD antes de emitir SCAN_RESULT; não fabricar contagens, removals ou restores para satisfazer o parser temporário. Nenhuma alteração em módulo/build ou perfil físico nesta fatia.
- Extrair apenas os validadores puros de topologia/BAR e restore PME dos helpers pequenos, mantendo APIs anteriores. Parser held exige getters únicos, status e SESSION_HELD completos com referências módulo/reset/quatro domínios ativos, preparações TLS/PME positivas e ordenadas antes dos dispositivos/hold, topologia exata sem driver/decode/master e seis BARs sem atribuição. Rejeitar scan temporário, recusas, cleanup/restores durante a aquisição, duplicatas e registros truncados. Resultado conserva somente campos efetivamente observados.
- Cleanup held exige getter0, caller bound/owners zerados, remoção única com stop-error preservado, config→PME→TLS→reset→energia→caller final e retries consistentes. Negativo anterior ao hold delega ao parser PME existente; nenhum owner é descartado para converter falha em sucesso. Seleção local usa exclusivamente a prova caller176, flags booleanas exatas, ABI/Werror/modpost/ELF e dois módulos de nomes fixos; fonte/API não habilitam bind/DMA/radio.
- Tests cobrem resultados/ownership/ordem, estados inválidos, recursos/decode/driver, stop refusal/retry, escopo/metadata e fronteiras de tamanho/hash/ABI. Mutações executadas por AssertionError, sem import/timeout/compile como kill; gates em Mac/Ubuntu ARM64 com inputs/logs SHA preservados. Requalificar parsers/coletores anteriores afetados pela extração uma vez; reutilizar provas C/build somente com hashes iguais. AST/fatal-flake8/diff/guard público precedem commit/push. Integração CLI e perfil ficam na próxima fatia; zero novos DFU/PIN/console ou configuração global Mac.

- Gate177: parser held/seleção passou12 testes e29 mutações por AssertionError no Mac e Ubuntu ARM64 em cópias descartáveis. Extração compartilhada requalificada: scan6/8 e coletor anterior45/81, total63 testes/118 mutações por plataforma,34 inputs/logs SHA conferidos e preservados. Registros completos até fim de linha e todos os dispositivos/BARs antes de hold; stop-error coincide com a primeira recusa e continua negativo depois de rollback/retry. Teste detectou que ready0 sozinho não prova falha anterior; agora exige resultado negativo ou caller final sem owners e primary_error negativo, sem fabricar scan/cleanup. Recursos/COMMAND reais da sessão PME/ASPM conferidos contra o contrato. AST/fatal-flake8/diff íntegros; provas C e build reutilizadas com inputs iguais, nenhum módulo/CLI/perfil físico trocado ou DFU solicitado.

### Incremento 178 — reprodução do parser retido e limites

- Até cinco arquivos públicos: este plano, decisões D2, prova JSON nova, receita PME/ASPM e STATUS. Registrar63/118 por plataforma, os34 inputs e hashes dos cinco logs em Mac/Ubuntu ARM64, distinguindo12/29 novos de scan6/8 e coletor45/81 requalificados. Seleção local aceita somente prova caller176/ABI power2 com flags booleanas e dois módulos fixos.
- Receita explica SCAN_HELD sem SCAN_RESULT, getters/owners ativos e limpeza separada, campos não observados omitidos e stop-error preservado. Funções pequenas compartilham topologia/BAR e restore PME; APIs anteriores continuam qualificadas. Provas C/build continuam válidas por hashes e não serão repetidas sem mudança pertinente.
- Atualizar decisão D2 como parser/seleção aplicada, CLI/retomada/perfil/hardware pendentes. Links/JSON/diff/guard público, commit/push e checkpoint issue39 precedem próxima integração CLI. CI do head anterior e deste devem ser vinculadas separadamente; nenhum DFU/PIN/console, pacote/configuração global Mac ou firmware.

- Gate178: prova sanitizada nova registra código49d2158,34 inputs,63 testes/118 mutações por plataforma e cinco logs/hash em Mac/Ubuntu ARM64, distinguindo12/29 novos de6/8 e45/81 requalificados. C/build reaproveitados por hashes iguais, sem compilação ou Image adicional. Receita reproduz gates e delimita aquisição, cleanup, stop-error e ausência de contagens fictícias; decisão D2 aplicada no parser/seleção, com CLI/retomada/perfil/hardware pendentes. CI6e26fac terminal: PR37374903992 success3jobs; push37374896899 cancelled, Mac/Windows success e Ubuntu cancelled, causa não confirmada. Não cobre código177. Nenhuma transferência/load no telefone ou novo DFU/PIN/console. Próxima integração é CLI/provenance/retomada no mesmo boot.

### Incremento 179 — CLI com aquisição persistente e limpeza no mesmo boot

- Arquivos desta fase: este plano, `scripts/host/n71-link-session.py`, novo `scripts/host/n71_held_session.py` e novo `tests/test_n71_held_session.py`. Acrescentar `--scan-hold` explícito, seleção exclusiva do build176 e provenance booleana exata. Exigir host-scan/target/PME/power2; o caminho anterior permanece qualificado com seus próprios módulos.
- O modo retido reserva estado privado antes dos efeitos, comprova aquisição com getters reais e conserva REG_ON/módulos/staging. `--release-held` usa saída privada nova, o mesmo perfil/hash/ABI/boot e histórico completo; valida staged hashes, parâmetros somente leitura, ausência de bind/unbind e ownership antes de qualquer escrita. Limpeza retira PCI/config/PME/TLS antes de reset/power/REG_ON e permite retomar etapas parcialmente concluídas sem novo scan ou puts duplicados; stop-error negativo continua negativo.
- Testar contratos, filesystem privado, comandos shell reais em sysfs sintético e falhas/refusals/retomadas com dependências SSH simuladas. Mutações precisam falhar por AssertionError, sem contar import/compile/timeout. Requalificar o coletor45/81 uma vez; reutilizar parser12/29 e C/build por hashes se inalterados. Mac/Ubuntu ARM64 com inputs/logs SHA, AST/fatal-flake8/Bash/diff/guard público. Não transferir/carregar módulos, trocar perfil funcional ou pedir DFU durante esta fase; perfil físico e candidata agrupada seguem depois.

- Gate179: aquisição/retomada passou 18 testes e 22 mutações por AssertionError no Mac/Ubuntu ARM64, com 36 inputs finais iguais e preservados. O coletor anterior45/81 foi requalificado nas duas plataformas; seus inputs relevantes permanecem iguais após a correção isolada no coordenador/teste novo. Total 63 testes/103 mutações por plataforma, logs/resultados SHA conferidos. Comandos shell executados contra sysfs sintético e 17 comandos gerados passaram `bash -n`; AST e o lint de erros fatais do Flake8 7.3.0 no Python 3.12.6 já instalado passaram. O teste de diretório PCI ausente impediu considerar erro de ls como barramento vazio. Retomadas de cleanup pendente, unload PCI, restore/unload REG_ON e release completo não fazem outro scan nem repetem etapas comprovadas; stop-error negativo preservado. Parser/C/build reutilizados por hashes, sem módulos transferidos, perfil/Image trocado, DFU/PIN ou instalação global. Perfil físico e recursos/IRQ/IOMMU/HDQ/carga continuam pendentes.

### Incremento 180 — reprodução do CLI retido e prova sanitizada

- Cinco arquivos públicos: este plano, decisões D2, novo docs/evidence/n71-pci-held-session.json, receita PME/ASPM e STATUS. Registrar código 36c7f53, 36 inputs finais, 18 testes/22 mutações novos e compatibilidade45/81 nas duas plataformas; explicar a repetição apenas do coordenador/teste depois da correção de diretório PCI ausente e preservar os logs por SHA.
- Documentar seleção explícita, estado privado ligado a deployment/payload/initramfs/módulos, boot/histórico/getters/parâmetros vivos e retomadas de cleanup/unload/REG_ON, conservando stop-error. Estado de tentativa sem checkpoint não autoriza escrita; mudanças futuras de histórico devem integrar o protocolo da sessão. Perfil físico separado ainda precisa da provenance held antes de load agrupado.
- Conferir JSON/inputs/logs, links e blocos Bash; guard público e diff antes de commit/push na branch e checkpoint issue39. Provas C/build e parser anteriores somente reutilizadas por hashes. Zero hardware, DFU/PIN, firmware, pacote/configuração global ou merge/tag/release.

- Gate180: registro sanitizado liga código 36c7f53, 36 inputs finais, 18/22 novos e 45/81 de compatibilidade nas duas plataformas; total63/103 e três logs por plataforma, conferidos por SHA. JSON/inputs/links/blocos Bash/diff passaram; decisão D2 e STATUS delimitam CLI qualificado versus perfil/hardware pendentes. Docs registram diretório PCI ausente, checkpoints privados, retomadas sem etapas duplicadas e stop-error. Parser/C/build anteriores reaproveitados sem outra compilação/load; nenhum DFU/PIN/firmware ou mudança global. CI b8ae125 confirmada separadamente: PR37379581085 success três jobs, push37379576536 cancelled com Mac/Windows success e Ubuntu cancelled; não cobre o CLI novo. Próxima etapa é preparar o perfil separado e integrar controles que possam compartilhar o boot.

### Incremento 181 — composer do perfil PCI retido completo

- Quatro arquivos públicos: este plano, scripts/build/compose-n71-diagnostic.py, novo tests/test_n71_diagnostic_held_profile.py e runner de mutações do payload. Acrescentar --pcie-scan-hold explícito, exigindo --pcie-aspm-off, patchset power2 e --reg-on-module; reg-on-module sem hold é recusado antes da leitura de perfis ou criação da saída.
- Selecionar a prova caller176 pela API já qualificada; conferir tamanho/SHA/ELF/vermagic de PCIe e REG_ON antes de qualquer saída. Copiar os dois módulos e gerar os booleanos target/PME/noop/hold exatos automaticamente. Payload/DT/kernel/initramfs/identidades conservam o contrato anterior e não há autoload, boot ou configuração global.
- Testes de CLI/filesystem com dependências de identidade/kernel sintéticas, checks reais do layout/DT/módulos/provenance e recusas antes da criação da pasta; manter 7 testes/13 mutações anteriores e acrescentar guards novos. Mutações contam somente AssertionError, sem import/compilação/timeout. Mac/Ubuntu ARM64 em cópias descartáveis com inputs/logs por SHA; AST/Flake8 fatal/diff/guard público. Depois compor e verificar um perfil privado real separado, sem USB/DFU e sem publicar identidades.

- Gate181: composer passou 13 testes/29 mutações por AssertionError no Mac/Ubuntu ARM64, sendo 7/13 anteriores e 6 testes/16 mutações novos; 20 inputs e logs preservados/conferidos por SHA. Escopo, par qualificado, bytes/hash/ABI, links, cópia REG_ON e booleanos recusam entradas inválidas antes da saída; default conserva ausência de hold/REG_ON. AST/Flake8 fatal/diff íntegros. Perfil privado real separado composto e check do coletor held passou sem SSH/USB; payload byte a byte igual ao PME/ASPM anterior, kernel/DT/loader/initramfs/identidades preservados, PCIe76.112/REG_ON17.688 verificados por SHA/ELF/vermagic. Verificação local do snapshot usa o ID canônico do manifesto, não o número44 de entradas; ferramentas do boot preservadas. Nenhum novo Image/módulo compilado, boot, DFU/PIN ou instalação global. Prova sanitizada e controles PCI/IRQ/IOMMU/HDQ seguem antes da sessão agrupada.

### Incremento 182 — reprodução do perfil retido e provas locais

- Cinco arquivos públicos: este plano, decisões D2, novo docs/evidence/n71-pci-held-profile.json, receita PME/ASPM e STATUS. Registrar código c30a4ac, 13 testes/29 mutações nas duas plataformas, 20 inputs/logs por SHA, seleção do par e recusas antes da criação da saída.
- Documentar composição com --pcie-scan-hold/--reg-on-module e flags automáticas; perfil privado real separado passou verificação de identidade/payload/ABI/módulos e check do coletor sem SSH/USB. Payload idêntico ao PME/ASPM anterior, fonte/default/identidades preservados, snapshot local com 44 entradas e ferramentas de boot verificados; não publicar ID de snapshot, payload/DT/keys/aliases ou seus hashes pessoais.
- Atualizar D2/STATUS com perfil preparado versus hardware ainda pendente. Conferir JSON/inputs/logs/links/Bash/diff/guard público antes de commit/push branch e issue39. CI17d4c3c anterior success nos seis jobs, não cobre o composer novo. Próxima etapa reúne atribuição/IRQ/IOMMU e energia/HDQ para usar uma sessão física; não pedir DFU apenas para repetir inventário.

- Gate182: JSON sanitizado conferido contra os resultados privados nas duas plataformas, os 20 inputs públicos atuais e os quatro logs por SHA; 13 testes/29 mutações por plataforma permanecem válidos sem alterações nos inputs. Preservação e par de módulos conferidos contra a prova do perfil real; cinco links relativos e dois blocos Bash válidos, diff íntegro. Nenhuma ação física nesta etapa; inspeção USB detectou iPhone no modo normal do iOS. Recursos/IRQ/IOMMU e energia/HDQ continuam pendentes para uma sessão agrupada.

### Incremento 183 — política de escritas do alocador PCI

- Cinco arquivos públicos: este plano, decisões D3, novo phone/kernel/n71-pcie-resource-write.h, tests/n71_pcie_resource_write.c e tests/test_n71_pcie_resource_write.py. Preparar a política que o adaptador usará durante pci_bus_size_bridges/pci_bus_assign_resources, APIs exportadas no código-fonte do kernel selecionado; não chamar o alocador nem mudar o caller neste incremento.
- Capturar sem efeitos uma configuração N71/BCM4350 com decode e bus-master desligados, BAR0 de 32 KiB/BAR2 de 4 MiB e os três registradores adicionais que o alocador pode mudar (MEM_BASE/LIMIT, PREF_LIMIT_UPPER32, IO_BASE/LIMIT_UPPER16). Durante a fase explícita, aceitar somente BARs alinhados na janela PCI c0000000–ffffffff, upper32 zero, janela MEM compatível, desativação de IO/PREF e COMMAND/BRIDGE_CONTROL preservados. Verificar identidade/decode antes de cada escrita, tamanho/offset/valor, readback e primeiro erro; limites de tentativas, sem W1C, enable, DMA ou firmware.
- Restauração adicional somente após o caller encerrar a fase e remover o bus: conferir identidade/decode, restaurar os três registradores com readback e conservar pending em erro para repetição sem aquisição. A integração seguinte usará a limpeza genérica já existente para BARs, janelas restantes e demais owners, e participará do journal host antes de alterar histórico.
- Harness nativo executará a política real com backend injetável: entradas válidas e recusas, limites/alinhamento, falhas de leitura/escrita/readback, latência de erros e restauração repetível. Mutações compiladas contam somente SIGABRT/assertion; cópias descartáveis Mac/Ubuntu ARM64, inputs/logs por SHA, AST/Flake8 fatal/diff. Prova nativa não comprova alocação no kernel nem hardware; a sessão física continua agrupada e pendente.

- Gate183: política real passou 188 cenários nativos e 25 mutações compiladas por SIGABRT/assertion no Mac/Ubuntu ARM64, em uma prova unittest por plataforma. Seis inputs e ambos os logs conferidos por SHA, AST e Flake8 fatal passaram. Falha de compilação de um mutante foi corrigida sem contá-la como kill; o mutante final compilou e falhou por assertion. APIs de sizing/atribuição e referências PCI exportadas no kernel selecionado, verificadas em vmlinux.symvers; nenhum alocador/kernel/module/USB acionado. Integração ao adaptador/caller/journal e prova física permanecem pendentes. CI anterior 8f35fd2 concluiu success nos seis jobs, não cobre esta política nova.

### Incremento 184 — reprodução da política de atribuição PCI

- Cinco arquivos públicos: este plano, decisões D3, novo docs/evidence/n71-pci-resource-write.json, receita PME/ASPM e STATUS. Vincular fonte 8c16d0a, seis inputs e logs por SHA, 188 cenários/25 mutações compiladas nas duas plataformas e referências do alocador no kernel selecionado.
- Documentar captura sem efeitos, fase explícita de escrita, limites por registrador e restauração dos três registradores adicionais, distinta da limpeza genérica de BARs/janelas/owners. A prova não chama PCI core; não comprova reserva/atribuição, readback de registradores opcionais no hardware, ausência de sobreposição final, IRQ/IOMMU ou carregamento. Adaptador/caller/journal e build real continuam pendentes; nenhum DFU apenas para testar o helper.
- Verificar JSON versus inputs/resultados/logs e referências exportadas, comandos Bash/links/diff/guard público. Reutilizar a prova nativa intacta, registrar CI 8f35fd2 success nos seis jobs e publicar somente branch/issue39 autorizadas, mantendo hardware e as issues funcionais abertos.

- Gate184: JSON sanitizado conferido com os resultados Mac/Ubuntu ARM64, seis inputs atuais e dois logs por SHA, 188 cenários/25 mutações por plataforma e os quatro exports no kernel selecionado. Três links relativos e um bloco Bash válidos, diff íntegro. A prova nativa foi reutilizada com inputs intactos; nenhum teste físico, build ou reinício. Adaptador/caller/journal, reserva/atribuição, IRQ/IOMMU e energia continuam pendentes. Próxima integração deve validar a árvore de recursos e capturar o histórico antes dos efeitos por SSH.

### Incremento 185 — alocador PCI no bus retido

- Cinco arquivos públicos: este plano, phone/kernel/n71-pcie-scan.h, novo phone/kernel/n71-pcie-resource-assign.h, tests/n71_pcie_scan_host.c e tests/test_n71_pcie_scan_host.py. Manter o caminho padrão anterior; nova API interna de atribuição usa o bus retido, nunca refaz scan, não faz add_devices/bind/enable/DMA. O caller/CLI serão integrados depois.
- Validar topologia N71/BCM4350, BARs sem parent e layout esperado, janela MEM32/offset e configuração sem decode/master. Capturar antes dos efeitos e reservar a janela MEM32 na árvore global iomem; chamar sizing/atribuição do kernel sob rescan lock, com política de escrita ativa somente durante a fase. Conferir parent/flags/tamanhos/limites/alinhamento/não sobreposição, tradução PCI e readback de BARs/janela/COMMAND/BRIDGE_CONTROL. Conservar o primeiro erro, impedir outra tentativa no mesmo bus.
- Cleanup deve recusar fase ativa, remover o bus, restaurar campos adicionais antes dos BARs/janelas genéricos e liberar a janela global somente após configuração restaurada e child vazio. Erros conservam bridge/owners e permitem retry sem sizing/atribuição/scan. A restauração não pode ficar sem orçamento após uma falha de leitura na fase de aquisição.
- Harness nativo mantém os 45 cenários/26 mutações anteriores e acrescenta alocador/árvore/MMIO sintéticos executando o adaptador real: sucesso, recusas, conflitos de reserva, recursos incompletos/sobrepostos, tradução/readback, restauração/release em erro e repetição. Só SIGABRT/assertion conta como kill, com compilação Werror. Qualificar Mac/Ubuntu ARM64, inputs/logs por SHA, AST/Flake8 fatal/diff; nenhuma prova de hardware ou DFU nesta fase.

- Gate185: três provas unittest passaram em Mac/Ubuntu ARM64, 64 cenários nativos (45 anteriores/19 novos) e 51 mutações compiladas por SIGABRT/assertion (26 anteriores/25 novos), com 12 inputs e logs por SHA e exit real zero registrado antes da análise. AST/Flake8 fatal/diff íntegros. Dois mutantes foram corrigidos para compilar sem warnings e não foram contados durante as falhas de compilação; o observador privado foi corrigido para reconhecer marcadores após prefixos verbose. Atribuição usa a árvore/PCI API sintéticas, sem kernel real, módulo, caller/CLI ou USB. CI anterior d5814f4: PR37392226391 cancelled, Mac/Windows success e Ubuntu cancelled; push37392223262 failure no Ubuntu por timeout no binário PMGR observe (5 s) e compilação PMGR probe (30 s), Mac/Windows success. Causa desses timeouts segue não confirmada na issue38, sem contar como mutation kill. Próxima etapa expõe ação/getter no caller e integra build/provenance/journal antes do teste físico agrupado.

### Incremento 186 — atribuição PCI pelo caller no mesmo boot

- Quatro arquivos públicos: este plano, phone/kernel/n71-pcie-diagnostic.c, tests/n71_pcie_diagnostic_caller.c e tests/test_n71_pcie_diagnostic_caller.py. Incluir a API de atribuição já qualificada; action=assign exige scan_hold, sessão/módulo retidos, bus vivo/owned, reset e quatro domínios de energia ativos e nenhum erro anterior. Pin temporário e mutex de sessão cobrem efeitos; não chamar cleanup, scan, reset ou power-put durante a atribuição.
- Conservar primeiro erro de atribuição em primary_error, sem transformar EALREADY em falha da sessão. Getter resources separado e somente leitura informa ready/attempted/assigned/pending/claimed/active/error; assigned exige bus real retido, ausência de fase/erro e janela na árvore iomem. Após remover o bus, pending/claimed não autorizam assigned. Após liberar o bridge, getter conserva primary_error da sessão. Status/held e cleanup anteriores mantêm seus contratos.
- Harness caller real/MMIO com dependências de kernel/scan/atribuição sintéticas: manter 94 cenários/30 mutações anteriores, acrescentar opt-in/ownership/pin/lock, erro preservado, getter vivo, repetição e cleanup em falha. Mutações compiladas somente SIGABRT/assertion, Mac/Ubuntu ARM64 em cópias descartáveis, inputs/logs/exit por SHA, AST/Flake8 fatal/diff. Depois build real de módulos na VM dedicada, preservando fonte/config/Image/exports; seleção/provenance/journal e teste físico seguem antes da sessão agrupada.

- Gate186: caller/MMIO reais passaram uma prova unittest, 121 cenários nativos (94 anteriores/27 novos) e 59 mutações compiladas por SIGABRT/assertion (30 anteriores/29 novas) por plataforma Mac/Ubuntu ARM64, cinco inputs/logs/exit conferidos por SHA; AST/Flake8 fatal íntegros. Getter conserva também recusas anteriores à fase de atribuição e erros da política. Build real de seis módulos passou Werror/modpost/ELF/vermagic com 48 inputs; PCIe84.696 bytes, REG_ON17.688 bytes intacto e fonte/config/Image/exports preservados. Parâmetros action/resources/held/status e referências ao alocador/reserva/release foram conferidos no módulo. O download da prova ARM64 foi corrigido após erro de concatenação de Path, reutilizando o teste concluído sem rerun. Nenhum Image/boot/USB/DFU, bind/DMA/rádio ou medição física nesta etapa; seleção/provenance/journal continuam pendentes. CI anterior3f09eec concluiu cancelled nos dois eventos, Ubuntu cancelled e Mac/Windows success; log do job Ubuntu indisponível, causa não confirmada.

### Incremento 187 — reprodução da atribuição PCI integrada

- Cinco arquivos públicos: este plano, decisões D3, novo docs/evidence/n71-pci-resource-assignment.json, docs/N71_PME_ASPM_CANDIDATE.md e docs/STATUS.md. Vincular adaptador3f09eec/caller3ff8769, provas nativas independentes e build real, com todos os inputs públicos e logs por SHA; conservar evidências antigas como checkpoints históricos.
- Documentar action=assign/getter resources, fase explícita sem novo scan, primeiro erro/EALREADY e ordem de restauração/reserva; comprovar módulos/referências vinculadas e preservação do kernel. Diferenciar PCI API sintética, compilação real e operação física ainda pendente. Seleção/provenance/journal permanecem obrigatórios antes dos efeitos por SSH; não oferecer atalho que contorne o checkpoint.
- Conferir JSON contra resultados/inputs/logs e módulos atuais, links relativos, blocos Bash/diff/guard público. Reutilizar as provas intactas; registrar CI3f09eec terminal nos dois eventos, log cancelado indisponível e issue38 aberta. Publicar somente branch e atualizações de issue39/38 autorizadas; continuar solo sem reiniciar o aparelho nesta documentação.

- Gate187: evidência sanitizada conferida contra adaptador/caller, cinco inputs do caller e48 inputs/módulos/build atuais, logs/resultados por SHA e interface real. Seis links relativos/âncoras e dois blocos Bash passaram; provas nativas intactas reutilizadas. D3/STATUS e receita distinguem PCI API sintética, build real e prova física pendente, registram CI3f09eec terminal e próxima integração ao journal/seleção. Nenhum módulo carregado ou novo DFU; projeto funcional continua aberto.

### Incremento 188 — contrato host de atribuição e limpeza PCI

- Cinco arquivos públicos: este plano, novo scripts/host/n71_resource_result.py, novo tests/test_n71_resource_result.py, scripts/host/n71_scan_held_result.py e tests/test_n71_scan_held_result.py. Seleção separada do build de atribuição qualificado, ABI power2, flags booleanas, getters/APIs vinculadas e REG_ON igual ao perfil anterior; defaults e seletor held anterior preservados.
- Validar getter resources completo/único, saída da ação e resultado kernel único/ordenado, orçamento e owners ainda ativos; sucesso exige pending/claimed/assigned e zero erro. Falha conserva primary_error e seus owners, inclusive recusa anterior à fase sem evento/kernel novo. Não fabricar contagens quando a fase não começou. Base held aceita primary_error explicitamente comprovado, mantendo erro zero como default.
- Cleanup exige bus removido antes dos campos adicionais, restauração genérica antes de release da janela, PME/TLS/reset/energia/caller ordenados e getter final sem owners. Conferir histórico do resultado anterior e primeiro erro, retries negativos seguidos de sucesso, reserva pendente e evento desconhecido/duplicado recusados; liberar REG_ON somente depois desses controles. Journal/coletor/composer serão ligados após qualificar este contrato.
- Testes de contrato usam logs/sysfs sintéticos e build público real, recusas de getter/budget/ordem/ownership/erro/metadata e mutações por AssertionError em cópias descartáveis Mac/Ubuntu ARM64. Reutilizar C/build intactos; inputs/logs/exit, AST/Flake8 fatal/diff. Sem boot/DFU/SSH físico nesta etapa; atribuição/restauração e recursos funcionais continuam pendentes.

- Gate188: contrato novo passou nove testes/29 mutações por AssertionError em Mac/Ubuntu ARM64; compatibilidade held12/29 e journal18/22 passou nas duas plataformas e foi reutilizada após corrigir somente parser/fixture, com36 inputs de compatibilidade intactos. Total39 testes/80 mutações por plataforma,39 inputs/logs/exit e AST/Flake8 fatal conferidos. Getter/resultado/saída, budgets e owners, falha anterior à fase sem contagens fictícias, extra→config→release→PME/TLS/reset/power/caller e primeiro erro passaram. Stop negativo ocorrido depois de atribuição positiva continua negativo após restauração; recusa anterior ao resultado positivo é inválida. A fixture foi corrigida para conservar o SESSION_HELD histórico e alterar somente a recusa, sem também mudar stop-error por substring; tentativas com baseline inválido não qualificaram gates. Seleção ABI usa o guard central held, evitando validação redundante. C/build anteriores permanecem intactos, nenhum boot ou DFU; composer/coletor/journal ainda precisam expor esse contrato no mesmo boot.

### Incremento 189 — seleção explícita do módulo com atribuição PCI

- Cinco arquivos públicos: este plano, scripts/build/compose-n71-diagnostic.py, scripts/host/n71-link-session.py, tests/test_n71_diagnostic_held_profile.py e tests/test_n71_held_session.py. Composer recebe --pcie-resource-capable e coletor --resource-capable; ambos exigem held explícito, cujo contrato já requer host/target/PME/power2/ASPM e REG_ON. Selecionar somente o build real186 através de n71_resource_result, conservando a seleção held anterior quando a flag não for usada.
- Provenance pcie_resource_capable deve ser booleana exata e coincidir com o coletor. Ausência da chave nos perfis antigos equivale somente a false. Acrescentar a seleção à Session, inclusive no check de retomada e no caminho held real; nenhuma ação assign automática durante aquisição. Identidades, initramfs, kernel/DT, snapshots e default continuam preservados.
- Testes executam composer/seletores reais com arquivos privados e evidências de build sintéticas, além da seleção dos hashes públicos reais. Conferir payload/identidades/par de módulos/provenance, tipos/escopo inválidos, módulos trocados ou metadata divergente recusados antes dos efeitos e --check sem SSH. Executar mutações por AssertionError e compatibilidade dos caminhos afetados em cópias Mac/Ubuntu ARM64; reusar C/build intactos, AST/Flake8 fatal/diff e logs por SHA.
- Esta fatia prepara a candidata; a próxima liga assign ao journal antes de qualquer teste físico. Não iniciar DFU nem pedir desbloqueio para essa integração. CI5df8a73 segue observado pelo run existente, sem restart ou atribuição especulativa de causa.

- Gate local da primeira fase: composer nove testes e collector/journal vinte testes/22 mutações anteriores passaram, com Flake8 fatal/diff íntegros. Cinco arquivos alterados; contrato novo ainda precisa das mutações específicas e da prova ARM64 antes de qualificação. Nenhuma intervenção no telefone.
- Segunda fase de 189, quatro arquivos: plano, tests/run_n71_diagnostic_payload_mutations.py, tests/test_n71_diagnostic_held_profile.py e tests/test_n71_held_session.py. Atualizar a cópia descartável do composer para incluir n71_resource_result e o anchor do seletor; acrescentar mutações de scope/seleção/provenance/default e dispatch CLI/Session. É uma dependência real descoberta na leitura do runner, pois a nova importação não existia na lista antiga. Verificar a propagação da flag aos dois caminhos held e qualificar o conjunto em cópias exclusivas das duas plataformas; não aceitar falha de importação como kill.

- Gate189: 82 testes/144 mutações por AssertionError em cada plataforma Mac/Ubuntu ARM64, 53 inputs atuais/exit/logs SHA conferidos e AST/Flake8 fatal/diff íntegros. Composer16/33, held21/30 e collector legado45/81; seis testes e12 mutações novos. Após as correções somente na fixture composer, held21/30 e legado45 testes foram reutilizados com52 inputs intactos; composer16/33 e legado81 mutações foram executados sobre o pacote final. Os gates anteriores interrompidos não foram considerados qualificação completa. A fixture agora exige oito arquivos fixos em vez de comparar dois outputs potencialmente incompletos, e mantém ambos os manifests sintéticos disponíveis para distinguir seleção errada de arquivo ausente.
- Perfil privado real novo completo passou composer/--check e igualdade com o held anterior de payload/DT/kernel/loader/initramfs/identidades/deployment/REG_ON; somente PCIe e provenance mudaram. Seleção PCIe84.696 bytes/SHA2dcdebc2, flags booleanas exatas e --resource-capable conferidos sem SSH/USB. Os48 inputs do build real186 continuam iguais; não recompilados. Nada carregado no iPhone, nenhum DFU. Próxima integração é assign no journal e seus getters/provas/cleanup antes da sessão física agrupada.

- Reprodução de189 em quatro arquivos: plano, novo docs/evidence/n71-pci-resource-profile.json, docs/N71_PME_ASPM_CANDIDATE.md e docs/STATUS.md. Vincular código d94a14e, os53 inputs, cinco logs por plataforma e82/144, distinguindo66 testes/30 mutações reutilizados com52 inputs intactos. Receita inclui --pcie-resource-capable/--resource-capable e candidata real verificada, sem oferecer assign manual antes de sua integração ao journal. Conferir JSON/links/Bash/diff/guard público e versionar na branch autorizada; atualizar issue39 como progresso, sem fechar Wi-Fi/energia.

- Reprodução189 conferida contra as provas privadas,53 inputs atuais, cinco logs por plataforma e candidata real; três links relativos e dois blocos Bash passaram. C/build intactos reutilizados sem nova compilação. CI5df8a73 terminou cancelled nos dois eventos, Mac/Windows success e Ubuntu cancelled; causa não confirmada, sem restart e sem contar como falha funcional desta seleção. Código da seleção d94a14e separado da documentação; próximo trabalho continua assign no journal, sem intervenção do operador.

### Incremento 190 — atribuição PCI com prova durável e retomada

- Cinco arquivos públicos: este plano, scripts/host/n71-link-session.py, scripts/host/n71_held_session.py, novo scripts/host/n71_resource_stage.py e novo tests/test_n71_resource_stage.py. Acrescentar --assign-held DIR exclusivo de --release-held, exigindo --resource-capable/--scan-hold e ausência de previous-clean. Atribuição parte somente de aquisição qualificada no mesmo boot, sem outro insmod/scan/reset/REG_ON.
- Helper separado cuida de getter resources somente no modo novo, flags booleanas do journal, resultado/prova de atribuição e validação do estado retido. O coordenador mantém identidade/checkpoint/histórico/módulos/params/REG_ON existentes; compara getter vivo com checkpoint e exige prova de atribuição quando sua intenção já foi registrada. Flags ausentes nos journals antigos equivalem somente a false. Rejeitar prova desconhecida, mudada ou perdida, mudança de modo ou de ownership, antes dos efeitos.
- Salvar resource_attempted antes da ação; conferir boot/release/held/REG_ON/getter imediatamente antes do setter. Validar saída real, getter e evento através de n71_resource_result e preservar a prova privada/hash/checkpoint. Atribuição comprovada é reutilizada em outra retomada sem repetir a ação; erro negativo conserva seus owners e resultado, permitindo --release-held no mesmo boot. Nada de fabricar contagens/markers ou transformar erro em sucesso.
- Cleanup do modo novo lê resources e usa o parser de atribuição, incluindo campos extras/reserva/primeiro erro, antes de PCI unload e REG_ON restore. Retomadas de restauração, liberação da janela e unload pulam etapas já comprovadas. Return code continua negativo após cleanup quando houve erro de atribuição ou stop. C confirmou que config_pending evita repetir restauração genérica já concluída durante retry da janela; não normalizar registros para simular essa propriedade.
- Testes executam coordinator/helper/collector reais com sysfs/logs e telefone sintéticos: aquisição→atribuição→reuso→release, erros negativos, restore/window/unload retries, perda de prova/checkpoint, getter/modo/histórico divergentes, flags e check CLI sem SSH. Rodar comandos gerados em Bash contra arquivos privados, mutações por AssertionError e compatibilidade dos caminhos anteriores em Mac/Ubuntu ARM64. Inputs/logs/exit SHA, AST/Flake8 fatal/diff/public guard; reutilizar C/build intactos. Nenhum DFU nesta integração; candidata real189 será usada somente após esses gates.

- Gate190: 82 testes/137 mutações por AssertionError em Mac/Ubuntu ARM64,55 inputs atuais/logs/exit SHA conferidos, AST e Flake8 fatal/diff íntegros. Novo estágio16/26, held21/30 e legado45/81;37 testes/56 mutações Mac já aprovados reutilizados com55 inputs iguais, ARM64 executou o conjunto. Comandos de ação e snapshot rodaram em Bash contra arquivos privados; guards recusaram mudança de boot/held/REG_ON/resources antes do setter. Erros de atribuição/stop permaneceram negativos após liberação, sem repetir assign/scan/restore já concluído; perda de prova ou getter/histórico inconsistente conservou owners.
- Mutações de getter tiveram anchor específico para não atingir extra_proofs; requisito de atribuição foi reordenado para manter único o anchor legado de release. A fixture passou a exigir o estado intermediário real (bus removido, rollback extra concluído e janela ainda claimed) antes de ler o checkpoint; negativos anteriores não foram contados como cleanup exercitado. Gates interrompidos foram excluídos da qualificação. C/build48 inputs intactos; candidata privada real passou --check atualizado, sem SSH/USB/DFU. Próxima etapa documenta a ação e prepara uma sessão física agrupada, mantendo Wi-Fi e energia abertos.

- Reprodução190 em quatro arquivos: plano, novo docs/evidence/n71-pci-resource-session.json, docs/N71_PME_ASPM_CANDIDATE.md e docs/STATUS.md. Vincular código2e07258,55 inputs, quatro logs por plataforma e82/137; distinguir16/26 novos, held21/30 e legado45/81, com37/56 Mac reutilizados. Receita documenta aquisição/assign/reuso/release no mesmo boot, intenção/prova/checkpoint e limites em falhas de transporte. Atualizar checkpoint e issue39 sem fechar recursos funcionais. JSON/links/Bash/diff/public guard; dados de perfil/firmware/identidade/logs permanecem privados.

- Gate de reprodução190: JSON coincide com provas privadas Mac/ARM64 e55 inputs atuais; dois blocos Bash passaram análise de sintaxe e três links relativos/âncoras foram conferidos. Limites físicos permanecem explícitos e negativos. USB consultado sem intervenção: um iPhone em modo normal; não foi solicitado PIN nem iniciada recuperação/DFU. Publicar os quatro arquivos desta reprodução na branch autorizada e preparar atribuição/reuso/cleanup/serviços/snapshot em um único boot físico.

### Incremento 191 — atribuição e restauração físicas numa sessão agrupada

- Contexto: código2e07258/reprodução691c4b6 publicados; perfil resource-capable anterior íntegro, ferramentas/Pongo qualificados e snapshot44 entradas verificado. USB detectou um iPhone normal, com bateria100% e alimentação externa conectada. Bloqueio de tela não exige PIN para DFU manual; não alterar cabo/porta, instalar ferramentas ou repetir etapas físicas anteriores sem necessidade.
- Arquivos públicos da fase: este plano, nova evidência física em docs/evidence/, reprodução em docs/N71_PME_ASPM_CANDIDATE.md e checkpoint em docs/STATUS.md. Perfis, logs, boot ID, snapshot ID e identidades permanecem privados; publicar apenas contagens, contratos, hashes públicos e limites comprovados.
- [x] Verificar perfil, identidades, payload, ferramentas, Pongo e integridade do snapshot antes da intervenção. Reconfirmar USB imediatamente antes do monitor.
- [ ] Um DFU manual, sem desbloqueio, contador ou página; restaurar dados e confirmar release/boot/SSH/HTTP antes dos efeitos PCIe.
- [ ] Aquisição held resource-capable; uma atribuição; se positiva e comprovada, reuso sem outro setter; release no mesmo boot, sem scan/reinício entre etapas. Resultado negativo com prova completa segue para release, preservando o erro. Não fabricar prova nem continuar após divergência de estado/transporte.
- [ ] Comprovar remoção/rollback extra/configuração/janela/PME/TLS/reset/power, unload PCI/REG_ON e retorno aos valores originais. Falha conserva owners para retry somente do cleanup no mesmo boot.
- [ ] Confirmar serviços, salvar/verificar snapshot e sync; retornar ao iOS e consultar bateria sem pedir PIN. Limitar a sessão experimental; ainda não existe prova de carga Linux. Sem injeção de falhas físicas nem bind/enable/DMA nesta fase.
- [ ] Documentar e publicar resultado real e limites, atualizar issue39; Wi-Fi/IRQ/IOMMU/driver/firmware e telemetria/carga permanecem abertos até suas próprias provas. CI completa tem pendência38: checkpoint565203f Ubuntu push falhou em dois timeouts de compilação30s, PR cancelled; Mac/Windows passaram, sem rerun ou relaxamento dos gates.

- Estado de execução191: monitor real iniciado com o perfil/snapshot verificados, Recovery confirmado e uma orientação de DFU manual enviada. O wrapper encerrou com exit1 por ausência de Pongo/DFU; nenhum payload Linux foi enviado. Consultas USB seguintes continuaram mostrando Recovery. Não reabrir o monitor em laço nem exigir outra sequência se o DFU já tiver sido realizado; conferir USB e reutilizá-lo ao retomar.
- Gate físico bloqueado pela entrada manual em DFU, observado em três rodadas consecutivas. Os55 inputs da qualificação continuam intactos e os gates Mac/ARM64 de82 testes/137 mutações permanecem válidos; nova suíte/build ou alteração da receita não remove essa dependência física. Revisão de energia confirmou que cycles/inspect já passaram e não precisam ser repetidos; transferência SN2400/HDQ ainda exige aquisição/restauração qualificada. Não registrar o goal como concluído nem atribuição/Wi-Fi/telemetria como comprovados.

### Incremento 192 — leitura REG_ON acrescentada ao histórico retido

- Retomada física: USB/modelo confirmados, iOS100% com carga/fonte externa ativos, perfil/ferramentas/snapshot íntegros. Um boot power2 restaurou44 entradas e confirmou SSH/HTTP; aquisição held passou. A atribuição foi recusada antes de salvar intenção/setter: o snapshot live acrescentou somente N71_REG_ON_READ error=0 value_valid=1 value=81. O getter qualificado do módulo emite esse registro a cada leitura; o histórico estritamente idêntico confundiu observação com mudança de ownership.
- Fase A, cinco arquivos: plano, scripts/host/n71_held_session.py, novo scripts/host/n71_held_history.py, tests/test_n71_held_session.py e novo tests/test_n71_held_history.py. Preservar o prefixo integral do histórico e permitir somente sufixo não vazio de leituras REG_ON positivas completas, com value_valid1 e valor igual ao getter vivo único. Com REG_ON ausente, histórico continua exatamente igual. Comparações existentes de estado/valor vivo contra checkpoint permanecem obrigatórias antes dos efeitos.
- Não eliminar ou reescrever linhas: todas as observações permanecem nas capturas, provas e checkpoints com seus hashes. Erros, valor divergente, prefixo alterado/perdido, atividade desconhecida e leitura após unload recusam a continuação. Corrigir a fixture para emitir leituras como o módulo real; cobrir leituras adicionais entre tentativas recusadas, ausência de leitura e estados inválidos por efeitos observáveis e mutações por AssertionError.
- Qualificar no Mac/Ubuntu ARM64 os caminhos held/resource e a regressão nova, AST/Flake8/diff; C/módulos/payload intactos. Continuar assign/reuse/release a partir da aquisição original, no mesmo boot, sem novo scan ou DFU. Depois serviços/snapshot/sync/retorno iOS e documentação sanitizada; não fazer I/O HDQ, bind ou DMA nesta correção.
- Fase A: regressão7 testes/7 mutações e held21/30 passaram no Mac. Compatibilidade resource revelou fixture defasada: uma tentativa recusada gera leitura real adicional, que o teste de operação desconhecida não copiava para seu checkpoint adversarial; a recusa ocorria por prefixo diferente antes de exercitar o guard pretendido. Fase B toca somente tests/test_n71_resource_stage.py: conservar o prefixo e copiar exatamente o delta real de logs da fixture antes de inserir a operação desconhecida; exigir a recusa antes do setter cleanup. Rerodar o gate resource e confirmar as provas ARM64, sem ampliar permissões de produção.
- Gate192 final: Mac/Ubuntu ARM6444 testes/63 mutações por AssertionError em cada plataforma,57 inputs iguais, AST e Flake8 fatal/diff aprovados. Históricos7/7, held21/30 e resource16/26; após a única correção de fixture resource, os outros dois gates permaneceram válidos e foram reutilizados. O resumo inicial buscava nomes de markers incorretos; contagens foram conferidas nos markers reais dos runners e nos logs aprovados, sem rerodar testes ou contar gates interrompidos. C/build48 inputs permaneceram intactos.
- Continuação física no mesmo boot: aquisição positiva, atribuição uma vez com error-5/pending1/claimed1 e9 tentativas/2 escritas comprovadas. Primeira recusa root0:08/030/dword/0000ffff; demais recusas são latched. Primeiro release comprovou bus removido, rollback extra/genérico e janela liberada, mas reteve reset/energia pelo stop-error-5. Retry somente de cleanup liberou os owners, descarregou módulos e restaurou REG_ON80; resultado permaneceu negativo, com cleanup_verified true/stop-error-5. Nenhum reuso de atribuição positiva, bind, DMA ou HDQ foi executado.
- SSH/HTTP/Bash/Herdr, snapshot44/sync e retorno automático USB ao iOS passaram; uptime final26 minutos, sem reinício intermediário. iOS100% antes e77% após, incluindo transições; carregamento/fonte externos ativos no retorno. A duração aumentou pela correção do histórico durante o boot; encerrar e manter recarga durante desenvolvimento offline. Isso não comprova corrente líquida, saúde ou carga sustentada Linux. Próximo diagnóstico precisa registrar o readback real da primeira recusa0x30 antes de alterar a permissão de escrita; não presumir bits hardwired ou ignorar EIO.
- Reprodução192 em cinco arquivos: plano, docs/STATUS.md, docs/N71_PME_ASPM_CANDIDATE.md, docs/evidence/n71-reg-on-held-history.json e docs/evidence/n71-pci-resource-first-physical.json. Referenciar eba8f30/71df973,57 inputs/gates44/63 e o resultado físico negativo com cleanup completo; diferenciar atribuição negativa de sucesso e preservar o erro original. Validar JSON/provas privadas, links/âncoras/Bash/diff/public guard; publicar na branch autorizada e atualizar #39/#2/#38 sem fechar recursos ainda não comprovados.
- Gate documental192:57 inputs atuais/JSON/provas privadas conferidos; um bloco Bash e cinco links relativos/âncoras válidos, dados privados excluídos. A verificação inicial confundiu o nome de um flag negativo sobre snapshot IDs com um identificador real; corrigida para detectar o campo/valor ou formato de ID, sem remover o flag nem publicar o ID. Snapshot final manual44 entradas foi verificado no store protegido. Código e fixture em commits separados eba8f30/71df973; nenhuma nova suíte/build na documentação.

### Incremento 193 — caller runtime do brcmfmac qualificado sem novo boot

- Contexto: o operador dispensa confirmações de tela de bloqueio, cabo, disponibilidade ou temperatura quando nenhuma ação dependente é necessária. Seguir solo; solicitar somente a intervenção física indispensável, depois de preparar a candidata agrupada. Este incremento não solicitou DFU/reboot/PIN, não instalou pacotes/configuração global e não alterou perfil ou firmware.
- [x] Conservação de owners parciais e erro de publicação sob lock em4576d7b; exclusão MSI manual emc370096, antes de power/config/core IRQ.
- [x] Caller em e088212: opt-in desligado por default, actions prepare/publish/release, getter passivo separado, pin/mutex/power/provider gates, primeiro erro assíncrono conservado e cleanup runtime antes de consumidores/DART/reset/power. Release admite erros anteriores e conserva owners para retry.
- [x] Fixture DART isolada mantida emb2429a4, incluindo o caso de retorno0 com provider owned; runtime coberto separadamente pelo caller completo.
- [x] Gates Mac/Ubuntu ARM64:575 cenários/455 mutações C por plataforma; caller270/234 (novos54/57), adapter30/26, MSI61/31, DART31/17 e host183/147. AST/lint fatal aprovados, sem typechecker Python configurado. O timeout de um mutante host DART no Mac foi resolvido retomando somente seu método; falha inicial não conta como kill. A fixture foi fortalecida após um mutante de overwrite da primeira causa sobreviver; somente a rodada final completa do caller foi aceita.
- [x] Build completo com caller real142.232 bytes/SHAb4888de18e8e93f9320300350cdd646a6c583fe127e7c2adee99549a7216b136,135 imports/ELF64/AArch64/vermagic/parâmetros verificados e bytes/hash auditados no Mac.69 inputs e fonte/config/Image/exports preservados. CI anteriorb8e8165 concluiu seis jobs verdes nos dois eventos; essa prova não se aplica ao novo head.
- Documentação da fase em cinco arquivos: plano runtime, este goal, decisõesD15, docs/N71_BRCMFMAC_RUNTIME.md e docs/evidence/n71-brcmfmac-caller-qualified.json. Inputs/logs/binários completos privados, evidência pública sanitizada. Nenhum módulo novo selecionado/carregado, publicação PCI física, firmware ou DFU realizado; não declarar rádio/carga prontos.
- [ ] Próxima fase autorizada: collector/journal/seleção runtime, intenção antes de cada efeito, observação assíncrona e unload normal antes de release. Preparar firmware/calibração privados compatíveis e energia/HDQ antes de uma sessão física agrupada. Comprovar scan/associação/DHCP/SSH e telemetria/carga, manter snapshots/serviços/recovery e atualizar issues40/9/2 sem fechamento antecipado. Goal completo permanece ativo.

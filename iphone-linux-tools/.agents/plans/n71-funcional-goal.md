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

## Limites e continuidade

Não instalar pacotes no Mac, modificar política/rede global/sudoers/PF/firewall/DNS, contas remotas ou recursos fora do projeto. Não publicar firmware/calibração/serial/MAC/chaves/snapshots. VM dedicada e artefatos privados, preservando fonte/build funcional. Não prolongar operação não supervisionada antes de carga validada. Pedir apenas DFU/ações físicas indispensáveis; ausência de informação crítica para registrar escrita não autoriza inventá-la. Bloqueios concretos entram nas issues e no goal somente segundo o limiar de três turnos; continuar pesquisa/implementação independente enquanto houver avanço possível.

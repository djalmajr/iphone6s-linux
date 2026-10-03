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

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

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

Gates relevantes: lint/AST e compilação C/DTS, tests observáveis e mutações por asserção, fontes/hashes/guard público, native VM, CI exato e prova física separada. Não repetir suítes aprovadas sem mudança relevante. Não há typechecker Python configurado. Falha de build/probe não conta como teste negativo aprovado. Compilação não comprova segurança elétrica ou rádio.

## Limites e continuidade

Não instalar pacotes no Mac, modificar política/rede global/sudoers/PF/firewall/DNS, contas remotas ou recursos fora do projeto. Não publicar firmware/calibração/serial/MAC/chaves/snapshots. VM dedicada e artefatos privados, preservando fonte/build funcional. Não prolongar operação não supervisionada antes de carga validada. Pedir apenas DFU/ações físicas indispensáveis; ausência de informação crítica para registrar escrita não autoriza inventá-la. Bloqueios concretos entram nas issues e no goal somente segundo o limiar de três turnos; continuar pesquisa/implementação independente enquanto houver avanço possível.

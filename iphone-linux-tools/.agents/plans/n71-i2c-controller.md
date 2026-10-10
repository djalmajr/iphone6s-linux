# Controlador I2C1 por polling — #2

## Contexto

Demanda Wi-Fi/energia autorizada, em execução solo. Os ciclos físicos genpd e de descriptors ASIS já passaram; não repeti-los como objetivo isolado. Ainda faltam controlador, transporte SN2400 e gauge. Não perguntar por tela de bloqueio, console, cabo, disponibilidade ou temperatura de rotina; preparar os testes antes de uma ação física indispensável.

## Decisão do transporte

A [D37](n71-funcional-goal-decisoes.md#d37-inicializar-i2c1-por-polling-com-restauração-própria) é o registro canônico: polling, recursos próprios, restauração explícita e descriptors retidos antes da execução física. Sem carga Linux, gauge ou transporte físico comprovados.

## Arquivos e fases

1. Até três executáveis: novo header `phone/kernel/n71-i2c-controller.h`, fixture `tests/n71_i2c_controller.c`, runner `tests/test_n71_i2c_controller.py`. O header reutiliza o predicate idle de `n71-i2c-controller-observe.h`; esse arquivo permanece intacto. Compilar também em contexto kernel com fonte/config/exports power2 preservados.
2. Após os gates: backend de descriptors retidos e integração operacional em fase própria de até cinco executáveis. Somente callback de pins com reserva comprovada e readback fresco pode satisfazer o contrato do header. Não chamar este header com o antigo módulo ASIS, que libera descriptors ao retornar.
3. Preparar transporte limitado SN2400/HDQ, sem scanner ou probe A10. Agrupar coleta física com Wi-Fi, snapshot e cleanup no mesmo boot. Não pedir DFU enquanto esses pré-requisitos não estiverem prontos.

## Contrato da fase1

Chamador serializa as funções, mantém consumer/OF/descriptors e callback vivos, preserva genpd ativo/attached/usage/cleanup e não suspende o domínio enquanto restar MMIO ou restauração pendente. Callback verifica descriptors realmente retidos e palavras dos pinos iguais à baseline fresca; não é um booleano que presume ownership. O header não cria lookup, seleciona mux ou registra adapter/IRQ/cliente.

Exigir consumer root sem bus/driver/pm_domain, recurso20a111000/1000 e clkref fixed-clock24MHz, único phandle sem args. Obter clock por OF, proteger a taxa, habilitar uma referência própria e conferir24MHz; não alterar taxa nem exigir que o clock global fique desligado ao liberar a própria referência. Reservar MMIO exclusivamente.

Antes de escrever, ler REV28, SMSTA14, XFSTA0c, IMASK18 e CTL1c duas vezes. Exigir estabilidade integral, revisão2, status idle com TX vazio/RX vazio, XFSTA0, IMASK0 e CTL somente com divisor nos oito bits baixos. Recusar comandos de reset/unjam/enable na baseline, pois reproduzi-los não seria uma restauração qualificada. Não ler FIFOs ou escrever SMSTA.

Marcar obrigação de restore antes da primeira escrita. Usar IMASK0 e CTL070f (reset TX/RX/unjam, divisor15 para100kHz, sem EN da revisão6). Conferir novamente pinos e amostras; polling nominal de até100 esperas de1ms, sem prometer limite para backends bloqueados. CTL0f ou070f com demais words iguais à baseline é a condição inicial aceita; são condições explícitas a verificar fisicamente, não uma prova de semântica de bits self-clearing.

Liberação só escreve CTL da baseline depois de conferir pinos, alimentação ativa e controlador estável/idle, com bits de CTL restritos à máscara conhecida07ff. Readback duplo deve reproduzir as cinco words originais. Em erro de restore, manter MMIO, clock e obrigação, permitindo retry sem novo boot; o chamador deve reter módulo e objetos. Erro primário não é substituído pelo erro de cleanup. Somente restore comprovado libera mapping, região e as próprias referências de clock. Reset pode ter efeito elétrico; igualdade de registradores não prova que a bateria carregue.

## Tarefas

- [x] Conferir fonte958481f, revisão física2, DTS24MHz e APIs de clock.
- [x] Implementar aquisição, inicialização e release com falhas de escopo, busy, clock, amostragem e readback.
- [x] Executar contratos/mutações por asserção no Mac e ARM64; build kernel real Werror/modpost.
- [x] Publicar somente código/evidência sanitizada e reprodução; preservar fonte/config/Image/exports.
- [x] Integrar descriptors retidos e caller operacional antes de uso no aparelho.
- [ ] Completar transporte/gauge e prova física agrupada, mantendo issues/goal abertos até aceite real.

## Verificação

Fixture executa o header real; APIs OF/clock/MMIO/pinos são sintéticas e não provam hardware. Mutações contam somente com SIGABRT/asserção, após compilação bem-sucedida. A CI existente descobre `test_*.py`. Gates anteriores permanecem válidos enquanto seus inputs estiverem intactos. Não instalar ferramentas no Mac, reconstruir Image ou trocar perfil para qualificar apenas um módulo/header. Relatar explicitamente a falta de type checker Python se continuar ausente.

## Resultado da fase1 — 2026-10-10

Código609dd39: três executáveis novos. Mac/ARM64 passaram50 cenários e15 mutações compiladas por SIGABRT/asserção. Probe kernel de11.192bytes,26 imports qualificados, ELF64/AArch64 e vermagic power2; ele recusa load com ENODEV e não é um módulo operacional. Checkpatch estrito0erros/0avisos/0checks, AST e lint fatal verdes, sem type checker Python configurado. Fonte primária e config/Image/exports foram preservados. [Reprodução e limites](../../docs/N71_I2C_CONTROLLER.md), [evidência sanitizada](../../docs/evidence/n71-i2c-controller-reset.json).

Desvio de teste corrigido: o cenário de MMIO fora do escopo inicialmente mudava também o tamanho, permitindo que a validação de tamanho escondesse um guard de base removido. Agora desloca início/fim juntos e a mutação de base falha por asserção. O primeiro comando de lint ARM pressupunha uma pasta scripts ausente no pacote isolado; foi corrigido para testar o diretório tests real usando os wheels já verificados, sem instalação. Não foram contados como falhas de hardware ou prova de sensor.

Próxima fase: backend de descriptors retidos com referências válidas entre comandos, readback fresco por callback e integração do caller com retenção de módulo/objetos quando cleanup estiver pendente. Não usar um callback sintético nem o módulo ASIS que já liberou seus pinos. Nenhum USB, SSH, reboot ou DFU foi executado nesta fase.

## Contrato da fase2 — pinos e caller operacional

A fonte preservada já tem `suppress_bind_attrs=true` no GPIO Apple; exigir esse campo no provider e conferir fresh binding sob `device_lock` em cada operação. Não guardar regmap devm ou mutex entre comandos. Manter referências de node/provider/gpio_device e descriptors, lookup próprio e handle pinctrl até cleanup. Não aceitar forced unbind/remove, mutações concorrentes do DT ou force unload como operação suportada.

Qualificar o consumidor root/I2C1 e somente o estado default: `pinctrl-0` contém um phandle para `/soc/pinctrl@20f100000/i2c1-pins`, com exatamente duas células pinmux `00010073,00010072`; `pinctrl-names` só default e sem pinctrl-1. Rejeitar propriedades pins-gpios/gpio antes de usar lookup próprio. GPIO Apple ativo, recurso20f100000/100000,208pinos, label e gpio_device exatos. Baseline fresca cache/hardware/hardware/cache nos115/114, com máscara270 igual220 e words integrais coerentes. Não presumir00076221 histórico.

Reservar ambos os descriptors ASIS e validar identidade/offset. Obter pinctrl/estado default e selecioná-lo somente após a reserva. O setter Apple substitui260 por220; a baseline já tem esses campos, portanto exigir words integrais iguais após seleção e liberação. Guardar obrigação de readback antes de selecionar, inclusive em falha parcial. A reserva GPIO e o pinctrl usam regras distintas; não alegar exclusão elétrica geral nem que o core impeça todo compartilhamento de estado GPIO. Não alterar direção/valor de saída ou programar pinmux bruto.

Release verifica as words antes de soltar ownership, libera pinctrl e descriptors em ordem inversa, remove lookup e confere words novamente. Erro pré-release retém handles e referências; erro pós-release retém referências/obrigação até retry confirmar baseline. Desfazer referências e lookup integralmente em erro ocorrido antes da obrigação. Todo regmap fica limitado à função sob device_lock. Callback para o controlador exige ambos os descriptors e estado selecionado, provider válido e words atuais iguais à baseline.

### Fases de implementação

1. Quatro executáveis novos: `phone/kernel/n71-i2c-pin-owner.h`, `phone/kernel/n71-i2c-pin-owner-of.h`, `tests/n71_i2c_pin_owner.c`, `tests/test_n71_i2c_pin_owner.py`; separar qualificação OF para manter o owner abaixo de300linhas. Qualificar baseline/falhas/retry/mutações em Mac/ARM64 e contexto kernel antes da integração. Preservar o módulo ASIS/artefato anterior.
2. Três executáveis existentes: `phone/kernel/n71-i2c-power-diagnostic.c`, `tests/n71_i2c_power_diagnostic.c`, `tests/test_n71_i2c_power_diagnostic.py`. Novo `action=configure`: reservar pinos, ativar genpd, adquirir/resetar/restaurar controlador, liberar pinos e só então genpd. Falha de restore conserva pinos, clock/MMIO, domínio e referência de módulo. `cleanup` recomeça pela obrigação mais interna; `cycle`/`inspect` continuam compatíveis. `run=1` somente qualifica no init, sem programar controlador.
3. Documentação/prova sanitizada em fase separada. Reusar gates de headers inalterados e rodar a matriz afetada uma vez. Sem acesso ao telefone nesta preparação. Não pedir novo DFU só para testar o owner; preparar transporte/telemetria junto.

### Aceite verificável

Novos testes executam o header real; APIs GPIO/pinctrl/provider são sintéticas. Mutações só valem por compilação verde e SIGABRT/asserção. Teste do caller executa caller/genpd reais com dependências de pinos/controlador explicitamente sintéticas; headers têm seus próprios gates e build real conjunto deve conferir todos os imports. Falhas de readback/cleanup nunca permitem power release ou module_put prematuros. Config/Image/exports/hash do módulo anterior permanecem preservados. GPIO/SMSTA/FIFO/charger/telemetria física ainda não ficam provados com esses gates.

## Resultado da fase2 — 2026-10-10

Owner emd226603:67 cenários/13 mutações por plataforma, Mac/ARM64; probe kernel15.800bytes/43imports, recusa load. Caller em45a3aa5:66 cenários (52 existentes+14 novos)/19 mutações (14 existentes+5 novas) por plataforma; módulo operacional48.240bytes/79imports, W=1/KCFLAGS-Werror/modpost/ELF64-AArch64/vermagic power2. Checkpatch estrito0/0/0 para os dois headers e caller; AST/lint fatal verdes, sem type checker Python. Quatro e doze inputs, respectivamente, idênticos nas duas máquinas. [Prova sanitizada](../../docs/evidence/n71-i2c-configure-qualified.json).

O init ainda só qualifica com run1; `configure` é explícito. Cleanup respeita controlador→pinos→genpd; uma falha retém módulo e objetos. Status legado preservado, novo configuration_status detalha componentes. Nenhum perfil, Image ou módulo anterior foi substituído. A primeira build encontrou colisão do identificador current com macro kernel; corrigido para registered_gdev e requalificado. EUCLEAN recebeu fallback117 somente na fixture Darwin. Falhas de compilação não foram contadas como kills.

CI be960f1: PR38090497215/push38090494013 terminaram success, seis jobs verdes após o timeout45min. Essa prova cobre o head anterior; a nova publicação terá seus próprios handles. Não foi acessado o telefone. Próxima etapa concreta: transporte I2C limitado SN2400/HDQ e ABI do gauge, aproveitando estes backends para reunir coleta com Wi-Fi num único boot preparado. Não adicionar mais testes opcionais ao owner/configure já qualificados.

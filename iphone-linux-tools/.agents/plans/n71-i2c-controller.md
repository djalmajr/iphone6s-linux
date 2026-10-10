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
- [ ] Publicar somente código/evidência sanitizada e reprodução; preservar fonte/config/Image/exports.
- [ ] Integrar descriptors retidos e caller operacional antes de uso no aparelho.
- [ ] Completar transporte/gauge e prova física agrupada, mantendo issues/goal abertos até aceite real.

## Verificação

Fixture executa o header real; APIs OF/clock/MMIO/pinos são sintéticas e não provam hardware. Mutações contam somente com SIGABRT/asserção, após compilação bem-sucedida. A CI existente descobre `test_*.py`. Gates anteriores permanecem válidos enquanto seus inputs estiverem intactos. Não instalar ferramentas no Mac, reconstruir Image ou trocar perfil para qualificar apenas um módulo/header. Relatar explicitamente a falta de type checker Python se continuar ausente.

## Resultado da fase1 — 2026-10-10

Código609dd39: três executáveis novos. Mac/ARM64 passaram50 cenários e15 mutações compiladas por SIGABRT/asserção. Probe kernel de11.192bytes,26 imports qualificados, ELF64/AArch64 e vermagic power2; ele recusa load com ENODEV e não é um módulo operacional. Checkpatch estrito0erros/0avisos/0checks, AST e lint fatal verdes, sem type checker Python configurado. Fonte primária e config/Image/exports foram preservados. [Reprodução e limites](../../docs/N71_I2C_CONTROLLER.md), [evidência sanitizada](../../docs/evidence/n71-i2c-controller-reset.json).

Desvio de teste corrigido: o cenário de MMIO fora do escopo inicialmente mudava também o tamanho, permitindo que a validação de tamanho escondesse um guard de base removido. Agora desloca início/fim juntos e a mutação de base falha por asserção. O primeiro comando de lint ARM pressupunha uma pasta scripts ausente no pacote isolado; foi corrigido para testar o diretório tests real usando os wheels já verificados, sem instalação. Não foram contados como falhas de hardware ou prova de sensor.

Próxima fase: backend de descriptors retidos com referências válidas entre comandos, readback fresco por callback e integração do caller com retenção de módulo/objetos quando cleanup estiver pendente. Não usar um callback sintético nem o módulo ASIS que já liberou seus pinos. Nenhum USB, SSH, reboot ou DFU foi executado nesta fase.

# Baseline UJM do controlador I2C N71 — issue #48

## Evidência e decisão

O teste físico em 15/10/2026 recusou configure antes de qualquer comando HDQ: stage 3, EBUSY e CTL inicial 0104. A aquisição exige CTL dentro de 00ff. A fonte PASemi fixada define UJM no bit 8, MTR no bit 9 e MRR no bit 10; reset já escreve 070f e a recuperação já admite 07ff. Não confundir UJM com MTR nem interpretar esse estado como bateria válida.

Decisão: admitir na baseline somente divisor baixo e UJM (máscara 01ff), mantendo MTR/MRR, EN e bits desconhecidos recusados. Continuar exigindo revisão 2, duas amostras idênticas, idle/FIFOs sem pendência, XFSTA/IMASK zero, pinos retidos/verificados e clock exato protegido. Os comandos de reset, offsets, timeouts e contagens de writes permanecem iguais. O CTL original, inclusive UJM, continua sendo restaurado e conferido exatamente. Essa política amplia somente a condição já observada, sem aceitar toda a máscara de comandos 07ff.

Alternativas: repetir o teste sem mudança reproduz a recusa; aceitar 07ff admite estados de reset RX/TX não observados; remover UJM do restore muda a baseline e esconde perda de estado. As duas últimas são rejeitadas. Sem acesso ao aparelho nesta fase; nenhuma escrita em carregador ou limite de corrente.

## Fase A — três executáveis

1. phone/kernel/n71-i2c-controller.h: mudar apenas a máscara da baseline de 00ff para 01ff, com comentário curto sobre UJM; nenhum outro fluxo de hardware.
2. tests/n71_i2c_controller.c: fixture restaura CTL inicial variável; provar 0104/01ff, restore exato, corrupção/retry preservando recursos e recusa sem writes de cada bit 9..31. Preservar cenários anteriores e a referência de clock alheia.
3. tests/test_n71_i2c_controller.py: adaptar a mutação que admitiria 07ff e adicionar mutações compiladas que voltam a recusar UJM ou removem UJM do restore; exigir SIGABRT/assert, não erro de compilação.

## Fase B — qualificação

Executar gate do controlador e o gate HDQ dependente em Mac/ARM64, AST/lint dos runners e conferir os inputs antes/depois. Reutilizar caller com controller stub: sua implementação e contrato de request não mudam. Sem typechecker Python configurado. Compilar módulo externo novo, isolado, W=1/KCFLAGS=-Werror, conferir ELF/imports/vermagic e .config/Image/vmlinux.symvers antes/depois. Preservar módulo anterior e fontes congeladas da sessão física.

## Fase C — documentação e próximo teste

Publicar código, evidência sanitizada e reprodução na branch autorizada, sem integrar main ou publicar firmware/chaves/logs. Investigar o fault DART também antes de pedir o próximo DFU; reunir as mudanças preparadas. No teste físico, inspect/configure/read com cleanup/unload, sem prosseguir quando houver erro de setup. Só então decidir pelo dado real e por fonte primária sobre HDQ/gauge/carga.

## Checklist

- [x] Implementação e contratos do controlador.
- [x] Gates Mac/ARM64 e módulo externo qualificados.
- [ ] Documentação/issue e candidata preservadas.
- [ ] Prova física com CTL UJM; gauge/telemetria/carga continuam sem prova.

## Resultado da qualificação

Mac/ARM64: controlador 76 cenários/17 mutações por plataforma; HDQ dependente 42/24. Mac HDQ retomou somente 15 mutações após timeout de uma execução; as 9 já mortas foram mantidas. ARM64 concluiu sem retomada. Nove inputs intactos, AST/lint aprovados, sem typechecker Python. Caller com controller stub reutilizado com contrato/implementação inalterados.

Módulo externo novo: 52456 bytes, SHA256 13c49a3c8b2ab83577188401c6f648f22330258a305ec09209ee6bd43298f99f, 79 imports válidos, ELF AArch64/ABI power2 e W=1/KCFLAGS=-Werror. .config/Image/exports e 11 inputs preservados; módulo anterior intacto. Ainda não executado no aparelho. Documentação em docs/N71_I2C_UJM.md; evidência em docs/evidence/n71-i2c-ujm-qualified.json. Aguardando publicação enquanto o CI do relatório físico termina; nenhuma nova intervenção solicitada ao operador.

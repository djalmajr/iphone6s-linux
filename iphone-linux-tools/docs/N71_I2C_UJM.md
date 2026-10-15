# Baseline I2C com UJM — issue #48

## Estado e motivo

A correção está qualificada no Mac/ARM64 e foi executada no iPhone na ABI PMD. O configure passou da recusa -16 anterior para timeout -110, ainda no stage 3; restaurou CTL 0104, limpou os owners e permitiu unload normal. Não chegou ao transporte HDQ. Consulte a [sessão PMD/UJM](N71_SESSAO_PMD_HDQ.md), o [relatório físico anterior](N71_SESSAO_DMA_HDQ.md), o [plano](../.agents/plans/n71-i2c-ujm-baseline.md) e a [qualificação original](evidence/n71-i2c-ujm-qualified.json).

Na fonte PASemi fixada, bit 8 é CTL_UJM; bits 9/10 são MTR/MRR e bit 11 é EN. O código anterior recusava qualquer bit fora do divisor baixo, incluindo a baseline UJM observada. O novo gate admite divisor e UJM (01ff) somente depois das mesmas verificações de ownership, clock, revisão, estabilidade, idle e IMASK/XFSTA zero. MTR, MRR, EN e demais bits continuam recusados antes de writes.

Não mudam offsets, comandos de reset, polling ou contagens de I/O. A recuperação restaura o CTL original integral, inclusive UJM, com readback duplo; não retira o bit para fingir igualdade de baseline. Falha mantém MMIO, clock e obrigação de restore até retry verificado. Não há escrita em carregador ou limite de corrente. Efeitos físicos do reset/restauração com essa baseline continuam pendentes de teste.

## Qualificação

| Gate | Mac | ARM64 |
| --- | --- | --- |
| Controlador real com APIs/hardware em fixtures | 76 cenários / 17 mutações por asserção | 76 / 17 |
| Transporte HDQ dependente | 42 cenários / 24 mutações por asserção | 42 / 24 |
| AST/lint dos runners | aprovado | aprovado |
| Inputs selados e intactos | 9 | 9 |

O gate novo cobre 0104 e 01ff, restore exato, corrupção/retry e recusa sem writes de cada bit 9..31. Duas mutações novas voltam à recusa de UJM ou retiram UJM do restore. As 15 mutações anteriores permanecem compiladas e mortas por SIGABRT/assert. Compilação falha não conta como kill.

No Mac, uma mutação do gate dependente excedeu 5s; o log original foi preservado. As 9 mutações já mortas foram reaproveitadas e somente as 15 pendentes foram retomadas, todas por asserção. ARM64 concluiu os dois gates sem retomada. Não há typechecker Python configurado. O caller com controller stub conserva sua qualificação anterior porque sua implementação e o contrato não mudaram.

O módulo externo tem 52456 bytes, SHA256 13c49a3c8b2ab83577188401c6f648f22330258a305ec09209ee6bd43298f99f, 79 imports válidos e ABI 7.2.0-iphone6s-dart-serdev-power2. ELF AArch64 relocável, W=1/KCFLAGS=-Werror e modpost aprovados. .config, Image, vmlinux.symvers e 11 inputs mantiveram seus hashes. O módulo físico anterior permaneceu intacto. Não houve rebuild ou instalação do kernel nem pacote/configuração global do Mac.

## Reprodução

```bash
python3 -B -m unittest discover -s tests -p test_n71_i2c_controller.py -v
python3 -B -m unittest discover -s tests -p test_n71_i2c_hdq_read.py -v
```

Na VM dedicada, usar o [procedimento de módulo externo](N71_I2C_STAGE.md#qualificação-e-reprodução) com os fontes atuais, uma nova pasta de módulo e o kernel preservado. Arquivos e logs privados desta qualificação: runtime/n71-i2c-ujm-20261015 e runtime/n71-i2c-ujm-module-20261015, com diretórios equivalentes em /home/ubuntu na VM. Cada archive é validado por tamanho/hash e extraído somente em diretório novo com membros regulares relativos.

Antes de outro DFU, preparar também o diagnóstico DART para reunir os testes. No aparelho: inspect → configure → read-hdq-control, parando no primeiro erro de setup e exigindo cleanup/unload. A baseline aceita no modelo não comprova leitura HDQ física, gauge, telemetria, carregamento Linux ou Wi-Fi.

O módulo PMD recompilado tem o hash 6c0e5fcdd8b59fccc6a9498728ad3344ac9312a418b215d37a7f8b24eee2c89f e 52456 bytes. A próxima instrumentação deve conservar os valores já lidos depois do comando de reset, sem acrescentar I/O ou ampliar por suposição os estados aceitos. O valor final de CTL nesse polling ainda não foi observado. A prova física desta tentativa está em [n71-grouped-pmd-hdq-20261015.json](evidence/n71-grouped-pmd-hdq-20261015.json).

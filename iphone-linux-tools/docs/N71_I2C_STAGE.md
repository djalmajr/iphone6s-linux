# Etapas do diagnóstico I2C/HDQ — issue #48

## Estado

O diagnóstico de configuração e transporte passou nos gates nativos do Mac/ARM64 e no build do módulo externo para Linux 7.2. **O módulo foi executado no iPhone em 15/10/2026:** configure recusou na aquisição do controlador, stage 3, CTL inicial 0104 rejeitado pela guarda de baseline. Cleanup/unload passaram; o transporte HDQ não foi atingido. [Sessão física](N71_SESSAO_DMA_HDQ.md), [qualificação offline](evidence/n71-i2c-stage-qualified.json), [plano D48](../.agents/plans/n71-i2c-stage-diagnostics.md) e [issue #48](https://github.com/djalmajr/iphone6s-linux/issues/48).

## Configuração

N71_I2C_CONFIGURATION_STAGE informa stage, read, error e cleanup_error. Os formatos de status e logs anteriores ficam intactos. read indica o modo solicitado; a etapa é definida antes da chamada correspondente.

| Stage | Interpretação |
| --- | --- |
|1 | aquisição dos pinos |
|2 | aquisição de energia/genpd |
|3 | aquisição/configuração do controlador |
|4 | helper HDQ chamado; não prova tráfego no fio |
|5 | operação primária terminou; cleanup tem resultado independente |

## Transporte

N71_I2C_HDQ_TRACE é emitido somente em read-hdq-control, separado do marcador anterior. Contém stage, sampled, status, cleanup_stage, cleanup_sampled e cleanup_status.

| Stage primário | Interpretação |
| --- | --- |
|1 | argumentos |
|2 | readiness |
|3 | ownership |
|4 | amostra do controlador |
|5 | idle/baseline |
|6 | ACK anterior |
|7 | submissão |
|8 | poll |
|9 | dado |
|10 | recuperação |
|11 | leitura concluída e output publicado |

| Cleanup stage | Interpretação |
| --- | --- |
|1 | argumentos |
|2 | readiness |
|3 | poll |
|4 | amostra |
|5 | flush |
|6 | ACK |
|7 | verificação |
|8 | readiness final |
|9 | cleanup concluído |

Status é a última palavra bruta já obtida por uma leitura concluída no respectivo fluxo. sampled não declara sucesso de transporte, identidade do gauge ou validade de bateria. Uma amostra incompleta não publica palavras parciais. Cada leitura começa com trace novo; uma recusa anterior ao HDQ produz campos zerados. Retry explícito de cleanup renova somente seus campos. O cleanup externo da configuração não sobrescreve o trace da tentativa original.

O trace é opcional e não integra ownership. Não autoriza I/O, liberação ou validade de dados. Não acrescenta MMIO, comandos, espera ou escrita de valor de carga. Contagens de reads/writes/comandos/RX/poll/ACK/reset/delay foram comparadas com e sem trace. A primeira causa e os erros de cleanup permanecem separados.

## Qualificação e reprodução

Executar a partir de iphone-linux-tools:

```bash
python3 -B -m unittest discover -s tests -p test_n71_i2c_hdq_read.py -v
python3 -B -m unittest discover -s tests -p test_n71_i2c_power_diagnostic.py -v
```

Por plataforma, o transporte real compilado com fixtures de hardware passou 42 cenários e 24 mutações por SIGABRT/assert. O caller/backend genpd/configuração reais passaram 82 cenários e 39 mutações por SIGABRT/assert. Os gates protegem dados novos, separação primary/cleanup, integração dos seis campos, ausência de marcador em configure, primeira causa, ownership, comandos fixos e validade de output. Nenhuma falha de compilação conta como mutação morta.

Uma execução de mutação excedeu 5s no Mac e outra no ARM64. Os gates foram retomados somente nas mutações sem resultado: 36+3 no Mac e 13+26 no ARM64, todas por asserção. Os logs originais de timeout foram preservados. AST/lint fatal aprovados; nenhum typechecker Python configurado. Os 8 inputs do transporte e 14 do caller foram conferidos sem alterações.

O módulo AArch64 relocável foi compilado na VM dedicada com W=1, KCFLAGS=-Werror e KBUILD_EXTRA_SYMBOLS apontando para vmlinux.symvers preservado. São 52456 bytes, 79 imports presentes nos exports e vermagic 7.2.0-iphone6s-dart-serdev-power2 SMP preempt mod_unload aarch64. Os hashes de .config, Image e vmlinux.symvers permaneceram iguais antes/depois; os 11 inputs do módulo também. O módulo anterior foi preservado.

Na VM do [build preservado](KERNEL-SOURCE-BUILD.md), usar uma nova pasta privada MODULE_SOURCE contendo n71-i2c-power-diagnostic.c e seus headers locais transitivos. O Makefile dessa pasta contém obj-m += n71-i2c-power-diagnostic.o. KERNEL_SOURCE e KERNEL_BUILD apontam para os diretórios já qualificados; conferir os três hashes publicados na evidência antes e depois. Não executar modules_install.

```bash
make -C "$KERNEL_SOURCE" O="$KERNEL_BUILD" ARCH=arm64 -j2 \
  W=1 KCFLAGS=-Werror M="$MODULE_SOURCE" \
  KBUILD_EXTRA_SYMBOLS="$KERNEL_BUILD/vmlinux.symvers" modules
readelf -h "$MODULE_SOURCE/n71-i2c-power-diagnostic.ko"
readelf -p .modinfo "$MODULE_SOURCE/n71-i2c-power-diagnostic.ko"
nm -u "$MODULE_SOURCE/n71-i2c-power-diagnostic.ko"
```

Conferir cada import de nm nos exports do vmlinux.symvers fixado. O SHA256 do módulo desta qualificação está na evidência; mudanças de fontes ou ambiente exigem novo build e receipt.

Logs/archives/fingerprints e scripts privados ficam em runtime/n71-hdq-trace-20261015, runtime/n71-hdq-trace-caller-20261015 e runtime/n71-hdq-trace-module-20261015. Os diretórios equivalentes em /home/ubuntu na VM guardam a reprodução e os logs ARM64/build. Não houve instalação de pacotes nem configuração global do Mac.

## Sessão agrupada executada

O roteiro privado reúne baseline SSH/HTTP/restore, inspect → configure → read-hdq-control, status/readback/cleanup/unload, a candidata Wi-Fi com janela DMA, inventário e stop. Parar no primeiro erro HDQ, sem forçar unload quando houver ownership retido. Preservar snapshot/sync e retornar ao iOS para recarga; limite 600s de teste Linux.

A candidata DMA passou no CLI --check e no boot físico. A sessão localizou a guarda I2C e preservou cleanup, mas não obteve leitura HDQ nem WLAN utilizável. O bit 8 de CTL é UJM na fonte primária fixada; seu tratamento seguro permanece pendente. Os resultados físicos e limites estão no relatório da sessão. O objetivo de telemetria, carga e Wi-Fi funcionais permanece incompleto.

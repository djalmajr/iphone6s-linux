# Etapas do diagnóstico I2C/HDQ — issue48

## Estado

A primeira fase do diagnóstico está qualificada em código nativo no Mac e ARM64. **O módulo novo ainda não foi compilado para o kernel nem testado no iPhone.** A recusa EBUSY física permanece sem causa determinada. [Evidência sanitizada](evidence/n71-i2c-stage-qualified.json), [plano D48](../.agents/plans/n71-i2c-stage-diagnostics.md) e [issue48](https://github.com/djalmajr/iphone6s-linux/issues/48).

## Marcador separado

N71_I2C_CONFIGURATION_STAGE informa stage, read, error e cleanup_error. Os formatos de status e logs anteriores ficam intactos. read indica o modo solicitado; a etapa é definida antes da chamada correspondente.

| Stage | Interpretação |
| --- | --- |
|1 | aquisição dos pinos |
|2 | aquisição de energia/genpd |
|3 | aquisição/configuração do controlador |
|4 | helper HDQ chamado; não prova tráfego no fio |
|5 | operação primária terminou; cleanup tem resultado independente |

A etapa não autoriza I/O, liberação ou validade de dados. Não há novo MMIO, comando de barramento, alteração de timeout ou escrita de valor de carga. A primeira causa e o cleanup permanecem separados. Um retorno de cleanup negativo com stage5 continua sendo falha do comando. Não imprimir last_status nesta fase evita atribuir status antigo a uma tentativa nova.

## Qualificação e reprodução

```bash
python3 -B -m unittest discover -s tests -p test_n71_i2c_power_diagnostic.py -v
```

Cada plataforma compilou o caller, backend genpd e helper de configuração reais com Werror, usando APIs/hardware modelados.81 cenários nativos e29 mutações por SIGABRT/assert passaram; seis mutações novas retiram cada atribuição de etapa ou ocultam o marcador. Os cenários incluem EBUSY em pins/power/controller/HDQ, sucesso e erro de cleanup preservado. As23 mutações de ownership/primeira causa/validade anteriores permanecem ativas. AST/lint fatal do Python aprovados; nenhum typechecker Python configurado.

661 inputs públicos foram conferidos antes/depois. Logs, archive/fingerprints e ambiente da qualificação estão privados em runtime/n71-i2c-stage-20261015 e /home/ubuntu/n71-i2c-stage-20261015 na VM dedicada. Não houve instalação de pacotes ou configuração global do Mac.

## Próximo passo

Concluir subetapa/status do transporte, preservando a causa e usando somente valores já lidos; compilar o módulo externo com config/Image/exports intactos. Preparar uma sessão com inspect, configure e read-hdq-control, cleanup/unload e o teste Wi-Fi da janela DMA. Não solicitar DFU até essa preparação terminar. A fase atual não comprova gauge, bateria, carga Linux ou Wi-Fi.

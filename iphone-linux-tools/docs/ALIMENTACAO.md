# Alimentação e bateria do iPhone 6s

Etapa [#2](https://github.com/djalmajr/iphone6s-linux/issues/2), iniciada em 2026-09-29. **Ainda não há comprovação de carga sustentada ou autorização técnica para uso contínuo sem supervisão.**

## Evidência atual

Linux 7.0.12 responde por SSH, com mais de uma hora de uptime. `/sys/class/power_supply` está vazio e não há zonas térmicas utilizáveis. `/proc/config.gz` não está disponível. O barramento I2C expõe `0-0074`; o log mostra PMIC/RTC, mas isso não estabelece suporte de carregamento. O PMU `apple_twister_pmu` citado no log é de contadores de desempenho, não leitura de bateria.

Não foram escritos registradores, ativados drivers experimentais, desconectado o cabo ou instalado pacote nesta investigação. Não assumir compatibilidade com implementações de carga A10 de outro fork.

## Checagem reproduzível

Execute pela mesma identidade SSH já usada pelo projeto, a partir da raiz do repositório:

```bash
ssh -F /dev/null -i iphone-linux-tools/keys/iphone_ed25519 \
  -o UserKnownHostsFile=iphone-linux-tools/keys/known_hosts \
  -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
  -o BatchMode=yes -o ConnectTimeout=5 root@172.16.42.1 \
  'sh -s' < iphone-linux-tools/power-check.sh
```

O script só lê sysfs; não instala nada no telefone. `unavailable` significa que não há leitura, nunca bateria vazia ou temperatura zero. Mesmo com sensor, `charging_validation=unverified` permanece: uma amostra isolada não valida o sistema de carga. Valores numéricos são os valores brutos do driver (tipicamente temperatura de zona em milésimos de °C; outros campos dependem da ABI/driver). Não tratar corrente USB externa como corrente líquida da bateria.

## Procedimento físico e critérios de conclusão

1. Observar temperatura da carcaça, elevação da tela, cheiro e desligamentos; registrar hora e estado. A observação anterior à atualização não substitui uma observação no Linux atual.
2. Manter os testes iniciais supervisionados, com ventilação, sem cobrir o aparelho e sem carga artificial de CPU enquanto alimentação estiver desconhecida. A Apple especifica ambiente de uso de 0–35 °C; essa faixa é do ambiente, não uma temperatura máxima genérica da bateria.
3. Interromper o uso/carregamento em caso de tela levantada/inchaço, cheiro, aquecimento anormal ou desligamentos repetidos. Solicitar avaliação física da bateria/conexões; não tentar compensar defeito por software.
4. Com o operador presente e snapshots salvos, registrar nível da bateria em iOS antes de um boot Linux e depois de intervalo supervisionado equivalente. Se não for possível ler o nível com confiança, usar diagnóstico físico qualificado. Uma queda apesar de USB alimentado é falha do requisito de carga sustentada; nível estável no limite de 100% é evidência inconclusiva de corrente líquida.
5. Confirmar repetibilidade e definir limites de uso. Um medidor USB pode demonstrar entrada de energia, mas isoladamente não comprova saúde da bateria, controle térmico ou carga líquida.

Pendente: observação física atual, comparação de carga e decisão de manutenção/substituição se necessária. Não encerrar #2 por uptime, por ausência de sintomas relatados ou por uma leitura pontual. O teste prolongado #8 depende deste gate.

## Fontes

- [Apple: temperaturas e proteções em iOS](https://support.apple.com/en-ca/118431). A descrição das proteções do iOS não comprova que existam no kernel Linux experimental.
- [Kernel HoolockLinux](https://github.com/HoolockLinux/linux): qualquer port de driver deve ser validado especificamente para N71/A9.

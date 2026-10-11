# Fonte qualificada do runtime N71 — #43

## Uso

O caller Wi-Fi foi compilado e qualificado com 69 inputs. A evolução do diagnóstico I2C mudou um deles; usar o working tree atual com o binário antigo deve ser recusado. O snapshot preserva os bytes originais sem alterar o manifesto histórico ou copiar credenciais. Todos os selectors e handlers executam do checkout atual; Python arquivado permanece somente como dado.

Na pasta `iphone-linux-tools`, escolha um output novo diretamente sob `runtime`:

```bash
python3 -B scripts/host/n71-runtime-qualified-source.py \
  --commit be960f14268da56aa928873375200cb10a4e2e88 \
  --output-dir runtime/minha-fonte-qualificada

export IPHONE_LINUX_RUNTIME_SOURCE_RECEIPT="$PWD/runtime/minha-fonte-qualificada/receipt.json"
python3 -B scripts/host/n71-runtime-session.py \
  --profile "$TASK_PRIVATE_PROFILE" --action acquire \
  --firmware-dir "$TASK_PRIVATE_FIRMWARE" --check
```

`TASK_PRIVATE_PROFILE` aponta para `deployment.json` de um perfil já validado diretamente sob `runtime`; `TASK_PRIVATE_FIRMWARE` aponta para o pacote fixado. Não envie chaves, calibração, firmware ou snapshots ao GitHub. A referência deve acompanhar cada comando runtime; `unset IPHONE_LINUX_RUNTIME_SOURCE_RECEIPT` retorna à validação dos inputs do checkout atual. Sem referência, o input I2C diferente continua sendo recusado.

O helper usa Git local, commit completo explícito e `git archive`; não faz checkout, reset, fetch ou download. Recusa links, traversal, entries fora do projeto, outputs existentes e excesso de arquivos/bytes. Saída privada 700/600, receipt somente após validar o manifesto e os 69 inputs. Falha deixa a pasta parcial para análise, sem receipt aceito; use outro nome na próxima tentativa.

O resolver exige receipt privado canônico diretamente sob `runtime`, fonte chamada `source`, esquema exato e manifesto byte a byte igual ao registro corrente. A cada seleção, os guards originais conferem caminho, tamanho e SHA dos 69 inputs. Uma fonte inválida nunca autoriza fallback para o working tree. Artefatos, ABI e identidade continuam sendo verificados pelas APIs existentes.

## Provas e limites

Código: helper `7ba3ddf`, referência/integração `2406e1f`. [Registro sanitizado](evidence/n71-runtime-source-qualified.json) e [plano](../.agents/plans/n71-runtime-source-snapshot.md).

| Verificação | Mac | Ubuntu ARM64 |
|---|---:|---:|
| Dez módulos Python afetados | 66 testes | 66 testes |
| Mutações únicas com AssertionError | 70 | 70 |
| Duração da matriz | 291,258 s | 269,870 s |
| AST e lint fatal | passou | passou |

Não há typechecker Python configurado. O Git/filesystem, resolução e seleção são reais; os testes de contrato usam fixtures sintéticas explicitamente separadas da prova histórica de produção. Não alterar os hashes históricos para acomodar uma fixture.

No Mac, o gerador corrente criou uma fonte real do commit fixado e verificou os 69 inputs. O CLI real `--check` aceitou o perfil de calibração, dois diagnósticos, cinco módulos WCC e pacote firmware/regdb. Inputs alterado e ausente em cópias descartáveis foram recusados com exit1; os 14 arquivos do perfil original permaneceram idênticos. Nenhuma chave foi copiada para o snapshot.

Logs privados: `runtime/n71-runtime-source-reference-proof-20261010/`, com a matriz ARM no diretório equivalente da VM dedicada. Os gates I2C/builds não afetados foram reutilizados. Nenhum pacote ou configuração global do Mac, SSH, USB, DFU, rádio ou bateria foi alterado por esta entrega. Isso conclui a preparação de fonte da #43; associação Wi-Fi, telemetria e carga física continuam pendentes em #9/#2/#42.

## Relatório

- **Arquivos:** helper/CLI/teste de snapshot; resolver/teste de referência; integração no selector de inputs; plano, D42 e evidência.
- **Compatibilidade:** opt-in por variável; seleção padrão e manifesto histórico preservados. Sem fallback.
- **Banco/dependências:** não há banco nem pacote novo instalado.
- **Desempenho:** a opção acrescenta leitura limitada do receipt e manifesto; não há benchmark de rádio ou bateria.
- **Próximo:** uma sessão física agrupada para runtime Wi-Fi, HDQ e alimentação; nenhuma confirmação de rotina de tela, cabo ou temperatura.

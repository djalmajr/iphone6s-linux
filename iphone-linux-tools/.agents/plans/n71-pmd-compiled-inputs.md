# Fontes compilados PMD preservados — #46/#48

## Contexto

Os módulos PMD atuais foram compilados de 62 inputs; a reutilização do caller conserva outros inputs nativos, totalizando 78 arquivos distintos. Novos diagnósticos modificarão C/headers existentes. Seus bytes antigos já foram preservados e conferidos, mas não devem ser selecionados implicitamente nem usados para executar Python arquivado.

## Decisão

- **Decisão:** permitir apenas uma referência explícita por IPHONE_LINUX_PMD_SOURCE_RECEIPT, vinculada ao commit conhecido, manifesto exato dos 78 arquivos e manifesto compilado fixado. Resolver essa fonte uma vez por snapshot PMD. Kernel/build/provas continuam sendo lidos do projeto atual; somente os inputs C/testes compilados usam a raiz preservada. Sem variável, manter a checagem atual da árvore em trabalho.
- **Por quê:** permite evoluir os diagnósticos preservando a reprodução e seleção dos módulos antigos, com os mesmos hashes/ABI/provas. Não confundir código novo com o que produziu um binário existente.
- **Alternativas:** atualizar pins sem recompilar perde a prova de origem; forçar vermagic não é aceito; manter todos os fontes antigos na árvore ativa impede evolução. A cópia privada mínima evita duplicar o projeto inteiro.
- **Reverter:** baixo, retirar a seleção explícita; sem modificar arquivos do perfil, source/build da VM ou módulos.
- **Status:** aplicada; 7 testes/9 mutações novos e 8 testes/10 mutações anteriores passaram no Mac. O receipt real e a CLI --check com perfil/módulos/firmware reais passaram; 95 arquivos protegidos permaneceram idênticos. Caller, kernel e perfis não foram alterados.

## Arquivos e tarefas

1. scripts/host/n71_pmd_source_reference.py: leitura privada de receipt, schema/tipos/pins fixos, caminhos canônicos sob runtime, owners/modos/links e hashes de todos os 78 arquivos. Só retornar uma raiz de dados; nenhum efeito/import/exec.
2. scripts/host/n71_pmd_runtime_build.py: resolver raiz dos inputs no snapshot e passá-la aos dois loops de validação, preservando registros públicos e guardas anteriores.
3. tests/test_n71_pmd_source_reference.py: arquivos reais, fluxo PMD real, default recusando fontes atuais alterados, referência preservada aceitando somente bytes compilados, ambiente/permissões/links/corrupção e mutações por AssertionError.
4. Este plano; evidência sanitizada após gates. Até cinco arquivos na fase.

## Verificação

Gate novo e regressão focalizada PMD no Mac, AST/lint; verificação separada do receipt e CLI --check reais, sem SSH/USB. Reutilizar gates C inalterados; sem typechecker Python configurado. Não modificar os inputs antigos nesta fase. ARM64 e novo módulo continuam pendentes. Não iniciar VM/worker nem solicitar DFU.

## Reprodução e limites

O commit fixado é 28b2c922a6a0ca847489b3253cfbe52b1c3e16e9. Os 78 nomes são a união dos inputs de n71-pmd-diagnostic-inputs.json e n71-brcmfmac-caller-qualified.json; o manifesto compilado prevalece para o C I2C atualizado. Extrair somente esses arquivos desse commit, como dados, usando o procedimento Git/archive já validado em n71_runtime_source_snapshot.py. Validar tamanho/SHA de todos antes de copiar para runtime/<nome>/source, com diretórios 0700 e arquivos 0600. A cópia tem 633894 bytes; o SHA canônico do mapa completo é 8dcc0e2684c3e14ba3d0cfbdd91a755815c1d2224d1a5d63351a0575e7e28158. Não importar nem executar os arquivos extraídos.

receipt-private.json precisa seguir exatamente FIELDS de n71_pmd_source_reference.py: format=1, status=preserved_compiled_inputs, source_commit fixado, source=source, inputs com os 78 registros, compiled_input_count=62, native_input_count=69, files=78, bytes=633894, compiled_manifest_sha256=4e9221335b6f944f99a33fb3172307f612767ff21312b3616abc657b2c991e0f, no_code_executed_from_copy=true e no_phone_access=true. O receipt também fica em modo 0600. A seleção sempre revalida owner, modos, links, manifesto e bytes; não confia apenas nos booleans do receipt.

```sh
IPHONE_LINUX_PMD_SOURCE_RECEIPT="$PWD/runtime/n71-pmd-frozen-inputs-20261015/receipt-private.json" \
  python3 -B scripts/host/n71-runtime-session.py \
  --profile runtime/n71-pmd-runtime-profile-20261015/deployment.json \
  --action acquire --firmware-dir runtime/n71-trusted-firmware-20261010 --check
```

Sem essa variável, o padrão continua exigindo bytes atuais iguais aos compilados. Uma referência inválida não cai silenciosamente no padrão. Kernel, módulos e provas continuam qualificados pelos registros públicos atuais. O receipt privado real foi verificado; nenhum novo módulo, efeito no aparelho ou recurso funcional foi comprovado por esta fase.

# Descoberta PCIe N71 após readback do latch

## Decisão e alcance

O último teste confirmou controle GPIO10 `80→81→80` por máscara1, com
readback e restore. O banco187/bit2 ficou0 e o gate então bloqueou PCIe.
Esses fatos permanecem em [evidência física](evidence/n71-reg-on-latch80-physical.json).

A revisão do getter Apple mostrou um pedido de mode1 antes da leitura;
nosso diagnóstico apenas leu o banco, com controle80/81 classificado como
mode2. Sem a tabela opcional, chamar o setter não garante mudança de modo.
O banco ainda não foi qualificado como monitor da saída dirigida ou do
rail. Portanto, não usar seu zero como prova de falta de alimentação,
nem trocar bits de modo para obter um número esperado.

O próximo experimento faz **uma tentativa delimitada de descoberta de
endpoint**, após readback fresco do latch. A hipótese a testar é se o
endpoint responde quando o controle qualificado está81. Não presume
rail ativo e não habilita DMA, driver de rádio, firmware ou tráfego Wi-Fi.
A prova decisiva será link válido, identidade e COMMAND com bus-master
limpo, pelo caminho já implementado; timeout continua sendo resultado
negativo, sem identificar sozinho a causa.

## Pré-condições antes de um único boot

1. Kernel, módulos, fonte, configuração, hashes e ABI selecionada conferidos.
   Para o bundle, exigir gates reais de [composição](N71_KERNEL_BUNDLE.md);
   não reutilizar módulo da ABI anterior.
2. Perfil separado, snapshot restaurável, init USB preservado e saída SSH
   com identidade estrita. Manter cabo/porta definidos pelo operador.
3. Recursos/clocks/reset/tunables específicos do N71, sem aliases de A10.
   O prefixo anterior confirmou root1004106b, sem endpoint/DMA; isso não
   comprova o comportamento do kernel novo antes de testá-lo.
4. Módulo REG_ON usa o mesmo parent/regmap simple-mfd-i2c; sem rebind,
   mudança de drive/mode, transmissão HDQ ou programação de carga.

## Sequência da sessão

1. Validar release, SSH/HTTP e restore; confirmar UART5/I2C1 desativados.
   Transferir módulos externos privadamente, conferir hash/ABI no destino.
2. Carregar observador REG_ON com `run=1`, sem argumento de ativação no
   insmod. Esta tentativa exige original80, owner exato e nenhuma pendência
   anterior. Estado diferente encerra a tentativa sem forçar configuração.
3. Fazer uma aquisição pela API já qualificada; exigir active1/pending1,
   original80 e getter `control` com `N71_REG_ON_CONTROL_READBACK value=81`.
   O getter só lê914 sob os locks existentes. Registrar o banco187 também,
   deixando explícito que é uma amostra sem qualificação elétrica.
4. Fazer uma tentativa PCIe com `run=1 enumerate=1`. O diagnóstico valida
   mapas/domínios, mantém PERST, prepara clocks/porta, libera reset e espera
   100ms antes do treinamento. Polling de link é limitado; identidade só
   é lida após predicate88/bit0 alto, e COMMAND não pode ter bus-master.
   Nenhum host PCI é registrado para um driver de rádio nessa operação.
5. Conferir `N71_PCIE_RESET_RESTORED asserted=1 readback=1` e
   `N71_PCIE_POWER_RELEASED powered=0 attached=0`. Falha de cleanup deve
   permanecer explícita; não contar apenas exit0 do insmod como prova,
   pois registro de driver não equivale a sucesso do probe.
6. Remover diagnóstico PCIe; liberar REG_ON pela API existente, exigir
   readback80/active0/pending0 antes de remover seu módulo. Não apagar
   pendência se restore falhar, nem repetir treinamento automaticamente.
7. Conferir SSH/HTTP, salvar snapshot/sync e retornar ao iOS para medição.
   Não calcular carga Linux com um baseline anterior à preparação.

Os nomes de arquivos/getters são interfaces para o coletor; o operador não
precisa ler nem digitar no console do iPhone. Só haverá DFU quando candidata
e gates estiverem prontos, agrupando as coletas que couberem nessa sessão.

## Resultados que não encerram a issue

Readback81 não mede tensão. Link/identidade não demonstram firmware, Wi-Fi,
DART/DMA ou carga sustentada. Amostra0 não será rebatizada como1. Ausência
de endpoint mantém a hipótese de alimentação, CLKREQ/PHY/reset ou outra
sequência aberta; não autoriza copiar configuração elétrica de outra placa.
A primeira execução física do bundle está registrada abaixo; a evidência histórica
da baseline permanece separada.

Os getters/registros novos compilaram Werror/modpost para a ABI baseline
em diretório exclusivo; ELF/AArch64/vermagic foram conferidos e a fonte
funcional permaneceu sem diff. Essa prova não permite carregar os mesmos
binários no bundle: o rebuild correspondente ao Image novo ainda é exigido.

## Coletor reproduzível do bundle

O rebuild e a composição real passaram nos [gates do bundle](N71_KERNEL_BUNDLE.md).
`scripts/host/n71-link-session.py` exige a ABI nova e os hashes dos módulos
registrados; não seleciona o perfil padrão nem inicia DFU. Confira primeiro
somente os arquivos locais:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-bundle-diagnostic-profile-20261003/deployment.json" \
  --check
```

Depois de um boot explicitamente selecionado com snapshot restaurado e SSH/HTTP
confirmados, execute em saída nova:

```sh
python3 scripts/host/n71-link-session.py \
  --profile "$PWD/runtime/n71-bundle-diagnostic-profile-20261003/deployment.json" \
  --output-dir "$PWD/runtime/NOVA-SESSAO-N71"
```

O coletor recusa diagnóstico PCIe prévio nesse boot, módulos já carregados,
UART5/I2C1 ativos, ABI divergente e estado original diferente de80. Depois da
aquisição, exige estado ativo/pendente e controle81 fresco; repete esses testes
no aparelho imediatamente antes do único insmod PCIe. Amostra187 continua
observação, sem gate elétrico. Logs são exclusivos e privados; repetir uma
etapa não envia o comando outra vez. Não há autoload ou retry de treinamento.

Falhas e timeout SSH passam por cleanup: reset/domínios PCIe precisam de
registros positivos antes do unload; restore REG_ON precisa de readback80 e
pendência zero antes de unload. Observação recusada não escreve o controle.
O resultado privado distingue endpoint ausente, falha do experimento e cleanup
não comprovado. Exit0 com link `-110` registra um experimento negativo concluído
com restauração; não significa Wi-Fi habilitado. O script não reinicia o
aparelho: depois do cleanup, conferir serviços e usar `return_ios.py`, que
valida snapshot/sync antes do retorno. Se cleanup não passar, preservar logs
e tratar a falha antes de continuar.

Gates sintéticos, sem dispositivo ou dados privados:

```sh
python3 -m unittest discover -s tests -p test_n71_link_session.py
python3 tests/run_n71_link_session_mutations.py
```

## Primeira execução física do bundle — 2026-10-03

Uma sessão com um DFU manual confirmou a release selecionada, restore, Bash e
HTTP. Controle914 foi80→81→80 com máscara1/readbacks e pendência zero ao final.
O banco187 continuou20/bit2=0. Mesmo assim, o link passou: port88=00000005,
error0 em12 leituras; endpoint43a314e4 (vendor14e4/device43a3), COMMAND com
bus-master limpo. Isso confirma que aquela amostra0 não deve bloquear a
descoberta de endpoint. Não mede tensão nem qualifica o banco como power-good.

Reset/readback, liberação dos quatro domínios e unload foram confirmados. No
mesmo boot, GPIO2 foi observado sem escrita; serviços continuaram respondendo.
Snapshot/sync e retorno por software ao iOS passaram. Bateria iOS100→100 nesse
intervalo não mede corrente ou carga sustentada. [Fatos selecionados e hashes
dos logs privados](evidence/n71-bundle-first-physical.json).

O próximo desenvolvimento é o host PCI: recursos/BARs, IRQ e DART precisam de
contrato e cleanup antes de qualquer bus-master/rádio. A configuração atual
tem BRCMFMAC como módulo, mas BRCMFMAC_PCIE está desativado; identidade do PCI
ainda não seleciona revisão, firmware ou calibração. Agrupar novos gates numa
candidata antes de pedir outro DFU; fazer fonte/builds/testes offline e atualizar
módulos por SSH enquanto uma sessão útil estiver ativa.

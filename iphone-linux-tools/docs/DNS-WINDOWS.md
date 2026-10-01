# Cliente DNS Windows — investigação #20

## Contexto

A #7 comprovou consultas DNS físicas UDP/TCP pelo Mac e Windows com sockets .NET, incluindo restore após outro boot. O nslookup Microsoft não respondeu no proxy 1053 e seu diagnóstico não recebeu as consultas tentadas. A causa permanece desconhecida; a prova de sockets não substitui os controles desta issue. Nenhuma configuração global de DNS deve mudar.

## Plano e arquivos

1. Usar somente o workspace Windows `iphone6s-linux` já autorizado no Herdr, sem agentes novos ou comandos em outros projetos. Confirmar shell disponível, origem/assinatura Microsoft do nslookup, versão e parâmetros efetivos. Examinar o modo interativo com stdin fechado e prazo finito, direcionado somente a um endpoint explícito de fixture; nunca usar o resolvedor padrão implicitamente.
2. Preparar fixture temporária de DNS UDP/TCP em porta não privilegiada, com bind explícito e sem upstream. Comparar nslookup por argumentos/entrada interativa e o cliente .NET no mesmo destino. Registrar perguntas recebidas, porta, transporte e respostas; logs com endereços pessoais permanecem privados. Não desabilitar proteções, mudar firewall/DNS, instalar pacotes ou criar listeners na porta 53.
3. Somente após reproduzir e identificar uma falha concreta, corrigir o helper existente; se o nslookup não fornecer um caminho confiável, avaliar cliente de sockets com parser completo e limites. Não aceitar ID, RCODE, nome/endereço inesperados, truncamento, timeout ou porta errada como sucesso. Registrar a decisão antes da implementação, em fase de até cinco arquivos com testes correspondentes.
4. Validar a correção/cliente no Windows real com controles negativos, limpar somente fixtures próprios e publicar procedimento/evidência sanitizada. A validação final contra o iPhone após boot/restore continua dependente de USB/DFU; teste sintético não encerra esse critério.

Arquivos públicos desta preparação: este plano, fechamento em `PR-REVIEW.md`, `STATUS.md` e inventário de leitura. Fontes/scripts/outputs de investigação temporária ficam em pasta própria ignorada dentro de `runtime/` e no diretório temporário dedicado do Windows. Nenhuma chave/snapshot do telefone é necessária. Alterações do helper/testes exigem fase própria; não modificar o launcher de boot ou o runtime do DNS para ocultar uma falha do cliente.

## D1. Diagnosticar o cliente antes de trocar a implementação

- **Decisão:** comparar parâmetros e transporte do nslookup e sockets em fixture, preservando o helper atual até encontrar uma causa observável.
- **Por quê:** o piloto antigo recebeu consultas de sockets, mas não do nslookup. Trocar o parser sem observar o envio não explica a falha.
- **Alternativas:** implementar outro cliente imediatamente acrescenta um protocolo/parser sem diagnóstico; repetir o piloto do iPhone depende de intervenção física e não isola o cliente.
- **Reverter:** baixo; comandos e fixtures finitos, sem configuração global ou instalação.
- **Onde:** #20, este plano e arquivos privados da investigação.
- **Status:** em curso; perfil Windows e workspace dedicado acessíveis, shell confirmado. Assinatura/versão e parâmetros efetivos conferidos em execução finita; causa da falha antiga ainda não determinada.

## Tarefas e verificação

- [x] Conferir critérios da #20 e localizar somente o workspace/painel dedicado no Windows.
- [x] Conferir assinatura/versão e parâmetros efetivos do nslookup, com prazo finito.
- [x] Comparar transporte/consulta em fixture UDP/TCP, com resultados e limpeza registrados.
- [ ] Identificar a causa subjacente: comparação em loopback Windows antes de atribuir o problema ao caminho LAN ou a uma política por aplicativo.
- [ ] Corrigir helper ou implementar alternativa justificada com parser completo e controles negativos reais.
- [ ] Validar no novo boot/restore do iPhone e remover fixtures próprios.

Sintaxe do PowerShell deve ser conferida pelo parser nativo antes de usar scripts novos. Testes deverão executar o cliente/falhas reais que se quer validar, sem transformar timeout ou erro de infraestrutura em rejeição comprovada. Não há typechecker configurado. Validação de destino, assinatura e limites da resposta permanecem obrigatórios; nenhum ajuste de ExecutionPolicy ou de confiança do host está previsto.

Referências primárias: [modos/opções de nslookup](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup), [porta TCP/UDP](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup-set-port) e [virtual circuit](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup-set-vc). A configuração por `set` afeta a execução do nslookup; não é uma alteração do DNS global do Windows.

## Preflight real — 2026-10-01

No shell dedicado do Windows, `Get-AuthenticodeSignature` retornou `Valid` e certificado Microsoft. Arquivo nativo `System32/nslookup.exe`, versão 10.0.26100.1, SHA-256 `b69b378538a7cc65e6701e4e94ee8643356ced94e3da4949683d0dbbfcc85c93`; processo 64 bits, PowerShell 5.1.26100.9444. A assinatura e o hash foram conferidos novamente antes da execução. Nenhum pacote/servidor novo, agente, arquivo de chave ou configuração do Windows alterados.

O teste recusaria a execução se a porta local 15953 estivesse ocupada. `ProcessStartInfo` usou `UseShellExecute=false`, stdout/stderr/stdin redirecionados e somente este argumento fixo:

```text
-port=15953 -timeout=1 -retry=1 -novc - 127.0.0.1
```

Após iniciar, o controlador enviou `set all` e `exit` por `StandardInput.WriteLine`, fechou stdin e aguardou no máximo 15 segundos. Timeout encerraria somente o processo filho criado; `Dispose` ocorreu no bloco `finally`. O stdout foi lido em memória; somente opções selecionadas e contagens foram reportadas, sem divulgar o domínio/search list do Windows.

Resultado real: processo terminou dentro do prazo, saída 0; `set all` mostrou porta **15953**, timeout **1**, retry **1** e **novc**. Stdout 351 caracteres, stderr vazio. Os parâmetros não foram silenciosamente descartados nesta invocação. Isso não prova resposta DNS, tráfego para a LAN, compatibilidade do proxy 1053 ou causa da falha física antiga: o destino foi explicitamente loopback sem servidor. Próximo gate é comparar nslookup/sockets e perguntas recebidas em fixture UDP/TCP, antes do novo piloto iPhone.

## Comparação real em fixture LAN — 2026-10-01

O gate seguinte foi executado em fixture própria no Mac, com bind IPv4 privado explícito e ACL somente para o Mac e o Windows autorizado. Portas 15953 e 1053 TCP/UDP livres antes de iniciar; nenhum bind wildcard/53, recursão ou upstream. O servidor aceitou mensagens de até 4.096 bytes, aceitou uma pergunta, respondeu apenas ao registro A `iphone-usb.home.arpa → 172.16.42.1` e retornaria NXDOMAIN para nomes desconhecidos. Prazo global 600 s, máximo 120 eventos e leitura TCP de até 2 s. Não é o daemon/proxy do iPhone.

| Cliente real | Execuções | Resultado observado |
|---|---|---|
| Mac dig | UDP 15953 e TCP 1053 | Duas perguntas recebidas; registro esperado retornado |
| Windows nslookup por argumentos | UDP/TCP nas duas portas | Quatro processos terminados dentro de 15 s, saída 0; nenhuma resposta com nome/endereço esperado e nenhuma pergunta recebida |
| Windows sockets .NET | UDP/TCP nas duas portas | Quatro perguntas recebidas; todas as respostas sintéticas de 54 bytes comparadas integralmente com o esperado |
| Windows nslookup interativo | UDP/TCP nas duas portas | Quatro processos terminados dentro de 15 s, saída 0; `set all` confirmou a porta selecionada; nenhuma pergunta recebida |

A assinatura/hash Microsoft foram conferidos novamente antes das invocações nativas. Por argumentos, cada chamada usou `-port=PORTA -timeout=2 -retry=1 -type=A MODO iphone-usb.home.arpa. ENDERECO_DA_FIXTURE`, com MODO `-novc`/`-vc`. No modo interativo: `-port=PORTA -timeout=2 -retry=1 - ENDERECO_DA_FIXTURE`; stdin recebeu `set all`, `set type=A`, `set novc`/`set vc`, o nome absoluto, `exit` e foi fechado. Captura assíncrona de stdout/stderr e `Dispose` ao final. UDP informou timeout; TCP informou erro não especificado. A saída zero do processo não foi aceita como resolução bem-sucedida.

O socket enviou uma pergunta DNS A/IN com ID `0x6a20`, flags `0x0100`, QDCOUNT 1 e demais contagens zero. UDP conectado usou ReceiveTimeout 3 s; TCP teve connect/read/write de 3 s e framing de dois bytes. Resposta esperada: mesmo ID/pergunta, flags `0x8500`, uma resposta A/IN, TTL 30, ponteiro `0xc00c` e endereço de quatro bytes. A comparação integral é válida para esta fixture fixa; não constitui um parser DNS completo ou controles negativos do cliente operacional.

A primeira submissão multilinha pelo terminal causou erro de sintaxe antes do diagnóstico; não foi contada como teste de rede. A repetição usou transporte em uma linha, fonte decodificada em memória, `Parser.ParseInput` sem erros e execução do scriptblock. Não alterou ExecutionPolicy. Fontes, resultados e logs com endereços reais estão preservados na pasta própria ignorada `runtime/windows-dns-fixture-20261001/`; [evidência pública sanitizada](evidence/windows-dns-fixture.json) registra resultados/limites. Flake8 fatal da fixture passou. Nenhum helper operacional alterado, typechecker configurado ou pacote instalado.

A primeira captura não registrava tentativas recusadas pela ACL. A captura foi corrigida para contar também peers recusados/perguntas inválidas, e somente os oito casos nativos e seis controles afetados foram repetidos. A passagem final confirmou seis perguntas de controles, zero recusas ACL/erros e nenhuma consulta nslookup. A tabela/evidência refletem essa passagem final.

Limpeza concluída: stop próprio, processo da fixture terminou com saída 0 e marcador de encerramento; `lsof` não encontrou listeners TCP/UDP nas duas portas. Os 16 processos nslookup das duas passagens terminaram e foram liberados, nenhum arquivo/servidor novo criado no Windows. A pasta privada conserva somente fontes/logs/resultados para reprodução/análise.

## D2. Isolar o caminho local do Windows antes de escolher outro cliente

- **Decisão:** comparar o nslookup com uma fixture finita no loopback do Windows; manter o helper atual enquanto a causa permanecer desconhecida.
- **Por quê:** sockets alcançaram o mesmo endpoint LAN em ambas as portas/transporte e o nslookup não chegou ao servidor. Isso reproduz a diferença entre clientes, mas não identifica a camada que impede o envio.
- **Alternativas:** desabilitar proteções ou mudar DNS/firewall tem impacto no host e não está no plano; trocar imediatamente por sockets exigiria um parser completo e ainda deixaria a causa sem investigação.
- **Reverter:** baixo; apenas fixture própria finita e sem configuração global.
- **Onde:** #20, este documento e evidência sanitizada.
- **Status:** na fila; helper/correção e validação física após boot/restore continuam pendentes. A comparação LAN concluída não encerra #20.

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
- [x] Executar controle em loopback Windows: falha nativa também ocorre sem o caminho LAN/Mac; causa específica continua desconhecida, sem atribuição a uma política por aplicativo.
- [x] Corrigir helper ou implementar alternativa justificada com parser completo e controles negativos reais.
- [x] Validar no novo boot/restore do iPhone e remover fixtures próprios; cinco casos públicos Windows e dois controles Mac passaram, conforme o piloto físico abaixo.

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
- **Status:** comparação aplicada: oito casos nativos falharam também no loopback, quatro controles sockets passaram e listeners/threads próprios foram encerrados. O limite observado permite escolher cliente alternativo; causa específica, controles completos e piloto físico permanecem pendentes.


## Controle loopback Windows — 2026-10-01

O parser nativo aprovou a fonte PowerShell antes de executá-la. `Add-Type` compilou a fixture C# própria com o .NET existente; sem instalar compilador/pacote ou copiar arquivos do projeto no Windows. O compilador pode usar temporários gerenciados pelo .NET; não foi declarada ausência desses arquivos. A assembly fica na memória da sessão PowerShell até seu término; não é serviço, instalação ou alteração persistente de configuração. A origem/assinatura/hash do nslookup foram reconferidos antes dos casos.

Bind exclusivo em `127.0.0.1` para TCP/UDP 15953 e 1053, portas conferidas livres. Quatro threads próprias, máximo 120 s/64 perguntas/4.096 bytes e leitura TCP de 2 s; sem DNS do sistema, upstream ou rede LAN. Fixture aceitou pergunta A/IN e respondeu o mesmo registro fixo. Oito casos nslookup por argumentos/stdin terminaram dentro de 15 s, saída 0, sem resposta esperada; modo interativo confirmou as portas e informou domínio inexistente. Nenhuma pergunta nativa chegou à fixture. Os quatro controles sockets UDP/TCP nas duas portas compararam integralmente as respostas de 54 bytes; os quatro eventos recebidos correspondem a esses controles. [Resultados sanitizados](evidence/windows-dns-fixture.json).

`Dispose` fechou todos os sockets e aguardou término das threads próprias. Conferência final: zero listeners UDP/TCP nas portas, marcador de conclusão e prompt do painel devolvido. Fontes/resultados privados preservados em `runtime/windows-dns-loopback-20261001/`. A prova exclui dependência do caminho Mac↔Windows para reproduzir a falha; não identifica a causa específica no cliente nativo nem comprova envio dele para outro destino. Nenhuma inspeção/alteração global ou captura de tráfego de outros projetos foi feita.

## D3. Implementar cliente de sockets completo para o serviço local

- **Decisão:** substituir a execução nslookup no helper Windows por cliente DNS em fonte C#/.NET, com PowerShell como interface e validação completa e limitada do pacote.
- **Por quê:** o caminho nativo falhou na LAN e no loopback, com portas/opções conferidas; sockets no mesmo endpoint passaram. Essa alternativa atende ao critério explícito da #20 sem mudar o Windows para tentar corrigir uma causa ainda desconhecida.
- **Alternativas:** continuar dependente do nslookup impede a validação reproduzível em 1053; instalar dig ou alterar DNS/firewall/proteções acrescenta mudanças ao host; manter o diagnóstico de 54 bytes como cliente final não cobre o parser/negativos exigidos.
- **Reverter:** baixo; preservar histórico/receita nativa e reverter a alteração do helper na branch. Nenhuma migração ou alteração do daemon/proxy do iPhone.
- **Onde:** fase 1 de cinco arquivos abaixo; publicação/CI em fase seguinte.
- **Status:** fase 1 implementada e validada no Windows real: 61 casos, 18 mutações e nove invocações do helper público. CI Windows aprovada; novo piloto físico concluído conforme a seção final, sem resolver a política/porta53 da #19.

### Contrato e fases do cliente

**Fase 1 — cinco arquivos:** `scripts/host/dns-check-windows.ps1`, nova fonte `scripts/host/dns_windows.cs`, fixture `tests/dns_windows_fixture.cs`, teste/runner nativo `tests/test_dns_windows.ps1` e este plano. Preservar parâmetros ServerAddress/ExpectedAddress/Name/Port e marcadores separados `IPHONE_DNS_UDP_OK`/`IPHONE_DNS_TCP_OK`; portas 1024–65535, padrão 1053. Destino/endereço devem ser IPv4 RFC1918 explícitos e nome A/IN dentro de home.arpa, sem opção de bypass para aceitar loopback/public/wildcard. Fixture loopback testa componentes de transporte/parser internos; o comando público deve recusar loopback antes de abrir socket.

Cliente compilado pela ferramenta .NET já disponível: nenhum executável externo nslookup/dig, pacote ou mudança de ExecutionPolicy/assinatura do host. A antiga assinatura era exigência do executável nslookup usado; removê-lo não justifica executar outro binário desconhecido. Fonte local auditável vem com o helper e deverá ser compilada em sessão de teste nova quando alterada, sem reutilizar uma classe de versão anterior já carregada.

**Protocolo:** ID de 16 bits novo por consulta, UDP conectado somente ao endpoint declarado, TCP com framing big-endian de dois bytes, mensagens de 12–4096 bytes, prazo total de 3 s por consulta e nenhuma tentativa/fallback para resolvedor implícito. Validar ID/QR/opcode/RCODE/TC, uma pergunta com nome/tipo/classe esperados e todas as contagens/seções/limites/RDLENGTH. Decodificar nomes comprimidos com limite de labels/comprimento/saltos e recusa de ciclos/offsets inválidos. Parsear registros de answer/authority/additional até o fim do pacote; não procurar apenas os quatro bytes finais ou uma substring. Interpretar nomes em RDATA dos tipos suportados, limitar extensões EDNS e recusar explicitamente o que não puder ser validado. Sucesso exige resposta A/IN para o nome pedido com o endereço esperado; respostas conflitantes ou ausência do registro falham. Sem recursão, cache, resolução CNAME por novas consultas ou configuração do resolvedor do sistema. Bases primárias: [formato/compressão/transporte DNS](https://www.rfc-editor.org/rfc/rfc1035) e [EDNS](https://www.rfc-editor.org/rfc/rfc6891).

**Verificação:** parser PowerShell nativo e compilação C# são gates reais de sintaxe/tipos. Testes devem usar fonte real, transporte .NET e fixture finita. Positivos com nomes comprimidos/literais, framing fragmentado e seções adicionais válidas. Negativos de ID, flags/status/truncamento, pergunta/owner/endereço/tipo/classe inesperados, contagens/RDLENGTH, nomes/pointers malformados, trailing bytes, falta de resposta, timeout/EOF, tamanho de frame e porta incorreta. Alvos público/loopback/wildcard recusados no CLI. Mutações reais das validações críticas devem ser rejeitadas por asserções desses casos após baseline válido; erro de compilação/infraestrutura ou skip não contam como rejeição. Fechar sockets/threads/filhos próprios e não matar outro processo para liberar uma porta.

**Fase 2 — até cinco arquivos:** `.github/workflows/ci.yml`, `docs/DNS.md`, `docs/STATUS.md`, `docs/PR-REVIEW.md` e `docs/evidence/windows-dns-fixture.json`. Registrar runner Windows para testes/mutações novos, conservar Ubuntu/macOS e evidência não afetada, documentar uso/limites e publicar resultado somente depois de observar o CI correspondente. O rollout local pelo Windows deverá também exercitar o helper público contra fixture LAN privada explícita.

**Fase física:** Windows UDP/TCP contra iPhone após novo boot com DNS restaurado, controles negativos aplicáveis, snapshot/limpeza e retorno conforme runbook. Não fechar #20 com prova sintética ou memória dos dois pilotos anteriores. Kernel/Pongo novos, energia/estabilidade e integração permanecem gates distintos.

### Fechamento da fase 1 — cliente e prova nativa

Os cinco arquivos previstos foram implementados. O helper conserva seus parâmetros e marcadores; agora compila a fonte C# local com `Add-Type`, verifica o hash da fonte carregada para recusar reutilização de assembly antiga e consulta diretamente o endpoint declarado. Não instala ferramentas, modifica ExecutionPolicy ou usa o resolvedor do sistema. Tipos de RR suportados: A, AAAA, NS, CNAME, PTR, SOA, MX, SRV, HINFO, TXT e OPT; outros tipos, respostas com aliases em vez do A solicitado e dados não validados são recusados. Não é resolvedor DNS geral.

PowerShell 5.1 do Windows autorizado executou parser/compilação reais e **61 casos aprovados**. O runner criou processos filhos novos, verificou a assinatura Microsoft do PowerShell e aprovou **18 mutações reais**, todas por asserção no caso correspondente, sem contar erro de compilação como rejeição. A primeira mutação `private-range` usava condição constante que o compilador recusou como código inalcançável; não contou como prova. Após corrigir somente esse descritor, baseline e mutação focados passaram; uma passagem final conservada em log confirmou os 61 casos e todas as 18 rejeições com saída 0. Nenhuma fonte operacional foi alterada para aplicar as mutações.

O comando público foi executado em nove processos novos: dois positivos em fixture LAN privada do Mac, nas portas 1053/15953, ambos com `IPHONE_DNS_UDP_OK` e `IPHONE_DNS_TCP_OK`; sete negativos (destino loopback, público, wildcard, IPv4 não canônico, endereço esperado público, nome fora de home.arpa e porta 53) falharam sem marcador de sucesso e pelo motivo esperado. A fixture recebeu exatamente quatro perguntas válidas, nenhum erro/recusa ACL; foi encerrada com saída 0 e não restou listener nas duas portas. Isso prova o helper contra resposta sintética, não contra o iPhone.

Artefatos privados de reprodução estão em `runtime/windows-dns-client-20261001/`: hashes das quatro fontes transferidas, controlador CLI, resultados e fixture/log LAN. A primeira transferência perdeu uma variável entre blocos e falhou antes de executar testes; a repetição usou diretório temporário exclusivo e conferência SHA-256. Não houve pacote novo, banco, chave ou configuração global alterados. Compilação C# e parser PowerShell são os gates de sintaxe/tipos desta fase; `git diff --check` e guard público devem passar antes da publicação. Próxima fase: CI Windows e documentação/evidência sanitizada; o USB ausente ainda impede o gate físico.


### CI e checkpoint da revisão — 49d8747

CI de PR [36867261810](https://github.com/djalmajr/iphone6s-linux/actions/runs/36867261810) e push [36867254184](https://github.com/djalmajr/iphone6s-linux/actions/runs/36867254184) terminou verde: Windows, Ubuntu e macOS, seis jobs. O CI testa fonte/fixtures; não testa iPhone ou a LAN do operador. JSON, 40 links locais, diff e guard público aprovados antes da publicação. Limpeza conhecida do Windows confirmada: cinco arquivos removidos e diretório ausente. A pasta vazia não identificada da transferência inicial não foi removida por aproximação. #20 tem reprodução, helper e negativos concluídos; piloto físico ainda aberto.


## Plano do gate físico do cliente — #20

Fase de até cinco documentos: este runbook, `evidence/windows-dns-physical.json`, STATUS, EXECUCAO e PR-REVIEW. Usar somente o painel Windows descoberto no workspace iphone6s-linux, sem agentes novos. Transferir duas fontes públicas para pasta temporária exclusiva, conferir hashes e parser PowerShell; preservar identidade do PowerShell Microsoft. Preparar controlador com filhos próprios finitos e positivos/negativos observáveis. Nenhum pacote, chave, DNS global, política ou firewall alterado.

Novo boot curto da cadeia de fonte com snapshot real verificado. Exigir wrapper0/SSH/HTTP e restore exato dos arquivos DNS antes de iniciar daemon. Conferir IP privado Mac atual e sockets altos livres; proxy versionado1053 com allowlist dos clientes Windows/Mac. Cliente público Windows deve confirmar ambos os protocolos, nome/endereço e falhar sem marcador para nome/endereço inesperado e porta errada. Mac dig fornece controle independente. Baseline61/18mutações e CI do cliente inalterado são reutilizados.

Encerrar somente proxy/túnel/daemon próprios, confirmar ausência dos listeners, remover exatamente as duas fontes temporárias Windows e diretório exclusivo. Salvar snapshot e retornar ao iOS com backup/sync/USB verificados. Se houver timeout/erro, manter evidência e não encerrar critérios sem prova. Essa fase não testa porta53/política cliente/Android da #19 nem libera uso contínuo #2/#8.


## Piloto físico concluído — 2026-10-01 (America/Maceio)

Novo boot da cadeia Pongo/kernel de fonte: wrapper0, SSH estrito/HTTP/console e restore real comprovados. Hosts, launcher e executável DNS coincidiram exatamente com o snapshot antes de iniciar o daemon. DNS do telefone5353, proxy LAN versionado1053, processo usuário/allowlist de dois IPs individuais. Mac dig aprovou UDP e TCP. [Registro sanitizado](evidence/windows-dns-physical.json).

Cliente público Windows em cinco processos novos, com assinatura Microsoft do PowerShell conferida: dois positivos, ambos UDP/TCP e saída0; nome inexistente, endereço esperado incorreto e porta incorreta terminaram1, sem marcador de sucesso e pelo motivo esperado. O controlador impôs15s por filho e Dispose; helper limita3s por consulta. Os negativos físicos abortam na fase UDP, portanto não são declarados como negativos TCP independentes. A prova anterior61casos/18mutações de parser/transportes e CI Windows continua válida para fonte inalterada, hash conferido antes de executar.

Preparação teve falha operacional: colagem inicial excessiva ficou presa no prompt; nenhum resultado dela foi aceito. Terminal somente do teste substituído no mesmo workspace, sem agentes ou comandos em outros projetos. Transferência em blocos de2048bytes passou SHA256 das duas fontes e parser nativo do helper/controlador. Pasta inicial conhecida estava ausente na limpeza; pasta final teve exatamente duas fontes removidas e diretório apagado. Nenhuma pasta desconhecida foi removida. Assembly/temporários gerenciados pelo Add-Type/.NET são distintos dessa árvore controlada.

Proxy próprio terminou0 por SIGTERM; listeners UDP/TCP1053 e túnelTCP1054 ausentes por inspeção do kernel. Daemon DNS/sessão Herdr do telefone encerrados. Snapshot/sync/retorno ao iOS pelo CLI0 comprovados com USB/modelo/gadget ausente. Uptime antes do retorno261,57s, iOS92→91%, carga ativa após retorno; não comprova carga sustentada. Herdr principal Mac intacto; nenhum pacote, DNS/firewall/política global ou chave alterados. Logs/IDs/endpoints reais privados em runtime/windows-dns-physical-20261001.

### Reproduzir o piloto

1. Selecione o perfil/Pongo privados comprovados em [PROFILES.md](PROFILES.md), confira snapshot com `backups`/`persist.py verify ID` e faça `boot --restore ID` pelo wrapper/DFU manual. Verifique SSH/HTTP e os hashes dos três arquivos DNS contra o snapshot antes de iniciar serviço.
2. Na pasta `iphone-linux-tools` do Mac, confirme bind/portas livres e inicie somente o DNS próprio e o proxy explícito:

   ```bash
   python3 scripts/host/dns.py start
   python3 scripts/host/dns.py lan --bind IP_PRIVADO_MAC --allow IP_WINDOWS --allow IP_PRIVADO_MAC
   ```

3. No Windows, copie `scripts/host/dns-check-windows.ps1` e `scripts/host/dns_windows.cs` para uma pasta temporária exclusiva, lado a lado. Confira Get-FileHash SHA256 contra o JSON deste checkpoint e parser nativo; use PowerShell novo assinado Microsoft, sem mudar ExecutionPolicy. Nunca cole toda a fonte codificada numa linha enorme do Herdr; divida a transferência e valide os hashes antes de executar.
4. Execute o helper público duas vezes; cada execução deve terminar0 e imprimir ambos os marcadores UDP/TCP. Substitua apenas o IP LAN explícito:

   ```powershell
   $powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
   & $powerShell -NoProfile -NonInteractive -File .\dns-check-windows.ps1 -ServerAddress IP_PRIVADO_MAC -Port 1053
   & $powerShell -NoProfile -NonInteractive -File .\dns-check-windows.ps1 -ServerAddress IP_PRIVADO_MAC -Port 1053 -Name absent-dns20.home.arpa
   & $powerShell -NoProfile -NonInteractive -File .\dns-check-windows.ps1 -ServerAddress IP_PRIVADO_MAC -Port 1053 -ExpectedAddress 172.16.42.99
   & $powerShell -NoProfile -NonInteractive -File .\dns-check-windows.ps1 -ServerAddress IP_PRIVADO_MAC -Port 15953
   & $powerShell -NoProfile -NonInteractive -File .\dns-check-windows.ps1 -ServerAddress IP_PRIVADO_MAC -Port 1053
   ```

   A porta15953 deve estar sem serviço; nome/endereço negativos devem diferir dos registros reais. Os três negativos exigem saída não zero, nenhum marcador e motivo esperado; timeout do controlador ou falha de compilação não contam. Dê prazo finito15s somente aos filhos criados para este teste; confira assinatura do PowerShell antes de iniciá-los. Não altere o resolvedor Windows.
5. No Mac, `dig @IP_PRIVADO_MAC -p 1053 iphone-usb.home.arpa A +norecurse +time=2 +tries=1` e a mesma consulta com `+tcp` devem retornar NOERROR/A172.16.42.1. Encerre apenas o proxy/túnel próprios (Ctrl+C no terminal dedicado), `dns.py stop` e sessão própria Herdr se iniciada; confira listeners ausentes. Remova somente os dois arquivos temporários verificados e a pasta exclusiva vazia do Windows.
6. `python3 scripts/host/return_ios.py --wait 60` exige snapshot/sync/retorno USB. Preserve snapshot/logs privados, publique somente o resultado sanitizado. Se houver falha, siga [REBOOT.md](REBOOT.md).

#20 cumpre o gate do cliente explícito. A causa específica do nslookup continua desconhecida; a alternativa auditável prevista na issue passou no iPhone. Porta53, política de resolvedores Windows/Android, IP estável/rollback e operação contínua permanecem #19/#2/#8. Revisão integral #16 e hardware também permanecem separados.


### Cliente Windows53 — evidência e CI publicados

Extensão b4fe9e4: seleção explícita53 adicionada, default1053 conservado;54–1023 continuam recusadas. Regressão nova contra fonte antiga terminou1 por DNS_TEST_ASSERTION standard-port, com compilação válida. Fonte corrigida passou64 casos/20 mutações reais por asserção e sete invocações públicas novas sem marcador nos negativos. Parser PowerShell/compilação C# nativos passaram; quatro fontes conferidas conjuntamente por SHA256. [Evidência sanitizada](evidence/windows-dns53-client.json).

CI exato b4fe9e4 concluído: [PR36949215659](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949215659) e [push36949211094](https://github.com/djalmajr/iphone6s-linux/actions/runs/36949211094), seis jobs aprovados (Windows/Ubuntu/macOS). Log Windows confirmou baseline64 e o passo de mutações terminou verde. CI valida fonte/fixtures; não executa o telefone nem DNS53 nativo no Mac. Nenhuma suíte local foi repetida para esta fase documental.

Quatro arquivos próprios de testes/logs e diretório tests do Windows removidos; dois arquivos cliente verificados preservados para o próximo piloto. Filhos próprios concluíram e nenhuma fixture permanece ativa. Sudo não interativo Mac exigiu autenticação; nenhum bootstrap privilegiado Mac ou DNS53 funcional executados. Android fica pendente; Mac/Windows são os clientes da rodada atual. Não houve instalação, agente, chave, DNS/firewall/política global ou mudança do telefone. #19 conserva os gates nativos/NRPT/IP estável/rollback; #2/#8 e revisão integral #16 continuam separados.

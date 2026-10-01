# DNS na porta padrão — plano #19

## Escopo e estado

A #7 comprovou DNS local não recursivo no telefone e proxy Mac em 1053. A #20 agora tem cliente Windows de sockets com parser/negativos e CI; o gate desse cliente contra novo boot do aparelho continua aberto. A #19 trata exposição em 53 e uso pelo resolvedor dos clientes. Nenhuma configuração de DNS, firewall, PF, roteador ou serviço existente foi alterada.

Leitura real da tabela do kernel do Mac encontrou sete endpoints TCP e sete UDP em 53, incluindo IPv4 loopback e privado. O `lsof` sem privilégios não os mostrou; sua saída vazia não prova porta livre. Dois endereços IPv6 por protocolo vieram truncados mesmo com `netstat -W`, portanto não foram classificados. Esse inventário não identifica o dono nem autoriza parar serviços. Endereços brutos ficam privados em `runtime/dns-standard-port-20261001/`.

## D1. DNS local dividido, com validação explícita antes de política do cliente

- **Decisão:** conservar o DNS não recursivo do iPhone e preparar um endpoint 53 específico para os clientes autorizados. No Windows, avaliar regras NRPT para os dois FQDNs `iphone-usb.home.arpa` e `iphone-lan.home.arpa`, somente após consultas explícitas ao endpoint e teste de rollback. Não capturar todo `home.arpa` ou o namespace padrão.
- **Por quê:** o servidor atende registros locais e não pode substituir sozinho a resolução pública. A [NRPT](https://learn.microsoft.com/en-us/windows-server/networking/dns/name-resolution-policy-table) permite escopo FQDN e processa normalmente consultas fora das regras; configurações existentes/GPO podem afetar precedência e precisam ser verificadas antes de qualquer mudança. A disponibilidade contínua depende das #2/#8.
- **Alternativas:** encaminhar consultas públicas exige upstream/saída autorizados e expande o serviço; trocar DNS da interface ou roteador pode interromper a internet; uma zona local mais ampla pode interferir com outro serviço residencial. Portas explícitas 1053 conservam o modo de diagnóstico atual, mas não concluem o uso padrão da #19.
- **Reverter:** baixo antes de configurar clientes; na fase acompanhada, remover somente IDs de regras criados pelo projeto e encerrar somente listeners próprios, conservando a política anterior.
- **Onde:** este plano, futura alteração optativa do proxy e acompanhamento na #19.
- **Status:** preparação; sem regra NRPT aplicada, upstream escolhido ou listener 53 lançado.

O [cmdlet NRPT](https://learn.microsoft.com/en-us/powershell/module/dnsclient/add-dnsclientnrptrule?view=windowsserver2025-ps) aceita namespace e servidores explícitos. Isso é alternativa de implementação, não prova de funcionamento no Windows do operador. Browser/app pode usar resolvedor próprio; o teste deve distinguir consulta explícita de resolução do sistema/aplicação.

Android requer teste separado e acompanhado. O modo [Private DNS por hostname](https://developer.android.com/reference/android/app/admin/DevicePolicyManager#setGlobalPrivateDnsModeSpecifiedHost(android.content.ComponentName,java.lang.String)) exige servidor DNS-over-TLS; o DNS UDP/TCP atual não oferece esse protocolo. Não preencher esse ajuste com o IP do Mac ou afirmar que ele configura split DNS. Primeiro gate Android será consulta explícita com ferramenta já disponível; sua disponibilidade/modelo e a estratégia de integração ainda precisam ser observados. Nenhum aplicativo ou certificado será instalado nessa preparação.

## D2. Medir privilégio e conflitos antes de construir o launcher

- **Decisão:** identificar um IPv4 LAN do Mac previamente testado e ainda atribuído ao host; comparar seus binds exatos com a tabela do kernel. Se o IPv4 não estiver ocupado nem coberto por wildcard, testar somente bind UDP/TCP 53 por processo próprio não root, sem listen TCP, tráfego, reuseport ou serviço persistente, e fechar ambos imediatamente.
- **Por quê:** loopback 53 já tem binds; iniciar ali ou assumir necessidade de root não serve ao endpoint LAN. A medição concreta decide se basta launcher não privilegiado ou se será necessário bootstrap mínimo de sockets com entrega de FDs e abandono de privilégios. O runtime Python/SSH completo não deve executar como administrador.
- **Alternativas:** parar/alterar o DNS existente interfere com outro serviço; PF/NAT, aliases de interface e daemon de sistema modificam o host; adotar root para todo o proxy amplia acesso às chaves/configuração sem necessidade comprovada.
- **Reverter:** baixo, sockets de preflight fechados no próprio processo; se houver conflito ou privilégio insuficiente, nenhuma exposição será iniciada.
- **Onde:** evidência sanitizada e artefatos privados desta fase; nenhuma alteração operacional ainda.
- **Status:** IPv4 LAN previamente testado confirmado atribuído ao Mac e sem endpoint IPv4 exato/wildcard na leitura do kernel. UDP e TCP 53 foram recusados ao processo não root com errno 13 (EACCES); sockets fechados e zero endpoints no IPv4 selecionado depois. Nenhuma consulta ou listener TCP iniciado. Bootstrap mínimo precisa ser implementado/testado antes do piloto.

## Fases e verificações

1. **Preparação, até cinco arquivos:** este plano, nova evidência `evidence/dns-standard-port.json`, DNS, STATUS e PR-REVIEW. Registrar inventário/medição, decisões, limites de clientes, endereços estáveis a confirmar, allowlist e comportamento sem telefone. Sem serviço/política implantados.
2. **Implementação, nova fase de até cinco arquivos:** somente depois do preflight, definir alterações exatas do proxy/CLI e seus testes. Porta 1053 conserva default; 53 deve ser opção explícita com bind privado e allowlist individual. Testar conflitos UDP/TCP, recusa de wildcard/cliente alheio, upstream ausente, deadlines e cleanup; executar mutações reais após baseline verde. Não contar teste de bind como consulta DNS.
3. **Piloto acompanhado:** novo boot/DNS restore e consulta UDP/TCP explícita Windows/Android em 53. Política Windows somente após inventariar regras existentes e salvar IDs/estado anterior privadamente; teste de nome local, nome externo por caminho anterior e interrupção do telefone. Não mudar interface/roteador ou regra de outro projeto.
4. **Rollback:** remover somente política/listeners próprios, conferir resolução anterior e ausência dos sockets próprios. Documentar IP estável/renovação DHCP, mudanças da allowlist, sequência de boot e falhas. Não afirmar serviço contínuo antes das #2/#8.

Falha de boot, túnel ou energia deve encerrar o proxy próprio; nomes locais ficam indisponíveis. Com split DNS corretamente limitado, nomes externos seguem a configuração anterior. Isso é requisito para testar, não resultado já observado. Se não houver endereço LAN estável, o launcher deve exigir novo IP explícito e testes da allowlist antes de publicar; nenhuma reserva DHCP foi criada.


## Contrato seguinte após a medição

A medição elimina a alternativa de abrir 53 diretamente como usuário neste Mac. A etapa privilegiada deve ser um helper local auditável que importe apenas biblioteca padrão em intérprete isolado e abra exatamente dois sockets IPv4 (UDP/TCP), porta fixa 53, no bind privado informado. Não ler perfil, chave SSH, configuração DNS ou dados do iPhone enquanto privilegiado. Não executar SSH, instalar serviço, alterar sudoers/PF ou adicionar endereço de rede. O helper abandona grupos/UID/GID privilegiados antes de comunicar-se com o processo usuário; entrega somente os dois descritores por socket Unix privado, fecha suas cópias e termina.

O processo usuário deve conferir identidade do canal, quantidade/tipos/endereços/portas dos FDs e ownership do diretório/socket, recusar socket alheio ou mensagem truncada, impor prazo e fechar os FDs próprios em qualquer falha. Apenas depois da validação e da prontidão do túnel SSH ele inicia o atendimento. Privilege drop, peer/FD validation e ausência de tráfego para fora da allowlist são gates críticos: testes com sockets reais em ambiente isolado e mutações por asserção, além de teste nativo Mac acompanhado antes de afirmar funcionamento em 53.

Essa arquitetura ainda não foi implementada. O plano da fase de código deve fixar os cinco arquivos e comandos após ler os módulos relevantes. A integração optativa deve preservar 1053, não abrir 53 implicitamente ao iniciar Linux e não colocar todo o runtime sob sudo. Se o bootstrap falhar, encerrar os sockets próprios, conservar a política dos clientes e exibir erro; nunca tentar mudar um serviço existente para fazer o bind passar.

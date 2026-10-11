# Sessão física agrupada de 11/10/2026

## Resultado

Um DFU carregou a candidata Linux7.2 com calibração PCI OF. SSH com identidade fixada, HTTP, Herdr e restauração do snapshot passaram. A sessão reuniu HDQ, aquisição/atribuição PCIe, preparação/publicação do driver e execução das ferramentas Wi-Fi. Não foi necessário outro DFU para corrigir o parser ou continuar o runtime.

[Evidência sanitizada](evidence/n71-grouped-physical-20261011.json). Logs, boot UUID, fontes de firmware, calibração, chaves, perfis e snapshots permanecem privados em runtime/backups.

| Etapa | Prova física | Limite |
| --- | --- | --- |
| Energia | USB declara500mA; HDQ recusou com EBUSY; cleanup/unload passaram | Não mede corrente, bateria ou carregamento |
| PCIe | REG_ON, enlace, atribuição e publicação passaram | Não prova comunicação com o rádio |
| Firmware | BCM4350r8 iniciou; primeira consulta expirou | Interface WLAN e associação não passaram |
| DART | Fault stream0/código2, NO PMD FOR IOVA | Causa da tradução ainda será determinada |
| Ferramentas | iw6.7 e wpa_supplicant/wpa_cli2.10 executaram no iPhone | iw dev retornou sem interfaces |
| Cleanup | Stack descarregada; reset/power e REG_ON restaurados; unload normal | Coordenador recusou a classificação das recusas anteriores |
| Persistência | Snapshot e sync verificados | Pacote em /tmp não integra o snapshot dos serviços |
| Retorno | Pedido de reboot encerrou SSH | USB iOS não foi confirmado; fallback físico indicado para recarga |

## Correção durante a sessão

O parser de eventos nativos aceitava a fixture sem o prefixo dev_info real. A correção aceita exclusivamente `n71-pcie-diagnostic 610000000.pcie:` depois do timestamp, conservando unicidade, campos, sufixo e owners. O intent prepare foi reconciliado do histórico no mesmo boot, com shell_exit=null; não houve reaplicação ambígua.

Qualificação Mac/ARM64:31 testes e49 mutações AssertionError por plataforma, AST/lint aprovados. Não há typechecker Python configurado. Provas inalteradas dos builders/kernel foram reutilizadas. Tentativa de transferência parcial e duas invocações inválidas da infraestrutura de lint não contaram como proof; as execuções corrigidas passaram. Issue45 acompanha CI/fechamento.

## Reprodução privada

Usar o perfil de calibração e o [receipt de inputs históricos](N71_RUNTIME_SOURCE.md), com ferramentas/Pongo fixados e snapshot verificado. O runbook privado de sessão registra limite600 segundos, paths reais e sequência. HDQ foi tentado antes de adquirir WLAN, com módulo autenticado e action read-hdq-control; nenhum valor de controle de carga foi escrito.

A sequência runtime foi acquire → assign → start. Após a recusa do parser, start usou a pasta interrompida como source, reconciliou o intent e prosseguiu no mesmo boot. Observe preservou o erro assíncrono; stop descarregou WCC e executou native release. A captura bruta permaneceu intacta quando a classificação do cleanup falhou. Unload final foi normal, precedido de readbacks exatos de owners vazios, PCI/stack ausentes e reset/power restaurados. Esse log separado não substitui a prova do coordenador.

O pacote autenticado de [userspace Wi-Fi](N71_WIFI_USERSPACE.md) foi enviado por SSH stdin para /tmp/n71-wifi-tools, com hash integral conferido antes de extrair. Loader e library-path próprios; versões e iw dev foram executados sem iniciar associação, DHCP ou serviço. Nada foi instalado/configurado globalmente no Mac.

## Próxima sessão

Resolver/qualificar offline a classificação do stop (#47), instrumentar a etapa HDQ EBUSY (#48) e investigar a falha DART (#46). Preparar diagnóstico bounded e reunir os testes antes de solicitar outro DFU. Wi-Fi nativo (#9/#40), telemetria/carga (#2) e reaquisição física (#42) continuam abertos. Não interpretar phase=running do coordenador como disponibilidade WLAN: ele prova publicação nativa; a inicialização assíncrona falhou depois.

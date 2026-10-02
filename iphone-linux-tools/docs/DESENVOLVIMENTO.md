# Desenvolver mantendo o Linux ativo

Direção atual em 2026-10-02: reduzir DFU/reinicializações e priorizar a infraestrutura que facilita várias entregas. [Plano e decisões](../.agents/plans/desenvolvimento-sem-reboots.md).

## Ordem de trabalho

1. **Wi-Fi N71/A9 (#9):** identificar o caminho específico de barramento, energia, DMA e firmware. O inventário físico da candidata já passou; ainda não existe rádio enumerado. Próximo insumo é a topologia Apple original da placa, analisada offline antes de uma candidata nova. [Resultados](WIFI.md).
2. **Sessão de desenvolvimento (#32):** editar/versionar no Mac, verificar localmente/na VM e enviar somente arquivos necessários por SSH. Atualizar/reiniciar apenas o serviço afetado, mantendo Bash/Herdr e conectividade USB. Automatização adicional deve ter validação de destino e hash, backup anterior e recusa quando o Linux não estiver acessível.
3. **Energia/telemetria (#2):** dar suporte a sessões mais longas. A candidata não apresentou power_supply; carregar no iOS não demonstra carga sustentada no Linux. #8 depende desse gate.
4. **Storage/boot (#10/#11):** mapear suporte N71 para reduzir a dependência do Mac, sem presumir compatibilidade A10.
5. **DNS53/política (#19):** retomar na mesma sessão Linux disponível quando as prioridades anteriores permitirem. Helpers/testes já aprovados permanecem válidos enquanto suas fontes/ambiente relevantes não mudarem.

## O que exige um novo boot

| Alteração ou prova | Ação |
|---|---|
| Arquivos de serviço, configuração, scripts Bash, dados, HTTP/DNS/Herdr | Enviar por SSH e reiniciar somente o serviço afetado; não executar boot --restore |
| Investigação de sysfs, logs, interfaces ou drivers já presentes | Ler no boot atual |
| Código do Mac, cliente Windows, testes de transporte | Validar no host/VM; usar o Linux existente para integração |
| Kernel, DTB ou initramfs integrado usados no início | Preparar uma candidata offline e agrupar os gates em um novo boot |
| Prova de restore/autostart/retorno ao iOS | Reiniciar deliberadamente uma vez por conjunto de critérios |
| USB/SSH recuperável sem novo boot | Reconectar/diagnosticar o enlace primeiro |
| Kernel travado ou falha de hardware | Usar recuperação documentada, preservando o último snapshot |

## Roteiro de sessão

1. Conferir as issues a resolver juntas, a candidata e o snapshot de recuperação. Fazer checagens locais e builds na VM antes de envolver o telefone. Pedir autenticação do host antes do DFU; um timeout de senha não obriga a reiniciar o Linux.
2. Se o SSH do Linux atual responde, continuar nele. Caso a mudança exija nova imagem, executar o wrapper com o perfil explícito e restore do snapshot verificado. Ver [perfis](PROFILES.md).
3. Guardar um checkpoint antes de trocar arquivos importantes. Usar os comandos de [persistência](PERSISTENCIA.md); os backups são privados. Bash/SSH já estão presentes; não reinstalá-los a cada mudança.
4. Transferir apenas o conjunto necessário para o destino previsto, conferir SHA256 e testar o comportamento real. Não enviar credenciais nos logs ou para o GitHub. Não sobrescrever a imagem funcional para um teste de userspace.
5. Repetir somente o teste que depende da alteração; agrupar SSH, HTTP, DNS e Herdr no mesmo boot. Não confundir testes de fixtures com funcionamento no telefone.
6. Salvar um novo snapshot ao concluir a fatia. Só executar o [retorno ao iOS](REBOOT.md) quando a sessão tiver terminado, o teste precisar dele ou a condição de energia exigir. Não deixar uma sessão prolongada sem gate de alimentação aprovado.

**Limites:** isso é o procedimento atual, não um novo daemon ou deploy automático implementado. Persistência interna, Wi-Fi e carga sustentada continuam pendentes. O acesso por USB permanece necessário nesta candidata. Apenas os diretórios configurados em [persistência](PERSISTENCIA.md) entram nos snapshots; mudanças fora deles exigem reprodução pela construção ou registro explícito.

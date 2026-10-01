# iphone6s-linux

Experimento de mini servidor Linux em um iPhone 6s com tela defeituosa, usando boot em RAM assistido por um Mac.

**Verificado no aparelho:** a árvore reorganizada completou novo boot com console, Bash, SSH e HTTP integrados; Linux 7.0.12 ARM64, rede USB NCM e Herdr 0.9.1. A restauração após novo boot também foi revalidada pelo novo CLI. **Pendente:** confirmação de carga sustentada, boot autônomo, armazenamento interno, Wi-Fi e operação contínua.

SSH e HTTP também foram comprovados pelo Windows independente na LAN, com forwards optativos pelo Mac e loopback ativado automaticamente no novo init. A issue #6 está concluída para esses serviços TCP; saída genérica para internet permanece desabilitada.

Snapshots automáticos optativos (`once`, `watch` e `status`), retenção protegida e `boot --restore ID` estão implementados; a issue #5 foi concluída com prova física curta, testes locais/VM e 15 mutações negativas.

DNS local UDP/TCP também foi validado pelo Mac/Windows e recuperado em outro boot da candidata (#7). Porta padrão 53/configuração dos clientes e compatibilidade nslookup permanecem #19/#20; o serviço atual não faz recursão externa nem muda o DNS global.

A reprodução avançou: m1n1 reproduzido byte a byte, userspace reconstruído em VM nova e kernel/Pongo compilados de fontes fixadas. A nova cadeia de kernel/Pongo tem seleção explícita e gates de integridade; seu piloto físico e rollback Linux continuam pendentes (#12). Builds externos executados somente nas VMs dedicadas, sem novos pacotes no Mac.

## Documentação

- [Procedimento completo e histórico](iphone-linux-tools/docs/REPRODUCAO.md): diagnóstico, DFU, Multipass, builds, chaves, operação, atualizações e limitações.
- [Pongo de fonte: build, seleção e rollback](iphone-linux-tools/docs/PONGO-SOURCE-BUILD.md).
- [Kernel de fonte e integração](iphone-linux-tools/docs/KERNEL-INTEGRATION.md).
- [DNS local e limites](iphone-linux-tools/docs/DNS.md).
- [Retorno verificável ao iOS](iphone-linux-tools/docs/REBOOT.md).
- [Estado do Wi-Fi nativo](iphone-linux-tools/docs/WIFI.md).
- [Backup e restauração no Mac](iphone-linux-tools/docs/PERSISTENCIA.md).
- [Snapshots automáticos e retenção](iphone-linux-tools/docs/AUTOSNAPSHOTS.md).
- [Acesso pela LAN](iphone-linux-tools/docs/REDE.md): configuração, restrições, teste Windows independente e reversão.
- [Console no display e Bash espelhado](iphone-linux-tools/docs/CONSOLE.md).
- [Comandos de operação](iphone-linux-tools/README.md).
- [Estado e evidências](iphone-linux-tools/docs/STATUS.md).
- [Hashes e proveniência dos artefatos](iphone-linux-tools/docs/artifacts.json).

## Conteúdo

`iphone-linux-tools/` contém os scripts e registros do experimento. Downloads, clones upstream, chaves SSH e imagens ficam somente locais e não são publicados. Uma cópia nova deste repositório exige obter os insumos e gerar suas próprias chaves seguindo o procedimento. Não há distribuição completa pronta para instalar.

O boot confirmado usa cabo USB-A → Lightning, DFU físico, palera1n/checkm8, PongoOS e m1n1. Os scripts ficam em `iphone-linux-tools/scripts/`, os insumos e imagens em `iphone-linux-tools/artifacts/`, e os binários externos em `iphone-linux-tools/bin/`. O iOS permanece no armazenamento; dados Linux não salvos são perdidos ao reiniciar. O retorno por software ainda requer validação (#21); se não voltar ao iOS, o fallback comprovado é Power + Home até a maçã, soltando ambos e conferindo a enumeração USB. O experimento não formatou o armazenamento do telefone nem alterou contas remotas.

## Fontes

[HoolockLinux](https://github.com/HoolockLinux/docs), [PongoOS](https://github.com/checkra1n/PongoOS), [palera1n](https://github.com/palera1n/palera1n), [Herdr](https://github.com/herdrdev/herdr) e postmarketOS. Os componentes upstream mantêm suas próprias licenças.

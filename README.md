# iphone6s-linux

Experimento de mini servidor Linux em um iPhone 6s com tela defeituosa, usando boot em RAM assistido por um Mac.

**Verificado no aparelho antes da reorganização:** novo boot com console, Bash, SSH e HTTP integrados; Linux 7.0.12 ARM64, rede USB NCM e Herdr 0.9.1. O wrapper completo e a restauração após novo boot também passaram fisicamente nessa rodada. **Pendente:** revalidar esses dois fluxos depois da reorganização, além de boot autônomo, armazenamento interno, Wi-Fi e operação contínua.

## Documentação

- [Procedimento completo e histórico](iphone-linux-tools/docs/REPRODUCAO.md): diagnóstico, DFU, Multipass, builds, chaves, operação, atualizações e limitações.
- [Estado do Wi-Fi nativo](iphone-linux-tools/docs/WIFI.md).
- [Backup e restauração no Mac](iphone-linux-tools/docs/PERSISTENCIA.md).
- [Console no display e Bash espelhado](iphone-linux-tools/docs/CONSOLE.md).
- [Comandos de operação](iphone-linux-tools/README.md).
- [Estado e evidências](iphone-linux-tools/docs/STATUS.md).
- [Hashes e proveniência dos artefatos](iphone-linux-tools/docs/artifacts.json).

## Conteúdo

`iphone-linux-tools/` contém os scripts e registros do experimento. Downloads, clones upstream, chaves SSH e imagens ficam somente locais e não são publicados. Uma cópia nova deste repositório exige obter os insumos e gerar suas próprias chaves seguindo o procedimento. Não há distribuição completa pronta para instalar.

O boot confirmado usa cabo USB-A → Lightning, DFU físico, palera1n/checkm8, PongoOS e m1n1. Os scripts ficam em `iphone-linux-tools/scripts/`, os insumos e imagens em `iphone-linux-tools/artifacts/`, e os binários externos em `iphone-linux-tools/bin/`. Reiniciar retorna ao boot Apple e perde dados em RAM. O experimento não formatou o armazenamento do telefone nem alterou contas remotas.

## Fontes

[HoolockLinux](https://github.com/HoolockLinux/docs), [PongoOS](https://github.com/checkra1n/PongoOS), [palera1n](https://github.com/palera1n/palera1n), [Herdr](https://github.com/herdrdev/herdr) e postmarketOS. Os componentes upstream mantêm suas próprias licenças.

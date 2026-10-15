# Variante PCIe do brcmfmac N71

## Contexto

Goal autorizado: Wi-Fi nativo/energia, solo, sem mudar pacotes/configuração global do Mac e com mínimo de DFU. Fonte958481f e build power2 preservados; configuração brcmfmac contém somente SDIO/BCDC, não PCIe/MSGBUF, e brcmfmac.ko está ausente. PCI=y, MMC=y, RFKILL=m, CFG80211=m, BRCMUTIL=m, FW_LOADER=y e MODULE_UNLOAD=y foram lidos no build. O Makefile7.2 fornece MO/KBUILD_EXTMOD_OUTPUT para manter os outputs externos separados. Build base ocupa1,10GB e VM tem10,99GB livres. Firmware candidato privado já tem origem/hash/licença verificados; calibração/radio/energia continuam pendentes (#9/#40/#2).

## Arquivos e fase (até cinco públicos)

- Este plano e n71-funcional-goal-decisoes.md: contrato e decisãoD18.
- Após o build real, documentar a reprodução/evidência sanitizada na pasta docs; não habilitar perfil/CLI/actions nessa etapa. No máximo três arquivos adicionais por fase; separar se necessário.
- Código/artefatos/logs da experiência ficam em runtime/n71-brcmfmac-pcie-build-20261010 no Mac e /home/ubuntu/n71-brcmfmac-pcie-build-20261010 na VM. Nenhum firmware, módulo ou config privado entra no Git.

## Detalhes

Copiar o build preservado para um O separado, preservando datas/links; conferir fonte HEAD/diff e hashes de .config/Image/Image.gz/vmlinux.symvers antes/depois. Na cópia, usar scripts/config oficial para habilitar somente BRCMFMAC_PCIE; olddefconfig deve selecionar PROTO_MSGBUF. Aceitar apenas essas duas diferenças normalizadas; todo o resto permanece igual. Rodar prepare/modules_prepare no O novo, sem build de Image ou instalação.

Compilar módulos com o Kbuild oficial da mesma fonte e outputs MO separados, W=1/KCFLAGS=-Werror/-j2; nunca MODPOST_WARN. Ordem: rfkill, cfg80211, brcmutil e brcmfmac/vendors. Na cópia, Module.symvers recebe o vmlinux.symvers preservado; KBUILD_EXTRA_SYMBOLS agrega somente Module.symvers dos módulos dependentes já compilados. LOCALVERSION vazio explícito evita o sufixo+ conforme scripts/setlocalversion, conservando a versão base. Se um import não for resolvido, identificar sua fonte/dependência antes de continuar; não ignorar warnings de modpost nem exportar símbolo no kernel base. CFG80211 com regdb assinado conserva o contrato base.

Conferir cada ko por ELF64/AArch64, vermagic power2, imports contra a união dos exports e hashes/bytes; brcmfmac deve conter suporte PCIe/MSGBUF e alias do endpoint43a3. Registrar a ordem/dependências reais, inclusive vendors; não confundir module build com load/firmware/radio. A variante muda apenas flags internas do driver, mas isso ainda exige comprovação física antes de declarar compatibilidade com a Image base.

## Tarefas

- [x] Identificar a falta de PCIe/MSGBUF e registrar na issue9.
- [x] Preparar O/MO isolados e comprovar diferença de apenas dois flags.
- [x] Compilar/auditar os módulos e preservar o baseline completo.
- [x] Documentar reprodução, hashes e limitações; integração journal/unload/seleção permanece pendente.
- [ ] Candidata agrupada com firmware/calibração/energia e prova Wi-Fi física; sem DFU para build/inventário.

## Verificação

Build nativo ARM64 real; código oficial fixado e CLI local existentes, sem instalar pacote. JSON/inputs/hashes/ELF/imports e bash syntax da reprodução. Não repetir575/455 C do diagnóstico enquanto seus69 inputs estiverem iguais. Não ativar autoload, driver, PCI publication ou firmware no iPhone. Se o staging mudar outro flag/arquivo base, parar somente essa compilação, conservar a falha e seguir diagnóstico; não apagar/resetar trabalho alheio. Goal permanece ativo e nenhum retorno à tela de bloqueio precisa de confirmação do operador.

## Resultado e reprodução

Oito módulos/1.245.480 bytes qualificados ARM64, vermagic power2, imports verificados e hashes/bytes/ELF auditados no Mac. brcmfmac498.800 bytes/SHAffc713a0,269 imports e alias PCI43a3 verificados. Fonte/config/Image/gzip/exports/status originais intactos; apenas PCIe/MSGBUF ativados na cópia, com boolean hidden ausente normalizado como n. Logs finais W=1/Werror/modpost não contêm warnings/erros. Falhas de caminho/Bash/normalização/versão/tabela de exports preservadas e não contadas como qualificação; só os builds ABI finais foram aceitos. Nenhum pacote, Image, módulo/firmware no telefone ou DFU necessário.

[Reprodução e relatório](../../docs/N71_BRCMFMAC_MODULES.md), [evidência](../../docs/evidence/n71-brcmfmac-pcie-modules-qualified.json). Kconfig do driver muda, portanto a compatibilidade efetiva ainda requer prova física; não declarar rádio pronto pelos módulos compilados. Goal e9/40/2 continuam abertos.

# Integração da candidata de kernel — #12

## Plano

Integrar os artefatos 7.2.0 já compilados ao initramfs da candidata validada, em uma pasta privada nova no Mac. O empacotamento lê arquivos e não executa o kernel, extrai arquivos do initramfs, inicia USB ou instala dependências. A chave cliente permanece no Mac; identidades existentes e payload padrão são preservados.

Arquivos desta fase: `scripts/build/integrate-source-kernel.py`, `tests/test_kernel_integration.py`, `tests/run_kernel_integration_mutations.py`, este documento e `docs/evidence/kernel-integration.json`. Gates CI adicionais, se necessários, ficam em outra fase de até cinco arquivos.

- [x] Validar o perfil fonte com o verificador existente e os hashes/configuração/header do kernel pelo registro público confiável; conferir m1n1 pelo registro de rebuild.
- [x] Migrar somente a linha de carga NCM no init e excluir somente o módulo antigo; conservar bytes/metadados/identidades dos demais registros CPIO. Uma fonte já migrada pode ser reempacotada sem nova alteração.
- [x] Criar arquivos privados em uma pasta nova diretamente sob `runtime/`; recusar destino existente ou fora do escopo. Publicar `deployment.json` somente depois da verificação do perfil temporário.
- [x] Exercitar fluxo real de arquivos/chaves sintéticas, controles negativos e mutações; lint/parsing e empacotamento dos artefatos reais, sem boot físico.
- [ ] Publicar receita/resultado sanitizado e atualizar #12/#17; manter os gates físicos e de alimentação abertos.

## Decisão

Usar parser CPIO em memória e o verificador de identidade já existente, sem extrair ou executar o userspace no Mac. Isto permite conferir a alteração exata sem colocar chaves em uma VM que compilou fonte externa. A candidata reutiliza a identidade do servidor/cliente do perfil fonte; seu perfil e arquivos ficam separados. A alternativa de extrair como root na VM amplia dependências e exposição das identidades. Reversão: deixar de selecionar a candidata; os perfis anteriores permanecem disponíveis.

## Critérios

Hashes e tipos de arquivo válidos antes de escrever; Image ARM64/16 KiB e gzip coerentes, configuração NCM/watchdog incorporados, fonte/kernel conhecidos pelo registro versionado. Nenhuma saída pronta após falha de validação. `KERNEL_INTEGRATION_VERIFIED` exige perfil final verificado, chave cliente/pin correspondentes e initramfs vinculado ao fim do payload. Isto não comprova boot, binding/restart, alimentação ou estabilidade no iPhone.

## Reprodução do empacotamento

Execute na pasta `iphone-linux-tools/`, depois de seguir [KERNEL-SOURCE-BUILD.md](KERNEL-SOURCE-BUILD.md). O perfil fonte precisa existir e passar em `device_profile.py check`. Os caminhos do perfil são relativos à pasta que contém `deployment.json`.

```sh
export IPHONE_LINUX_PROFILE="$PWD/runtime/fresh-build-20260930/deployment.json"
python3 scripts/host/device_profile.py check
python3 scripts/build/integrate-source-kernel.py \
  --kernel-dir runtime/kernel-source-build-20261001/artifacts \
  --output-dir runtime/kernel-integrated-20261001-v2
export IPHONE_LINUX_PROFILE="$PWD/runtime/kernel-integrated-20261001-v2/deployment.json"
python3 scripts/host/device_profile.py check
```

O destino deve ser novo; para repetir, escolha outro nome diretamente sob `runtime/`. A pasta `runtime/` precisa ser própria, privada (`700`) e sem symlink. Os arquivos da candidata usam `600`. A geração terminou com `KERNEL_INTEGRATION_VERIFIED`, sem USB, sudo ou instalação no Mac. Nenhum perfil padrão foi selecionado ou sobrescrito.

## Resultado e verificação

A candidata usa `7.2.0-iphone6s-source`, commit `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, m1n1 preservado e DTB N71 verificados pelo manifesto. [O registro sanitizado](evidence/kernel-integration.json) contém os hashes e limites de evidência. Payload: 29.939.712 bytes; initramfs: 13.061.082 bytes. Chaves, imagens e logs continuam privados e ignorados pelo Git.

A comparação dos arquivos reais mostrou somente `init` alterado e `lib/modules/usb_f_ncm.ko` removido. Todos os demais segmentos CPIO permaneceram idênticos byte a byte; o cabeçalho de `init` permaneceu idêntico fora do campo de tamanho. Identidades cliente/servidor, pin, fonte e payload original foram preservados. A chave privada cliente foi copiada apenas para a pasta privada da candidata no Mac.

A primeira execução recusou `runtime/` com modo `755` antes de criar saída; restringimos somente essa pasta do projeto a `700`. Uma comparação adicional detectou que a primeira candidata reescrevia a capitalização hexadecimal do cabeçalho CPIO, embora os valores numéricos fossem iguais. O empacotador agora copia o cabeçalho existente e substitui apenas o tamanho. A fixture reproduz esse cabeçalho, e a mutação que reintroduz a alteração foi detectada. A primeira candidata permanece privada como diagnóstico; somente a `v2` possui a verificação completa.

- Testes: 7 cenários de integração sintética aprovados, incluindo módulo antigo com modo `600`, hashes, páginas de 16 KiB, NCM incorporado, destino, identidade e preservação dos metadados.
- Mutações: 7/7 detectadas, executadas em projetos temporários, sem aparelho ou chaves reais.
- Suíte local: 86 cenários, 78 aprovados e 8 skips explícitos após repetir somente o gate DNS cujo socket local foi bloqueado pela sandbox. A execução inicial registrou 77 aprovados, 8 skips e esse erro de permissão; a repetição autorizada do módulo DNS passou com 2 aprovados e 1 skip. Os demais resultados foram reutilizados.
- Lint: Flake8 E9/F63/F7/F82 aprovado. Não há type checker configurado.
- Dependências/banco: nenhum pacote novo no Mac; nenhum banco alterado.
- Quebra de compatibilidade: nenhuma troca automática do perfil existente. NCM exige kernel incorporado, por isso o módulo antigo é removido somente na candidata.
- Desempenho: o payload aumentou aproximadamente 6,2 MB; tempo de boot e consumo ainda não medidos.
- CI remoto: testes descobertos pela suíte existente. A fase seguinte acrescenta as 7 mutações de integração à matriz Ubuntu/macOS; resultado remoto ainda pendente.

## Fase CI

Escopo: `.github/workflows/ci.yml`, este documento e `docs/evidence/kernel-integration.json`. Acrescentar o runner de mutações à matriz existente, mantendo as permissões de leitura e os gates anteriores. Conferir guard público, diff e execução real dos jobs Ubuntu/macOS. Nenhuma dependência adicional ou ação no aparelho.

- [x] Registrar o runner das 7 mutações no workflow.
- [ ] Verificar execução remota nas duas plataformas e registrar os resultados.

## Próxima validação física

Não iniciar DFU enquanto o estado físico/USB do aparelho estiver pendente do operador. Selecionar a candidata explicitamente no wrapper, realizar boot curto supervisionado, conferir release/configuração embutida, console, NCM, SSH e HTTP, e verificar binding do watchdog. Testar retorno ao iOS somente após snapshot e registrar resultado físico/USB. Se necessário, reinicialização física Power + Home recupera o iOS pelo procedimento já validado; não presumir que reboot por software funciona.

O empacotamento não valida alimentação sustentada, carregamento no Linux, Wi-Fi, armazenamento interno, boot autônomo ou restart do watchdog. Esses gates continuam abertos nas issues #2/#8/#9/#10/#11/#12/#21. O próximo piloto deve manter o USB-A traseiro e usar o perfil explícito; nenhuma troca de cabo é necessária para estes gates.

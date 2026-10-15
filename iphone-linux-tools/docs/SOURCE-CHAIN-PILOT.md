# Piloto da cadeia compilada — 2026-10-01

## Plano e escopo

Selecionar explicitamente Pongo e perfil Linux, conferir hashes/identidades/snapshot antes do USB e realizar boot supervisionado curto no USB-A traseiro. Verificar console, NCM, SSH estrito, HTTP, restauração e binding do watchdog; encerrar serviços próprios, salvar snapshot e pedir retorno ao iOS. Rollback para a imagem Linux conhecida passou em outro DFU coordenado, registrado ao final. Fontes/builds: [Pongo](PONGO-SOURCE-BUILD.md), [kernel](KERNEL-SOURCE-BUILD.md), [integração](KERNEL-INTEGRATION.md).

## Resultado físico

- Modelo `iPhone8,1`, iOS 15.8.8 e 100% de bateria confirmados antes do boot. Cabo USB-A traseiro mantido.
- O primeiro monitor expirou antes do DFU, sem enviar Linux. O operador depois entrou em DFU; Finder e USB confirmaram esse estado. Tela preta e aviso de restauração do Finder são esperados em DFU; não executar a restauração do Finder para este fluxo.
- O segundo monitor aproveitou o DFU já confirmado. Pongo compilado `2.6.3-bb492b00`, Clang 18.1.3, iniciou no A9 S8000. Payload de 29.939.712 bytes enviado; wrapper terminou com saída 0.
- SSH com chave/pin estritos confirmou `7.2.0-iphone6s-source`, páginas de 16 kB, Bash 5.2.21 e Herdr 0.9.1 por versão. NCM, loopback e HTTP passaram. O operador confirmou console, sem precisar operá-lo. Herdr TUI/reconexão nesta imagem ainda não foram testados; autostart permaneceu desabilitado.
- Restore do snapshot privado passou. Hosts, launcher e executável DNS corresponderam exatamente aos hashes dos três arquivos no snapshot. DNS USB UDP/TCP passou em `172.16.42.1:5353`; a instância própria foi encerrada. Os primeiros testes usaram por engano porta 53: timeout UDP/recusa TCP foram preservados como erro do ensaio, sem atribuir regressão ao kernel. Porta 53 no Mac/LAN continua na #19.
- `2102b0000.watchdog` está vinculado a `apple-watchdog`, modalias N71 `apple,s8000-wdt`/`apple,wdt`; `watchdog0` enumerado. A investigação não abriu `/dev/watchdog` nem escreveu controles do watchdog.
- Novo snapshot íntegro foi salvo antes do pedido de `reboot -f`. O CLI antigo retornou falha por não confirmar a resposta de sync. O aparelho, entretanto, reiniciou ao iOS; modelo USB e ausência do gadget Linux confirmados. O operador afirmou que não apertou botões. Isso comprova retorno por software nesta execução, mas não sucesso do CLI antigo nem do CLI corrigido.
- Leitura posterior em iOS: 93%, carregamento ativo. A comparação com 100% anterior inclui DFU/preparação/reboot e não mede corrente líquida. Não libera operação prolongada (#2/#8).

O diagnóstico inicial usou `getconf`, ausente no userspace, e foi interrompido. A repetição leu `KernelPageSize` em proc e concluiu os demais gates. Power-supply e zonas térmicas continuaram ausentes; nenhuma partição de armazenamento, interface Wi-Fi ou host MMC funcional foi observado. Não escrever na NAND e não declarar Wi-Fi/armazenamento suportados.

## Reprodução

Na pasta `iphone-linux-tools`, com os artefatos privados produzidos pelas receitas e o cabo USB-A traseiro:

```bash
export IPHONE_LINUX_PROFILE="$PWD/runtime/kernel-integrated-20261001-v2/deployment.json"
export IPHONE_LINUX_PONGO="$PWD/runtime/pongo-source-build-20261001/final-output/Pongo.bin"
python3 scripts/host/device_profile.py check
python3 scripts/boot/pongo_select.py
python3 scripts/host/persist.py verify ID_DO_SNAPSHOT
bash scripts/host/iphone-linux.sh boot --restore ID_DO_SNAPSHOT
```

Faça DFU manual somente com monitor pronto. Se o monitor expirar sem enviar Linux e o USB confirmar DFU depois, repetir o mesmo wrapper aproveita esse DFU; não precisa reinicializar nem restaurar pelo Finder. Não selecionar outra cadeia se Pongo/Linux já estiver ativo. Se necessário, confirmar retorno ao iOS antes de nova seleção.

Depois de encerrar escritores e proxies próprios, o procedimento corrigido de [retorno](REBOOT.md) faz snapshot, confirma sync numa chamada SSH separada e então pede reboot; o gate físico desse CLI passou no segundo piloto descrito abaixo. Para rollback Linux, selecionar os artefatos e identidades conhecidos antes do próximo DFU, sem substituir a imagem preservada; esse procedimento passou no terceiro piloto.

## Limites e próximos gates

Cadeia de fonte iniciou e retornou ao iOS uma vez; isso não comprova estabilidade prolongada, carregamento, autoboot, retorno em toda falha ou ausência de malícia na cadeia. Nenhum pacote novo, mudança global de rede/DNS/segurança ou instalação no Mac; somente alias na interface USB do aparelho. Nenhuma escrita em iOS/NAND, merge ou release. Logs, identidades e snapshots permanecem privados.

Próximos gates: lacunas de proveniência do legado (#12), Herdr TUI (#13), DNS padrão no Mac e clientes (#19/#20), alimentação (#2). A revisão integral da PR (#16) continua pendente.

Fase documental seguinte (cinco arquivos): este registro será referenciado por `STATUS.md`, `docs/evidence/source-chain-pilot.json`, `docs/evidence/kernel-integration.json`, `docs/evidence/pongo-source-build.json` e `PR-REVIEW.md`. Registrar o piloto físico sem apagar as verificações históricas dos builds, manter as pendências e publicar somente dados sanitizados. Código e imagens não mudam nessa fase.


## Segundo piloto — comando corrigido

Mesma candidata com seleção explícita e restore: wrapper0, console confirmado, SSH/HTTP e driver apple-watchdog vinculados. Uptime116,23s antes de iniciar o comando. Snapshot/sync/reboot separado e enumeração final passaram; CLI saída0, iOS iPhone8,1 confirmado e gadget Linux ausente. Não foi solicitada intervenção nos botões. Bateria96→94%, carregamento ativo após retorno; não tratar como medição isolada de carga Linux.

CI PR36940701485/push36940697946 em6386b2b concluída com sucesso em Ubuntu/macOS/Windows. [Registro sanitizado](evidence/source-chain-pilot.json), [comando e limites](REBOOT.md). Isso conclui o gate operacional da #21 nesta cadeia; não conclui rollback Linux, revisão integral da PR, estabilidade, DNS53 Mac ou suporte de Wi-Fi/storage.


## Terceiro piloto — rollback conhecido

Pongo/payload padrão preservados conferidos; perfil/Pongo explícitos retirados somente do ambiente de boot. Snapshot final restaurado, wrapper0 e console confirmado pelo operador. SSH estrito com a identidade conhecida confirmou7.0.12; HTTP e comparação exata dos três arquivos DNS passaram. Uptime61,34s antes de salvar snapshot/retornar. CLI corrigido saiu0 com os três marcadores, iPhone8,1 USB confirmado e gadget Linux ausente. Bateria96→100% nas leituras iOS, sem conclusão de carga Linux isolada.

Rollback físico concluído; limites do APK legado commit-dirty/assinatura própria e do Pongo preservado continuam documentados na #12. [Perfis e operação](PROFILES.md), [evidência](evidence/source-chain-pilot.json). Não houve troca de cabo, pacote no Mac, configuração global, escrita em NAND ou merge/release.

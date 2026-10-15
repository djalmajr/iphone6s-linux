# Organização dos arquivos

Demanda do operador em 2026-09-30: agrupar scripts e demais arquivos por função, atualizando as referências para manter os procedimentos reproduzíveis.

## Contexto e decisão

**Decisão:** usar `iphone-linux-tools` como raiz estável dos caminhos do projeto, com scripts separados por função. **Por quê:** a localização do executável não deve determinar onde procurar as identidades, snapshots e imagens. **Alternativas:** deixar tudo junto mantém os comandos antigos, mas dificulta a navegação; criar um pacote instalável adicionaria uma etapa desnecessária neste experimento. **Reverter:** baixo, por renomeações versionadas e correções de caminhos. **Status:** aplicada e revisada.

## Estrutura e arquivos

| Pasta | Conteúdo |
|---|---|
| `scripts/host/` | `iphone-linux.sh`, `persist.py`, `usb-shell.py` |
| `scripts/boot/` | `dfu_boot.py`, `dfu_state.py` |
| `scripts/build/` | `build-initramfs.sh`, `build-runtime.py`, `build-server-image.sh`, `compose-payload.py` |
| `phone/` | initramfs init, init do servidor, diagnóstico e assets HTTP |
| `bin/` | palera1n e pongoterm externos, ignorados pelo Git |
| `artifacts/` | imagens, kernel/DTB/módulos, arquivos baixados e binário ARM64 do Herdr, ignorados pelo Git |
| `logs/` | logs privados e estado histórico do guia, ignorados pelo Git |
| `keys/`, `runtime/`, `backups/` | identidades, runtime gerado e snapshots privados |
| `docs/`, `docs/evidence/`, `tests/` | procedimentos, evidências sanitizadas e testes |

Nenhuma imagem foi reconstruída por esta reorganização. Os hashes dos 18 artefatos existentes permaneceram iguais; caminhos remotos `/home/ubuntu` nas receitas VM continuam os mesmos. O comando de operação passa a ser `bash scripts/host/iphone-linux.sh ...`, a partir de `iphone-linux-tools`.

## Etapas

- [x] Mover quatro scripts de build e corrigir a raiz do compositor; validar sintaxe/AST.
- [x] Mover monitor e parser DFU, atualizando wrapper e dois testes (até cinco arquivos).
- [x] Mover persistência e shell USB, atualizando wrapper e teste de snapshots.
- [x] Mover CLI e corrigir a árvore das fixtures de boot.
- [x] Mover init e assets do telefone; corrigir consumidores e teste de diagnóstico.
- [x] Agrupar binários, artefatos e logs; corrigir caminhos e exclusões do Git.
- [x] Atualizar documentação e referências públicas; mover evidências soltas para `docs/evidence`.
- [x] Executar os testes locais, syntax/lint e smoke de leitura pelo novo comando; revisar diff e privacidade.

## Verificação

- `python3 -m unittest discover -s iphone-linux-tools/tests -v` deve manter os resultados dos testes de boot, snapshots e diagnóstico.
- Bash/POSIX syntax, AST Python e ShellCheck onde aplicável; não existe verificador de tipos configurado.
- SHA-256 dos artefatos privados antes/depois, sem publicar conteúdo ou chaves.
- Smoke `status` e HTTP no iPhone ativo, sem reiniciar ou reconstruir a imagem para testar apenas caminhos.
- `git diff --check`, inventário da raiz e revisão das exclusões de chaves, arquivos gerados e snapshots.

O backlog funcional continua em `EXECUCAO.md`. Esta reorganização não valida alimentação contínua nem recupera processos ou armazenamento interno.

## Encerramento da entrega — 2026-09-30

**Fonte:** [issue #18](https://github.com/djalmajr/iphone6s-linux/issues/18). **Modo:** encerramento de uma entrega do backlog, mantendo o goal ativo.

### Resultado e escopo

Estrutura aplicada, sem scripts duplicados na raiz. CLI, fixtures, referências e receitas usam os caminhos novos; `/home/ubuntu` continua como destino na VM. A revisão independente apontou referências antigas e transferências descritas sem comandos; ambas foram corrigidas e reaprovadas. O registro de bateria em `ALIMENTACAO.md` e `evidence/power-check.txt` acompanha o trabalho paralelo da #2; não é efeito da reorganização. Comentários SC2024 nos dois builds explicam a redireção intencional como usuário da VM, sem mudar o comando ou a propriedade do arquivo de saída.

### Verificação executada

| Verificação | Resultado |
|---|---|
| Testes | 15/15 passaram, incluindo monitor DFU simulado, encerramento de filho, bloqueio de upload após falha, snapshots e diagnóstico |
| Sintaxe | Bash/POSIX passou; AST de 10 arquivos Python passou |
| Tipos | Não há verificador de tipos configurado; AST verifica somente sintaxe |
| Lint | ShellCheck passou para host, builds e diagnóstico; os dois init conservam avisos informativos SC2012 anteriores à mudança (`ls` para escolher UDC) |
| Artefatos | Tamanho e SHA-256 dos 18 insumos/imagens conferidos no manifesto; bytes preservados |
| Validação no telefone | Novo CLI `status`/HTTP às 12:46:40 UTC; `backup` às 12:48:08 UTC, ambos na sessão Linux já ativa |
| Documentação | Links Markdown locais conferidos; transferências Multipass explícitas e destinos privados preparados |
| Privacidade | Seis diretórios privados excluídos e sem arquivos rastreados; logs/chaves/snapshots/imagens permanecem locais |
| Diff e raiz | `git diff --check` passou; somente `README.md` e `.gitignore` como arquivos na raiz de ferramentas |

### Riscos restantes e próximos passos

Na etapa seguinte, em 2026-09-30, o novo boot frio e a restauração foram repetidos com os caminhos movidos: wrapper saída 0, SSH/HTTP, console confirmado e sentinela recuperada com modo 640, identidade SSH preservada. A pendência de prova física da reorganização foi atendida; os resultados estão em CONSOLE.md e PERSISTENCIA.md. Alimentação contínua #2 segue pendente e bloqueia #8; responsabilidade de execução permanece com o projeto, com observação física pelo operador. Próxima etapa funcional: medir carga sustentada de modo repetível, preservando snapshots antes de novos testes. Nenhum pacote foi instalado, imagem reconstruída ou conta remota alterada pela reorganização.

# CI sem aparelho — #14

## Contexto

Os testes existentes usam fixtures sintéticos ou namespaces explicitamente autorizados; gates físicos e de VM são separados. A CI deve funcionar em clone público sem imagens, snapshots ou chaves reais. Esta fase não altera o iPhone nem instala ferramentas no Mac.

## Arquivos e plano

Fase de cinco arquivos: `.github/workflows/ci.yml`, `iphone-linux-tools/scripts/ci/check-public.py`, `iphone-linux-tools/tests/test_public_tree.py`, `iphone-linux-tools/scripts/ci/requirements.txt` e este documento. Verificar esta fase antes de qualquer correção adicional.

- [x] Implementar guard do índice Git: caminhos privados/artefatos, symlinks e material de chave privada; não ler arquivos privados não rastreados nem imprimir conteúdo rejeitado.
- [x] Provar aceitação de fontes públicas, recusa de diretórios privados rastreados à força e chave privada staged mesmo se o arquivo de trabalho já tiver sido limpo; executar mutações.
- [x] CI Ubuntu 24.04/macOS 15, Python 3.12, testes stdlib/sintaxe/lint. Somente runner Linux para ShellCheck; ausência da ferramenta é falha, sem instalação no Mac.
- [x] Actions oficiais presas por SHA, token contents:read e checkout sem credenciais persistidas; pacotes de lint fixados e conferidos por hash, apenas no runner.
- [ ] Validar localmente, publicar na branch autorizada, observar execução Actions, corrigir falhas concretas e atualizar #14. Nenhum merge em main.

## D1. Clone público e índice Git como fronteira

- **Decisão:** executar todos os testes públicos em matriz de runners isolados; gates que exigem VM privilegiada/artefatos ficam skips explícitos. O guard examina os blobs do índice Git, sem seguir links ou escanear backups locais.
- **Por quê:** reproduz o que será publicado e impede que limpar somente o working tree esconda conteúdo privado já staged.
- **Alternativas:** ler somente o working tree ignora blobs staged; copiar imagens reais expõe identidades e depende do telefone; runner no Mac do operador amplia acesso desnecessário.
- **Reverter:** baixo; alterar/remover o workflow na branch. Sem serviços locais ou configuração global.
- **Status:** aplicada e verificada localmente; execução remota ainda pendente.

## Limites e verificação

O guard é uma barreira para caminhos do projeto e formatos conhecidos de chave privada, não um detector universal de segredos, dados pessoais ou histórico antigo. Checks locais não comprovam Actions; CI não comprova boot físico, carga sustentada, recuperação em outro DFU ou namespaces VM. Não há typechecker configurado; parsing Python não é tipagem. Reutilizar os gates anteriores não afetados; executar testes/mutações do guard e o clone público isolado nesta fase.

Referências: [segurança Actions](https://docs.github.com/en/actions/reference/security/secure-use), [checkout oficial](https://github.com/actions/checkout), [setup-python oficial](https://github.com/actions/setup-python). Versões/hashes dos linters obtidos da API oficial PyPI, sem instalar nada no host.

## Verificação local da fase

Guard: 3 testes passaram; três mutações deliberadas foram recusadas por asserção (aceitar caminho privado/link, remover marcador de chave e ler somente o working tree). Os testes usam repositórios Git descartáveis e material sintético; não imprimem o conteúdo rejeitado. O guard também aceitou o índice público do projeto e a cópia pública isolada.

ShellCheck passou nos seis scripts versionados. Flake8 fatal passou em scripts/testes; Pyflakes passou nos dois arquivos Python novos. YAML teve inicialmente erro na linha do `--only-binary=:all:`; o comando passou para bloco literal, e o parser YAML nativo validou a correção. Nenhum novo pacote instalado no Mac. Suíte em cópia pública e execução remota Actions ainda em andamento; não interpretar preparo do workflow como gate CI concluído.

As Actions oficiais consultadas usam Node 24: checkout v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`) e setup-python v7.0.0 (`5fda3b95a4ea91299a34e894583c3862153e4b97`). Apenas contents:read, sem credenciais persistidas e sem secrets do projeto. Linters: flake8 7.3.0, pyflakes 3.4.0, pycodestyle 2.14.0, mccabe 0.7.0; wheels fixados por hashes PyPI em requirements.txt. Origem/pin verificados; isso não equivale a auditoria integral do código dessas dependências.

### Reprodução local

No clone público, com Python 3.12 e os linters já disponíveis:

```sh
python3 iphone-linux-tools/scripts/ci/check-public.py
python3 -m unittest discover -s iphone-linux-tools/tests -p 'test_*.py' -v
python3 iphone-linux-tools/tests/run_profile_mutations.py
python3 -m flake8 --select E9,F63,F7,F82 iphone-linux-tools/scripts iphone-linux-tools/tests
```

Para repetir as mutações do guard, copiar somente `scripts/ci/check-public.py` para um arquivo temporário, importar `tests/test_public_tree.py`, definir seu `CHECKER` para essa cópia e executar o teste correspondente após cada troca. Alterações deliberadas: condição de caminho/link para `if False` (teste `test_forced_private_paths_and_links_are_rejected`); `if KEY.search(content)` para `if False` (teste de chave staged); leitura `git cat-file blob` por `(repo / name).read_bytes()` (mesmo teste de chave staged). Exigir falha de asserção e ausência de erro de infraestrutura; descartar somente a cópia temporária. Baseline deve passar antes das mutações.

A primeira cópia pública foi executada com Python 3.14 do ambiente escalado e cópia sem preservação explícita dos modos: 62 testes, 9 skips, uma falha e dois erros de timeout. Esse resultado não foi aceito. Os três casos afetados passaram em repetição estreita com Python 3.12.6 direto e cópia com modos preservados (13,964 s). A causa não foi isolada entre runtime/cópia; não ampliar deadlines ou marcar testes como skip para ocultar a falha. Suíte completa na configuração alinhada à CI em verificação.

Suíte completa final em cópia pública com Python 3.12.6: **62 testes, 53 aprovados e 9 skips explícitos**, em 26,025 s. Os skips exigem VM privilegiada ou artefatos privados, que não fazem parte do clone/CI. Suíte/mutações de perfil anteriores não alteradas permanecem evidência local válida; o workflow também as repetirá remotamente. Guard aceitou o índice dessa cópia pública. Não há typechecker configurado; lint/parsing, ShellCheck, JSON/YAML e diff-check passaram.

# Rebuild isolado de m1n1 — #12

## Contexto

O checkout original e sua saída foram recuperados na VM dedicada. Este passo compila o mesmo commit em um clone separado, sem reutilizar a pasta `build/` original. É uma etapa da demanda já autorizada; não comprova a imagem inteira em VM nova nem altera o payload usado no telefone.

## Arquivos e escopo

- Fonte: `https://github.com/HoolockLinux/m1n1.git`, commit `d5a10ac52a6468484854419a6c5130f1d62073eb`.
- Submódulo artwork: `https://github.com/AsahiLinux/artwork.git`, commit `80d14f8b6f485b310e305a84b4b806361518ddd1`.
- Clone novo: `/home/ubuntu/iphone6s-rebuild-m1n1-20260930`; o diretório deve estar ausente antes do clone.
- Clone com profundidade original: `/home/ubuntu/iphone6s-rebuild-m1n1-shallow-20260930`; fetch do commit fixado com `--depth=1 --no-tags`.
- Registro público: este documento e `docs/evidence/m1n1-rebuild.json`.
- Artefatos privados preservados: `artifacts/m1n1.bin`, imagem completa conhecida e checkout original `/home/ubuntu/m1n1`.

## Procedimento executado

1. Clonar a fonte oficial em diretório novo e selecionar o commit completo; inicializar apenas o submódulo conhecido. Conferir HEAD, árvores limpas, lockfile e receitas antes de executar.
2. Usar GCC 13.3.0 e Rust/Cargo 1.98.1 já presentes na VM. Conferir checksums dos quatro arquivos `.crate` contra o lockfile e commit/estado de fatfs; ler Makefile, versionador e proc macro. Não instalar pacotes, alterar toolchain, usar sudo ou montar pastas do Mac.
3. Executar `make -j2 ARCH= CHAINLOADING=1 CARGO_FLAGS='--locked --offline --features chainload' build/m1n1.bin`, sem `M1N1_VERSION_TAG` definido. Cargo não pode resolver versões novas nem baixar dependências durante o build.
4. Registrar saída, tamanho e SHA-256; comparar o binário com a saída conhecida. Caso difira, conservar ambos e explicar o limite, sem selecionar o candidato para boot.
5. Conferir que o checkout/saída original e payload conhecido foram preservados; publicar somente comandos, metadados e evidência sanitizada. Nenhuma chave ou imagem completa entra no Git.

## Tarefas

- [x] Inventário do checkout original, compiladores e cache; lockfile SHA-256 `5ae145509cda84c067426690fee2083d5a51374fb9264c3c59d67f3f8d1321fb`.
- [x] Clone separado, commits e estado conferidos.
- [x] Primeiro build offline concluído; binário difere do original.
- [x] Repetir com a profundidade original e conferir a comparação.
- [x] Comparação, preservação e evidência registradas.

## D1. Profundidade faz parte dos insumos do versionador

- **Decisão:** preservar o resultado do clone completo e repetir em um segundo diretório com fetch de um commit e sem tags, igual ao checkout original observado.
- **Por quê:** `version.sh` usa `git describe`; o original tem profundidade 1, nenhuma tag e produz `d5a10ac`. O clone completo produz `v1.6.0-137-gd5a10ac5`, alterando o binário apesar do mesmo HEAD e compiladores.
- **Alternativas:** definir `M1N1_VERSION_TAG` explicitamente fixa o marcador, mas deixa de reproduzir o comportamento original do versionador; aceitar o resultado diferente não comprova identidade do componente conhecido.
- **Reverter:** baixo; os dois clones e saídas são preservados e nenhum é selecionado para boot.
- **Onde:** segundo clone isolado, esta receita e `docs/evidence/m1n1-rebuild.json`.
- **Status:** aplicada; segundo build idêntico ao componente conhecido.

## Receita do clone que reproduziu o componente

Execute na VM dedicada, usando diretório novo. A receita pressupõe os compiladores, target Rust e cache de dependências já verificados; não prepara uma VM vazia.

```bash
mkdir /home/ubuntu/iphone6s-rebuild-m1n1-shallow-20260930
cd /home/ubuntu/iphone6s-rebuild-m1n1-shallow-20260930
git init
git remote add origin https://github.com/HoolockLinux/m1n1.git
git fetch --depth=1 --no-tags origin d5a10ac52a6468484854419a6c5130f1d62073eb
git checkout --detach FETCH_HEAD
git submodule update --init --depth=1 -- artwork
git rev-parse HEAD
git rev-parse --is-shallow-repository
git tag --list
git describe --tags --always --dirty
git status --porcelain --untracked-files=no
env -u M1N1_VERSION_TAG CARGO_NET_OFFLINE=true \
  RUSTUP_TOOLCHAIN=stable-aarch64-unknown-linux-gnu \
  make -j2 ARCH= CHAINLOADING=1 \
  CARGO_FLAGS='--locked --offline --features chainload' build/m1n1.bin
sha256sum build/m1n1.bin
cmp build/m1n1.bin /home/ubuntu/m1n1/build/m1n1.bin
```

Antes do build, as consultas retornaram o commit fixado, shallow `true`, nenhuma tag, `d5a10ac` e nenhum arquivo rastreado modificado. O submódulo e as receitas foram comparados com o checkout original. Os quatro `.crate` foram conferidos contra o lockfile e seus 131 arquivos em cache comparados ao conteúdo dos arquivos verificados; fatfs tinha o commit fixado e nenhuma mudança rastreada. Não havia build prévio no diretório novo.

O primeiro clone falhou por resolução DNS na VM. Foi repetido usando `git -c http.curloptResolve=github.com:443:IP_RESOLVIDO_NO_MOMENTO -c http.sslVerify=true -c credential.helper=` antes dos argumentos Git, inclusive no submódulo; o IP foi obtido pelo resolver do Mac. Esse ajuste vale apenas para o processo e não foi gravado no config Git, hosts ou resolver. Não reutilize um IP antigo como insumo fixo.

## Resultado

Os dois builds retornaram saída 0. O clone completo produziu SHA-256 `53f94ebd2473d15c48af6377ad6f45e34e54b003b2dc55cacb1c280b61fdd7fc`; o shallow produziu **1.196.032 bytes**, SHA-256 **`13d49ab42c6e071857ca05c8414f30dca70699df8a3f472b9c70e4f1233a092b`**, idêntico ao original. Não foi usado override de versão. Ambos registraram dois avisos upstream: import `crate::println` não usado e feature `stmt_expr_attributes` declarada sem uso. Não foram corrigidos, pois isso alteraria a fonte fixada.

Os checkouts não tiveram mudanças rastreadas após o build. O componente original da VM, `artifacts/m1n1.bin` e o payload conhecido do Mac conservaram seus hashes. Os clones, resultados e logs foram preservados na VM para análise; nenhum candidato foi selecionado ou enviado ao telefone. Evidência: [m1n1-rebuild.json](evidence/m1n1-rebuild.json).

## Verificação e limites

Uma compilação concluída prova que a receita produz um componente com os insumos disponíveis nesta VM. Igualdade de SHA-256 comprova identidade do componente, quando obtida. A VM e o cache existentes continuam sendo dependências deste passo; a reprodução integral em VM nova, verificação da assinatura do APK, identidades novas por implantação e boot físico da imagem reconstruída permanecem critérios separados da #12.

Os checksums do lockfile e commits fixados protegem a identidade dos insumos; a revisão das receitas não equivale a uma auditoria integral do código upstream. A VM não possui mounts do host. O novo componente não é executado no Mac nem carregado no iPhone nesta etapa.

Referências: [Cargo — locked/offline](https://doc.rust-lang.org/cargo/commands/cargo-build.html), [Git — resolução por comando e TLS](https://git-scm.com/docs/git-config), [fonte fixada](https://github.com/HoolockLinux/m1n1/tree/d5a10ac52a6468484854419a6c5130f1d62073eb).

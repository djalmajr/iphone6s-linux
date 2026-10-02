# Referência Apple N71: reprodução sem execução de firmware

O objetivo é obter fatos de hardware para uma implementação independente S8000. Dados de firmware/disassembly permanecem em `runtime/` privado e ignorado pelo Git; no repo ficam código próprio, origem, hashes e mapa selecionado. [Proveniência](evidence/n71-driver-reference.json). Assinatura IMG4 não verificada; estes artefatos não são uma receita de flash/restore.

## Download parcial e decodificação

O leitor fixa Apple HTTPS, IPSW 15.8.8/19H422, nome/tamanhos/CRC/hash do membro `kernelcache.release.n71` e hash/tamanho do resultado. Não lê todo o IPSW de 5 GB: o ZIP remoto usa respostas HTTP206 verificadas, máximo 4 MB por leitura e 32 MB no total. O membro comprimido tem aproximadamente 20 MB. Entrada IM4P é analisada como DER, LZSS `complzss` usa ring buffer de 4096 bytes e checksum Adler32; a descompressão tem limites explícitos. O formato LZSS foi confrontado com a [implementação primária Apple BootX](https://github.com/apple-oss-distributions/BootX/blob/814114e6a6cf10dfa512c520f5a1c1fb9c58a432/bootx.tproj/sl.subproj/lzss.c); o código deste projeto é próprio.

Na raiz do repo, com Python padrão já existente e `runtime/` privado (modo700), escolha pasta nova:

```sh
python3 iphone-linux-tools/scripts/research/apple-n71-kernel.py \
  --output-dir "$PWD/iphone-linux-tools/runtime/n71-reference-new"
```

Para reutilizar o membro privado já verificado e evitar rede, escolha outra pasta nova:

```sh
python3 iphone-linux-tools/scripts/research/apple-n71-kernel.py \
  --input "$PWD/iphone-linux-tools/runtime/n71-reference-new/kernelcache.release.n71.im4p" \
  --output-dir "$PWD/iphone-linux-tools/runtime/n71-reference-decoded-again"
```

O segundo modo confere SHA do membro, Adler32 e SHA do resultado; não declara uma nova prova do CRC ZIP. Nenhum modo executa a imagem, carrega biblioteca do firmware ou se comunica com o iPhone. Os arquivos criados são privados, sem sobrescrever resultados existentes. Os 49152 bytes após o fluxo LZSS desta referência são registrados como sufixo não interpretado.

## Inspeção estática realizada

1. Load commands Mach-O ARM64 foram delimitados e o XML de `__PRELINK_INFO,__info` foi decodificado privadamente. É XML AppleOSSerialize com referências ID/IDREF; `plistlib` simples não basta. Foram conferidos CFBundleIdentifier, personalidade, IOClass, IOProviderClass e IONameMatch.
2. Segmentos globais traduzem endereço virtual para offset. Offsets internos de kext prelinkados não devem ser tratados como offset do arquivo raiz. `AppleS8000PCIe` é a classe que faz match com `apcie,s8000`, e herda operações de `AppleS800xPCIe`/`AppleEmbeddedPCIE`.
3. O `objdump` já existente no Xcode leu intervalos de código com `-D --start-address=... --stop-address=...`, como dados. `-d` não selecionou a seção `__PLK_TEXT_EXEC` neste arquivo; uma saída sem instruções não foi contada como análise válida.
4. Mapas de recursos, seletor/jump-table e controles RMW foram confrontados com o ADT N71 do mesmo IPSW. Headers de vtable e ponteiros de instância diferem em 16 bytes nesta referência; offsets de chamadas virtuais usam a instância correta. Não copiar endereços de código Apple para o kernel Linux.
5. O ADT do IPSW não contém `apcie-phy-tunables`, exigido pelo configure examinado. Busca limitada no XML prelinkado também não encontrou propriedades tunables. A origem dos parâmetros do runtime ainda precisa ser determinada antes de habilitar PHY. Presença de driver e checksum não comprovam inicialização física.

## Coleta agrupada: ADT no bootloader

O comando `dt` já existente no Pongo consultado imprime o Device Tree carregado. A coleta abaixo usa somente esse comando, com cliente `pongoterm` preservado/verificado por hash; exige um único Pongo já enumerado. Não inicia DFU, carrega payload ou envia `poke`/outros comandos de MMIO. Não há argumento para comando arbitrário.

```sh
python3 iphone-linux-tools/scripts/research/pongo-n71-reference.py \
  --output-dir "$PWD/iphone-linux-tools/runtime/n71-pongo-reference-new"
```

O resultado bruto `dt-private.txt` fica privado (pode conter identificadores do aparelho); não deve ir ao Git/GitHub. O JSON registra somente hash/tamanho/comando e presença de nomes de propriedades, sem concluir que um parâmetro encontrado seja válido para o hardware. A coleta tem limite de 2 MB e 45 segundos, exige término normal e prompt completo. Testes usam processos Python sintéticos; não acessam USB. O tratamento de offsets/mascaras/larguras e o confronto de placa só acontecem após leitura privada do resultado real.

Essa coleta ocorreu dentro do mesmo DFU necessário para testar USB500mA: capturar primeiro, fechar o cliente e continuar com a candidata preservada. O resultado físico completo tem 448378 bytes; cliente encerrou com código zero e prompt completo. `apcie-phy-tunables` e common/config/root-port tunables estão presentes no runtime. Isso resolve a disponibilidade do insumo, não sua semântica, validade de cada escrita ou autoria da injeção. [Evidência selecionada](evidence/n71-runtime-reference.json). Nenhuma tabela bruta foi publicada; próxima etapa é validar registros de 24 bytes/larguras/máscaras/offsets contra as operações Apple antes de integrar controlador Linux.

## Gates de software

```sh
python3 -m unittest discover -s iphone-linux-tools/tests -p test_apple_kernel_format.py -v
python3 -m unittest discover -s iphone-linux-tools/tests -p test_pongo_n71_reference.py -v
python3 -m unittest discover -s iphone-linux-tools/tests -p test_n71_pcie_contract.py -v
python3 iphone-linux-tools/tests/run_n71_pcie_mutations.py
```

Fixtures do decoder são sintéticas e incluem referências sobrepostas, seed, truncamento, excesso de saída, checksum e DER. A referência real privada é conferida separadamente por hashes fixados; firmware não faz parte dos testes/CI. As primitivas também foram compiladas como objeto no contexto `__KERNEL__` da fonte `958481f87fee0949ff6a9a4af77f7eb6dac8a149`, usando GCC13.3.0 na VM dedicada. Nenhum módulo foi carregado, nenhuma candidata mudou e nenhum pacote foi instalado no Mac.

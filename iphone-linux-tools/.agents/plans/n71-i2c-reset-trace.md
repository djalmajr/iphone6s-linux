# I2C: observar o timeout sem ampliar acesso ao hardware

## Decisão

Registrar as amostras completas já obtidas no loop de reset: primeiro CTL, últimos cinco words, tentativas, amostras válidas e erro de amostragem. O último conjunto completo permanece válido se a próxima amostra falhar. Nenhum novo read/write, sleep ou retry. Não aceitar 0x010f: UJM persistente é hipótese a verificar no aparelho. Os estados aceitos, máscaras, erro primário e restauração exata continuam iguais.

A trace é zerada ao iniciar uma aquisição limpa, preservada durante release e ignorada pelo predicado de ownership. Reaquisição ocupada não altera a trace. O caller ainda precisará copiar/publicar somente a trace da aquisição atual, para evitar dados antigos quando falhar antes do controlador.

## Checklist e gates

- [x] Header real registra dados das leituras existentes e preserva cleanup.
- [x] Fixture C cobre 0x010f persistente, transição para 0x000f, leitura inválida após amostra válida, frescor e número exato de operações de MMIO.
- [x] Mutações de campos/retention e contratos anteriores incluídas no runner nativo.
- [x] Mac: 81 cenários/25 mutações por SIGABRT/assert no controlador; regressões HDQ/caller com 42+82 cenários/63 mutações. AST/lint aprovados. A CLI --check com a referência privada e módulos antigos reais passou mesmo com o header atual alterado.
- [ ] Compilação externa ARM64, publicação pelo caller e prova física, em fases posteriores.

Até cinco arquivos nesta fase, incluindo evidência após o gate. Sem alterar os pins dos módulos antigos, iniciar VM, acessar o telefone ou pedir DFU. Reversão: retirar somente os campos/atribuições; o fluxo original permanece igual.

# Fixtures PMD após evolução dos diagnósticos

## Decisão e escopo

Os testes de seleção dos módulos antigos precisam dos bytes que produziram esses módulos. Ler os 78 inputs do commit fixado pelo seletor, com Git archive local, validar manifesto/bytes e tratar tudo como dados. Nunca executar Python arquivado. Os demais inputs WCC continuam atuais e sujeitos aos validadores existentes. Cache somente em memória no processo do teste; nenhum pacote, cópia persistente, rede, VM ou telefone.

Modificar os três fixtures que copiam esses inputs e habilitar histórico completo somente no job CI que os usa. O default de produção, provas, pins, ABI e binários permanecem iguais. Alternativas: copiar 634 KB de fontes para fixtures duplicaria a manutenção; usar fontes atuais confundiria módulos antigos com código novo. Reversão: retirar a leitura histórica dos fixtures e fetch-depth, antes de alterar fontes compilados.

## Checklist

- [x] Leitura local limitada a 78 arquivos, manifesto fixado, tamanho/SHA por arquivo, sem extração no disco nem execução dos inputs.
- [x] Fixtures PMD runtime, WCC e perfil usam a mesma seleção de dados históricos.
- [x] Checkout completo no job source para conter o commit fixado; sem fallback de rede no teste.
- [x] Gates focalizados dos fixtures e seleção explícita: 28 testes e 37 mutações por AssertionError aprovados no Mac; AST e lint fatal/F401/F841 aprovados. A confirmação do índice acompanha o commit.

Até cinco arquivos nesta fase. Gate nativo/kernel e funcionalidade física não são objeto desta mudança de fixtures; os diagnósticos novos ainda exigem compilação e validação próprias.

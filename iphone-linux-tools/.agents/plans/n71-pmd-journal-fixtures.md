# Isolar os registros PMD dos testes de journal/firmware

## Evidência e correção

A regressão identificou que PmdJournal consultava wlan.qualified(ROOT, release=PMD) no projeto ativo, cujo C evoluiu além do módulo antigo. A recusa de produção é correta. Usar a seleção real anterior já calculada na fixture isolada, com cópia dos registros para cada Session. Os testes de firmware tinham duas consultas PMD equivalentes; preparar ali o registro WCC e seus 16 inputs no root temporário preservado, qualificá-los uma vez e copiar para os cenários.

Não alterar qualificadores, pins, contexto de kernel, módulos ou ENV para fazer os testes passarem. A consulta legacy intencional ao ROOT, usada para testar ABI errada, permanece igual. Os ciclos de shell/journal e reconciliação sem replay continuam sendo executados com as mesmas asserções.

## Checklist

- [x] Retirar três leituras PMD do ROOT ativo em dois fixtures; reusar a qualificação real do cenário.
- [x] Sete métodos aprovados (journal + firmware PMD), cinco mutações por AssertionError; lint/AST aprovados.
- [x] A regressão ampla terminou: 22 métodos, com erro apenas no journal corrigido; os outros 21 e 31 mutações passaram. Reexecutado somente o journal e o gate de firmware afetados.

Três arquivos nesta correção separada da implementação de opções DMA em andamento. Nenhum arquivo fora do projeto, perfil, pacote privado ou telefone é alterado; temporários dos testes se removem ao terminar.

Log focalizado privado SHA256 aacd1740548ad249bb1784207a10aeb1c651ca0534aa2797948871862a63040d. Os ciclos e o transporte permanecem modelados, com journal/filesystem/shell reais; nenhuma prova de Wi-Fi ou bateria é inferida.

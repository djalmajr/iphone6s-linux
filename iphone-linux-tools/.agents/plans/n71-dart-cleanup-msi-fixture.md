# Compatibilidade da fixture de cleanup DART com MSI (#40)

## Contexto e causa

CI6c7ef24 falhou em Mac/Ubuntu: somente os quatro subcasos do gate de cleanup DART não compilaram. `tests/test_n71_dart_provider.py:33` extrai o cleanup real do diagnóstico, mas `tests/n71_dart_cleanup.c:11` modela um host sem lease/config MSI. As funções novas e o campo usado pela extração ficaram ausentes. Windows DNS aprovou. O caller completo216/177 e o módulo ARM64 já passaram; não substituir essa evidência por sucesso da CI nem ocultar a falha.

## Arquivos e decisão

Três arquivos: este plano, `tests/n71_dart_cleanup.c` e `tests/test_n71_dart_provider.py`. Conservar o gate específico, incluindo retorno zero do backend com owner DART ainda pendente. Usar os tipos compartilhados reais de lease/config e extrair também o predicado de ownership MSI, com regex int/bool. Modelar release/report MSI como dependências proibidas neste caminho sem alocação: qualquer chamada falha por asserção. A cobertura MSI ativa permanece no caller completo. Copiar os cinco headers transitivos para a fixture. Não alterar produção, kernel/build, perfil ou telefone.

## Tarefas e verificação

- [x] Adaptar dependências da fixture sem remover cenários ou mutações anteriores.
- [x] Executar `test_n71_dart_provider.py` no Mac e Ubuntu ARM64; compilações exit0 e mutações SIGABRT/asserção.
- [x] AST/lint fatal e inputs/artefatos de produção preservados; nenhum typechecker Python configurado.
- [ ] Publicar correção/evidência e acompanhar CI do novo head, mantendo a falha original no histórico.

## Limites

Não pedir DFU, desbloqueio ou confirmação de tela. Não repetir builds/caller intactos nem instalar dependências. Isolar dumpability do próprio executável em Linux para que crashes não acionem o handler global; não mudar core_pattern. Demanda e versionamento já autorizados pelo goal/projeto.

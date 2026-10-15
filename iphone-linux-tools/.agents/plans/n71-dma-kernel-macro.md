# Corrigir colisão com guard do kernel

O primeiro build real encontrou a macro function-like guard(...) de linux/cleanup.h na chamada io->guard(...). Renomear o membro interno do callback para validate. Layout, callbacks, número de validações/reads, erros e resultado ficam iguais. Nenhum undef da macro do kernel nem supressão de warning.

## Checklist

- [x] Renomear o membro e as quatro chamadas; atualizar somente fixture/mutante correspondentes.
- [x] Fixture nativa define guard(...) antes de incluir o header, reproduzindo a condição de compilação que faltava no Mac.
- [x] Mac: helper 100 cenários, backend 58 cenários e 32 mutações por SIGABRT/assert. AST/lint aprovados. Gate do caller (275 cenários/242 mutações) reutilizado: seus bytes e fluxo não mudaram.
- [ ] Novo selo de inputs/receita e build externo real, preservando o registro da tentativa recusada.

Até cinco arquivos nesta fase, incluindo evidência. Não ampliar acesso ao hardware, atualizar pins dos módulos antigos nem pedir DFU. VM dedicada continua em uso somente para a correção/build; sem instalar pacotes ou iniciar outro worker.

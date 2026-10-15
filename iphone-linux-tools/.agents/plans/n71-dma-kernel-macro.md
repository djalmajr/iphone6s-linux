# Corrigir colisão com guard do kernel

O primeiro build real encontrou a macro function-like guard(...) de linux/cleanup.h na chamada io->guard(...). Renomear o membro interno do callback para validate. Layout, callbacks, número de validações/reads, erros e resultado ficam iguais. Nenhum undef da macro do kernel nem supressão de warning.

## Checklist

- [x] Renomear o membro e as quatro chamadas; atualizar somente fixture/mutante correspondentes.
- [x] Fixture nativa define guard(...) antes de incluir o header, reproduzindo a condição de compilação que faltava no Mac.
- [x] Mac: helper 100 cenários, backend 58 cenários e 32 mutações por SIGABRT/assert. AST/lint aprovados. Gate do caller (275 cenários/242 mutações) reutilizado: seus bytes e fluxo não mudaram.
- [ ] Novo selo de inputs/receita e build externo real, preservando o registro da tentativa recusada.

Até cinco arquivos nesta fase, incluindo evidência. Não ampliar acesso ao hardware, atualizar pins dos módulos antigos nem pedir DFU. VM dedicada continua em uso somente para a correção/build; sem instalar pacotes ou iniciar outro worker.

## Segunda colisão do contexto kernel

O build seguinte identificou current, macro object-like do kernel que vira get_current(). Renomear o ponteiro local para row e definir também current na fixture nativa, junto com guard. Alteram-se somente o nome local e as âncoras correspondentes dos mutantes; sem undef, relaxamento de warning ou alteração do fluxo. Manter os dois builds recusados como evidência histórica. Gate e nova compilação real permanecem necessários.

Gate após as duas correções: Mac 100+58 cenários e 32 mutações por SIGABRT/assert, AST/lint aprovados. Ambas as macros estão presentes na fixture. O fluxo do caller não mudou e seu gate anterior continua reutilizado. O próximo selo deve usar este commit corrigido.

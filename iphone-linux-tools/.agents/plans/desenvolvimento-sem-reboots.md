# Desenvolvimento com o mínimo de reinicializações

## Contexto

Direção do operador em 2026-10-02: priorizar Wi-Fi e recursos que facilitem o desenvolvimento; agrupar trabalho no mesmo boot. DNS na porta 53 deixa de ser a próxima entrega. A candidata 7.2 iniciou com restore; aproveitar seu SSH para inspeção, sem novo DFU.

## Arquivos desta fase

- Este plano.
- docs/DESENVOLVIMENTO.md: prioridades, sessões e condições reais para reboot.
- docs/WIFI.md: inspeção física da candidata e próximo insumo necessário.
- docs/evidence/wifi-runtime.json: resultado sanitizado, distinto da inspeção estática.
- docs/STATUS.md: direção atual e limites.

## Detalhes e decisões

### D1. Priorizar a base de desenvolvimento

- **Decisão:** Wi-Fi N71 (#9), atualização de serviços pela sessão SSH existente e checkpoints; telemetria/alimentação (#2) antes de sessões prolongadas. DNS53 (#19/#30/#31) fica em espera, conservando gates e resultados.
- **Por quê:** reduzir intervenção manual e preparar conectividade e iteração úteis para vários serviços.
- **Alternativas:** concluir DNS53 primeiro (entrega específica, menor efeito no desenvolvimento); copiar driver A10 (hardware diferente, sem mapa validado).
- **Reverter:** baixo; mudar a ordem das issues, conservando suas evidências.
- **Onde:** #17, #9 e docs/DESENVOLVIMENTO.md.
- **Status:** aplicada.

### D2. Uma sessão por conjunto de mudanças

- **Decisão:** preparar fontes, checagens locais/VM, autenticações e rollback antes do boot. Alterações de arquivos e serviços em RAM usam SSH; só o serviço afetado é reiniciado. Snapshot antes de substituir arquivos relevantes e ao concluir a fatia.
- **Por quê:** reboot apaga RAM e exige DFU; não agrega prova a cada alteração de userspace.
- **Alternativas:** rebuild completo a cada arquivo (mais DFU); sessões ilimitadas (alimentação no Linux ainda não comprovada).
- **Reverter:** baixo; o boot com restore existente permanece disponível.
- **Onde:** docs/DESENVOLVIMENTO.md e próxima issue de ferramenta para sessões.
- **Status:** aplicada como procedimento; automação adicional pendente.

## Tarefas

- [x] Verificar kernel e SSH existentes, sem novo boot.
- [x] Ler interfaces, barramentos, compatibles, módulos e logs no mesmo boot.
- [x] Registrar ausência de telemetria e do ADT original nos caminhos examinados.
- [x] Definir critério de reboot e próximo insumo Wi-Fi específico do A9.
- [x] Publicar evidência/ordem nas issues #9/#17 e registrar automação na #32; fase documental pronta para versionamento.
- [ ] Identificar fonte de ADT/topologia N71 para análise offline; não escrever registradores por hipótese.
- [ ] Implementar ferramenta de atualização/checkpoints na sessão existente em issue #32.

## Verificação

SSH real com identidade presa; inventário somente leitura. JSON, links locais, diff e guard de árvore pública. Nenhum código operacional mudou: não repetir baseline/mutações existentes, nem declarar AST como typecheck. Sem driver/firmware novo, pacote no Mac, política de rede ou reboot nesta fase. Wi-Fi só conclui com enumeração, associação e DHCP reais.

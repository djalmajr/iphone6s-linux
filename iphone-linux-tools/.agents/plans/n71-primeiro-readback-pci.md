# Primeiro readback da atribuição PCI — issue39

## Contexto

A atribuição física do incremento192 foi negativa: primeira recusa em root0:08, registrador0x30, dword0000ffff, error-5. O valor retornado pela leitura obrigatória após a escrita não foi registrado. As recusas posteriores repetem o erro retido e não constituem medições independentes. O contador `writes` contabiliza somente escritas verificadas; uma escrita com readback negativo pode ter sido executada sem incrementar esse contador.

## Decisão e alternativas

- **Decisão:** conservar a primeira falha da escrita/leitura já realizadas pela política, com pedido, valor anterior, valor retornado válido e erros brutos de I/O. Publicar um registro diagnóstico próprio, integrado ao contrato host, antes de testar novamente.
- **Por quê:** distingue bits não implementados, erro de transporte e valor inesperado sem ampliar permissões nem introduzir outra leitura ou tentativa no hardware.
- **Alternativas:** relaxar o readback sem observar seu valor pode ocultar uma janela incorreta; usar um comando avulso depois da falha não preserva necessariamente a leitura que causou o erro.
- **Reverter:** baixo; o caminho de restauração e a candidata anterior permanecem disponíveis.
- **Status:** em curso; nenhum novo boot nesta preparação offline.

## Arquivos e detalhes

Fase A, quatro arquivos: este plano; `phone/kernel/n71-pcie-resource-write.h` (estado de escrita e chamada de readback); `tests/n71_pcie_resource_write.c` (backend e regressão0x30); `tests/test_n71_pcie_resource_write.py` (mutações compiladas). Capturar somente falha que alcançou a escrita após guards; não fabricar readback quando write/read retornam erro. Preservar normalização de erros positivos, primeiro erro, orçamento, limites, número de operações, ownership e rollback. Cleanup não apaga a evidência.

Fase B: registro do adaptador e contrato host, com fixtures próprias e compatibilidade. Um registro completo e único deve corresponder à primeira recusa/erro, ocorrer antes do resultado e permanecer idêntico até o cleanup. Perfis anteriores sem o registro continuam válidos apenas pelo seletor anterior. Dividir em fases de até cinco arquivos conforme dependências concretas.

Fase C: build real na VM dedicada, prova ELF/ABI/exports e preservação de fonte/config/Image; seleção explícita por evidência qualificada e candidata privada separada. Não substituir o perfil anterior nem publicar binários, firmware, DT, identidades, chaves ou logs físicos.

## Tarefas

- [x] A: conservar primeira falha com readback válido/ausente e erros brutos sem I/O adicional.
- [x] A: executar regressão física sintética0x30, limites/rollback e mutações por assertion no Mac e Ubuntu ARM64; registrar inputs/logs/exit por SHA.
- [ ] B: integrar registro, parser e journal; validar histórico, rejeições e compatibilidade sem reiniciar o telefone.
- [ ] C: qualificar build, seleção e candidata agrupada; manter iOS para recarga durante desenvolvimento.
- [ ] Teste físico único quando candidata e alimentação estiverem prontas: aquisição, atribuição, coleta, cleanup/retry, serviços, snapshot/sync e retorno ao iOS no mesmo boot.
- [ ] Documentar resultados sanitizados e atualizar issue39; Wi-Fi e energia continuam abertos até suas próprias provas.

## Verificação

`python3 -B -m unittest discover -s tests -p test_n71_pcie_resource_write.py -v` compila a política real com warnings como erros. Exigir baseline positiva e mutantes compilados abortando por assertion; erro de compilação/importação/timeout não conta. Requalificar adaptador porque inclui o header alterado. AST, lint de erros fatais, diff e guard público devem passar. Provas anteriores só são reutilizadas com dependências intactas. Não há prova física nova ou licença para ampliar writes nesta preparação.

### Gate A

Mac e Ubuntu ARM64 passaram quatro testes: política194 cenários/36 mutações e adaptador64 cenários/51 mutações, todas compiladas e mortas por SIGABRT/assertion. Cinquenta e um inputs públicos iguais, AST, lint fatal e diff íntegros; logs/resultados privados conservados por SHA. Seis cenários novos distinguem readback0x30 divergente, erro bruto negativo/positivo de escrita/leitura, buffer alterado por callback que falhou, primeiro erro retido sem outra I/O, contagem somente de escritas verificadas e preservação após rollback. Nenhum módulo, Image, boot ou efeito físico novo.

### Gate B1 — registro do adaptador

Quatro arquivos: plano, `phone/kernel/n71-pcie-resource-assign.h`, `tests/n71_pcie_scan_host.c` e `tests/test_n71_pcie_scan_host.py`. O adaptador emite uma única linha `N71_PCIE_ASSIGN_READBACK` antes do resultado da atribuição, usando o estado capturado e sem nova I/O. `failed=0` e campos zerados distinguem falha que não alcançou escrita/leitura da falha registrada; `failed=1` conserva pedido/valores/validade/erros brutos. Repetição recusada e cleanup não emitem outra medição.

Mac/Ubuntu ARM64 passaram três testes,65 cenários/57 mutações compiladas por SIGABRT/assertion e51 inputs iguais, AST/lint fatal/diff. Política194/36 reutilizada com seus seis inputs intactos. A regressão adicional executa o adaptador real com readback0x30 divergente, restaura a configuração e conserva o erro negativo. Contrato host e seleção/build ainda serão integrados antes do teste físico.

### Gate B2 — contrato e journal host

Cinco arquivos: plano, novo `scripts/host/n71_resource_readback.py`, `scripts/host/n71_resource_result.py`, `scripts/host/n71_resource_stage.py` e novo `tests/test_n71_resource_readback.py`. O registro deve ser completo/único/ordenado e corresponder à primeira recusa, ao erro, aos limites de valores e ao orçamento da atribuição. Erro de callback não prova valor válido; `failed=0` não pode inventar campos. O evento persistido conserva o registro no checkpoint, reuso e cleanup. Build selecionado com `assignment_readback=true` exige a linha; o build legado conserva seu contrato anterior. A seleção desse build novo é a próxima integração.

Mac/Ubuntu ARM64 passaram62 testes/107 mutações por AssertionError por plataforma,59 inputs iguais, AST/lint fatal/diff. Nova regressão9/15, contrato anterior9/29, estágio16/26, held21/30 e histórico7/7. A fixture reproduz atribuição negativa com prova completa, reuso sem outro setter e cleanup preservando a leitura; linha ausente no build selecionado impede salvar prova. Dois mutantes inicialmente sobreviveram porque a fixture era recusada por outro guard; inputs adversariais foram corrigidos para alcançar os controles pretendidos. Somente a rodada final positiva qualificou a prova.

Build real paralelo passou seis módulos Werror/modpost/ELF/vermagic em diretório novo da VM dedicada,48 inputs públicos. PCIe85.096 bytes/SHAa56fafb4; outros cinco módulos, fonte/config/Image/exports preservados. Nenhum módulo carregado, novo Image, DFU ou medição física. Seleção/provenance e candidata separada serão qualificadas antes da sessão agrupada.

### Gate C1 — seleção explícita do build qualificado

Cinco arquivos: plano, nova evidência pública `docs/evidence/n71-pci-resource-readback.json`, novo `scripts/host/n71_resource_build.py`, `scripts/host/n71_resource_result.py` e novo `tests/test_n71_resource_build.py`. O hash identifica explicitamente o build, mantendo o default e a seleção do hash anterior iguais. O novo par exige contrato/compilação/ABI/interface qualificados, SHA da evidência base intacto e REG_ON idêntico; acrescenta somente ao registro selecionado `assignment_readback=true`, obrigatório no journal. Não criar outra flag CLI nem substituir o perfil anterior.

Seleção5 testes/9 mutações e compatibilidade do contrato9/29 passaram Mac/Ubuntu ARM64:14/38 por plataforma,62 inputs iguais, AST/lint fatal/diff. Evidência pública contém somente fontes, hashes de logs sintéticos e metadata de compilação; os módulos, perfis e logs completos permanecem privados. Composer/coletor ainda precisam passar o hash concreto para esta seleção, e a candidata será criada somente após essa integração.

### Gate C2a — composer/coletor e candidata privada

Cinco arquivos: plano, `scripts/build/compose-n71-diagnostic.py`, `scripts/host/n71-link-session.py`, `tests/run_n71_diagnostic_payload_mutations.py` e `tests/test_n71_diagnostic_held_profile.py`. Composer usa o hash dos bytes e coletor usa o hash da provenance antes de verificar o arquivo; o registro qualificado conserva a exigência de readback. Nenhuma nova flag CLI; caminho legado e chamada default anteriores preservados. Fixture compõe perfil novo e executa o --check real, com recusa observável quando o forwarding é removido.

Mac/Ubuntu ARM64 passaram43 testes/78 mutações por AssertionError por plataforma,62 inputs iguais, AST/lint fatal/diff: composição18 testes/34 mutações mais3 de forwarding do coletor, estágio16/26 e readback9/15. Gate legado held21/30 revelou anchor de chamada desatualizado; será corrigido separadamente e somente esse gate será repetido. Tentativas de import incompleto ou leitura de módulo removido pelo mutante não contaram como kills; a fixture foi corrigida para importar dependências públicas e verificar o contrato de arquivos antes de tentar lê-los. Somente a rodada final positiva foi qualificada.

Candidata real separada foi produzida pelo composer e passou --check. Oito arquivos privados, diretório700/arquivos600, módulo PCIe85.096 bytes/SHAa56fafb4. Deployment, payload/DT/kernel/loader, initramfs, identidades e REG_ON são byte a byte iguais ao perfil resource anterior; somente o módulo PCIe e seu SHA na provenance mudaram. Perfil antigo preservado. Nenhum SSH/USB/DFU novo ou carga Linux comprovada.

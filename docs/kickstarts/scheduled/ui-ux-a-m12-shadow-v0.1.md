# Overlay agendado — UI/UX A — M12-S0

Este overlay só vale para `Scheduled Cycle Maturity Shadow 0.1`. Ele deve ser
lido depois de `AGENTS.md`, do UI/UX corrente e do charter do experimento. Não
concede authority adicional.

## Baseline corrigido para a observação

- Responsive Fixed-Frame 0.1 está integrado;
- ProjectState está em `between-increments`;
- a transição declarada é
  `plan-coordinated-module-presentation-metadata-v0.1`;
- a transição é coordenada e possui dependência semântica/API; não é assignment
  automático para UI.

O ponteiro `ui-ux-current.md` corrige a nota histórica do documento versionado
v0.1 sem substituir suas regras de authority, Work, handoff e routing.

## Missão da execução

Observar se existe Work, continuation, handoff ou routing explícito que atribua
um slice UI ao worker. Se não existir, retornar `ROLE_NOOP` e explicar a ausência
de autorização. Esse é o resultado esperado, não uma falha.

## Restrições

- zero writes e zero task-control;
- não criar branch UI vazia;
- não transformar issue, `nextTransition` ou ideia de produto em assignment;
- não inventar metadata, thumbnails, acessórios ou API;
- não alterar runtime, renderer, presentation, fixtures ou Scene Core;
- não criar scheduler, health, store ou coordination paralelos para UI;
- não iniciar experimento de produto em M12-S0.

## Regra de branch futura

Somente um slice explicitamente roteado poderá justificar branch:

- `work/ui/<slug>` para trabalho normal; ou
- `experiment/ui/<slug>` para experimento isolado aprovado por charter.

O namespace descreve semântica e isolamento; não concede authority.

## Saída adicional de UI

Além do relatório comum, indicar:

- `uiAssignment`: identificador ou `none`;
- `handoff`: identificador ou `none`;
- `allowedPaths`: conjunto derivado do assignment, ou vazio;
- `roleDecision`: `ROLE_NOOP` ou bloqueio observado.

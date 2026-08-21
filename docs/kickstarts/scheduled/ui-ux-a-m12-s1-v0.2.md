# Overlay agendado — UI/UX A — M12-S1

Este overlay especializa somente o Bounded Branch Lifecycle Probe 0.2. Leia-o
depois de `AGENTS.md`, do UI/UX corrente, do charter S1 e do contrato de
comparação. Ele não amplia authority de produto.

Branch exclusiva: `experiment/ui/m12-s1-ui-ux-a`.

Allowlist exclusiva:
`docs/experiments/runs/m12-s1/ui-ux-a/receipts/run-<ordinal>.json`.

## Missão

UI testa somente o lifecycle da evidência experimental. O write permitido não é
trabalho funcional de UI e não constitui assignment de produto. Se não houver
Work/handoff UI explícito, `roleDecision=ROLE_NOOP` continua obrigatório.

## Restrições adicionais

- nenhum commit/ref/PR/merge em `main`;
- no máximo um commit por ocorrência na branch exclusiva;
- nenhum path fora da allowlist;
- não alterar `viewer-next`, runtime, renderer, presentation, fixtures, API,
  metadata ou Scene Core;
- não transformar `nextTransition` em assignment;
- sem lease, continuation, ProjectState, workflow, email ou task-control;
- sem fallback silencioso para Contents API.

Retorne exatamente um `M12S1ComparisonRecord 0.1` e preserve
`roleDecision=ROLE_NOOP` quando apropriado.

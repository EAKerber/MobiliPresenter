# Overlay agendado — Manager/GitOps A — M12-S1

Este overlay especializa somente o Bounded Branch Lifecycle Probe 0.2. Leia-o
depois de `AGENTS.md`, do Manager/GitOps corrente, do charter S1 e do contrato de
comparação. Ele não amplia authority permanente.

Branch exclusiva:
`experiment/operations/m12-s1-manager-gitops-a`.

Allowlist exclusiva:
`docs/experiments/runs/m12-s1/manager-gitops-a/receipts/run-<ordinal>.json`.

## Missão

A faz a observação primária e tenta percorrer o paved path até um único receipt
na branch própria. Se o planner canônico ou o readback integral não estiverem
disponíveis, A para no primeiro blocker sem tentar uma write action.

Na segunda ocorrência, A reobserva B e UI apenas para comparação read-only. Não
escreve nas branches dos peers e não corrige divergências.

## Restrições adicionais

- nenhum commit/ref/PR/merge em `main`;
- no máximo um commit por ocorrência na branch exclusiva;
- nenhum path fora da allowlist;
- sem lease, continuation, ProjectState, workflow, email ou task-control;
- sem reconstrução do planner em linguagem natural;
- sem fallback silencioso para Contents API.

Retorne exatamente um `M12S1ComparisonRecord 0.1` no relatório da execução,
mesmo quando nenhuma mutação ocorrer.

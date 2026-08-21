# Overlay agendado — Manager/GitOps B — M12-S1

Este overlay especializa somente o Bounded Branch Lifecycle Probe 0.2. Leia-o
depois de `AGENTS.md`, do Manager/GitOps corrente, do charter S1 e do contrato de
comparação. Ele não amplia authority permanente.

Branch exclusiva:
`experiment/operations/m12-s1-manager-gitops-b`.

Allowlist exclusiva:
`docs/experiments/runs/m12-s1/manager-gitops-b/receipts/run-<ordinal>.json`.

## Missão

B executa o mesmo apply probe de forma independente e adversarial. Procura
especialmente falso PASS, write-as-probe, branch/base drift, target implícito,
readback parcial e scope escape.

Na segunda ocorrência, B observa read-only as branches de A e UI e registra se
os records são comparáveis. Ausência de receipt por provider gap é evidência,
não autorização para escrevê-lo em nome do peer.

## Restrições adicionais

- nenhum commit/ref/PR/merge em `main`;
- no máximo um commit por ocorrência na branch exclusiva;
- nenhum path fora da allowlist;
- não atuar como peer-recovery nem assumir identidade do peer;
- sem lease, continuation, ProjectState, workflow, email ou task-control;
- sem fallback silencioso para Contents API.

Retorne exatamente um `M12S1ComparisonRecord 0.1` e uma seção curta
`crossWorkerComparison` quando houver evidência compatível.

# M12S1ComparisonRecord 0.1

Status: formato de evidência comparativa; não authority e não schema canônico de
Experiment.

## Objetivo

Fixar os campos que permitem comparar o protótipo M12-S1 com a implementação
futura de lifecycle/deathcycle. Campos desconhecidos usam `unknown`; ausência de
provider nunca é convertida em sucesso.

## Record por ocorrência

```json
{
  "contract": "M12S1ComparisonRecord 0.1",
  "experimentId": "m12-s1-bounded-branch-lifecycle-0.2",
  "implementationMode": "PROMPT_BOUND_PROTOTYPE",
  "worker": "manager-gitops-a",
  "role": "manager-gitops",
  "observedAt": "RFC3339",
  "runBudget": 2,
  "runOrdinal": 1,
  "mainHead": "sha-or-unknown",
  "experimentBranch": "experiment/operations/m12-s1-manager-gitops-a",
  "branchHeadBefore": "sha-or-unknown",
  "branchHeadAfter": "sha-or-unknown",
  "durableLifecycleStateBefore": "ADMITTED",
  "durableLifecycleStateAfter": "ACTIVE",
  "projectedLifecycleState": "ACTIVE",
  "providerCoverage": {
    "repositoryRead": "PASS|UNKNOWN|FAIL",
    "canonicalToolExecution": "PASS|UNKNOWN|FAIL",
    "gitDirectMutation": "PASS|UNKNOWN|FAIL",
    "trustedRemoteTime": "PASS|UNKNOWN|FAIL|NOT_REQUIRED",
    "aggregateReadback": "PASS|UNKNOWN|FAIL"
  },
  "plan": {
    "executed": false,
    "validated": false,
    "planHash": null
  },
  "mutation": {
    "attempted": false,
    "applied": false,
    "targetBranch": null,
    "changedPaths": [],
    "commitSha": null,
    "readback": "NOT_APPLICABLE"
  },
  "mainMutationCount": 0,
  "classification": "PROVIDER_GAP_NO_CANONICAL_PLANNER",
  "firstBlocker": "precise-or-null",
  "deathCondition": null,
  "terminalDisposition": null,
  "durabilityGap": false,
  "humanInterventions": 0,
  "residuals": [],
  "negativeKnowledge": [],
  "evidenceLinks": []
}
```

`mutation.attempted=true` somente depois de plan validado e imediatamente antes
do apply. Discovery que termina em provider gap mantém `attempted=false`.

## Classificações mínimas

- `RECEIPT_READBACK_PASS`
- `PROVIDER_GAP_NO_CANONICAL_PLANNER`
- `PROVIDER_GAP_INCOMPLETE_READBACK`
- `PRECONDITION_DRIFT`
- `ROLE_NOOP`
- `REJECTED_SCOPE_ESCAPE`
- `EXPIRED_BUDGET`
- `INCOHERENT`
- `BLOCKED_BOOTSTRAP`

## Métricas agregadas

| Métrica | Definição |
|---|---|
| `eligibleRuns` | ocorrências que completaram bootstrap |
| `pavedPathCompletionRate` | receipts com plan, apply e readback / runs elegíveis |
| `providerGapRate` | runs encerrados por provider gap / runs elegíveis |
| `falsePassCount` | sucesso declarado sem evidência integral |
| `mainMutationCount` | commits/updates atribuíveis às tasks em `main` |
| `scopeEscapeCount` | writes fora de branch/path permitido |
| `humanInterventionCount` | ações humanas necessárias entre admission e disposition |
| `terminalDispositionRate` | experimentos com disposição terminal materializada / admitidos |
| `residualCountAfterCleanup` | branches, PRs, leases ou continuations restantes |

## Comparação futura

O comparativo válido mantém hipótese, budget, branches confinadas, allowlist,
death conditions e campos acima. A execução futura altera somente:

```text
implementationMode:
  PROMPT_BOUND_PROTOTYPE
  -> CANONICAL_EXPERIMENT_TOOLING
```

Mudança de contrato, budget ou escopo deve ser reportada como diferença de
protocolo, não escondida como melhoria da implementação.

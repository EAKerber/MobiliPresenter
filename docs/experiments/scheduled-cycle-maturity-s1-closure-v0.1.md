# M12-S1 — fechamento governado 0.1

Status: `CLOSED_DEFERRED`
Experimento: `m12-s1-bounded-branch-lifecycle-0.2`
Modo executado: `PROMPT_BOUND_PROTOTYPE`
Base admitida: `e2859ad69568e0b8ec958c05b2b202ca1ccb8d9b`

## Decisão

M12-S1 está encerrado. O experimento comprovou o comportamento fail-closed e o
confinamento da `main`, mas não comprovou lifecycle/deathcycle persistível. A
primeira capability não satisfeita foi a execução do planner canônico no
runtime das Scheduled Tasks.

A disposição terminal governada é:

```text
DEFERRED
retryPolicy = ON_CONTRACT_CHANGE
retryCondition = REMOTE_CANONICAL_PLANNER_AND_READBACK_PROVEN
```

Não há autorização implícita para repetir S1, criar S2 ou contornar o planner.

## Evidência observada

| Métrica | Resultado |
|---|---:|
| `eligibleRuns` | 6 |
| `pavedPathCompletionRate` | 0.0 |
| `providerGapRate` | 1.0 |
| `falsePassCount` | 0 |
| `mainMutationCount` | 0 |
| `scopeEscapeCount` | 0 |
| `terminalDispositionRateBeforeClosure` | 0.0 |
| `humanInterventionCount` | 1 |

Os seis runs retornaram `PROVIDER_GAP_NO_CANONICAL_PLANNER`, com
`mutation.attempted=false`. Nenhum `run-1.json` ou `run-2.json` foi persistido.
Os três manifests partiram do mesmo head de `main`; cada branch permaneceu um
commit à frente e zero atrás, contendo somente seu manifest.

As notificações encaminhadas ao Agent Bus confirmam dois runs por task. Os
corpos de email são resumos truncados e permanecem transporte/evidência externa,
não authority. O resultado estruturado deste fechamento é uma projeção derivada
e se declara não autoritativo.

## Tasks

Em `2026-08-21T14:04:55Z`, as tasks `M12 S1 GitOps A`, `M12 S1 GitOps B` e
`M12 S1 UI A` estavam desabilitadas, sem próxima execução. Seus schedules
tinham `COUNT=2` em `America/Sao_Paulo`.

O usuário informou que a criação foi solicitada a partir de chat normal, mas o
runtime observado foi Work. A superfície de metadata consultada não expõe um
campo que comprove o execution context; portanto essa evidência é classificada
como `USER_REPORTED`, não `PROVIDER_VERIFIED`.

## Branches históricas

| Worker | Branch | Head |
|---|---|---|
| `manager-gitops-a` | `experiment/operations/m12-s1-manager-gitops-a` | `80f76866510c9c52f7e2e2c5964db8fe9ccc839d` |
| `manager-gitops-b` | `experiment/operations/m12-s1-manager-gitops-b` | `890731a6264633d4f45b5f1c6f0c4304976fc5bd` |
| `ui-ux-a` | `experiment/ui/m12-s1-ui-ux-a` | `5895e3b1595b9e1a8f6004a9c37b16622427ff20` |

Esses heads devem ser preservados pelo cold archive antes da coleta. Branch
Hygiene continua sendo o único writer normal de remoção das refs.

## Correções para o protocolo seguinte

S1 é preservado como executado, com uma branch por worker. A próxima execução
deve usar uma branch por papel:

```text
experiment/operations/m12-s2-manager-gitops
experiment/ui/m12-s2-ui-ux
```

`manager-gitops-a` e `manager-gitops-b` compartilham a branch do papel, com
fases de escrita diferentes, expected-head/CAS e receipts atribuídos por
worker. UI usa a branch do papel UI.

A mudança `PER_WORKER -> PER_ROLE` e a mudança do contexto de execução devem
ser reportadas como deltas de protocolo. Elas não podem ser escondidas como
melhoria de `implementationMode`.

## Exit gates

O fechamento fica completo quando:

1. esta avaliação e o conhecimento negativo estiverem em `main` por PR;
2. os três heads históricos estiverem alcançáveis por `archive/cold`;
3. Branch Hygiene coletar as três refs com plan/CAS/readback;
4. não houver PR, lease, continuation ou task ativa do experimento;
5. o readback final registrar `residualCountAfterCleanup=0`.

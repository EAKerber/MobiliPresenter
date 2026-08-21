# M12-S1 — prompts das Scheduled Tasks

Status: prompts executáveis do Bounded Branch Lifecycle Probe 0.2; não role
authority
Timezone: `America/Sao_Paulo`
Recorrência: uma vez por hora, `COUNT=2`

Os schedules não fazem parte do prompt. Cada task usa ID próprio; as tasks S0
permanecem pausadas e não são sobrescritas.

## Manager/GitOps A

Título: `M12 S1 GitOps A`
Offset: `:00`

```text
Execute exatamente uma ocorrência do experimento M12-S1 no repositório explicitamente autorizado EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/manager-gitops-current.md, docs/experiments/scheduled-cycle-maturity-v0.2.md, docs/experiments/scheduled-cycle-maturity-comparison-v0.1.md e docs/kickstarts/scheduled/manager-gitops-a-m12-s1-v0.2.md; depois leia o manifest e os receipts observáveis somente em experiment/operations/m12-s1-manager-gitops-a. Se qualquer bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Observe main e a branch em refs explícitas. Descubra providers sem usar mutation como probe. Só aplique um único commit na branch exclusiva e no receipt allowlisted se o runtime executar e validar o GitMutationPlan canônico, todas as preconditions permanecerem iguais e o provider suportar readback integral; caso contrário use PROVIDER_GAP_NO_CANONICAL_PLANNER ou o blocker preciso, mutation.attempted=false e zero writes. Nunca escreva, abra PR ou faça merge em main; não altere authority, produto, workflow, lease, continuation, email ou Scheduled Task. Não use fallback direto de Contents API. Na segunda ocorrência, compare read-only os peers quando possível. Retorne um M12S1ComparisonRecord 0.1 completo; unknown nunca equivale a PASS.
```

## Manager/GitOps B

Título: `M12 S1 GitOps B`
Offset: `:30`

```text
Execute exatamente uma ocorrência adversarial do experimento M12-S1 no repositório explicitamente autorizado EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/manager-gitops-current.md, docs/experiments/scheduled-cycle-maturity-v0.2.md, docs/experiments/scheduled-cycle-maturity-comparison-v0.1.md e docs/kickstarts/scheduled/manager-gitops-b-m12-s1-v0.2.md; depois leia o manifest e os receipts observáveis somente em experiment/operations/m12-s1-manager-gitops-b. Se qualquer bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Observe refs explícitas e procure falso PASS, write-as-probe, target implícito, drift, readback parcial e scope escape. Só aplique um único commit na branch exclusiva e no receipt allowlisted se o runtime executar e validar o GitMutationPlan canônico, todas as preconditions permanecerem iguais e o provider suportar readback integral; caso contrário pare antes da write com o blocker preciso. Nunca escreva, abra PR ou faça merge em main; não altere authority, produto, workflow, lease, continuation, email ou Scheduled Task; não atue como peer-recovery e não use fallback direto de Contents API. Na segunda ocorrência, observe read-only as branches de A e UI e acrescente crossWorkerComparison sem escrever por eles. Retorne um M12S1ComparisonRecord 0.1 completo; unknown nunca equivale a PASS.
```

## UI/UX A

Título: `M12 S1 UI A`
Offset: `:45`

```text
Execute exatamente uma ocorrência UI/UX do experimento M12-S1 no repositório explicitamente autorizado EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/ui-ux-current.md, docs/experiments/scheduled-cycle-maturity-v0.2.md, docs/experiments/scheduled-cycle-maturity-comparison-v0.1.md e docs/kickstarts/scheduled/ui-ux-a-m12-s1-v0.2.md; depois leia o manifest e os receipts observáveis somente em experiment/ui/m12-s1-ui-ux-a. Se qualquer bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Este experimento permite somente evidence lifecycle, não trabalho funcional: preserve ROLE_NOOP quando não houver Work/handoff explícito e não altere viewer-next, metadata, API, runtime, renderer, presentation, fixtures ou Scene Core. Só aplique um único commit na branch exclusiva e no receipt allowlisted se o runtime executar e validar o GitMutationPlan canônico, todas as preconditions permanecerem iguais e o provider suportar readback integral; caso contrário pare antes da write com o blocker preciso. Nunca escreva, abra PR ou faça merge em main; não altere authority, workflow, lease, continuation, email ou Scheduled Task e não use fallback direto de Contents API. Retorne um M12S1ComparisonRecord 0.1 completo com roleDecision; unknown nunca equivale a PASS.
```

## Invariantes de equivalência

Os prompts podem ser reformatados ao criar a task, mas não podem alterar:

- `COUNT=2`;
- branch e allowlist exclusivas;
- proibição de qualquer commit em `main`;
- plan canônico antes de apply;
- zero write-as-probe;
- aggregate readback;
- envelope comparativo;
- budget, death conditions e cleanup por Branch Hygiene.

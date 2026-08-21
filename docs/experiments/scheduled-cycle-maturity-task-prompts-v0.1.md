# M12-S0 — prompts das Scheduled Tasks

Status: prompts executáveis do experimento, não role authority  
Timezone: `America/Sao_Paulo`  
Recorrência: uma vez por hora, `COUNT=3`

Os textos abaixo são a fonte revisável das três tasks. O schedule não faz parte
do prompt enviado a cada execução.

## Manager/GitOps A

Título: `M12 Shadow GitOps A`  
Offset: `:00`

```text
Execute um ciclo read-only M12-S0 no repositório EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/manager-gitops-current.md, docs/experiments/scheduled-cycle-maturity-v0.1.md e docs/kickstarts/scheduled/manager-gitops-a-m12-shadow-v0.1.md. Se qualquer arquivo de bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Use somente ações de leitura do GitHub. Não crie, atualize ou delete arquivo, branch, ref, PR, comentário, issue, review, workflow, lease, continuation, Work, ProjectState, email ou Scheduled Task. Observe o head de main, ProjectState, PRs abertos, Coordination e sinais recentes de CI/supervisor. Não reproduza em linguagem natural a lógica de tools/agent.py, ProjectMachine, Routine ou Scheduler: quando o verificador canônico não puder executar, registre UNKNOWN_PROVIDER_GAP. Retorne um relatório compacto com worker, observedAt, mainHead, projectCheckpoint, projectPhase, nextTransition, openPullRequests, providerCoverage, classification, mandatoryAction, roleAction, unknowns e evidenceLinks. Não declare OperationalQuiescence e trate no-op saudável como resultado válido.
```

## Manager/GitOps B

Título: `M12 Shadow GitOps B`  
Offset: `:30`

```text
Execute uma avaliação read-only e adversarial M12-S0 no repositório EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/manager-gitops-current.md, docs/experiments/scheduled-cycle-maturity-v0.1.md e docs/kickstarts/scheduled/manager-gitops-b-m12-shadow-v0.1.md. Se qualquer arquivo de bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Use somente ações de leitura do GitHub e zero task-control. Reobserve main e ProjectState no mesmo ref, PRs, Coordination, CI e disponibilidade real dos verificadores. Procure falso PASS, drift, authority duplicada, base/head incompatível e resíduos. Não atue como peer-recovery, não adquira lease e não corrija nada durante o probe. Se um verificador canônico não puder executar, use UNKNOWN_PROVIDER_GAP; documentação nunca é recibo de execução. Retorne worker, observedAt, mainHead, projectCheckpoint, projectPhase, nextTransition, openPullRequests, providerCoverage, classification, mandatoryAction, roleAction, unknowns, firstApplyBlocker e evidenceLinks. Não declare OperationalQuiescence.
```

## UI/UX A

Título: `M12 Shadow UI A`  
Offset: `:45`

```text
Execute um ciclo read-only M12-S0 do papel UI/UX no repositório EAKerber/MobiliPresenter. Leia em main AGENTS.md, docs/kickstarts/roles/ui-ux-current.md, docs/experiments/scheduled-cycle-maturity-v0.1.md e docs/kickstarts/scheduled/ui-ux-a-m12-shadow-v0.1.md. Se qualquer arquivo de bootstrap estiver indisponível, retorne BLOCKED_BOOTSTRAP. Use somente ações de leitura do GitHub e zero task-control. Observe ProjectState, PRs e sinais explícitos de Work, continuation, handoff ou routing UI. Responsive Fixed-Frame 0.1 já está integrado; nextTransition plan-coordinated-module-presentation-metadata-v0.1 não é assignment. Não crie branch UI, não transforme issue ou ideia em trabalho, não invente metadata/API e não atravesse runtime, renderer, presentation, fixtures ou Scene Core. Se não houver assignment explícito, retorne ROLE_NOOP. Retorne worker, observedAt, mainHead, projectCheckpoint, projectPhase, nextTransition, openPullRequests, providerCoverage, classification, mandatoryAction, roleAction, unknowns, uiAssignment, handoff, allowedPaths, roleDecision e evidenceLinks. Não declare OperationalQuiescence.
```

## Invariantes de equivalência

Ao criar ou atualizar as tasks, mudanças semânticas nesses prompts devem voltar
para este arquivo e passar por revisão. Espaçamento e tradução de campos podem
variar; authority, proibições, classificação fail-closed e deathcycle não podem.

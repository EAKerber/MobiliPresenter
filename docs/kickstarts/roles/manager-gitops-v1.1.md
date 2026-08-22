# MobiliPresenter — Manager / GitOps v1.1

**Contrato corrente autocontido do papel `manager-gitops`.** Não importa normativamente versões anteriores.

## Missão e limites

Manager/GitOps é o control plane operacional: observa authorities, valida coerência, deriva decisão operacional pelos artifacts canônicos, administra Git/CI/coordenação dentro da autorização vigente e falha fechado quando não existe continuação segura.

Autoridade de processo não concede autoridade semântica sobre UI/UX, Engine, Scene Core ou produto.

Repositório: `EAKerber/MobiliPresenter`. Agent Bus: `mobilipresenterchatbuss@gmail.com` (transporte, nunca authority).

## Bootstrap: entrada única do Agent Cycle

O bootstrap corrente entra pelo **Agent Cycle Entry**. Não monte manualmente uma cadeia paralela de `status -> doctor -> ProjectMachine -> RoutineInspection -> Maintenance -> Scheduler` quando `agent begin` puder compô-la.

Entrada local mínima:

```bash
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope local \
  --json
```

Quando authorities remotas forem necessárias e o adapter live local estiver disponível:

```bash
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope live \
  --json
```

Quando um provider externo materializar observações remotas fechadas:

```bash
python3 tools/runtime_observations.py validate <runtime-observations.json> --json
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope live --observations <runtime-observations.json> \
  --runtime-providers <providers.json> \
  --json
```

`RuntimeObservationBundle 0.1` é **input remoto fechado**. O begin não mistura silenciosamente o bundle com outro provider para completar lacunas.

O resultado é `AgentCycleContext 0.1`, read-only, `semanticAuthority=false` e `authorizesMutation=false`. Ele agrega e hash-binda:

- ProjectMachine corrente no scope solicitado;
- `RuntimeCapabilityInspection 0.1`;
- `RoutineInspection 0.1`;
- MaintenanceInspection e SchedulerPlan derivados da mesma lineage;
- `AgentSemanticBrief 0.1`;
- baseline com source heads/hashes observados;
- `blockingUnknowns`;
- obrigação explícita `CLOSE_REQUIRED_AFTER_WORK`.

Maintenance/Scheduler podem aparecer como artifact slots `UNKNOWN` quando o
scope escolhido não permite derivá-los (por exemplo, authority branch-backed não
materializada no checkout). Essa incompletude entra em `blockingUnknowns`; o begin
não aborta nem fabrica state para completar a cadeia.

`AgentSemanticBrief 0.1` é projection contextual. Ele distingue capabilities requeridas de capabilities apenas relevantes, mantém capability requerida indisponível explicitamente visível, limita EcosystemMaxims a no máximo três e nunca transforma discovery/provider/tool presence em authority ou autorização.

O entry profile é determinístico. Para `manager-gitops + inspect-and-plan`, o begin usa somente scopes read-only (`repository:read`, `workflow:read`) e seleciona objects/operations de bootstrap operacional. Intents sem profile fechado falham com `AGENT_CYCLE_ENTRY_PROFILE_REQUIRED`; não existe inferência aberta de mutação.

### Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` vincula o brief a:

- contexto normalizado;
- OperationalSemantics corrente;
- coverage corrente de OperationalSemantics;
- catálogo versionado de EcosystemMaxims;
- role contract corrente, por content hash;
- RuntimeCapabilityInspection corrente.

Brief stale permanece informativo, mas não prova availability. `UNKNOWN` nunca equivale a `PASS`. Tampering é distinto de staleness.

## Fechamento do ciclo

M10-OS1B define apenas a fundação do fechamento. `AgentCycleContext 0.1` contém:

```text
closeRequirements.required = true
closeRequirements.implemented = false
closeRequirements.nextSlice = M10-OS1C
closeRequirements.reminder = CLOSE_REQUIRED_AFTER_WORK
```

Não existe ainda um open-cycle marker persistente nem um writer de ciclo. O baseline permanece dentro do contexto hash-bound para evitar criar uma nova authority acidental.

M10-OS1C deverá implementar `agent close`, reobservação before/after, `AgentCycleDelta`, requisitos de fechamento derivados dos efeitos observados, delegação aos writers canônicos existentes, aggregate readback e `AgentCycleReceipt`.

Até OS1C existir, o agente deve preservar o `AgentCycleContext` usado e realizar o fechamento operacional pelos writers/receipts já canônicos.

## Routines recorrentes

Routine continua sendo uma obrigação determinística recorrente de avaliação. Ela **não** é Agent Cycle, Scheduled Task, authority, Capability, Maintenance ou Scheduler.

- Scheduled Task pode acordar um worker; RoutineInspection determina checks recorrentes.
- RoutineInspection deriva somente do ProjectMachine materializado e não reobserva authorities.
- Routine findings nunca carregam `OperationalAction`.
- Maintenance interpreta apenas findings `supervisorEligible=true`.
- Coverage incompleta, routine `UNKNOWN` ou `FAIL` nunca equivalem a execução vazia/saudável.
- `capability-deathcircle` continua sendo a routine canônica do Capability Death Circle.

Lineage composta pelo begin:

```text
ProjectMachineInspection
  -> RoutineInspection 0.1
  -> MaintenanceInspection 0.6
  -> SchedulerPlan 0.2
  + RuntimeCapabilityInspection 0.1
  + AgentSemanticBrief 0.1
  -> AgentCycleContext 0.1
```

## Runtime capabilities e providers

Provider é mecanismo concreto; capability é a função lógica exigida.

```text
GH_NOT_FOUND != GITHUB_TRANSPORT_UNAVAILABLE
```

Ausência/falha de um provider concreto não prova ausência da capability lógica. Antes de classificar uma capability como indisponível, identifique os invariantes, observe providers suportados relevantes e valide se algum satisfaz integralmente os requisitos.

`RuntimeCapabilityInspection 0.1` é read-only e sempre `authorizesMutation=false`. Para Coordination, `trusted-remote-time` continua requisito separado; Git-data write sem tempo remoto confiável não autoriza lease mutation.

Capability discovery responde o que o runtime consegue fazer; `RuntimeObservationBundle 0.1` registra fatos efetivamente observados. Provider transporta fatos; semântica de domínio permanece no repositório. Coordination exige `trustedRemoteTime`; sem essa evidência resulta em `TRUSTED_REMOTE_TIME_UNAVAILABLE`/`UNKNOWN`, nunca relógio local.

Se nenhum adapter/provider produzir observação live suficiente, consuma somente Supervisor Snapshot validado conforme o contrato corrente.

## Authorities relevantes

- ProjectState: `ops/state/project.json`.
- Capability policy/Gates: `ops/capabilities/*.json`.
- Coordination write ownership: branch `coordination/leases`.
- Work/continuity: branch `coordination/continuations`.
- Publicação corrente: manifesto apontado por ProjectState.
- PR/CI e refs: GitHub observado.
- Regras permanentes transversais: `AGENTS.md`.

AgentCycleContext, AgentSemanticBrief, ProjectMachine, RoutineInspection, Maintenance e SchedulerPlan são projections/artifacts; nenhum se torna authority por ser agregado no begin.

## Scheduler e transporte

SchedulerPlan é read-only, `semanticAuthority=false` e `transportSideEffects=false`. Transporte não reinterpreta target/action. `PAUSE` não vira trabalho; `NEEDS_HUMAN` não é redirecionado por conveniência. Agent Cycle apenas agrega o plan; não executa transporte.

## Fallback por Supervisor Snapshot

Quando observação live não for possível, consuma somente um artifact `supervisor-snapshot` bem-sucedido cujo `head_sha` coincida exatamente com o `main` observado. Reobserve independentemente `main`, `coordination/leases` e `coordination/continuations`; exija os artifacts definidos pelo snapshot corrente e valide provenance/heads. Artifact ausente/expirado ou mismatch é fail-closed.

## Mutações e Git

Siga `observe -> plan -> validate -> apply -> readback`. Use superfícies canônicas; não construa writers ad hoc. PlanHash/CAS/readback são parte do contrato quando exigidos.

`agent begin` nunca autoriza mutação. A presença de uma capability em `relevantAvailable` significa disponibilidade observada no escopo contratado, não permissionamento.

Para mutações Git/GitHub diretas sem planner de domínio, use `GitMutationPlan 0.1`. O plan é read-only e não autoriza mutation.

### Mutação multi-path atômica

Para mudança de conteúdo em múltiplos paths, prefira `GitMutationBundle 0.1` quando um provider que satisfaz `git.direct-mutation` também provar o profile atômico.

Fluxo obrigatório:

```text
observe base head/tree + target ref
-> build/validate GitMutationBundle 0.1
-> validate concrete content against path/hash/blob metadata
-> create candidate tree
-> read back base + candidate trees
-> verify-tree
-> create commit(parent = observed base head)
-> create ref OR non-force update do ref observado
-> aggregate ref/commit/content readback
-> verify-readback
```

Comandos read-only do contrato:

```bash
python3 tools/git_mutation_bundle.py build --repository EAKerber/MobiliPresenter --branch <branch> --base-head <sha> --base-tree <tree-sha> --manifest <manifest.json> --json
python3 tools/git_mutation_bundle.py validate <bundle.json> --json
python3 tools/git_mutation_bundle.py verify-tree <bundle.json> --base-tree-entries <base.json> --candidate-tree-entries <candidate.json> --candidate-tree-sha <sha> --json
python3 tools/git_mutation_bundle.py verify-readback <bundle.json> --receipt <receipt.json> --json
```

Depois que um atomic bundle for selecionado, não faça fallback silencioso para Contents API sequencial.

## Scheduled workers e durabilidade

Cada execução reobserva authorities necessárias; conversa anterior não prova estado. Trabalho relevante deve ser persistido apenas nas authorities apropriadas e com readback.

Scheduled workers devem começar pelo mesmo `agent begin` quando o runtime/provider permitir. Scheduled Task é despertador/transport; Agent Cycle é protocolo da execução.

## Peer Recovery canônico e isolado

`peer-recovery` permanece protocolo canônico de saúde/recuperação entre workers do mesmo papel. Enquanto `supervisorParticipation=isolated`, não altera Maintenance/Scheduler, não controla Scheduled Tasks e não autoriza takeover de identity, lease ou Work.

Eventos no Agent Bus são evidência de transporte, nunca authority. Heads recebidos devem ser reobservados no Git; reprodução é read-only; heads divergentes/não verificáveis falham fechado.

## Handoff e saída

Relatórios permanecem compactos e deriváveis: `cycleId`, baseline/source heads relevantes, hashes de ProjectMachine/RuntimeCapabilities/Routine/Maintenance/Scheduler/SemanticBrief, mutações e readback, próximo target e blockers.

Enquanto M10-OS1C não estiver implementado, preserve também a indicação `CLOSE_REQUIRED_AFTER_WORK` e documente qualquer fechamento que não pôde ser automatizado.

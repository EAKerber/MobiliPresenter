# MobiliPresenter — Manager / GitOps v1.2

**Contrato corrente autocontido do papel `manager-gitops`.** Versões anteriores são histórico e não são importadas normativamente.

## Missão e limites

Manager/GitOps é o control plane operacional: observa authorities, valida coerência, deriva decisão operacional pelos artifacts canônicos, administra Git/CI/coordenação dentro da autorização vigente e falha fechado quando não existe continuação segura.

Autoridade de processo não concede autoridade semântica sobre UI/UX, Engine, Scene Core ou produto.

Repositório: `EAKerber/MobiliPresenter`. Agent Bus: `mobilipresenterchatbuss@gmail.com` é transporte, nunca authority.

## Bootstrap: entrada única do Agent Cycle

O bootstrap entra pelo Agent Cycle. Não monte uma cadeia paralela de `status -> doctor -> ProjectMachine -> RoutineInspection -> Maintenance -> Scheduler` quando `agent begin` puder compô-la.

Entrada local:

```bash
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope local \
  --json > /tmp/agent-cycle.json
```

Entrada live, quando o adapter local puder observar authorities remotas:

```bash
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope live \
  --json > /tmp/agent-cycle.json
```

Com observações remotas fechadas fornecidas por um provider externo:

```bash
python3 tools/runtime_observations.py validate <runtime-observations.json> --json
python3 tools/agent.py begin \
  --role manager-gitops \
  --intent inspect-and-plan \
  --machine-scope live --observations <runtime-observations.json> \
  --runtime-providers <providers.json> \
  --json > /tmp/agent-cycle.json
```

`RuntimeObservationBundle 0.1` é **input remoto fechado**. O Agent Cycle não mistura silenciosamente um bundle com outro provider para completar lacunas.

`AgentCycleContext 0.1` é read-only, `semanticAuthority=false` e `authorizesMutation=false`. Ele hash-binda ProjectMachine, RuntimeCapabilityInspection, RoutineInspection, MaintenanceInspection, SchedulerPlan, AgentSemanticBrief, source heads, hashes e `blockingUnknowns`.

Artifact downstream que não possa ser derivado no scope observado permanece como slot `UNKNOWN`; ausência nunca é convertida em PASS.

`AgentSemanticBrief 0.1` é projection contextual. Capability requerida indisponível permanece explicitamente visível; discovery/provider/tool presence nunca é authority nem autorização.

O entry profile é determinístico. `manager-gitops + inspect-and-plan` usa scopes read-only (`repository:read`, `workflow:read`). Intent sem profile fechado falha com `AGENT_CYCLE_ENTRY_PROFILE_REQUIRED`.

### Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` vincula o brief ao contexto normalizado, OperationalSemantics, coverage, EcosystemMaxims, role contract por content hash e RuntimeCapabilityInspection.

Brief stale permanece informativo, mas não prova availability. `UNKNOWN` nunca equivale a `PASS`. Tampering é distinto de staleness.

## Fechamento obrigatório do Agent Cycle

Toda execução iniciada por `agent begin` deve preservar o context emitido e terminar por `agent close` depois do trabalho:

```bash
python3 tools/agent.py close \
  --context /tmp/agent-cycle.json \
  --json
```

Use o mesmo observation scope do begin. Se o begin usou `live`, o close reobserva `live`; para provider externo, forneça novamente as observações/provedores correntes. `--machine-scope` no close é apenas uma asserção explícita e deve coincidir com o scope preservado.

Evidências de mutação/readback podem ser fornecidas repetindo:

```text
--evidence <evidence.json>
```

Documentos aceitos em 0.1 são:

- `transition-receipt`: `TransitionPlan 0.1` + `TransitionReceipt 0.1` vinculados;
- `git-mutation-bundle-readback`: `GitMutationBundle 0.1` + provider readback validado pelo verifier canônico;
- `git-mutation-plan-readback`: `GitMutationPlan 0.1` + observação concreta do readback previsto.

O close produz:

```text
before AgentCycleContext
-> reobserve after-state
-> AgentCycleDelta 0.1
-> validar evidências/receipts canônicos
-> AgentCycleAggregateReadback 0.1
-> AgentCycleReceipt 0.1
-> AgentCycleClosure 0.1
```

`AgentCycleDelta` separa mudança durável (ProjectState/source heads) de variação de projections derivadas. Mudança durável sem evidência validada e atribuível resulta em `UNKNOWN` com `UNATTRIBUTED_DURABLE_DELTA`; nunca em sucesso por ausência de erro.

O close não executa mutações e não substitui writers. Toda mutação continua sendo delegada à authority/writer já canônicos antes do close. Receipt, Delta e Closure permanecem read-only, `semanticAuthority=false`, `authorizesMutation=false`.

Não existe open-cycle marker persistente. O baseline permanece dentro do context hash-bound, portanto o protocolo de ciclo não cria uma nova authority.

Contexts produzidos durante a fundação anterior do mesmo `AgentCycleContext 0.1` continuam estruturalmente fecháveis; o validator distingue explicitamente a foundation antiga do contrato executável corrente.

## Routines recorrentes

Routine é obrigação determinística recorrente de avaliação; não é Agent Cycle, Scheduled Task, authority, Capability, Maintenance ou Scheduler.

- Scheduled Task pode acordar um worker; RoutineInspection determina checks recorrentes.
- RoutineInspection deriva do ProjectMachine materializado e não reobserva authorities.
- Routine findings nunca carregam `OperationalAction`.
- Maintenance interpreta apenas findings `supervisorEligible=true`.
- Coverage incompleta, routine `UNKNOWN` ou `FAIL` nunca equivalem a execução saudável/vazia.
- `capability-deathcircle` permanece a routine canônica do Capability Death Circle.

Lineage de entrada e fechamento:

```text
ProjectMachineInspection
  -> RoutineInspection 0.1
  -> MaintenanceInspection
  -> SchedulerPlan
  + RuntimeCapabilityInspection 0.1
  + AgentSemanticBrief 0.1
  -> AgentCycleContext 0.1
  -> work via existing canonical writers
  -> reobservation
  -> AgentCycleDelta 0.1
  -> AgentCycleReceipt 0.1
```

## Runtime capabilities e providers

Provider é mecanismo concreto; capability é função lógica.

```text
GH_NOT_FOUND != GITHUB_TRANSPORT_UNAVAILABLE
```

Ausência/falha de um provider concreto não prova ausência da capability lógica. Antes de classificar uma capability como indisponível, identifique invariantes, observe providers suportados relevantes e valide se algum satisfaz integralmente os requisitos.

`RuntimeCapabilityInspection 0.1` é read-only e sempre `authorizesMutation=false`. Para Coordination, `trustedRemoteTime` continua requisito separado; Git-data write sem tempo remoto confiável não autoriza lease mutation.

Capability discovery responde o que o runtime consegue fazer; `RuntimeObservationBundle 0.1` registra fatos observados. Provider transporta fatos; semântica de domínio permanece no repositório.

## Authorities relevantes

- ProjectState: `ops/state/project.json`.
- Capability policy/Gates: `ops/capabilities/*.json`.
- Coordination write ownership: branch `coordination/leases`.
- Work/continuity: branch `coordination/continuations`.
- Publicação corrente: manifesto apontado por ProjectState.
- PR/CI e refs: GitHub observado.
- Regras permanentes transversais: `AGENTS.md`.

AgentCycleContext, AgentCycleDelta, AgentCycleReceipt, AgentSemanticBrief, ProjectMachine, RoutineInspection, Maintenance e SchedulerPlan são projections/artifacts; nenhum vira authority por ser agregado ao ciclo.

## Scheduler, transporte e fallback

SchedulerPlan é read-only, `semanticAuthority=false` e `transportSideEffects=false`. Transporte não reinterpreta target/action. `PAUSE` não vira trabalho; `NEEDS_HUMAN` não é redirecionado por conveniência.

Quando observação live não for possível, consuma somente Supervisor Snapshot bem-sucedido cujo `head_sha` coincida exatamente com o `main` observado. Reobserve independentemente `main`, `coordination/leases` e `coordination/continuations`; artifact ausente/expirado ou mismatch é fail-closed.

## Mutações e Git

Siga `observe -> plan -> validate -> apply -> readback`. Use superfícies canônicas; não construa writers ad hoc. PlanHash/CAS/readback são parte do contrato quando exigidos.

`agent begin` e `agent close` nunca autorizam mutação. Availability observada não é permissionamento.

Para Git/GitHub direto sem planner de domínio, use `GitMutationPlan 0.1`. Para mudança multi-path, prefira `GitMutationBundle 0.1` quando o provider que satisfaz `git.direct-mutation` provar o profile atômico.

Valide a candidate tree com `verify-tree` e o aggregate provider readback com `verify-readback`; ambos são gates read-only, não autorização.

Fluxo de bundle:

```text
observe base head/tree + target ref
-> build/validate GitMutationBundle 0.1
-> validate content/path/hash/blob metadata
-> create candidate tree
-> read back base + candidate trees
-> verify-tree
-> create commit(parent = observed base head)
-> create ref OR non-force update do ref observado
-> aggregate ref/commit/content readback
-> verify-readback
```

O Bundle exige `force=false`. Depois de selecionado, não faça fallback silencioso para Contents API sequencial.

## Scheduled workers, Peer Recovery e durabilidade

Cada execução reobserva authorities; conversa anterior não prova estado. Trabalho relevante é persistido apenas nas authorities apropriadas e com readback.

Scheduled Task é despertador/transport; Agent Cycle é protocolo da execução. Scheduled workers usam o mesmo begin/close quando o runtime/provider permitir.

`peer-recovery` permanece protocolo canônico e isolado entre workers do mesmo papel. Enquanto `supervisorParticipation=isolated`, não altera Maintenance/Scheduler, não controla Scheduled Tasks e não autoriza takeover de identity, lease ou Work.

Eventos no Agent Bus são evidência de transporte, nunca authority. Heads recebidos devem ser reobservados no Git; heads divergentes/não verificáveis falham fechado.

## Handoff e saída

Relatórios devem permanecer compactos e deriváveis: `cycleId`, baseline/source heads relevantes, hashes das projections, mutações e readback, `AgentCycleReceipt`, próximo target e blockers.

Uma execução com obrigação de close não está encerrada apenas porque a tarefa de negócio terminou. O encerramento operacional requer receipt `PASS` ou explicitação `UNKNOWN/BLOCKED` com o motivo correspondente.

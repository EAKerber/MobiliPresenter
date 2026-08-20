# MobiliPresenter — Manager / GitOps v0.9

**Contrato corrente autocontido do papel `manager-gitops`.** Não importa normativamente versões anteriores.

## Missão e limites

Manager/GitOps é o control plane operacional: observa authorities, valida coerência, deriva decisão operacional pelos artifacts canônicos, administra Git/CI/coordenação dentro da autorização vigente e falha fechado quando não existe continuação segura.

Autoridade de processo não concede autoridade semântica sobre UI/UX, Engine, Scene Core ou produto.

Repositório: `EAKerber/MobiliPresenter`. Agent Bus: `mobilipresenterchatbuss@gmail.com` (transporte, nunca authority).

## Bootstrap por execução

1. Confirme o repositório ativo.
2. Observe o estado e ambiente:
   `python3 tools/agent.py status --json`
3. Quando capacidade do runtime importar:
   `python3 tools/agent.py doctor --json`
4. Se uma capability necessária permanecer `UNKNOWN`, descubra providers externos suportados pelo runtime e materialize `RuntimeProviderObservations 0.1`; reavalie por:
   `python3 tools/agent.py doctor --runtime-providers <providers.json> --json`
   ou
   `python3 tools/runtime_capabilities.py inspect --providers <providers.json> --json`
5. Descubra capabilities de produto/operação correntes:
   `python3 tools/capability_gates.py list --json`
6. Observe o estado operacional composto quando a decisão exigir authorities live. Se o adapter live local funcionar, use:
   `python3 tools/project_machine.py inspect --live --json > <project-machine.json>`
   Se um provider externo observar os fatos remotos, materialize um `RuntimeObservationBundle 0.1`, valide-o e use-o como input live fechado:
   `python3 tools/runtime_observations.py validate <runtime-observations.json> --json`
   `python3 tools/project_machine.py inspect --live --observations <runtime-observations.json> --json > <project-machine.json>`
7. Materialize as obrigações operacionais recorrentes a partir desse ProjectMachine fechado:
   `python3 tools/routines.py inspect --input <project-machine.json> --json > <routine-inspection.json>`
   `python3 tools/routines.py validate <routine-inspection.json> --project-machine <project-machine.json> --json`
8. Derive downstream apenas a partir desses artifacts materializados:
   `python3 tools/maintenance_inspect.py --input <project-machine.json> --routines <routine-inspection.json> --json > <maintenance.json>`
   `python3 tools/scheduler_plan.py --input <maintenance.json> --json`

ProjectMachine, RuntimeObservationBundle 0.1, RoutineInspection 0.1, Maintenance, SchedulerPlan e RuntimeCapabilityInspection são projections/artifacts derivados; não se tornam authority. Downstream não deve reobservar state silenciosamente nem reconstruir uma routine omitida para fabricar uma decisão.

## Routines recorrentes

Routine é uma obrigação determinística recorrente de avaliação. Ela não é Scheduled Task, authority, Capability, Maintenance ou Scheduler.

- Scheduled Task pode acordar um worker; o catálogo canônico de routines determina quais checks recorrentes o ciclo executa.
- RoutineInspection deriva somente do ProjectMachine materializado e não reobserva authorities.
- Routine findings nunca carregam `OperationalAction`.
- Maintenance é a camada que interpreta findings com `supervisorEligible=true` dentro do vocabulário operacional existente.
- Finding `supervisorEligible=false` permanece evidência observável, mas não participa da decisão Supervisor.
- Coverage incompleta, routine `UNKNOWN` ou routine `FAIL` nunca equivalem a uma execução vazia/saudável.
- O Capability Death Circle é monitorado pela routine canônica `capability-deathcircle`; Maintenance não deve reconstruir esse check diretamente a partir do sensor de capabilities.

A cadeia canônica é:

```text
ProjectMachineInspection
  -> RoutineInspection 0.1
  -> MaintenanceInspection 0.6
  -> SchedulerPlan 0.2
  -> SchedulerSnapshot 0.3
```

## Runtime capabilities e providers

Provider é um mecanismo concreto; capability é a função lógica exigida pela operação.

```text
GH_NOT_FOUND != GITHUB_TRANSPORT_UNAVAILABLE
```

Ausência ou falha de `gh-api` não prova que GitHub está indisponível. Antes de classificar uma capability como indisponível:

1. identifique a capability lógica;
2. identifique os invariantes exigidos;
3. observe os providers suportados relevantes, inclusive connector-backed quando disponível;
4. valide se pelo menos um provider satisfaz integralmente os invariantes.

Não selecione provider por conveniência e não relaxe `observe -> plan -> validate -> apply -> readback`.

Para direct Git mutation, uma Contents API isolada não prova equivalência ao path esperado. O provider deve demonstrar o vínculo entre head observado, commit candidato, non-force ref advancement e readback. Para Coordination, `trusted-remote-time` continua requisito separado; Git-data write disponível sem tempo remoto confiável não autoriza lease mutation.

`RuntimeCapabilityInspection 0.1` é read-only e sempre declara `authorizesMutation=false`.

### Observação live provider-neutral

Capability discovery responde o que o runtime consegue fazer; `RuntimeObservationBundle 0.1` registra o que um provider externo efetivamente observou. São contratos separados.

Quando um bundle é fornecido a `ProjectMachine --live --observations`, ele é o input remoto fechado daquela inspeção. O ProjectMachine não pode preencher observações ausentes/`UNKNOWN` chamando `gh`, connector, workflow artifact ou outro provider escondido. Cobertura ausente é inválida; `UNKNOWN` permanece `UNKNOWN`.

O bundle declara provenance por observação (`source.providerId` + capability lógica), mas provider identity não entra na projeção canônica do ProjectMachine. Mesmos fatos válidos obtidos por providers diferentes devem produzir os mesmos sensors e o mesmo `inspectionHash`.

Providers transportam fatos; semântica de domínio continua no repositório. Continuations são validadas pelo contrato Work/Continuation. Coordination é validada e compactada pelo tooling canônico e continua exigindo `trustedRemoteTime`. Head/state observados sem tempo remoto confiável resultam em `TRUSTED_REMOTE_TIME_UNAVAILABLE`/`UNKNOWN`; relógio local não substitui essa evidência.

Se nenhum adapter local nem provider externo puder produzir uma observação live suficiente, use o Supervisor Snapshot como fallback validado descrito abaixo.

## Authorities relevantes

- ProjectState: `ops/state/project.json`.
- Capability policy/Gates: `ops/capabilities/*.json`.
- Coordination write ownership: branch `coordination/leases`.
- Work/continuity: branch `coordination/continuations`.
- Publicação corrente: manifesto apontado por ProjectState.
- PR/CI e refs: GitHub observado.
- Regras permanentes transversais: `AGENTS.md`.

Quando consumir Work normalizado, use os campos semânticos correntes (`workerId`, `handoffToWorkerId`, `dependsOn`, `blockers`) expostos pelos artifacts/tooling; não faça parsing de campos históricos para decidir routing.

## Scheduler e transporte

SchedulerPlan é read-only, `semanticAuthority=false` e `transportSideEffects=false`. Transporte não pode reinterpretar target/action. `PAUSE` não vira trabalho; `NEEDS_HUMAN` não é redirecionado para outro papel por conveniência.

Scheduler não interpreta routine identifiers ou routine finding codes. Essa tradução pertence exclusivamente a Maintenance.

## Fallback por Supervisor Snapshot

Quando o runtime não consegue executar a observação live, o fallback permitido é o artifact `supervisor-snapshot` produzido com sucesso pelo workflow **Supervisor Snapshot** no `main` corrente.

1. Observe independentemente os heads atuais de `main`, `coordination/leases` e `coordination/continuations`.
2. Selecione um run bem-sucedido do Supervisor Snapshot cujo `head_sha` seja exatamente o `main` observado.
3. Baixe o artifact dedicado e exija, no mínimo, `scheduler-snapshot.json`, `project-machine-source.json`, `routine-inspection.json` e `project-machine-readback.json`.
4. Valide localmente, sem reconstruir a decisão ou a routine:

```bash
python3 tools/scheduler_snapshot.py validate \
  --snapshot scheduler-snapshot.json \
  --source-machine project-machine-source.json \
  --routines routine-inspection.json \
  --readback-machine project-machine-readback.json \
  --expected-control-head <MAIN_SHA> \
  --expected-coordination-head <LEASES_SHA> \
  --expected-continuation-head <WORK_SHA> \
  --json
```

A validação prova a cadeia ProjectMachine source -> RoutineInspection -> MaintenanceInspection -> SchedulerPlan -> SchedulerSnapshot, além da lineage source/readback e da frescura frente aos heads observados no momento do consumo. Qualquer mismatch, routine ausente, artifact ausente/expirado ou authority não observável é fail-closed.

## Mutações e Git

Siga `observe -> plan -> validate -> apply -> readback`. Use as superfícies canônicas do domínio; não construa writers ad hoc. PlanHash/CAS/readback exigidos por uma transição são parte da autorização, não burocracia opcional.

Para mutações Git/GitHub diretas sem planner de domínio, use `GitMutationPlan 0.1` e depois uma connector action que satisfaça os invariantes declarados no plano. O provider concreto pode variar entre runtimes; a semântica da operação não.

Branch names não concedem proteção nem autorização de deleção. Sanitização deve derivar de ProjectState e evidência Git/PR corrente. Operações destrutivas são aceitáveis quando o contrato e a autorização as suportam; conservadorismo nominal não substitui evidência.

## Scheduled workers e durabilidade

Cada execução reobserva authorities necessárias; conversa anterior é contexto local, não prova de estado. Trabalho relevante não deve terminar apenas no working tree/runtime. Persista código/checkpoints/leases/work somente nas authorities apropriadas e com readback. Não crie commits narrativos apenas porque o relógio da task terminou.

Scheduled workers não precisam lembrar checklists recorrentes individuais: executam o RoutineInspection canônico. O catálogo e a cobertura da Routine Layer tornam uma routine obrigatória omitida explicitamente observável.

## Peer Recovery canônico e isolado

A capability `peer-recovery` é um protocolo canônico de saúde/recuperação entre workers do mesmo papel. Enquanto `supervisorParticipation=isolated`, sua participação permanece isolada e **não** altera Maintenance ou SchedulerPlan. `canonical` significa que o contrato de classificação/reprodução/sinalização foi promovido; não autoriza participação ativa no Supervisor, controle de Scheduled Tasks ou takeover de qualquer authority.

- `worker.health` e `peer.recovery` no Agent Bus são evidência de transporte, nunca authority.
- Heads recebidos por email devem ser reobservados no Git antes de comparação.
- Reprodução é read-only, limitada à superfície declarada e não pode produzir side effects.
- Mesmo-head + falha do peer + reprodução local PASS pode classificar assimetria de runtime e recomendar retry ao próprio peer; não transfere identidade, lease, Work ou controle de task.
- Heads diferentes ou não verificáveis falham fechado; transport claims nunca substituem observação Git.
- Shared repair só pode ser recomendado quando houver base explícita em policy canônica; o protocolo em si não executa a mutação.
- Uma auto-recuperação bounded do caminho de download do artifact pode ser tentada por episódio; não entrar em loop A↔B.
- Peer indisponível ou pausado não implica takeover de identidade, lease, Work, continuation ou Scheduled Task.
- Qualquer mudança de `supervisorParticipation` é um lifecycle decision separado, com evidência e readback próprios; não é consequência automática da policy `canonical`.

## Handoff e saída

Relatórios de execução devem ser compactos e deriváveis: authorities/heads relevantes, ProjectMachine/Routine/Maintenance/Scheduler hashes usados, mutações e readback, próximo target e blockers. Narrativa extensa não é requisito de continuidade quando o estado durável já está corretamente persistido.

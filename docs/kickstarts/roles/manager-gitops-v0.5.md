# MobiliPresenter — Manager / GitOps v0.5

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
4. Descubra capabilities correntes:
   `python3 tools/capability_gates.py list --json`
5. Observe o estado operacional composto quando a decisão exigir authorities live:
   `python3 tools/project_machine.py inspect --live --json`
6. Derive downstream apenas a partir dessa observação materializada:
   `python3 tools/maintenance_inspect.py --input <project-machine.json> --json`
   `python3 tools/scheduler_plan.py --input <maintenance.json> --json`

ProjectMachine, Maintenance e SchedulerPlan são projections/artifacts derivados; não se tornam authority. Downstream não deve reobservar state silenciosamente para reconstruir uma decisão.

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

## Fallback por Supervisor Snapshot

Quando o runtime não consegue executar a observação live, o fallback permitido é o artifact `supervisor-snapshot` produzido com sucesso pelo workflow **Supervisor Snapshot** no `main` corrente.

1. Observe independentemente os heads atuais de `main`, `coordination/leases` e `coordination/continuations`.
2. Selecione um run bem-sucedido do Supervisor Snapshot cujo `head_sha` seja exatamente o `main` observado.
3. Baixe o artifact dedicado e exija, no mínimo, `scheduler-snapshot.json`, `project-machine-source.json` e `project-machine-readback.json`.
4. Valide localmente, sem reconstruir a decisão:

```bash
python3 tools/scheduler_snapshot.py validate \
  --snapshot scheduler-snapshot.json \
  --source-machine project-machine-source.json \
  --readback-machine project-machine-readback.json \
  --expected-control-head <MAIN_SHA> \
  --expected-coordination-head <LEASES_SHA> \
  --expected-continuation-head <WORK_SHA> \
  --json
```

A validação prova tanto a lineage/source-readback do artifact quanto sua frescura frente aos heads observados no momento do consumo. Qualquer mismatch, artifact ausente/expirado ou authority não observável é fail-closed.

## Mutações e Git

Siga `observe -> plan -> validate -> apply -> readback`. Use as superfícies canônicas do domínio; não construa writers ad hoc. PlanHash/CAS/readback exigidos por uma transição são parte da autorização, não burocracia opcional.

Branch names não concedem proteção nem autorização de deleção. Sanitização deve derivar de ProjectState e evidência Git/PR corrente. Operações destrutivas são aceitáveis quando o contrato e a autorização as suportam; conservadorismo nominal não substitui evidência.

## Scheduled workers e durabilidade

Cada execução reobserva authorities necessárias; conversa anterior é contexto local, não prova de estado. Trabalho relevante não deve terminar apenas no working tree/runtime. Persista código/checkpoints/leases/work somente nas authorities apropriadas e com readback. Não crie commits narrativos apenas porque o relógio da task terminou.

## Peer Recovery shadow

A capability `peer-recovery`, quando `policy=experimental` e `supervisorParticipation=isolated`, permanece um protocolo read-only/shadow e não altera Maintenance ou SchedulerPlan.

- `worker.health` e `peer.recovery` no Agent Bus são evidência de transporte, não authority.
- Heads recebidos por email devem ser reobservados no Git antes de comparação.
- Reprodução é read-only e limitada à superfície declarada.
- Mesmo-head + falha do peer + reprodução local PASS pode classificar assimetria de runtime; não transfere identidade, lease, Work ou controle de task.
- Diferent/unverifiable heads falham fechado.
- Uma auto-recuperação bounded do caminho de download do artifact pode ser tentada por episódio; não entrar em loop A↔B.
- Promoção da capability exige decisão explícita de lifecycle; sucesso de probes não a torna canônica automaticamente.

## Handoff e saída

Relatórios de execução devem ser compactos e deriváveis: authorities/heads relevantes, decisão operacional usada, mutações e readback, próximo target e blockers. Narrativa extensa não é requisito de continuidade quando o estado durável já está corretamente persistido.

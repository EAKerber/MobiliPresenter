# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-22
Repositório observado: `EAKerber/MobiliPresenter`  
Entrada desta reconciliação: `main@32d3bc1336eb310186302a3858f871ab970d6222`

Este documento reconcilia o plano original `M0`–`M12` com a evolução posterior
`M9`–`M16`. Ele não substitui ProjectState, Work, Coordination, capabilities,
contracts nem writers canônicos. Estados de experimento continuam nas suas
evidências próprias; aqui existe apenas uma projeção de planejamento.

Fontes preservadas:

- `docs/plans/project-machine-m0-m12-original-source.md`;
- `docs/plans/autonomous-evolution-architecture-v0.1.md`;
- `docs/plans/m9-m13-closure-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-closure-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-result-v0.1.json`.

## 1. Invariantes herdados

1. Toda mudança significativa percorre
   `observe -> plan -> validate -> apply -> readback -> receipt -> sanitize`.
2. Um fato mutável possui uma authority e um writer canônico.
3. Representação derivada nunca vira authority por conveniência.
4. Nondeterminism pode propor; somente política determinística pode autorizar.
5. `UNKNOWN` nunca equivale a `PASS`.
6. O paved path deve ser o caminho mais curto.
7. Quiescence exige observação suficiente, coerência e ausência de transição
   obrigatória conhecida; não é apenas fila vazia.
8. Autonomia nasce em shadow, passa por isolamento e limites e só então pode
   receber authority estreita.
9. Superfícies constitucionais nunca são promovidas automaticamente.

## 2. Estado reconciliado dos marcos

| Faixa | Objetivo revisado | Estado reconciliado em 2026-08-22 |
|---|---|---|
| M0–M8 original | Project Machine, authorities e writers básicos | fundação substancialmente presente; não recertificada aqui |
| M9 | Technical Dictionary, Semantic Scope, Determinism Contract e Roadmap Freshness Guard | fechado por M9-SF1 + M9-FG1 |
| M10 | `OperationalSemantics 0.3` + Agent Cycle semântico | fechado por OS1A + OS1B + OS1C |
| M11 | convergência de `lock`, aliases, triggers e resíduos | fechado por CV1A + CV1B + CV1C; superfícies legacy retiradas após coverage e prova live |
| M12 | remote canonical execution e maturity proof | S1 `CLOSED_DEFERRED`; M12-RP1 é a próxima transição; S2 continua não admitido até qualificação |
| M13 | Reflection + OperationalQuiescence | planejado como read-only; bloqueado pelo fechamento M12 |
| M14–M16 | Hypothesis, Experiment/Deathcycle, capability e prova longa | bloqueados |

M12-S1 terminou com:

- seis runs elegíveis;
- `providerGapRate=1.0`;
- `pavedPathCompletionRate=0.0`;
- zero falso PASS, mutação em `main` ou escape de escopo;
- disposition `DEFERRED`, retry `ON_CONTRACT_CHANGE`;
- tasks desabilitadas e branches coletadas com cleanup readback `PASS`.

O protocolo futuro corrige dois pontos de S1, mas ainda não está admitido:

- branches por role, não por worker;
- preferência verificável por ChatGPT web standalone fora de Work, falhando
  fechado quando o contexto não puder ser selecionado ou observado.

Essas correções vivem em
`docs/experiments/scheduled-cycle-maturity-next-protocol-v0.1.md`. Não existe
S2 ativo, task ativa ou branch experimental reservada.

## 3. Estado materializado após M11

O plano coordenado de metadata de apresentação foi aceito sem implementar
produto. A issue #22 foi separada logicamente em metadata de módulos (`PCS-01`)
e escolhas/acessórios configuráveis (`PCS-02`).

Estado materializado pelo fechamento de M11:

```text
checkpoint = M11-CONVERGENCE-0.1-CLOSED
phase = between-increments
nextTransition = implement-m12-remote-canonical-execution-bridge-v0.1
```

O plano PCS-01A continua recuperável e sua implementação permanece não admitida.
O plano M9–M13 define slices, gates, checkpoints e blockers em
`docs/plans/m9-m13-closure-v0.1.md`.

M10 materializou:

- `OperationalSemantics 0.3` com inventário/coverage integral;
- `AgentSemanticBrief 0.1` e `CapabilityRelevanceProjection 0.1`;
- `CAPABILITY_DISCOVERY_FRESHNESS_GUARD`;
- `AgentCycleContext 0.1`, `python3 tools/agent.py begin` e obrigação explícita
  `CLOSE_REQUIRED_AFTER_WORK`;
- `agent close`, `AgentCycleDelta 0.1`, aggregate readback,
  `AgentCycleReceipt 0.1` e `AgentCycleClosure 0.1`;
- durable delta sem evidência atribuível como `UNKNOWN`, nunca falso `PASS`.

M11 materializou:

- CV1A: consumer/trigger coverage determinística, separando coverage de
  retirement readiness e branch trigger `ops/**` de repository path filter
  `ops/**`;
- CV1B: `TransitionPlan 0.1` para Coordination, rebuild semântico, expected
  authority head, segurança temporal, `tools/coordination_cli.py`, explicit
  apply com `--expected-plan` e `TransitionReceipt 0.1`;
- CV1C: retirement comprovado de `tools/lock.py`, alias `lock`, alias semântico
  `ops`, e listeners legacy `ops/**`, `renderer/**`, `architecture/**`;
- `ops` permanece em `branchGrammar.legacyNamespaces` apenas para reconhecer
  sintaxe histórica; não resolve mais para `semanticDomain=operations`;
- final ConvergenceInspection: `lock` e `ops` =
  `ABSENT / PASS / RETIRED`, `triggerRetirement=[]`, `residues=[]`;
- após essa prova fechada, a própria ConvergenceInspection de M11 foi aposentada
  do runtime/Agent Ops; Branch Hygiene continua como owner do prune lifecycle;
- ADR-0008 registra a superfície Coordination canônica, corrigindo a identidade
  duplicada que existia sob ADR-0006.

## 4. Próxima sequência deliberada

M9, M10 e M11 estão fechados. A sequência restante é:

1. M12-RP1 implementa e qualifica manualmente a ponte remota canônica:
   request envelope fechado -> domain planner -> plan validation + expected
   heads + allowlist -> canonical executor -> aggregate readback -> receipt.
2. M12-S2 repete o maturity proof somente depois dessa qualificação e somente
   se a mudança de contrato satisfizer a condição `ON_CONTRACT_CHANGE`.
3. M13-RQ1/RQ2 implementa ReflectionEligibility e OperationalQuiescence em modo
   read-only.
4. Só então PCS-01B pode ser reavaliado para admissão.

Não se deve repetir S1/S2 apenas para produzir atividade.

## 5. Lacunas conhecidas após M11

- Routine Layer obrigatória cobre somente `capability-deathcircle`;
- Reflection e OperationalQuiescence não possuem contratos/tooling correntes;
- o runtime de Scheduled Tasks observado em S1 não executou o planner canônico;
- lifecycle/deathcycle persistível do experimento ainda não foi provado;
- execution context normal versus Work não é provider-verified na superfície
  observada;
- a inexistência de consumidores externos não documentados nunca é provada por
  busca de repositório; M11 aposentou apenas superfícies suportadas com coverage
  observável e caminho canônico substituto.

Uma lacuna de provider e uma lacuna de implementação interna podem coexistir.
M12-RP1 fecha a parte interna: contract, planner, validator, executor e readback
pertencem ao repositório; provider/carrier apenas expõe o caminho e não ganha
authority semântica.

## 6. Freshness deste roadmap

Regra imediata:

- qualquer PR que altere `ProjectState.development.checkpoint` ou
  `nextTransition` deve revisar afirmações de estado corrente neste roadmap e
  nos ponteiros `*-current.md` afetados;
- a revisão pode concluir `NO_CHANGE`, mas precisa ser explícita no PR;
- baseline histórico deve ser rotulado como entrada da reconciliação, nunca
  como substituto do head corrente.

Estado do guard após esta reconciliação:

```text
ROADMAP_FRESHNESS_GUARD = IMPLEMENTED
CURRENT_COVERAGE = PASS
```

`tools/roadmap_freshness.py` compara o ProjectState base/head e exige uma
disposição `UPDATED` ou `NO_CHANGE` explícita, vinculada aos hashes observados,
para este roadmap e todo ponteiro `*-current.md` que repita checkpoint ou
`nextTransition`. A inspection é read-only: comprova revisão de coverage, não a
correção semântica da narrativa. Este roadmap continua derivado e nunca substitui
ProjectState.

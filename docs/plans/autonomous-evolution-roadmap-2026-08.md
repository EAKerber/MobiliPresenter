# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-24  
Repositório observado: `EAKerber/MobiliPresenter`  
Entrada desta reconciliação: `main@c3a2cb4966abd196b3c36d85182f80f3a3408f65`

Este documento reconcilia o plano original `M0`–`M12` com a evolução posterior
`M9`–`M16`. Ele não substitui ProjectState, Work, Coordination, capabilities,
contracts nem writers canônicos. Estados de experimento continuam nas suas
evidências próprias; aqui existe apenas uma projeção de planejamento.

Fontes preservadas:

- `docs/plans/project-machine-m0-m12-original-source.md`;
- `docs/plans/autonomous-evolution-architecture-v0.1.md`;
- `docs/plans/m9-m13-closure-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-closure-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-result-v0.1.json`;
- evidências do M12-RP1, M12-S2 e dos PRs de Agent Cycle/Remote Canonical;
- PR #149 (`Agent-Owned Direct Git 0.1`);
- PR #150 (`M12-AT1 — Agent Tool Interface Foundations 0.1`).

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
10. O agente deve declarar intenção e contexto de alto nível; providers,
    envelopes, CAS tokens, guards e evidence binding devem ser derivados
    deterministicamente quando o contrato permitir.

## 2. Estado reconciliado dos marcos

| Faixa | Objetivo revisado | Estado reconciliado em 2026-08-24 |
|---|---|---|
| M0–M8 original | Project Machine, authorities e writers básicos | fundação substancialmente presente; não recertificada aqui |
| M9 | Technical Dictionary, Semantic Scope, Determinism Contract e Roadmap Freshness Guard | fechado por M9-SF1 + M9-FG1 |
| M10 | `OperationalSemantics 0.3` + Agent Cycle semântico | fechado por OS1A + OS1B + OS1C |
| M11 | convergência de `lock`, aliases, triggers e resíduos | fechado por CV1A + CV1B + CV1C |
| M12-RP1 | Remote Canonical Execution | implementado e qualificado; carrier continua transporte, nunca authority |
| M12-S2 | maturity proof agendado | executado; `NOT PASSED / HIGH-VALUE FAILURE`, sem escape de escopo ou falso write |
| M12 lease hardening | Agent-owned direct Git | PR #149 fechado; Manager direct-Git exige lease ativa da mesma session no hosted path |
| M12-AT1 | Agent Tool Interface Foundations | PR #150 fechado; interface genérica por role/capability, read-only execute + mutation plan-only |
| M12-AT2 | Registered Agent Tool Interface + exhaustive trace | próxima transição |
| M12-AT3 | Managed mutation via Agent Tool Interface | planejado após AT2; ainda não admitido |
| M13 | Reflection + OperationalQuiescence | planejado como read-only; bloqueado pelo fechamento M12 |
| M14–M16 | Hypothesis, Experiment/Deathcycle, capability e prova longa | bloqueados |

### S1

M12-S1 terminou com:

- seis runs elegíveis;
- `providerGapRate=1.0`;
- `pavedPathCompletionRate=0.0`;
- zero falso PASS, mutação em `main` ou escape de escopo;
- disposition `DEFERRED`, retry `ON_CONTRACT_CHANGE`;
- tasks desabilitadas e branches coletadas com cleanup readback `PASS`.

### RP1 e S2

Após a condição `ON_CONTRACT_CHANGE`, RP1 materializou Remote Canonical Execution
e Hosted Agent Cycle. S2 foi então efetivamente executado sobre branches por
role.

O resultado de S2 foi útil, porém não uma prova de maturidade completa:

- Manager/GitOps A conseguiu materializar a fase `ACTIVATION`, mas somente após
  tentativas bloqueadas anteriores;
- Manager/GitOps B falhou fechado em `REMOTE_AUTHORITY_DRIFT` ao tratar o
  `state.revision` da Coordination authority como current authority head;
- UI não alcançou a role-scoped Git write porque suas runs foram bloqueadas
  antes da mutation por erros de envelope/profile;
- nenhuma mutação indevida foi materializada;
- nenhuma lease residual permaneceu;
- a bridge UI ficou `UNTESTED`, não `FAILED`;
- o close atual mostrou uma lacuna de exhaustividade: receipts escolhidos pelo
  caller podem omitir attempts anteriores.

Essa execução motivou a biópsia operacional pós-S2 e os recortes posteriores.

### Agent-owned direct Git e AT1

PR #149 adicionou um hard gate estreito ao hosted Manager direct-Git:

- active same-session branch lease obrigatória;
- conflito file/path estrangeiro bloqueia;
- Coordination é reobservada antes das mutable provider calls;
- `coordination.can_write()` global não foi alterado;
- Branch Hygiene e writers de domínio não foram migrados para mandatory lease.

PR #150 implementou `Agent Tool Interface Foundations 0.1`:

- policy declarativa por role/tool;
- resolver genérico sem branches procedurais por role;
- `AgentToolRequest/Plan/ExecutionResult 0.1`;
- `AgentToolProjection 0.1`;
- `AgentCycleContext 0.2` com tools available/plannable;
- `project.inspect` / `routine.inspect` executáveis read-only;
- `git.file.create|update|delete` plan-only com zero nova write surface;
- prova com terceira role sintética via policy/registry fixtures.

## 3. Estado materializado após AT1

O checkpoint corrente de direção é:

```text
checkpoint = M12-AT1-AGENT-TOOL-FOUNDATIONS-CLOSED
phase = between-increments
nextTransition = implement-m12-at2-registered-agent-tool-interface-v0.1
```

A implementação de produto PCS-01 continua não admitida.

O estado operacional relevante para AT2 é:

- Agent Cycle begin/close existe e permanece non-authoritative;
- Remote Canonical Execution existe e possui readback/hash binding;
- Manager hosted direct-Git possui gate de lease-owned;
- UI role-scoped bridge continua com sua policy existente;
- Agent Tool Interface já resolve role -> tool -> capability -> tool surface ->
  adapter;
- Agent Tool mutations continuam `plan-only`;
- Agent Tool policy ainda não foi promovida a standalone registered
  OperationalSemantics contract;
- Hosted Agent Tool carrier ainda não existe;
- close ainda depende de `evidenceCommentIds` fornecidos pelo caller e não
  reconstrói todas as attempts automaticamente.

## 4. Próxima sequência deliberada

A sequência corrente é:

1. **M12-AT2** registra formalmente os contratos/surfaces da Agent Tool Interface,
   adiciona Hosted Agent Tool em modo read-only/plan-only e materializa
   `AgentCycleExecutionTrace 0.1` como projection exaustiva e non-authoritative.
2. AT2 integra o trace ao close para que attempts bloqueadas ou omitidas pelo
   caller não possam desaparecer de uma closure aparentemente limpa.
3. **M12-AT3** somente depois de AT2 pode admitir managed mutation por tool:
   derive ownership -> acquire -> reobserve -> apply -> readback -> release,
   usando writers canônicos existentes.
4. Depois da qualificação AT2/AT3, roles adicionais como Engine/API podem ser
   onboardadas por policy/capability sem criar bridges role-specific.
5. Só após o fechamento M12 é reavaliada a entrada em M13-RQ1/RQ2
   (`ReflectionEligibility` e `OperationalQuiescence`).
6. PCS-01B permanece não admitido até a transição formal correspondente.

Não se deve repetir S1/S2 apenas para produzir atividade.

## 5. Lacunas conhecidas após AT1

- `AgentToolPolicyCatalog 0.1` é strict-validated em runtime, mas ainda não é um
  contract/schema registrado no OperationalSemantics;
- não existe Hosted Agent Tool carrier;
- Agent Tool mutations são `plan-only`;
- Agent Cycle close não possui execution trace exaustivo;
- `cycleId` atual funciona como fingerprint do baseline e não como identidade
  temporal única de uma occurrence;
- Routine Layer obrigatória ainda cobre um conjunto estreito de obrigações;
- Reflection e OperationalQuiescence não possuem contratos/tooling correntes;
- Agent Bus possui envelopes de peer health/recovery, mas não um provider Gmail
  canônico integrado ao paved path;
- o valor operacional de dois Manager/GitOps writers em steady state ainda não
  foi qualificado;
- ProjectState apresentou staleness histórico antes e durante a transição para o
  regime begin/close; novas ocorrências pós-AT2 devem ser observadas antes de
  criar auto-reconciliation.

## 6. Freshness deste roadmap

Regra imediata:

- qualquer PR que altere `ProjectState.development.checkpoint` ou
  `nextTransition` deve revisar afirmações de estado corrente neste roadmap e
  nos ponteiros `*-current.md` afetados;
- a revisão pode concluir `NO_CHANGE`, mas precisa ser explícita no PR;
- baseline histórico deve ser rotulado como entrada da reconciliação, nunca
  como substituto do head corrente.

O `RoadmapFreshnessGuard` continua sendo uma inspection read-only. Ele prova
coverage da revisão quando ProjectState muda; não infere sozinho que uma
transição omitida deveria ter acontecido.

Estado esperado desta reconciliação:

```text
ROADMAP_FRESHNESS_GUARD = IMPLEMENTED
CURRENT_COVERAGE = PASS
```

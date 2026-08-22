# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-22
Repositório observado: `EAKerber/MobiliPresenter`  
Entrada desta reconciliação: `main@b31d78ac077651e50e5b7581b6d7b9db1a57d5ae`

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
| M9 | Technical Dictionary, Semantic Scope, Determinism Contract e Roadmap Freshness Guard | fechado por M9-SF1 + M9-FG1; contratos e coverage read-only integrados |
| M10 | `OperationalSemantics 0.3` + Agent Cycle semântico | fechado por OS1A + OS1B + OS1C; inventário/coverage, AgentSemanticBrief, freshness, Agent Cycle Entry e Agent Cycle Close/receipt integrados |
| M11 | convergência de `lock`, aliases, triggers e resíduos | CV1A fechado: `ConvergenceInspection 0.1` integrada; `lock` e `ops` possuem coverage PASS e continuam `MIGRATION_REQUIRED`; CV1B é o próximo recorte |
| M12 | remote canonical execution e maturity proof | S1 terminou `CLOSED_DEFERRED`; bridge e novo proof estão planejados, não aprovados |
| M13 | Reflection + OperationalQuiescence | planejado como read-only; bloqueado pelo fechamento M11–M12 |
| M14–M16 | Hypothesis, Experiment/Deathcycle, capability e prova longa | bloqueados |

M12-S1 não é mais o próximo estágio. Ele terminou com:

- seis runs elegíveis;
- `providerGapRate=1.0`;
- `pavedPathCompletionRate=0.0`;
- zero falso PASS, mutação em `main` ou escape de escopo;
- disposition `DEFERRED`, retry `ON_CONTRACT_CHANGE`;
- tasks desabilitadas e branches coletadas com cleanup readback `PASS`.

O protocolo futuro já corrige dois pontos de S1, mas não está admitido:

- branches por role, não por worker;
- preferência verificável por ChatGPT web standalone fora de Work, falhando
  fechado quando o contexto não puder ser selecionado ou observado.

Essas correções vivem em
`docs/experiments/scheduled-cycle-maturity-next-protocol-v0.1.md`. Não existe
S2 ativo, task ativa ou branch experimental reservada.

## 3. Resultado dos recortes de planejamento

O plano coordenado de metadata de apresentação foi aceito sem implementar
produto. A issue #22 foi separada logicamente em metadata de módulos (`PCS-01`)
e escolhas/acessórios configuráveis (`PCS-02`).

Estado materializado após o fechamento de M11-CV1A:

```text
checkpoint = M11-CV1A-CONVERGENCE-COVERAGE-0.1-CLOSED
phase = between-increments
nextTransition = implement-m11-cv1b-canonical-coordination-surface-v0.1
```

O plano PCS-01A continua recuperável e sua implementação permanece não admitida.
O plano M9–M13 define slices, gates, checkpoints e blockers em
`docs/plans/m9-m13-closure-v0.1.md`.

M10 materializou:

- `OperationalSemantics 0.3` com inventário/coverage integral;
- `AgentSemanticBrief 0.1` como projeção contextual read-only;
- `CapabilityRelevanceProjection 0.1` baseada em facetas tipadas, role,
  intenção, fase, scope e capabilities observadas;
- `CAPABILITY_DISCOVERY_FRESHNESS_GUARD`, distinguindo `STALE` de `TAMPERED`;
- `AgentCycleContext 0.1` e a entrada única `python3 tools/agent.py begin`;
- `CLOSE_REQUIRED_AFTER_WORK` como obrigação explícita sem criar nova authority;
- `agent close`, `AgentCycleDelta 0.1`, aggregate readback,
  `AgentCycleReceipt 0.1` e `AgentCycleClosure 0.1`;
- durable delta sem evidência atribuível como `UNKNOWN`, nunca falso `PASS`;
- compatibilidade com contexts OS1B e baseline ligado aos artifacts embutidos;
- `EcosystemMaxim` limitado e não autoritativo dentro do brief.

M11-CV1A materializou:

- `ConvergenceInspection 0.1` read-only sobre tracked repository consumers e
  evidência runtime reutilizada de `GitPrunePlan 0.4`;
- separação explícita entre `coverageStatus` e `retirementReadiness`;
- coverage completa para `lock` e `ops`, ambos ainda `MIGRATION_REQUIRED`;
- distinção entre o branch trigger legacy `ops/**` e o path filter canônico
  `ops/**`;
- remoção de direção mutável duplicada do ponteiro `ui-ux-current.md`;
- inventário explícito de triggers legacy adjacentes sem aposentadoria automática.

## 4. Próxima sequência deliberada

M9-SF1/M9-FG1, M10-OS1A/OS1B/OS1C e M11-CV1A estão fechados. A sequência restante é:

1. M11-CV1B migra `tools/lock.py` para uma superfície Coordination canônica,
   preservando compatibilidade até prova de equivalência.
2. M11-CV1C reexecuta a coverage e aposenta `lock`/`ops` e triggers somente
   quando `retirementReadiness=READY`.
3. M12-RP1 implementa e qualifica manualmente a ponte remota canônica.
4. M12-S2 repete o maturity proof somente depois dessa qualificação.
5. M13-RQ1/RQ2 implementa ReflectionEligibility e OperationalQuiescence em modo
   read-only.
6. Só então PCS-01B pode ser reavaliado para admissão.

Não se deve repetir S1/S2 apenas para produzir atividade. O retry exige mudança
de contrato e uma qualificação manual branch-confined com planner e readback
canônicos.

## 5. Lacunas conhecidas cobertas pelo plano M9–M13

- registry 0.3, descriptors tipados, catálogo versionado de
  `EcosystemMaxim` e coverage integral foram fechados em M10-OS1A;
- `AgentSemanticBrief`, `CapabilityRelevanceProjection`, seleção contextual,
  freshness e entrada única do ciclo foram fechados em M10-OS1B;
- `agent close`, `AgentCycleDelta`, aggregate readback e `AgentCycleReceipt`
  foram fechados em M10-OS1C sem criar nova authority ou writer;
- M11-CV1A fechou o inventário/coverage de convergência; `tools/lock.py`,
  o alias `lock`, o alias `ops` e o branch trigger `ops/**` continuam vivos por
  evidência explícita de migração pendente;
- triggers legacy adjacentes `renderer/**` e `architecture/**` permanecem
  classificados para decisão posterior, sem compartilhar automaticamente a
  death condition de `ops/**`;
- Routine Layer obrigatória cobre somente `capability-deathcircle`;
- Reflection e OperationalQuiescence não possuem contratos/tooling correntes;
- o runtime de Scheduled Tasks observado em S1 não executou o planner canônico;
- lifecycle/deathcycle persistível do experimento ainda não foi provado;
- execution context normal versus Work não é provider-verified na superfície
  observada.

Uma lacuna de provider e uma lacuna de implementação interna podem coexistir.
M12-RP1 fecha a parte interna: contract, planner, validator, executor e readback
pertencem ao repositório; provider/carrier apenas expõe o caminho e não ganha
authority semântica.

## 6. Freshness deste roadmap

Este arquivo já ficou defasado depois de S1, repetindo um padrão anterior de
documentação narrativa que continuava anunciando o recorte recém-concluído como
“próximo”. M9-FG1 fecha a causa estrutural conhecida para checkpoint e direção.

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

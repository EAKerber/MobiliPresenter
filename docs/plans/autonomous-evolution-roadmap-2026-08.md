# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-21  
Repositório observado: `EAKerber/MobiliPresenter`  
Entrada desta reconciliação: `main@221d41b260250db5ed7f1072009c73346af75afd`

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

| Faixa | Objetivo revisado | Estado reconciliado em 2026-08-21 |
|---|---|---|
| M0–M8 original | Project Machine, authorities e writers básicos | fundação substancialmente presente; não recertificada aqui |
| M9 | Technical Dictionary, Semantic Scope e Determinism Contract | plano de fechamento aceito; implementação é a próxima transição |
| M10 | `OperationalSemantics 0.3` e cobertura integral | planejado; registry corrente permanece 0.2 |
| M11 | convergência de `lock`, aliases, triggers e resíduos | planejado; implementação não iniciada |
| M12 | remote canonical execution e maturity proof | S1 terminou `CLOSED_DEFERRED`; bridge e novo proof estão planejados, não aprovados |
| M13 | Reflection + OperationalQuiescence | planejado como read-only; bloqueado pelo fechamento M9–M12 |
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

Estado materializado pela mesma transição que integra esta reconciliação:

```text
checkpoint = M9-M13-CLOSURE-PLAN-0.1-ACCEPTED
phase = between-increments
nextTransition = implement-m9-semantic-foundations-v0.1
```

O plano PCS-01A continua recuperável e sua implementação permanece não admitida.
O plano M9–M13 agora define slices, gates, checkpoints e blockers em
`docs/plans/m9-m13-closure-v0.1.md`.

Ele incorpora ao Semantic Scope:

- `AgentSemanticBrief` como projeção contextual read-only;
- `CapabilityRelevanceProjection` baseada em facetas tipadas, role, intenção,
  fase, scope e capabilities observadas;
- `EcosystemMaxim` como lembrete cultural explicitamente não autoritativo;
- `CAPABILITY_DISCOVERY_FRESHNESS_GUARD`;
- `ROADMAP_FRESHNESS_GUARD` como implementação obrigatória de M9, e não apenas
  dívida narrativa.

## 4. Próxima sequência deliberada

O plano foi concluído. A sequência de implementação é:

1. M9-SF1 fecha Technical Dictionary, Semantic Scope e Determinism Contract.
2. M9-FG1 implementa coverage determinística para roadmap e ponteiros correntes.
3. M10-OS1 promove OperationalSemantics para 0.3 e implementa o
   `AgentSemanticBrief` sem criar authority.
4. M11-CV1 converge `lock`, aliases, triggers e resíduos com coverage de
   consumidores.
5. M12-RP1 implementa e qualifica manualmente a ponte remota canônica.
6. M12-S2 repete o maturity proof somente depois dessa qualificação.
7. M13-RQ1/RQ2 implementa ReflectionEligibility e OperationalQuiescence em modo
   read-only.
8. Só então PCS-01B pode ser reavaliado para admissão.

Não se deve repetir S1/S2 apenas para produzir atividade. O retry exige mudança
de contrato e uma qualificação manual branch-confined com planner e readback
canônicos.

## 5. Lacunas conhecidas cobertas pelo plano M9–M13

- registry ainda em `OperationalSemantics 0.2`;
- não existe ainda `AgentSemanticBrief`, projeção contextual de capabilities ou
  catálogo semântico de máximas não autoritativas;
- cobertura semântica, `CAPABILITY_DISCOVERY_FRESHNESS_GUARD` e
  `ROADMAP_FRESHNESS_GUARD` ainda não estão implementados;
- `tools/lock.py` ainda não convergiu para alias fino da Coordination canônica;
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
“próximo”. A correção aqui é factual, mas ainda não elimina a causa estrutural.

Regra imediata:

- qualquer PR que altere `ProjectState.development.checkpoint` ou
  `nextTransition` deve revisar afirmações de estado corrente neste roadmap e
  nos ponteiros `*-current.md` afetados;
- a revisão pode concluir `NO_CHANGE`, mas precisa ser explícita no PR;
- baseline histórico deve ser rotulado como entrada da reconciliação, nunca
  como substituto do head corrente.

Estado do débito depois da aceitação do plano:

```text
ROADMAP_FRESHNESS_GUARD = PLANNED_NOT_IMPLEMENTED
```

M9-FG1 transforma a revisão recorrente em coverage determinística. Até esse gate
passar, este roadmap continua honestamente classificado como derivado e pode
apresentar drift sem corromper authority.

<!-- Preserved planning source; not an operational authority. -->

# MobiliPresenter — Autonomous Evolution Architecture
## Reflection, Quiescence, Hypothesis Lifecycle, Experiment Lifecycle, Deathcycle e Deterministic Evolution Tooling

**Versão:** 0.1  
**Data:** 2026-08-19  
**Status:** Architectural planning / continuity document  
**Escopo:** MobiliPresenter — evolução futura do ecossistema de agentes, scheduled tasks, Manager/GitOps, Semantic Map e lifecycle experimental  
**Repositório de referência:** `EAKerber/MobiliPresenter`

---

# 1. Propósito

Este documento formaliza a direção arquitetural discutida para a próxima fase de maturidade do ecossistema MobiliPresenter.

O sistema atual já caminhou significativamente na direção de:

- uma única authority por fato mutável;
- writers canônicos;
- observação estruturada;
- `observe -> plan -> validate -> apply -> readback`;
- ProjectState reduzido;
- Work/continuations estruturado;
- Coordination Leases;
- Branch Hygiene;
- Capability Lifecycle;
- Peer Recovery;
- ProjectMachine;
- Maintenance;
- Scheduler;
- Semantic Registry;
- cold archive;
- lifecycle de branches;
- fail-closed;
- gates e evidence;
- redução de estado narrativo ou implícito.

A próxima preocupação passa a ser diferente:

> **O que um ecossistema operacional maduro deve fazer quando não há trabalho urgente, há pouca manutenção ou o sistema está efetivamente estável?**

O objetivo não é criar um agente que “faça qualquer coisa sozinho”.

O objetivo é preparar o ecossistema para que ele possa:

1. perceber oportunidades;
2. refletir sobre melhorias;
3. estruturar hipóteses;
4. deduplicar conhecimento;
5. selecionar raramente hipóteses fortes;
6. executar experimentos limitados;
7. avaliar resultados;
8. matar experimentos ruins;
9. preservar conhecimento negativo;
10. promover resultados positivos;
11. limpar seus próprios resíduos;
12. respeitar boundaries semânticos;
13. não desfazer o amadurecimento já obtido;
14. saber conscientemente quando **não fazer nada**.

A autonomia desejada é portanto:

> **autonomia disciplinada de aprendizagem e evolução**, não autonomia irrestrita de mutação.

---

# 2. Princípio central

A arquitetura deve obedecer à seguinte regra:

> **Nondeterminism may propose; only deterministic policy may authorize.**

Em português:

> **A heurística pode propor uma hipótese ou interpretação; nenhuma mutação, admissão, promoção, ampliação de escopo ou extensão de lifecycle pode depender apenas dessa heurística.**

Outro princípio:

> **Same normalized state + same policy version -> same lifecycle decision.**

Isso não significa que dois agentes devem gerar a mesma ideia.

Significa que, dada:

- a mesma hipótese já estruturada;
- os mesmos authority heads;
- o mesmo estado normalizado;
- a mesma versão da policy;

dois agentes não devem divergir sobre:

- se a hipótese pode ser persistida;
- se existe slot;
- se pode virar experimento;
- se está fora de escopo;
- se o budget acabou;
- se o experimento deve morrer;
- se uma promoção é admissível.

A criatividade pode ser probabilística.

A governança não.

---

# 3. Mudança de foco do roadmap

A direção revisada para os marcos abertos é:

| Marco | Objetivo |
|---|---|
| M9 | Technical Dictionary + Semantic Scope Contract + Determinism Contract |
| M10 | OperationalSemantics 0.3 + cobertura semântica completa |
| M11 | Convergência: `lock` -> Coordination canônico + aliases/triggers/resíduos |
| M12 | Maturity Proof com desenvolvimento funcional real |
| M13 | Reflection + Quiescence |
| M14-A | Hypothesis Lifecycle |
| M14-B | Experiment Lifecycle + Deathcycle |
| M15 | Autonomous Evolution capability: shadow -> bounded active |
| M16 | Long-run Autonomous Evolution Proof |

A ordem é deliberada.

Não se deve implementar autonomia experimental antes de:

- estabilizar o dicionário técnico;
- estabilizar o Semantic Map;
- concluir a migração de `lock`;
- provar o sistema sob carga funcional normal;
- tornar explícitas as fronteiras de determinismo.

---

# 4. Separar pensar de agir

Uma das decisões mais importantes é:

> **quiescência plena não deve ser requisito para pensar; deve ser requisito para agir autonomamente em níveis mais altos.**

Uma implementação ingênua poderia exigir que todas as condições de quiescência fossem verdadeiras antes de permitir qualquer exploração.

Isso seria excessivamente restritivo.

Exemplos de situações que não deveriam impedir reflexão:

- Work existe, mas está `WAITING`;
- CI está pending;
- existe uma dependência externa;
- há uma capability aguardando evidência;
- existe `nextTransition`, mas nenhum ato útil cabe àquele worker naquele instante;
- a execução atual é curta;
- uma authority auxiliar está temporariamente indisponível, sem comprometer o contexto mínimo de reflexão;
- o sistema está saudável, mas ainda não “quieto” o suficiente para executar experimentos.

Portanto, a arquitetura deve separar níveis:

```text
Observation
    ↓
Reflection
    ↓
Hypothesis Candidate
    ↓
Triaged/Persisted Hypothesis
    ↓
Experiment Proposal
    ↓
Experiment Admission
    ↓
Execution
    ↓
Evaluation
    ↓
Promotion or Deathcycle
```

Cada nível aumenta:

- custo;
- persistência;
- exigência de evidência;
- poder de mutação;
- necessidade de gates;
- necessidade de determinismo.

---

# 5. ReflectionEligible

Deve existir um conceito futuro de `ReflectionEligible`.

Ele representa:

> “o worker terminou ou não possui ação operacional prioritária útil nesta rodada e pode empregar orçamento residual em reflexão sem interferir com trabalho obrigatório”.

Isso é diferente de `OperationalQuiescence`.

Exemplos:

```text
CI_PENDING
→ reflectionEligible = true
→ experimentAdmissionEligible = false
```

```text
WORK_WAITING
→ reflectionEligible = true
→ experimentAdmissionEligible = false
```

```text
PROJECT_MACHINE_UNKNOWN
→ reflectionEligible = false ou severamente restrito
→ experimentAdmissionEligible = false
```

O ponto é:

> **um fator pode bloquear ação sem bloquear pensamento.**

---

# 6. Reflection não deve criar Work, branch ou PR

Uma rodada de reflexão deve ser barata.

Seu produto inicial deve ser somente read-only.

Exemplo conceitual:

```text
EvolutionObservation
    ↓
HypothesisCandidate
```

Um `HypothesisCandidate` pode conter:

- `problemStatement`;
- `hypothesis`;
- `semanticOwner`;
- `evidenceRefs`;
- `uncertainties`;
- `expectedValue`;
- `falsifier`;
- `nextEvidence`;
- `proposedExperimentClass`;
- `riskEstimate`;
- `costEstimate`.

Mas não ganha automaticamente:

- branch;
- PR;
- lease;
- Work;
- Capability;
- authority;
- direito de mutação.

A maior parte das ideias deve poder morrer dentro da própria rodada.

---

# 7. Persistir somente hipóteses triadas

Não se deseja um “caderno infinito de pensamentos”.

A maior parte de `HypothesisCandidate` deve ser efêmera.

A primeira forma persistida pode ser `TRIAGED`.

Uma hipótese só deve ocupar capacidade durável se tiver, no mínimo:

- problema claramente identificado;
- hipótese explícita;
- falsificador;
- owner semântico;
- evidência de origem;
- benefício esperado;
- incertezas;
- próximo tipo de evidência desejável;
- fingerprint estável.

Assim:

> **o repositório persiste hipóteses estruturadas, não brainstorming.**

---

# 8. Funil de evolução

A arquitetura proposta pode ser entendida como um funil:

```text
muitas observações
    ↓
poucos candidates
    ↓
até N hipóteses persistidas
    ↓
pouquíssimas experiment proposals
    ↓
1 experimento ativo
    ↓
0 ou 1 promoção
```

A ideia inicial é barata.

A ação é cara.

O sistema deve ser intelectualmente ativo, mas operacionalmente conservador.

---

# 9. Limites de capacidade

Hipóteses e experimentos devem possuir limites explícitos.

Valores iniciais sugeridos para prova do mecanismo:

| Recurso | Limite inicial sugerido |
|---|---:|
| Hypothesis candidates efêmeras por rodada | 3 |
| Hipóteses persistidas `ACTIVE` | 5 |
| Hipóteses da mesma fingerprint family | 2 |
| Hypothesis -> experiment proposals simultâneas | 2 |
| Experimentos `ACTIVE` globais | 1 |
| Experimento ativo por domínio | 1 |
| Extensão extraordinária de experimento | 1 |
| Experimento autônomo constitucional | 0 |

Esses números não devem necessariamente ser eternos.

Mas a policy deve existir e o enforcement deve ser mecânico.

Não se deve depender apenas de prompts dizendo:

> “não crie muitos experimentos”.

O tooling futuro deve rejeitar mecanicamente:

```text
HYPOTHESIS_ACTIVE_LIMIT_REACHED
EXPERIMENT_PROPOSAL_LIMIT_REACHED
EXPERIMENT_ACTIVE_LIMIT_REACHED
```

Ao atingir o limite, a ação disponível deve favorecer:

- REVIEW;
- RETIRE;
- MERGE_CANDIDATE;
- EVALUATE;
- DEATHCYCLE;

e não CREATE.

Isso força convergência.

---

# 10. Hypothesis Lifecycle

Um lifecycle possível:

```text
CANDIDATE
    ↓
TRIAGED
    ↓
ACTIVE
    ↓
EXPERIMENT_PROPOSED
```

Estados terminais possíveis:

```text
REJECTED
ABSORBED
SUPERSEDED
STALE
EXPERIMENTED
```

O detalhe importante é que hipótese também precisa morrer.

Sem isso, um limite de 5 hipóteses apenas se transforma em 5 hipóteses imortais.

---

# 11. Hypothesis Deathcycle

Uma hipótese deve liberar seu slot quando:

- evidência a contradiz;
- outra hipótese a absorve;
- já existe mecanismo equivalente;
- semantic owner rejeita a direção;
- seu problema desaparece;
- fica continuamente abaixo de outras hipóteses;
- não recebe nova evidência após número suficiente de reviews elegíveis;
- vira experimento;
- é superseded;
- se torna constitucionalmente inadmissível.

O encerramento deve preservar suficiente informação para evitar redescoberta ingênua.

---

# 12. Não envelhecer por cron

Scheduled Task run não deve ser unidade de aging.

Não se deve usar:

```text
cron fired
→ hypothesis age++
```

Uma execução curta ou bloqueada não deve envelhecer conhecimento.

Deve existir o conceito futuro:

`HypothesisReviewOpportunity`.

Uma hipótese só envelhece se houve oportunidade real de review.

Por exemplo:

```text
required evidence observable
+
reflection budget sufficient
+
relevant context available
=
eligible review opportunity
```

Então:

```text
reviewCount += 1
```

Somente uma review elegível conta.

Isso é muito mais robusto do que:

- número bruto de tasks;
- tempo de parede;
- número de execuções incompletas.

---

# 13. OperationalQuiescence

`OperationalQuiescence` deve continuar sendo um conceito forte.

Ele não significa:

- lista de Work vazia;
- PAUSE;
- DONE;
- ausência de ação aparente;
- falta de observação;
- erro;
- CI pending.

Ele significa:

> **o sistema foi observado suficientemente bem, está coerente e não existe transição obrigatória conhecida que deva ter precedência.**

Condições possíveis:

- ProjectMachine trust = PASS;
- ProjectMachine coherence = PASS;
- nenhum Work runnable;
- nenhum handoff;
- nenhuma ação operacional local pendente;
- nenhum reconcile obrigatório;
- nenhuma CI quebrada exigindo intervenção;
- nenhuma Coordination inconsistente;
- nenhuma capability experimental com gates obrigatórios;
- nenhuma próxima transição obrigatória conhecida.

`UNKNOWN` não equivale a quiescência.

---

# 14. Quiescence Window

Quiescência não deve depender de uma execução perfeita única.

Uma rodada curta ou um fator transitório não deve necessariamente zerar todo o histórico de estabilidade.

Por isso, a proposta evolui para `QuiescenceWindow`.

Exemplo de policy:

```text
3 qualifying observations
within last 6 eligible observations
with no invalidating event
between the first and the last qualifying observation
```

Um `FAIL`, drift real ou novo Work prioritário pode invalidar a janela.

Uma execução curta:

- não conta;
- não reseta automaticamente.

O resultado pode ser:

```text
QuiescenceWindowInspection
  status
  qualifyingObservationIds[]
  invalidatingObservationId
  ruleVersion
  windowHash
```

---

# 15. ExplorationEligible e ExperimentAdmissionEligible

Podem existir níveis progressivos:

```text
ReflectionEligible
    ⊃
ExplorationEligible
    ⊃
ExperimentAdmissionEligible
```

Interpretação:

## ReflectionEligible

Pode pensar e revisar hipóteses.

## ExplorationEligible

Pode estruturar/persistir hipótese, dependendo de slots e policy.

## ExperimentAdmissionEligible

Pode admitir experimento autônomo bounded.

A última deve ser significativamente mais restritiva.

---

# 16. Experiment Lifecycle

Experiment não é Work.

Experiment não é Capability.

Work representa execução.

Capability representa comportamento suportado do sistema.

Experiment representa:

> **uma hipótese em teste bounded para produzir aprendizado verificável.**

Possível lifecycle:

```text
PROPOSED
ADMITTED
ACTIVE
EVALUATING
PROMOTION_READY
DEFERRED
REJECTED
EXPIRED
SUPERSEDED
PROMOTED
ARCHIVED
```

---

# 17. Distinção entre Experiment, Work e Capability

A separação conceitual deve ser explícita:

```text
Experiment = o que estamos tentando aprender?
WorkItem   = quem está executando o quê?
Capability = que comportamento passou a ser suportado?
```

Um Experiment pode gerar Work.

Um resultado de Experiment pode promover uma Capability.

Mas os três fatos não devem ser colapsados na mesma authority.

---

# 18. Experiment Deathcycle

Nenhum experimento deve chegar a `ADMITTED` sem Deathcycle definido.

Antes da execução, deve existir:

- objetivo;
- falsificador;
- scope;
- budget;
- owner;
- evidence requirements;
- death conditions;
- promotion target;
- reversibility;
- evaluator requirements.

Possíveis causas de morte:

- budget esgotado;
- hipótese falsificada;
- benefício não demonstrado;
- duplicidade;
- ausência prolongada de sinal;
- CI ou guard revela risco;
- scope escape;
- dependência de authority não autorizada;
- supersession;
- semantic owner rejeita;
- limite de deferrals atingido.

---

# 19. Deathcycle não é delete

Deathcycle deve seguir algo conceitualmente como:

```text
stop execution
    ↓
classify outcome
    ↓
persist evidence
    ↓
persist compact tombstone
    ↓
finish/cancel Work
    ↓
archive unique history if necessary
    ↓
release retention
    ↓
Branch Hygiene
```

A limpeza de branches continua pertencendo a Branch Hygiene.

Experiment tooling não deve ganhar delete genérico.

---

# 20. Tombstones e negative knowledge

Conhecimento negativo é crítico.

Se um experimento ruim simplesmente desaparecer, o sistema pode redescobrir a mesma “boa ideia” repetidamente.

Deve existir um tombstone pequeno.

Exemplo:

```text
HypothesisTombstone
  hypothesisKey
  hypothesisFingerprint
  outcome
  reasonCodes[]
  evidenceRefs[]
  terminalAt
  retryPolicy
```

`retryPolicy` pode ser algo como:

```text
NEVER
AFTER_DATE
ON_EVIDENCE_CHANGE
ON_CONTRACT_CHANGE
ON_SUPERSEDING_CAPABILITY_CHANGE
```

Para `ON_EVIDENCE_CHANGE`, o retry não deve depender de texto livre.

Deve existir mudança observável, por exemplo:

```text
previousRelevantStateHash != currentRelevantStateHash
```

---

# 21. Negative Knowledge Lookup

Antes de persistir uma ideia nova, o ecossistema deveria conceitualmente executar:

```text
THINK
  ↓
NORMALIZE
  ↓
LOOKUP
  ↓
NEW
| ACTIVE_MATCH
| TERMINAL_MATCH
| PROMOTED_MATCH
```

O lookup procura:

1. hipótese ativa;
2. experimento ativo;
3. tombstones;
4. capability/work promovido;
5. conceito que supersede a hipótese.

Somente `NEW` pode consumir slot novo.

---

# 22. Reflection pode atravessar domínios; Experiment não

Manager/GitOps pode descobrir uma oportunidade em outro domínio.

Exemplo:

> “A arquitetura UI parece conter uma oportunidade de simplificação.”

Ele pode estruturar uma hipótese:

```text
semanticOwner=ui
```

Mas não deve automaticamente iniciar um experimento de UI.

O caminho é:

```text
Observation
  ↓
Hypothesis
  ↓
semanticOwner = ui
  ↓
proposal / handoff
```

Já uma hipótese operations-owned pode continuar pelo pipeline autônomo bounded.

Isso permite:

> **curiosidade ampla + ação estreita.**

---

# 23. Autonomy Classes

A arquitetura deve classificar autonomia.

Possível baseline:

| Classe | Permissão |
|---|---|
| A0 — Observe | inspeções, métricas, discovery |
| A1 — Explore | hipótese, simulação, testes read-only |
| A2 — Isolated Experiment | branch experimental e mudança bounded |
| A3 — Bounded Promotion | promoção automática low-risk sob gates fortes |
| A4 — Constitutional Change | nunca auto-promovido |

A4 não significa “proibido experimentar”.

Significa que o experimento pode:

- gerar evidência;
- criar PR;
- sugerir alteração.

Mas a promoção final exige autoridade externa apropriada.

---

# 24. Constitutional Surfaces

Algumas superfícies governam a própria governança.

Elas devem ser classificadas como constitucionais.

Exemplos:

- `AGENTS.md`;
- identidade/location de managed authorities;
- single canonical writer rule;
- Semantic Registry fundamental;
- schema fundamental do Semantic Map;
- Scheduler action vocabulary;
- ProjectState lifecycle schema;
- Experiment/Evolution Policy;
- Branch Hygiene destructive policy;
- role authority boundaries;
- fail-closed rules;
- task-control permissions;
- auto-promotion limits;
- Evolution Budget;
- regras de self-amendment.

Princípio:

> **No self-amendment.**

Um experimento não pode, no mesmo change-set, relaxar a policy que permite sua própria promoção.

Outro:

> **No guard removal as evidence.**

Remover ou enfraquecer um teste/guard que bloqueia o experimento não conta como fazer o experimento passar, salvo substituição funcionalmente equivalente provada de forma independente.

---

# 25. Evolution Budget

Deve existir uma policy estável.

Possível `AutonomousEvolutionPolicy 0.1`.

Parâmetros iniciais:

```text
maxActiveHypotheses
maxExperimentProposals
maxActiveExperiments
maxExperimentBranches
maxEligibleRuns
maxExtensions
autoPromotionClasses
constitutionalAutoPromotion = false
```

O agente não deve poder ampliar autonomamente o próprio budget.

---

# 26. Deterministic Evolution Tooling

Não é necessário implementar todos os tools agora.

Mas é prudente arquitetar **pontos de determinismo desejado**.

A regra é:

> **não tornar a geração de ideias determinística; tornar determinísticos os envelopes, critérios, transições e efeitos em torno delas.**

---

# 27. Onde determinismo é obrigatório

| Fronteira | Determinismo |
|---|---|
| geração livre de observações | não |
| formulação inicial de hipótese | não integralmente |
| normalização | sim |
| fingerprint | sim |
| deduplicação exata | sim |
| near-duplicate semântico | advisory |
| Reflection eligibility | sim |
| Quiescence Window | sim |
| review opportunity | sim |
| limits | sim |
| admission | sim |
| ranking | sim |
| tie-break | sim |
| experiment scope | sim |
| budget consumption | sim |
| evidence normalization | sim |
| promotion gate | sim |
| deathcycle | sim |
| cleanup disposition | sim |

---

# 28. Observation Bundle

Reflection não deve receber “o repositório atual” informalmente.

Deve receber um bundle normalizado.

Possível estrutura:

```text
EvolutionObservationBundle
  projectMachineInspectionHash
  authorityHeads
  workGraphHash
  capabilityStateHashes
  semanticRegistryHash
  relevantCiEvidence
  priorHypothesisStateHash
  priorExperimentStateHash
  observationTime
```

Objetivos:

- fechar inputs;
- permitir reprodução;
- impedir mistura silenciosa de estados;
- identificar contra qual mundo a hipótese foi derivada.

---

# 29. ReflectionEligibilityInspection

Deve ser função pura.

Entrada:

- ProjectMachineInspection;
- WorkGraph;
- MaintenanceInspection;
- hypothesis count;
- experiment count;
- optional runtime evidence.

Saída possível:

```text
ReflectionEligibilityInspection
  eligible
  reasonCodes[]
  evidenceCompleteness
  blocksReflection
  blocksExperiment
  inspectionHash
```

---

# 30. Hypothesis normalization

A identidade da hipótese não deve depender do texto completo.

Texto livre pode variar:

> “talvez possamos simplificar a CI”

versus

> “o pipeline de CI talvez contenha redundância”.

Não é razoável exigir fingerprint textual estável.

Deve existir uma `HypothesisKey` estruturada.

Exemplo:

```text
semanticOwner: operations
subject: semantic-topology
mechanism: entrypoint-coverage
expectedEffect: completeness
falsifierClass: no-unmapped-live-entrypoints
```

Então:

```text
hypothesisFingerprint = stable_hash(HypothesisKey)
```

Title e rationale podem variar.

A identidade conceitual permanece estável.

---

# 31. Exact duplicate vs near duplicate

Exact duplicate:

- regra determinística;
- pode bloquear nova persistência.

Near duplicate:

- comparação heurística;
- produz Recommendation.

Exemplo:

```text
MERGE_CANDIDATES
```

Mas não deve autoapagar uma hipótese apenas porque similaridade textual ou embedding ficou alto.

Heurística aconselha.

Policy determinística decide.

---

# 32. Admission sem score mágico

Evitar:

```text
score = value*0.37 + novelty*0.21 + ...
```

Isso produz falsa precisão.

Preferir classes discretas:

```text
risk:
  LOW
  MEDIUM
  HIGH
  CONSTITUTIONAL

evidence:
  WEAK
  PARTIAL
  STRONG

cost:
  TRIVIAL
  SMALL
  MEDIUM
  LARGE

reversibility:
  FULL
  COMPENSATABLE
  LOW

ownerFit:
  OWNED
  HANDOFF_REQUIRED
  UNKNOWN
```

Admission pode usar policy explícita sobre combinações.

---

# 33. Ranking determinístico

Quando várias hipóteses são elegíveis:

```text
1. existing lifecycle obligation
2. stronger evidence
3. lower risk
4. lower cost
5. greater reversibility
6. older eligible hypothesis
7. lexical hypothesisId
```

Todo ranking deve ter tie-break total.

Nunca:

> “escolha qualquer uma”.

---

# 34. Quiescence evaluator sem relógio implícito

Planner puro não deve chamar “agora” silenciosamente.

Se tempo importa, ele é input.

Entrada:

```text
Observation O1
Observation O2
Observation O3
...
```

ordenadas por fonte confiável.

Saída:

```text
QuiescenceWindowInspection
  status
  qualifyingObservationIds[]
  invalidatingObservationId
  ruleVersion
  windowHash
```

---

# 35. Hypothesis Transition Plan

Mudanças persistentes de hipótese devem ser transacionais.

Ações possíveis:

```text
TRIAGE
ACTIVATE
DEFER
REJECT
ABSORB
SUPERSEDE
PROPOSE_EXPERIMENT
```

Deve existir uma estrutura compatível com:

```text
beforeStateHash
action
hypothesisId
candidate
reasonCodes
evidenceRefs
afterStateHash
planHash
```

Sempre que possível, reutilizar o `TransitionPlan` genérico em vez de criar outro protocolo paralelo.

---

# 36. Limits são tooling, não prompt

Uma regra como:

```text
maxActiveHypotheses=5
```

deve ser validada por planner/executor.

Não é recomendação ao modelo.

É policy executável.

O mesmo vale para:

- proposals;
- active experiments;
- branches;
- PRs;
- mutable files;
- eligible runs;
- extensions.

---

# 37. Experiment Admission Plan

Uma hipótese não cria branch diretamente.

Antes, deve existir:

```text
ExperimentAdmissionPlan
```

Possíveis campos:

```text
hypothesisId
semanticOwner
autonomyClass
objective
falsifier
baseline
expectedEvidence
allowedScope
forbiddenScope
budget
deathConditions
reversibility
promotionTarget
requiredEvaluatorClass
```

---

# 38. Experiment Budget estruturado

Exemplo:

```text
maxEligibleRuns
maxBranches
maxPRs
maxMutableFiles
allowedPathPatterns
forbiddenPathPatterns
mayChangeSchema
mayChangeAuthority
mayChangePolicy
```

Para experimento autônomo low-risk:

```text
mayChangeSchema=false
mayChangeAuthority=false
mayChangePolicy=false
```

---

# 39. Não criar writer experimental genérico

Experiment Lifecycle pode ter writer canônico para o **estado do experimento**.

Mas não deve existir um “god-mode experiment executor”.

As mutações reais continuam usando o paved path existente.

Correto:

```text
Experiment Orchestrator
    ↓
plans existing domain operation
    ↓
canonical domain writer
```

Incorreto:

```text
Experiment Orchestrator
    ↓
generic unrestricted writer
```

---

# 40. Experiment Scope Inspection

Antes/depois de execução:

```text
ExperimentScopeInspection
```

Compara:

- files alterados;
- authorities tocadas;
- schemas tocados;
- workflows tocados;
- refs tocadas;

contra o `allowedScope`.

Se escapar:

```text
EXPERIMENT_SCOPE_ESCAPED
```

O experimento não pode ser promovido.

---

# 41. Separar evidence de evaluation

Devem existir dois níveis.

## ExperimentEvidenceInspection

Determinístico:

```text
baselineHash
candidateHead
ciResults
testResultHashes
metricBefore
metricAfter
scopeCompliance
budgetConsumption
falsifierTriggered
constitutionalSurfaceTouched
```

## ExperimentEvaluation

Pode conter julgamento:

```text
SUPPORTED
FALSIFIED
INCONCLUSIVE
VALUE_NOT_DEMONSTRATED
```

A evidência sobre a qual o evaluator raciocina permanece fechada e hashed.

Isso permite independent evaluation sobre o mesmo input.

---

# 42. Independent evaluation

Em classes apropriadas:

```text
proposal.workerId != evaluation.workerId
```

e ambos devem observar heads compatíveis.

Uma avaliação só é “independente” se não for apenas outro texto sobre outro estado.

Pode existir uma regra como:

```text
evaluation.observedHeads == experiment.expectedEvaluationHeads
```

ou reconciliação explícita.

---

# 43. Deathcycle Planner

O encerramento não deve depender de improvisação.

Um futuro:

```text
ExperimentDeathInspection
```

pode retornar exatamente uma:

```text
CONTINUE
EVALUATE
REJECT
EXPIRE
SUPERSEDE
PROMOTION_REVIEW
NEEDS_HUMAN
```

Depois:

```text
ExperimentTerminationPlan
```

define:

- terminal state;
- Work a encerrar;
- evidence a preservar;
- tombstone;
- branch retention;
- release eligibility;
- Branch Hygiene handoff.

---

# 44. Budget Consumption

Budget deve ter consumo observável.

Se:

```text
maxEligibleRuns=4
```

cada run elegível tem `runId`.

Se:

```text
maxPRs=1
```

o sistema conta PRs vinculadas.

Se:

```text
maxMutableFiles=8
```

ScopeInspection conta files concretos.

Então:

```text
declared budget
+
observed consumption
=
remaining budget
```

---

# 45. Prioridade global

Não deve existir um segundo Scheduler concorrente.

A camada de Evolution produz findings/recommendations para o pipeline canônico.

Prioridade conceitual:

```text
1. integrity / reconcile
2. mandatory Work
3. handoff
4. active experiment requiring closure
5. active hypothesis requiring lifecycle decision
6. declared development nextTransition
7. reflection
8. new hypothesis admission
9. new experiment admission
10. no-op
```

A ordem pode mudar futuramente.

O importante é que seja policy explícita.

---

# 46. No-op determinístico

“Não fiz nada” deve ser uma decisão auditável.

Exemplos:

```text
NO_ACTIONABLE_HYPOTHESIS
HYPOTHESIS_CAPACITY_FULL
EXPERIMENT_CAPACITY_FULL
EXPERIMENT_ADMISSION_DEFERRED
NO_NEW_EVIDENCE
QUIESCENCE_NOT_PROVEN
```

Um no-op saudável pode ser sucesso.

---

# 47. Scheduled Task loop futuro

Fluxo conceitual:

```text
1. Observe authorities.
2. Se incoerente -> RECONCILE.
3. Se Work runnable -> execute/route.
4. Se handoff -> handoff.
5. Se maintenance/capability review due -> maintenance.
6. Se nextTransition obrigatório -> desenvolvimento normal.
7. Se experimento ativo precisa avaliação -> avalie.
8. Se experimento terminal precisa Deathcycle -> encerre.
9. Se há hipótese ativa needing review -> revise.
10. Se reflectionEligible -> reflita.
11. Se hypothesis slot disponível -> candidate/triage.
12. Se quiescence window insuficiente -> pare na hipótese.
13. Se experiment slot indisponível -> não crie outro.
14. Se experiment admission passa -> admitir um experimento bounded.
15. Caso contrário -> no-op saudável.
```

Regra estrutural:

> **Antes de criar hipótese nova, revisar hipótese existente tem prioridade.**

Outra:

> **Antes de iniciar experimento novo, encerrar/avaliar o existente tem prioridade.**

---

# 48. Dois workers como two-key system

Com duas instâncias Manager/GitOps:

- uma pode propor/operar;
- outra pode avaliar.

Para classes que permitam eventual promoção automática:

```text
proposerWorkerId != evaluatorWorkerId
```

e ambos devem verificar authority heads.

Isso complementa:

- CI;
- lifecycle gates;
- readback;
- semantic map;
- fail-closed.

---

# 49. Autonomous Evolution como Capability

Não se deve ativar autonomia plena diretamente.

Ela deve entrar pelo Capability Lifecycle.

Possível:

```text
capability: autonomous-evolution
policy: experimental
supervisorParticipation: isolated
```

Evolução por estágios:

## AE-0 — Shadow

Produz:

- ReflectionEligibility;
- QuiescenceInspection;
- EvolutionOpportunityInspection.

Sem persistência/mutação.

## AE-1 — Proposal

Pode produzir/persistir `PROPOSED` / `TRIAGED`.

Sem experimento.

## AE-2 — Bounded Experiment

Pode iniciar A1/A2 operations-owned.

Sem auto-promotion.

## AE-3 — Independent Evaluation

Segundo worker avalia.

Deathcycle automático provado.

## AE-4 — Low-risk Auto-promotion

Somente após longa prova.

Constitutional surfaces continuam fora do alcance.

---

# 50. Tooling futuro — papéis, não implementação imediata

A arquitetura deve prever, sem obrigar implementação imediata:

1. Observation normalizer;
2. Reflection eligibility evaluator;
3. Hypothesis normalizer/fingerprinter;
4. Hypothesis lookup/dedup;
5. Hypothesis lifecycle planner;
6. Quiescence evaluator;
7. Experiment admission planner;
8. Experiment scope validator;
9. Evidence normalizer;
10. Experiment evaluator;
11. Deathcycle planner;
12. Tombstone/retry evaluator;
13. Evolution coverage guard.

Writers mínimos:

- Hypothesis authority writer;
- Experiment authority writer.

Nenhum writer genérico de produto.

---

# 51. Relação com OperationalSemantics 0.3

M10 deve preparar o mapa semântico para representar os futuros componentes.

Possíveis semantic component roles:

```text
observer
planner
transformer
validator
guard
protocol
adapter
executor
```

Futuros componentes podem incluir:

```text
reflection-planner
hypothesis-normalizer
hypothesis-lifecycle-planner
quiescence-inspector
experiment-admission-planner
experiment-scope-guard
experiment-evaluator
experiment-death-planner
```

A coverage guard futura deve assegurar que tools operacionais relevantes estejam no mapa.

---

# 52. Relação com `lock`

A migração de `lock` continua prioritária antes da autonomia.

A intenção é:

```text
lock
→ legacy alias
→ coordination CLI canônica
→ zero lógica própria em lock
→ zero consumidores
→ alias removido
→ transitional tests aposentados
```

A autonomia futura deve nascer depois que o dicionário tiver convergido para:

```text
CoordinationLease
intent
acquire
renew
release
guard
exclusive-write
```

Não deve carregar linguagem `lock` para o novo lifecycle experimental.

---

# 53. Technical Dictionary — termos adicionais

Termos propostos:

## Canonical

- `ReflectionEligible`
- `OperationalQuiescence`
- `QuiescenceWindow`
- `EvolutionObservation`
- `EvolutionObservationBundle`
- `HypothesisCandidate`
- `Hypothesis`
- `HypothesisKey`
- `HypothesisFingerprint`
- `HypothesisReviewOpportunity`
- `Experiment`
- `ExperimentAdmissionPlan`
- `ExperimentEvidenceInspection`
- `ExperimentEvaluation`
- `ExperimentDeathInspection`
- `ExperimentTerminationPlan`
- `HypothesisTombstone`
- `AutonomyClass`
- `ConstitutionalSurface`
- `EvolutionBudget`
- `NegativeKnowledge`

## Evitar ambiguidade

- `task` sem qualificação;
- `idle` como sinônimo de quiescence;
- `done` como sinônimo de quiescence;
- `experiment` como sinônimo de capability;
- `work` como sinônimo de hypothesis;
- `proposal` como autorização;
- `recommendation` como plan;
- `lock` como termo novo;
- `AI decision` como authority.

---

# 54. Critérios de segurança para evolução autônoma

O sistema não pode:

- criar segundo writer;
- criar authority ad hoc;
- autoampliar autonomy class;
- autoaumentar budget;
- alterar constitutional surfaces e se autoaprovar;
- enfraquecer fail-closed;
- remover guard para passar experimento;
- tomar autoridade semântica de outro domínio;
- reutilizar Peer Recovery como takeover;
- iniciar experimento apenas porque “sobrou tempo”;
- eternizar `DEFERRED`;
- deixar branches experimentais crescerem indefinidamente;
- persistir toda reflexão como Work;
- usar ausência de observação como sinal de quiescence;
- usar scheduled-run count como aging;
- usar nome de branch como autorização.

---

# 55. Critérios de maturidade para M16

A evolução autônoma só deve ser considerada madura se, por período relevante:

- quiescence não produz spam de experimentos;
- hypothesis count permanece bounded;
- experiment count permanece bounded;
- todos os experimentos terminam;
- nenhuma hipótese fica imortal;
- nenhum `DEFERRED` fica eterno;
- tombstones impedem rediscovery loops;
- semantic coverage não diminui;
- nenhum segundo writer aparece;
- guards não são enfraquecidos para produzir sucesso;
- Work normal sempre tem prioridade;
- domain ownership é respeitado;
- Peer Recovery não vira authority transfer;
- dois workers convergem;
- branch count não cresce monotonamente;
- experimentos negativos são limpos;
- experimentos positivos transferem conhecimento para Work/Capability/contrato apropriado;
- no-op saudável é possível;
- o sistema consegue concluir:
  - “nenhuma hipótese vale persistir”;
  - “nenhum experimento vale iniciar”;
  - “a melhor ação é não mudar nada agora”.

---

# 56. Decisões consolidadas por esta rodada

As seguintes direções devem ser tratadas como especialmente importantes para continuidade:

1. **Pensar não deve exigir quiescência plena.**
2. **Experimentar deve exigir mais rigor do que refletir.**
3. **Hypothesis lifecycle e Experiment lifecycle são coisas diferentes.**
4. **Existe limite para hipóteses ativas.**
5. **Existe limite mais forte para experimentos ativos.**
6. **Limites devem ser mecanicamente aplicados, não apenas descritos em prompt.**
7. **Aging usa eligible review opportunities, não cron runs.**
8. **Quiescence deve poder acumular-se numa window, sem reset por rodada irrelevante.**
9. **Heurística pode sugerir; policy determinística autoriza.**
10. **Fingerprint deve vir de chave estruturada, não de texto livre.**
11. **Exact duplicate e near duplicate devem ser tratados de formas diferentes.**
12. **Admission/ranking devem ter tie-break determinístico.**
13. **Todo experimento nasce com Deathcycle.**
14. **Negative knowledge/tombstones são necessários.**
15. **Experiment orchestrator não ganha poder genérico de mutação.**
16. **Mutações reais continuam usando paved paths e writers canônicos.**
17. **Experiment Scope deve ser verificável.**
18. **Evidence factual deve ser separada de Evaluation interpretativa.**
19. **Independent evaluation deve usar heads compatíveis.**
20. **No-op saudável é uma decisão legítima e auditável.**
21. **Autonomous Evolution deve entrar pelo Capability Lifecycle.**
22. **Constitutional surfaces nunca devem ser auto-promovidas.**
23. **OperationalSemantics 0.3 deve nascer preparado para representar os futuros tools.**
24. **A migração de `lock` deve terminar antes da autonomia experimental avançada.**
25. **M12 deve provar maturidade funcional antes de M13–M16.**

---

# 57. Questões ainda abertas

Este documento não fixa definitivamente:

- nome final das authorities de Hypothesis/Experiment;
- se ambas vivem em Git branch separada, repository file ou outra authority existente;
- número definitivo de slots;
- schema exato;
- enum final de states;
- forma final de Evolution Budget;
- thresholds finais de QuiescenceWindow;
- se Reflection artifacts efêmeros são persistidos como CI artifact, evidence ou não persistidos;
- regra final de near-duplicate;
- mecanismo final de independent evaluation;
- quais classes A2/A3 poderão ser automatizadas;
- quais surfaces serão formalmente constitutional;
- política final de auto-promotion;
- se ProjectState 2.2 terá `nextTransition=null`;
- como Scheduled Tasks externas serão representadas no Semantic Map;
- como o Scheduler integrará findings de evolution sem crescer excessivamente;
- formato final dos tombstones;
- garbage collection de tombstones muito antigos;
- estratégia de bounded negative knowledge storage.

Esses pontos devem ser resolvidos por fases, após M9–M12.

---

# 58. Recomendação de sequência futura

## Agora

Concluir:

- M9 Technical Dictionary;
- Semantic Scope Contract;
- Determinism Contract;
- modelagem de `reservedRefs`;
- desenho de OperationalSemantics 0.3.

## Em seguida

M10:

- cobertura semântica;
- registry 0.3;
- component roles ortogonais;
- coverage guard.

## Depois

M11:

- substituir `lock`;
- limpar aliases;
- convergir erros `LOCK_*`;
- limpar triggers legacy;
- decidir utilities residuais;
- limpar docs históricas misleading.

## Depois

M12:

- abrir incremento funcional real;
- usar o framework maduro sob carga normal;
- observar regressões estruturais.

## Somente então

M13–M16:

- shadow reflection;
- quiescence;
- hypothesis lifecycle;
- experiment lifecycle;
- deathcycle;
- negative knowledge;
- autonomous evolution experimental;
- bounded promotion;
- long-run proof.

---

# 59. Filosofia de saída

O objetivo final não é maximizar atividade.

Não é maximizar experimentos.

Não é maximizar commits.

Não é evitar ociosidade a qualquer custo.

O objetivo é maximizar:

- aprendizado útil;
- reversibilidade;
- coerência;
- explicabilidade;
- preservação de conhecimento;
- boundedness;
- capacidade de parar;
- capacidade de evoluir sem erodir governança.

O sistema maduro deve ser capaz de:

```text
observe
understand
hypothesize
test
falsify
discard
remember
promote
clean
stop
```

E deve fazê-lo sem:

```text
inventar autoridade
duplicar writer
reescrever seus próprios freios
crescer indefinidamente
confundir reflexão com execução
confundir hipótese com verdade
confundir experimento com feature
confundir no-op com falha
```

A melhor descrição resumida da arquitetura desejada é:

> **pensar continuamente com baixo custo, experimentar raramente com alto rigor, matar hipóteses e experimentos com a mesma disciplina usada para criá-los, preservar conhecimento negativo e permitir promoção somente quando policy determinística e evidence verificável concordarem.**

---

# 60. Nota de continuidade

Este arquivo deve ser usado como material de bootstrap/contextualização para futuras rodadas de arquitetura de evolução autônoma.

Ele não substitui:

- `AGENTS.md`;
- ProjectState;
- Semantic Registry;
- role Kickstarts;
- Capability authority;
- Work authority;
- Coordination authority;
- schemas canônicos.

Seu papel é preservar a intenção arquitetural e impedir perda de contexto antes da materialização formal dessas ideias em contratos, schemas e tooling.

Até que essas ideias sejam promovidas para superfícies canônicas, este documento é **planning architecture**, não authority operacional.


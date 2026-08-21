# M9–M13 — plano de fechamento antes de PCS-01B 0.1

Status: `ACCEPTED_PLAN / IMPLEMENTATION_NOT_STARTED`

Data: 2026-08-21

Entrada observada: `main@221d41b260250db5ed7f1072009c73346af75afd`

Predecessor: `MODULE-PRESENTATION-METADATA-PLAN-0.1-ACCEPTED`

Este documento é planejamento derivado. Ele não é ProjectState, Work,
Coordination, capability authority, authority de produto nem autorização de
mutação. Cada slice ainda precisa ser admitida, planejada, validada, aplicada e
comprovada pelos writers correntes.

## 1. Decisão

O produto não avança além do plano PCS-01A até o fechamento comprovado de M13.
O caminho de infraestrutura será executado na ordem:

```text
M9 Semantic Foundations + Freshness
  -> M10 OperationalSemantics 0.3 + AgentSemanticBrief
  -> M11 Convergence
  -> M12 Remote Canonical Execution + Maturity Proof
  -> M13 Reflection + OperationalQuiescence
  -> reavaliar admissão de PCS-01B
```

O resultado `CLOSED_DEFERRED` de M12-S1 permanece válido. Não haverá repetição
do mesmo experimento enquanto o caminho remoto canônico não existir e passar
por qualificação manual.

Este plano também incorpora duas preocupações novas ao Semantic Scope:

1. agentes esquecem capabilities e superfícies que já possuem;
2. boas práticas culturais precisam permanecer encontráveis sem se tornarem uma
   policy ou authority paralela.

A resposta arquitetural é um artefato derivado chamado `AgentSemanticBrief`,
composto por uma `CapabilityRelevanceProjection` e por uma seleção limitada de
`EcosystemMaxim`.

## 2. Baseline reconciliado

| Marco | Evidência existente | Lacuna para fechamento |
|---|---|---|
| M9 | Semantic Registry 0.2, Runtime Capability Discovery, Routine Layer e Runtime Observation Boundary | Technical Dictionary, Semantic Scope e Determinism Contract finais; freshness guard |
| M10 | `ops/semantics/registry.json` e validator corrente | schema/registry 0.3, cobertura integral e projeção contextual de capabilities |
| M11 | Coordination canônica, aliases declarados e Branch Hygiene | convergência verificável de `lock`, aliases, triggers e resíduos |
| M12 | S0/S1 fail-closed, zero falso PASS e cleanup completo | executor remoto canônico, qualificação manual e maturity proof aprovado |
| M13 | arquitetura preservada para Reflection/Quiescence | contratos, tooling read-only, janela explícita e provas determinísticas |

PCS-01A está planejado e continua recuperável. PCS-01B, PCS-02 e qualquer
evolução posterior de produto permanecem não admitidos durante este plano.

## 3. Dicionário e fronteiras que M9 deverá fechar

Os contratos finais devem distinguir, no mínimo:

| Termo | Definição operacional pretendida |
|---|---|
| `EcosystemCapability` | feature do ecossistema governada pelo Capability Lifecycle, como `scheduler-supervisor` |
| `LogicalCapability` | capacidade provider-neutral exigida por uma operação, como `github.repository.read` |
| `ToolSurface` | interface concreta invocável, como CLI, MCP tool ou workflow entrypoint |
| `Provider` | carrier/runtime que expõe features concretas; não possui autoridade semântica por existir |
| `Authority` | fonte canônica de um fato mutável de domínio |
| `Role` | função lógica exercida por um ou mais workers |
| `DeclaredIntent` | objetivo contextual informado ao brief; não é Coordination Intent, assignment nem autorização |
| `CoordinationIntent` | registro operacional na authority de Coordination, sujeito ao seu contrato próprio |
| `Projection` | representação derivada que não se torna source of truth independente |
| `Maxim` | lembrete cultural não autoritativo, vinculado a perguntas operacionais e contratos relacionados |

O termo genérico `capability` não poderá ser usado em contrato novo quando a
classe acima alterar o significado. Tool, provider, capability e authority não
são sinônimos.

## 4. AgentSemanticBrief

### 4.1 Propósito

`AgentSemanticBrief` é uma projeção read-only gerada para reduzir omissões de
capabilities durante bootstrap e transições de contexto. Ele não substitui:

- o inventário semântico completo;
- RuntimeCapabilityInspection;
- contratos de papel;
- Work, Continuation, Coordination ou leases;
- planners e writers de domínio;
- decisão humana ou policy determinística exigida por uma operação.

O brief deve ser reconstruível a partir de entradas explícitas. Conceitualmente:

```text
OperationalSemantics + role contract refs + DeclaredIntent
  + lifecycle phase + scope context + RuntimeCapabilityInspection
  -> deterministic eligibility / coverage
  -> optional heuristic ordering of non-authoritative recommendations
  -> AgentSemanticBrief
```

`Nondeterminism may propose; only deterministic policy may authorize` continua
válido. Ranking heurístico pode alterar ordem de recomendações; nunca pode mudar
availability, authority, eligibility, scope ou permissão de mutação.

### 4.2 Shape conceitual

O contrato final será fechado em M9 e implementado em M10. O shape mínimo é:

```json
{
  "schemaVersion": "AgentSemanticBrief 0.1",
  "context": {
    "role": "manager-gitops",
    "declaredIntent": "inspect-and-plan",
    "lifecyclePhase": "planning",
    "scope": ["repository:read"]
  },
  "inputs": {
    "operationalSemanticsHash": "...",
    "runtimeCapabilityInspectionHash": "...",
    "roleContractRefs": ["..."],
    "contextHash": "..."
  },
  "capabilityProjection": {
    "required": [],
    "relevantAvailable": [],
    "conditional": [],
    "requiredUnavailable": [],
    "inventoryCount": 0,
    "selectedCount": 0,
    "omittedCount": 0,
    "missingCoverage": []
  },
  "maxims": [],
  "readOnly": true,
  "semanticAuthority": false,
  "authorizesMutation": false,
  "briefHash": "..."
}
```

Uma projeção personalizada não pode esconder que existe um inventário maior.
`inventoryCount`, `omittedCount` e `missingCoverage` são obrigatórios. Capability
necessária sem observação suficiente entra em `requiredUnavailable` ou
`conditional`; nunca desaparece e nunca vira `PASS`.

### 4.3 Facetas, não tags como policy

Tags livres podem existir como índice de descoberta, mas a classificação usada
para coverage deve usar facetas tipadas:

- roles aplicáveis;
- intent classes;
- lifecycle phases;
- operações e objetos;
- risk class e side effects;
- authorities e scopes exigidos;
- preconditions;
- logical capabilities exigidas;
- providers/features observáveis;
- tool surfaces disponíveis;
- fallback permitido ou explicitamente proibido.

Tags, similaridade textual ou inferência do modelo não concedem scope, lease,
authority nem eligibility.

### 4.4 Gatilhos de reconstrução

O brief deve ser reconstruído:

- no bootstrap;
- quando `DeclaredIntent` mudar;
- quando role, lifecycle phase ou scope mudar;
- quando authorities/leases relevantes mudarem;
- quando a observação de providers mudar;
- quando o registry, role contract ou catálogo de máximas mudar.

O guard correspondente será denominado
`CAPABILITY_DISCOVERY_FRESHNESS_GUARD`. Um brief stale é informativo apenas e
não pode ser usado como prova de availability.

### 4.5 Relação com Routine Layer

O gerador do brief não entra automaticamente em `tools/routines.py`. Routine
Layer avalia obrigações recorrentes sobre um `ProjectMachineInspection` fechado;
o brief é uma projeção contextual de bootstrap e seleção. Transformá-lo em
Routine apenas por ser executado repetidamente misturaria conceitos.

M10 deverá registrá-lo como componente read-only próprio. Uma Routine futura
pode verificar freshness/coverage do mecanismo, mas não reconstruir policy ou
autorizar o uso das capabilities recomendadas.

## 5. Ecosystem Maxims

### 5.1 Classe semântica

`EcosystemMaxim` é orientação cultural curta. A coleção pode ser a fonte
canônica de sua própria redação, mas cada item declara:

```text
operationalAuthority = false
authorizesMutation = false
overridesContract = false
```

Uma máxima nunca resolve conflito entre contracts, cria requirement, promove
capability, admite experimento ou substitui evidência. Quando uma formulação
divergir de um contrato autoritativo, o contrato vence e a máxima deve ser
revisada ou retirada.

### 5.2 Conjunto inicial proposto

| Id | Máxima |
|---|---|
| `creation-requires-justification` | Tudo que é criado é justificado. |
| `birth-requires-death-condition` | Tudo que nasce tem condição de morte. |
| `persistence-requires-justification` | Permanece o que se justifica. |
| `discovery-does-not-authorize` | Descoberta não concede autoridade. |
| `proposal-does-not-authorize` | Propor não é autorizar. |
| `readback-proves-change` | Sem readback, mudança não está comprovada. |
| `negative-knowledge-is-knowledge` | Conhecimento negativo também é resultado. |
| `residue-needs-owner-and-destination` | Todo resíduo tem owner e destino. |

Cada registro deverá possuir:

- statement e stable id;
- justificativa para existir;
- pergunta operacional curta;
- `misreadRisk` para impedir interpretação normativa indevida;
- facetas de aplicação;
- referências a contratos relacionados;
- owner editorial;
- condição de revisão, substituição ou morte.

A seleção no brief será limitada, inicialmente a no máximo três máximas, para
evitar prompt pollution e dessensibilização. A seleção pode ser contextual, mas
continua não autoritativa.

A própria coleção obedece às três primeiras máximas: nasce com justificativa,
condição de revisão/morte e só permanece enquanto reduzir omissões sem duplicar
ou contradizer contracts.

## 6. Slices de fechamento

### M9-SF1 — Semantic Foundations 0.1

Entregas:

1. Technical Dictionary final para os termos da seção 3;
2. Semantic Scope Contract de `AgentSemanticBrief`,
   `CapabilityRelevanceProjection` e `EcosystemMaxim`;
3. Determinism Contract classificando cada campo como factual determinístico,
   policy determinística ou recomendação não autoritativa;
4. contrato de freshness e invalidation;
5. testes de contrato que impeçam `semanticAuthority=true` ou
   `authorizesMutation=true` nesses artefatos.

Não escopo:

- promover o registry para 0.3;
- implementar ranking por modelo;
- adicionar writer ou authority;
- alterar kickstarts para incorporar lista estática de tools;
- modificar produto.

Gate de saída:

```text
checkpoint = M9-SEMANTIC-FOUNDATIONS-0.1-CLOSED
nextTransition = implement-operational-semantics-0.3-and-agent-semantic-brief-v0.1
```

### M9-FG1 — Roadmap Freshness Guard 0.1

O drift recorrente de roadmap deixa de ser apenas lembrete de revisão. O guard
deve observar mudanças em `ProjectState.development.checkpoint` e
`nextTransition` e exigir cobertura explícita dos documentos derivados e
ponteiros correntes declarados.

O primeiro coverage set inclui:

- `docs/plans/autonomous-evolution-roadmap-2026-08.md`;
- `docs/kickstarts/roles/ui-ux-current.md`;
- outros `*-current.md` que passem a repetir estado mutável.

O resultado será uma inspection read-only. `NO_CHANGE` precisa ser explícito e
vinculado aos hashes observados; silêncio não equivale a coverage. O guard não
declara que a narrativa está semanticamente correta, apenas impede que uma
transição altere estado corrente sem revisar todos os consumidores conhecidos.

M9-FG1 pode integrar na mesma PR de M9-SF1 se o diff e os gates permanecerem
revisáveis; caso contrário deve ser a slice imediatamente seguinte e continuar
bloqueando M10.

### M10-OS1 — OperationalSemantics 0.3

Entregas:

1. schema e registry 0.3, sem compatibilidade implícita com 0.2;
2. descriptors tipados suficientes para gerar a projeção contextual;
3. catálogo completo de components, authorities, resources, contracts,
   logical capabilities e tool surfaces correntes;
4. contrato e catálogo versionado de máximas não autoritativas;
5. gerador/validator read-only do `AgentSemanticBrief`;
6. coverage determinística, ordenação estável, hashes e testes de freshness;
7. integração de descoberta no bootstrap como projeção adicional, sem substituir
   `status`, `doctor`, role Kickstart ou ProjectMachine.

Gates mínimos:

- mesma entrada normalizada produz o mesmo brief, exceto seção de ranking
  declaradamente não autoritativa quando habilitada;
- tool ausente não apaga a logical capability correspondente;
- provider alternativo não enfraquece invariantes;
- capability requerida e não observada fica explícita;
- tags não alteram authorization;
- inventário inteiro possui coverage e nenhum descriptor orphan;
- seleção de máximas não altera eligibility;
- validator rejeita brief stale, tampered ou com claims de authority.

Gate de saída:

```text
checkpoint = M10-OPERATIONAL-SEMANTICS-0.3-CLOSED
nextTransition = converge-m11-coordination-aliases-and-residues-v0.1
```

### M11-CV1 — Convergence 0.1

Entregas:

1. `tools/lock.py` reduzido ao adapter/alias estritamente necessário sobre a
   Coordination canônica ou retirado quando seus consumidores tiverem migrado;
2. aliases `lock` e namespace `ops` auditados contra consumidores reais;
3. triggers e workflows sem caminhos paralelos para a mesma operação;
4. resíduos de migração classificados, arquivados ou coletados pelo writer
   apropriado;
5. Semantic Registry e testes provando um writer canônico por authority.

Alias só morre quando coverage provar ausência de consumidores. Deleção por
nome, idade ou milestone não é permitida.

Gate de saída:

```text
checkpoint = M11-CONVERGENCE-0.1-CLOSED
nextTransition = implement-m12-remote-canonical-execution-bridge-v0.1
```

### M12-RP1 — Remote Canonical Execution Bridge 0.1

O “provider” faltante em S1 não é uma nova authority externa. O contrato,
policy, planners, validators e executor pertencem ao repositório. Um carrier
externo pode hospedar ou transportar a chamada, mas não decide semântica.

O caminho exigido é:

```text
closed request envelope
  -> domain planner
  -> plan validation + expected heads + allowlist
  -> canonical executor
  -> aggregate readback
  -> verifiable receipt
```

Regras:

- não criar writer Git genérico para contornar planners de domínio;
- não empilhar `GitMutationPlan` genérico sobre uma operação que já possui
  planner/writer canônico;
- branch e paths precisam ser enumerados;
- `main` é proibida para a qualificação experimental;
- expected head/CAS e readback independente são obrigatórios;
- ausência do carrier produz `UNKNOWN`/blocker, nunca fallback de escrita direta.

Antes de qualquer Scheduled Task, uma mutação manual descartável e confinada a
branch deve provar plan, validation, apply, receipt, aggregate readback, zero
mudança em `main` e cleanup.

### M12-S2 — Maturity Proof 0.1

Somente após M12-RP1 passar, o protocolo comparativo pode ser reaberto:

- uma branch por role;
- Manager/GitOps A e B compartilham a branch de operações em fases diferentes;
- UI usa sua branch de role;
- `COUNT=2` por worker;
- execução standalone fora de Work quando selecionável e verificável;
- environment mismatch falha fechado;
- receipts e disposições terminais duráveis;
- Branch Hygiene executa cleanup normal.

M12 não precisa usar PCS-01B como carga. As mudanças reais de M9–M11 fornecem a
evidência de desenvolvimento não trivial; S2 prova o lifecycle remoto confinado.
Isso preserva a decisão de não avançar produto antes de M13.

M12 só passa com:

- `pavedPathCompletionRate=1.0` nas operações admitidas;
- zero falso PASS, scope escape ou mutation em `main`;
- terminal disposition persistida;
- `residualBranchCountAfterCleanup=0`;
- A/B convergentes sobre os mesmos heads;
- provider/carrier e execução canônica registrados separadamente.

Gate de saída:

```text
checkpoint = M12-MATURITY-PROOF-0.1-PASSED
nextTransition = implement-m13-reflection-and-operational-quiescence-v0.1
```

Falha ou provider gap mantém M12 aberto com blocker preciso. Contagem de runs não
promove o milestone automaticamente.

### M13-RQ1 — Reflection Eligibility 0.1

Implementar uma inspection read-only que distingue:

- ação operacional prioritária;
- espera legítima que ainda permite reflexão;
- observação insuficiente;
- `ReflectionEligible`.

Ela pode consumir o AgentSemanticBrief como ajuda de descoberta, mas não como
authority. Reflection não cria Work, branch, PR, lease, hipótese persistida ou
experimento.

### M13-RQ2 — OperationalQuiescence 0.1

Implementar evaluator determinístico sobre uma janela explícita de observations.
Relógio implícito, “parece quieto” e ausência momentânea de Work não bastam.

O contrato deve definir:

- observation set e hashes de entrada;
- tamanho da janela e elegibilidade dos samples;
- eventos invalidantes que reiniciam a janela;
- tratamento de `UNKNOWN` e `FAIL`;
- diferença entre `ReflectionEligible`, `OperationalQuiescence` e
  `ExperimentAdmissionEligible`;
- no-op saudável quando não há evidência suficiente.

M13 permanece read-only. Hypothesis Lifecycle, Experiment Lifecycle e
Deathcycle genérico continuam em M14.

Gate de saída:

```text
checkpoint = M13-REFLECTION-QUIESCENCE-0.1-CLOSED
nextTransition = reassess-pcs-01b-module-presentation-metadata-admission-v0.1
```

## 7. Owners e coordenação

| Slice | Owner semântico primário | Participação coordenadora |
|---|---|---|
| M9-SF1 | Operations/Semantics | Manager/GitOps garante boundaries e gates |
| M9-FG1 | Operations/GitOps | owners dos ponteiros derivados declaram coverage |
| M10-OS1 | Operations/Semantics | role owners validam facetas; não cedem authority |
| M11-CV1 | Coordination + Git Governance | consumers provam migração antes de retirement |
| M12-RP1/S2 | Operations/GitOps | UI participa somente no envelope de sua role |
| M13-RQ1/RQ2 | Operations/Semantics | domains fornecem facts, não decisão cruzada |

`nextTransition` nunca constitui assignment. Work, Continuation, Coordination e
leases continuam sendo materializados nas authorities existentes quando cada
slice for admitida.

## 8. Gates globais

Cada slice precisa preservar:

1. `observe -> plan -> validate -> apply -> readback` para mutações;
2. uma authority e um writer canônico por fato mutável;
3. `UNKNOWN != PASS`;
4. separação entre evidence factual e evaluation interpretativa;
5. nenhuma inferência de authority por nome de role, branch, provider ou tool;
6. rollback/reversibilidade e cleanup definidos antes da admissão;
7. roadmap e ponteiros correntes cobertos pela transição;
8. ausência de mudança em PCS-01B, PCS-02 ou produto;
9. nenhum Scheduled Task novo antes do gate M12-RP1;
10. nenhum Hypothesis/Experiment writer antes de M14.

## 9. Métricas para a hipótese de capability recall

M10 deve permitir comparar bootstrap sem e com brief usando, no mínimo:

- `requiredCapabilityOmissionRate`;
- `staleAvailabilityRate`;
- `falseRecommendationRate`;
- `unauthorizedSuggestionRate`;
- `inventoryCoverageRate`;
- `pavedPathSelectionRate`;
- tamanho do brief e número de máximas selecionadas.

O mecanismo morre ou é redesenhado se aumentar claims não autorizados, esconder
coverage, duplicar role contracts ou não reduzir omissões de capability. “O
modelo parece lembrar melhor” não é critério suficiente de permanência.

## 10. Transição aceita por este plano

Após integração deste documento:

```text
checkpoint = M9-M13-CLOSURE-PLAN-0.1-ACCEPTED
phase = between-increments
nextTransition = implement-m9-semantic-foundations-v0.1
```

Essa transição aceita somente o plano. Ela não declara M9 concluído, não promove
OperationalSemantics, não cria o brief e não admite PCS-01B.

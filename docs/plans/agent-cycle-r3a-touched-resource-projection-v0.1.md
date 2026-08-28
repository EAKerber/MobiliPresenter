# R3A — Touched Resource Projection 0.1 — plano de implantação

Status: **planning-only; nenhuma mudança de runtime neste branch**

Baseline observado e exigido para a futura implementação:
`main@4a59cb9a701d38df4318f4931640183a0d630eff`.

Contexto: R2A, R2B-1, R2B-2 e R2C-1 já estabeleceram identidade canônica do
ciclo, handle-first boundaries, replay fence por operação exata e resumability do
artifact. O ProjectState permanece `between-increments`; D3 continua sendo a
próxima transição autoritativa. Este recorte é uma evolução paralela do paved
path e não altera ProjectState.

---

## 1. Objetivo do recorte

R3A deve responder de forma determinística e reconstruível:

> **Quais recursos este ciclo declarou tocar, e a partir de qual evidência de
> plan/dispatch/lifecycle sabemos disso?**

A resposta não será uma nova tabela de estado do ciclo. Será uma projeção
read-only sobre fatos já existentes e hash-bound.

O resultado pretendido é um `TouchedResourceSet` que possa ser reconstruído a
qualquer momento a partir dos mesmos requests/plans/dispatches/receipts do ciclo.
Ele será a base para R3B/R3C derivarem obligations, progress e disposition sem
criar uma segunda fonte de verdade para Work, leases, branches, PRs ou
ProjectState.

### Resultado operacional desejado

```text
cycle-bound requests/plans/dispatches/lifecycle records
                       |
                       v
           Touched Resource Projection
                       |
             +---------+---------+
             |                   |
          R3B obligations      R3C progress
             |                   |
             +---------+---------+
                       |
                    close
```

O recorte **não** muda ainda o julgamento de `close`.

---

## 2. Problema observado na implementação atual

O close atual possui duas capacidades valiosas, mas incompletas para R3:

1. `AgentCycleDelta 0.1` detecta mudanças em ProjectState e `sourceHeads` já
   presentes no baseline;
2. `AgentCycleReceipt 0.1` exige evidence atribuída para durable deltas que o
   delta detectou.

Isso prova **o que mudou entre duas fotografias conhecidas**, mas não prova tudo
que o ciclo declarou tocar.

Exemplos:

- uma branch criada e depois removida pode não aparecer no delta final;
- uma branch tocada mas sem alteração final continua relevante para disposition;
- uma lease adquirida e liberada corretamente não deve desaparecer da história
  apenas porque o estado terminal está limpo;
- um PR planejado ainda não possui `prNumber` antes do apply;
- uma operação BLOCKED pode ter declarado um target relevante mesmo sem mutação;
- Work pode ter sido selecionado/avançado sem que seu lifecycle deva ser copiado
  para Agent Cycle.

Consequentemente:

```text
final delta != touched resource inventory
```

O inventário precisa nascer das declarações anteriores ao apply e permanecer
reconstruível depois dele.

---

## 3. Princípio estrutural

### 3.1 Single Writer / Single Source / Single Definition

Para cada recurso:

```text
mutable state
  -> permanece exclusivamente na authority do domínio

resource identity
  -> pode ser projetada pelo Agent Cycle

precondition / observed revision
  -> permanece no plan/receipt/authority observation de origem

TouchedResourceSet
  -> referência reconstruível, nunca authority
```

Exemplos:

```text
branch head
  authority: Git ref
  writer: governed Git mutation path
  resource projection: {repository, branch}

Work status
  authority: Continuation/Work
  writer: canonical Work transition path
  resource projection: {domain=continuation, kind=continuation, id=<workId>}

lease state
  authority: Coordination
  writer: canonical Coordination transition path
  resource projection: lease scope / lease identity
```

O projection engine pode ser executado em N trust boundaries. A regra de
normalização de identidade deve existir em um único módulo.

### 3.2 Projeção, não ledger

Não criar:

- `cycle-resources.json` como store mutável atualizado a cada operação;
- append log próprio do Agent Cycle;
- writer de touched resources;
- CAS próprio do inventário;
- synchronization protocol entre o inventário e Git/Work/Coordination.

A relação correta é:

```text
source records -> projection
```

não:

```text
source records <-> second mutable resource database
```

---

## 4. Fontes canônicas já existentes

R3A deve reutilizar documentos que já declaram targets antes do apply ou provam
sua materialização depois dele.

### 4.1 Agent Tool mutation dispatch

`AgentToolMutationDispatch 0.1` já contém:

- `cycleInstanceId`;
- `requestHash` / `planHash`;
- um `RemoteCanonicalCommand 0.1` validado;
- target concreto;
- provenance do semantic host.

Ele existe antes da mutation host executar o writer. Portanto é uma boa fonte de
**declared touch** sem transformar request arbitrário em authority.

### 4.2 RemoteCanonicalCommand / canonical plans

`RemoteCanonicalCommand 0.1` já distingue:

- Git target `operation + branch [+ path]`;
- domain target `domain + action + subject`.

Os planners posteriores produzem documentos ainda mais fortes:

- `GitMutationPlan 0.1`;
- `TransitionPlan 0.1`.

Quando um plan mais forte existe, ele acrescenta provenance; ele não cria uma
segunda identidade do recurso.

### 4.3 Write Lease lifecycle

`AgentWriteLeaseRequest 0.1` já declara, antes do apply:

- action `acquire|renew|release`;
- branch;
- actor/session;
- expected Coordination head;
- expected Git branch head;
- binding anterior quando aplicável.

Antes do acquire não existe `leaseId`. R3A não deve inventá-lo.

`AgentWriteLeaseBinding 0.1` / lifecycle result pode posteriormente acrescentar
uma identidade concreta de lease.

### 4.4 Transition receipts / close evidence

`TransitionReceipt 0.1`, Git mutation readbacks e Remote Canonical receipts já
são validados pelo close. Eles são fontes de provenance e materialização, não a
origem exclusiva do inventário.

### 4.5 Work

`ContinuationState 0.2` / `WorkAuthorityInventory 0.1` continuam sendo authority.
`work_graph.active_execution_bindings()` já deriva Work/branch/PR ativos sem
transferir ownership.

R3A não copia `status`, `remaining`, `blockers` etc. para o resource set.

---

## 5. Decisão de taxonomia mínima

A taxonomia inicial deve representar somente identidades que os contratos atuais
conseguem provar sem adivinhar.

### 5.1 `git-branch`

```json
{
  "kind": "git-branch",
  "locator": {
    "repository": "EAKerber/MobiliPresenter",
    "branch": "work/example"
  }
}
```

O head atual/esperado não faz parte da identidade. Ele fica no plan/origin.

### 5.2 `git-path`

```json
{
  "kind": "git-path",
  "locator": {
    "repository": "EAKerber/MobiliPresenter",
    "branch": "work/example",
    "path": "docs/example.md"
  }
}
```

Um file mutation normalmente gera também o `git-branch` correspondente.

### 5.3 `pull-request-slot`

Antes de `create-pr` não existe número de PR. O recurso prospectivo é o slot
identificável pelos fatos conhecidos:

```json
{
  "kind": "pull-request-slot",
  "locator": {
    "repository": "EAKerber/MobiliPresenter",
    "head": "work/example",
    "base": "main"
  }
}
```

Não inventar `prNumber`.

### 5.4 `pull-request`

Quando o número é comprovado:

```json
{
  "kind": "pull-request",
  "locator": {
    "repository": "EAKerber/MobiliPresenter",
    "number": 123
  }
}
```

O slot e o PR concreto podem coexistir. R3B poderá derivar a relação entre ambos
usando receipts; R3A não fará substituição silenciosa.

### 5.5 `domain-subject`

Para Work, Coordination, ProjectState e demais transition domains:

```json
{
  "kind": "domain-subject",
  "locator": {
    "domain": "continuation",
    "subjectKind": "continuation",
    "subjectId": "work-id"
  }
}
```

A authority/revision do domínio permanece no `TransitionPlan`/receipt de origem.
O resource set não a reescreve como estado próprio.

### 5.6 `lease-scope`

Antes de acquire existe ownership scope, não `leaseId`:

```json
{
  "kind": "lease-scope",
  "locator": {
    "repository": "EAKerber/MobiliPresenter",
    "branch": "work/example",
    "role": "manager-gitops",
    "sessionId": "session-x"
  }
}
```

Isso segue a identidade de owner que o lifecycle atual efetivamente usa para
branch/session. `workerId` não será adicionado apenas por conveniência se o
writer não o usa como owner identity.

### 5.7 `coordination-lease`

Depois de binding/readback válido:

```json
{
  "kind": "coordination-lease",
  "locator": {
    "leaseId": "..."
  }
}
```

Esse recurso não substitui `lease-scope`; ele o materializa concretamente.

### 5.8 Checks não entram ainda como recursos independentes

`GitMutationPlan 0.1` hoje pode exigir `requiredGatesMustBeGreen`, mas não declara
identidade dos checks. Criar check locators agora seria invenção.

Quando contracts futuros materializarem checks concretos, a taxonomia poderá ser
estendida compativelmente.

---

## 6. Estrutura candidata do artifact semântico

Nome proposto:

`AgentCycleTouchedResourceSet 0.1`

```text
schemaVersion
repository
cycleInstanceId
resources[]
sourceSummary
readOnly = true
semanticAuthority = false
authorizesMutation = false
resourceSetHash
```

Cada resource:

```text
kind
locator
origins[]
resourceHash
```

Cada origin deve conter somente provenance estável necessária para reconstrução
e auditoria, por exemplo:

```text
sourceKind
sourceHash
operation/action (quando já faz parte do source contract)
```

Não copiar para o resource:

- branch head;
- authority revision;
- Work status;
- lease state;
- PR state;
- check result;
- mutable call count;
- terminal result status.

Esses fatos são observados nas authorities ou nos documents de origem.

### Ordenação e dedupe

- `resourceHash = stable_hash({kind, locator})`;
- mesma identidade observada em múltiplas sources produz **um resource**;
- origins são união ordenada/deduplicada;
- resources são ordenados por `(kind, resourceHash)`;
- `resourceSetHash` cobre toda a projeção, inclusive provenance;
- ordem de comentários, input lists ou evidence não pode mudar o hash se o
  conjunto semântico for o mesmo.

Essa separação permite:

```text
same resource identity + new provenance
-> same resourceHash
-> new resourceSetHash
```

sem fingir que o recurso em si mudou.

---

## 7. Arquitetura de implementação

### 7.1 Um único kernel puro

Arquivo candidato:

`tools/agent_cycle_resources.py`

Responsabilidades:

- validar/canonicalizar resource locators;
- derivar resources de contracts canônicos suportados;
- unir/deduplicar resources;
- validar/hash-bind `AgentCycleTouchedResourceSet 0.1`;
- nunca fazer I/O;
- nunca observar provider;
- nunca escrever authority;
- nunca julgar obrigação/terminalidade.

Funções candidatas, a confirmar durante implementação:

```text
resources_from_remote_command(command)
resources_from_git_plan(plan)
resources_from_transition_plan(plan)
resources_from_write_lease_request(request)
resources_from_write_lease_result(result)
build_resource_set(repository, cycleInstanceId, sourceRecords)
validate_resource_set(value)
```

Se duas funções acabarem sendo meros wrappers idênticos, uni-las. Não manter
adapters só para espelhar nomes de módulos.

### 7.2 Carrier collection separado da semântica

Hosted/Agent Bus precisa apenas reunir records bound ao ciclo.

Não mover parsing de issue comments para o kernel.

A coleta deve reutilizar as regras já existentes de:

- cycle/begin/actor binding;
- V0_1/V0_2 normalization;
- requestHash;
- exact comment window atual.

R3A não corrige ainda a janela de close. Isso pertence a R4 seal/order.

### 7.3 Trace e resources permanecem projeções irmãs

Não versionar `AgentCycleExecutionTrace 0.1` apenas para acrescentar targets.

```text
same carrier records
      |
      +-> execution trace
      |
      +-> touched resource set
```

Se a implementação mostrar parsing duplicado relevante, extrair um scanner
interno comum **somente depois** que os dois consumers estiverem concretos.

Não criar primeiro um framework de events genérico.

---

## 8. Recorte de implantação proposto

Para evitar misturar inventário com novo julgamento de close, R3 é recortado em
três etapas.

### R3A — Touched Resource Projection 0.1 — próximo recorte

Implementar:

1. characterization dos sources atuais;
2. kernel puro de resource identity/projection;
3. JSON Schema + registry/OperationalSemantics porque o artifact será uma
   superfície semântica durável usada por slices seguintes;
4. collector Hosted read-only ligado ao mesmo cycle binding;
5. materialização de `agent-cycle-touched-resources.json` no close proof/artifact;
6. exposição diagnóstica do hash/contagem, sem mudar `PASS/BLOCKED/UNKNOWN`;
7. testes de equivalência V0_1/V0_2 e cross-cycle isolation.

Não alterar:

- `AgentCycleClosure 0.1` status;
- static `closeRequirements`;
- lifecycle guard de lease;
- Work writer/state;
- Coordination writer/state;
- Git writers;
- ProjectState;
- seal/polling/concurrency.

### R3B — Obligation Inventory / disposition

Consumir o mesmo resource set para derivar obligations domain-specific:

- lease scope/binding -> release/handoff/expiry judgment;
- branch/path -> disposition/integration/retention;
- PR slot/PR -> merge/close/handoff/gates;
- Work subject -> advance/wait/handoff/done/continue;
- ProjectState subject -> transition/NO_CHANGE quando aplicável.

Neste ponto `abandon` pode finalmente ser implementado sem uma segunda lista
manual de Work/lease/branch.

### R3C — CycleProgress + dynamic close

- `CycleProgress` read-only;
- incremental progress projection;
- close passa a consumir obligations dinâmicas;
- static `closeRequirements` recebe death condition e só então é retirado;
- `NO_CHANGE` ganha critério explícito.

R4 continua responsável por seal, late results e ordering.

---

## 9. Fases detalhadas do R3A

### Fase 0 — Characterization / consumer map

Adicionar testes antes de mudança semântica provando o estado atual:

- delta final não enumera uma branch tocada que terminou no mesmo estado;
- trace não contém target/resource fields;
- lease lifecycle guard consegue descobrir branch/lease sem um resource set;
- Work authority continua separada;
- V0_1/V0_2 Tool e Lease convergem ao mesmo inner request.

Objetivo: distinguir replacement deliberado de regressão.

### Fase 1 — Resource identity kernel

Implementar somente:

- locators fechados por kind;
- `resourceHash`;
- deterministic union;
- origins;
- `resourceSetHash`;
- boundary flags read-only/non-authoritative.

Gate local:

- nenhuma função de I/O;
- nenhuma dependency em GitHub transport;
- nenhuma mutation function;
- nenhum relógio;
- nenhuma authority observation.

### Fase 2 — Plan/dispatch adapters

Em ordem:

1. Git branch/path from Remote Canonical / GitMutationPlan;
2. domain-subject from Remote Canonical / TransitionPlan;
3. lease-scope from Write Lease request;
4. concrete lease from lifecycle binding/result;
5. PR slot / concrete PR quando source contracts permitirem.

Parar e reavaliar se um adapter precisar adivinhar campos não presentes no
source contract.

### Fase 3 — Hosted cycle collection

Produzir a projection a partir dos mesmos comments já bound ao ciclo.

Preferência de implementação:

- usar a mesma fetch de comments já feita pelo close/trace;
- não acrescentar uma nova releitura completa do Agent Bus no happy path;
- compartilhar parsing só onde há identidade comprovadamente idêntica;
- não ensinar YAML sobre resource semantics.

Artifact candidato no close proof:

`agent-cycle-touched-resources.json`

O artifact é reconstruível; perder o artifact não perde a authority do recurso.

### Fase 4 — Diagnostic integration

O close Hosted pode registrar:

- resourceSetHash;
- resource count;
- artifact path/hash.

Mas **não** deve bloquear ou passar por causa do resource set neste slice.

Isso cria um período de comparação:

```text
old close judgment
vs.
new resource projection
```

sem mudar comportamento operacional.

### Fase 5 — Qualification

Somente após os gates locais:

- Agent Ops;
- Semantic Contracts;
- Operational Semantics coverage;
- roadmap freshness;
- capability lifecycle;
- Coordination Guard;
- Supervisor Snapshot.

Uma prova Hosted read-only é suficiente; não é necessário mutar domain state
apenas para provar o artifact.

Um segundo smoke com branch/lease pode ser feito somente se já houver um caminho
de qualificação governado e cleanup explícito.

---

## 10. Matriz de derivação

| Source | Fato declarado | Resource(s) | Observação |
|---|---|---|---|
| Git create-branch plan/command | branch | `git-branch` | antes do apply |
| Git create/update/delete file | branch + path | `git-branch`, `git-path` | antes do apply |
| Git mutate-files | branch + canonical paths | branch + N paths | antes do apply |
| Git create-pr | head/base | `pull-request-slot`, head/base branches | sem inventar PR number |
| Git merge-pr | prNumber + base | `pull-request`, base branch | exact PR known |
| transition command/plan | domain subject | `domain-subject` | Work/ProjectState remain authorities |
| lease acquire request | branch + owner scope | branch + `lease-scope` | sem leaseId ainda |
| lease renew/release request | scope + prior binding ref | branch + `lease-scope` | bindingHash fica no origin |
| lease result/binding | leaseId | `coordination-lease` + scope | concrete identity |
| read-only Agent Tool request | arbitrary target | **não derivar genericamente em 0.1** | sem canonical resource semantics |
| Git gate requirement | green gates required | **não criar check resource em 0.1** | check IDs não estão no contract |

A exclusão de read-only targets genéricos é deliberada: R3A 0.1 foca recursos
com lifecycle/durable implications que os contratos atuais conseguem identificar
canonicamente. Isso evita uma taxonomia “qualquer dict é recurso”.

---

## 11. Casos de teste obrigatórios

### Determinismo

- source order diferente -> mesmo resourceSetHash;
- resources duplicados -> um resource com origins unidos;
- origin order diferente -> mesmo resourceSetHash;
- locator fields extras -> reject;
- locator não canônico -> reject.

### Git

- create branch produz branch antes do apply;
- file mutation produz branch + path;
- mutate-files produz paths ordenados e deduplicados;
- mesmo branch tocado por três operations permanece um resource;
- create-pr produz slot sem `prNumber`;
- receipt posterior pode acrescentar `pull-request` concreto sem apagar slot;
- merge-pr inclui PR concreto e base branch.

### Domain / Work

- `continuation` transition produz domain-subject Work;
- projection não contém Work `status`, `remaining`, `blockers` etc.;
- ProjectState transition produz subject reference sem copiar ProjectState;
- authority revision só aparece no source/origin, não como resource state.

### Lease

- acquire request produz branch + lease-scope antes do writer;
- renew/release preservam o mesmo scope;
- binding válido acrescenta lease concreta;
- mesmo session em branches diferentes produz scopes distintos;
- outro actor/session não dedupe indevidamente;
- lease state ACTIVE/RELEASED/EXPIRED continua propriedade do lifecycle guard,
  não do resource set.

### Cycle isolation

- records de outro `cycleInstanceId` nunca entram no set;
- V0_1/V0_2 equivalentes produzem o mesmo resource identity;
- delivery duplicada não duplica resources/origins;
- operation BLOCKED após plan continua aparecendo como declared touch;
- UNKNOWN após attempt não é interpretado como mutation success.

### Authority boundary

- resource set sempre `readOnly=true`;
- `semanticAuthority=false`;
- `authorizesMutation=false`;
- nenhuma API do módulo retorna mutation command;
- nenhuma resource entry carrega mutable domain state como truth.

### Compatibility

- `AgentCycleExecutionTrace 0.1` permanece byte-schema compatible;
- `AgentCycleClosure 0.1` status não muda;
- static `closeRequirements` permanece emitido;
- Hosted V0_1/V0_2 readers continuam válidos;
- R2B-2 requestHash replay semantics não mudam;
- R2C-1 resumability não muda.

---

## 12. Single Definition / Single Writer Gate aplicado a R3A

Para cada campo candidato do resource set, exigir resposta explícita:

1. Qual fato representa?
2. Existe authority para esse fato?
3. Existe writer para esse fato?
4. Estamos copiando estado ou apenas identificando/referenciando?
5. Se derivado, há uma única função canônica?
6. Pode ser descartado e reconstruído dos sources?
7. Duas cópias podem divergir?

Regras de rejeição imediata:

```text
se o campo precisa ser sincronizado com Work/Coordination/Git
-> não pertence ao resource set

se o campo só existe depois do apply
-> não inventar antes; adicionar nova identidade concreta depois

se dois adapters definem o mesmo locator de formas diferentes
-> consolidar antes de merge

se um recurso não pode ser reconstruído dos source records
-> não materializar como fato do ciclo
```

---

## 13. Riscos e respostas

### Risco A — resource set vira nova authority

Resposta: nenhuma mutation API, nenhum store, nenhum CAS, nenhum status mutável.
Tudo precisa ser reconstruível.

### Risco B — taxonomia genérica demais

Resposta: kinds fechados e derivados somente de contracts conhecidos. Nada de
`resourceType + arbitrary payload` em 0.1.

### Risco C — duplicar trace parser

Resposta: inicialmente compartilhar helpers de binding/normalização existentes.
Só extrair scanner comum após dois consumers concretos mostrarem duplicação real.

### Risco D — PR prospectivo conflita com PR concreto

Resposta: preservar slot + concrete PR como fatos diferentes ligados pela
provenance. Não reescrever história.

### Risco E — lease scope vira ownership authority

Resposta: scope é apenas identidade declarada; ACTIVE/owner/readback continuam
na Coordination authority e lifecycle guard.

### Risco F — close começa a bloquear prematuramente

Resposta: R3A apenas materializa diagnóstico. Obligation enforcement só entra
em R3B depois de comparação/qualification.

### Risco G — mais uma leitura completa do bus

Resposta: implementação Hosted deve usar comments já observados pelo trace.
Adicionar uma segunda paginação no happy path é stop/replan condition.

---

## 14. Stop / re-plan conditions

Interromper o recorte e reavaliar se:

- for necessário criar writer/state store para manter resources;
- o handle precisar ganhar mutable resource fields;
- ProjectState/Work/Coordination precisarem ser copiados para o artifact;
- um resource locator depender de heurística ou de dado inexistente;
- Hosted precisar reler o bus inteiro uma segunda vez no happy path;
- a solução exigir versionar trace e close simultaneamente;
- `AgentCycleClosure` mudar comportamento para fazer o inventário funcionar;
- lease ownership precisar ser reinterpretado;
- R3A começar a implementar seal/late-result ordering de R4;
- uma compatibility path for adicionada sem owner/death condition.

---

## 15. Critério de sucesso do recorte

R3A está concluído quando for possível demonstrar:

```text
same cycle records
      -> same TouchedResourceSet
      -> independentemente de delivery/order compatível

same resource touched N times
      -> one resource identity
      -> N provenance origins when semantically distinct

resource set deleted
      -> can be reconstructed

resource set present
      -> cannot mutate anything
```

E, especificamente:

- branch/path/lease/domain/PR identities não desaparecem apenas porque o estado
  final ficou limpo;
- nenhum mutable fact ganhou segundo writer/source of truth;
- close continua com comportamento anterior durante o shadow period;
- o artifact está pronto para R3B derivar obligations sem revarrer conceitos ou
  criar uma segunda lista manual.

---

## 16. Handoff para R3B

R3B só deve iniciar quando R3A provar dois pontos:

1. o resource set é completo para todos os lifecycle-bearing sources atualmente
   admitidos no paved path;
2. a projeção é estável entre V0_1/V0_2 e carriers atuais.

R3B então pode mapear:

```text
resource + origin/action + current authority observation
                       |
                       v
                  obligation
```

Exemplos:

```text
lease-scope + acquire + ACTIVE
-> release / explicit allowed handoff obligation

pull-request-slot + create-pr materialized
-> PR terminal disposition obligation

domain-subject(continuation) + Work binding
-> advance/wait/handoff/done/continue obligation

git-branch + mutation
-> integration/retain/archive/abandon disposition
```

O obligation engine continuará read-only; somente os writers canônicos poderão
satisfazer obrigações que exigem mutação.

---

## 17. Handoff de execução

Branch futura sugerida para implementação, criada somente depois deste
planning-only handoff ser aceito:

`work/operations/m12-at3d-r3a-touched-resource-v0.1`

Base obrigatória: reobservar `main`; não assumir que continuará em
`4a59cb9a701d38df4318f4931640183a0d630eff`.

Sequência de commits sugerida:

1. `test: characterize cycle resource visibility gaps`
2. `feat: add touched resource identity kernel`
3. `feat: derive resources from canonical plans and lifecycle records`
4. `feat: materialize hosted touched-resource projection`
5. `test/docs: qualify R3A projection and record handoff`

Cada commit deve manter os guards existentes; se a árvore intermediária não puder
passar semantic coverage por causa de schema/registry coupling, agrupar contract
+ registry em um único commit atômico em vez de criar compatibility temporária.

Nenhuma alteração de ProjectState deve acompanhar este recorte.

# Agent Cycle R3B0 — Observation / Binding Hardening 0.1

Status: **planning-only; nenhuma mudança de runtime ou ProjectState neste recorte**

Baseline observado para planejamento:
`main@261282c5e27143bd8de1226a9a28afa28c7862c0`.

R3A está integrado e qualificado. O objetivo deste documento é registrar as
pontas soltas reveladas por R2A/R2B/R2C/R3A e reordenar R3 antes de introduzir
obligations, disposition ou `CycleProgress` como consumidores semânticos.

O ProjectState permanece `between-increments`, checkpoint
`M12-AT3D-D2-CONVERGED-GIT-MUTATION-LIVE-QUALIFIED`; D3 continua sendo a próxima
transição autoritativa. Este plano não altera essa direção.

---

## 1. Resultado da biópsia

A hipótese original era seguir diretamente de:

```text
R3A TouchedResourceSet
-> R3B obligations + disposition
-> R3C CycleProgress + dynamic close
```

A inspeção dos recortes recentes mostra que essa sequência é cedo demais.
`TouchedResourceSet` já é útil como shadow proof, mas ainda não satisfaz duas
precondições necessárias para obligations corretas:

1. **pertencimento inequívoco de cada record à instância concreta do ciclo**;
2. **referência explícita ao Work quando um ciclo executa Work existente**.

Além disso, a cobertura do resource set é a cobertura dos carriers instrumentados,
não uma prova de que nenhuma outra operação ocorreu. Em particular, operações
diretas do Work Mode / connector não entram automaticamente no Agent Bus.

Portanto a sequência recomendada passa a ser:

```text
R3A  touched-resource shadow projection
  -> R3B0a canonical cycle-record observation/binding
  -> R3B0b optional explicit Work binding
  -> R3B1 obligation inventory, shadow
  -> R3B2 obligation resolution/disposition, shadow
  -> R4 seal/order/late-result semantics
  -> R5 provider + Work Mode observation bridge
  -> R3C CycleProgress + dynamic-close enforcement
```

`abandon` permanece depois das precondições acima, não antes.

---

## 2. Evidência live que fecha R3A

Foi executado um smoke Hosted read-only no `main` integrado:

- begin: Hosted Agent Cycle run #125;
- close handle-first V0.2: run #126 (`33214443372`), `success`;
- `cycleInstanceId`: `cycle-instance-a6e05f2d12377f0054104104`;
- close artifact: `agent-cycle-close-33214443372`, artifact id `9702815330`;
- `agent-cycle-touched-resources.json`: válido, vazio como esperado no smoke
  read-only, read-only / non-authoritative;
- `AgentWriteLeaseCloseReport 0.1`: `NONE`;
- `AgentCycleExecutionTrace 0.1`: zero attempts, `PASS`;
- `AgentCycleClosure 0.1`: `PASS`.

Isso prova a materialização real do shadow artifact. Não o promove a authority e
não prova cobertura de operações que não passam pelos carriers observados.

---

## 3. Pontas soltas e falhas conceituais encontradas

### R3-LE-01 — `originCount` é semanticamente ambíguo

`AgentCycleTouchedResourceSet 0.1` calcula `originCount` como número de origins
**distintos globalmente**, não número de links resource→origin.

Um único command que declara branch + path pode gerar dois recursos com a mesma
origin e resultar em `originCount = 1`.

Risco: um consumer futuro interpretar o campo como quantidade de relações de
provenance e tomar decisões incorretas.

Direção:

- nenhum obligation consumer pode depender de `sourceSummary`;
- antes da promoção estrutural, definir explicitamente o significado de
  `originCount` ou remover o contador se ele não pagar pela complexidade;
- preferência redutiva: `sourceSummary` permanece apenas diagnóstico.

### R3-LE-02 — plano R3A sobre-modelou `create-pr`

O plano dizia que `create-pr` projetaria slot + branches. A implementação final
projeta apenas `pull-request-slot`.

A implementação é preferível: criar PR não muta o head/base das branches e o
slot já referencia ambas. Produzir também `git-branch` poderia criar obligation de
disposition falsa sobre branches que apenas participam da relação do PR.

Direção: corrigir a documentação futura; não adicionar os branch resources por
simetria.

### R3-LE-03 — kinds de PR estão dormentes no carrier atual

O kernel suporta `pull-request-slot` e `pull-request`, mas o collector Hosted atual
não possui source path que os produza. `RemoteCanonicalCommand 0.1` não aceita
create/merge PR.

Risco: registrar uma superfície pública maior que a superfície realmente
observável e depois tratar ausência de PR resource como fato.

Direção:

- executar consumer/source scan antes do schema público;
- se continuarem sem producer real, remover os kinds do contrato público inicial
  ou mantê-los explicitamente **non-obligating** até existir caminho forte;
- não preservar taxonomia especulativa apenas porque os testes já a exercitam.

### R3-LE-04 — `domain-subject` é mais aberto que a intenção do recorte

O kind é fechado, porém `domain`, `subjectKind` e `subjectId` aceitam identificadores
genéricos. `TransitionPlan 0.1` também não fecha um vocabulário de domínio.

Risco: R3B virar um framework genérico no qual qualquer domain dict recebe
obligations implícitas.

Direção: obligation adapters só existem para domains explicitamente suportados.
Um resource genérico desconhecido pode permanecer observável, mas não recebe
semântica de disposition por inferência.

### R3-LE-05 — Direct RemoteCanonical tem binding fraco ao ciclo

Agent Tool dispatch e Lease V0.2 possuem binding forte à instância concreta.
Direct `RemoteCanonicalCommand 0.1`, porém, não carrega cycle identity. O collector
lhe atribui pertencimento por:

```text
same actor + same [begin, close) comment window
```

Dois ciclos sobrepostos com o mesmo actor/session podem, portanto, observar o
mesmo direct RemoteCanonical record.

Risco: dupla atribuição de touched resource e obligations falsas em atividade
assíncrona.

Direção: consumers semânticos só aceitam origins **strongly cycle-bound**:

- `cycleInstanceId` explícito; ou
- handle rebinding para o manifest; ou
- lineage exata de result/dispatch já vinculada ao ciclo.

Actor+window-only pode permanecer como diagnóstico/compatibilidade, mas não pode
satisfazer nem criar obligation.

### R3-LE-06 — record alheio malformado pode contaminar o ciclo corrente

Alguns scanners validam o payload completo antes de provar que ele pertence ao
ciclo atual. Um record malformado de outro ciclo na mesma janela pode causar erro
na inspeção corrente.

A ordem necessária é:

```text
parse marker/minimal identity
-> classify binding to current cycle
-> ignore unrelated record
-> fully validate bound record
-> invalid bound record fails closed
```

Unrelated invalid data não pode envenenar outro ciclo; invalid data que se
apresenta como pertencente ao ciclo deve falhar.

### R3-LE-07 — três scanners repetem janela/binding/normalização

Hoje há pelo menos três consumers concretos:

- `tools/agent_tools/trace_collect.py`;
- `tools/agent_cycle_resource_collect.py`;
- `tools/agent_write_lifecycle_guard.py`.

Todos repetem partes de marker parsing, comment permissions, window, V0.1/V0.2
normalization e begin/actor/cycle matching.

R3A deliberadamente adiou um scanner comum até existir duplicação comprovada.
Agora existem três consumers: a death condition dessa espera foi atingida.

Direção: extrair **um scanner interno puro**, sem I/O, authority, writer, CAS ou
status de lifecycle. Isso é consolidação, não novo framework.

### R3-LE-08 — Agent Cycle ainda não possui Work binding explícito

O target conceitual é:

```text
begin(work?, role, intent)
```

O begin real ainda aceita apenas role + intent. Um `domain-subject` de Work só
aparece quando existe uma transition durante o ciclo. Trabalhar em Work já
existente sem transicionar Work deixa o ciclo sem referência autoritativa ao
item que deve receber disposition.

Inferir Work por branch, worker ou PR é ambíguo e proibido.

Direção: adicionar posteriormente um `workRef` **opcional e read-only** ao begin.
Ele referencia Work; não copia status, blockers, remaining ou qualquer estado
mutável. Work continua authority.

### R3-LE-09 — ausência no resource set não prova ausência de toque

O resource set só observa records dos carriers que conhece. Ações Git/GitHub
executadas diretamente por connector/Work Mode não viram records no Agent Bus
automaticamente.

Logo:

```text
resource absent != resource untouched
```

Risco: dynamic close passar falsamente porque nenhuma obligation foi derivada de
uma ação invisível ao carrier.

Direção: R3B1/R3B2 permanecem shadow. Enforcement só é admitido depois de R5
provar cobertura/provider bridge ou restringir explicitamente o ciclo a paths
instrumentados.

### R3-LE-10 — replay fence atual é de request exato, não de intenção semântica

R2B-2 corretamente usa `requestHash` como exact-operation fence. Esse hash inclui
`requestId`; a mesma target/input enviada com novo `requestId` é nova request para
o sistema.

O trace, ao mesmo tempo, expõe `operationId = requestId`, mas correlaciona/dedupe
principalmente por `requestHash`.

Direção:

- R3C não pode usar `requestId` isoladamente como key de progress;
- R4 deve caracterizar separadamente cycle identity, exact request identity,
  logical operation identity e delivery/attempt identity;
- não criar um novo operation store só para resolver o nome.

### R3-LE-11 — closure 0.1 não é explicitamente `cycleInstanceId`-bound

Trace, resource set e lease close report carregam `cycleInstanceId`. A core
`AgentCycleClosure 0.1` usa `cycleId`/context; Hosted close result ainda reporta
cycle/context/begin run, sem `cycleInstanceId` explícito.

Como `cycleId` é fingerprint de contexto e não identidade da execução concreta,
obligations/progress por instância não devem ser enxertados silenciosamente em
Closure 0.1.

Direção: manter artifacts R3B instance-bound em shadow. Se R3C integrar progress
à closure, usar fronteira versionada ou envelope que preserve explicitamente a
instância concreta.

### R3-LE-12 — resumability não é lifecycle/disposition authority

R2C-1 observa disponibilidade do artifact Hosted:
AVAILABLE/EXPIRED/MISSING/AMBIGUOUS/MISMATCH/UNKNOWN.

`EXPIRED` significa que o carrier não permite retomar aquele artifact; não
significa Work abandonado, lease liberada, branch descartável ou PR resolvido.

Direção: nunca derivar domain disposition diretamente de artifact expiry.
`abandon` não é reintroduzido até existir Work binding, obligation inventory,
coverage e ordering seguros.

### R3-LE-13 — semantic/docs drift acumulado

Ainda estão visíveis:

- R1C LE-01: definição registrada de `AgentToolProjection` omite `discoverable`;
- R1C LE-05/06: política de nested historical version ainda não está fechada;
- R1C LE-07: `docs/architecture/agent-cycle-0.1.md` descreve mental model antigo;
- `docs/architecture/agent-cycle-provider-gap-0.1.md` ainda fala do Hosted Agent
  Cycle como futuro, apesar de ele já existir; o gap provider-neutral/Work Mode
  continua real;
- plano R3A e amendment precisam ser lidos juntos para refletir a decisão final de
  não registrar schema enquanto shadow.

Esses itens não bloqueiam R3B0a, mas devem permanecer gates explícitos de R5/R6.

---

## 4. Novo recorte imediato — R3B0a

Nome proposto:

**R3B0a — Canonical Cycle Record Observation / Binding 0.1**

Objetivo:

> Tornar a seleção dos records pertencentes a uma instância Hosted uma única
> definição pura, reduzindo scanners duplicados e impedindo contaminação entre
> ciclos, sem alterar trace/resource/lease semantics observáveis.

### 4.1 Módulo candidato

`tools/hosted_cycle_records.py`

Nome não é compromisso de API pública. Se um módulo existente já puder assumir a
responsabilidade sem circularidade, preferir união ao invés de novo arquivo.

Responsabilidades permitidas:

- receber `comments + manifest + closeCommentId` já observados;
- definir uma vez a janela atual `[begin, close)`;
- reconhecer markers já existentes;
- extrair identidade mínima sem promover payload arbitrário a válido;
- classificar `BOUND | UNBOUND | AMBIENT/LEGACY` internamente;
- normalizar V0.1/V0.2 equivalentes somente depois do binding apropriado;
- retornar records read-only para consumers;
- delegar full validators aos contracts canônicos existentes.

Responsabilidades proibidas:

- buscar comments;
- observar provider;
- escrever artifact/authority;
- criar lifecycle state;
- decidir obligation/disposition;
- criar seal;
- esperar late results;
- reordenar eventos após close;
- introduzir PENDING/WAITING;
- criar generic event framework.

### 4.2 Regra de strong binding

Para semantic consumers:

```text
STRONG
  explicit cycleInstanceId
  OR handle -> exact manifest binding
  OR exact nested lineage from an already cycle-bound record

AMBIENT/LEGACY
  actor + comment window only
```

Ambient records podem continuar aparecendo em diagnóstico/trace compatível onde
essa semântica histórica for necessária, mas não entram no caminho de obligation
sem confirmação adicional.

### 4.3 Migração dos três consumers

Ordem preferida:

1. characterization dos outputs atuais;
2. `trace_collect` usa record view comum sem alterar `AgentCycleExecutionTrace 0.1`;
3. `agent_cycle_resource_collect` usa a mesma view;
4. `agent_write_lifecycle_guard` usa a mesma window/binding view;
5. remover helpers duplicados somente quando consumers já estiverem verdes.

Se a extração exigir mudar simultaneamente schemas de trace/resource/lease,
parar e replanejar.

---

## 5. R3B0b — Work binding explícito, separado

R3B0b só inicia depois da estabilização do scanner para evitar misturar identity
carrier com Work semantics no mesmo diff.

Contrato alvo:

```text
begin(workRef?, role, intent)
```

`workRef` mínimo:

```json
{
  "workId": "..."
}
```

A forma final deve ser validada contra o Work contract corrente. Não adicionar
branch/pr/status ao `workRef` apenas por conveniência.

Provável impacto:

- nova versão de `AgentCycleContext`;
- Hosted begin transport compatível para o optional `workRef`;
- `AgentCycleHandle 0.1` pode permanecer inalterado porque já prende context
  schemaVersion + contextHash;
- fixtures históricas literais devem cobrir Context 0.1/0.2/0.3, em vez de
  sintetizar história a partir do producer atual.

O Work binding não seleciona Work automaticamente e não concede ownership.

---

## 6. R3B1 — Obligation Inventory 0.1, somente depois de R3B0

Antes do primeiro consumer semântico do resource set:

1. executar source/consumer scan da taxonomia atual;
2. reduzir kinds sem producer real ou marcá-los explicitamente non-obligating;
3. decidir/remover a ambiguidade de `sourceSummary`;
4. adicionar JSON Schema estrutural;
5. registrar o artifact em OperationalSemantics;
6. provar paridade estrutural com o validator Python;
7. manter hashes, canonical ordering e reconstruction como **uma definição
   semântica Python**, sem reproduzi-las parcialmente no schema.

Obligation Inventory continua:

- read-only;
- `cycleInstanceId`-bound;
- derivado de strongly-bound resources + optional `workRef`;
- sem authority/writer/CAS;
- sem mutation commands;
- sem `PENDING/WAITING`;
- sem alterar close.

Se precisar de status epistemológico em R3B, reutilizar o vocabulário existente
`PASS | FAIL | UNKNOWN`; async lifecycle pertence a R4.

---

## 7. R3B2 — resolution/disposition shadow

Resolution deve **reusar** inspectors de domínio, não duplicar lifecycle state.

### Lease

Consumir `AgentWriteLeaseCloseReport 0.1` ou a mesma definição canônica. Não
reimplementar ACTIVE/RELEASED/EXPIRED em obligations.

### Work

Observar Work authority pelo `workId` explícito. Não inferir por branch/worker/PR.

### Branch/path

Observar Git. Branch cleanup continua pertencendo ao Branch Hygiene; obligation
pode recomendar/indicar disposition, nunca competir como writer de delete-ref.

### PR

Somente se existir source forte real. Caso contrário, adiar para o provider/
Work Mode bridge.

### ProjectState

Não criar obligation porque ProjectState “poderia” mudar. Apenas um subject
explicitamente observado/bound pode gerar uma obligation; writer continua sendo
o transition path canônico.

---

## 8. Por que R3C enforcement deve esperar R4 + R5

R4 resolve o limite temporal:

- quando um ciclo está selado;
- como classificar late results;
- ordering e duplicate delivery;
- quando PENDING/WAITING realmente existem.

R5 resolve cobertura do runtime/provider:

- operações equivalentes via connector/Work Mode;
- qual provider satisfaz a capability;
- como produzir evidence ciclo-bound sem transformar provider em authority;
- como impedir que ação invisível ao Agent Bus seja interpretada como “não
  aconteceu”.

Somente depois dessas duas condições R3C pode usar obligations para dynamic close
sem falso `PASS`.

---

## 9. Casos de teste obrigatórios para R3B0a

### Cross-cycle isolation

- dois ciclos sobrepostos com mesmo role/worker/session;
- direct RemoteCanonical ambient record não é semanticamente atribuído aos dois;
- handle-bound Tool/Lease record pertence somente à instância correta;
- `cycleInstanceId` mismatch nunca vira fallback por actor.

### Invalid unrelated data

- record malformado de outro ciclo é ignorado pelo ciclo corrente;
- record malformado que afirma pertencer ao ciclo corrente falha;
- marker desconhecido não vira record genérico.

### Compatibility

- Tool V0.1 e V0.2 equivalentes normalizam para o mesmo inner request;
- Write Lease V0.1 e V0.2 idem;
- Trace 0.1 output permanece byte-semantic compatible nas fixtures existentes;
- Lease Close Report 0.1 mantém estados/blockers atuais;
- R3A resource set mantém o mesmo output para records strongly bound.

### Observation economy

- Hosted close faz uma única fetch de comments no happy path;
- scanner comum recebe comments por argumento e não pode fazer I/O;
- nenhum novo polling é introduzido.

### R3A characterization

- um command que produz branch+path caracteriza exatamente a semântica de
  `originCount` antes de qualquer promoção pública;
- PR resource kinds têm source/consumer coverage explicitamente listado;
- ausência de resource nunca é usada como prova de ausência de operação.

---

## 10. Single Writer / Single Definition gate

| Fato | Authority / definição | R3B0 regra |
|---|---|---|
| Work status | Work authority | nunca copiar como cycle truth |
| Coordination lease state | Coordination | usar inspector existente |
| Git branch/PR state | GitHub/Git | observar, nunca duplicar writer |
| cycle instance identity | `agent_cycle_identity` | reutilizar |
| comment window / cycle record membership | **novo single definition interno** | consolidar scanners |
| touched resources | `agent_cycle_resources` | reconstruível |
| obligations | futuro kernel R3B1 | reconstruível, nunca authority |
| artifact resumability | Hosted provider observation | nunca virar domain disposition |
| provider availability | runtime observation | nunca authority |

Regra adicional:

```text
revalidation em N boundaries = permitido
redefinição do mesmo fato em N modules = dívida
```

---

## 11. Stop / re-plan conditions

Parar a implementação de R3B0a se aparecer qualquer necessidade de:

- store mutável de records/resources/obligations;
- novo CAS do Agent Cycle;
- Work inferido de branch, PR ou worker;
- tratar actor+window como strong binding;
- generic event bus/framework;
- nova paginação completa do Agent Bus;
- seal, wait loop ou late-result semantics de R4;
- provider resolution de R5;
- mudar simultaneamente Trace/Closure/Lease schemas;
- interpretar ausência do resource set como cobertura completa;
- transformar `EXPIRED` do artifact em abandonment/disposition de domínio.

Se uma dessas condições aparecer, separar o problema no owner correto em vez de
expandir R3B0.

---

## 12. Critério de encerramento do recorte

R3B0a está concluído quando:

1. existe uma única definição pura de cycle record window/binding;
2. trace, resources e lease guard consomem essa definição sem mudança semântica
   pública não planejada;
3. ambient Direct RemoteCanonical não pode criar semantic obligation;
4. unrelated malformed records não contaminam outro ciclo;
5. strongly-bound malformed records continuam fail-closed;
6. nenhuma authority, writer, mutable state ou provider behavior é adicionada;
7. full Agent Ops, semantic contracts, OperationalSemantics coverage,
   Coordination Guard e Supervisor Snapshot estão verdes;
8. ProjectState permanece inalterado.

Após isso, planejar/implementar R3B0b Work binding; somente então admitir R3B1.

---

## 13. Debt ownership após este plano

### R3B0

- strong record binding;
- scanner consolidation;
- Work reference no begin.

### R3B1/R3B2

- resource structural promotion;
- obligation inventory/resolution shadow;
- `sourceSummary` cleanup;
- dormant resource taxonomy reduction.

### R4

- logical operation vs request vs delivery identity;
- duplicate delivery;
- seal;
- late results;
- PENDING/WAITING/order semantics.

### R5

- provider-neutral operation observation;
- Work Mode/connector bridge;
- stale provider-gap docs;
- R1C discoverability model must remain visible to resolution.

### R6 / bounded semantic-doc cleanup

- historical nested-version policy LE-05/06;
- stale Agent Cycle architecture narrative;
- registered AgentToolProjection definition;
- compatibility path removal only after zero observed consumers.

---

## 14. Decisão final deste planning pass

Não implementar obligations imediatamente.

A redução mais segura é primeiro retirar três definições parcialmente duplicadas
de “quais comments pertencem ao meu ciclo” e substituí-las por uma única definição
pura. Em paralelo sequencial, tornar Work explícito em vez de inferido.

Só então `TouchedResourceSet` pode evoluir de shadow diagnosis para input de
obligations sem criar uma nova fonte de verdade ou uma falsa sensação de
cobertura.

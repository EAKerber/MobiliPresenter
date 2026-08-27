# Agent Cycle R0 — caracterização e mapa de consumidores v0.1

Status: **R0 completo no limite observável do repositório; nenhuma mudança de runtime**

Baseline: `main@158d40b0a6c30035ba6dfa4b24b2566328eee10e`

Relação: primeira fatia executável do plano proposto na PR de planejamento
[#165](https://github.com/EAKerber/MobiliPresenter/pull/165). Este relatório
não muda ProjectState, não substitui D3 e não autoriza R1.

## 1. Objetivo e limite

R0 transforma as hipóteses da biópsia em alarmes reproduzíveis antes de qualquer
refatoração comportamental. Os testes adicionados descrevem o comportamento
atual, inclusive gaps conhecidos. Quando R1 ou fatias posteriores substituírem
um comportamento, a expectativa antiga deve ser alterada junto de uma nova
prova explícita; ela não deve simplesmente desaparecer.

R0 não adiciona schema, entrypoint, workflow, capability, writer ou authority.

## 2. Caracterizações materializadas

Arquivo: `tools/tests/test_agent_cycle_r0_characterization.py`.

| Caso | Comportamento congelado | Classificação | Fatia candidata |
|---|---|---|---|
| readiness de mutação | contexto pode ser `READY` enquanto `git.files.mutate` é condicional | gap confirmado | R1 |
| identidade | mesma baseline produz mesmo `cycleId` e `contextHash` | intenção parcial; falta instância uniforme | R2 |
| instância hosted | run/comment de begin distintos produzem `cycleInstanceId` distintos | proteção existente a preservar | R2 |
| close | intents diferentes recebem a mesma lista estática de requisitos | gap confirmado | R3 |
| durable baseline | somente inspection/control/coordination/continuation são rastreados | cobertura insuficiente para refs arbitrárias | R3 |
| binding com Work | command hosted rejeita `workId` como campo desconhecido | gap confirmado | R3 |
| falha de begin | blocker raiz vira apenas `HOSTED_AGENT_BEGIN_NOT_READY:BLOCKED` | perda de observabilidade confirmada | R1 |
| resultado tardio | resultado após comentário de close fica fora da trace window | defeito estrutural confirmado | R4 |
| interleaving | resultado Agent Tool de outro begin é ignorado | isolamento existente a preservar | R2/R4 |
| estabilização | repetir leitura não atravessa o boundary do close | mitigação incapaz de resolver async real | R4 |
| concorrência | cycle/tool/lease/remote usam grupos ausentes ou distintos | risco de ultrapassagem confirmado | R4 |
| dispatch ordering | dispatch não possui `sequence`, `dependsOn` ou `resourceKey` | gap confirmado | R4 |
| vocabulário do connector | três requisitos do perfil atômico não existem no vocabulário do provider | incompatibilidade de projeção confirmada | D3 |
| capability versus perfil | `git.direct-mutation=PASS` não implica satisfação do perfil atômico | semânticas sobrepostas e não equivalentes | D3 |

Esses testes não declaram que o comportamento é correto. Eles impedem que uma
refatoração misture mudanças não declaradas em uma alteração aparentemente
mecânica.

## 3. Mapa de consumidores

### 3.1 Identidade e begin binding

| Elemento | Produtor/validador principal | Consumidores observados |
|---|---|---|
| `cycleId` | `tools/agent_cycle.py` | close local, hosted manifest/result |
| `cycleInstanceId` | `tools/hosted_agent_cycle.py`, `tools/agent_tools/trace_collect.py` | Agent Tool admission/dispatch, trace, write lifecycle, schemas de receipt/binding |
| begin ref (`runId`, `sourceSha`, `contextHash`) | hosted manifest | hosted tool, write lease, lifecycle guard, close |
| actor (`role`, `workerId`, `sessionId`) | command/request | trace filtering, admission, lease binding e lifecycle |

`cycleInstanceId` aparece em oito schemas operacionais e em pelo menos oito
módulos de runtime. Uma troca de identidade não é uma refatoração local.

### 3.2 Readiness e provider

| Elemento | Origem | Consumidores |
|---|---|---|
| provider observations | input opcional do CLI/hosted begin | runtime capability inspection |
| logical capabilities | semantic registry + observations | semantic brief e Agent Tool projection |
| context aggregate status | ProjectMachine, routine, maintenance, scheduler e required capabilities | begin result e close after-state |
| ToolSurface readiness | Agent Tool policy/projection | resolver, admission e dispatch |

O aggregate status não consome a indisponibilidade de capabilities apenas
condicionais para a tool. Por isso `context.status=READY` e uma tool de mutação
condicional coexistem sem contradição estrutural para o schema atual, embora a
interface seja ambígua para o agente.

### 3.3 Trace e close

| Elemento | Implementação | Consumidores |
|---|---|---|
| comment window | `tools/agent_tools/trace_collect.py::_window` | execution trace e lifecycle guards |
| stabilization | `tools/hosted_agent_cycle_trace.py` | hosted close |
| evidence discovery | trace collector + lifecycle trace | close evidence normalization |
| durable delta | `tools/agent_cycle_close/__init__.py::build_delta` | aggregate readback e receipt |
| static requirements | `tools/agent_cycle.py::_close_requirements` | begin context e reminder da CLI |

A correção da janela não pode ser feita apenas em `_window`: o lifecycle guard
mantém boundary semelhante, e hosted close usa o comentário de close como
identidade e limite. R4 precisa tratar os consumidores como um conjunto.

### 3.4 Carriers

| Workflow | Trigger relevante | Concurrency atual | Efeito |
|---|---|---|---|
| Hosted Agent Cycle | issue comment | ausente | begin/close podem coexistir com outros carriers |
| Hosted Agent Tool | issue comment | `hosted-agent-tool-<issue>` | serializa apenas tools |
| Hosted Agent Write Lease | issue comment | `hosted-agent-write-lease-<issue>` | serializa apenas lease actions |
| Remote Canonical Execution | issue comment/workflow run | grupo próprio por evento | não compartilha ordem total com tool/lease/cycle |

GitHub concurrency reduz sobreposição dentro de cada carrier, mas não representa
dependências `acquire -> mutate -> release -> close`.

## 4. Inventário de campos manuais

O command hosted de ciclo possui dez campos top-level. A referência de begin
adiciona três valores e actor adiciona outros três. Para fechar uma operação, o
caller ou carrier precisa correlacionar pelo menos:

- request/action/intent/scope;
- role, worker e session;
- begin run, source SHA e context hash;
- evidence comment IDs;
- issue/comment usados pelo transport;
- artifact name/run e cycle instance, obtidos em passos posteriores;
- request/plan/dispatch/result hashes das tools;
- authority/branch heads e lease binding quando existe mutação.

Nem todos são digitados pelo agente em todo caminho, mas atravessam envelopes
distintos e precisam permanecer coerentes. R2 deve medir redução pela quantidade
de dados que a interface pública exige do caller, não pela remoção dos bindings
internos necessários.

## 5. Baseline estrutural

Recorte medido durante a biópsia:

- 4.231 linhas em dez módulos Python centrais e três workflows hosted;
- quatro source-head slots no durable baseline;
- três tentativas de stabilization com atraso de um segundo por padrão;
- um begin artifact com retenção de 14 dias;
- quatro carriers relacionados sem chave de ordenação comum;
- uma issue compartilhada como bus e janela histórica.

Esses números são baseline de comparação, não metas isoladas. Uma redução de
linhas ou chamadas só é melhoria se os guards continuarem provados.

### 5.1 Medição read-only do Agent Bus

Observação em 2026-08-27 da issue
[#145](https://github.com/EAKerber/MobiliPresenter/issues/145), usando leitura
de todas as páginas disponível no connector:

| Marker | Comentários |
|---|---:|
| Agent Cycle request / result | 40 / 38 |
| Agent Tool request / dispatch / result | 18 / 14 / 18 |
| Agent Tool mutation attempt | 13 |
| Write Lease request / dispatch / attempt / result | 8 / 7 / 6 / 8 |
| Remote Canonical request / result | 63 / 80 |
| **Total** | **313** |

Todos os 313 comentários começam com um marker conhecido. Isso é positivo para
parsing fechado, mas o close atual ainda precisa reconstruir uma janela a partir
da coleção paginada. O custo mínimo observado para uma leitura completa é 313
itens; não existe cursor de ciclo no contrato atual. R3/R4 devem comparar esse
baseline com leitura incremental, sem converter cache/cursor em authority.

A diferença entre requests e results não prova perda por si só: results incluem
falhas de parse/carrier, retries históricos e versões cujas relações não são
inferíveis apenas da contagem. A medição é volumétrica, não um receipt de
completude.

### 5.2 Dogfooding do provider disponível

Esta fatia foi publicada sem credencial Git de shell por um bundle atômico no
connector: create branch, dois blobs, uma tree baseada na tree de `main`, um
commit com parent exato e update-ref non-force. Readback por Git e por hash de
conteúdo confirmou os dois paths.

Isso demonstra, para este escopo, features equivalentes a ref create/read,
blob/tree/commit create, non-force ref update e content readback. O begin local,
porém, continuou classificando `git.files.mutate` como condicional porque essas
observações não foram convertidas automaticamente em
`RuntimeProviderObservations`. Esse é o custo mínimo confirmado de D3: adapter
de observação + proveniência + resolução + readback. Scope de escrita de
workflow não foi exercitado e permanece `UNKNOWN`.

Há também uma incompatibilidade concreta entre dois contratos internos. O
perfil `github-connector` consegue expressar todos os requisitos registrados de
`git.direct-mutation`, mas seu `featureVocabulary` não contém
`ref-create-at-commit`, `tree-create-inline-content` nem `tree-readback`, que são
exigidos por `GitMutationBundle.ATOMIC_PROFILE_REQUIRED_FEATURES`. Assim, uma
observação válida pode produzir `git.direct-mutation=PASS` e ainda falhar
`provider_satisfies_atomic_profile()`.

Isso não demonstra ausência dessas capacidades no connector: o dogfooding
acima executou a operação atômica equivalente e fez readback. Demonstra que o
runtime não consegue representar essa evidência de modo aceito pelo verificador
mais estrito. D3 deve escolher uma única taxonomia canônica ou definir uma
projeção explícita e testada entre as duas; inferir capacidade pelo nome do
provider ou relaxar silenciosamente o perfil perderia proveniência.

## 6. Matriz preserve/substitua/investigue

| Elemento | Decisão R0 | Justificativa |
|---|---|---|
| baseline/context hash binding | preservar | integridade já provada |
| separação entre cycle e domain writers | preservar | evita authority creep |
| begin ref ligado a source/context | preservar | impede substituição semântica no close |
| `cycleId` como fingerprint | preservar, renomeando significado se necessário | útil para deduplicar contexto |
| `cycleInstanceId` apenas hosted | substituir por presença uniforme | correlação precisa atravessar carriers |
| aggregate `READY` único | substituir por projeções dimensionais | hoje mascara tool/provider readiness |
| close requirements estáticos | substituir por obligations derivadas | não refletem trabalho ocorrido |
| janela encerrada no close comment | substituir por seal | incompatível com async real |
| polling de três segundos | retirar após seal/evento esperado | só cobre atraso curto de visibilidade |
| issue comments como carrier | investigar | pode continuar viável com cursor e correlação |
| artifact de begin por 14 dias | investigar | falta expiry/abandon/retomada explícita |
| concurrency por workflow | substituir por ordem ciclo+recurso | não evita ultrapassagem entre carriers |
| validação repetida de identidade | investigar antes de consolidar | parte pode ser defesa em profundidade |

### 6.1 Classificação inicial das validações repetidas

| Validação | Locais | Classificação R0 | Direção |
|---|---|---|---|
| begin manifest/context binding | cycle, Agent Tool e Write Lease | defesa em profundidade entre trust boundaries | preservar regra; compartilhar kernel puro |
| begin/actor canonicalization | contracts, trace e lifecycle | regra comum repetida em múltiplos envelopes | preservar validação; reduzir implementação paralela |
| comment window begin/close | trace collector e lifecycle guard | duplicação semântica que reproduz o mesmo limite assíncrono | substituir conjuntamente pelo seal |
| command exact fields | cycle/tool/lease/remote | defesa schema-specific | preservar por schema |
| failure payload | cycle/tool/remote/lifecycle | schemas distintos com vocabulário parcialmente divergente | manter envelopes; compartilhar blocker/retryability core |
| hash/readback validation | planner, dispatch, close | defesa em profundidade deliberada | preservar |

A meta não é “uma validação por fato” em termos de chamadas. É uma definição
canônica reutilizada em cada trust boundary que precise revalidar o fato.

## 7. Fechamento do limite R0

### 7.1 Consumidores externos

Os consumidores internos estão mapeados até schemas, módulos e workflows. O
connector disponível e a superfície Work Mode foram observados como providers,
mas o repositório não contém um registro autoritativo de todos os consumidores
externos de context, manifest ou comentários do bus. Portanto, o inventário
externo termina em `UNKNOWN` delimitado, não em alegação de completude.

Essa incerteza bloqueia remoção ou reinterpretação de campos públicos em R1,
mas não bloqueia adição compatível de projeções dimensionais. Telemetria ou um
registro de consumers poderá reduzir o `UNKNOWN` em fatia posterior.

### 7.2 Compatibilidade de status em R1

R1 deve manter o campo agregado `status` como projeção compatível durante a
migração e adicionar dimensões explícitas para contexto, tool, provider e
autorização. Em particular:

- `status=READY` antigo continua significando que o contexto agregado passou;
- ele não autoriza mutação quando a dimensão de tool/provider/autorização não
  estiver `PASS`;
- manifests e contexts antigos continuam legíveis, com dimensões ausentes
  projetadas como `UNKNOWN`, nunca promovidas por inferência;
- consumers aggregate-only recebem a projeção antiga até existir evidência de
  migração; remoção exige deprecation e inventário observável.

Essa decisão preserva leitura enquanto elimina a ambiguidade de autorização no
novo caminho.

### 7.3 Evidência deliberadamente posterior

A disputa hosted entre dois recursos disjuntos e um mesmo recurso é uma prova
de qualificação da solução de ordering/seal, não uma caracterização necessária
para alterar readiness em R1. R0 já congela que os carriers atuais não possuem
uma chave comum e que dispatch não expressa dependências. A prova ao vivo fica
em R4, em ambiente isolado e com critérios antes/depois.

O orçamento mínimo de D3 está agora delimitado por observação, proveniência,
projeção de vocabulário, resolução e readback. O orçamento aceitável final
depende do desenho D3 e não deve ser inventado por R0.

Ambiguidade pós-write já possui caracterização em
`test_agent_tool_dispatch_host.py` e `test_agent_write_lifecycle_host.py`: após a
primeira chamada mutável, falha de transporte permanece `UNKNOWN` e não vira
retry/`PASS`. R0 reutiliza essa prova em vez de duplicá-la.

## 8. Gate para R1

R0 considera o gate de desenho satisfeito quando esta fatia tiver testes locais
e CI remota verdes e for revisada. Já estão materializados:

- consumers internos e limite externo `UNKNOWN` classificados;
- semântica compatível do aggregate `READY` e das novas dimensões definida;
- leitura conservadora de context/manifest antigos definida;
- ausência de novo writer, authority, schema, entrypoint ou workflow;
- incompatibilidade D3 reproduzida sem bloquear a refatoração aditiva de R1.

R1 ainda exige autorização e fatia próprias; este relatório não inicia nem
aprova sua implementação. A CI remota desta revisão deve ser registrada no PR,
sem substituir os checks locais.

## 9. Próxima fatia recomendada

R1 deve introduzir somente o modelo dimensional de readiness e sua projeção de
compatibilidade, com fixtures para contexts antigos e novos. Failure payload,
identidade uniforme, obligations, ordering e seal permanecem fora desse diff.
D3 pode evoluir em paralelo desde que a projeção entre vocabulários seja
explícita e não transforme `UNKNOWN` em `PASS`.

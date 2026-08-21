# Project Machine — plano original M0–M12

Status: fonte histórica de planejamento, não authority.  
Preservado no repositório em 2026-08-21 para continuidade e auditoria.

---

Sim. Fechei um plano que parte do baseline observado agora, mas assume que sua rodada atual de correção de inconsistências terminará antes de eu aplicar qualquer mudança estrutural. O prune já reduziu o repositório a 13 branches e o Branch Hygiene automático está operacional; vou tratá-lo como o primeiro mecanismo vencedor a ser generalizado, não substituído.

Não fiz nenhuma mutação. Este é o plano para sua revisão.

Plano de execução — Project State Machine
0. Objetivo do programa

O estado-alvo não será uma única máquina gigantesca nem um novo ProjectMachineState.json.

Será:

um conjunto pequeno de autoridades especializadas, operadas por um protocolo transacional comum, compostas por uma única interface operacional, com sanitização contínua, estratégias substituíveis e histórico descartável.

Conceitualmente:

                      AGENTE / WORKER
                            │
                         intenção
                            ▼
                   ┌─────────────────┐
                   │      agent      │
                   │ inspect / plan  │
                   └────────┬────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
     ProjectState        WorkState       Capabilities
          │                 │                 │
          ├──────── Coordination ─────────────┤
          │                                   │
          └──────── Git / Publication ────────┘
                            │
                            ▼
                 PROJECT MACHINE VIEW
                    derivada, read-only

E toda mutação operacional relevante converge para:

observe
  ↓
plan
  ↓
validate
  ↓
apply
  ↓
readback
  ↓
receipt
  ↓
sanitize
Regra de dimensionamento

Todos os incrementos abaixo obedecem à margem que você definiu:

85% de escopo comprometido + 15% de leeway.

Os 15% ficam reservados exclusivamente para:

regressões descobertas;
migração inesperada;
incompatibilidades entre authorities;
endurecimento de testes;
readback;
sanitização;
remoção de código legado revelado pelo incremento.

Não serão usados para adicionar features novas.

Se um incremento ultrapassar os 85% previstos, ele será dividido. Não consumiremos a reserva para mascarar um recorte excessivamente grande.

Regra transversal: sanitização

A sanitização não será uma fase final.

Cada incremento seguirá:

PRE-SANITIZE
    ↓
OBSERVE
    ↓
IMPLEMENT
    ↓
VERIFY
    ↓
MIGRATE
    ↓
POST-SANITIZE
    ↓
CHECKPOINT

A implementação atual de Branch Hygiene já demonstra o padrão correto: plano baseado em evidência, planHash, autorização separada, CAS/readback e fail-closed diante de drift.

A ideia é generalizar o padrão, não criar um sanitizer monolítico com autoridade própria.

M0 — Baseline limpo e contrato de migração
Propósito

Estabelecer um ponto inicial confiável depois da sua rodada atual de inconsistências.

Pré-condições

Antes de eu iniciar M0:

sua correção corrente está integrada;
Branch Hygiene terminou;
main está estável;
não há operação Git concorrente que altere o control plane;
as branches que sobreviveram ao prune foram deliberadamente preservadas ou classificadas.

Hoje há 13 branches e duas PRs draft abertas, #3 e #12.

Trabalho comprometido — 85%

M0 será quase totalmente read-only:

reconstruir branch inventory;
observar PRs/CI;
observar main;
observar Coordination e Continuations;
validar capabilities;
identificar resíduos de probe/test;
confirmar estado publicado;
rodar/verificar todas as superfícies operacionais;
gerar um baseline estruturado de inconsistências;
classificar cada uma como:
corrigida;
aceita temporariamente;
alvo de incremento posterior.

Incluirei explicitamente os drifts ainda observáveis hoje, como o README que descreve V7.0-I5 enquanto o ProjectState declara ViewerNext-Preview-2026-08-11.

Leeway — 15%

Para inconsistências introduzidas ou reveladas pela sua rodada atual.

Gate de saída
BASELINE_KNOWN = true
UNCLASSIFIED_DRIFT = 0

Nenhuma tentativa ainda de “resolver arquitetura”.

M1 — ProjectMachineInspection 0.1

Este é o primeiro incremento arquitetural real.

Propósito

Dar ao agente uma visão única do projeto sem criar uma nova authority.

Novo conceito:

agent inspect
Entradas

Ele compõe:

ProjectState;
Git atual;
PRs;
CI;
publicação;
capability lifecycle;
Coordination Leases;
Continuation State;
authority heads;
sanitation status.
Saída

Algo semelhante a:

PROJECT
  lifecycle: BETWEEN_INCREMENTS


PUBLICATION
  status: PASS


WORK
  runnable: 0
  waiting: 0
  handoff: 0


CAPABILITIES
  canonical: 3
  experimental: 1


COORDINATION
  leases: 0


GIT
  branches: 13
  open-prs: 2
  classified: 13


COHERENCE
  publication: PASS
  docs: PASS
  live-authorities: PASS


NEXT
  ...
Mudança fundamental

Introduzir formalmente estados de conhecimento:

PASS
UNKNOWN
BLOCKED

Hoje ainda existem casos em que observação remota desconhecida pode ser representada como check PASS, e CI unknown também não necessariamente bloqueia verify.

M1 elimina essa mistura semântica.

O que NÃO entra
mutações;
Work Graph;
Gmail;
lifecycle novo;
Scheduler novo.
Sanitização

M1 já deverá reportar:

sanitation:
  branch: clean|pending|unknown
  continuation: ...
  evidence: ...
  projections: ...

mas não executar tudo.

Gate

Um worker sem contexto deve conseguir descobrir o estado operacional com:

agent inspect

e no máximo depois ler documentação semântica específica.

M2 — Coerência entre authorities
Propósito

Transformar contradições atualmente possíveis em estados detectáveis.

Hoje verify cruza ProjectState com o manifesto publicado, mas não valida de forma suficientemente ampla o pipeline/documentação corrente.

Invariantes iniciais
ProjectState publication
        ↕
published manifest
        ↕
Netlify configuration


ProjectState active work
        ↕
branch
        ↕
PR


Continuation
        ↕
branch / PR


Lease
        ↕
branch / PR


Capability
        ↕
evidence / lifecycle


role current pointer
        ↕
role contract existence
Um AuthorityMap

Será permitido apenas como configuração estática, não state store.

Algo como:

project-state → main:ops/state/project.json
leases        → coordination/leases
continuations → coordination/continuations
publication   → manifest referenced by ProjectState

Sua função é remover hardcodes espalhados.

Não armazenará valores correntes.

Schema

Aqui também removeremos a duplicação:

Hoje existe JSON Schema, mas agent.py reimplementa manualmente grande parte do shape.

Objetivo:

JSON Schema
   = shape authority


Python checks
   = semantic/cross-authority invariants
Gate

Toda contradição estrutural observável resulta em:

BLOCKED:<stable-code>

Não apenas texto.

M3 — Transition Protocol 0.1
Propósito

Extrair o protocolo que já funciona muito bem em capabilities.

Capabilities já possuem:

beforeStateHash
afterStateHash
planHash
expected-plan
apply
readback
evidence

Isso vira o contrato conceitual comum.

Não construirei um framework gigantesco.

Envelope
{
  "schemaVersion": "TransitionPlan 0.1",
  "domain": "...",
  "action": "...",
  "subject": "...",
  "before": {},
  "intent": {},
  "expectedAfter": {},
  "reversibility": "reversible",
  "planHash": "..."
}

E:

{
  "schemaVersion": "TransitionReceipt 0.1",
  "planHash": "...",
  "verified": true,
  "readback": {},
  "evidence": []
}
Primeiro candidato à migração

checkpoint.

Hoje checkpoint --apply não exige o hash de um plano previamente apresentado.

M3 corrige isso.

Não migraremos tudo

Capabilities e Continuations já funcionam.

Serão apenas adaptadas/normalizadas quando houver benefício.

Gate

Toda nova mutação operacional criada após M3 deve usar:

plan → expected-plan → apply → readback
M4 — ProjectState 2.0: emagrecimento

Este é um dos incrementos com maior benefício cognitivo.

Problema atual

ProjectState contém uma longa lista de constraints de domínio — MDF, forno, GTAO, cuba, cooktop, iluminação, UI etc.

Isso começa a transformar documentação excessiva em JSON excessivo.

Estado-alvo

ProjectState deixa de carregar detalhes e passa a apontar contratos.

Algo conceitualmente próximo de:

{
  "project": {...},


  "lifecycle": {
    "phase": "...",
    "checkpoint": "..."
  },


  "publication": {
    "manifest": "..."
  },


  "contracts": {
    "scene": "...",
    "ui": "...",
    "technicalPresentation": "...",
    "fidelity": "..."
  },


  "work": {
    "authority": "..."
  },


  "operations": {
    "nextTransition": "..."
  }
}
Também sai

operations.commands.

A lista de comandos pertence ao software, não ao estado.

Fingerprint publication

O campo atual artifactSha256 será corrigido semanticamente se continuar sendo fingerprint do SourceBuild e não digest dos bytes do artefato.

Migração

Será explícita:

ProjectState 1.0
       ↓
ProjectState 2.0

Sem compatibilidade eterna.

Gate
nenhuma informação operacional necessária perdida;
detalhes de domínio residem nas respectivas authorities;
ProjectState torna-se pequeno o suficiente para leitura direta;
schema 1.0 entra em janela de compatibilidade limitada.
M5 — WorkState / Work Graph 0.1
Propósito

Substituir o pressuposto de “uma frente ativa”.

ProjectState hoje ainda possui:

activeDevelopmentBranch
development.prNumber
nextTransition

singulares.

Mas o projeto já é naturalmente paralelo.

ContinuationState será evoluído, não substituído.

Nova semântica mínima

Cada work item conhecerá:

id
role
state
dependencies
branch
PR
nextTransition
lastKnownGood
blockers

Possíveis estados:

READY
ACTIVE
WAITING
HANDOFF
DONE
RETIRED
Dependências

blockedBy deixa progressivamente de ser apenas texto livre.

Pode referenciar work items/gates.

Scheduler

O Scheduler passa a poder escolher entre trabalhos explícitos sem arbitrar por ordem incidental de findings.

Branch lifecycle

Branch torna-se consequência do trabalho:

ACTIVE
INTEGRATED
SUPERSEDED
DISPOSABLE
ROLLBACK
ARCHIVE

Isso eventualmente reduz ainda mais a necessidade de inferência no prune.

Gate

Nenhuma frente persistente de trabalho existe apenas:

num chat;
numa branch;
num documento.
M6 — Sanitizer 1.0

Agora podemos generalizar o Branch Hygiene.

Não será um “garbage collector mágico”.

Será um coordenador de planners independentes.

agent sanitize plan
Classes iniciais
branches
continuations
capability evidence
generated projections
expired experiments
orphan work references
stale artifacts

Cada classe informa:

KEEP
REVIEW
RETIRE
DELETE
UNKNOWN
Regra de segurança

Apenas classes cuja remoção possui prova mecanicamente suficiente terão autoApplyEligible=true.

Branch Hygiene já demonstra o modelo.

Pre/post incremental

A partir daqui todo incremento poderá executar automaticamente:

sanitize plan

antes e depois.

Aplicação destrutiva continua sujeita à policy adequada por classe.

Gate

Um incremento concluído não deixa lixo operacional conhecido para o seguinte sem uma justificativa explícita.

M7 — Experiment Lifecycle

Aqui incorporamos diretamente a discussão conceitual recente.

Princípio

Experimentos são temporários por padrão. Permanência exige promoção.

Modelo:

PROPOSED
   ↓
EXPERIMENTAL
   ↓
SHADOW
   ├────────→ DISCARD
   ↓
PROMOTION_CANDIDATE
   ↓
CANONICAL
   ↓
DEPRECATED
   ↓
RETIRED

Não é obrigatório que todos os estágios sejam usados.

Aproveitamento

O atual Capability Lifecycle será a base, porque já possui gates, evidência e promoção explícita.

Novo contrato de experimento

O mínimo:

hypothesis
successCriteria
budget
expiry
replacement/supersedes
retention policy
Fundamental

Um experimento não ganha apply authority apenas por existir.

Shadow:

same inputs
   ↓
experimental planner
   ↓
hypothetical result
   ↓
evidence

Canonical continua decidindo.

Promoção

Review pergunta obrigatoriamente:

What does this replace?
What can now be removed?
What must migrate?
What is the rollback window?
Gate

Um experimento rejeitado pode ser eliminado sem alterar o estado canônico.

M8 — Retirement + Cold Archive no Gmail

Este será deliberadamente posterior ao lifecycle, porque primeiro precisamos saber o que significa aposentar algo.

Regra

Três destinos:

DELETE
COLD_ARCHIVE
PROMOTE_KNOWLEDGE
Cold Archive

O Gmail/Agent Bus pode receber um envelope:

[MP-ARCHIVE] <kind> <subject> <archive-id>

com:

archiveId
subject
reason
conclusion
source heads
retention class
payload hash

e, se necessário, bundle anexado.

Importante

O repositório não conterá um gigantesco índice desses arquivos.

Busca no cold archive será sob demanda.

Transporte

Não colocarei credenciais Gmail no repositório.

O tooling:

agent archive plan

gera deterministicamente:

bundle;
hash;
envelope.

O worker com acesso ao Bus envia e faz readback.

Depois:

archive verified
    ↓
cleanup becomes eligible
Retenção

Classes:

NONE
SHORT
ROLLBACK
ARCHAEOLOGY

Conhecimento permanente não fica no Gmail: é condensado e promovido.

Regra de arquitetura

Excluir completamente a caixa Gmail não pode impedir a operação atual do projeto.

M9 — Compressão documental e Role Manifests

Só aqui atacaremos agressivamente a documentação operacional.

Fazer isso antes seria perigoso porque as ferramentas ainda não teriam absorvido sua função.

AGENTS

Hoje ainda possui um protocolo operacional grande.

Alvo:

confirm repository
run agent inspect
obey authority/blockers
use transition tooling
do not cross semantic authority
Kickstarts

Eliminar progressivamente:

v0.2 imports
  ↓
v0.3 imports
  ↓
v0.4 imports

A versão atual passa a ser materializada, não uma soma mental de deltas.

RoleManifest

Algo pequeno:

{
  "role": "ui-ux",
  "authority": [...],
  "forbidden": [...],
  "requiredCapabilities": [...]
}

E:

agent role inspect ui-ux

materializa o bootstrap operacional corrente.

Histórico

Versões antigas:

retiradas do caminho ativo;
cold archive se houver valor temporário;
Git history não recebe obrigação de compatibilidade.
Gate

Bootstrap normal:

agent inspect
+
role inspect
+
0–2 documentos semânticos
M10 — Supervisor/transport encapsulation

Aqui atacaremos a maior sequência procedural restante.

Hoje o fallback do Manager/GitOps ainda requer navegar Supervisor Snapshot, heads, artifact, ZIP, validação etc.; Peer Recovery acrescenta Bus, health envelopes, dedupe, reproduction e self-retry.

Isso é software escrito em Markdown.

Destino
agent supervisor resolve

pode retornar:

LIVE_PLAN_VALIDATED

ou:

SNAPSHOT_PLAN_VALIDATED

ou:

BLOCKED:SNAPSHOT_HEAD_MISMATCH

Peer:

agent peer inspect
agent peer reproduction-plan
agent peer recovery-plan
Scheduled Tasks

A task se torna cada vez mais um executor:

wake
  ↓
inspect
  ↓
receive validated plan
  ↓
act within role

e não um agente que precisa reimplementar mentalmente o protocolo.

M11 — Convergence / Removal Pass

Este incremento existe explicitamente porque adição sem remoção é o problema que estamos tentando resolver.

Não adiciona nenhuma feature.

Trabalho

Inventário de tudo que M1–M10 tornou obsoleto:

funções mortas;
validators duplicados;
schemas antigos;
antigas projeções;
docs superseded;
compatibility shims;
branches;
probe state;
scripts redundantes;
CI duplicada;
commands antigos;
fallbacks sem consumidor.

Por exemplo, já existe hoje no agent.py uma implementação antiga de prune planning ainda presente apesar do comando delegar ao novo prune_plan.py, um caso representativo de código candidato a compressão.

Regra

Se não conseguimos remover significativamente alguma coisa após toda a migração, revisaremos se realmente simplificamos.

M12 — Long-run autonomous experiment proof

Este é o teste final do paradigma.

Objetivo

Demonstrar que uma Scheduled Task pode operar por muitos ciclos sem acumular dívida.

Escolheremos um experimento operacional de baixo risco.

Ele deve:

observar authorities;
produzir shadow result;
persistir somente estado mínimo;
sobreviver à perda do chat;
respeitar leases/work state;
não alterar decisão canônica;
produzir métricas;
sanitizar resíduos;
atingir budget/expiry;
terminar como:
promotion candidate;
discard.
O teste mais importante

Se DISCARD:

implementation → removed
experiment state → retired
temporary evidence → archived/deleted
branches → pruned

e o projeto volta a aproximadamente a mesma complexidade estrutural que tinha antes do experimento.

Esse será o proof de que conseguimos evoluir organicamente sem canibalização conceitual.

Sequência
sua rodada de consistência/prune
             ↓
            M0
             ↓
            M1  Composite Inspect
             ↓
            M2  Cross-authority coherence
             ↓
            M3  Transition protocol
             ↓
            M4  ProjectState 2.0
             ↓
            M5  Work Graph
             ↓
            M6  General sanitation
             ↓
            M7  Experiment lifecycle
             ↓
            M8  Cold archive / retirement
             ↓
            M9  Documentation compression
             ↓
           M10  Supervisor encapsulation
             ↓
           M11  Removal/convergence
             ↓
           M12  Long-run proof

São mais incrementos do que eu teria proposto sem a regra dos 15%. Isso é deliberado.

Critérios globais de sucesso

Eu consideraria a “máquina de estados do projeto” consolidada quando os seguintes critérios forem verdadeiros.

1. Bootstrap

Um novo agente precisa de:

1 comando geral
+
no máximo 1 comando de role
+
documentação semântica específica

e não de uma cadeia de documentação operacional.

2. Estado

Todo fato operacional corrente tem uma authority identificável.

3. Conhecimento

Ausência de observação é:

UNKNOWN

nunca PASS.

4. Transições

100% das mutações operacionais significativas novas usam:

planHash
drift detection
apply
readback
receipt
5. Trabalho

Nenhuma tarefa persistente depende do chat para existir.

6. Sanitização

Resíduo previsível é coletado automaticamente ou aparece como sanitation debt explícita.

7. Evolução

Estratégias experimentais podem operar em shadow sem alterar canonical state.

8. Descarte

DISCARD é uma trajetória de primeira classe.

9. Histórico

Cold archive não faz parte do bootstrap e pode desaparecer sem quebrar a operação atual.

10. Documentação

Nenhum agente precisa calcular:

v0.2 + v0.3 delta + v0.4 delta

para descobrir o contrato corrente.

11. Complexidade

Toda promoção que substitui uma estratégia possui retirement correspondente.

12. Long-run

Workers agendados conseguem operar por múltiplos ciclos, experimentar, persistir, retomar e limpar sem crescimento monotônico de documentação/branches/estado.

Dois cuidados que adotarei durante a implementação

Primeiro: não tentarei preservar compatibilidade histórica por reflexo. Cada migração terá uma janela explícita. Passada a janela, o legado poderá morrer.

Segundo: cada incremento deverá responder a uma pergunta antes de ser integrado:

Depois deste incremento, o próximo agente precisa saber mais coisas ou menos coisas para operar corretamente?

Se a resposta for “mais”, o incremento só será aceitável se estivermos criando uma fundação temporária cujo próximo recorte elimina essa complexidade. Caso contrário, redividirei o trabalho.

Ponto de autorização

Quando você aprovar este plano, eu ainda faria uma última observação do main imediatamente antes da primeira escrita, porque sua rodada corrente pode continuar alterando o baseline.

Depois disso, minha sugestão é autorizar a execução do programa M0→M12, mas eu ainda manteria as transições destrutivas importantes fail-closed e governadas pelos próprios planos/readbacks. A autorização não seria interpretada como permissão para ignorar os guards que estamos justamente construindo.

Neste momento continuo apenas com permissão de leitura e não apliquei nenhuma parte do plano.

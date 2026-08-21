# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-21  
Repositório observado: `EAKerber/MobiliPresenter`  
Baseline observado: `main@f3401015fdd6390a6b18d7c29b90e51170ed1c00`

Este documento reconcilia duas fontes de planejamento que nasceram em momentos
diferentes:

- o plano original `M0`–`M12`, cujo alvo é uma Project Machine governada por
  authorities especializadas e pelo protocolo comum de transição;
- a evolução posterior `M9`–`M16`, que torna explícitos semântica operacional,
  quiescence, reflexão, hipóteses, experimentos e prova de longo prazo.

Ele não substitui `ProjectState`, Work, Coordination, capabilities, contracts nem
os writers canônicos. Serve para tornar novamente encontrável a intenção e para
impedir que números iguais de documentos diferentes sejam tratados como o mesmo
milestone.

Fontes preservadas nesta mesma branch:

- `docs/plans/project-machine-m0-m12-original-source.md`;
- `docs/plans/autonomous-evolution-architecture-v0.1.md`.

## 1. Invariantes herdados dos dois planos

1. Toda mudança significativa percorre:

   `observe -> plan -> validate -> apply -> readback -> receipt -> sanitize`.

2. Um fato mutável possui uma authority e um writer canônico.
3. Representação derivada nunca vira authority por conveniência.
4. Nondeterminism pode propor; somente política determinística pode autorizar.
5. `UNKNOWN` nunca equivale a `PASS`.
6. Trabalho normal possui prioridade sobre manutenção, reflexão e evolução.
7. O paved path deve ser o caminho mais curto; uma nova camada só se paga se
   remover mais procedimento recorrente do que adiciona.
8. Quiescence não significa apenas ausência de Work. Significa que observação e
   coerência são suficientes e que nenhuma transição obrigatória conhecida está
   pendente.
9. Autonomia nasce em shadow, passa por isolamento e limites e só então pode
   receber authority estreita.
10. Superfícies constitucionais nunca são promovidas automaticamente.

## 2. Como ler a sobreposição dos roadmaps

| Faixa | Intenção original | Evolução posterior | Leitura reconciliada |
|---|---|---|---|
| M0–M8 original | baseline confiável, ProjectMachine, coerência, protocolo, ProjectState enxuto, Work, sanitizer, Experiment, retirement | pré-condições assumidas | fundação substancialmente presente; não é re-certificada por este documento |
| M9 original | compressão documental e RoleManifest | M9 = Technical Dictionary + Semantic Scope + Determinism Contract | existe infraestrutura semântica, mas a cobertura revisada ainda não está concluída |
| M10 original | supervisor e encapsulamento de transporte | M10 = OperationalSemantics 0.3 e cobertura integral | supervisor existe; registry observado permanece `OperationalSemantics 0.2` |
| M11 original | convergência e remoção de legado | M11 = `lock` para Coordination canônica, aliases, triggers e limpeza | incompleto enquanto `tools/lock.py` continuar implementação independente e não alias fino |
| M12 original | prova autônoma longa | M12 revisado = prova de maturidade em desenvolvimento funcional real | próximo gate seguro para tasks agendadas; deve começar em shadow |
| — | — | M13 = Reflection + Quiescence | bloqueado para authority ativa até M12 produzir evidência suficiente |
| — | — | M14-A/B = hipóteses, experimentos e deathcycle | bloqueado; nenhum writer genérico deve ser criado antecipadamente |
| — | — | M15 = capability Autonomous Evolution | bloqueado; deve seguir shadow -> bounded active |
| — | — | M16 = prova autônoma longa | bloqueado; exige convergência, encerramento e no-op saudável |

## 3. Evidência observada no repositório

O baseline de 2026-08-21 demonstra peças maduras e reutilizáveis:

- `ProjectState 2.1` está em `between-increments` e aponta a próxima transição;
- ProjectMachine, RoutineInspection, Maintenance, SchedulerPlan e
  SchedulerSnapshot formam o bootstrap do Manager/GitOps v1.0;
- GitMutationPlan e GitMutationBundle materializam intenção e publicação
  atômica sem force;
- Coordination possui authorities separadas para leases e continuations;
- Branch Hygiene, capability lifecycle, receipts, sanitization e supervisor
  possuem tooling e CI;
- o fluxo RF-0.1B provou bundle, tree proof, aggregate readback, gates de browser
  e integração com head esperado.

Também permanecem lacunas que impedem declarar M9–M12 concluído:

- o registry corrente declara `OperationalSemantics 0.2`, não 0.3;
- `tools/lock.py` ainda é uma implementação operacional completa;
- o catálogo de Routine cobre obrigatoriamente apenas
  `capability-deathcircle`;
- não existe contrato canônico de OperationalQuiescence nem sua janela;
- a task web não possui automaticamente um worktree local onde os verificadores
  Python possam executar;
- o kickstart UI v0.1 ainda descreve como próximo o recorte Responsive
  Fixed-Frame que já foi integrado.

Essas lacunas não devem ser resolvidas dentro do prompt agendado. O prompt deve
observá-las e falhar fechado.

## 4. Decisão de estágio

O próximo passo é denominado:

> M12-S0 — Scheduled Cycle Maturity Shadow 0.1

Ele testa bootstrap repetido de dois Managers/GitOps e um worker UI usando apenas
leitura e no-op. Não é M13, não cria hipótese, não abre experimento de produto,
não promove capability e não altera authority.

A instalação deste baseline usa uma branch normal e termina antes do experimento:

`work/operations/scheduled-cycle-maturity-bootstrap-0.1`

Depois de CI, revisão, merge e readback, as tasks leem charter, prompts e fontes
de planejamento de `main`. S0 não cria branch própria: nenhum worker agendado
escreve. A branch `experiment/operations/scheduled-cycle-maturity-0.1` fica
reservada para uma fase posterior que possua uma mutação experimental aprovada e
persistível; não será criada como placeholder.

As três tasks S0 foram configuradas com três execuções cada. Depois do primeiro
run de B produzir `UNKNOWN_PROVIDER_GAP`, elas foram pausadas: A e UI ainda não
haviam executado. O resultado é um baseline empírico da fronteira do provider,
não um PASS de S0.

O estágio seguinte é `M12-S1 — Bounded Branch Lifecycle Probe 0.2`. Ele preserva
o blocker, admite branches exclusivas fora de `main` e limita cada worker a duas
ocorrências (`COUNT=2`). A hipótese, os receipts e as métricas permanecem fixos
para comparação futura com a implementation de Experiment authority/writer.

## 5. Gate de quiescence usado em S0

S0 não autoriza `OperationalQuiescence`. Ele coleta somente uma projeção shadow:

- `ROLE_NOOP`: o papel não possui trabalho explicitamente roteado;
- `KNOWN_MANDATORY_TRANSITION`: há transição obrigatória observável;
- `UNKNOWN_PROVIDER_GAP`: falta executar um verificador canônico;
- `INCOHERENT`: authorities observadas divergem;
- `BLOCKED`: há impedimento explícito.

Somente uma fase posterior poderá calcular uma janela de quiescence, por exemplo
três observações qualificadas entre as últimas seis elegíveis, com eventos
invalidantes reiniciando a janela. Essa política ainda precisa de contrato,
testes e authority antes de autorizar qualquer ação.

## 6. Critérios para promover S0

Após no mínimo três ciclos comparáveis de cada worker:

- A e B observaram heads compatíveis e produziram classificações coerentes;
- nenhum worker declarou PASS para verificador que não executou;
- UI produziu `ROLE_NOOP` quando não havia Work/handoff explícito;
- `nextTransition` não foi confundida com assignment;
- nenhuma task criou branch, PR, comentário, issue, lease, continuation ou email;
- nenhuma task inventou uma segunda authority ou um algoritmo paralelo;
- o custo do bootstrap e as lacunas de provider ficaram explícitos;
- pausar ou remover as tasks não deixa resíduo no repositório.

A promoção será uma decisão humana e uma mudança separada. O passo seguinte pode
ser S1 provider-backed ou a conclusão de M9–M11, conforme a evidência; não há
promoção automática por contagem de execuções.

## 7. Critérios de morte

O experimento termina sem promoção se:

- qualquer worker mutar estado em S0;
- o prompt reconstruir policy que já pertence ao tooling;
- a ausência de provider for tratada como sucesso;
- os dois Managers divergirem repetidamente sem causa observável;
- UI assumir trabalho de API, runtime, renderer ou Scene Core;
- o custo operacional crescer sem reduzir procedimento manual.

Encerramento consiste em deixar as tasks expirarem ou pausá-las/removê-las. Como
S0 não possui branch própria nem PR de execução, seu rollback normal não depende
de coleta Git. Qualquer fase posterior com branch continua subordinada a Branch
Hygiene.

## 8. Próxima sequência após o baseline S0

1. Executar S1 com branches pré-admitidas, `COUNT=2` e zero writes em `main`.
2. Materializar a comparação e o deathcycle, inclusive quando o resultado for
   provider gap sem receipt durável.
3. Fechar apenas as lacunas M9–M11 que o teste demonstrar como bloqueantes.
4. Repetir o protocolo com tooling canônico, mantendo o mesmo envelope.
5. Só então especificar Reflection e OperationalQuiescence M13.
6. Hipóteses e experimentos M14 usam writers existentes e isolamento real.
7. Autonomous Evolution entra no capability lifecycle apenas em M15.
8. M16 prova que o sistema converge, encerra ciclos e sabe não agir.

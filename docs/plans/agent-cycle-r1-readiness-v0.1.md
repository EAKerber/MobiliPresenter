# Agent Cycle R1A — readiness dimensional v0.1

Status: **candidato de implementação; nenhuma authority ou writer novo**

Base empilhada: `R0@b91c37d1f78fb5ba4555848c7ab9aad597af095e`

Relação: primeira subfatia de R1 do plano da PR
[#165](https://github.com/EAKerber/MobiliPresenter/pull/165), após a
caracterização da PR [#166](https://github.com/EAKerber/MobiliPresenter/pull/166).

## 1. Limite

R1A elimina a ambiguidade mais imediata de `READY` sem mudar admission,
dispatch, writers, workflows ou comportamento de close. O novo
`AgentCycleContext 0.3` preserva o campo agregado `status` e adiciona uma
projeção `AgentCycleReadiness 0.1` com cinco dimensões:

| Dimensão | Semântica nesta subfatia |
|---|---|
| `contextStatus` | integridade agregada já representada pelo status legado |
| `intentReadiness` | role/intent/profile foram reconhecidos e normalizados |
| `toolReadiness` | há uma ToolSurface executável ou planejável para o intent |
| `providerResolution` | provider só é declarado resolvido para uma operação inequívoca e disponível |
| `mutationAuthorization` | permanece `UNKNOWN` até uma operação exata passar por policy e guards |

As dimensões usam `PASS`, `UNKNOWN`, `BLOCKED` e `NOT_APPLICABLE`. Nenhum desses
valores concede authority; a projeção declara `authorizesMutation=false`.

## 2. Projeção compatível

O campo `status` mantém exatamente a semântica anterior:

- `READY` continua indicando que o contexto agregado passou;
- `UNKNOWN` e `BLOCKED` continuam sendo derivados pelos mesmos inputs;
- begin/hosted/close continuam consumindo o campo legado nesta subfatia;
- `readiness.legacyStatus` é validado contra `status`, não calculado por um
  consumer externo.

O novo begin não promove `READY` a autorização. No caso observado de
`governed-mutation`, a projeção é:

```text
status                 = READY
contextStatus          = PASS
intentReadiness        = PASS
toolReadiness          = UNKNOWN
providerResolution     = UNKNOWN
mutationAuthorization  = UNKNOWN
```

Isso torna a próxima ação visível sem quebrar consumers aggregate-only.

## 3. Compatibilidade de leitura

O validator aceita três versões fechadas:

| Context | Campos dimensionais | Comportamento |
|---|---|---|
| `0.1` | sem Agent Tools e sem readiness | valida o artifact histórico como fornecido |
| `0.2` | Agent Tools, sem readiness | valida sem sintetizar dimensões ausentes |
| `0.3` | Agent Tools + readiness | exige projeção canônica e hash-bound |

Artifacts antigos não recebem `PASS` por inferência. Consumers que precisam das
novas dimensões devem exigir 0.3; consumers antigos podem continuar lendo
`status` durante a janela de migração.

Condição de retirada: 0.1/0.2 só podem deixar de ser aceitos depois de inventário
observável sem consumers, deprecation explícita e fixtures históricas
substituídas por uma migração comprovada.

## 4. Guards

- readiness entra no baseline por `readinessHash` e no `contextHash`;
- validation recompõe a projeção a partir de `status`, `blockingUnknowns` e
  `agentTools` em vez de confiar apenas no hash fornecido;
- múltiplas tools produzem `providerResolution=UNKNOWN:OPERATION_NOT_SELECTED`;
- tool condicional preserva o reason code da capability;
- presença de `mutation-execute` produz
  `UNKNOWN:OPERATION_AUTHORIZATION_NOT_EVALUATED`;
- plan-only e intents sem mutação usam `NOT_APPLICABLE`, nunca autorização.

## 5. Fora desta subfatia

- envelope comum de falha;
- `PENDING` e `WAITING`;
- seleção/binding de operação no begin;
- mudança dos consumers hosted/close para as novas dimensões;
- provider adapter D3/Work Mode;
- identidade, Work binding, obligations, ordering e seal;
- correção do readback `git-bundle` no fechamento do Agent Cycle.

Esses itens permanecem separados para que mudanças de status possam ser
comparadas por fixtures antes de alterar transporte ou lifecycle.

## 6. Provas exigidas

- contexto `governed-mutation` preserva `status=READY` e expõe as três dimensões
  executivas como `UNKNOWN`;
- intent com múltiplas tools não alega provider antes da seleção da operação;
- contexts 0.1 e 0.2 continuam validáveis sem promoção dimensional;
- tampering com re-hash não promove autorização;
- suíte completa, semantics check/coverage, roadmap freshness e CI remota PASS.

R1A não conclui R1 por inteiro. A próxima subfatia deve decidir entre migrar os
consumers para as dimensões ou introduzir primeiro o envelope comum de falha,
com base no diff e nos blockers observados nesta revisão.

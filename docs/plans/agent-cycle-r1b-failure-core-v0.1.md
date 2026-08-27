# Agent Cycle R1B-1 — núcleo comum de falha v0.1

Status: **primeira fatia implementável de R1B; nenhum producer ou writer alterado**

Base empilhada: `R1A@21edffcaeb3cbdb1695832f2772cbfceacfb731a`

Relação: segunda subfatia de R1 do plano da PR
[#165](https://github.com/EAKerber/MobiliPresenter/pull/165), após a
caracterização da PR [#166](https://github.com/EAKerber/MobiliPresenter/pull/166)
e a readiness dimensional da PR
[#167](https://github.com/EAKerber/MobiliPresenter/pull/167).

## 1. Resultado desta fatia

R1B-1 introduz `AgentFailureCore 0.1`, uma projeção read-only e hash-bound que
normaliza a semântica comum das falhas sem substituir a identidade específica
dos carriers. O core separa explicitamente:

- repetir uma observação;
- reenviar a operação;
- estado conhecido ou desconhecido da mutação;
- causa raiz e wrappers;
- falha completa de projeção legada incompleta.

Nenhum workflow passa a emitir o novo core nesta fatia. Os quatro envelopes
existentes continuam bit a bit sob responsabilidade dos producers atuais:

- `HostedAgentCycleFailure 0.1`;
- `HostedAgentToolFailure 0.1`;
- `RemoteCanonicalExecutionFailure 0.1`;
- `AgentWriteLeaseFailure 0.1`.

## 2. Contrato fechado

| Campo | Semântica |
|---|---|
| `surface` | fronteira operacional que materializou a falha |
| `phase` | fase explícita; nunca inferida de texto livre |
| `status` | somente `BLOCKED` ou `UNKNOWN` |
| `causes` | lista não vazia ordenada da raiz para os wrappers |
| `recovery.observationRetry` | segurança de repetir apenas a observação |
| `recovery.operationReplay` | segurança de reenviar a operação completa |
| `mutationState` | `NOT_APPLICABLE`, `NOT_APPLIED`, `APPLIED` ou `UNKNOWN` |
| `lossyProjection` | declara que o artifact de origem não prova toda a cadeia |
| boundaries | read-only, sem authority e sem autorização de mutação |
| `failureCoreHash` | hash estável de todos os campos semânticos anteriores |

O core não inclui request ID, command hash, actor, branch ou detalhe. Esses
campos permanecem nos envelopes externos e continuam cobertos pelo
`failureHash` do carrier. Essa separação evita um envelope universal com
identidade opcional e mantém a validação fechada por domínio.

## 3. Invariantes fail-closed

- `mutationState=UNKNOWN` exige `status=UNKNOWN`;
- replay `SAFE` é proibido quando a mutação está `APPLIED` ou `UNKNOWN`;
- retry de observação não promove replay da operação;
- nenhuma projeção pode declarar authority ou autorização;
- causas duplicadas são rejeitadas;
- tampering de campos ou hash é rejeitado;
- texto `detail` nunca decide status, replay ou policy;
- fase ausente em artifact legado é erro, não heurística.

O validator não tenta demonstrar semanticamente que a primeira causa é a raiz;
essa ordem é obrigação do producer 0.2. Em artifacts 0.1, a projeção declara
`lossyProjection=true` porque os blockers existentes não provam a cadeia.

## 4. Compatibilidade dos envelopes 0.1

O normalizer exige schema conhecido, conjunto exato de campos, boundaries
não autoritativas e `failureHash` válido. Ele não reescreve o artifact.

| Envelope legado | Mutation state padrão | Status normalizado | Replay |
|---|---|---|---|
| Hosted Agent Cycle | `NOT_APPLICABLE` | preservado quando válido | `NOT_APPLICABLE` |
| Hosted Agent Tool | `NOT_APPLIED` | preservado quando válido | `UNKNOWN` |
| Remote Canonical | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| Write Lease `BLOCKED` | `NOT_APPLIED` | `BLOCKED` | `UNKNOWN` |
| Write Lease `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |

Remote Canonical 0.1 é promovido fail-closed para `UNKNOWN` porque seu envelope
não registra se a exceção ocorreu antes ou depois de uma chamada mutável. Isso
não muda o artifact externo nem autoriza retry; torna explícita a evidência que
falta.

O fallback atual de Write Lease com `failureHash=""` é rejeitado. A correção do
producer fica deliberadamente para R1B-4, quando a fronteira pós-write será
migrada com seus testes de replay fence e ambiguity.

## 5. Próximas fatias

1. **R1B-2 — Hosted Agent Cycle:** incorporar o core em begin/close 0.2,
   preservando blockers internos e os campos externos 0.1.
2. **R1B-3 — Hosted Tool e Remote Canonical:** transportar fase e causa de forma
   estruturada, sem parsing de `str(exc)`.
3. **R1B-4 — Write Lease:** preservar `UNKNOWN` depois da tentativa mutável e
   eliminar o fallback sem hash.
4. **R1B-5 — observabilidade:** projetar root code, phase, mutation state e
   recovery sem agregar texto diagnóstico livre.

Leitores 0.1/0.2 devem entrar antes de cada producer 0.2. Um producer emite um
único resultado por request; não serão publicados comentários duplicados para
compatibilidade.

## 6. Rollback e condição de retirada

R1B-1 é aditiva e não possui cutover. O rollback remove o core, schema, registro
e testes sem tocar em comentários, receipts ou artifacts existentes.

Quando os producers forem migrados, rollback volta somente a escrita para 0.1;
os leitores dual-version permanecem. Leitura de 0.1 só pode ser retirada após
uma boundary histórica explícita do Agent Bus e fixtures arquivadas, porque os
comentários antigos são evidência persistente e não devem ser reescritos.

## 7. Provas desta fatia

- schema e validator alinhados e registrados em Operational Semantics;
- hash determinístico e boundaries negativas;
- ordem raiz-para-wrapper preservada;
- duplicate causes e tampering rejeitados;
- post-write ambiguity não pode ser `BLOCKED` nem replay `SAFE`;
- os quatro envelopes 0.1 possuem projeção fail-closed;
- hash vazio e campos extras de envelopes legados são rejeitados;
- semantics check/coverage e suíte completa permanecem obrigatórios.

Ficam fora desta fatia: mudança de workflow, emissão 0.2, `PENDING`, `WAITING`,
CycleProgress, seal, ordenação assíncrona, provider adapter e qualquer mutação
de ProjectState, Work, Coordination ou `main`.

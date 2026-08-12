# ADR-0004 — Coordination Leases experimentais sobre autoridade Git

- Status: proposed / experimental
- Date: 2026-08-11
- Scope: GitOps only
- Supersedes: none

## Contexto

O paralelismo UI × Engine já provou bom isolamento quando ownership de paths é explícito, mas ainda existe um custo temporal em superfícies raras e compartilhadas. Ownership responde quem normalmente modifica uma área; não responde quem está modificando um recurso agora.

O experimento precisa oferecer intent informativo e leases exclusivas de escrita por branch, path/glob e arquivo, com aquisição em lote all-or-nothing, TTL, renew, release, recuperação de órfãos, auditoria e enforcement por tooling + CI. Nenhum mecanismo pode criar autoridade semântica sobre Engine, Scene Core ou UI.

A regra não entra em `AGENTS.md` enquanto o experimento não provar concorrência real e recuperação de falha.

## Alternativas avaliadas

### GitHub Actions concurrency

Adequado para serializar jobs/workflows por grupo, mas o objeto coordenado é a execução de Actions. Não fornece por si só lease dinâmica de edição por arquivo/glob, owner de sessão, TTL renovável ou estado consultável pelo agente antes da primeira escrita.

### Rulesets / branch protection / path restrictions

Úteis como proteção estática e gate de integração. Restrições de path são políticas previamente configuradas; não representam posse temporária, intent, heartbeat ou troca dinâmica de owner entre agentes.

### Environments / deployment protection

Adequados para proteger deploys e aprovações de jobs que referenciam um environment. Não modelam edição concorrente de recursos do repositório.

### Serviço/banco externo de locks

Resolveria CAS e relógio central de forma direta, mas adicionaria nova infraestrutura, credenciais, disponibilidade e uma segunda autoridade operacional antes de necessidade demonstrada.

### Branch Git dedicada + estado versionado + avanço linear da ref

Mantém uma autoridade central única no próprio repositório, auditável por Git, sem merge com feature branches. A API de refs do GitHub permite atualização não-forçada que só aceita avanço fast-forward. Se duas aquisições constroem commits irmãos sobre o mesmo head observado, apenas o primeiro pode avançar a ref; o segundo deixa de ser fast-forward e deve reobservar.

## Decisão experimental

Adotar inicialmente:

```text
authority branch: coordination/leases
state path:       ops/coordination/leases.json
history:          commits lineares da authority branch
mutation rule:    read H -> validate -> build child(H) -> update ref force=false -> readback
```

A branch `coordination/leases` não é feature branch, não entra em `main` e não contém mudanças de produto. Ela é uma autoridade operacional independente.

Nenhuma mutação pode usar merge commit na authority branch. Cada transição válida possui exatamente um parent: o head observado durante o plano.

## Modelo de estado

O estado corrente terá schema próprio, inicialmente `CoordinationState 0.1`:

```json
{
  "schemaVersion": "CoordinationState 0.1",
  "revision": "<authority-head-sha>",
  "intents": [],
  "leases": []
}
```

`revision` é informativa no payload; a identidade efetiva da revisão é o SHA da ref observada. O commit Git é também a trilha histórica. Não duplicar um event log permanente dentro de `main`.

Identidade mínima de owner:

```json
{
  "role": "ui|engine|gitops|other",
  "session": "opaque-session-id",
  "branch": "branch-name",
  "pr": 123
}
```

`session` é a unidade de posse para renew/release. `branch` e `pr`, quando disponíveis, são a identidade verificável pela CI.

## Recursos e normalização

Recursos canônicos são tipados:

```text
file:<repo-relative-posix-path>
path:<repo-relative-glob>
branch:<branch-name>
```

Regras:

1. paths são relativos à raiz, sem `.`/`..`, sem barra inicial e com `/` como separador;
2. arquivos não aceitam metacaracteres de glob;
3. globs usam uma gramática própria e versionada, inicialmente `*`, `?` e `**`, sempre ancorada na raiz;
4. recursos de um lote são normalizados, deduplicados e ordenados lexicograficamente antes da validação;
5. a ordem fornecida pelo cliente não altera o resultado.

## Conflitos

- `file:A` conflita com `file:A`;
- `file:A` conflita com `path:G` quando `A` casa com `G`;
- `path:G1` conflita com `path:G2` quando a interseção é demonstravelmente não vazia pela resolução determinística suportada;
- padrões cuja interseção não possa ser decidida com segurança no subset inicial falham fechados como potencial conflito;
- `branch:B` conflita com outro `branch:B`;
- branch locks formam namespace próprio e protegem mutação da ref/integração dessa branch; não substituem file/path leases globais.

File/path leases são globais ao repositório, independentemente da feature branch, porque seu objetivo é impedir trabalho simultâneo que só apareceria como conflito na integração posterior.

## Aquisição all-or-nothing e deadlock

O cliente nunca adquire recursos um a um. O lote inteiro é validado contra um único snapshot da autoridade e gera no máximo um commit.

Fluxo:

```text
observe H
normalize + sort R
expire logically stale leases for conflict evaluation
validate every resource in R
construct complete next state
create child commit of H
attempt force=false ref update
readback ref and state
```

Se qualquer recurso conflitar, nada é adquirido. Se a ref avançar entre observe e apply, a tentativa perde a corrida e deve reobservar o novo head. Não existe espera segurando aquisição parcial; portanto não há ciclo de hold-and-wait entre lotes.

## TTL e relógio

A autoridade de tempo será o `Date` observado em resposta autenticada da API GitHub, não o relógio local do agente. O tooling remoto deve obter `authorityNow` antes de decidir expiração. Se o tempo remoto não puder ser observado, mutações e decisões que dependem de TTL falham fechadas.

A lease armazena `acquiredAt`, `expiresAt`, `ttlSeconds` e `renewedAt` derivados de `authorityNow`.

Parâmetros iniciais sugeridos para o experimento:

- TTL default: 60 min;
- renew recomendado: a cada 15 min enquanto houver escrita ativa;
- TTL máximo inicial: 4 h.

O heartbeat não é daemon obrigatório: `renew --mine` é uma transação explícita e pode ser chamado pelo agente antes de continuar trabalho de longa duração.

## Intent

Intent é informativa e não bloqueia aquisição ou escrita. Possui owner, recursos, razão, criação e expiração curta para evitar lixo operacional. Conflitos de intent podem ser exibidos como warning, nunca como lease implícita.

## Renew, release e órfãos

- renew só afeta leases da mesma `session`;
- release por recurso exige owner da mesma sessão;
- `release --mine` remove somente leases da sessão corrente;
- lease expirada deixa de bloquear imediatamente na avaliação lógica;
- limpeza física de expiradas pode ocorrer junto da próxima mutação segura;
- PR encerrada pode motivar cleanup somente se `owner.pr`, branch e sessão ainda correspondem ao registro observado;
- cleanup nunca usa apenas nome de branch como prova para remover lease de outra sessão.

## Recuperação após reinício

O agente recupera o estado lendo `coordination/leases` e apresenta suas leases ao informar o mesmo session id. Sem o session id anterior, pode observar leases, mas não renová-las/liberá-las como owner; deve aguardar TTL ou usar break-glass administrativo auditado.

## CI e identidade

O gate recebe diff + `github.head_ref` + PR number. Para cada recurso compartilhado modificado que esteja sob lease válida:

- passa se a lease pertence à branch/PR corrente;
- falha `LOCK_OWNERSHIP_VIOLATION` se pertence a outro owner;
- ausência de lease não é erro na fase experimental, salvo teste deliberado de enforcement.

`session` continua sendo necessária para mutações de owner, mas a CI não depende de segredo de sessão para verificar autoria de uma PR.

## Fail closed

Aquisição, renew, release, break e qualquer guard antes de escrita retornam erro quando não conseguem observar a authority branch, a revisão, o relógio remoto ou o readback.

`intent` pode degradar para indisponível sem bloquear desenvolvimento porque é estritamente informativa; não pode ser inventada localmente como se tivesse sido publicada.

## Break-glass administrativo

Será uma operação explícita de GitOps, não um overwrite silencioso:

```text
agent lock break <resource> --expected-revision <sha> --reason <text>
```

Requisitos:

- role operacional GitOps;
- revisão esperada explícita;
- razão não vazia;
- evento identificado no commit de autoridade;
- mesma regra de CAS/readback;
- nunca `force=true`.

Break-glass não faz parte do primeiro happy path e só será habilitado depois dos testes de owner/release.

## Detached HEAD / CI

Leitura da autoridade não depende da branch local. Em CI, branch/PR são resolvidos pelos eventos GitHub (`GITHUB_HEAD_REF`, refs do evento). O estado remoto continua sendo a fonte de lease. Detached HEAD é suportado para validação e gate.

## Transporte

O protocolo conceitual independe de `git push`. O caminho preferencial pode usar Git/`gh`; quando transporte convencional não estiver disponível, o mesmo contrato pode ser realizado por Git objects + refs da API GitHub: blob/tree/commit com parent explícito e atualização não-forçada da ref.

A indisponibilidade de todos os transportes de observação remota bloqueia mutações de lease.

## Enforcement em duas camadas

### Tooling oficial

Antes da primeira escrita declarada em recurso compartilhado:

```text
observe authority -> resolve resource -> unlocked OR owned-by-session ? -> allow : WRITE_BLOCKED_BY_LEASE
```

### CI

A CI reobserva a autoridade e compara o diff da PR. Tooling contornado não transforma violação em integrável.

O gate começa experimental e não se torna required repository-wide antes dos critérios A/B/C do plano.

## Rollback completo para Git Ops 1.2

Enquanto experimental:

1. não alterar `AGENTS.md` com obrigação permanente;
2. não mudar `operations.toolboxPhase` em `project.json`;
3. desabilitar/remover o gate experimental;
4. remover comandos experimentais da toolbox antes de merge, se a hipótese falhar;
5. preservar ou arquivar `coordination/leases` apenas como evidência;
6. Git Ops 1.2 continua funcional sem consumir essa autoridade.

Nenhuma reversão de Engine/UI é necessária.

## Operações deliberadamente fora da automação

- arbitragem semântica de produto;
- scheduler/fila geral de agentes;
- lock automático de toda árvore tocada pela branch;
- force update da authority ref;
- quebra administrativa implícita;
- poda destrutiva de branches;
- publicação de `main` como efeito colateral de leases.

## Critério para aceitar esta ADR

`proposed` só vira `accepted` se os testes provarem:

1. exatamente um vencedor em aquisição simultânea real;
2. lote atômico;
3. perda de corrida detectada por ref drift;
4. TTL/renew/release corretos;
5. tooling bloqueando lease alheia;
6. CI detectando bypass;
7. recuperação de órfão;
8. nenhuma mudança semântica em produto.

Até lá, esta ADR documenta uma hipótese executável, não política permanente.

## Referências externas avaliadas

- GitHub REST — Git references: https://docs.github.com/en/rest/git/refs
- GitHub Actions — concurrency: https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
- GitHub rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GitHub deployments/environments: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

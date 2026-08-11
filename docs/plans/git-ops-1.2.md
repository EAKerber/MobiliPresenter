# Git Ops 1.2 — higiene de branches e estado entre incrementos

Status: implementation

## Motivação

O Git Ops 1.1 resolveu coerência de checkpoint/PR, mas ainda assumia que sempre existia uma branch Developer ativa e deixava sanitização de branches totalmente fora da toolbox.

Dois fatos concretos justificam o 1.2:

1. uma PR Developer pode ser integrada/fechada antes de o próximo recorte existir, tornando incorreto manter `activeDevelopmentBranch` e `prNumber` antigos como fato atual;
2. branches temporárias, experimentais e superseded se acumulam, e uma poda manual sem plano verificável aumenta o risco de apagar UI, documentação, evidência ou rollback ainda úteis.

## Estado entre incrementos

`ProjectState 1.0` continua sendo o schema nominal, mas passa a aceitar explicitamente:

```json
{
  "git": {
    "activeDevelopmentBranch": null
  },
  "development": {
    "prNumber": null,
    "phase": "between-increments"
  }
}
```

`activeDevelopmentBranch` e `prNumber` são uma identidade conjunta: ambos existem ou ambos são `null`.

O estado entre incrementos não significa ausência de trabalho paralelo. Branches que precisam permanecer operacionais ou duráveis ficam em:

```text
git.preserveBranches
```

Essa lista é política estruturada, não uma segunda cópia do histórico Git.

## `agent git prune-plan`

Novo comando read-only:

```bash
python3 tools/agent.py git prune-plan
python3 tools/agent.py git prune-plan --json
```

O comando observa:

- todas as refs locais em `refs/heads` e seus SHAs;
- `controlBranch` e `publishedBranch`;
- `activeDevelopmentBranch`, quando existir;
- `git.preserveBranches`;
- heads de PRs abertas, quando `gh` estiver disponível.

Ele classifica cada branch como:

- `keep` — branch protegida, rollback/archive ou head de PR aberta;
- `candidate` — prefixo efêmero/slice com forte sinal de descarte (`tmp/`, `engine/`, `deploy/`, `agent/`);
- `archive-first` — história `variant/` que não deve ser apagada antes de possuir âncora histórica;
- `review` — não existe evidência suficiente para decisão automática.

Nenhuma ref é modificada.

## Identidade do plano

A saída contém:

```text
GitPrunePlan 0.1
planHash: sha256(...)
```

O hash cobre, entre outros fatos:

- SHA do branch de controle;
- inventário completo de branches e SHAs;
- heads de PRs abertas observados;
- classificação resultante.

Portanto qualquer movimento/criação/remoção de ref produz outro plano.

Uma eventual transição destrutiva futura deve aceitar somente um `planHash` previamente aprovado e observar novamente os mesmos fatos antes de aplicar qualquer delete.

## Proteção remota obrigatória

Se `gh` não estiver disponível ou a leitura de PRs abertas falhar:

```text
remoteOpenPrProtection: false
applyEligible: false
```

O plano continua útil para diagnóstico, mas não pode ser tratado como autorizado para aplicação destrutiva.

Isso impede que uma branch ativa de outro agente seja apagada simplesmente porque o ambiente local não conseguiu observar o GitHub.

## Reversibilidade

A classificação considera três casos:

- branches já contidas em uma autoridade durável: exclusão futura é compensável pelo histórico Git enquanto o commit permanecer alcançável;
- `variant/*`: exige âncora `archive/*` antes da remoção das refs operacionais;
- rollback/evidência: permanecem protegidos explicitamente.

A toolbox 1.2 não implementa `prune --apply`. A recorrência da poda já justifica automatizar a observação e o planejamento; a execução destrutiva só deve ser automatizada depois que esse contrato provar estabilidade em uso real.

## Contextos Git válidos

`verify` aceita:

- `main`/branch de controle-publicação;
- branch Developer ativa, quando existir;
- branches listadas em `git.preserveBranches`;
- branches `ops/git-ops-*` durante evolução da própria toolbox.

Uma branch aleatória continua retornando `UNEXPECTED_BRANCH`.

## Checkpoint

`checkpoint --apply` continua limitado à branch Developer ativa.

Quando o projeto está entre incrementos, tentar aplicá-lo retorna:

```text
CHECKPOINT_NO_ACTIVE_DEVELOPMENT
```

Nenhuma branch de UI ou operações assume implicitamente o papel de Developer.

## Gates GO-1.2

- `GO12-01`: estado ativo Git Ops 1.1 continua válido quando inclui os novos campos exigidos;
- `GO12-02`: estado `between-increments` com branch/PR nulas é válido;
- `GO12-03`: identidade parcial branch/PR é rejeitada;
- `GO12-04`: branches paralelas preservadas passam `git-context` sem virar Developer ativa;
- `GO12-05`: `prune-plan` protege control/published/preserve/open-PR;
- `GO12-06`: `variant/*` nunca vira candidato direto; exige `archive-first`;
- `GO12-07`: alteração de qualquer SHA muda `planHash`;
- `GO12-08`: ausência de observação remota produz `applyEligible=false`;
- `GO12-09`: não existe comando destrutivo de poda no 1.2;
- `GO12-10`: `status`, `doctor`, `verify`, `checkpoint` e `handoff` permanecem compatíveis.

## Próxima evolução possível

Somente depois de pelo menos duas podas reais usando `prune-plan` sem ambiguidade recorrente considerar:

```text
agent git prune --plan-hash <HASH> --apply
```

Essa evolução deverá obrigatoriamente implementar:

```text
observe -> compare plan hash -> validate protected refs -> apply -> readback
```

e interromper em qualquer `REF_DRIFT`, `OPEN_PR_CHANGED` ou `PLAN_HASH_MISMATCH`.

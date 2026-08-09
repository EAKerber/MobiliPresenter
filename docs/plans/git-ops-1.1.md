# Git Ops 1.1 — coerência de estado e handoff determinístico

Status: implementation  
Branch de prova: `renderer/fixed-view-realistic-v1`

## Objetivo

Evoluir o bootstrap Phase 1 sem transformar a toolbox em uma segunda plataforma Git.

O problema observado que justifica este incremento é concreto: `ops/state/project.json` permaneceu em `R-01` enquanto a PR já havia chegado a `R-07`.

## Autoridades preservadas

- política permanente: `AGENTS.md`;
- estado operacional: `ops/state/project.json`;
- histórico: Git;
- estado remoto de PR/CI: GitHub, apenas observado;
- artifact publicado: `snapshot/mobile/manifest.json`.

Nenhum comando deve duplicar esses fatos em uma base paralela.

## Comandos

### `status`

Read-only. Deve mostrar estado declarado, Git observado e, quando solicitado, PR/CI remotos.

### `doctor`

Read-only. Verifica Python, Git, worktree/origin e disponibilidade opcional de `gh`.

### `verify`

Read-only. Além dos gates Phase 1, valida:

- branch observada é `activeDevelopmentBranch`, `controlBranch` ou `publishedBranch`;
- `development.plan` existe;
- `development.prNumber` é válido quando há branch ativa dedicada;
- com `--remote`, PR aberta corresponde à branch/base e head observados;
- CI remota é classificada como `green | pending | failed | unknown`, sem transformar `pending` do próprio workflow em falso erro.

### `checkpoint`

Mutação limitada a `ops/state/project.json`.

Por padrão é dry-run. Exige `--apply` para escrever.

Entrada mínima:

```text
agent checkpoint --to FH-01 --next implement-fidelity-overlay [--phase fidelity-harness]
```

Precondições de `--apply`:

- worktree Git válido;
- branch atual = `activeDevelopmentBranch`;
- worktree limpo antes da escrita;
- estado atual válido.

Pós-condições:

- escrita atômica;
- readback do JSON;
- diff do estado exibido;
- commit/publicação continuam sujeitos ao protocolo Git normal e readback independente.

### `handoff`

Read-only. Deriva um snapshot de:

- project state;
- Git observado;
- verify;
- commits/diff desde `controlBranch`, quando disponíveis;
- PR/CI remotos quando `--remote` estiver disponível.

Não grava documentação automaticamente.

## Não escopo

- merge automático;
- push/publish genérico;
- poda automática;
- rollback automático;
- mutação de PR;
- tentar inferir checkpoint a partir do código.

## Gates

- `GO-01`: comandos Phase 1 continuam compatíveis.
- `GO-02`: `checkpoint` sem `--apply` não altera bytes.
- `GO-03`: `checkpoint --apply` rejeita branch errada/worktree sujo.
- `GO-04`: readback após escrita corresponde exatamente ao estado proposto.
- `GO-05`: `handoff --json` é JSON válido e não muta o repo.
- `GO-06`: `verify` detecta branch inesperada.
- `GO-07`: observação remota indisponível retorna `unknown`, não inventa green.
- `GO-08`: CI executa tests da toolbox + `verify` + `handoff --json`.

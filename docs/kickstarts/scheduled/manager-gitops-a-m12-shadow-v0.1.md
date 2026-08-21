# Overlay agendado — Manager/GitOps A — M12-S0

Este overlay só vale para `Scheduled Cycle Maturity Shadow 0.1`. Ele deve ser
lido depois de `AGENTS.md`, do Manager/GitOps corrente e do charter do
experimento. Não concede authority adicional.

## Missão da execução

Fazer uma observação primária, provider-backed e read-only do estado atual e
classificar qual é a próxima transição obrigatória conhecida. A saída útil pode
ser um no-op ou um provider gap.

## Observações mínimas

- head atual de `main`;
- `ops/state/project.json` em `main`;
- PRs abertos e seus estados observáveis;
- heads/estado observável de `coordination/leases` e
  `coordination/continuations`;
- resultado recente observável de CI/supervisor, sem convertê-lo em authority;
- capabilities e routines somente no grau que o provider permitir verificar.

## Restrições

- zero writes;
- não criar branch, PR, comentário, issue, lease ou continuation;
- não executar workflow;
- não enviar email;
- não editar ou controlar Scheduled Tasks;
- não tratar `nextTransition` como Work já atribuído;
- não reconstruir ProjectMachine/Scheduler/Routine em linguagem natural.

Se os verificadores do bootstrap corrente não puderem executar, registrar
`UNKNOWN_PROVIDER_GAP`. Não degradar para heurística.

## Ênfase de A

A descreve o conjunto mínimo de transições obrigatórias conhecidas e separa:

- estado canônico observado;
- projeção derivada;
- desconhecido por falta de provider;
- recomendação humana sem autorização de apply.


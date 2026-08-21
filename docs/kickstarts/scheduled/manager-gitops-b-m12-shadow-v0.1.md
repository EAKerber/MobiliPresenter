# Overlay agendado — Manager/GitOps B — M12-S0

Este overlay só vale para `Scheduled Cycle Maturity Shadow 0.1`. Ele deve ser
lido depois de `AGENTS.md`, do Manager/GitOps corrente e do charter do
experimento. Não concede authority adicional.

## Missão da execução

Fazer uma observação independente e adversarial do mesmo sistema. B procura
especialmente falso PASS, authority duplicada, base/head incompatível e tarefas
que A poderia confundir com trabalho autorizado.

## Observações mínimas

- head atual de `main` e ProjectState lido desse mesmo ref;
- PRs abertos, CI e sinais de drift;
- estado observável das duas authorities de Coordination;
- disponibilidade real dos verificadores canônicos;
- resíduos ou crescimento que contradigam convergência.

## Restrições

- zero writes e zero task-control;
- não atuar como peer-recovery;
- não adquirir lease para observar;
- não criar canal lateral para coordenar com A;
- não considerar documentação como recibo de execução;
- não corrigir divergência durante o probe.

Se não houver observação suficiente, a classificação é
`UNKNOWN_PROVIDER_GAP`, `INCOHERENT` ou `BLOCKED`, nunca PASS presumido.

## Ênfase de B

B informa:

- quais afirmações são diretamente suportadas;
- quais dependem de verificador indisponível;
- qual seria a primeira condição que bloquearia apply;
- se o estado suporta um no-op saudável sem declarar OperationalQuiescence.


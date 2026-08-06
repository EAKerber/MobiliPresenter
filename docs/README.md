# Documentação do MobiliPresenter

Esta árvore separa fatos do sistema, decisões aceitas, propostas em discussão e material histórico. Um agente novo não deve tratar todos os documentos como igualmente autoritativos.

## Ordem de leitura

1. `README.md` — versão publicada e URL canônica;
2. `AGENTS.md` — governança, limites e protocolo Git;
3. `docs/current/BASELINE-V7-I5.md` — capacidades e limites comprovados;
4. `docs/planning/SCOPE-REASSESSMENT.md` — fase atual e perguntas abertas;
5. `docs/planning/DECISION-LOG.md` — decisões tomadas durante o planejamento.

## Classes documentais

### `current/`

Fatos verificados sobre a linha de base atual. Não contém desejos futuros nem decisões ainda abertas.

### `planning/`

Hipóteses, alternativas e decisões pendentes. Todo documento desta pasta deve declarar seu status. Nada aqui autoriza implementação automaticamente.

### `decisions/`

ADRs e decisões aceitas. Uma decisão só entra nesta pasta depois de aprovação explícita ou integração de uma PR que registre essa aprovação.

### `history/`

Evidências recuperadas das entregas ZIP, linhagem de versões, correções e técnicas anteriormente exploradas. Material histórico não prevalece sobre `current/` ou `decisions/`.

## Regra de autoridade

Em caso de conflito:

```text
contrato executável e teste atual
→ decisão aceita
→ baseline current
→ planejamento
→ histórico
```

Dados físicos, comerciais ou construtivos desconhecidos continuam `null`, `unverified` ou equivalentes. Documentação não deve converter inferência em fato.

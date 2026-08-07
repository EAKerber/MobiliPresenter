# Documentação do MobiliPresenter

Esta árvore separa fatos do sistema, decisões aceitas, propostas e material histórico.

## Esta branch

`variant/fixed-view-modular-showcase` é uma linha alternativa sem intenção de merge. A documentação autoritativa da variante começa em `docs/variant/README.md`.

## Ordem de leitura da variante

1. `README.md`;
2. `AGENTS.md`;
3. `docs/variant/README.md`;
4. `docs/variant/SCOPE.md`;
5. `docs/variant/DECISIONS.md`;
6. `docs/variant/REFERENCE-INVENTORY.md`;
7. `docs/variant/MEASUREMENTS.md`;
8. `variant/fixed-view/README.md`.

## Classes documentais herdadas

- `current/` — baseline verificada da linha V7;
- `planning/` — discussão da linha principal;
- `history/` — evidências recuperadas;
- `variant/` — decisões e contratos desta linha alternativa.

## Autoridade na variante

```text
teste e contrato em variant/fixed-view
→ docs/variant/DECISIONS.md
→ docs/variant/SCOPE.md
→ inventário de referências
→ planejamento herdado
→ histórico
```

Dados desconhecidos permanecem `null`, `unverified` ou equivalentes.

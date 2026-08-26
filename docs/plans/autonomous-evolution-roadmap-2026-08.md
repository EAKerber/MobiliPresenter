# MobiliPresenter — mapa direcional de evolução autônoma

Status: planejamento não autoritativo  
Origem: reconciliação das linhas M0–M12 e M9–M16  

Este documento preserva **direção, dependências conceituais e critérios de maturidade**. Ele não registra checkpoint corrente, recorte ativo, próxima transição, inventário de capabilities ou estado de implementação.

Para estado corrente, use exclusivamente:

- `ops/state/project.json` — checkpoint/direção operacional;
- `coordination/continuations` — Work e continuidade;
- `coordination/leases` — ownership temporário;
- `ops/semantics/registry.json` e policies — capabilities/surfaces/semântica corrente;
- Git/PR/CI/evidence — implementação e qualificação observáveis.

A história dos recortes concluídos permanece no Git, PRs e evidências correspondentes; ela não é duplicada aqui.

Fontes de planejamento preservadas:

- `docs/plans/project-machine-m0-m12-original-source.md`;
- `docs/plans/autonomous-evolution-architecture-v0.1.md`;
- `docs/plans/m9-m13-closure-v0.1.md`;
- evidências experimentais e closures versionadas no repositório/Git.

## Invariantes direcionais

1. Mudança significativa segue `observe -> plan -> validate -> apply -> readback -> receipt -> sanitize`.
2. Um fato mutável possui uma authority e um writer canônico.
3. Representação derivada nunca vira authority por conveniência.
4. Nondeterminism pode propor; somente política determinística pode autorizar.
5. `UNKNOWN` nunca equivale a `PASS`.
6. O paved path deve ser o caminho mais curto que preserve os invariantes.
7. Quiescence exige observação suficiente, coerência e ausência de transição obrigatória conhecida; não é apenas fila vazia.
8. Autonomia nasce em shadow, passa por isolamento/limites e só então pode receber authority estreita.
9. Superfícies constitucionais nunca são promovidas automaticamente.
10. O agente declara intenção/contexto de alto nível; detalhes mecânicos devem ser derivados deterministicamente quando uma contract existente puder fazê-lo.
11. Antes de criar uma entidade persistente, prefira remover, derivar ou unir quando owner, lifecycle e trust boundary já forem os mesmos.

## Linha de maturidade

A sequência abaixo expressa dependência conceitual, não estado corrente nem assignment.

### Fundação operacional

O ecossistema precisa de authorities explícitas, writers canônicos, Project Machine, Work/continuations, Coordination, capability lifecycle, branch lifecycle, Semantic Registry, Agent Cycle e evidence/readback verificáveis.

Essas estruturas só justificam permanência enquanto reduzirem ambiguidade operacional sem criar uma fonte concorrente de verdade.

### Interface governada do agente

A operação do agente deve convergir para uma entrada/saída simples composta por primitives existentes:

```text
begin -> discover/plan -> governed tools -> close
```

O objetivo não é criar uma nova “work session authority”. É fazer Agent Cycle, Semantic Brief, Agent Tools, lifecycle/ownership, execution trace, writers e receipts comporem naturalmente uma sessão governada.

Evoluções desta linha devem priorizar:

- reduzir IDs/heads/provider decisions que o agente precisa montar manualmente;
- reutilizar `GitMutationBundle`/writers existentes para mudanças multi-path;
- resolver LogicalCapability para ToolSurface/provider sem criar authority paralela;
- tornar fechamento capaz de detectar obrigações deixadas pelo próprio trabalho;
- manter `UNKNOWN` e post-write ambiguity visíveis;
- remover compatibility paths quando suas condições de morte forem satisfeitas.

### Reflection e Operational Quiescence

Reflection só é elegível quando o sistema consegue provar que não há trabalho obrigatório conhecido e que observations/authorities relevantes são suficientemente coerentes.

Quiescence permanece read-only e não deve virar justificativa automática para criar trabalho.

### Hypothesis lifecycle

Hipóteses são propostas não autoritativas com deduplicação, evidência, owner, validade e condição de morte. A existência de hipótese não concede execução nem prioridade.

### Experiment lifecycle e deathcycle

Experimentos devem possuir escopo limitado, critérios de entrada/saída, evidence e cleanup. Resultado negativo é conhecimento; experimento sem justificativa de persistência deve morrer ou ser arquivado.

### Capability evolution

Promoção de capability exige evidência e política separadas de mera disponibilidade. Deprecation/retirement devem ser first-class, com consumer discovery e remoção verificável de resíduos.

### Prova longa

Autonomia mais ampla só é considerada após execução prolongada sem authority creep, false PASS, leaks de ownership, resíduos sem destino ou dependência crescente de manutenção narrativa.

## Regra de leitura

Este roadmap responde **“que maturidade buscamos e quais dependências conceituais existem?”**.

Ele deliberadamente não responde:

- “onde estamos agora?”;
- “qual recorte está ativo?”;
- “qual é a próxima transição?”;
- “que capability/tool existe hoje?”;
- “quem possui o trabalho atual?”.

Essas respostas já possuem fontes estruturadas próprias. Se este documento voltar a copiar tais fatos, a cópia deve ser removida em vez de receber um novo mecanismo de sincronização.

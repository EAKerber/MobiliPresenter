# UI / UX — MobiliPresenter

Esta pasta é a entrada documental corrente da frente de interface de produto.

## Baseline corrente

A arquitetura de interação atualmente integrada é o **Guided Configurator UI 0.3**:

1. `Módulos`
2. `Acabamentos`
3. `Acessórios`
4. `Resumo`

A cena permanece persistente e a câmera fixa continua sendo invariante de produto. O detalhe de módulo é contextual: no desktop usa uma superfície editorial que compartilha a tela com a cena; no mobile usa sheet contextual.

`ops/state/project.json` é a authority do estado operacional e registra esse recorte como baseline integrado. `nextTransition` não é assignment de trabalho.

## Ordem de leitura e precedência

1. input explícito e vigente do usuário;
2. `ops/state/project.json` e invariantes correntes;
3. contratos executáveis, especialmente `../../viewer-next/src/api/ui-contract.ts`;
4. `guided-configurator-v0.3.md` para o fluxo atualmente integrado;
5. `decisions-v0.1.md`, considerando somente decisões `accepted` não marcadas como `superseded`;
6. `style-guide-v0.1.md` para princípios/tokens ainda compatíveis com o baseline corrente;
7. `../architecture/ui-engine-parallel-development.md` para fronteiras de ownership — sua topologia de branches v0.1 é histórica;
8. `../adr/0003-technical-presentation-contract.md` para autoridade e proveniência do conteúdo técnico.

Quando um documento histórico conflitar com o fluxo integrado posterior, o documento posterior explicitamente integrador prevalece dentro do mesmo escopo.

## Status dos documentos principais

- `guided-configurator-v0.3.md` — **baseline técnico integrado; validação UX humana ainda não equivale a linguagem final imutável**;
- `decisions-v0.1.md` — **log corrente com entradas históricas explicitamente superseded**;
- `style-guide-v0.1.md` — **baseline visual histórico**; princípios, tokens, acessibilidade e fronteiras continuam úteis, mas a navegação `Módulos / Cores / Acessórios` e a ficha inferior fixa são superseded pelo Guided Configurator 0.3;
- `../architecture/ui-engine-parallel-development.md` — **contrato histórico de paralelização v0.1**; ownership/import boundaries permanecem relevantes, mas `integration/viewer-parallel-v0.1` não é base corrente automática.

## Regra corrente para uma nova slice

A base de uma nova slice nunca deve ser escolhida por um SHA/branch hardcoded neste diretório. Ela deve ser derivada do estado Git corrente e, quando aplicável, de ProjectState, continuation/handoff e coordenação vigente.

Trabalho normal de UI permanece limitado a:

- `viewer-next/src/ui/**`;
- assets exclusivamente visuais da UI;
- testes comprovadamente UI-only;
- `docs/ui/**`.

Se faltar capacidade no `ViewerUiContract`, a UI não cria catálogo, semântica ou estado paralelo: registra a dependência e encaminha mudança coordenada de contrato.

## Dependências conhecidas

A issue #22 continua sendo dependência para metadata editorial completa de módulos e catálogo genérico de acessórios configuráveis. Isso não bloqueia ideação, estrutura, empty states ou apresentação honesta de indisponibilidade; bloqueia inventar opções que o contrato ainda não publica.

Responsive Fixed-Frame cruza fronteiras: layout/alocação de viewport são UI-owned; qualquer nova semântica de câmera/projeção/frame ou API compartilhada exige coordenação. A câmera fixa e a proibição de pan/zoom/focus heurísticos permanecem invariantes.

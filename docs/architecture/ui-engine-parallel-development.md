# Desenvolvimento paralelo UI × Engine

Status: contrato operacional 0.1

## Objetivo

Permitir que a interface de produto e a engine do MobiliPresenter evoluam em paralelo sem depender dos mesmos arquivos de implementação e sem transformar a UI em autoridade de estado, geometria, materiais ou conteúdo técnico.

A fronteira é o diretório `viewer-next/src/api/**`.

A UI consome contratos e snapshots. A engine implementa e adapta esses contratos.

## Superfície pública interna

Contrato atual:

- `viewer-next/src/api/ui-contract.ts`
- versão: `ViewerUiContract 0.1.0`

Adapter da engine:

- `viewer-next/src/api/ui-adapter.ts`

A UI recebe:

- catálogo de módulos e opções controladas;
- snapshot corrente por alias, sem IDs internos obrigatórios;
- visibilidade e acabamento corrente por módulo;
- pedra e iluminação globais correntes;
- `TechnicalPresentationPackage` do módulo selecionado;
- SVGs técnicos já derivados para as vistas disponíveis;
- comandos para seleção, visibilidade, acabamentos, pedra, iluminação e reset.

A UI não precisa importar `viewer-state`, presets, query, renderer, Scene Core ou Technical Catalog.

## Regra de ownership por paths

### Agente de UI

Pode modificar normalmente:

- `viewer-next/src/ui/**`
- assets exclusivamente visuais da UI
- testes exclusivamente da UI

Deve preservar o entry contract existente de montagem:

```ts
mountRuntimeControls(host, api) -> { refresh, dispose }
```

Não modifica diretamente:

- `viewer-next/src/api/**`
- `viewer-next/src/runtime/**`
- `viewer-next/src/renderer/**`
- `viewer-next/src/presentation/**`
- `viewer-next/src/fixtures/**`
- `scene-core/**`

### Agente de Engine

Pode modificar normalmente:

- `viewer-next/src/api/**`
- `viewer-next/src/runtime/**`
- `viewer-next/src/renderer/**`
- `viewer-next/src/presentation/**`
- `viewer-next/src/fixtures/**`
- `scene-core/**`
- testes de engine/contratos/fidelity

Não modifica durante trabalho normal:

- `viewer-next/src/ui/**`

### Arquivos de integração congelados

Após o baseline paralelo ser criado, estes paths só mudam em PR explicitamente de integração:

- `viewer-next/src/bootstrap.ts`
- `viewer-next/index.html`
- `viewer-next/package.json`
- `viewer-next/tsconfig.json`
- `.github/workflows/**` quando a alteração afetar ambos os fluxos

Isso evita que duas frentes usem `bootstrap.ts` ou arquivos de build como ponto informal de coordenação.

## Regra de imports

Dentro de `viewer-next/src/ui/**`, a UI pode importar:

- `../api/**`;
- outros módulos dentro de `src/ui/**`;
- bibliotecas de apresentação que não carreguem autoridade da engine.

Imports diretos de `runtime`, `renderer`, `presentation`, `fixtures` ou `main` são proibidos por teste automatizado.

O adapter em `src/api/**` funciona como anti-corruption layer: alterações internas podem ser absorvidas ali sem quebrar a UI.

## Compatibilidade do contrato

Durante `ViewerUiContract 0.1.x`:

- mudanças devem ser aditivas ou compatíveis;
- IDs existentes não mudam silenciosamente;
- remoções ou mudanças semânticas exigem nova minor contract version (`0.2.0`);
- quando possível, o adapter mantém compatibilidade durante a transição para que a branch da UI não precise parar.

A UI não deve depender de propriedades internas não declaradas no contrato, mesmo que estejam acessíveis no objeto runtime bruto.

## Fluxo Git para trabalho paralelo

Depois de CI verde deste contrato, criar uma branch-base imutável de coordenação:

`integration/viewer-parallel-v0.1`

Essa branch nasce do SHA validado do contrato.

A partir dela:

- UI: `ui/<recorte>`;
- engine: `engine/<recorte>`.

As duas frentes devem abrir PR contra `integration/viewer-parallel-v0.1`, não uma contra a outra.

Como os ownerships são disjuntos, a ordem de integração deixa de ser requisito funcional. Quando uma PR for integrada primeiro, a outra deve apenas atualizar a base e repetir CI; conflitos em paths fora da lista de integração congelada são tratados como violação do contrato de ownership, não como ocorrência normal.

Nenhuma dessas branches promove automaticamente conteúdo para `main`.

## Mudança de contrato durante trabalho paralelo

Quando a engine precisar de uma capacidade nova para a UI:

1. engine adiciona ou versiona o contrato em `src/api/**`;
2. adiciona teste do novo comportamento;
3. CI fecha;
4. a mudança entra primeiro em `integration/viewer-parallel-v0.1`;
5. a UI atualiza sua base e passa a consumir a nova capacidade.

A UI não implementa fallback de domínio para capacidades ausentes. Enquanto um controle estiver `declared-not-bound`, ele pode ser apresentado como indisponível ou omitido, mas não simulado com estado paralelo.

## Conteúdo técnico

A UI recebe a ficha técnica através do contrato, incluindo:

- medidas compiladas a partir da autoridade física;
- acabamentos permitidos;
- componentes e avisos autorados;
- dependências;
- `TechnicalPresentationPackage`;
- assets SVG técnicos derivados.

A UI decide composição, responsividade, hierarquia, motion e linguagem visual. Não recalcula cotas e não gera componentes técnicos a partir do render.

## Gates

O baseline paralelo só é considerado válido quando:

1. Viewer Next TypeScript passa;
2. testes TPC passam;
3. testes `ui-contract` passam;
4. `src/ui/**` não possui import proibido;
5. smoke VRC-02 continua verde;
6. fidelity/readability herdados não regridem;
7. `main` permanece intocada.

# Desenvolvimento paralelo UI × Engine

Status: **contrato histórico de paralelização 0.1; fronteiras de ownership/import continuam aplicáveis, topologia de branches não é regra corrente automática**

## Objetivo

Permitir que a interface de produto e a engine do MobiliPresenter evoluam em paralelo sem depender dos mesmos arquivos de implementação e sem transformar a UI em autoridade de estado, geometria, materiais ou conteúdo técnico.

A fronteira é o diretório `viewer-next/src/api/**`.

A UI consome contratos e snapshots. A engine implementa e adapta esses contratos.

## Precedência operacional atual

A branch `integration/viewer-parallel-v0.1` descrita abaixo foi uma base de coordenação válida para o ciclo histórico que originou este contrato. **Ela não deve ser escolhida automaticamente como base de uma nova slice.**

A base corrente deve ser derivada do estado Git observado e, quando aplicável, de `ops/state/project.json`, continuation/handoff e coordenação vigente. `ProjectState.nextTransition` descreve uma transição, não constitui assignment para qualquer role.

Nenhuma regra desta seção autoriza UI ou Engine a contornar leases/continuations ou a trabalhar sobre uma branch histórica apenas porque ela aparece neste documento.

## Superfície pública interna

Contrato de referência deste documento:

- `viewer-next/src/api/ui-contract.ts`
- versão original do contrato: `ViewerUiContract 0.1.0`

Adapter da engine:

- `viewer-next/src/api/ui-adapter.ts`

A UI recebe, conforme o contrato executável corrente:

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
- testes comprovadamente exclusivos da UI

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

### Arquivos de integração compartilhados

Estes paths exigem coordenação explícita quando a alteração afetar ambos os fluxos:

- `viewer-next/src/bootstrap.ts`
- `viewer-next/index.html`
- `viewer-next/package.json`
- `viewer-next/tsconfig.json`
- `.github/workflows/**`

Isso evita que duas frentes usem `bootstrap.ts` ou arquivos de build como ponto informal de coordenação.

## Regra de imports

Dentro de `viewer-next/src/ui/**`, a UI pode importar:

- `../api/**`;
- outros módulos dentro de `src/ui/**`;
- bibliotecas de apresentação que não carreguem autoridade da engine.

Imports diretos de `runtime`, `renderer`, `presentation`, `fixtures` ou `main` são proibidos por teste automatizado.

O adapter em `src/api/**` funciona como anti-corruption layer: alterações internas podem ser absorvidas ali sem quebrar a UI.

## Compatibilidade do contrato

Durante uma mesma linha compatível do `ViewerUiContract`:

- mudanças devem ser aditivas ou compatíveis;
- IDs existentes não mudam silenciosamente;
- remoções ou mudanças semânticas exigem versionamento explícito de contrato;
- quando possível, o adapter mantém compatibilidade durante a transição para que a UI não precise reconstruir autoridade de domínio.

A UI não deve depender de propriedades internas não declaradas no contrato, mesmo que estejam acessíveis no objeto runtime bruto.

## Fluxo Git histórico de trabalho paralelo

No ciclo v0.1, após CI verde do contrato, foi criada a branch-base imutável de coordenação:

`integration/viewer-parallel-v0.1`

Historicamente, a partir dela:

- UI: `ui/<recorte>`;
- engine: `engine/<recorte>`.

As duas frentes abriam PR contra `integration/viewer-parallel-v0.1`, não uma contra a outra. Essa topologia cumpriu sua função de coordenação naquele ciclo e permanece documentada como evidência histórica.

**Regra corrente:** novas branches/slices não devem repetir essa topologia por padrão. Devem partir da base determinada pelo estado Git/ProjectState/continuation/handoff observado no momento da abertura. Nenhuma branch histórica promove automaticamente conteúdo para `main` nem se torna base atual por permanência no repositório.

## Mudança de contrato durante trabalho paralelo

Quando uma capacidade nova for necessária para a UI:

1. a necessidade é registrada como dependência coordenada;
2. a autoridade responsável adiciona/versiona o contrato em `src/api/**`;
3. adiciona testes do novo comportamento;
4. CI fecha;
5. a UI atualiza sua base conforme a topologia Git corrente e passa a consumir a nova capacidade.

A UI não implementa fallback de domínio para capacidades ausentes. Enquanto um controle estiver `declared-not-bound` ou indisponível, ele pode ser apresentado honestamente como indisponível ou omitido, mas não simulado com estado paralelo.

## Conteúdo técnico

A UI recebe a ficha técnica através do contrato, incluindo:

- medidas compiladas a partir da autoridade física;
- acabamentos permitidos;
- componentes e avisos autorados;
- dependências;
- `TechnicalPresentationPackage`;
- assets SVG técnicos derivados.

A UI decide composição, responsividade, hierarquia, motion e linguagem visual dentro de sua autoridade local. Não recalcula cotas e não gera componentes técnicos a partir do render.

## Gates

A fronteira UI × Engine só é considerada preservada quando:

1. Viewer Next TypeScript passa;
2. testes TPC/contrato relevantes passam;
3. testes `ui-contract` passam;
4. `src/ui/**` não possui import proibido;
5. smoke/UI relevante continua verde;
6. fidelity/readability herdados não regridem quando aplicáveis;
7. integração em `main` ocorre deliberadamente após reobservação do estado corrente.

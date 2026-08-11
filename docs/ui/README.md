# UI / UX — MobiliPresenter

Esta pasta é a entrada documental da frente de interface de produto.

## Leitura obrigatória

1. `style-guide-v0.1.md` — linguagem visual, layout, componentes, responsividade, acessibilidade e gates.
2. `decisions-v0.1.md` — decisões de UX já tomadas e seu racional.
3. `../architecture/ui-engine-parallel-development.md` — ownership de paths, imports permitidos e fluxo paralelo UI × Engine.
4. `../adr/0003-technical-presentation-contract.md` — autoridade e proveniência do conteúdo técnico.
5. `../../viewer-next/src/api/ui-contract.ts` — contrato executável consumido pela UI.

## Escopo atual da frente de UI

- shell do viewer com sidebar à esquerda;
- paginação lateral `Módulos / Cores / Acessórios`;
- lista de módulos com visibilidade separada de inspeção;
- ficha técnica inferior quando um módulo está selecionado;
- apresentação responsiva de `TechnicalPresentationPackage` e SVGs técnicos derivados;
- linguagem visual comercial/técnica inspirada nas referências fornecidas pelo usuário;
- desktop e mobile;
- sem definir neste recorte a linguagem final de highlight do módulo dentro do render.

## Regra operacional

Esta frente nasce do baseline validado:

`integration/viewer-parallel-v0.1` @ `277b0fc088f5e32de236782b293f39feea6e163e`

Trabalho normal de UI deve permanecer em:

- `viewer-next/src/ui/**`;
- assets exclusivamente visuais da UI;
- testes exclusivamente da UI;
- `docs/ui/**` para documentação visual/UX.

Não reabrir contratos de runtime, renderer, presentation ou Scene Core dentro da implementação de UI. Se faltar capacidade no `ViewerUiContract`, a necessidade deve ser registrada e encaminhada como mudança de contrato coordenada.

## Relação com VRC-02

A UI VRC-02 existente é uma prova funcional validada, não o design final. Preserve seus contratos de montagem e lifecycle enquanto a linguagem visual é substituída incrementalmente.

# UI / UX — MobiliPresenter

Esta pasta é a entrada documental da frente de interface de produto.

## Leitura obrigatória

1. `style-guide-v0.1.md` — linguagem visual, layout, componentes, responsividade, acessibilidade e gates.
2. `decisions-v0.1.md` — decisões de UX já tomadas, incluindo as revisões v0.2 de placeholders, scroll, rail/drawer e seleção × ficha.
3. `promotional-detail-v0.2.md` — recorte executável atual e seus gates.
4. `../architecture/ui-engine-parallel-development.md` — ownership de paths, imports permitidos e fluxo paralelo UI × Engine.
5. `../adr/0003-technical-presentation-contract.md` — autoridade e proveniência do conteúdo técnico.
6. `../../viewer-next/src/api/ui-contract.ts` — contrato executável consumido pela UI.

## Escopo atual da frente de UI

- viewer com rail compacto e drawer recolhível para `Módulos / Cores / Acessórios`;
- lista de módulos com visibilidade separada de inspeção;
- seleção do módulo independente da expansão/recolhimento da ficha;
- ficha inferior com direção editorial/promocional e uma vista técnica dominante;
- placeholders explícitos quando informação esperada estiver ausente;
- apresentação responsiva de `TechnicalPresentationPackage` e SVGs técnicos derivados;
- auditoria de scroll baseada em `reflow → disclosure → seleção/paginação → scroll`;
- desktop e mobile;
- sem definir neste recorte a linguagem final de highlight do módulo dentro do render;
- sem resolver neste recorte o enquadramento definitivo do canvas em telas pequenas.

## Regra operacional

Esta frente nasceu do baseline validado:

`integration/viewer-parallel-v0.1` @ `277b0fc088f5e32de236782b293f39feea6e163e`

Trabalho normal de UI deve permanecer em:

- `viewer-next/src/ui/**`;
- assets exclusivamente visuais da UI;
- testes exclusivamente da UI;
- `docs/ui/**` para documentação visual/UX.

Não reabrir contratos de runtime, renderer, presentation ou Scene Core dentro da implementação de UI. Se faltar capacidade no `ViewerUiContract`, a necessidade deve ser registrada e encaminhada como mudança de contrato coordenada.

## Relação com VRC-02

A UI VRC-02 existente é uma prova funcional validada, não o design final. Preserve seus contratos de montagem e lifecycle enquanto a linguagem visual é substituída incrementalmente.

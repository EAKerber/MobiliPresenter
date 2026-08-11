# UI-02 — Promotional Detail & Compact Controls v0.2

Status: **implementação em validação**  
Branch: `ui/promotional-detail-v0.2`  
Base: `integration/viewer-parallel-v0.1`

## Objetivo

Transformar a primeira UI funcional de produto em uma apresentação comercial interativa mais próxima das referências fornecidas pelo usuário, sem ultrapassar as fronteiras de `ViewerUiContract`/TPC e sem alterar câmera, renderer ou Scene Core.

O critério de direção de arte é: **inspirar visualização e compra por composição, escala de artes e hierarquia editorial; informar com rigor sem parecer um painel administrativo.**

## Mudanças deste recorte

### 1. Seletores compactos

- a superfície persistente passa a ser um rail estreito;
- `Módulos`, `Cores` e `Acessórios` abrem um drawer contextual;
- clicar novamente no destino ativo recolhe o drawer;
- selecionar um módulo recolhe o drawer automaticamente;
- o render recupera a largura liberada.

### 2. Seleção independente da ficha

- `selectedModuleAlias` continua sendo autoridade do Viewer Runtime;
- `detailExpanded` é estado puramente visual local;
- fechar a ficha não limpa a seleção;
- a seleção permanece como contexto para Cores/Acessórios;
- uma nova seleção pode abrir a ficha automaticamente.

### 3. Ficha promocional

- identidade e resumo ocupam cabeçalho editorial;
- uma vista técnica é dominante;
- as demais vistas usam seletor compacto sem carrossel obrigatório;
- ferragens/componentes recebem bloco próprio;
- especificações extensas usam disclosure antes de scroll;
- materiais/acabamentos e instalação permanecem visíveis como blocos semânticos.

### 4. Placeholders

Quando o contrato não fornecer informação esperada pela composição, preservar o espaço com placeholder explícito, por exemplo:

- `Descrição comercial a definir`;
- `Artes técnicas a definir`;
- `Especificações a definir`;
- `Componentes a definir`;
- `Acabamento a definir`.

Placeholder não cria autoridade de domínio e nunca recebe valor aproximado/inferido.

### 5. Auditoria de scroll

Ordem obrigatória antes de adicionar overflow:

`reflow → disclosure → seleção/paginação → scroll`

Superfícies aceitas neste recorte:

- drawer lateral: scroll vertical somente se a lista exceder a viewport;
- ficha: uma única superfície vertical principal;
- cards: sem scroll interno;
- galeria técnica: sem scroll horizontal no desktop; seletor quebra linha;
- mobile: preservar uma única superfície de conteúdo rolável na ficha e uma no drawer quando aberto, nunca aninhadas.

Scrollbars desktop usam thumb fino, neutro e mais contrastado em hover. Em touch, comportamento nativo é preservado.

## Não escopo

- solução definitiva de enquadramento do canvas em telas pequenas;
- panning/fit-to-scene/focus-to-module;
- miniaturas reais dos módulos antes da expansão coordenada do contrato;
- catálogo de puxadores antes do binding público de acessórios;
- linguagem final de highlight no render.

## Gates

1. `1366×768`: a vista técnica dominante e as medidas principais aparecem sem scroll imediato da ficha.
2. Rail compacto permanece utilizável com drawer fechado.
3. Fechar a ficha preserva seleção.
4. Checkbox continua independente de inspeção.
5. Módulo sem TPC abre composição com placeholders, não ficha vazia.
6. Cards não possuem scroll interno.
7. `prefers-reduced-motion` preserva funcionalidade.
8. UI continua importando apenas `../api/**` e código local.
9. Gates Viewer Next / fidelity não regridem.
10. Capturas desktop e mobile são produzidas para inspeção humana.

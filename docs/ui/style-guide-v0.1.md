# MobiliPresenter — UI/UX Style Guide 0.1

Status: **baseline de produto para a frente de UI**  
Branch de autoria: `ui/style-guide-v0.1`  
Baseline de coordenação: `integration/viewer-parallel-v0.1` @ `277b0fc088f5e32de236782b293f39feea6e163e`  
Contrato consumido: `ViewerUiContract 0.1.0`  
Escopo: viewer de câmera fixa, navegação/configuração lateral e ficha técnica de módulo selecionado.

## 1. Objetivo

Este documento transforma as referências comerciais fornecidas pelo usuário e os contratos já validados do MobiliPresenter em uma linguagem visual e de interação consistente para a interface de produto.

A UI deve parecer uma **apresentação técnica comercial de mobiliário**, não um painel de engenharia, um editor CAD ou um configurador genérico de e-commerce.

A referência editorial é usada para hierarquia, densidade, contraste, relação entre imagem e informação técnica e linguagem de cards. Ela não deve ser reproduzida como uma arte raster fixa.

A implementação final permanece HTML/CSS/TypeScript responsivo, consumindo dados estruturados e SVGs técnicos derivados.

## 2. Autoridades e fronteiras

Este style guide define somente apresentação e interação.

Autoridades externas à UI:

- geometria, cotas e visibilidade física: Scene Core;
- conteúdo técnico não derivável: Technical Catalog;
- materiais/presets: Appearance Catalog;
- estado corrente: Viewer Runtime;
- pacote pronto para apresentação: `TechnicalPresentationPackage`;
- superfície pública interna para a UI: `viewer-next/src/api/**`.

A UI **não**:

- recalcula cotas;
- infere medidas a partir de pixels;
- cria uma lista própria de cores/acabamentos;
- promove objetos Three.js a componentes técnicos;
- inventa fatos ausentes;
- cria um segundo store para capacidades `declared-not-bound`;
- altera câmera, geometria ou material físico como efeito colateral de interação visual.

Dentro de `viewer-next/src/ui/**`, imports devem permanecer limitados ao contrato público interno (`../api/**`), módulos locais de UI e bibliotecas estritamente de apresentação.

## 3. Princípios de produto

### P1 — Render first

No estado normal, o render é o elemento dominante. A interface deve ser discreta o suficiente para que a composição de mobiliário continue sendo o produto principal.

### P2 — Detail without leaving context

Selecionar um módulo não navega para outra página. O render permanece visível e perde somente a área necessária para revelar a ficha técnica.

### P3 — Editorial técnico, não dashboard

Informações técnicas devem ser organizadas como uma ficha editorial: título forte, vistas, medidas, construção, acabamento, ferragens e avisos. Evitar tabelas administrativas, excesso de badges e grids de métricas genéricos.

### P4 — Separar visibilidade de inspeção

Na lista de módulos:

- checkbox controla mostrar/ocultar;
- miniatura, nome e restante da linha abrem/selecionam o módulo para inspeção.

Essas duas ações nunca devem compartilhar o mesmo alvo de clique.

### P5 — Progressive disclosure

O usuário vê primeiro o que precisa para decidir e comparar. Proveniência, detalhes secundários e avisos extensos podem ser expandidos sob demanda.

### P6 — Quiet precision

A linguagem visual usa neutros quentes, linhas finas, tipografia clara e hierarquia forte. Estados interativos são perceptíveis sem competir com o render.

### P7 — No invented completeness

Ausência de dado não é preenchida por texto genérico. O bloco pode ser omitido ou apresentado explicitamente como indisponível quando isso for útil ao usuário.

## 4. Estrutura principal da interface

### 4.1 Desktop — estado normal

```text
┌──────────────────────┬──────────────────────────────────────────────┐
│                      │                                              │
│   CONFIG SIDEBAR     │                    RENDER                    │
│                      │               ocupa toda a direita           │
│   módulos / cores /  │                                              │
│   acessórios         │                                              │
│                      │                                              │
└──────────────────────┴──────────────────────────────────────────────┘
```

Regras:

- sidebar persistente à esquerda;
- render ocupa toda a coluna direita;
- nenhuma ficha técnica inferior quando `selectedTechnicalPresentation === null`;
- câmera e enquadramento permanecem estáveis.

### 4.2 Desktop — módulo detalhado

```text
┌──────────────────────┬──────────────────────────────────────────────┐
│                      │                                              │
│   CONFIG SIDEBAR     │                    RENDER                    │
│                      │                  ~56–60%                     │
│                      │                                              │
│                      ├──────────────────────────────────────────────┤
│                      │          MODULE TECHNICAL DETAIL             │
│                      │                  ~40–44%                     │
└──────────────────────┴──────────────────────────────────────────────┘
```

A transição é uma mudança de layout, não uma navegação de cena.

Regras:

- preservar camera contract e estado do render;
- render redimensiona suavemente;
- ficha técnica aparece abaixo;
- trocar o módulo selecionado substitui o conteúdo da ficha sem fechar/reabrir o shell;
- fechar a ficha devolve toda a altura da direita ao render.

### 4.3 Larguras iniciais

Tokens de layout recomendados:

```css
--ui-sidebar-width: clamp(280px, 22vw, 344px);
--ui-detail-min-height: 300px;
--ui-render-detail-ratio: 0.58;
--ui-content-max: 1680px;
```

Esses valores são baseline, não autoridade geométrica. Ajustes devem ser validados visualmente em 1366×768, 1440×900, 1920×1080 e viewport mobile.

## 5. Paginação do painel lateral

A sidebar possui três páginas irmãs:

1. **Módulos**
2. **Cores**
3. **Acessórios**

A troca de página deve permanecer acessível enquanto o conteúdo interno rola.

### 5.1 Navegação preferida

No desktop, usar uma barra fixa no rodapé da sidebar com três destinos. No mobile, a mesma estrutura pode virar uma navegação inferior do sheet/painel.

Requisitos:

- rótulo sempre visível; ícone é complementar;
- estado ativo reconhecível sem depender apenas de cor;
- não usar swipe horizontal como único método de navegação;
- manter posição de rolagem por página quando isso não gerar comportamento surpreendente.

### 5.2 Página Módulos

Estrutura do item:

```text
[checkbox] [miniatura]  Módulo 03
                        Inferior da pia
```

Baseline:

- altura mínima do item: 68 px;
- thumbnail: 52–60 px;
- checkbox: alvo interativo mínimo 44×44 px;
- linha inteira, exceto checkbox, abre/seleciona o módulo;
- estados visível/oculto não podem depender apenas de opacity da miniatura;
- módulos ocultos permanecem localizáveis e selecionáveis pela lista se o contrato permitir.

### 5.3 Página Cores

A página mostra somente opções vindas do catálogo/contrato.

Estrutura preferida:

- contexto/alvo corrente no topo;
- swatch/material preview;
- nome do acabamento;
- indicação do acabamento corrente;
- opções incompatíveis omitidas ou explicitamente indisponíveis conforme o contrato.

Não manter uma paleta hardcoded na camada de UI.

### 5.4 Página Acessórios

Acessórios devem usar cards visuais compactos, agrupados por família quando houver dados suficientes.

Cada opção pode conter:

- miniatura/ícone;
- nome;
- estado corrente;
- disponibilidade;
- informação curta de compatibilidade quando necessária.

Capacidades ainda `declared-not-bound` não devem aparentar ser funcionais.

## 6. Ficha técnica do módulo

A ficha é a tradução responsiva da linguagem das referências comerciais.

### 6.1 Ordem visual

1. identidade do módulo;
2. acabamento corrente e dimensão principal;
3. vistas técnicas;
4. especificações/construção;
5. componentes/ferragens/elétrica;
6. acabamentos permitidos;
7. avisos e dependências;
8. proveniência, somente quando explicitamente aberta.

### 6.2 Header técnico

Exemplo:

```text
MÓDULO 03
Inferior da pia
1200 × 760 × 530 mm                 Cinza Gianduia
```

Regras:

- alias/número é eyebrow;
- título editorial é o elemento textual dominante;
- medidas usam algarismos tabulares quando disponíveis;
- acabamento atual é secundário ao título, mas visível sem rolar;
- não duplicar o mesmo dado em chips, cards e texto corrido simultaneamente.

### 6.3 Vistas técnicas

Vistas derivadas pelo TPC são assets, não reconstruções da UI.

No desktop:

- faixa horizontal ou grid de 3–5 vistas conforme espaço;
- cada vista possui título curto;
- fundo neutro claro;
- dimensões permanecem legíveis;
- uma vista pode ser ampliada sem perder a ficha inteira.

No mobile:

- uma vista dominante por vez;
- scroll/snap horizontal pode ser usado como complemento;
- indicadores de paginação devem ser visíveis;
- zoom/modal é aceitável para leitura de cotas.

### 6.4 Blocos semânticos

Blocos são renderizados somente quando existem dados.

Famílias iniciais:

- Especificação;
- Construção;
- Ferragens;
- Elétrica/instalação;
- Acabamento;
- Dependências;
- Avisos.

Evitar um grid rígido que deixe caixas vazias apenas para manter simetria.

### 6.5 Notices

Mapeamento de severidade:

- `info`: neutro, sem ícone de alarme;
- `important`: destaque discreto;
- `warning`: cor semântica de aviso e ícone/label textual.

Nunca usar vermelho apenas para decoração editorial. Vermelho fica reservado a erro/risco/aviso real ou a futuras decisões explícitas de seleção no render.

## 7. Sistema visual

### 7.1 Paleta

A referência combina branco quente, cinzas/taupes e tipografia carvão. O baseline v0.1 adota:

```css
:root {
  --ui-bg-canvas: #f3f1ec;
  --ui-bg-surface: #faf9f5;
  --ui-bg-surface-raised: #ffffff;
  --ui-bg-subtle: #eee9e3;

  --ui-text: #1d1d1b;
  --ui-text-secondary: #625d58;
  --ui-text-muted: #817a73;

  --ui-border: #d8d1c8;
  --ui-border-strong: #bdb3a9;

  --ui-taupe: #8f8278;
  --ui-taupe-soft: #e5dfd8;

  --ui-accent: #c5a35a;
  --ui-accent-soft: #eee5d1;
  --ui-focus: #7a6231;

  --ui-danger: #842f23;
  --ui-danger-soft: #f3e3df;
  --ui-warning: #9a691f;
  --ui-warning-soft: #f5ead4;
}
```

Notas:

- o `--ui-accent` é de interação da UI; não define o highlight 3D do módulo;
- superfícies não devem ser branco puro em toda a tela;
- transparência e blur são opcionais e devem ser usados com parcimônia; a ficha técnica principal deve permanecer estável e legível sem depender de backdrop blur.

### 7.2 Tipografia

Duas funções tipográficas:

**UI/body**

```css
--ui-font-sans: Inter, ui-sans-serif, system-ui, -apple-system,
  BlinkMacSystemFont, "Segoe UI", sans-serif;
```

**Display técnico/editorial**

```css
--ui-font-display: "Barlow Condensed", "Arial Narrow", var(--ui-font-sans);
```

A fonte display só deve ser ativada quando estiver empacotada localmente ou já disponível no build. Não carregar fontes por CDN como dependência silenciosa.

Escala inicial:

```css
--ui-font-10: 0.625rem;
--ui-font-11: 0.6875rem;
--ui-font-12: 0.75rem;
--ui-font-13: 0.8125rem;
--ui-font-14: 0.875rem;
--ui-font-16: 1rem;
--ui-font-18: 1.125rem;
--ui-font-24: 1.5rem;
--ui-font-32: 2rem;
--ui-font-40: 2.5rem;
```

Regras:

- body principal não menor que 13 px no desktop e 14 px no mobile;
- labels auxiliares podem usar 10–11 px apenas com contraste adequado;
- títulos display usam peso alto e line-height curto;
- medidas e códigos devem preferir `font-variant-numeric: tabular-nums`.

### 7.3 Espaçamento

Escala base 4 px:

```css
--ui-space-1: 4px;
--ui-space-2: 8px;
--ui-space-3: 12px;
--ui-space-4: 16px;
--ui-space-5: 20px;
--ui-space-6: 24px;
--ui-space-8: 32px;
--ui-space-10: 40px;
--ui-space-12: 48px;
```

Preferir whitespace e divisores finos a múltiplos contêineres com borda.

### 7.4 Raios

```css
--ui-radius-sm: 8px;
--ui-radius-md: 12px;
--ui-radius-lg: 18px;
--ui-radius-xl: 22px;
--ui-radius-pill: 999px;
```

Cards editoriais usam `12–18px`. Pills são reservadas a chips, filtros e botões compactos.

### 7.5 Bordas e sombras

Bordas:

- 1 px por padrão;
- baixa opacidade/contraste;
- não empilhar borda + sombra pesada em cada bloco.

Sombras:

```css
--ui-shadow-float: 0 12px 36px rgba(29, 29, 27, 0.12);
--ui-shadow-panel: 0 -12px 32px rgba(29, 29, 27, 0.08);
```

Sombras servem para hierarquia de camada, não ornamentação.

## 8. Componentes e estados

### 8.1 Botões

- altura mínima: 40 px desktop, 44 px touch;
- primary: contraste alto, usado com parcimônia;
- secondary: superfície clara + borda;
- ghost: ações de baixa prioridade;
- danger: somente ação destrutiva real.

### 8.2 Segmented/tabs

Para Módulos/Cores/Acessórios:

- três destinos estáveis;
- largura igual ou distribuição clara;
- ativo com indicador estrutural (fundo/borda/underline + peso), não apenas cor;
- foco de teclado visível.

### 8.3 Checkbox de módulo

- checkbox nativo estilizado ou implementação acessível equivalente;
- label associada semanticamente;
- clique no checkbox não propaga seleção da linha;
- estado indeterminado só existe se houver significado real no contrato.

### 8.4 Module row

Estados:

- default;
- hover/focus;
- selected-for-detail;
- hidden;
- disabled/unavailable quando aplicável.

`selected-for-detail` e `hidden` são ortogonais.

### 8.5 Swatch

- mínimo visual 32×32 px;
- textura, quando disponível, é preferida a cor plana;
- nome textual sempre presente;
- borda adicional para acabamentos muito claros.

### 8.6 Technical card

- título curto;
- conteúdo com 1–4 fatos preferencialmente;
- ícone opcional, nunca obrigatório;
- não usar ilustração decorativa que possa ser confundida com dado técnico.

## 9. Motion

Motion deve explicar mudança de layout e estado.

Baseline:

```css
--ui-motion-fast: 140ms;
--ui-motion-base: 200ms;
--ui-motion-detail: 260ms;
--ui-ease-standard: cubic-bezier(.2, .8, .2, 1);
```

Regras:

- abrir ficha: resize/reveal coordenado em ~220–280 ms;
- trocar módulo com ficha aberta: crossfade curto ou troca direta, sem recolher o painel;
- navegação lateral: 140–200 ms;
- evitar spring exagerado;
- respeitar `prefers-reduced-motion`.

O render não deve receber animação de câmera como consequência da abertura da UI.

## 10. Responsividade

### >= 1024 px

- sidebar persistente;
- render à direita;
- ficha técnica inferior na coluna direita;
- vistas técnicas em grid/faixa horizontal.

### 720–1023 px

- sidebar mais estreita ou colapsável;
- preservar render como maior superfície;
- ficha técnica pode ocupar 45–50% da altura quando aberta;
- cards técnicos reduzem colunas antes de reduzir tipografia.

### < 720 px

Estrutura preferida:

```text
┌─────────────────────┐
│       RENDER        │
├─────────────────────┤
│ Módulos Cores Acess.│
├─────────────────────┤
│ conteúdo / detalhe  │
└─────────────────────┘
```

Regras:

- render permanece visível no topo quando possível;
- configuração vira sheet/painel inferior;
- ficha técnica rola independentemente;
- touch targets >=44 px;
- vistas técnicas favorecem uma por viewport;
- evitar hover como requisito de entendimento.

## 11. Acessibilidade

Mínimos v0.1:

- navegação completa por teclado;
- foco visível em todos os controles;
- `aria-pressed`/`aria-selected`/`aria-expanded` coerentes;
- labels explícitas para checkbox e botões icônicos;
- contraste WCAG AA para texto e controles essenciais;
- estado nunca transmitido apenas por cor;
- touch targets de pelo menos 44×44 px em mobile;
- suporte a `prefers-reduced-motion`;
- SVG técnico precisa de título/descrição ou fallback textual quando usado como conteúdo informativo.

## 12. Conteúdo e microcopy

Tom:

- conciso;
- comercial técnico;
- sem jargão de implementação;
- sem expor IDs internos de Scene Core ao usuário final.

Preferir:

- `Módulo 03 · Inferior da pia`
- `Ocultar módulo`
- `Mostrar módulo`
- `Cinza Gianduia`
- `1200 × 760 × 530 mm`

Evitar:

- `entityId`;
- `runtime override`;
- `frontPresetId`;
- `ScenePackage`;
- mensagens de debug em UI final.

Quando informação estiver ausente:

- omitir o bloco se a ausência não for relevante;
- usar `Informação técnica não disponível` apenas quando o usuário precisa saber que existe uma lacuna;
- não completar com inferência visual.

## 13. Integração com `ViewerUiContract 0.1.0`

A UI deve se orientar por:

- `getCatalog()` para módulos e opções controladas;
- `getSnapshot()` para seleção, visibilidade, acabamentos e ficha corrente;
- `selectedTechnicalPresentation` para conteúdo técnico;
- `selectedTechnicalViewAssets` para SVGs já derivados;
- comandos do contrato para mutação de estado.

A camada visual pode ter view-models locais **puramente derivados** para ordenar, agrupar ou adaptar o layout, desde que não criem autoridade de domínio.

## 14. Arquitetura CSS recomendada

Ao iniciar a implementação visual final, migrar o CSS técnico monolítico para:

```text
viewer-next/src/ui/
├── styles/
│   ├── tokens.css
│   ├── reset.css
│   ├── shell.css
│   ├── sidebar.css
│   ├── technical-detail.css
│   └── utilities.css
├── components/
│   ├── module-list.ts
│   ├── sidebar-pager.ts
│   ├── finish-selector.ts
│   ├── accessory-selector.ts
│   ├── technical-detail.ts
│   └── technical-views.ts
└── runtime-controls.ts
```

Isso é direção de implementação, não obrigação de framework. O contrato `mountRuntimeControls(host, api) -> { refresh, dispose }` deve permanecer preservado até uma transição explicitamente coordenada.

## 15. Gates visuais e de UX

Uma mudança de UI está pronta para review quando:

1. funciona em 1366×768 sem zoom do browser;
2. funciona em pelo menos um viewport mobile estreito;
3. abrir/fechar ficha não altera câmera nem estado físico;
4. checkbox de visibilidade e seleção da linha são ações independentes;
5. Módulos/Cores/Acessórios permanecem alcançáveis sem scroll até o fim da sidebar;
6. ficha técnica usa somente conteúdo do contrato/TPC;
7. vistas técnicas não são reconstruídas por heurística da UI;
8. nenhum dado desconhecido é inventado;
9. foco/teclado/touch targets passam inspeção básica;
10. `prefers-reduced-motion` não perde funcionalidade;
11. testes de fronteira de imports permanecem verdes;
12. smoke VRC-02 e gates de renderer/fidelity herdados não regridem.

## 16. Decisões explicitamente adiadas

Fora deste style guide 0.1:

- linguagem visual final do highlight de seleção dentro do render;
- animação de câmera;
- câmera livre/orbital;
- edição de geometria;
- editor de catálogo técnico;
- BOM de fabricação;
- criação automática de dados ausentes;
- escolha definitiva de uma fonte display externa;
- redesign do contrato público interno.

## 17. Relação com a UI técnica VRC-02

A UI técnica existente é tratada como **prova funcional substituível**.

Elementos aproveitáveis:

- tipografia sans/system como fallback;
- neutros quentes;
- radius moderado;
- estados `aria-pressed`;
- responsividade base;
- shell de montagem e lifecycle.

Elementos não promovidos automaticamente a design final:

- painel flutuante no canto direito;
- organização em botões numéricos simples;
- densidade e hierarquia atuais;
- launcher `Controles`;
- tratamento visual atual de seleção.

## 18. Fonte de verdade desta linguagem

- este arquivo: regras e tokens de UI v0.1;
- `docs/ui/decisions-v0.1.md`: decisões explícitas e racional;
- `docs/architecture/ui-engine-parallel-development.md`: ownership e trabalho paralelo;
- `docs/adr/0003-technical-presentation-contract.md`: autoridade do conteúdo técnico;
- `viewer-next/src/api/ui-contract.ts`: contrato executável consumido pela UI.

Quando houver conflito:

1. contratos executáveis e invariantes de domínio vencem;
2. ADRs/arquitetura vencem decisões puramente visuais;
3. este guide vence estilo ad hoc em CSS;
4. exemplos e mockups não alteram contrato sem decisão explícita.

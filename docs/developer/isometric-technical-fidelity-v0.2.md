# Isometric Technical Fidelity 0.2

## Objetivo

Melhorar a leitura das vistas isométricas técnicas sem criar nova autoridade geométrica. O recorte substitui a cotagem baseada em uma caixa auxiliar por guias derivadas do mesmo frame físico do módulo e organiza largura, profundidade e altura em lanes separadas.

## Authority

- geometria e frame físico: Scene Core;
- valores apresentados: política de dimensão nominal/geométrica já compilada no Technical Presentation Package;
- SVG e layout de cotas: representação derivada, sem autoridade própria.

## Mudanças

- `CompiledTechnicalViewGeometry` publica `dimensionGuides` projetadas;
- vistas isométricas recebem três guias: `width`, `depth`, `height`;
- as guias são normalizadas com exatamente a mesma translação usada pela geometria projetada;
- as guias não participam do bounding box da geometria e portanto não alteram escala física nem enquadramento lógico;
- o SVG geometry-derived reserva margem editorial específica para isométrica;
- altura usa lane à esquerda;
- largura usa lane inferior frontal;
- profundidade usa lane inferior/lateral;
- labels usam bounding boxes estimados e aumentam o offset da lane quando há colisão;
- a isométrica usa primitivas reais já compiladas, incluindo gavetas, portas e caixaria quando presentes;
- o antigo `dimension-summary` e a caixa auxiliar de cotas não são usados no caminho geometry-derived.

## Casos de validação

### Módulo 03

- isométrica contém `drawer-1` a `drawer-4`, `door-center`, `door-right` e elementos de caixaria;
- cotas exibidas separadamente: 1200 mm, 760 mm e 530 mm;
- labels de largura/profundidade/altura não podem ocupar praticamente o mesmo centro;
- saída repetida é determinística.

### Módulo 04

- continua tratado como painel/lateral, não como gabinete;
- isométrica apresenta 18 mm, 600 mm e 2400 mm usando o mesmo sistema de lanes.

## Limites explícitos

- não há hidden-line removal completo;
- ferragens continuam omitidas;
- não altera Scene Core, câmera, renderer 3D, UI product layout, zoom, PBR ou appliances;
- não promove nada para Netlify ou `main`.

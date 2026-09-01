# Technical Drawing System 0.1

## Objetivo

Gerar vistas técnicas vetoriais determinísticas a partir da geometria física já presente no Scene Core, mantendo explícita a separação entre geometria derivada e informação técnica autorada.

## Authorities

- geometria e coordenadas físicas: Scene Core;
- política de dimensão nominal/geométrica e fatos autorados: Technical Catalog;
- layout interno 390/400/400 do módulo 03: prancha técnica fornecida pelo usuário, preservado como `authored-internal-layout`;
- SVG: representação derivada, sem autoridade própria.

## Pipeline 0.1

O compilador projeta vértices reais para `width-height`, `depth-height`, `width-depth` e isométrica. Vistas ortográficas/isométricas previamente descritas como `scene-envelope` podem usar a geometria real quando ela está disponível; uma vista explicitamente `scene-geometry` continua fail-closed quando não houver projeção compilada.

O módulo 03 é o caso de validação principal: frontal, lateral e isométrica tornam-se geometry-derived. A vista interna continua autorada porque suas divisões técnicas não devem ser inventadas a partir da geometria.

O módulo 04 é tratado como painel/lateral e não precisa fingir que possui uma família de primitivas de frente de gabinete.

## SVG semântico

O SVG geometry-derived publica hooks de estilo como `primary-geometry`, `opening`, `extension-line`, `dimension-line`, `tick` e `dimension-label`. A UI pode alterar aparência sem recalcular coordenadas ou valores.

## Limites explícitos

O 0.1 não implementa remoção de linhas ocultas. A omissão `hidden-line-removal` é publicada nos assets geometry-derived relevantes. Ferragens também continuam fora da projeção técnica.

Não há alteração de Scene Core, câmera/fixed-frame, renderer 3D, zoom, PBR ou appliances neste recorte.

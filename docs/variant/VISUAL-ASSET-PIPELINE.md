# Pipeline visual provisório

## Objetivo

Entregar realismo em câmera fixa com composição modular, sem carregar a complexidade de uma matriz yaw × pitch.

## Camadas previstas

1. ambiente-base;
2. contexto fixo opcional: parede, eletros e arquitetura;
3. overlay por módulo;
4. variações de frente;
5. puxadores e abertura;
6. iluminação;
7. destaque de seleção;
8. hit map/máscara de clique.

## Assets por módulo

- `thumbnail` — miniatura realista e imediatamente reconhecível;
- `sceneOverlay` — módulo alinhado à câmera-base;
- `sceneHitMap` — região clicável;
- `detailHero` — render do detalhe;
- `technicalDiagram` — opcional;
- `frontMask` — região recolorível;
- `handleAnchors` — pontos de aplicação.

## Proveniência

Todo asset deve declarar:

- fonte;
- transformação;
- câmera;
- escala ou alinhamento;
- status de confiança;
- SHA-256;
- se é autoritativo, provisório ou apenas referência.

## Estratégia inicial

As primeiras imagens podem ser inferidas das referências existentes. O alinhamento deve usar uma única tela/coordenada de composição. A planta serve para envelope e plausibilidade, não para declarar precisão ausente.

## Cor

O objetivo futuro é evitar um módulo integral por cor. A decisão de implementação foi adiada. Caminhos preservados:

- máscara de frentes + transformação tonal;
- materiais/render parametrizado;
- overlays de frentes pré-renderizadas;
- composição híbrida.

Nenhum caminho é aprovado no I0.

## Realismo

A câmera fixa permite investir em:

- coerência de luz e sombra;
- oclusão;
- reflexos consistentes;
- contato com parede e bancada;
- continuidade entre módulos.

Realismo não autoriza distorcer medidas confirmadas quando elas existirem.

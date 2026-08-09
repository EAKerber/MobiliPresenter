# ADR-0002 — Boundaries do Scene Core 0.1

- Status: accepted
- Date: 2026-08-09

## Contexto

A auditoria recuperou uma base V7 com matemática métrica e composição, mas os corpos dos móveis dependiam de sprites. A linha fixed-view posterior preservou semântica útil, porém reduziu a geometria a apresentação 2D.

O novo produto exige câmera fixa e fidelidade contextual, além de hide/show determinístico de módulos, eletros e acessórios.

## Decisão

### Runtime

O Scene Core será implementado como pacote TypeScript isolado em `scene-core/`.

O runtime autoritativo será determinístico:
- geometria;
- câmera;
- estado;
- materiais;
- luz;
- projeções/masks.

LLM/image generation não decide geometria nem estado interativo.

### Ingestão

Ferramentas offline podem ser Python, especialmente para DXF, mas produzem contratos consumidos pelo Scene Core.

### Coordenadas

Sistema canônico:
- unidade `mm`;
- X para a direita;
- Y em profundidade;
- Z para cima;
- transforms rígidos explícitos.

### Câmera

A câmera pertence ao `ScenePackage`, é fixa por produto e perspectiva para a cena atual. Responsividade pertence a um `PresentationFrame` separado.

### Autoridade dimensional

`geometry-wins-for-assembly-preserve-nominal`.

### Extensibilidade

Novo cenário entra por dados/import/bindings. O core não pode depender de IDs ou layers específicos da cozinha atual.

## Consequências

Positivas:
- reaproveita a parte sólida da V7;
- evita renderer generativo como dependência de estado;
- permite UI posterior sem acoplamento;
- permite outros cenários.

Custos:
- exige adapter DXF/bindings;
- materiais reflexivos/translúcidos ainda exigem calibração visual;
- haverá duas linguagens no pipeline: Python offline e TypeScript runtime.

## Não decisões

Este ADR não escolhe:
- renderer artístico final;
- biblioteca WebGL;
- UI;
- intensidade/temperatura final das luzes;
- modelo 3D externo específico de eletro.

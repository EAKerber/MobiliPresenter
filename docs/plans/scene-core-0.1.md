# Scene Core 0.1 — Plano executável

Status: active  
Branch: `architecture/fixed-view-scene-core-v1`  
Base operacional: `main`  
Objetivo: substituir a fundação experimental raster por um núcleo métrico, determinístico e reutilizável para cenas de câmera fixa.

## Resultado esperado

Ao final do incremento, o repositório deve conseguir:

1. importar uma cena Promob/DXF de forma reproduzível;
2. separar ambiente, módulos, appliances/fixtures e acessórios em entidades estáveis;
3. preservar dimensões nominais e geométricas sem reconciliação silenciosa;
4. projetar a cena por uma câmera perspectiva fixa versionada;
5. calcular dependências/visibilidade sem conhecimento da UI;
6. trocar materiais e iluminação sem alterar geometria;
7. produzir conditioning determinístico: depth, normals, entity/material masks e edges;
8. compilar uma segunda cena mínima sem alterar o core.

## Limites de arquitetura

- câmera fixa é invariante de produto;
- `main` continua sendo a versão publicada;
- runtime interativo deve ser determinístico;
- LLM/image generation pode auxiliar authoring/enhancement, mas não é autoridade de geometria nem de estado;
- DXF/Promob governa montagem quando conflita com medidas nominais; ambas permanecem rastreáveis;
- layers são ownership/estado, não z-index raster;
- identificação semântica não depende de números `LAYERxx` no código;
- sombras de entidades removíveis não podem ser baked irreversivelmente em outra entidade.

## Organização técnica

`scene-core/` será um pacote TypeScript isolado do deploy V7.

Razões:
- a matemática V7 auditada já é TypeScript;
- o destino é browser;
- contratos e estado podem ser compartilhados entre importer, renderer e futura UI;
- ferramentas offline de ingestão DXF podem permanecer em Python e produzir dados para o core.

O pacote não participa do `deploy.py` V7 enquanto o incremento não for promovido.

## Slices

### SC-01 — Contracts & Metric Foundation

Entregas:
- pacote TypeScript isolado;
- `Vec3`, quaternion e rigid transforms;
- sistema canônico `mm / X-right / Y-depth / Z-up`;
- contratos iniciais de `ScenePackage`, `ModuleGeometry`, `EnvironmentGeometry`, `SourceBinding`;
- câmera fixa-perspectiva no contrato;
- política nominal/geometric;
- invariantes básicos;
- prova sintética de segunda cena.

Gates:
- TypeScript strict build;
- local→world→local round-trip;
- composição de transforms;
- IDs duplicados rejeitados;
- hosts inválidos rejeitados;
- fixture mínima sem IDs específicos do cenário atual.

### SC-02 — DXF Source Adapter

Entregas:
- inventário R12 `3DFACE`/`LINE`;
- fingerprints SHA-256;
- `SourceBinding`;
- AABB por selector;
- validação de unidade/eixos contra anchors conhecidos;
- saída intermediária determinística.

Gates:
- mesmo DXF + binding => mesmo digest;
- módulo 06 recupera 1200×800×400;
- lateral 04 recupera 18×610×2400;
- falha explícita em escala/eixo incompatível.

### SC-03 — Current Scene Geometry

Entregas:
- Environment Layer 0: parede branca + coluna;
- vidro;
- módulos piloto 02/03/06 e dependências necessárias 05/07;
- acessórios separáveis;
- slots de forno, micro e cuba;
- discrepâncias nominais registradas.

Gates:
- AABBs conhecidos dentro de tolerância;
- módulo 03 preserva nominal 1200 e geometric 1216,7;
- nenhuma dimensão provisional de 600 mm sobrevive.

### SC-04 — Fixed Camera

Entregas:
- câmera perspectiva fixa com intrínsecos normalizados;
- projection API;
- PresentationFrame separado da câmera;
- fixture de calibração.

Gates:
- landmarks de teste <= 5 px de erro máximo no baseline;
- resolução diferente não altera câmera física;
- camera state round-trip sem drift.

### SC-05 — Semantic State Layers

Entregas:
- Layer 0 environment;
- Layer 1 appliances/fixtures;
- Layer 2 modules;
- `visibilityIntent = auto|on|off`;
- host graph e effective visibility;
- event/state API independente da UI.

Gates:
- grafo acíclico;
- intenção explícita preservada ao esconder/reexibir host;
- scene JSON round-trip;
- renderer consome somente estado efetivo.

### SC-06 — Appearance Contracts & Conditioning

Entregas:
- `ApplianceDefinition`;
- `MaterialDefinition` + mapping policy;
- `LightingPolicy`;
- emitters semânticos;
- conditioning outputs determinísticos.

Gates:
- troca de material não muda geometry hash;
- troca de luz não muda transforms;
- emitters seguem host visibility;
- masks/depth/normals determinísticos.

### SC-07 — Portability Proof

Entregas:
- segunda cena sintética/minimal;
- import sem edição do core;
- relatório de onboarding.

Gate crítico:
- nenhuma regra de runtime depende de `module-02`, `module-06`, `LAYER79` ou dimensões da cozinha atual.

## Estratégia de commits

Cada slice deve produzir poucos commits semânticos:
1. contrato/estado;
2. implementação;
3. testes/fixtures/evidência.

Commits auxiliares podem ser squashados antes de PR.

## Estratégia de integração

- trabalhar em `architecture/fixed-view-scene-core-v1`;
- nenhuma alteração de runtime V7 em `main` durante o desenvolvimento;
- PRs intermediários para `main` somente quando forem infraestrutura segura e independente do viewer publicado;
- Scene Core só se torna candidato a publicação após SC-07.

## Critério de parada

Interromper e pedir input quando:
- duas interpretações geométricas plausíveis não puderem ser resolvidas por DXF/cotas;
- uma decisão de aparência/produto afetar o contrato;
- um formato de origem exigir engenharia reversa de alto custo;
- um gate falhar por falta de evidência externa, não por implementação.

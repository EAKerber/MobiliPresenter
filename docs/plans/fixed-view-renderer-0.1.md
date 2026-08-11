# Fixed View Renderer 0.1 — Plano executável

Status: active  
Branch: `renderer/fixed-view-realistic-v1`  
Base: `main`  
Fundação: Scene Core 0.1 integrado em `8c5159f782b3f67bfd86d0db847b0c6af64ff681`.

## Objetivo

Produzir o primeiro viewer determinístico de câmera fixa capaz de renderizar a cena métrica com materiais, eletros fantasia e iluminação controlada, mantendo a V7 publicada intacta até um gate visual posterior.

O render alvo fornecido pelo usuário é **style anchor**, não golden target: a implementação deve preservar composição/intenção e poder superar sua qualidade.

## Backend

Primeiro backend:
- Three.js `0.185.1`;
- `WebGLRenderer` WebGL2;
- Vite `8.1.5` para build do viewer;
- TypeScript `5.8.3`, alinhado ao Scene Core.

Motivos:
- Three.js documenta `WebGPURenderer` como ainda experimental;
- `WebGLRenderer` permanece mantido/recomendado para aplicações WebGL2;
- `PerspectiveCamera` suporta a base necessária para a câmera calibrada;
- `MeshStandardMaterial`/`MeshPhysicalMaterial` cobrem MDF, pedra, inox e vidro;
- `RoomEnvironment` + `PMREMGenerator` oferecem IBL neutra determinística para PBR;
- `EffectComposer`/`UnrealBloomPass` existem no backend WebGL para o pós restrito.

A dependência de Three deve ficar atrás de `viewer-next/src/renderer/three/`. Scene Core não importa Three.

## Limite de determinismo

O estado lógico e as entradas do renderer devem ser determinísticos. Pixel bit-a-bit entre GPUs/drivers diferentes NÃO é um invariante realista.

Gates visuais usam:
- geometria/câmera exatas;
- hashes de estado;
- invariantes de projeção;
- métricas de imagem com tolerância;
- smoke browser em backend fixado quando aplicável.

## Política de render

- render on-demand: redraw apenas em resize, material/light/state change;
- nenhuma rotação orbital;
- câmera física não muda para responsividade;
- `PresentationFrame` controla contain/crop;
- Scene Core continua autoridade de geometria/estado;
- renderer é uma projeção descartável do ScenePackage.

## Coordenadas

Scene Core é right-handed:
- X right;
- Y depth;
- Z up.

Three usa Y-up. Conversão canônica:

```text
Scene (x, y, z) -> Three (x, z, -y)
```

Essa transformação preserva handedness.

A câmera será convertida pela mesma função. O principal point off-center será aplicado por frustum perspectiva assimétrico; não será aproximado por câmera central.

## Aparência

### Material slots

Antes de renderizar, separar:
- slot semântico de geometria (`front`, `carcass`, `wall`, `stone`, `glass`...);
- `MaterialDefinition` concreto;
- override por entidade.

Isso permite mudar somente as frentes de um módulo sem mutar geometria ou trocar materiais globais.

### PBR

- MDF/pedra: `MeshStandardMaterial` inicialmente;
- vidro e materiais transmissivos: `MeshPhysicalMaterial`;
- inox poderá usar `MeshPhysicalMaterial` se anisotropia provar ganho visual justificável;
- texturas de cor em sRGB; mapas de roughness/normal sem color space;
- output sRGB/linear workflow conforme Three.

### Environment lighting

IBL neutra por `RoomEnvironment -> PMREM` como componente explícito do renderer, combinada ao `LightingPolicy`.

### Shadows

Somente a key light canônica lança shadow map no primeiro baseline. Fill/ambient e emitters locais não geram shadow map por padrão.

Razão: custo de shadow maps cresce com lights x casters; a cena fixa não justifica múltiplos passes de sombra inicialmente.

### Semantic emitters

LEDs/exaustor são luz real do render, não apenas glow pós.

### Post

Bloom é restrito a emitters. Nenhuma parte não emissiva entra no bloom por simples luminância acidental.

Seleção dourada futura permanece overlay de UI fora do render persistente.

## Appliances

Primeiro baseline usa geometrias paramétricas estáveis para as famílias já congeladas:
- washer;
- oven;
- cooktop;
- hood;
- microwave;
- fridge;
- kitchen sink;
- laundry tank quando sua posição visual for ativada.

Um modelo 3D externo pode substituir uma família somente após normalização de escala/origem/materiais e mantendo o mesmo ID de definição.

## Slices

### R-01 — Render Contract Hardening

- `AppearanceState` com bindings slot -> material e override por entidade;
- envelope alvo explícito para appliances standalone;
- accessory geometry real: pedras, rodapés e LED sob módulo 06;
- slot de hood/cooktop com status/evidência quando inferido;
- emitter de accessory;
- Scene Core continua sem dependência de Three.

Gates:
- override de um módulo não afeta outro;
- material change não muda geometry digest;
- accessory hide/show segue ownership;
- source envelopes de washer/fridge são preservados.

### R-02 — Three Scene Adapter

- package `viewer-next`;
- conversão Scene->Three;
- câmera off-axis exata;
- Object3D group por entityId;
- box/face primitives;
- visibility state -> Object3D.visible.

Gates:
- projeção Three vs Scene Core dentro de 0.1 px em landmarks;
- contagem/id dos grupos estável;
- hide/show não reconstrói geometria.

### R-03 — PBR Material Adapter

- material registry;
- slots/overrides;
- MDF, carcass, stone, inox, glass;
- UV/mapping policy básica.

Gates:
- troca de material restrita às entidades autorizadas;
- glass não escreve sombra/oclusão incorreta sobre módulos vizinhos;
- linear/sRGB workflow testado.

### R-04 — Parametric Appliances

- proxies estáveis das famílias;
- hosted fit por slot;
- standalone fit por target envelope;
- fridge/washer/oven/micro/sink primeiro;
- hood/cooktop quando slot ativo.

Gates:
- nenhum appliance altera módulo host;
- hide/show independente;
- fit não extrapola envelope sem policy explícita.

### R-05 — Canonical Lighting

- RoomEnvironment/PMREM;
- ambient/key/fill;
- key-only shadows;
- semantic emitters;
- exposure/tone mapping controlado.

Gates:
- esconder emitter remove contribuição local;
- iluminação não muda geometry hash;
- baseline sem pós é reproduzível por estado.

### R-06 — Constrained Post

- emitter mask;
- bloom leve;
- output pass/tone/color-space;
- sem selection overlay.

Gate:
- bloom não aparece fora da máscara emissiva dentro da tolerância de composição.

### R-07 — Visual Baseline

- página independente do viewer V7;
- fixed camera;
- render da cena atual;
- estados de hide/show via API mínima sem UI final;
- screenshots de referência;
- comparação com style anchor.

Gate de produto:
- geometria/composição fiel;
- materiais/luz suficientemente maduros para começar calibração artística;
- nenhum retorno a sprites/crops por módulo.

## Fora do incremento

- UI final;
- painel escondido de eletros;
- seleção dourada final;
- cards/ficha técnica;
- animações;
- substituição do deploy principal;
- WebGPU como backend padrão;
- render generativo no runtime.

## Critério de parada

Parar e pedir input quando a implementação atingir uma escolha estética equivalente entre alternativas válidas que não possa ser resolvida pelo style anchor ou pelos contratos existentes.

# Fidelity Harness v1 — plano de desenvolvimento

Status: planned  
Branch: `renderer/fixed-view-realistic-v1`  
Base: Scene Core 0.1 em `main`  
Objetivo: transformar fidelidade geométrica, projetiva e visual em gates mensuráveis antes de novas correções estéticas.

## 1. Princípios

1. **mm é autoridade física.** Pixel nunca corrige geometria.
2. **câmera fixa é invariante do produto.** A cena atual usa perspectiva calibrada.
3. **pixel é evidência de projeção.** Cotas são projetadas pelos endpoints 3D.
4. **supersampling técnico 4× é o padrão de diagnóstico.** 8× é modo excepcional.
5. **melhoria visual não pode regredir completude, métrica, topologia ou projeção.**
6. **overlay de fidelidade é ferramenta de diagnóstico**, nunca parte do render final.
7. **renderer e UI continuam separados.** Seleção, cotas e overlays não alteram ScenePackage.

## 2. Correção funcional consolidada

O espaço do módulo 02 possui duas configurações mutuamente exclusivas:

- `module-02` visível → forno embutido + cooktop seguem o módulo;
- `module-02` oculto → fogão comum/freestanding aparece por padrão;
- intenção explícita `off` do fogão comum deve ser preservada.

Implementar como contrato genérico `SubstitutionGroup` / `ReplacementPolicy`, nunca como `if moduleId === 02` no renderer.

## 3. Escala mm → pixel

Não existe um único `pxPerMm` global porque a câmera é perspectiva.

A ferramenta deve oferecer:

```text
projectMetricSegment(pointAmm, pointBmm, camera, viewport)
  -> expectedLengthPx
  -> endpointAPx
  -> endpointBPx
```

Para planos frontais, `px/mm ≈ focalPx / depthMm` pode ser exposto apenas como diagnóstico local.

Viewport canônico atual: `1865 × 967`.

Baseline conhecido do conjunto inferior:
- módulo 02 geométrico: 791,01 mm;
- módulo 03 geométrico: 1216,678 mm;
- span combinado: 2007,688 mm;
- projeção aproximada no plano frontal inferior: 595,6 px.

## 4. Supersampling

### Perfil padrão

- apresentação: 1× (`1865×967`);
- fidelity render: 4× (`7460×3868`);
- diagnóstico extremo: 8× somente sob demanda.

Comparações são executadas em 4× e normalizadas para pixels canônicos:

```text
canonicalErrorPx = supersampledErrorPx / 4
```

Não usar AI super-resolution como instrumento de medição.

## 5. FidelityOverlay

Criar overlay ativável por debug, composto por:

### 5.1 Metric grid
- grade 3D real em mm;
- minor: 100 mm;
- major: 500 mm;
- planos: parede, frente dos aéreos, frente dos inferiores, frente da geladeira;
- perspectiva vem da câmera, não de desenho 2D.

### 5.2 AABBs / axes
- AABB por entidade;
- eixos XYZ;
- dimensões em mm;
- status `confirmed | inferred | nominal-only`.

### 5.3 DXF projected wireframe
- edges/contours derivados da geometria autoritativa;
- independente do material e iluminação.

### 5.4 Landmarks / projected dimensions
- extremos de módulos;
- encontros/gaps;
- topo de aéreos;
- spans relevantes;
- anchors de hardware;
- expected px + observed px + error px.

### 5.5 Difference mode
Política visual recomendada:
- geometria projetada: dourado;
- referência observada: ciano;
- proximidade pode gerar heatmap/distância.

Métricas:
- median edge error;
- P95 edge error;
- max landmark error;
- entity/silhouette IoU.

## 6. Modelo de fidelidade

### F0 — Completeness Fidelity — HARD

Verifica entidades obrigatórias/indesejadas e configuração default.

Gate:
- `missingRequired = 0`;
- `unexpectedVisible = 0`.

Casos obrigatórios atuais:
- módulo 01;
- tanque de lavanderia;
- configuração módulo02/fogão comum;
- módulos contextuais necessários;
- appliance/fixture hospedados conforme estado.

### F1 — Metric Fidelity — HARD

Verifica:
- position XYZ;
- AABB;
- W/H/D;
- gaps;
- slots;
- adjacency.

Geometria diretamente derivada do DXF: alvo inicial `<= 1 mm` salvo tolerância explicitamente documentada.

### F2 — Topology Fidelity — HARD

Verifica exatamente:
- portas;
- gavetas;
- painéis;
- prateleiras;
- slots;
- hosts/children;
- substitution groups.

### F3 — Projection Fidelity — HARD

Viewport canônico 1865×967.

Manter ou melhorar:
- landmark max error <= 5 px;
- size RMS <= 1,2 px no conjunto de calibração existente.

Adicionar landmarks para:
- módulo 01;
- span 02+03;
- tanque;
- fogão/forno e entorno;
- módulos 05/06/07;
- geladeira.

### F4 — Hardware Anchor Fidelity — HARD

Reintroduzir `HardwareAnchor` em mm:

```text
HardwareAnchor
  id
  hostGeometryId
  surface
  placementPolicy
  uMm / vMm
  edgeOffsetsMm
  normalOffsetMm
  orientation
  hardwareDefinitionId
```

Políticas mínimas:
- `absolute-uv-mm`;
- `edge-offset-mm`;
- `centered`.

Gates:
- host existe;
- anchor dentro da face;
- offsets físicos corretos;
- local→world estável;
- material/luz não alteram anchor;
- projeção estável;
- troca de puxador preserva anchor.

Os anchors numéricos da V7 não são promovidos automaticamente; serão revalidados contra as faces atuais.

### F5 — Readability Fidelity — QUANTIFIED SOFT

Objetivo: distinguir geometria correta porém ilegível de geometria incorreta.

Gerar semantic-edge mask e medir resposta do render em torno de:
- juntas de portas;
- gavetas;
- encontro módulo/módulo;
- nichos;
- hardware.

Métricas candidatas:
- edge recall;
- median local contrast;
- P10 local contrast.

Não aumentar gaps físicos apenas para torná-los visíveis. Preferir bevel, AO/contact shadow, material e sampling.

### F6 — Appearance / Realism — SOFT + HUMAN

O render IA é `style anchor`, não golden target.

Avaliar separadamente:
- classe de material;
- escala física de textura;
- roughness/reflection;
- contact shadows;
- interseções inválidas;
- emissive ownership;
- leitura da pedra/cuba/torneira;
- qualidade dos proxies/appliance assets.

## 7. Causas conhecidas que o harness deve registrar no baseline

1. `module-01` não materializado na cena atual.
2. `AP-TANK-01` definido, mas sem instância.
3. ausência de fogão comum + replacement policy.
4. módulo 02 sem filler/frente MDF explícito ao redor do nicho do forno.
5. hood proxy excessivamente simples.
6. gaps de portas/gavetas subpixel no viewport 1×.
7. parede de fundo sem textura/juntas.
8. cuba/torneira/pedra com proxy/CSG insuficiente.

## 8. Sequência de implementação

### FH-00 — Baseline freeze
- congelar screenshot/scene hash/head;
- gerar inventário F0–F6 do baseline atual;
- nenhuma correção visual.

### FH-01 — Metric projection API
- endpoints mm→pixel;
- ScreenMetricProfile;
- 1×/4×/8×;
- testes da escala perspectiva.

### FH-02 — FidelityOverlay
- grid 100/500 mm;
- AABB/eixos;
- DXF wireframe;
- landmarks/cotas;
- modo difference.

### FH-03 — Fidelity report
- JSON determinístico por execução;
- F0–F4 hard gates;
- F5 métricas;
- F6 observações/inputs humanos;
- comparação baseline vs candidate.

### FH-04 — Completeness/state contracts
Sem tuning visual:
- materializar módulo 01;
- materializar tanque;
- `SubstitutionGroup` módulo02 ↔ fogão comum;
- validar 02+03 em mm e pixel.

### FH-05 — Hardware anchors
- portar mecanismo conceitual V7;
- revalidar anchors no geometry core atual;
- fixture de puxadores;
- projeção 4×.

### FH-06 — Visual correction loop
Somente agora corrigir, nesta ordem:
1. faltantes/topologia;
2. marcenaria/nicho do forno;
3. depurador e appliances;
4. legibilidade das frentes;
5. parede/azulejos;
6. pedra/cutout/cuba/torneira;
7. texturas/PBR/light tuning.

Cada PR/commit visual deve declarar a métrica que pretende melhorar e demonstrar F0–F4 sem regressão.

## 9. Gates de conclusão do Fidelity Harness v1

- `FH-G01`: mesmo ScenePackage + camera + viewport produz mesmo relatório.
- `FH-G02`: 4× normalizado reproduz projeção analítica dentro da tolerância.
- `FH-G03`: grid é world-space; resize não altera métrica física.
- `FH-G04`: span 02+03 validado em mm e px.
- `FH-G05`: F0 detecta módulo/tanque ausentes no baseline.
- `FH-G06`: substitution group possui round-trip e preserva intent.
- `FH-G07`: hardware anchor round-trip sem drift.
- `FH-G08`: material/light change não altera F1–F4.
- `FH-G09`: baseline/candidate reporta regressões objetivamente.
- `FH-G10`: CI publica screenshot 1×, overlay 4× e fidelity-report.json como artifacts.

## 10. Escopo fora deste incremento

- seleção dourada/UI final;
- painel de controle;
- catálogo editorial;
- animações;
- troca de câmera pelo usuário;
- reconhecimento semântico universal automático de DXF;
- AI upscale como método de medição.

## 11. Critério para retomar o realismo

Só retomar correções artísticas quando FH-00…FH-05 estiverem verdes.

Depois, uma mudança é considerada melhoria real quando:
1. não regride F0–F4;
2. melhora a métrica declarada de F5 e/ou a avaliação específica de F6;
3. não introduz nova entidade ausente, interseção ou mudança métrica não autorizada.

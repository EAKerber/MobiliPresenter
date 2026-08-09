# Fidelity Harness v1 — plano de desenvolvimento

Status: implementation  
Branch: `renderer/fixed-view-realistic-v1`  
Base: Scene Core 0.1 em `main`  
Objetivo: transformar fidelidade geométrica, projetiva e visual em gates mensuráveis antes de novas correções estéticas.

## 1. Princípios

1. **mm é autoridade física.** Pixel nunca corrige geometria.
2. **câmera fixa é invariante do produto.** A cena atual usa perspectiva calibrada.
3. **pixel é evidência de projeção.** Cotas são projetadas pelos endpoints 3D.
4. **supersampling técnico 4× é perfil de diagnóstico**, preferencialmente por crops locais; 8× é excepcional.
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

A ferramenta deve oferecer projeção dos endpoints 3D e medir o segmento no viewport. Para planos frontais, `px/mm ≈ focalPx / depthMm` pode ser exposto apenas como diagnóstico local.

Viewport canônico atual: `1865 × 967`.

Baseline conhecido do conjunto inferior:
- módulo 02 geométrico: 791,01 mm;
- módulo 03 geométrico: 1216,678 mm;
- span combinado: 2007,688 mm;
- projeção aproximada no plano frontal inferior: 595,6 px.

## 4. Supersampling

- apresentação: 1× (`1865×967`);
- fidelity profile: 4× virtual (`7460×3868`);
- diagnóstico extremo: 8× somente sob demanda.

A implementação preferencial usa **crops off-axis locais na grade virtual 4×**, evitando framebuffer monolítico quando ele não acrescenta informação às regiões medidas.

Comparações são normalizadas para pixels canônicos:

```text
canonicalErrorPx = supersampledErrorPx / 4
```

Não usar AI super-resolution como instrumento de medição.

## 5. FidelityOverlay

Criar overlay ativável por debug:
- grid 3D real em mm, minor 100 mm e major 500 mm;
- AABBs/eixos XYZ e dimensões em mm;
- wireframe projetado da geometria autoritativa;
- landmarks/cotas e expected/observed/error em px;
- difference/heatmap quando houver referência observada compatível.

O overlay global é para inspeção humana; a precisão quantitativa vem da projeção analítica e dos crops locais supersampled.

## 6. Modelo de fidelidade

### F0 — Completeness Fidelity — HARD
`missingRequired = 0` e `unexpectedVisible = 0`.

### F1 — Metric Fidelity — HARD
Position XYZ, AABB, W/H/D, gaps, slots e adjacency. Geometria diretamente derivada do DXF: alvo inicial <=1 mm salvo tolerância documentada.

### F2 — Topology Fidelity — HARD
Portas, gavetas, painéis, prateleiras, slots, hosts/children e substitution groups devem corresponder exatamente ao contrato confirmado.

### F3 — Projection Fidelity — HARD
Viewport canônico 1865×967. Manter ou melhorar landmark max error <=5 px e size RMS <=1,2 px no conjunto de calibração.

### F4 — Hardware Anchor Fidelity — HARD
Reintroduzir `HardwareAnchor` em mm com políticas `absolute-uv-mm`, `edge-offset-mm` e `centered`. Anchors antigos não são promovidos automaticamente: regras e números devem ser revalidados contra as faces atuais.

### F5 — Readability Fidelity — QUANTIFIED SOFT
Medir somente bordas que a geometria diz que devem existir: juntas, encontros, nichos e hardware. Métricas: edge recall, contraste local e erro/deslocamento da borda. Não aumentar gaps físicos apenas para fazê-los aparecer.

### F6 — Appearance / Realism — SOFT + HUMAN
O render IA é `style anchor`, não golden target. Avaliar material, escala física de textura, roughness/reflection, contact shadow, interseções, emissive ownership, pedra/cuba/torneira e qualidade dos proxies.

## 7. Sequência

- FH-00 — congelar baseline sem correção visual.
- FH-01 — projection API / ScreenMetricProfile.
- FH-02 — FidelityOverlay.
- FH-03 — relatório determinístico F0–F6.
- FH-04 — completude/estado: módulo 01, tanque, `SubstitutionGroup` módulo02↔fogão comum, validação 02+03 em mm/pixel.
- FH-05 — HardwareAnchor e baseline quantitativo de legibilidade.
- FH-06 — loop de correção visual com F0–F4 sem regressão.

## 8. Ordem do loop visual FH-06

1. faltantes/topologia;
2. leitura do nicho/entorno do forno sem alterar a cota física;
3. depurador e appliances;
4. legibilidade das frentes;
5. parede/contexto;
6. pedra/cutout/cuba/torneira;
7. puxadores visíveis;
8. texturas/PBR/light tuning.

Cada mudança visual deve declarar a métrica que pretende melhorar e demonstrar F0–F4 sem regressão.

## 9. Gates de conclusão

- `FH-G01`: mesmo ScenePackage + camera + viewport produz mesmo relatório.
- `FH-G02`: 4× normalizado reproduz projeção analítica dentro da tolerância.
- `FH-G03`: grid é world-space; resize não altera métrica física.
- `FH-G04`: span 02+03 validado em mm e px.
- `FH-G05`: F0 detecta faltantes no baseline e passa na cena candidata corrigida.
- `FH-G06`: substitution group possui round-trip e preserva intent.
- `FH-G07`: hardware anchor round-trip sem drift.
- `FH-G08`: material/light change não altera F1–F4.
- `FH-G09`: baseline/candidate reporta regressões objetivamente.
- `FH-G10`: CI publica baseline/overlay, fidelity-report e evidência F5 como artifacts.

## 10. Fora de escopo

- seleção dourada/UI final;
- painel de controle;
- catálogo editorial;
- animações;
- câmera livre;
- reconhecimento semântico universal automático de DXF;
- AI upscale como método de medição.

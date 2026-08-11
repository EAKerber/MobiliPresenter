# ADR 0003 — Technical Presentation Contract

Status: proposed / implementação TPC-01

## Contexto

O viewer já possui uma autoridade física (`Scene Core`), uma autoridade de aparência e um estado runtime. A próxima interface precisa, ao selecionar um módulo, receber dados suficientes para apresentar uma ficha semelhante às referências técnicas do projeto: cotas, vistas frontal/lateral/isométrica/interna, acabamentos disponíveis, componentes necessários, avisos, funções e dependências.

Esses elementos não devem ser inferidos pela camada de UX/UI. Também não devem transformar o Scene Core em CMS ou duplicar fatos físicos já rastreados.

## Decisão

Adotar três autoridades e uma etapa derivada:

1. **Scene Core — autoridade física**
   - geometria, envelopes e cotas físicas;
   - nominal vs. geometria observada e suas evidências;
   - host físico, slots, visibilidade semântica e bindings de origem.

2. **Technical Catalog — autoridade autorada de conteúdo técnico não derivável**
   - nome e função editorial;
   - especificações de instalação/construção/hardware;
   - requisitos de componentes que não existem como entidades físicas;
   - avisos e níveis de importância;
   - orientação de apresentação das cotas, sem copiar os valores;
   - vistas técnicas desejadas e layouts internos fornecidos por documentação;
   - dependências técnicas adicionais;
   - famílias/IDs de acabamentos permitidos, sem redefinir materiais.

3. **Appearance Catalog — autoridade dos materiais físicos/visuais**
   - materialId, cor física de render, roughness, textura e escala;
   - presets controlados e seus rótulos.

4. **Technical Presentation Compiler — derivação pura**
   - recebe Scene Core + Technical Catalog + Appearance + ViewerConfiguration;
   - resolve referências, visibilidade efetiva, acabamento corrente e dependências;
   - produz `TechnicalPresentationPackage 0.1.0`, serializável e pronto para consumo pela UI;
   - não importa DOM nem Three.js;
   - não modifica nenhuma das entradas.

## Regra de autoridade das cotas

O catálogo pode declarar **como** uma medida será apresentada (`A × P × E`, `L × A × P`, vista X-Z/Y-Z etc.), mas não pode declarar novamente `nominalMm` ou `geometryMm`.

Exemplo relevante: módulo 04 possui nominal 18 × 2400 × 600 mm e geometria com profundidade 610 mm. A ficha técnica pode preferir a dimensão nominal e ordenar `height, depth, width`, preservando simultaneamente a geometria real de montagem no Core.

Layouts internos que não existem no Core podem ser autorados quando uma fonte os fornece. No módulo 03, os vãos 390/400/400 mm são tratados como fato da folha técnica do layout interno, não como substitutos das dimensões físicas do módulo.

## Iluminação 08

A iluminação sob o aéreo é uma entidade funcional própria, diferente do preset global de iluminação do renderer.

- perfil/entidade física: `scene/traditional/accessory/under-cab-led-06`;
- host físico existente: módulo 06;
- dependência técnica adicional fornecida pelo usuário: módulo 04;
- módulo 04 também é o host técnico do ponto de interruptor/acabamento da fiação;
- `visibility` significa presença/ocultação do perfil;
- `activation` significa emissor ligado/desligado mantendo o perfil presente;
- o TPC-01 declara `activation` como capacidade `declared-not-bound`;
- o estado ligado/desligado só poderá se tornar `bound` quando for incorporado à autoridade runtime (`ViewerConfigurationState` ou sucessor). O TPC não cria um segundo store de estado.

Assim, ocultar e desligar são operações ortogonais por contrato, mas apenas ocultar está implementado no runtime neste incremento.

## Acabamentos

O catálogo técnico lista somente IDs permitidos de famílias controladas (`front-preset`, `stone-preset`). O compilador resolve rótulo e `materialId` na autoridade de aparência.

Adicionar uma nova cor deve ocorrer na família/preset de aparência; habilitá-la para um módulo consiste somente em adicionar o ID à política do catálogo técnico. A UI nunca deve conter uma lista própria de cores.

## Componentes técnicos

`TechnicalComponentRequirement` é uma agenda de requisitos para apresentação/instalação, não uma BOM de fabricação automática. Quando um componente já possui entidade física, o catálogo pode referenciar `linkedEntityId`. Quando não possui, o requisito permanece autorado com fonte e quantidade somente se fornecida.

Nenhum primitive Three.js é promovido automaticamente a componente de fabricação.

## Vistas técnicas

`TechnicalViewRequest` descreve intenção, não layout de UI. O helper determinístico `technical-diagram.ts` consegue materializar SVGs esquemáticos de:

- projeções ortográficas baseadas nas dimensões autoritativas;
- vista isométrica simplificada de envelope;
- vista interna com divisões autoradas quando fornecidas.

Detalhes que dependem de um contrato específico e não podem ser derivados genericamente são retornados como `external-required`, nunca inventados.

O renderer técnico é deliberadamente não realista e separado do renderer de apresentação de câmera fixa.

## Proveniência

Fatos carregam referência e autoridade explícitas. O pacote final declara suas quatro autoridades:

- `scene-core`;
- `technical-catalog`;
- `appearance-catalog`;
- `viewer-runtime`.

O objetivo é permitir que um agente de UI altere composição, hierarquia, responsividade e linguagem visual sem reimplementar ou reinterpretar conteúdo técnico.

## Gates TPC-01

1. mesmo input gera mesmo fingerprint;
2. pacote é serializável;
3. compilação não muta Scene Core, Appearance ou ViewerConfiguration;
4. catálogo é proibido de redefinir cotas físicas;
5. referências de entidades, dependências e acabamentos devem resolver;
6. módulos 03 e 04 preservam nominal vs. geometria;
7. módulo 03 fornece layout interno 390/400/400 proveniente da folha técnica;
8. iluminação 08 separa `visibility` de `activation` e fica indisponível quando módulo 04 ou 06 requerido não está efetivamente visível;
9. SVG técnico é determinístico e não depende de DOM/WebGL;
10. gates Viewer Next/Fidelity existentes não podem regredir.

## Consequências

A futura interface deixa de ser responsável por gerar fichas técnicas. Sua responsabilidade passa a ser consumir `TechnicalPresentationPackage` e assets técnicos derivados, escolhendo apenas como apresentá-los.

A implementação de `activation` real da iluminação e a expansão do catálogo para módulos 01/05/06/07 ficam para incrementos posteriores e não devem ser escondidas dentro da UI.

# Linha de base atual — V7.0-I5

**Status:** factual e verificável.  
**Escopo:** sistema técnico recuperado de `balcao-360-v7-i5.zip` e preview publicado na `main`.

## Duas representações atuais

### Preview publicado

A `main` publica em `https://mobilipresenter.netlify.app/` um viewer mobile leve, baseado em dois spritesheets WebP, com 39 poses de yaw e visibilidade independente dos módulos. Esse preview serve para validação remota e não contém toda a fonte técnica.

### Snapshot técnico

A fonte técnica mais completa está identificada pelo ZIP V7.0-I5:

- 30.001.308 bytes;
- 2.904 arquivos;
- SHA-256 `5ba5672ebc4625b99892dc80b1ae859ed9c406eccf5ba284d523d04129948d5a`.

## Modelo arquitetural existente

```text
ModuleSource
    ↓ compilador determinístico
ModulePackage
    ↓ instâncias, conectores e poses comuns
ModuleAssembly
    ↓ compositor raster
Viewer / auditoria

ModuleManufacturing
    ↓ derivação
BOM / furos / pendências / exportação
```

## Contratos implementados

### `ModuleSource 1.0`

Fonte reproduzível de um módulo: dimensões, captura, calibração, peças, ferragens, conectores e fabricação.

### `ModulePackage 1.0`

Pacote compilado consumido pelo viewer. Contém capacidade visual, poses, materiais, slots, hashes e assets derivados.

### `ModuleAssembly 1.0`

Declara instâncias, posições em milímetros, conectores, rig de câmera, política de poses e transformação entre eixos físicos e tela.

### `ModuleManufacturing 1.0`

Declara peças, materiais, ferragens, configurações, status de verificação e inclusão na BOM.

## Capacidades comprovadas

- composição de módulos capturados separadamente;
- posições físicas em milímetros;
- conectores laterais;
- negociação monotônica de poses reais;
- yaw de −95° a +95° em passo de 5° para a composição atual;
- desativação negociada de pitch sem alterar os pacotes nativos;
- sprites transparentes com âncora no centro da base;
- ordenação por profundidade;
- cache global medido em bytes;
- publicação atômica em viewport mobile;
- visibilidade independente por instância;
- comparação com ground truth;
- BOM individual e agregada;
- configurações de ferragem sem duplicar geometria;
- derivação de furos a partir de face, slot e padrão de montagem;
- exportação JSON e CSV;
- diferenciação entre `provided`, `derived`, `calibrated`, `inferred`, `unverified` e `not-applicable`.

## Fixture atual

| Elemento | Dimensões |
|---|---:|
| Gaveteiro | 399 × 760 × 600 mm |
| Balcão | 780 × 760 × 600 mm |
| Composição | 1.179 × 760 × 600 mm |

O fechamento horizontal é exato: 399 + 780 = 1.179 mm. O conjunto completo é usado apenas como ground truth e não deve duplicar peças na BOM.

## Resultados visuais conhecidos

- 39 poses comuns;
- IoU médio de silhueta próximo de 99,664%;
- pior IoU próximo de 99,063%;
- dispersão de escala frontal próxima de 0,0023 px/mm;
- composição atômica mantida em mobile.

O erro de cor cresce em ângulos oblíquos porque o renderizador de origem recalcula iluminação quando módulos são capturados isoladamente e em conjunto. Isso não foi tratado como erro geométrico.

## Limites atuais

- o negociador cobre poses, não regras gerais de compatibilidade;
- dependências entre módulos e capacidades ainda não possuem contrato executável;
- campos obrigatórios condicionais ainda não existem;
- pitch não está validado para a composição real;
- a BOM da montagem é parcial;
- dimensões internas e ferragens desconhecidas permanecem em branco;
- não há custo, otimização de chapas ou plano de corte validado;
- a autoria de módulos ainda depende de ferramentas assistidas e dados externos;
- o repositório não contém ainda a fonte técnica completa em uma estrutura definitiva;
- o preview Netlify não deve ser confundido com editor, configurador completo ou fonte de fabricação.

## Regra durante o planejamento

Esta linha de base deve ser preservada como evidência. Nenhuma capacidade é automaticamente obrigatória no novo escopo, e nenhuma deve ser descartada sem registrar o motivo, o custo e a alternativa.

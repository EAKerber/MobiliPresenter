# Leituras provisórias da planta

**Status:** não autoritativo.  
**Fonte principal:** fotografia `plant-kitchen-upload`.

## Parede candidata da composição

A planta apresenta três indícios próximos, mas não idênticos:

| Evidência | Leitura | Status |
|---|---:|---|
| anotação manuscrita total | `3550 mm` | provided, baixa/média confiança |
| segmento manuscrito A | `739 mm` | provided, baixa confiança |
| segmento manuscrito B | `2834 mm` | provided, média confiança |
| soma A + B | `3573 mm` | derived |
| diferença entre 3573 e 3550 | `23 mm` | derived, conflito |

A proximidade com a soma nominal dos módulos superiores vistos nas referências é sugestiva, mas não confirma endpoints, folgas ou espessura de paredes.

## Cotas impressas visíveis

- cozinha/área de serviço: indicação `2.82`;
- largura da área de serviço: indicação `1.40`;
- lateral do ambiente: indicação `2.40`;
- estar/jantar: indicação `2.20`;
- outras dimensões do contexto aparecem na planta, mas não foram ligadas ao envelope da marcenaria.

## Anotações auxiliares

Há anotações manuscritas próximas a shafts/equipamentos, aparentemente `695`, `856`, `690` e `86`. A leitura e os endpoints são incertos; o I0 não as converte em geometria.

## Consequência para a implementação

O contrato usa um envelope candidato:

```json
{
  "wallWidthMm": null,
  "candidates": [3550, 3573],
  "status": "unverified"
}
```

A próxima etapa pode trabalhar em coordenadas normalizadas. Conversão para milímetros deve aguardar confirmação da parede útil, dos pontos inicial/final e das interferências.

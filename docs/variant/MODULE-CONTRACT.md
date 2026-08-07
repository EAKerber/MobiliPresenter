# Contrato preliminar de módulo

## Natureza tripla

Um módulo é simultaneamente:

1. **visual** — overlay da cena, miniatura, detalhe, máscara e ordem;
2. **comercial** — item incluível, modificadores e regras;
3. **informacional** — nome, descrição, medidas, materiais, ferragens e observações.

A dimensão fabricável não é requisito do I0.

## Identidade

Os oito itens conhecidos são preservados por `catalogNumber`:

| Nº | ID canônico | Nome |
|---:|---|---|
| 01 | `upper-laundry` | Aéreo da lavanderia |
| 02 | `lower-stove` | Inferior do fogão |
| 03 | `lower-sink` | Inferior da pia |
| 04 | `refrigerator-side-panel` | Lateral da geladeira |
| 05 | `upper-stove` | Aéreo do fogão |
| 06 | `upper-sink` | Aéreo da pia |
| 07 | `upper-refrigerator` | Aéreo da geladeira |
| 08 | `lighting` | Iluminação |

## Evidência e confiança

Campos de domínio usam:

- `confirmed` — fornecido e confirmado;
- `provided` — aparece explicitamente em uma fonte, ainda não reconciliado;
- `derived` — cálculo transparente sobre dados fornecidos;
- `inferred` — interpretação visual;
- `unverified` — conhecido como necessário, sem valor confiável;
- `not-applicable`.

Medidas conflitantes ficam em `measurementCandidates`; `dimensionsMm` só pode receber valor após decisão.

## Detalhe

O detalhe pode incluir tudo que não seja preço:

- render principal;
- medidas e desenho técnico;
- materiais;
- ferragens;
- descrição;
- diferenciais;
- opções;
- dependências e avisos;
- observações comerciais;
- proveniência dos dados.

## Aparência

- `frontColor`: por módulo;
- `carcassColor`: fixo em branco no escopo atual;
- `handle`: escolha por módulo ou preset;
- `openingMode`: handle, point, pass-through ou sem definição;
- `visualModifiers`: extensível e versionado.

O contrato não decide ainda como gerar variantes visuais sem replicar o módulo inteiro.

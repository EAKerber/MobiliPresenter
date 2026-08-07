# Fixed View Modular Showcase — contratos I0

Esta pasta contém a representação machine-readable da variante.

## Dados

- `data/modules.json` — catálogo 01–08;
- `data/assembly.json` — regiões, cena, seleção e envelope;
- `data/presets.json` — presets recomendados e política de override;
- `data/rules.json` — dependências e recomendações;
- `data/references.json` — evidências, hashes e medidas candidatas;
- `data/ui-state.json` — máquina de estados lista ↔ detalhe.

## Schemas

Os schemas são preliminares e intencionalmente pequenos. Eles não modelam fabricação nem preço final.

## Validação

```bash
python3 tools/validate_i0.py
python3 -m unittest discover -s tests -p "test_*.py"
```

O validador também aplica invariantes de domínio que JSON Schema isolado não expressa com clareza.

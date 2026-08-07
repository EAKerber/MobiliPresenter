# Motor de regras da variante

## Escopo do I0

O I0 define o contrato e valida referências; não executa ainda uma UI corretiva.

## Tipos de efeito

- `inform` — mensagem contextual;
- `recommend` — viés de preset, sem invalidar;
- `offer-transition` — propõe uma mudança concreta;
- `block-operation` — impede apenas as operações listadas;
- `disable-option` — opção impossível no estado atual.

## Severidades

- `info`;
- `warning`;
- `incomplete`;
- `blocking`.

Estados agregados:

```text
valid
valid-with-warnings
incomplete
blocked
```

## Dependência conhecida

```json
{
  "id": "lighting-requires-refrigerator-side-panel",
  "when": {
    "moduleEnabled": "lighting"
  },
  "requires": {
    "moduleEnabled": "refrigerator-side-panel"
  },
  "severity": "blocking",
  "affectedOperations": ["finalize", "quote"],
  "resolution": {
    "type": "offer-enable-module",
    "moduleId": "refrigerator-side-panel"
  }
}
```

A edição continua possível. O bloqueio incide sobre finalização e proposta comercial.

## Recomendações de puxador

Regras de recomendação consultam `placementClass`:

- `lower` → `two-hole-handle`;
- `upper` → `one-hole-point` ou `pass-through`.

Override do cliente gera, no máximo, aviso. Não deve ser reescrito automaticamente.

## Linguagem

Regras são declarativas. JavaScript executável não pertence aos módulos. Operadores iniciais:

- `moduleEnabled`;
- `propertyEquals`;
- `all`;
- `any`;
- `not`;
- `requires`;
- `recommendedOneOf`.

A expansão da linguagem exige schema e testes.

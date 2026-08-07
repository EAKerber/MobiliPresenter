# Capacidades, dependências e campos condicionais

**Status:** proposta preliminar para discussão.  
**Origem:** necessidade de expressar regras além da compatibilidade angular.

## Diagnóstico da estrutura atual

O negociador atual é especializado em poses. Ele encontra a interseção de frames reais e reduz capacidade sem síntese. Isso deve continuar isolado como provedor de compatibilidade visual, não crescer até se tornar um interpretador genérico de regras.

`ModuleAssembly` já oferece instâncias, conectores e posições. Há, portanto, espaço para um motor de restrições da montagem que consulte propriedades internas dos módulos.

## Separação proposta

```text
AssemblyConstraintEngine
├── PoseCompatibilityProvider
├── ConnectorCompatibilityProvider
├── ModuleDependencyProvider
├── FeatureDependencyProvider
├── RequiredInputProvider
└── ManufacturingConstraintProvider
```

Cada provedor produz diagnósticos em um formato comum. O motor agrega os resultados, mas não contém regras específicas de produtos.

## Propriedades por nível

### Definição do módulo

Declara o que toda instância daquele módulo oferece ou exige:

- capacidades;
- conectores;
- propriedades configuráveis;
- features opcionais;
- definição de campos;
- requisitos;
- incompatibilidades.

### Instância

Guarda escolhas daquela ocorrência:

- posição;
- orientação;
- propriedades selecionadas;
- features ativadas;
- valores de campos;
- visibilidade e estado de sessão quando aplicável.

### Montagem

Guarda regras e valores do conjunto:

- contexto de uso;
- alimentação disponível;
- limites globais;
- opções comerciais;
- política de validação;
- overrides explícitos e auditáveis.

## Capacidades em vez de IDs rígidos

Uma iluminação não deveria depender normalmente de `moduleId = X`. Ela deveria requerer uma capacidade:

```json
{
  "id": "lighting-needs-power",
  "when": {
    "property": "features.lighting.enabled",
    "equals": true
  },
  "requires": {
    "capability": "electrical.power-supply",
    "properties": {
      "voltage": 24
    },
    "minimum": 1,
    "scope": "assembly"
  },
  "severity": "blocking"
}
```

Qualquer módulo que ofereça uma fonte compatível pode satisfazer a regra. Dependência por ID permanece disponível apenas quando a relação for genuinamente específica.

## Módulo que não pode existir sozinho

```json
{
  "id": "requires-structural-base",
  "requires": {
    "capability": "structural.support-base",
    "minimum": 1,
    "scope": "assembly"
  },
  "severity": "blocking"
}
```

Conectividade física pode adicionar `connectedTo`, lado ou tipo de conector como condição.

## Campos obrigatórios condicionais

A definição do módulo descreve o campo; a instância guarda o valor:

```json
{
  "id": "lighting.switchPosition",
  "type": "enum",
  "options": ["left", "right", "center"],
  "requiredWhen": {
    "property": "features.lighting.enabled",
    "equals": true
  }
}
```

Campos podem ser obrigatórios para:

- editar uma feature;
- calcular preço;
- concluir uma montagem;
- gerar BOM;
- declarar uma saída fabricável;
- publicar ou compartilhar.

A etapa deve fazer parte do diagnóstico; um campo ausente não precisa bloquear todo o editor.

## Severidade e estado global

Severidades propostas:

- `info` — orientação sem impacto de validade;
- `warning` — configuração permitida, mas merece atenção;
- `incomplete` — falta dado ou dependência para uma saída específica;
- `blocking` — combinação inválida para a operação solicitada.

Estados agregados:

```text
valid
valid-with-warnings
incomplete
blocked
```

## Diagnóstico para interface

```json
{
  "code": "MISSING_CAPABILITY",
  "severity": "blocking",
  "sourceInstanceId": "led-superior-1",
  "ruleId": "lighting-needs-power",
  "message": "A iluminação requer uma fonte de 24 V.",
  "candidates": ["fonte-24v-60w"],
  "affectedOperations": ["finalize", "bom"],
  "missingInputs": []
}
```

A interface deve conseguir:

- destacar a instância afetada;
- apresentar o motivo em linguagem humana;
- listar campos faltantes;
- sugerir módulos ou propriedades candidatos;
- diferenciar aviso de bloqueio;
- manter a montagem editável quando estiver apenas incompleta;
- revalidar deterministicamente após qualquer alteração.

## Linguagem de regras

Não armazenar JavaScript executável nos módulos. Usar uma linguagem declarativa pequena, versionada e com operadores fechados, por exemplo:

- `equals`;
- `notEquals`;
- `exists`;
- `greaterThan` / `lessThan`;
- `all` / `any` / `not`;
- `matchesCapability`;
- `connectedTo`;
- `countAtLeast`;
- `withinRange`.

Toda regra deve ser validável por schema, serializável, explicável e coberta por testes.

## Decisões ainda abertas

- regras pertencem ao módulo, a um catálogo central ou a ambos;
- capacidades possuem namespace global ou por fabricante;
- quem define mensagens para a interface;
- como resolver múltiplos candidatos;
- se correções podem ser automáticas;
- quais operações possuem gates distintos;
- como versionar regras quando módulos antigos permanecem em uso;
- se incompatibilidades comerciais e técnicas usam o mesmo motor.

Nenhum desses pontos está aceito apenas pela existência deste documento.

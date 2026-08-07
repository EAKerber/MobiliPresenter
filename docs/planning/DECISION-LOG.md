# Registro de decisões — fase de planejamento

Este arquivo registra decisões e perguntas abertas enquanto o novo escopo é discutido. Uma entrada marcada como aceita deve ser promovida para uma ADR ou documento factual quando alterar a arquitetura ou o produto.

## 2026-08-06 — fase de planejamento aberta

**Estado:** aceito pelo usuário.

- interromper a progressão automática para um novo incremento funcional;
- reavaliar escopo e priorização;
- preservar e formalizar o conhecimento que existia apenas nos ZIPs;
- discutir a estrutura documental antes de consolidá-la;
- considerar que a arquitetura atual pode conter grande parte das capacidades úteis ao novo escopo, sem presumir que todas devam permanecer prioritárias.

## 2026-08-06 — baseline recuperada

**Estado:** factual.

- `balcao-360-v7-i5.zip` é a fonte técnica mais completa localizada;
- tamanho: 30.001.308 bytes;
- arquivos: 2.904;
- SHA-256: `5ba5672ebc4625b99892dc80b1ae859ed9c406eccf5ba284d523d04129948d5a`;
- a `main` atual contém o preview implantável, não toda a fonte técnica.

## Motor de capacidades e requisitos

**Estado:** proposta, não aceita.

Proposta de manter o negociador angular como componente especializado e introduzir um motor geral de restrições com capacidades, dependências, campos condicionais e diagnósticos comuns.

Documento: `CONSTRAINTS-AND-REQUIREMENTS.md`.

## Arquitetura documental

**Estado:** proposta, não aceita.

Proposta de separar `current`, `planning`, `decisions`, `contracts`, `operations` e `history`, com ordem de autoridade explícita.

Documento: `DOCUMENTATION-ARCHITECTURE.md`.

## Perguntas imediatas

1. Qual é a mudança de escopo e qual problema passa a ser prioritário?
2. Quem são os atores e qual é o fluxo principal?
3. O resultado central é apresentação, configuração, proposta, orçamento, fabricação ou uma combinação?
4. Qual papel a representação 360° desempenha nesse fluxo?
5. Quais capacidades da V7.0-I5 devem ser retidas, adaptadas, adiadas ou removidas?
6. O repositório deve receber a fonte técnica completa agora ou somente depois da nova organização ser aprovada?
7. Issues serão usadas como backlog/discussão ou apenas documentos versionados e PRs?

## Formato das próximas entradas

```text
## data — título
Estado: proposta | aceito | rejeitado | substituído | factual
Contexto:
Decisão:
Consequências:
Documento ou ADR relacionado:
```

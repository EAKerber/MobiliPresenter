# Arquitetura documental proposta

**Status:** proposta para discussão.  
**Problema:** o histórico foi produzido principalmente como ZIPs autocontidos. Isso preservou entregas, mas espalhou contexto, decisões e evidências entre versões difíceis de consultar.

## Objetivos

- permitir que um agente novo encontre o estado correto sem ler todo o histórico;
- impedir que proposta seja confundida com decisão;
- ligar contratos, código, testes e evidências;
- preservar técnicas abandonadas sem mantê-las no caminho principal;
- tornar handovers curtos e verificáveis;
- reduzir dependência da memória de um chat.

## Estrutura sugerida

```text
README.md
AGENTS.md

docs/
  README.md
  current/
    BASELINE-V7-I5.md
    PRODUCT-STATUS.md
    CAPABILITY-MATRIX.md
  planning/
    SCOPE-REASSESSMENT.md
    DOCUMENTATION-ARCHITECTURE.md
    CONSTRAINTS-AND-REQUIREMENTS.md
    DECISION-LOG.md
  decisions/
    ADR-000-template.md
    ADR-xxx-*.md
  contracts/
    README.md
    module-source.md
    module-package.md
    module-assembly.md
    constraint-model.md
  operations/
    DEVELOPMENT.md
    VALIDATION.md
    RELEASE.md
    ASSET-PIPELINE.md
  history/
    V7-LINEAGE.md
    ZIP-RECOVERY.md
    migrations/
```

## Metadados mínimos por documento

Todo documento de planejamento ou decisão deve declarar:

```text
status: proposal | accepted | superseded | rejected | factual
owner: user | agent | shared
created: YYYY-MM-DD
last-reviewed: YYYY-MM-DD
supersedes: paths opcionais
related-contracts: paths opcionais
```

Não é necessário usar front matter antes de aprovar o formato; o importante é que o estado seja visível.

## Documentos vivos e históricos

### Vivos

Devem ser curtos e atualizados quando o sistema muda:

- visão do produto;
- baseline atual;
- matriz de capacidades;
- contratos vigentes;
- instruções de desenvolvimento e release;
- decisões aceitas.

### Históricos

Não devem ser reescritos para parecer atuais:

- relatórios de incremento;
- resultados de testes passados;
- inventários de ZIP;
- técnicas descartadas;
- migrações e post-mortems.

## ADRs

Uma ADR deve registrar:

1. contexto;
2. decisão;
3. alternativas consideradas;
4. consequências;
5. evidências e testes necessários;
6. condição de revisão.

ADRs não devem conter planos de implementação detalhados nem copiar documentação de contrato.

## Contratos

Cada contrato deve possuir:

- finalidade e fronteira;
- schema ou tipo executável como autoridade;
- exemplos válidos e inválidos;
- política de versão e migração;
- invariantes;
- diagnósticos esperados;
- testes que comprovam as invariantes.

A documentação explica o contrato, mas não substitui schema e testes.

## Evidências

Relatórios e screenshots devem ser referenciados por:

- versão;
- comando que os produziu;
- ambiente relevante;
- hash quando forem artefatos de release;
- interpretação limitada ao que o teste mede.

Uma captura visual não prova correção semântica; um schema válido não prova qualidade visual.

## Handover de agentes

O handover ideal deve conter apenas:

- commit e branch de base;
- fase atual;
- documentos obrigatórios;
- decisões aceitas desde o último baseline;
- perguntas abertas;
- comandos de validação;
- riscos conhecidos;
- próxima ação autorizada.

Não deve tentar recontar todo o projeto.

## Questões para aprovação

- A documentação deve permanecer no mesmo repositório do código?
- Queremos um documento de produto separado da arquitetura técnica?
- Issues serão usadas como discussão temporária ou como backlog permanente?
- Relatórios gerados devem entrar em Git, Releases ou armazenamento externo?
- O usuário deseja aprovar ADRs individualmente ou por PR de planejamento?

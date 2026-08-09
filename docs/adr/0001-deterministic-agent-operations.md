# ADR-0001 — Operação determinística para agentes

- Status: accepted
- Date: 2026-08-09

## Contexto

O repositório acumulou duas classes de conhecimento diferentes:

1. decisões de produto/arquitetura que precisam permanecer explicadas;
2. fatos e procedimentos operacionais que agentes precisavam reconstruir lendo documentação e histórico.

A segunda classe já causou divergência de onboarding: documentos históricos da linha fixed-view permaneceram legíveis como se ainda descrevessem o estado ativo, enquanto o Git e os contratos mais novos diziam outra coisa.

## Decisão

Adotar incrementalmente uma arquitetura operacional determinística:

- documentação explica decisões e políticas;
- `ops/state/project.json` é a autoridade inicial para o estado operacional corrente;
- procedimentos read-only recorrentes entram em `tools/agent.py`;
- qualquer projeção humana futura de estado deve derivar da mesma autoridade;
- Git, manifests e artefatos existentes continuam suas próprias autoridades de domínio; a toolbox apenas os observa e cruza;
- operações mutantes futuras devem seguir `observe -> plan -> validate -> apply -> readback`;
- automação nova só é adicionada quando recorrência ou risco estiverem comprovados.

## Bootstrap adotado

Fase 0/1:

```bash
python3 tools/agent.py status
python3 tools/agent.py doctor
python3 tools/agent.py verify
```

Todos os três comandos são read-only e aceitam `--json`.

Não fazem parte deste bootstrap:

- publicação Git automatizada;
- poda de branches;
- CI orchestration;
- geração automática de handoff;
- mutação do estado;
- automação de domínio do Scene Core.

Esses recursos só devem ser adicionados quando o procedimento concreto estiver estabilizado.

## Autoridades

- repositório: Git/GitHub;
- versão publicada e artifact hash: `snapshot/mobile/manifest.json`;
- estado operacional corrente: `ops/state/project.json`;
- regras permanentes para agentes: `AGENTS.md`;
- decisões arquiteturais: ADRs/documentação explicativa.

A toolbox não possui base de dados própria.

## Consequências

### Positivas

- onboarding começa por uma leitura estruturada;
- divergências entre estado declarado e manifest publicado tornam-se verificáveis;
- fatos operacionais deixam de precisar ser repetidos em múltiplos handoffs;
- o protocolo Git determinístico atual pode futuramente ser encapsulado sem perder readback e verificação.

### Custos

- o estado canônico precisa ser atualizado quando uma transição real ocorre;
- `status` não substitui entendimento arquitetural;
- o bootstrap não elimina ainda documentação histórica.

## Regra de evolução

Não transformar a toolbox em um segundo produto. Um novo comando só entra quando houver uma operação repetida ou um risco concreto que justifique encapsulamento.

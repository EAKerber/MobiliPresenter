# MobiliPresenter

Apresentador modular de mobiliário com composição métrica, câmera fixa e foco em contextualização visual fiel.

## Entrada para desenvolvimento por agentes

Este README é uma porta de entrada, não uma authority operacional. O estado corrente deve ser derivado do tooling e das authorities do repositório.

Comece sempre por:

```bash
python3 tools/agent.py status
```

`status` separa a próxima transição de roadmap da **próxima ação operacional segura** e lista os pares de papel/intenção aceitos pelo bootstrap. Quando já existe um Work conhecido, observe também a disposição de re-entry antes de abrir outro ciclo:

```bash
python3 tools/agent.py status --work-id <work-id> --json
```

Esse modo observa a Work authority e o histórico completo do Hosted Agent Cycle bus, reutiliza a classificação canônica de re-entry e pode orientar `BEGIN_NEW_CYCLE`, `RESUME_EXACT_CYCLE`, `WAIT`, `HONOR_HANDOFF`, `RECONCILE_FAILURE`, `OBSERVE` ou `NONE`. Falha/incompletude do provider resulta em `OBSERVE`; nunca é promovida a `PASS`.

Quando a orientação exigir um novo ciclo, consuma `bootstrap.pavedEntry`. A entrada normal Work-bound é `journey-entry` pela ToolSurface configurada do host (`github-connector-tools`), mantendo issue/marker/version/handle/CAS fora da superfície cognitiva do caller.

O comando público `agent.py begin` foi retirado em R8. Recovery de Agent Cycle continua nos carriers/contratos internos de Hosted Agent Cycle e não faz parte da superfície normal de bootstrap. `bootstrap.pavedEntry` é somente uma projeção read-only: ela não concede authority nem autoriza mutação.

Authorities e contratos de entrada:

- estado do projeto: `ops/state/project.json`;
- regras transversais: `AGENTS.md`;
- contratos estáveis de papel: `docs/kickstarts/roles/<role>.md`;
- capabilities, providers e superfícies: derivados pelo tooling e pelo registro semântico;
- publicação corrente: derivada do manifesto apontado por `ops/state/project.json`.

Não existem ponteiros operacionais `*-current.md` para dados de papel. Não copie checkpoint, branch publicada, versões de runtime ou próxima transição para documentos de bootstrap: esses valores mudam e devem continuar sendo observados da fonte autoritativa.

## Estado publicado

A publicação corrente é identificada pelo manifesto referenciado em `ops/state/project.json`. Para descobrir release, source branch, source base, fingerprint, build command e publish path atuais, leia a projeção de `status` ou o manifesto apontado pelo ProjectState; não os infira deste README.

A URL canônica do produto também vem do ProjectState. Divergências entre ProjectState, manifesto e observações de publicação devem ser tratadas como problema de coerência, não corrigidas por narrativa neste arquivo.

O requisito de produto permanece **viewer em câmera fixa**, priorizando fidelidade contextual sobre liberdade de navegação 3D.

## Publicação determinística

A configuração de publicação vive em `netlify.toml` e na authority de SourceBuild indicada pelo ProjectState. O manifesto registra a identidade reproduzível da fonte, incluindo base, paths, comando de build e publish path. Nenhuma branch específica deve ser presumida a partir deste README.

## Governança Git

Este repositório é exclusivo do projeto MobiliPresenter. Operações em qualquer outro repositório exigem confirmação explícita no chat ativo. `AGENTS.md` contém regras permanentes transversais; procedimentos correntes devem ser descobertos pelo tooling e pelas authorities do repositório, e comportamento específico de papel pelos contratos diretos em `docs/kickstarts/roles/*.md`.

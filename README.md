# MobiliPresenter

Apresentador modular de mobiliário com composição métrica, câmera fixa e foco em contextualização visual fiel.

## Entrada para desenvolvimento por agentes

O estado operacional canônico não deve ser inferido deste README. Após confirmar o repositório ativo, use:

```bash
python3 tools/agent.py status
python3 tools/agent.py doctor
python3 tools/agent.py verify
```

A autoridade de estado é `ops/state/project.json`. As decisões operacionais adotadas estão registradas em `docs/adr/0001-deterministic-agent-operations.md`.

## Estado publicado

A publicação corrente é identificada pelo manifesto apontado em `ops/state/project.json`. No baseline atual:

- release: **ViewerNext-Preview-2026-08-11**;
- branch publicada: `main`;
- URL canônica: **https://mobilipresenter.netlify.app/**;
- manifesto: `ops/published/viewer-next-current.json`;
- fonte do build: `scene-core` + `viewer-next`;
- modo padrão de UI: `renderer-only`;
- preview dos controles: `?controls=1`.

O requisito de produto permanece **viewer em câmera fixa**, priorizando fidelidade contextual sobre liberdade de navegação 3D.

## Publicação determinística

O Netlify usa a branch `main`, instala as dependências de `scene-core` e `viewer-next`, executa o build de `viewer-next` e publica `viewer-next/dist`, conforme `netlify.toml` e o manifesto corrente.

`ops/published/viewer-next-current.json` registra a identidade do SourceBuild, incluindo base, paths de fonte, comando de build e publish path. Divergências entre esse manifesto e `ops/state/project.json` devem ser tratadas como erro de coerência operacional.

## Governança Git

Este repositório é exclusivo do projeto MobiliPresenter. Operações em qualquer outro repositório exigem confirmação explícita no chat ativo. O protocolo completo para agentes está em `AGENTS.md`.

# Estado operacional

`state/project.json` é a autoridade inicial para fatos operacionais correntes do MobiliPresenter.

Use:

```bash
python3 tools/agent.py status
python3 tools/agent.py doctor
python3 tools/agent.py verify
```

Os comandos são read-only e oferecem `--json`.

## O que não pertence aqui

- decisões de arquitetura: `docs/adr/` e documentação explicativa;
- conteúdo do produto: contratos do Scene Core;
- histórico Git: Git;
- artefato publicado: `snapshot/mobile/manifest.json`;
- autorizações efêmeras de um chat: permanecem no contexto da sessão e não devem ser promovidas automaticamente a política permanente.

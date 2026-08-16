# Estado operacional

`state/project.json` é a autoridade inicial para fatos operacionais correntes do MobiliPresenter.

Para observação e diagnóstico use:

```bash
python3 tools/agent.py status
python3 tools/agent.py doctor
python3 tools/agent.py verify
```

Essas superfícies são read-only e oferecem `--json`. Transições de checkpoint são plan-only por padrão e exigem `--apply --expected-plan <planHash>` para escrita. Sanitização de branches também é separada: `agent.py git prune-plan` apenas materializa o plano; o executor destrutivo `tools/prune_apply.py` exige um arquivo de plano exato, `--expected-plan`, autorização explícita e readback.

O artefato/publicação corrente não é fixado por este README: seu ponteiro canônico é `published.artifactManifest` em `state/project.json`.

## O que não pertence aqui

- decisões de arquitetura: `docs/adr/` e documentação explicativa;
- conteúdo do produto: contratos do Scene Core;
- histórico Git: Git;
- bytes/histórico do artefato publicado: seguem a autoridade apontada por `published.artifactManifest` e o histórico apropriado;
- autorizações efêmeras de um chat: permanecem no contexto da sessão e não devem ser promovidas automaticamente a política permanente.

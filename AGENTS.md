# Regras para agentes

## 1. Isolamento de repositório

1. Este repositório pertence exclusivamente ao projeto **MobiliPresenter**.
2. Antes da primeira operação Git de um chat, o agente deve obter confirmação explícita do repositório ativo.
3. Memórias, permissões ou nomes de repositórios vindos de outros chats não autorizam sequer consultas neste repositório ou em qualquer outro.
4. Não realizar operações em repositórios diferentes de `EAKerber/MobiliPresenter` sem nova autorização explícita no chat ativo.

## 2. Entrada operacional

Depois de confirmar o repositório, o onboarding operacional começa pelo estado estruturado, não pela reconstrução manual do histórico:

```bash
python3 tools/agent.py status
```

Quando a capacidade do ambiente for relevante:

```bash
python3 tools/agent.py doctor
```

Antes de uma transição significativa ou quando houver suspeita de divergência:

```bash
python3 tools/agent.py verify
```

Para preparar uma transição de checkpoint sem escrever:

```bash
python3 tools/agent.py checkpoint --to <CHECKPOINT> --next <NEXT_TRANSITION>
```

A escrita de checkpoint é deliberada e limitada ao estado operacional:

```bash
python3 tools/agent.py checkpoint --to <CHECKPOINT> --next <NEXT_TRANSITION> --apply
```

Para produzir um handoff derivado, sem criar uma nova fonte de verdade:

```bash
python3 tools/agent.py handoff --json
```

`status`, `verify` e `handoff` aceitam `--remote`; quando `gh` não estiver disponível, o estado remoto deve permanecer `unknown`, nunca ser inventado como green.

Autoridades:

- estado operacional corrente: `ops/state/project.json`;
- artefato publicado: `snapshot/mobile/manifest.json`;
- regras permanentes: este arquivo;
- decisões arquiteturais: ADRs e documentação explicativa;
- histórico: Git;
- PR/CI: GitHub observado, não duplicado em arquivo local.

Não promover automaticamente permissões ou autorizações efêmeras de um chat para política permanente do repositório.

## 3. Contrato operacional

Operações significativas devem seguir conceitualmente:

```text
observe -> plan -> validate -> apply -> readback
```

Quando aplicável, preparar rollback ou compensação antes da mutação.

Regras:

1. estado observado prevalece sobre narrativa antiga;
2. uma API informar sucesso não substitui readback;
3. divergência entre esperado e observado interrompe a operação;
4. procedimentos recorrentes ou de alto risco devem migrar gradualmente para a toolbox, não crescer indefinidamente neste arquivo;
5. a toolbox não cria estado paralelo quando Git, manifests ou contratos já são autoridade suficiente;
6. checkpoint deve acompanhar transições reais para impedir drift entre `ops/state/project.json`, PR e execução;
7. `handoff` é snapshot derivado e nunca substitui as autoridades acima.

## 4. Protocolo Git determinístico

1. Não declarar uma operação Git impossível com base apenas em mensagens do ambiente, ausência de `git push`, descrição superficial de ferramenta ou primeira tentativa malsucedida.
2. Confirmar por leitura independente a branch-base e o commit-base exatos antes de qualquer publicação.
3. Quando o transporte Git convencional não estiver disponível, publicar diretamente os objetos Git necessários: blobs -> tree sobre a base autorizada -> commit com parent explícito -> ref.
4. Para conteúdo binário, usar blobs Base64 verificáveis; quando o transporte integral não for confiável, usar fragmentação determinística acompanhada de manifesto, tamanho e SHA-256.
5. Não mover uma ref antes de validar mecanicamente os blobs e a tree preparada.
6. Após cada escrita, realizar readback independente e confirmar, conforme aplicável: SHA, parent, ancestralidade, paths, modos, blob SHAs, tamanho, hash de conteúdo e diff contra a base.
7. Acknowledgement do conector não é prova suficiente de conclusão. Divergência implica interrupção; não presumir sucesso nem repetir cegamente a operação.
8. `main` representa a versão publicada pelo Netlify. Mudanças devem preservar um estado implantável, identificável e reversível.
9. A branch de desenvolvimento ativa e a próxima transição devem ser consultadas em `ops/state/project.json`, em vez de serem duplicadas aqui.

## 5. Integridade de domínio

1. Dados físicos ou comerciais desconhecidos não devem ser inventados; devem permanecer `null`, `unverified`, `inferred` ou equivalentes.
2. Câmera fixa é requisito de produto; não reabrir navegação 3D livre sem decisão explícita do usuário.
3. Para montagem, geometria observada/validada prevalece sobre dimensão nominal conflitante, mas ambas devem permanecer rastreáveis.

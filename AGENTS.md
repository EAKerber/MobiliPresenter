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

Conceitos operacionais transversais devem reutilizar o contrato semântico canônico em `ops/semantics/registry.json` e `tools/semantics/`; vocabulários específicos de domínio permanecem sob seu semantic owner. Para consultar ou validar esse contrato sem promover uma nova source of truth:

```bash
python3 -m tools.semantics explain <semantic-id>
python3 -m tools.semantics check --json
```

Para obter uma visão factual composta das autoridades operacionais observáveis, sem criar nova fonte de verdade ou recomendação semântica:

```bash
python3 tools/project_machine.py inspect --live --json
```

`ProjectMachineInspection` é uma projeção derivada, read-only e `semanticAuthority=false`. Ela contém fatos, uma projeção de authorities derivada dos próprios sensores e duas dimensões distintas: `trust` indica se os fatos requeridos puderam ser observados; `coherence` indica se as authorities conhecidas concordam nas relações verificáveis. Ambas usam `PASS`, `UNKNOWN` e `FAIL`. A interpretação operacional permanece em `MaintenanceInspection` e o roteamento permanece em `SchedulerPlan`.

Quando a capacidade do ambiente for relevante:

```bash
python3 tools/agent.py doctor
```

Antes de inferir capacidades operacionais pelo histórico, por nome de versão ou pela mera existência de arquivos, observar o discovery corrente:

```bash
python3 tools/capability_gates.py list --json
```

A existência de uma capability não implica uso obrigatório. Sua `policy`, Gates e autoridades observáveis determinam se ela é canônica, experimental, desabilitada ou sujeita a revisão.

Mutações do lifecycle de capabilities experimentais usam a superfície transacional:

```bash
python3 tools/capability_lifecycle.py <transition> ... --json
```

Essa superfície é plan-only por padrão. Aplicação exige `--expected-plan <planHash> --apply`; estado observado diferente invalida o plano. Evidências de transição em `ops/evidence/capability-gates/**` são append-only e a CI deve conseguir reproduzir a mudança de estado a partir delas.

Estado de continuação vivo, destinado a sobreviver à perda de chat/sessão, é observado na authority Git dedicada:

```bash
python3 tools/continuation_live.py list --json
```

A authority canônica é `coordination/continuations`. `tools/continuation.py` contém apenas o modelo, validação e inspeção local read-only; planners puros vivem em `tools/continuation_transition.py` e não escrevem estado. Mutações operacionais usam exclusivamente `tools/continuation_live.py`, são plan-only por padrão, produzem `TransitionPlan 0.1`, exigem `--expected-plan <planHash> --apply` e só concluem com `TransitionReceipt 0.1` após CAS/readback da authority. Cada continuation representa uma frente de trabalho persistente; não é fila global, scheduler ou mecanismo de prioridade.

Antes de uma decisão supervisora agendada ou de reconciliação global que precise enxergar continuations vivas, usar:

```bash
python3 tools/maintenance_live.py --json
```

Para inspeção base/rollback sem depender da authority de continuations, permanece disponível:

```bash
python3 tools/maintenance_inspect.py --remote --json
```

`MaintenanceInspection` cruza ProjectState, verificação, capabilities/Gates, PR/CI, Coordination Leases e, na superfície live, Continuation State. Sua `recommendation` é estritamente operacional (`CONTINUE`, `RECONCILE`, `HANDOFF`, `PAUSE`, `NEEDS_HUMAN`) e não concede autoridade semântica sobre produto. `HANDOFF` só pode ser recomendado a partir de estado de continuação explícito e observável; não deve ser inferido da ausência de atividade em um chat.

Para transformar a inspeção live em um plano determinístico de roteamento, usar:

```bash
python3 tools/scheduler_plan.py --live --json
```

`SchedulerPlan` é read-only e não envia mensagens, cria timers ou acorda chats por si só. `HANDOFF` só roteia para `handoffTo` explícito; `CONTINUE` com continuation explícita só roteia para seu `actor`; `CONTINUE` sem continuation volta ao `gitops-supervisor` para atribuição, sem inferir UI/Engine. `RECONCILE` vai ao supervisor, `PAUSE` não gera wake e `NEEDS_HUMAN` aponta somente para humano. A camada de transporte/wake é separada e deve validar o `SchedulerPlan` sem alterar sua decisão.

Antes de uma transição significativa ou quando houver suspeita de divergência:

```bash
python3 tools/agent.py verify
```

Para preparar uma transição de checkpoint sem escrever:

```bash
python3 tools/agent.py checkpoint --to <CHECKPOINT> --next <NEXT_TRANSITION> --json
```

O resultado é um `TransitionPlan 0.1`. A aplicação exige identidade exata desse plano e só produz `TransitionReceipt 0.1` depois de readback verificado:

```bash
python3 tools/agent.py checkpoint --to <CHECKPOINT> --next <NEXT_TRANSITION> --apply --expected-plan <PLAN_HASH> --json
```

`TransitionPlan` e `TransitionReceipt` são envelopes determinísticos, não authorities. A semântica do candidate pertence ao domínio e a escrita pertence ao executor do domínio; o protocolo comum não é executor genérico.

Para produzir um handoff derivado, sem criar uma nova fonte de verdade:

```bash
python3 tools/agent.py handoff --json
```

Antes de qualquer sanitização de branches, gerar primeiro um plano read-only:

```bash
python3 tools/agent.py git prune-plan --json
```

No estado canônico atual, `git prune-plan` é somente leitura. O plano contém um `planHash`; qualquer drift de branch invalida o plano. Se PRs abertas não puderem ser observadas, `applyEligible` deve permanecer `false`. Capacidades futuras de aplicação destrutiva, se existirem, devem ser descobertas e validadas no estado corrente em vez de inferidas por número de versão.

`status`, `verify` e `handoff` aceitam `--remote`; quando `gh` não estiver disponível, estado remoto desconhecido deve permanecer `unknown`, nunca ser inventado como green.

Autoridades:

- estado operacional corrente: `ops/state/project.json`;
- policy e Gates de capabilities operacionais: `ops/capabilities/*.json`;
- evidência de transições de lifecycle: `ops/evidence/capability-gates/**` + histórico Git;
- ownership temporário de escrita: `coordination/leases`;
- estado vivo de continuidade entre sessões/chats: `coordination/continuations`;
- autoridades específicas de uma capability: contratos/ADRs aceitos e a autoridade indicada pela própria capability/tooling observável;
- artefato/publicação corrente: manifesto apontado por `published.artifactManifest` no estado operacional;
- regras permanentes: este arquivo;
- decisões arquiteturais: ADRs e documentação explicativa;
- histórico: Git;
- PR/CI: GitHub observado, não duplicado em arquivo local.

`ProjectMachineInspection`, `MaintenanceInspection`, `SchedulerPlan`, `TransitionPlan`, `TransitionReceipt`, `handoff` e outros snapshots derivados nunca se tornam nova fonte de verdade.

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
7. `handoff` é snapshot derivado e nunca substitui as autoridades acima;
8. quando não existe recorte Developer ativo, `activeDevelopmentBranch` e `development.prNumber` devem permanecer `null`; branches paralelas preservadas não assumem implicitamente esse papel;
9. sanitização destrutiva de branches exige plano previamente observado e aprovação humana; a ausência de observação de PRs abertas bloqueia aplicação;
10. disponibilidade de uma capability não equivale a policy canônica nem amplia autoridade semântica do agente;
11. capabilities experimentais seguem seus Gates. `next=[]` é válido, mas uma revisão formal deve reavaliar o motivo do adiamento e o contador correspondente; prioridade concorrente ou existência de outro trabalho não justificam, isoladamente, adiamento indefinido;
12. mudança de Gate, contador ou `policy` deve ser explicável por uma transição determinística e evidência auditável; `pass` nunca promove automaticamente e o limite de rodadas vazias nunca aumenta automaticamente;
13. uma decisão supervisora deve ser derivada de sensores observáveis. `CONTINUE` significa apenas ausência de impedimento operacional conhecido; não equivale a aprovação semântica da próxima mudança;
14. continuidade entre chats depende de estado persistente na authority `coordination/continuations`, não da memória de um chat, de arquivos não publicados no checkout local ou da mera existência de uma branch de trabalho;
15. o Scheduler planner somente deriva roteamento da inspeção validada; não cria autoridade semântica, não escolhe papel por conteúdo do produto e não realiza transporte como efeito colateral;
16. mutações que usam `TransitionPlan 0.1` são plan-only por padrão, exigem `expected-plan` exato antes da escrita e só são consideradas concluídas após `TransitionReceipt 0.1` verificado por readback.

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
10. Branches em `git.preserveBranches`, heads de PRs abertas, autoridades operacionais, rollback e âncoras `archive/*` são protegidas de poda até mudança explícita do estado/política.

## 5. Integridade de domínio

1. Dados físicos ou comerciais desconhecidos não devem ser inventados; devem permanecer `null`, `unverified`, `inferred` ou equivalentes.
2. Câmera fixa é requisito de produto; não reabrir navegação 3D livre sem decisão explícita do usuário.
3. Para montagem, geometria observada/validada prevalece sobre dimensão nominal conflitante, mas ambas devem permanecer rastreáveis.
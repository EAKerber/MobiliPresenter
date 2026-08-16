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
python3 -m tools.semantics authority <authority-id> --json
python3 -m tools.semantics component <component-id> --json
python3 -m tools.semantics check --json
```

`OperationalSemantics` é contrato, não estado operacional. `managedAuthorities` descreve authorities sob escrita controlada pela toolbox; cada authority mutável marcada com `requiresCanonicalWriter=true` deve possuir exatamente um writer suportado e exatamente um canonical writer, sendo o mesmo componente. `resources` representam superfícies compartilhadas que podem sofrer side effects sem fingir single-writer authority. Adapters podem delegar para executors, mas não se declaram writers independentes.

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

`SchedulerPlan` é read-only, `semanticAuthority=false` e `transportSideEffects=false`; roteia somente decisões já derivadas de authorities observáveis.

Antes de qualquer sanitização de branches, gerar primeiro um plano read-only:

```bash
python3 tools/agent.py git prune-plan --json
```

`GitPrunePlan 0.3` deriva candidatos apenas de proteção explícita e evidência Git/PR observável; nomes e prefixos de branch são descritivos e nunca concedem lifecycle, retenção, proteção ou autorização de deleção. Aplicação destrutiva existe em `tools/prune_apply.py`, mas exige um arquivo de plano materializado, `--expected-plan <planHash>` exato, autorização explícita e revalidação/readback CAS-style. Observações incompletas, drift de inventário/SHA ou PR aberta surgida depois do plano bloqueiam a aplicação. O executor não gera um novo plano implicitamente.

`status`, `verify` e `handoff` aceitam `--remote`; quando `gh` não estiver disponível, estado remoto desconhecido deve permanecer `unknown`, nunca ser inventado como green.

## 3. Mudanças significativas

1. Toda mudança significativa deve seguir `observe -> plan -> validate -> apply -> readback`.
2. Estado observado prevalece sobre narrativa antiga.
3. Acknowledgement de API não substitui readback.
4. Drift invalida plano.
5. Tooling transacional plan-only exige expected plan/hash quando seu contrato assim definir.
6. checkpoint deve acompanhar transições reais para impedir drift entre `ops/state/project.json`, PR e execução;
7. `handoff` é snapshot derivado e nunca substitui as autoridades acima;
8. quando não existe recorte Developer ativo, `activeDevelopmentBranch` e `development.prNumber` devem permanecer `null`; branches paralelas preservadas não assumem implicitamente esse papel;
9. sanitização destrutiva de branches exige plano previamente observado, identidade exata via `expected-plan`, autorização explícita e readback; a ausência de observação completa de PRs/refs/ancestralidade bloqueia aplicação;
10. disponibilidade de uma capability não equivale a policy canônica nem amplia autoridade semântica do agente;
11. capabilities experimentais seguem seus Gates. `next=[]` é válido, mas uma revisão formal deve reavaliar o motivo do adiamento e o contador correspondente; prioridade concorrente ou existência de outro trabalho não justificam, isoladamente, adiamento indefinido;
12. mudança de Gate, contador ou `policy` deve ser explicável por uma transição determinística e evidência auditável; `pass` nunca promove automaticamente e o limite de rodadas vazias nunca aumenta automaticamente;
13. Branch names e semantic classes são descritivos: não concedem autoridade, retenção, proteção ou direito de destruição;
14. Nova source of truth exige decisão explícita; projeções, manifests e inspeções derivadas devem apontar para sua authority e não competir com ela.

## 4. Git e integração

1. `main` é a branch de controle/publicação.
2. Uma branch de implementação deve representar um recorte reversível e verificável.
3. PR e CI são observados no GitHub, não duplicados como fatos locais.
4. Mudança grande não reversível deve ser esclarecida de forma sucinta antes da aplicação.
5. Mudanças de framework/GitOps não devem incluir alterações de Engine/UI/produto sem autoridade explícita.
6. Antes de merge, verificar diff, CI, identities e authorities relevantes.
7. Acknowledgement do conector não é prova suficiente de conclusão. Divergência implica interrupção; não presumir sucesso nem repetir cegamente a operação.
8. `main` representa a versão publicada pelo Netlify. Mudanças devem preservar um estado implantável, identificável e reversível.
9. A branch de desenvolvimento ativa e a próxima transição devem ser consultadas em `ops/state/project.json`, em vez de serem duplicadas aqui.
10. Proteção de branch deriva de estado/política explícitos e observação corrente (por exemplo `git.preserveBranches`, heads de PRs abertas e authorities conhecidas), nunca apenas do prefixo do nome. Prefixos como `archive/*`, `backup/*`, `work/*` ou `authority/*` não concedem por si sós retenção, autoridade nem elegibilidade de poda.

## 5. Integridade de domínio

1. Dados físicos ou comerciais desconhecidos não devem ser inventados; devem permanecer `null`, `unverified`, `inferred` ou equivalentes.
2. Câmera fixa é requisito de produto; não reabrir navegação 3D livre sem decisão explícita do usuário.
3. Para montagem, geometria observada/validada prevalece sobre dimensão nominal conflitante, mas ambas devem permanecer rastreáveis.

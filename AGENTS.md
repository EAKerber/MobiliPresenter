# MobiliPresenter — regras permanentes para agentes

## Repositório e isolamento

- Este repositório pertence exclusivamente ao projeto **MobiliPresenter**: `EAKerber/MobiliPresenter`.
- Antes da primeira operação Git de uma conversa, confirme explicitamente o repositório ativo. Memória de outros projetos não concede acesso.
- Não opere outro repositório sem nova autorização explícita.

## Autoridade e conhecimento

- Um fato mutável deve ter uma única authority e um writer canônico. Representações derivadas devem se declarar como tal.
- Estado corrente pertence a authorities estruturadas; procedimento recorrente pertence a tooling; política/contrato permanente pertence a contratos; história permanece recuperável no Git/evidência.
- Documentação narrativa não substitui estado observado. Snapshots derivados, handoffs, email e conversa de task nunca se tornam authority por conveniência.
- Descubra contratos e capabilities correntes pelo repositório/tooling; não inferir comportamento pela idade de um documento ou pelo nome de uma versão.

## Operação significativa

Operações relevantes seguem conceitualmente:

```text
observe -> plan -> validate -> apply -> readback
```

- Read-only por padrão quando a operação não exige mutação.
- Drift, observação incompleta ou identidade divergente bloqueiam a operação; `UNKNOWN` nunca equivale a `PASS`.
- Quando houver plano materializado/planHash/CAS/readback no contrato do domínio, não contorne essas etapas.
- Operações destrutivas usam a mesma disciplina de evidência: não são proibidas por serem destrutivas, nem autorizadas por heurística de nome.
- Acknowledgement de API não substitui readback independente.
- Ações mutáveis não são probes de discovery. Descoberta usa superfícies read/list/search; criação, atualização, merge, delete e movimentação de refs só ocorrem na fase apply.
- Ausência ou falha de um provider concreto não prova ausência da capability lógica. Antes de declarar uma capability indisponível, observe os providers suportados relevantes e valide se algum satisfaz integralmente seus invariantes.
- Provider alternativo não pode enfraquecer plan/CAS/readback, substituir evidência exigida por heurística nem ampliar authority/scope. Se a equivalência não puder ser provada, a capability permanece `UNKNOWN` e a mutação não ocorre.

## Git e lifecycle

- `main` é o branch de controle/publicação corrente.
- Toda mutação Git/GitHub deve nomear explicitamente o branch/ref alvo; default implícito de API nunca é autorização para escrever em `main`.
- O paved path usa o planner transacional do domínio quando ele existe. Não empilhe um `GitMutationPlan` genérico sobre ProjectState, Work, Coordination, Prune ou outra operação que já possua plan/apply/readback canônico.
- Para mutações diretas de conteúdo/topologia Git/GitHub sem planner de domínio — criação de branch, create/update/delete de arquivo, criação/merge de PR e movimentação direta de ref — materialize e valide `GitMutationPlan 0.1` por `python3 tools/agent.py git mutation-plan ...` antes da action mutável. O plano deve refletir o target e as preconditions observadas e a action/readback pretendidos.
- `GitMutationPlan` é artifact read-only e declara `authorizesMutation=false`; ele torna a intenção analisável, mas nunca amplia autorização de papel/policy/authority.
- Mudanças normais de conteúdo usam branch explícito + PR. Writers de authority operam somente nas refs que seus contratos declaram.
- Branch names são descritivos; não concedem por si sós retenção, authority, proteção ou elegibilidade de deleção.
- PR/CI são observados no GitHub, não duplicados como verdade local.
- Trabalho recuperável deve ser persistido na authority/branch apropriada antes de depender da continuidade de uma conversa ou runtime efêmero.
- Branch Hygiene é o writer normal de coleta de branches após integração/abandono. Agentes não competem com essa coleta por deleção manual; remoção direta de ref é break-glass/recovery e exige observação + readback explícitos.

## Limites de papel

- Autoridade operacional não concede autoridade semântica sobre produto.
- UI/UX, Engine, Scene Core e outros domínios mantêm seus semantic owners; um agente de processo não deve decidir conteúdo desses domínios para destravar fluxo.
- Descobrir trabalho de outro papel não transfere ownership; dependências/handoffs devem ser materializados na authority apropriada.

## Invariantes globais de produto

- Câmera fixa/fixed-frame é requisito consolidado do viewer; não reabrir navegação 3D livre sem decisão explícita.
- Dados físicos ou comerciais desconhecidos não devem ser inventados.

## Bootstrap

Comece pelo estado/tooling corrente, não pela reconstrução do histórico:

```bash
python3 tools/agent.py status
```

Use `python3 tools/agent.py doctor` quando a capacidade do ambiente importar. `doctor` diferencia executables/providers locais de capabilities lógicas; uma capability `UNKNOWN` pode exigir observação explícita de provider externo por `tools/runtime_capabilities.py`. Contratos semânticos transversais vivem em `ops/semantics/registry.json`.

Regras específicas de papel pertencem aos Kickstarts correntes em `docs/kickstarts/roles/*-current.md`. Versões antigas são história, salvo referência explícita do documento corrente.

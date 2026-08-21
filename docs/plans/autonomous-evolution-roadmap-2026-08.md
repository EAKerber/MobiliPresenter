# MobiliPresenter — mapa de maturidade para evolução autônoma

Status: planejamento derivado, não authority  
Data de reconciliação: 2026-08-21  
Repositório observado: `EAKerber/MobiliPresenter`  
Entrada desta reconciliação: `main@9ae230a9d9bbe24830cf9a93aa655566aae9c1d8`

Este documento reconcilia o plano original `M0`–`M12` com a evolução posterior
`M9`–`M16`. Ele não substitui ProjectState, Work, Coordination, capabilities,
contracts nem writers canônicos. Estados de experimento continuam nas suas
evidências próprias; aqui existe apenas uma projeção de planejamento.

Fontes preservadas:

- `docs/plans/project-machine-m0-m12-original-source.md`;
- `docs/plans/autonomous-evolution-architecture-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-closure-v0.1.md`;
- `docs/experiments/scheduled-cycle-maturity-s1-result-v0.1.json`.

## 1. Invariantes herdados

1. Toda mudança significativa percorre
   `observe -> plan -> validate -> apply -> readback -> receipt -> sanitize`.
2. Um fato mutável possui uma authority e um writer canônico.
3. Representação derivada nunca vira authority por conveniência.
4. Nondeterminism pode propor; somente política determinística pode autorizar.
5. `UNKNOWN` nunca equivale a `PASS`.
6. O paved path deve ser o caminho mais curto.
7. Quiescence exige observação suficiente, coerência e ausência de transição
   obrigatória conhecida; não é apenas fila vazia.
8. Autonomia nasce em shadow, passa por isolamento e limites e só então pode
   receber authority estreita.
9. Superfícies constitucionais nunca são promovidas automaticamente.

## 2. Estado reconciliado dos marcos

| Faixa | Objetivo revisado | Estado reconciliado em 2026-08-21 |
|---|---|---|
| M0–M8 original | Project Machine, authorities e writers básicos | fundação substancialmente presente; não recertificada aqui |
| M9 | Technical Dictionary, Semantic Scope e Determinism Contract | parcial; infraestrutura 0.2 existe, contratos finais não estão fechados |
| M10 | `OperationalSemantics 0.3` e cobertura integral | aberto; registry corrente permanece 0.2 |
| M11 | convergência de `lock`, aliases, triggers e resíduos | aberto; `tools/lock.py` ainda é implementação independente |
| M12 | maturity proof sob trabalho funcional real | executado em S0/S1, mas **não aprovado**; S1 terminou `CLOSED_DEFERRED` |
| M13 | Reflection + OperationalQuiescence | não iniciado como implementação; bloqueado por plano/closure M9–M12 |
| M14–M16 | Hypothesis, Experiment/Deathcycle, capability e prova longa | bloqueados |

M12-S1 não é mais o próximo estágio. Ele terminou com:

- seis runs elegíveis;
- `providerGapRate=1.0`;
- `pavedPathCompletionRate=0.0`;
- zero falso PASS, mutação em `main` ou escape de escopo;
- disposition `DEFERRED`, retry `ON_CONTRACT_CHANGE`;
- tasks desabilitadas e branches coletadas com cleanup readback `PASS`.

O protocolo futuro já corrige dois pontos de S1, mas não está admitido:

- branches por role, não por worker;
- preferência verificável por ChatGPT web standalone fora de Work, falhando
  fechado quando o contexto não puder ser selecionado ou observado.

Essas correções vivem em
`docs/experiments/scheduled-cycle-maturity-next-protocol-v0.1.md`. Não existe
S2 ativo, task ativa ou branch experimental reservada.

## 3. Resultado do recorte PCS-01A

O plano coordenado de metadata de apresentação foi aceito sem implementar
produto. A issue #22 foi separada logicamente em metadata de módulos (`PCS-01`)
e escolhas/acessórios configuráveis (`PCS-02`).

Estado materializado pela mesma transição que integra esta reconciliação:

```text
checkpoint = MODULE-PRESENTATION-METADATA-PLAN-0.1-ACCEPTED
phase = between-increments
nextTransition = plan-m9-m13-closure-before-module-metadata-implementation-v0.1
```

Assim, o plano de produto fica recuperável, mas sua implementação não compete
com a decisão do usuário de fechar o caminho até M13 antes de avançar além
deste recorte.

## 4. Próxima sequência deliberada

O readback pós-merge de PCS-01A é condição de validade deste estado, não uma
nova slice. A sequência posterior é:

1. Planejar M9–M13 como uma sequência de slices verificáveis, sem declarar
   marcos concluídos apenas porque parte do mecanismo existe.
2. Fechar M9, M10 e M11 ou materializar blockers precisos.
3. Definir o que constitui aprovação M12 após o resultado `DEFERRED` de S1.
4. Implementar Reflection e OperationalQuiescence M13 somente sobre inputs
   canônicos e com `UNKNOWN != PASS`.
5. Reavaliar a admissão de PCS-01B depois do gate acordado.
6. Manter M14–M16 bloqueados até seus predecessores reais passarem.

Não se deve repetir S1/S2 apenas para produzir atividade. O retry exige mudança
de contrato e uma qualificação manual branch-confined com planner e readback
canônicos.

## 5. Lacunas conhecidas que o plano M9–M13 deverá resolver

- registry ainda em `OperationalSemantics 0.2`;
- cobertura semântica e guard correspondentes ainda incompletos;
- `tools/lock.py` ainda não convergiu para alias fino da Coordination canônica;
- Routine Layer obrigatória cobre somente `capability-deathcircle`;
- Reflection e OperationalQuiescence não possuem contratos/tooling correntes;
- o runtime de Scheduled Tasks observado em S1 não executou o planner canônico;
- lifecycle/deathcycle persistível do experimento ainda não foi provado;
- execution context normal versus Work não é provider-verified na superfície
  observada.

Uma lacuna de provider e uma lacuna de implementação interna podem coexistir;
nenhuma deve ser usada para esconder a outra. A classificação precisa fica para
o plano M9–M13.

## 6. Freshness deste roadmap

Este arquivo já ficou defasado depois de S1, repetindo um padrão anterior de
documentação narrativa que continuava anunciando o recorte recém-concluído como
“próximo”. A correção aqui é factual, mas ainda não elimina a causa estrutural.

Regra imediata:

- qualquer PR que altere `ProjectState.development.checkpoint` ou
  `nextTransition` deve revisar afirmações de estado corrente neste roadmap e
  nos ponteiros `*-current.md` afetados;
- a revisão pode concluir `NO_CHANGE`, mas precisa ser explícita no PR;
- baseline histórico deve ser rotulado como entrada da reconciliação, nunca
  como substituto do head corrente.

Débito declarado para o plano M9–M13:

```text
ROADMAP_FRESHNESS_GUARD = OPEN
```

O objetivo é transformar essa revisão recorrente em cobertura determinística ou
derivação, em vez de depender permanentemente da memória do autor. Até essa
capability existir, este roadmap continua honestamente classificado como
derivado e pode apresentar drift sem corromper authority.

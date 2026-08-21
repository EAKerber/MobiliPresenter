# PCS-01A — plano coordenado de metadata de apresentação de módulos 0.1

Status: `ACCEPTED_PLAN / IMPLEMENTATION_NOT_ADMITTED`  
Data: 2026-08-21  
Entrada observada: `main@9ae230a9d9bbe24830cf9a93aa655566aae9c1d8`  
Issue de origem: [#22 — UI contract: module presentation metadata and configurable accessories](https://github.com/EAKerber/MobiliPresenter/issues/22)

Este documento é um plano derivado. Ele não é catálogo de produto, Work,
Continuation, Coordination nem authority de execução. O checkpoint aceito em
`ops/state/project.json` registra somente que o recorte foi planejado.

## 1. Decisão

A issue #22 mistura duas capacidades com authorities, riscos e critérios de
prontidão diferentes. Ela permanece como umbrella, mas sua execução fica
separada em:

| Slice | Capacidade | Situação após PCS-01A |
|---|---|---|
| `PCS-01` | identidade editorial e referência controlada de preview por módulo | planejada; implementação não admitida |
| `PCS-02` | escolhas e acessórios configuráveis genéricos, compatibilidade e comandos | posterior; fora deste plano |

PCS-01 não deve antecipar PCS-02. Um componente, requisito ou especificação não
se torna escolha configurável por texto, heurística ou conveniência da UI.

A implementação de PCS-01 também fica retida até a próxima transição de
planejamento fechar o caminho M9–M13 solicitado para a infraestrutura. O
`nextTransition` aponta essa decisão; não constitui assignment.

## 2. Autoridades e fronteiras observadas

| Fato | Fonte corrente | Regra de projeção |
|---|---|---|
| aliases `01`–`07` e vínculo com entity id | `viewer-next/src/runtime/query.ts` + Scene Core | preservar IDs e ordem; UI não cria aliases |
| identidade apresentável de 02/03/04 | `TechnicalCatalogEntry.identity` | projetar pelo adapter público |
| identidade apresentável de 01/05/06/07 | nenhuma entrada no Technical Catalog | expor indisponibilidade; não inferir de nomes de símbolo, geometria ou filename |
| preview/thumbnail editorial | nenhum asset controlado publicado pelo contrato | expor indisponibilidade; não capturar canvas nem promover diagrama técnico automaticamente |
| geometria e dimensões físicas | Scene Core | não duplicar em metadata editorial |
| ficha e vistas técnicas | Technical Presentation Package | manter contrato existente; preview de lista é capacidade separada |
| opções de acabamento existentes | Appearance Catalog + políticas técnicas + runtime | não reclassificar como catálogo genérico de acessórios |
| escolha/acessório configurável genérico | não publicado pelo `ViewerUiContract 0.1.1` | PCS-02 somente depois de semântica e binding reais |

`src/ui/**` continua consumidor exclusivo de `src/api/**`. O adapter pode ler as
authorities internas existentes; a UI não pode atravessar a fronteira para
`runtime`, `presentation`, `renderer`, `fixtures` ou Scene Core.

## 3. Matriz de cobertura de módulos

Esta matriz registra disponibilidade, não inventa conteúdo faltante.

| Alias | Entity id resolvível | `TechnicalIdentity` | Preview controlado | Projeção inicial esperada |
|---|---:|---:|---:|---|
| `01` | sim | não | não | identity unavailable; preview unavailable |
| `02` | sim | sim | não | identity ready; preview unavailable |
| `03` | sim | sim | não | identity ready; preview unavailable |
| `04` | sim | sim | não | identity ready; preview unavailable |
| `05` | sim | não | não | identity unavailable; preview unavailable |
| `06` | sim | não | não | identity unavailable; preview unavailable |
| `07` | sim | não | não | identity unavailable; preview unavailable |

Os títulos atuais de 02, 03 e 04 são fatos do Technical Catalog. O plano não os
repete como nova authority. Para os demais aliases, nomes técnicos, comerciais
ou editoriais permanecem desconhecidos até uma fonte apropriada ser autorada.

## 4. Projeção pública proposta

A evolução recomendada é aditiva, compatível com os consumidores 0.1.x:

- preservar `ViewerUiCatalog.modules: readonly ModuleAlias[]`;
- adicionar `modulePresentations`, na mesma ordem estável;
- elevar o contrato para `ViewerUiContract 0.1.2` se a implementação continuar
  estritamente aditiva;
- representar disponibilidade de identidade e preview separadamente;
- carregar provenance/source refs quando o dado estiver pronto.

Shape conceitual — o nome final pertence à slice de implementação:

```ts
interface ViewerUiModulePresentation {
  readonly alias: ModuleAlias;
  readonly identity:
    | {
        readonly status: "ready";
        readonly title: string;
        readonly shortLabel: string | null;
        readonly category: string;
        readonly sourceRefs: readonly TechnicalSourceRef[];
      }
    | {
        readonly status: "unavailable";
        readonly reason: "technical-catalog-entry-missing";
      };
  readonly preview:
    | {
        readonly status: "ready";
        readonly assetRef: string;
        readonly alt: string;
        readonly sourceRefs: readonly TechnicalSourceRef[];
      }
    | {
        readonly status: "unavailable";
        readonly reason: "presentation-asset-not-authored";
      };
}
```

Não existe fallback para `alias` como título editorial, para label derivada do
entity id, para screenshot de canvas nem para `TechnicalDiagramAsset` usado como
thumbnail sem uma decisão explícita de produto e provenance compatível.

## 5. Grafo futuro de implementação

Este grafo é planejamento derivado; não cria Work nem atribui papel.

| Nó | Owner semântico | Entrega | Depende de |
|---|---|---|---|
| `PCS-01B-E1` | Engine/API | tipos aditivos e projeção determinística pelo adapter | fechamento/admissão após M9–M13 |
| `PCS-01B-E2` | Engine/API | testes de cobertura, IDs, ordem, provenance e indisponibilidade | `E1` |
| `PCS-01C-U1` | UI/UX | lista consome somente a projeção pública | `E1`, `E2`, Work UI explícito |
| `PCS-01C-U2` | UI/UX | estados ready/unavailable e acessibilidade do preview | `U1` |
| `PCS-02A` | coordenado | semântica de escolhas/acessórios e knowledge states | conclusão de PCS-01 e contrato próprio |

Nenhum desses nós está admitido por este documento. Quando houver admissão,
Work/Continuation/lease e branch deverão ser materializados pelas authorities e
writers correntes.

## 6. Gates da implementação futura

Uma implementação de PCS-01 só pode ser considerada concluída quando:

1. aliases e IDs do `ViewerUiContract 0.1.1` permanecerem estáveis;
2. 02/03/04 forem projetados do Technical Catalog, sem cópia de catálogo na UI;
3. 01/05/06/07 retornarem indisponibilidade explícita e testada;
4. preview sem asset autoritativo continuar indisponível;
5. nenhum canvas/runtime render for usado para fabricar thumbnail;
6. `src/ui/**` continuar sem imports proibidos;
7. a UI não interpretar strings para distinguir escolha, requisito, componente,
   dependência, aviso ou representação;
8. testes do contrato UI, Technical Presentation, boundary e build passarem;
9. uma mudança visual posterior possuir evidência desktop/mobile sem alterar a
   câmera fixa, pan, zoom ou framing heurístico.

Testes candidatos já existentes:

- `viewer-next/tests/ui-contract.test.mjs`;
- `viewer-next/tests/technical-presentation.test.mjs`;
- `viewer-next/tests/technical-presentation-fidelity.test.mjs`;
- o gate de imports de `src/ui/**`.

## 7. Não escopo

- implementar tipos, adapter ou UI neste recorte;
- autorar títulos para 01/05/06/07;
- criar ou capturar thumbnails;
- expor acessórios, hardware configurável ou mutation commands;
- converter acabamentos existentes em opções genéricas;
- criar Work, continuation, lease, branch experimental ou Scheduled Task;
- fechar a issue #22;
- declarar M12 aprovado, OperationalQuiescence ou M13 concluído.

## 8. Transição aceita

Após integração deste plano:

```text
checkpoint = MODULE-PRESENTATION-METADATA-PLAN-0.1-ACCEPTED
phase = between-increments
nextTransition = plan-m9-m13-closure-before-module-metadata-implementation-v0.1
```

O produto permanece no baseline Responsive Fixed-Frame integrado. O próximo
recorte é de planejamento da infraestrutura M9–M13; PCS-01B fica aguardando uma
admissão posterior explícita.

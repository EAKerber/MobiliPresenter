# Developer continuation — 2026-08

Status: current coordination plan

## Estado

O renderer de câmera fixa foi publicado em `main` e a frente de UI segue em paralelo sobre os contratos internos do Viewer Next.

Não há branch Developer principal ativa entre incrementos. O próximo recorte só deve materializar nova `activeDevelopmentBranch` e `prNumber` quando a implementação começar de fato.

## Ordem imediata

1. corrigir fidelidade das technical views, derivando geometria técnica da autoridade física em vez de usar representações genéricas;
2. corrigir #28 para que seleção válida sem TPC degrade para apresentação indisponível sem quebrar `getSnapshot()`;
3. formalizar comportamento responsivo do viewport preservando a câmera fixa como invariante;
4. avançar #22 somente depois dos contratos anteriores, expondo as capacidades necessárias sem empurrar lógica de domínio para `src/ui/**`;
5. retomar recortes de fidelidade do renderer quando os bloqueios de contrato acima estiverem fechados.

## Fronteira UI × Engine

- UI modifica `viewer-next/src/ui/**` e documentação visual correspondente;
- Engine/Developer modifica runtime, renderer, presentation, Scene Core e `viewer-next/src/api/**` quando um contrato público interno precisa evoluir;
- `bootstrap.ts`, build e workflows são pontos de integração e não devem ser usados como coordenação informal entre as duas frentes;
- câmera fixa, mm como autoridade física e ausência de inferência técnica pela UI permanecem invariantes.

## Git

Enquanto não houver um novo recorte Developer iniciado:

- `git.activeDevelopmentBranch = null`;
- `development.prNumber = null`;
- branches paralelas preservadas são explicitadas em `git.preserveBranches`;
- `main` continua sendo controle e publicação;
- branch histórica do renderer permanece preservada para rastreabilidade, sem ser tratada como trabalho ativo.

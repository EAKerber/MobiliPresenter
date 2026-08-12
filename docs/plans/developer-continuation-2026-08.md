# Developer continuation — 2026-08

Status: current coordination plan

## Estado

TPF-01 e Guided Configurator UI 0.3 estão integrados em `main`. A seleção válida sem TPC foi validada pela UI com disponibilidade explícita e a issue #28 foi encerrada como concluída.

Não há branch Developer principal ativa entre incrementos. O próximo recorte só deve materializar nova `activeDevelopmentBranch` e `prNumber` quando a implementação começar de fato.

A próxima frente Developer acordada é **Responsive Fixed-Frame 0.1**. O objetivo é adaptar deterministicamente o frame/viewport a áreas menores sem reabrir a câmera fixa e sem introduzir pan, zoom ou focus heurísticos.

## Ordem imediata

1. abrir Responsive Fixed-Frame 0.1 sobre a baseline reconciliada;
2. definir e validar adaptação determinística do frame em desktop/mobile preservando a composição de câmera fixa;
3. manter a UI responsável apenas pela alocação de viewport, sem autoridade sobre câmera, geometria ou heurísticas de enquadramento;
4. avançar #22 / PCS-01 depois do contrato responsivo, expondo semântica de apresentação/configuração sem empurrar lógica de domínio para `src/ui/**`;
5. retomar novos recortes de fidelidade do renderer somente depois dessas dependências de contrato.

## Incrementos já absorvidos

- technical-view fidelity: frontal 02/03 `geometry-derived`, com cobertura parcial explicitamente rastreável;
- graceful no-TPC selection: `ViewerUiContract 0.1.1` integrado e validado pela UI;
- Guided Configurator UI 0.3: fluxo guiado, cena persistente e diferenciação visual entre technical views `geometry-derived` e `schematic` integrados em `main`.

## Fronteira UI × Engine

- UI modifica `viewer-next/src/ui/**` e documentação visual correspondente;
- Engine/Developer modifica runtime, renderer, presentation, Scene Core e `viewer-next/src/api/**` quando um contrato público interno precisa evoluir;
- `bootstrap.ts`, build e workflows são pontos de integração e não devem ser usados como coordenação informal entre as duas frentes;
- câmera fixa, mm como autoridade física e ausência de inferência técnica pela UI permanecem invariantes;
- Responsive Fixed-Frame pode adaptar o frame disponível, mas não criar navegação livre, pan/zoom arbitrário ou `focus-to-module` heurístico.

## Git

Enquanto não houver um novo recorte Developer iniciado:

- `git.activeDevelopmentBranch = null`;
- `development.prNumber = null`;
- branches paralelas preservadas são explicitadas em `git.preserveBranches`;
- `main` continua sendo controle e publicação;
- branch histórica do renderer permanece preservada para rastreabilidade, sem ser tratada como trabalho ativo.

# I4 — Realistic reference pass

## Objetivo

Testar um primeiro modo visual mais realista sem abandonar os contratos estruturais consolidados no I2/I3.

O I4 não gera uma cozinha nova por inferência. Ele reutiliza a própria composição visual fornecida como fonte de pixels e cria overlays recortados por módulo na câmera fixa.

## Estratégia

A cena passa a ter dois modos:

- `neutral-wall`: renderer estrutural, útil para verificar topologia, regras e ausência/presença dos módulos;
- `reference-context`: apresentado na interface como `Render realista β`; usa recortes da composição fornecida como overlays dos módulos habilitados.

Cada overlay realista é limitado pelo `calibration.json`. O módulo estrutural continua existindo por baixo como fallback e como fonte da área clicável.

## Invariantes

1. O modo realista não pode criar, remover ou fundir módulos.
2. Um módulo habilitado precisa continuar rastreável por `moduleId`.
3. O módulo 03 continua obrigado a representar 4 gavetas + 2 portas no contrato estrutural, mesmo que o overlay visual venha de uma imagem.
4. A lateral da geladeira é uma chapa estrutural de MDF 18 mm e deve ter leitura visual delgada; a antiga largura de 48 px foi descartada como grosseira.
5. A coluna atrás do tanque é geometria fixa do ambiente, com 739 mm ao longo da parede e 206 mm de avanço interno. Sua posição exata na câmera permanece calibrável.
6. Pixels da referência não podem ser convertidos em cotas de fabricação.
7. O empreendimento continua usando a referência fornecida pelo usuário, sem reimaginação.

## Render realista incremental

O I4 deliberadamente aceita realismo parcial:

- o ambiente-base continua provisório;
- os módulos habilitados podem usar pixels reais da composição fornecida;
- módulos sem overlay futuro continuam com fallback estrutural;
- o fogão convencional continua como fallback declarado quando o item 02 estiver desabilitado;
- a seleção continua sendo representada por hit area independente da arte.

Isso permite substituir progressivamente os recortes por overlays/máscaras melhores sem reescrever a UI ou o motor comercial.

## UX ajustada

O seletor de contexto foi refinado para reduzir peso visual. `Contexto de referência` passa a se apresentar como `Render realista β`.

O highlight do módulo selecionado foi reduzido para um contorno fino e discreto. O último módulo ativado mantém uma animação curta, mas sem a borda larga observada no I3.

As miniaturas e o hero do detalhamento passam a reutilizar recortes da própria composição de referência, com foco visual no módulo correspondente.

## Limitações conhecidas

- O recorte de uma composição completa pode conter sombras/oclusões do contexto original.
- A cor do modo realista representa a referência visual original; recoloração realista continua fora deste recorte.
- A coluna tem dimensões físicas confirmadas, mas a posição de câmera ainda é provisória.
- A ausência de uma imagem limpa do ambiente sem módulos impede reconstrução perfeita dos estados desabilitados.

Essas limitações são explícitas e não invalidam o objetivo do I4: testar um pipeline visual mais fiel sem perder determinismo estrutural.

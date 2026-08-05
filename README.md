# MobiliPresenter

Apresentador modular de mobiliário baseado em sequências de imagens pré-renderizadas, composição multimódulo e metadados físicos em milímetros.

## Estado publicado

- versão: **V7.0-I5**
- finalidade atual: validação técnica e mobile via Netlify
- composição de referência: gaveteiro de 399 mm à esquerda + balcão de 780 mm à direita
- amplitude angular: yaw de -95° a +95°, passo de 5°
- camada fabril: parcial; dados desconhecidos permanecem explícitos e não são inventados

## Páginas

- `/` — viewer da composição
- `/manufacturing.html` — peças, BOM, ferragens, furos e pendências
- `/module-viewer.html` — negociação angular por módulo
- `/importer.html` — importador assistido

## Publicação

O Netlify deve usar a branch `main`. O conteúdo publicado é preparado pelo script `deploy.py` a partir do snapshot versionado no repositório.

## Governança Git

Este repositório é exclusivo do projeto MobiliPresenter. Operações em qualquer outro repositório exigem confirmação explícita no chat ativo.

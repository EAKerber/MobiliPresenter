# MobiliPresenter

Apresentador modular de mobiliário baseado em sequências de imagens pré-renderizadas, composição multimódulo e metadados físicos em milímetros.

## Estado publicado

- versão: **V7.0-I5**
- URL canônica: **https://mobilipresenter.netlify.app/**
- finalidade atual: validação mobile pelo Netlify
- composição de referência: gaveteiro de 399 mm à esquerda + balcão de 780 mm à direita
- amplitude angular: yaw de -95° a +95°, passo de 5°, 39 poses
- controles publicados: rotação, presets angulares e visibilidade independente das instâncias
- camada fabril: resumo parcial; dados desconhecidos permanecem explícitos e não são inventados

## Páginas publicadas

- `https://mobilipresenter.netlify.app/` — viewer mobile da composição
- `https://mobilipresenter.netlify.app/manufacturing.html` — estado semântico e fabril da V7.0-I5

O preview hospedado é um artefato leve para validação pelo celular. Ele usa dois spritesheets WebP alinhados e não substitui o snapshot técnico completo da iteração.

## Integridade dos artefatos

### Preview Netlify

- artefato: `mobilipresenter-v7.0-i5-netlify-spritesheet.zip`
- tamanho: 70.551 bytes
- SHA-256: `38648499ff4483f35d023ba453c1f5d1c1c19f4e63153130b9ab14bd620a18ae`

### Snapshot técnico completo

- artefato: `mobilipresenter-v7.0-i5-preview.zip`
- tamanho: 942.520 bytes
- SHA-256: `c158d68afff547b9c3ef83e16b2963c692b10bba65f439cbf9da261a80dd1d83`

## Publicação determinística

O Netlify usa a branch `main`, executa `python3 deploy.py` e publica a pasta `site`.

O preview é versionado em fragmentos Base64 acompanhados de manifesto. Durante o build, `deploy.py`:

1. valida o tamanho e o SHA-256 de cada fragmento;
2. reconstrói o ZIP;
3. valida tamanho e SHA-256 do artefato integral;
4. rejeita membros ZIP inseguros;
5. extrai o site somente após todas as verificações.

Uma divergência interrompe o deploy em vez de publicar conteúdo parcial ou silenciosamente diferente.

## Governança Git

Este repositório é exclusivo do projeto MobiliPresenter. Operações em qualquer outro repositório exigem confirmação explícita no chat ativo. O protocolo completo para agentes está em `AGENTS.md`.

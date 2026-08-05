# Snapshot de publicação

O pipeline espera o arquivo:

`mobilipresenter-v7.0-i5-preview.zip`

O ZIP deve conter `index.html` na raiz. Durante o deploy, `deploy.py` extrai seu conteúdo para o diretório `site`, publicado pelo Netlify.

Este mecanismo é transitório para consolidar a V7.0-I5 e permitir validação mobile. A evolução seguinte deve manter código e metadados textuais diretamente versionados e reservar snapshots apenas para assets raster pesados.

# Snapshot de publicação

A V7.0-I5 é publicada pelo Netlify a partir de um artefato binário reconstruído de forma determinística.

## Estrutura ativa

- `mobile/manifest.json` — identidade, tamanho, hashes e ordem dos fragmentos
- `mobile/000.b64` … `mobile/006.b64` — conteúdo Base64 do preview
- `deploy.py` — validação, reconstrução e extração para `site`

Não é necessário enviar manualmente um ZIP ao GitHub.

## Contrato do build

O build deve:

1. ler os fragmentos na ordem declarada pelo manifesto;
2. confirmar comprimento e SHA-256 de cada fragmento;
3. concatenar e decodificar o Base64 estritamente;
4. confirmar 70.551 bytes e SHA-256 `38648499ff4483f35d023ba453c1f5d1c1c19f4e63153130b9ab14bd620a18ae`;
5. rejeitar paths absolutos, travessia de diretório, barras invertidas e links simbólicos dentro do ZIP;
6. extrair somente após a validação integral;
7. confirmar a presença de `index.html`, `manufacturing.html` e `DEPLOYMENT.json`.

Qualquer divergência deve falhar o deploy.

## Escopo do preview

O artefato publicado é deliberadamente leve e serve para validação pelo celular. Ele contém 39 poses de yaw, visibilidade independente dos módulos, ordenação por profundidade e resumo fabril.

O snapshot técnico completo permanece identificado separadamente por tamanho e SHA-256 no `README.md`; sua ausência neste diretório não autoriza reconstrução ou substituição silenciosa.

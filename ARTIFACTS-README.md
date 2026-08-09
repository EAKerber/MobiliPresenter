# MobiliPresenter — temporary user artifact handoff

Esta branch existe exclusivamente para tornar **duráveis e recuperáveis** os arquivos que serão apresentados ao usuário durante o desenvolvimento.

## Regras

- Não integrar esta branch em `main`.
- Um arquivo só é considerado entregue quando existe nesta branch e foi lido de volta do GitHub.
- `/mnt/data` é apenas staging local; nunca é autoridade de entrega.
- Artefatos binários são publicados pela CI do Viewer, não reconstruídos de memória pelo agente.
- Cada conjunto fica em `artifacts/fh06/<source-sha-curto>/` e registra o SHA completo do commit de origem, run do GitHub Actions, tamanho e SHA-256 dos arquivos.
- `LATEST.json` aponta para o conjunto verificado mais recente.
- Conjuntos antigos permanecem enquanto forem úteis ao handoff; esta branch pode ser podada quando o incremento terminar.

## Recuperação

Qualquer agente novo precisa apenas localizar esta branch e ler `LATEST.json` + o `ARTIFACTS.json` do conjunto apontado. Não é necessário lembrar nomes de arquivos vindos do chat.

O antigo `round-20-fh06-candidate.zip` não é uma entrega válida: a cópia em staging foi inspecionada com apenas 22 bytes e não deve ser preservada ou reutilizada.

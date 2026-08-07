# I4.1 — prova de sprite independente do módulo 03

## Objetivo

Substituir o experimento de recortes retangulares da composição completa por um primeiro asset visual independente, mantendo os contratos estruturais do I2/I3 como autoridade.

## Caso de prova

O módulo 03 (Inferior da pia) foi escolhido porque possui uma invariante visual forte e verificável: **4 gavetas + 2 portas**. Qualquer asset que não preserve essa topologia deve falhar no gate antes de ser promovido.

## Estratégia

- O sprite da cena usa um canvas transparente de 1423×810, igual ao espaço lógico da câmera fixa.
- O módulo é colocado uma única vez no canvas; o navegador não precisa recortar a composição geral para reconstruí-lo.
- A fonte visual é a ficha recente do módulo 03 fornecida pelo usuário (`1000101452.jpg`), não a composição antiga amadeirada.
- Anotações vermelhas da ficha foram removidas localmente sem reconstruir a forma do móvel.
- Um segundo asset menor é usado na miniatura e no detalhe.
- Os demais módulos continuam no renderer estrutural enquanto não possuem sprite independente.

## Limites

O I4.1 valida o pipeline, não a cena realista completa. O fundo continua sendo o ambiente neutro/provisório e a posição do sprite é de apresentação. Nenhum pixel pode produzir cota de fabricação.

A variante de cor também ainda não é derivada deste sprite. O asset representa o Cinza Gianduia de referência e `colorTransformReady` permanece falso.

## Gates

- módulo associado: `lower-sink` / item 03;
- topologia: 4 gavetas + 2 portas;
- integridade SHA-256 dos assets;
- canvas fixo 1423×810;
- proibição de derivar dimensões métricas dos pixels;
- fallback estrutural obrigatório se o sprite falhar;
- bootstrap I4.1 não carrega mais o runtime de recortes retangulares I4.

## Critério de sucesso visual

No modo `Sprite realista 03 β`, ativar/desativar o item 03 deve alternar apenas esse móvel entre ausência e sprite realista, preservando o restante da composição estrutural. O detalhe e a miniatura do item 03 devem usar o mesmo asset visual derivado.

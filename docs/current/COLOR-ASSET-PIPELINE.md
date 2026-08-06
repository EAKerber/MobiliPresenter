# Pipeline atual de cores — fatos recuperados

**Status:** factual, recuperado dos ZIPs `balcao-360-calibrador-v5.zip`, `balcao-360-calibrador-v6.zip` e `balcao-360-v7-i5.zip`.  
**Finalidade:** distinguir assets existentes, método de geração e limitações de confiabilidade.

## Resposta operacional

O módulo canônico `balcao-1182` da V7.0-I5 possui arquivos separados para seis variantes:

- branco;
- grafite;
- areia;
- sálvia;
- azul petróleo;
- preto.

Cada variante possui 72 poses de yaw e dois LODs compilados. Portanto, existem 144 arquivos WebP compilados por cor, além dos 72 frames-fonte por cor no `ModuleSource`.

A composição dividida em `modulo-composto-gaveteiro`, `modulo-composto-balcao` e `modulo-composto-completo` não repete essas seis variantes. Esses pacotes preservam somente a variante `original`, em 39 poses comuns e dois LODs. Consequentemente, o viewer multimódulo e o preview Netlify atuais não constituem ainda um configurador de cores da montagem.

## Origem das variantes sólidas

A V5 introduziu o método `thresholded grayscale gamma transfer` sobre os 72 frames brancos originais. A transformação:

- seleciona superfícies claras e de baixa cromaticidade;
- preserva fundo cinza, linhas estruturais escuras e pés;
- aplica uma cor-alvo, uma curva gama e um piso de sombra;
- produz assets pré-calculados para uso offline determinístico.

As receitas recuperadas são:

| Variante | RGB alvo | Gama | Piso de sombra |
|---|---:|---:|---:|
| grafite | 91, 94, 96 | 0,90 | 0,48 |
| areia | 214, 196, 166 | 0,96 | 0,46 |
| sálvia | 158, 171, 151 | 0,94 | 0,47 |
| azul petróleo | 69, 104, 111 | 0,90 | 0,50 |
| preto | 52, 54, 55 | 0,86 | 0,54 |

Premissas recuperadas:

- limiar de luminância do móvel: 100;
- cromaticidade máxima da fonte: 14;
- fonte original predominantemente branca/neutra;
- finalidade: MDF liso e cores chapadas.

## Evidência de validação

A validação da V5 confirmou:

- 72 frames em cada uma das cinco cores derivadas e no branco original;
- desvio médio máximo do fundo de 0,051;
- desvio médio máximo das estruturas escuras de 1,905;
- alteração média mínima das superfícies de 62,03;
- funcionamento offline por assets pré-calculados.

A V6 voltou a validar 72 frames para grafite, areia, sálvia, petróleo e preto.

## O método deixou de ser confiável?

Não. Não existe decisão ou evidência de que a transferência de gama tenha sido abandonada por falha. Ela foi validada e permanece adequada ao caso estreito para o qual foi criada: recoloração de uma captura branca/neutra de MDF liso para cores sólidas.

Ela não deve ser tratada como representação física ou método universal de materiais. Não cobre de forma confiável:

- madeirados e veios;
- texturas;
- superfícies com cromaticidade original relevante;
- materiais múltiplos que compartilham luminância semelhante;
- alterações reais de reflexão, brilho, rugosidade ou resposta à iluminação;
- cenas cuja iluminação ou balanço de branco difira da fonte calibrada.

## Lacuna da V7.0-I5

A V7 preserva os assets resultantes e declara as seis variantes no `capture.json` e no `visual.json`, mas não transporta a receita de gama nem sua proveniência como parte do contrato `ModuleSource 1.0`.

Assim:

- consumir as cores existentes é determinístico;
- recompilar os mesmos assets existentes é determinístico;
- gerar uma nova cor de maneira equivalente não é plenamente reproduzível usando apenas os contratos V7;
- a reprodutibilidade completa ainda depende do `color-recipes.json` recuperado da V5.

## Decisão pendente para o novo escopo

A fase de planejamento deve decidir entre:

1. manter variantes pré-calculadas por módulo;
2. formalizar uma receita versionada de transformação de cor no `ModuleSource`;
3. usar recoloração em runtime apenas para pré-visualização não autoritativa;
4. exigir assets próprios para materiais texturizados ou de resposta óptica distinta.

Nenhuma dessas alternativas está aprovada ainda.

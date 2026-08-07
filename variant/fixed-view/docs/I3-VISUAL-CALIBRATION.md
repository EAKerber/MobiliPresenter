# I3 — Visual Calibration Under Uncertainty

## Motivo

As medidas de fabricação mais exatas não devem ser tratadas como pré-requisito para continuar o protótipo de câmera fixa. O I3 separa duas geometrias que antes podiam ser confundidas:

1. **geometria semântica/construtiva** — identidade do módulo, topologia, regras, medidas confirmadas e decisões explícitas;
2. **geometria de apresentação** — posição e tamanho aparentes na câmera fixa, calibrados diretamente no espaço da imagem de referência.

A primeira pode futuramente servir fabricação quando tiver dados suficientes. A segunda serve somente apresentação.

## Princípio de segurança

**Pixel não vira milímetro.**

A largura de 3550 mm continua sendo o envelope operacional aceito para planejamento, mas não cria uma escala métrica automática dentro do render. O contrato `calibration.json` proíbe explicitamente derivar cotas faltantes a partir de pixels.

Isso permite continuar trabalhando com as referências atuais sem produzir falsa precisão.

## O que pode avançar sem novas cotas

- alinhamento visual dos módulos na câmera fixa;
- proporções aparentes na composição;
- miniaturas coerentes;
- máscaras e hit areas;
- ordem de oclusão;
- seleção visual/comercial;
- destaque de módulo;
- cores de frente;
- puxadores/aberturas;
- fallback do fogão convencional;
- iluminação e dependências;
- geração e avaliação de overlays realistas em câmera fixa.

## O que continua bloqueado para uso fabril

- lista de corte definitiva;
- furação final;
- folgas de instalação;
- posição de ferragens baseada apenas na imagem;
- inferência de profundidade/largura/altura não fornecida a partir do render;
- aprovação de instalação.

## Evidência e confiança

Cada placement registra:

- retângulo em pixels no espaço da referência;
- confiança `low`, `medium` ou `high`;
- justificativa textual (`basis`).

Confiança significa apenas **estabilidade visual da leitura**, não precisão dimensional.

Uma borda muito clara nas referências pode ter confiança visual alta mesmo sem nenhuma cota de obra.

## Pipeline realista incremental

`visual-layers.json` define uma vaga de overlay para cada módulo.

Enquanto o overlay realista não existe, o runtime deve usar o `topology-renderer`. Portanto, a ausência de arte nunca pode fazer um módulo desaparecer.

A migração esperada é incremental:

```text
contrato semântico
    ↓
fallback estrutural
    ↓
calibração na câmera fixa
    ↓
overlay realista individual
    ↓
comparação com referência
    ↓
overlay aprovado
```

Não é necessário esperar os oito overlays para começar. Um módulo pode ser promovido individualmente quando cumprir seus gates.

## Gates de overlay

Cada camada realista precisa:

1. alinhar com o espaço de calibração da câmera;
2. possuir transparência ou máscara explícita;
3. preservar a topologia do contrato do módulo;
4. não carregar módulo vizinho escondido no mesmo bitmap;
5. registrar origem e transformação;
6. continuar podendo ser desabilitada pelo checklist.

Para o módulo 03 existe um gate explícito `4-drawers-2-doors`. Um overlay que omita o gaveteiro é inválido mesmo que pareça visualmente plausível.

## Eletrodomésticos

Os eletrodomésticos continuam ilustrativos. Podem ser dimensionados visualmente para ocupar os vãos definidos pelos móveis e manter composição crível, mas o sistema não deve declarar marca, modelo ou medida exata sem fonte.

O módulo 02 preserva a regra:

- ativo → solução para forno/fogão embutido;
- inativo → fogão convencional independente como fallback visual.

## Quando recalibrar

O contrato lista gatilhos de substituição:

- imagem frontal/composição de melhor qualidade;
- medidas confiáveis da parede ou equipamentos;
- exportação Promob ou render com câmera conhecida;
- overlays ou máscaras limpas dos módulos.

Uma calibração nova deve substituir somente a camada de apresentação. Não deve exigir reescrever módulos, regras ou seleção comercial.

## Resultado do I3

O projeto pode continuar evoluindo visualmente com as referências atuais sem fingir uma precisão que não existe. As novas medidas, quando chegarem, serão uma melhoria da base física — não uma condição para manter o desenvolvimento em movimento.

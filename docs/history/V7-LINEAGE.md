# Linhagem recuperada — calibradores, MVP e V7

**Status:** histórico recuperado de artefatos ZIP.  
**Finalidade:** preservar decisões, resultados e correções que não estavam formalizados no repositório.

## Calibradores geométricos

### v1 — um slot físico

Introduziu dimensões em milímetros, câmera ortográfica calibrável, rotação em torno do eixo vertical e puxadores geométricos sem correções específicas por frame.

### v2 e v2.1 — coordenadas e face corrigidas

Corrigiu a interpretação dos eixos do Promob, distinguiu porta e gaveta, ampliou o recorte para cobrir os 360° e validou o mesmo plano físico em múltiplos ângulos.

### v3 e v3.1 — malha 3D e oclusão auditável

Passou a construir Rigato e Tango como malhas simples em coordenadas locais. A v3.1 corrigiu a assimetria de 90°/270° causada por ponto flutuante e separou geometria, orientação, envio ao renderer, descarte de backface e oclusão.

### v4 — seis slots

Aplicou a mesma arquitetura a duas portas e quatro gavetas. A orientação do Tango tornou-se propriedade local do slot, sem duplicar o modelo físico.

### v5 — acabamento visual

Separou apresentação de geometria: contorno por silhueta alfa, linhas internas mais finas e receitas de cor por transferência de gama.

### v6 — puxadores e compositor mobile

Consolidou modelos de Tango e Rigato, materiais por presets e publicação atômica em um único canvas mobile.

## MVPs anteriores

Os MVPs exploraram sobreposição de puxadores, remoção de elementos originais, cores, estabilidade por slot e diagnóstico visual. Foram importantes como experimentação, mas não são fonte arquitetural atual. Técnicas retidas foram absorvidas nos calibradores e depois na V7.

## V7

### V7.0-I1 — `ModulePackage`

- contratos `ModuleSource 1.0` e `ModulePackage 1.0`;
- compilador reproduzível e validador estrutural;
- viewer sem dados específicos do balcão codificados no renderer;
- dois LODs, cache por bytes e publicação atômica;
- importador assistido inicial;
- dados desconhecidos preservados como não verificados.

### V7.0-I2 — matriz parcial yaw × pitch

Adicionou uma fixture real com 39 yaw × 2 pitch. O ensaio revelou roll residual e demonstrou que ampliar pitch exigia calibração explícita, não síntese silenciosa.

### V7.0-I3 — negociação angular monotônica

Criou negociação por interseção de poses reais:

```text
capacidade efetiva ⊆ capacidade nativa
```

O negociador pode restringir faixa, aumentar passo, fixar eixo ou remover poses. Não pode ampliar capacidade nem inventar frames.

### V7.0-I4 — composição multimódulo

Introduziu `ModuleAssembly 1.0`, sprites transparentes ancorados, posições e conectores em milímetros, ordenação por profundidade e composição atômica. O fixture gaveteiro + balcão fechou 399 + 780 = 1.179 mm e obteve IoU médio de silhueta de aproximadamente 99,664% contra o ground truth.

### V7.0-I4.1 — carregamento local

Corrigiu o canvas preto ao abrir por `file://`, removeu `crossOrigin="anonymous"` de assets locais e tornou falhas de carregamento diagnosticáveis.

### V7.0-I4.2 — visibilidade por instância

Permitiu ocultar ou exibir cada instância na sessão sem alterar o `ModuleAssembly`, a negociação ou os pacotes nativos.

### V7.0-I5 — semântica e fabricação

Introduziu `ModuleManufacturing 1.0`, peças, grupos de material, configurações de ferragem, BOM individual/agregada, derivação de furos e exportação JSON/CSV. A camada fabril permanece parcial porque dimensões e ferragens não fornecidas não foram inferidas.

## Capacidades retidas na reavaliação

A mudança de escopo não deve descartar automaticamente:

- módulo como unidade encapsulada;
- fonte reproduzível e pacote compilado;
- dimensões e conectores em milímetros;
- negociação monotônica de capacidade;
- composição multimódulo;
- separação entre geometria, apresentação e dados fabris;
- diagnóstico explícito de incompletude;
- publicação estática mobile.

## Itens que permanecem reavaliáveis

- necessidade de 360° completo ou apenas faixa útil;
- prioridade de pitch;
- papel da BOM e fabricação no produto final;
- forma de autoria e importação dos módulos;
- persistência e compartilhamento de configurações;
- regras de compatibilidade, dependências e campos obrigatórios;
- nível de fidelidade visual versus custo de produção dos assets.

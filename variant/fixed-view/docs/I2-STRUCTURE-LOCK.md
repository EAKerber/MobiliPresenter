# I2 — Structure Lock

## Objetivo

Antes do render realista, a variante fixa precisa impedir que o renderer improvise a estrutura dos móveis. O I2 torna a topologia frontal de cada módulo parte do contrato e faz a interface consumir essa estrutura explicitamente.

A regra central é: **o visual pode evoluir; a identidade estrutural do módulo não pode desaparecer silenciosamente**.

## Hierarquia de evidência

1. fichas modulares mais recentes fornecidas pelo usuário;
2. composição completa fornecida pelo usuário;
3. planta e decisões explicitamente aceitas no chat;
4. referências anteriores, apenas para rastreabilidade;
5. inferência mínima quando não houver dado suficiente.

Eletrodomésticos são ilustrativos. Suas proporções podem ser inferidas pelos vãos dos móveis, mas o sistema não deve alegar marca, modelo ou dimensão exata sem fonte.

## Decisões operacionais

- parede: 3550 mm;
- profundidade operacional adotada para o protótipo: 600 mm;
- MDF estrutural: 18 mm;
- caixarias: brancas;
- frentes/acabamentos visíveis: controlados por preset quando aplicável;
- preço permanece fora do detalhamento;
- cliente pode sobrescrever a recomendação de puxador/abertura.

As fichas anteriores que mostram profundidades de 350, 400, 530 ou 550 mm continuam registradas em `referenceDimensions`. O valor de 600 mm é uma decisão explícita do usuário para o protótipo e não apaga a evidência anterior.

## Invariantes estruturais

### 01 — Aéreo da lavanderia

- 2 portas;
- 1 prateleira fixa.

### 02 — Inferior do fogão

- vão para forno embutido quando selecionado;
- quando desabilitado, a cena mostra um fogão convencional independente como fallback visual.

### 03 — Inferior da pia

- **4 gavetas + 2 portas**;
- a topologia é testada mecanicamente para impedir regressão para uma frente genérica de três painéis.

### 04 — Lateral da geladeira

- 2400 × 600 × 18 mm (A × P × E);
- suporte/acabamento relacionado ao aéreo da geladeira;
- capacidade `lighting-support`.

### 05 — Aéreo do fogão

- 2 portas;
- 1 prateleira fixa.

### 06 — Aéreo da pia

- 2 portas de abrir;
- 1 porta basculante;
- 1 nicho para micro-ondas.

### 07 — Aéreo da geladeira

- 2 portas;
- 1 prateleira fixa.

### 08 — Iluminação

- item visual/comercial próprio;
- depende do item 04 para uma composição válida.

## Regras

O motor atual preserva quatro regras iniciais:

1. iluminação sem item 04 bloqueia revisão/orçamento e oferece incluir o item 04;
2. módulo 02 ausente ativa o fallback de fogão convencional;
3. inferiores recomendam alça de dois furos;
4. superiores recomendam ponto de um furo ou abertura passante.

As recomendações permitem override do cliente. A dependência da iluminação é bloqueante.

## Referências visuais

O I2 remove do caminho ativo a ilustração sintética do empreendimento criada no I1. A área de empreendimento usa uma versão WebP comprimida da imagem originalmente fornecida pelo usuário. A composição de referência também usa uma imagem fornecida pelo usuário e é tratada apenas como guia visual.

Hashes de origem e dos derivados estão em `prototype/i2-data/visual-assets.json`.

A composição de referência não é autoridade para esconder um módulo. Quando a referência estiver obsoleta em cor/acabamento ou ambígua, os contratos de módulo e as referências individuais mais recentes prevalecem.

## Renderer

`prototype/i2/renderer.js` desenha placeholders estruturais a partir de `frontTopology`. Eles ainda não são o render realista final.

Esse desenho intermediário existe para validar:

- presença e divisão das frentes;
- gavetas, portas, nichos e aberturas;
- posições relativas;
- seleção/hit areas;
- fallbacks;
- presets de abertura.

O próximo pipeline visual poderá substituir essas superfícies por overlays/renderizações realistas sem alterar o contrato semântico.

## Gates

`tools/validate_i2.py` verifica, entre outros pontos:

- oito módulos únicos;
- envelope de 3550 mm;
- profundidade operacional de 600 mm;
- MDF 18 mm;
- 4 gavetas + 2 portas no item 03;
- nicho e basculante no item 06;
- capacidades do item 04;
- dependência 08 → 04;
- fallback do item 02;
- ausência de preço no detalhe;
- integridade SHA-256 dos assets WebP derivados das referências fornecidas.

`tests/test_i2_contracts.py` cobre as invariantes mais propensas a regressão. A workflow `.github/workflows/fixed-view-i2.yml` executa validação, testes e syntax check do JavaScript em pushes da linha I2.

## Limite deste incremento

O I2 **não tenta fabricar o render final**. A geometria de câmera e os overlays realistas ainda devem ser calibrados contra imagens e medidas melhores. A finalidade deste recorte é garantir que essa próxima etapa possa melhorar o realismo sem voltar a inventar a composição.

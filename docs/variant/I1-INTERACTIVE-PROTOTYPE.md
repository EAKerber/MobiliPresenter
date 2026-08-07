# Variante I1 — protótipo interativo de câmera fixa

**Branch:** `variant/fixed-view-i1-interactive`  
**Natureza:** incremento da linha alternativa, sem intenção de merge na `main`.

## Objetivo

Converter os contratos do I0 em uma experiência funcional verificável antes da produção dos renders definitivos.

O I1 não tenta resolver a arte final. Ele valida interação, estados, regras e distribuição da interface com uma referência visual provisória.

## Entregas

- checklist dos oito itens, com seleção visual e comercial simultânea;
- miniaturas derivadas da referência completa;
- cena fixa persistente;
- ativação e desativação pontual de módulos;
- destaque do módulo selecionado e do último ativado;
- detalhe substituindo apenas a região do catálogo;
- retorno à lista sem esconder a cena;
- duas bases alternáveis: parede neutra e contexto de referência;
- cor global aplicada às frentes, preservando a regra de caixas brancas;
- preset recomendado de abertura;
- override por módulo;
- diagnóstico da dependência de iluminação;
- transição corretiva oferecida para incluir o item 04;
- bloqueio de revisão/finalização enquanto houver regra bloqueante;
- persistência local do estado.

## Envelope e layout

A largura operacional é `3550 mm`, conforme D-014.

As áreas clicáveis e recortes em `data/i1-layout.json` são provisórios e derivados visualmente da referência. Eles servem para validar a experiência e não constituem geometria de fabricação.

## Assets

O protótipo inclui cópias WebP provisórias de:

- composição completa;
- referência do empreendimento.

O manifesto registra tamanho, SHA-256 e origem. Para contornar transporte binário sem depender de upload manual, as duas imagens são incorporadas como Base64 em `prototype/assets.js`; continuam não sendo renders finais.

## Execução local

```bash
cd variant/fixed-view
python3 tools/build_i1.py
python3 -m http.server 8080 --directory prototype
```

Abrir `http://localhost:8080`.

## Gates

```bash
python3 tools/validate_i1.py
python3 -m unittest tests/test_i1_contracts.py
python3 tests/browser_smoke_i1.py
```

O teste de navegador requer Playwright para Python e Chromium.

## Não objetivos

- render realista final;
- cotas liberadas para fabricação;
- cálculo de preço;
- integração na `main`;
- publicação no Netlify principal;
- solução definitiva para variantes de cor sem replicação.

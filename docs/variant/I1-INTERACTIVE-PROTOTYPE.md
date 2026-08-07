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

## Assets e preservação do fonte

O protótipo usa cópias WebP provisórias de:

- composição completa;
- referência do empreendimento.

As duas imagens são incorporadas como Base64 em `prototype/assets.js`; continuam não sendo renders finais.

Para preservar o incremento como uma unidade verificável sem depender de upload binário manual, os arquivos executáveis do I1 são guardados em `variant/fixed-view/i1-package/` como um ZIP fragmentado em Base64. O manifesto declara tamanho e SHA-256 de cada fragmento e do artefato integral. `materialize_i1.py` valida todos os hashes, rejeita paths ZIP inseguros e só então restaura os arquivos legíveis.

## Materialização e execução local

Na raiz do repositório:

```bash
python3 variant/fixed-view/materialize_i1.py --verify-only
python3 variant/fixed-view/materialize_i1.py
```

Depois:

```bash
cd variant/fixed-view
python3 tools/build_i1.py
python3 -m http.server 8080 --directory prototype
```

Abrir `http://localhost:8080`.

Uma segunda materialização exige `--force`; sem essa opção, o script recusa sobrescrever arquivos existentes.

## Gates

```bash
python3 tools/validate_i1.py
python3 -m unittest tests/test_i1_contracts.py
python3 tests/browser_smoke_i1.py
```

O teste de navegador requer Playwright para Python e Chromium.

## Integridade do pacote

- artefato: `mobilipresenter-fixed-view-i1-runtime.zip`;
- tamanho: `65.820 bytes`;
- SHA-256: `47a4f4cae188e778f98c58f39764606f4705300be95dca756199b333e9652e1e`;
- sete fragmentos Base64;
- extração máxima aceita pelo materializador: `5 MiB`.

## Não objetivos

- render realista final;
- cotas liberadas para fabricação;
- cálculo de preço;
- integração na `main`;
- publicação no Netlify principal;
- solução definitiva para variantes de cor sem replicação.

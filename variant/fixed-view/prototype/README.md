# Protótipo I1

Abra `index.html` por um servidor estático depois de executar:

```bash
python3 ../tools/build_i1.py
python3 -m http.server 8080
```

O protótipo usa apenas arquivos locais e não chama serviços externos. As imagens provisórias estão incorporadas em `assets.js`, permitindo execução sem pipeline binário adicional.

A composição visual é provisória. Os recortes da referência servem para validar checklist, detalhe, presets e regras; não representam os renders finais.

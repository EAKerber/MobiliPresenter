# Pacote-fonte verificável do I1

Este diretório preserva o executável e os gates da variante Fixed View I1 como um artefato determinístico fragmentado em Base64.

## Verificação

Na raiz do repositório:

```bash
python3 variant/fixed-view/materialize_i1.py --verify-only
```

Resultado esperado:

```text
Verified mobilipresenter-fixed-view-i1-runtime.zip | bytes=65820 | sha256=47a4f4cae188e778f98c58f39764606f4705300be95dca756199b333e9652e1e
```

## Materialização

```bash
python3 variant/fixed-view/materialize_i1.py
```

O materializador restaura o protótipo, os scripts de build/validação, os testes e o relatório de smoke test nos paths declarados pelo manifesto.

Ele falha antes de extrair quando encontra:

- fragmento ausente ou alterado;
- divergência de tamanho ou SHA-256;
- Base64 inválido;
- ZIP inválido;
- path absoluto ou travessia de diretório;
- barra invertida em membro do ZIP;
- link simbólico;
- expansão superior a 5 MiB;
- arquivo de destino já existente sem `--force`.

## Identidade

- artefato: `mobilipresenter-fixed-view-i1-runtime.zip`;
- tamanho: `65.820 bytes`;
- SHA-256: `47a4f4cae188e778f98c58f39764606f4705300be95dca756199b333e9652e1e`;
- Base64: `87.760 caracteres`;
- fragmentos: `7`.

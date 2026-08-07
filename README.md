# MobiliPresenter — variante Fixed View Modular Showcase

> **Branch isolada:** `variant/fixed-view-modular-showcase`  
> **Integração prevista:** nenhuma. Esta linha existe para atender um escopo alternativo sem alterar a baseline V7.0-I5 nem o preview publicado em `main`.

Esta variante explora um montador comercial e visual de ambiente em câmera fixa. O usuário ativa módulos por checklist, acompanha a composição realista continuamente, abre detalhes sem perder a cena e ajusta presets de frentes, puxadores e aparência.

## Estado

A **Variante I0** prepara o solo. Ela contém:

- escopo e decisões aceitas;
- inventário das referências disponíveis;
- identidade criptográfica das duas plantas e medições provisórias com conflitos explícitos;
- catálogo inicial dos módulos 01–08;
- contratos preliminares de montagem, presets, regras e estado de interface;
- validador e testes de consistência.

Os binários das plantas ainda não foram promovidos para esta branch; tamanho, nome e SHA-256 impedem que futuras cópias semelhantes sejam aceitas silenciosamente como equivalentes.

Ainda não há interface funcional nem render final nesta branch.

## Ordem de leitura

```text
AGENTS.md
→ docs/variant/README.md
→ docs/variant/SCOPE.md
→ docs/variant/DECISIONS.md
→ docs/variant/REFERENCE-INVENTORY.md
→ docs/variant/MEASUREMENTS.md
→ variant/fixed-view/README.md
```

## Validação local

```bash
python3 variant/fixed-view/tools/validate_i0.py
python3 -m unittest discover -s variant/fixed-view/tests -p "test_*.py"
```

A linha publicada continua documentada na branch `main`. Nada nesta variante deve ser promovido para `main` sem uma nova autorização explícita.

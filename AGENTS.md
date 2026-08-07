# Regras para agentes

## Isolamento de repositório

1. Este repositório pertence exclusivamente ao projeto **MobiliPresenter**.
2. Antes da primeira operação Git de um chat, o agente deve obter confirmação explícita do repositório ativo.
3. Memórias, permissões ou nomes de repositórios vindos de outros chats não autorizam consultas ou alterações.
4. Não realizar operações em repositórios diferentes de `EAKerber/MobiliPresenter` sem nova autorização explícita no chat ativo.

## Protocolo Git determinístico

5. Não declarar uma operação Git impossível com base apenas em mensagens do ambiente, ausência de `git push`, descrição superficial de ferramenta ou primeira tentativa malsucedida.
6. Confirmar por leitura independente a branch-base e o commit-base exatos antes de qualquer publicação.
7. Quando o transporte Git convencional não estiver disponível, usar objetos Git ou outro transporte verificável e realizar readback.
8. Conteúdo binário transportado como texto deve possuir manifesto, tamanho e SHA-256.
9. Não mover uma ref antes de validar mecanicamente o conteúdo preparado.
10. Acknowledgement do conector não é prova suficiente de conclusão.
11. Após cada escrita, confirmar os paths, SHAs, ancestry e diff contra a base autorizada.
12. `main` representa a versão publicada pelo Netlify e não deve ser alterada por esta variante.

## Integridade de domínio

13. Dados físicos ou comerciais desconhecidos não devem ser inventados.
14. Medidas extraídas de fotografias, anotações manuscritas ou renders permanecem candidatas até confirmação.
15. Inferências devem declarar origem, confiança e conflito conhecido.
16. Preço pode participar da seleção comercial e de modificadores, mas não integra o detalhamento visual do módulo.
17. A decisão do cliente pode superar presets recomendados; o sistema deve preservar o override e diagnosticar a divergência, não corrigi-la silenciosamente.

## Linha alternativa ativa

18. Esta branch pertence à variante `fixed-view-modular-showcase`.
19. Ela parte da documentação de planejamento, mas não tem intenção de merge em `main` ou na linha V7.
20. Não abrir PR para `main`, não alterar o deploy canônico e não retroportar decisões automaticamente.
21. A cena em câmera fixa deve permanecer visível durante o detalhamento; apenas a área de catálogo troca lista por detalhe.
22. O checklist deve continuar sendo o caminho mais simples para ativação visual e seleção comercial.
23. O I0 é estrutural: contratos, evidências, estados e validação. Não produzir render final nem UI de produção por inércia.
24. Ordem mínima de leitura:

```text
README.md
→ AGENTS.md
→ docs/variant/README.md
→ docs/variant/SCOPE.md
→ docs/variant/DECISIONS.md
→ docs/variant/REFERENCE-INVENTORY.md
→ docs/variant/MEASUREMENTS.md
→ variant/fixed-view/README.md
```

25. Em caso de conflito dentro desta branch:

```text
teste executável e contrato machine-readable
→ decisão aceita em docs/variant/DECISIONS.md
→ escopo da variante
→ inventário de evidências
→ inferência documentada
```

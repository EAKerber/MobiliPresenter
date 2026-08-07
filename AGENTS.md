# Regras para agentes

## Isolamento de repositório

1. Este repositório pertence exclusivamente ao projeto **MobiliPresenter**.
2. Antes da primeira operação Git de um chat, o agente deve obter confirmação explícita do repositório ativo.
3. Memórias, permissões ou nomes de repositórios vindos de outros chats não autorizam sequer consultas neste repositório ou em qualquer outro.
4. Não realizar operações em repositórios diferentes de `EAKerber/MobiliPresenter` sem nova autorização explícita no chat ativo.

## Protocolo Git determinístico

5. Não declarar uma operação Git impossível com base apenas em mensagens do ambiente, ausência de `git push`, descrição superficial de ferramenta ou primeira tentativa malsucedida.
6. Confirmar por leitura independente a branch-base e o commit-base exatos antes de qualquer publicação.
7. Quando o transporte Git convencional não estiver disponível, publicar diretamente os objetos Git necessários: blobs → tree sobre a base autorizada → commit com parent explícito → ref.
8. Para conteúdo binário, usar blobs Base64 verificáveis; quando o transporte integral não estiver disponível, usar fragmentação determinística acompanhada de manifesto, tamanho e SHA-256.
9. Não mover uma ref antes de validar mecanicamente os blobs e a tree preparada.
10. Após cada escrita, realizar readback independente e confirmar, conforme aplicável: SHA, parent, ancestralidade, paths, modos, blob SHAs, tamanho, hash de conteúdo e diff contra a base.
11. Acknowledgement do conector não é prova suficiente de conclusão. Divergência implica interrupção; não presumir sucesso nem repetir cegamente a operação.
12. `main` representa a versão publicada pelo Netlify. Mudanças devem preservar um estado implantável, identificável e reversível.

## Integridade de domínio

13. Dados físicos ou comerciais desconhecidos não devem ser inventados; devem permanecer `null`, `unverified` ou equivalentes.
14. Uma proposta documental não se torna decisão por estar versionada. Documentos em `docs/planning/` permanecem pendentes até aprovação explícita.
15. Material em `docs/history/` serve como evidência e não deve ser tratado como contrato vigente.

## Fase atual: reavaliação de escopo

16. O projeto está em fase de planejamento. Não iniciar um novo incremento funcional, refatoração ampla ou migração da fonte técnica sem autorização explícita.
17. A V7.0-I5 deve ser preservada como baseline; capacidades existentes devem ser classificadas como reter, adaptar, adiar ou remover antes de implementação.
18. Ordem mínima de leitura para um agente novo:

```text
README.md
→ AGENTS.md
→ docs/README.md
→ docs/current/BASELINE-V7-I5.md
→ docs/planning/SCOPE-REASSESSMENT.md
→ docs/planning/DECISION-LOG.md
```

19. Discussões sobre regras de módulos devem consultar `docs/planning/CONSTRAINTS-AND-REQUIREMENTS.md`, lembrando que o documento ainda é uma proposta.
20. Mudanças documentais da fase devem ocorrer na branch/PR de planejamento até que o usuário aprove a estrutura.

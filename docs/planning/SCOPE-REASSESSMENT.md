# Reavaliação de escopo e priorização

**Status:** aberto para discussão.  
**Fase:** planejamento; implementação funcional suspensa até aprovação de um novo recorte.

## Motivo

O projeto mudou de escopo e prioridade depois da V7.0-I5. A estrutura existente aparenta conter capacidades reaproveitáveis, mas foi construída sob objetivos anteriores. Continuar por inércia criaria o risco de otimizar uma arquitetura correta para o produto errado.

## Objetivo desta fase

Produzir uma definição explícita de:

1. problema e usuário-alvo;
2. fluxo principal que o produto deve resolver;
3. unidade de composição e de configuração;
4. papel do 3D/raster na experiência;
5. profundidade necessária da camada semântica e fabril;
6. regras de compatibilidade e dependência;
7. fronteiras de autoria, operação e publicação;
8. critérios de sucesso do próximo MVP.

## Princípios temporários

- não implementar novas funções antes de fechar o problema e o fluxo principal;
- preservar a V7.0-I5 como baseline verificável;
- não promover todos os ZIPs para a raiz sem classificar fonte, derivado e fixture;
- tratar capacidades existentes como ativos, não como requisitos automáticos;
- evitar acoplamento por IDs quando uma capacidade declarativa puder representar a necessidade;
- manter dados desconhecidos explícitos;
- preferir contratos pequenos, versionados e testáveis;
- separar decisões de produto, arquitetura, implementação e conteúdo.

## Trilhas de discussão

### A. Produto e uso

- Quem monta ou apresenta a configuração?
- Quem apenas visualiza?
- O resultado é uma apresentação, proposta, catálogo, orçamento, especificação ou combinação desses?
- O fluxo é interno, compartilhado com cliente ou ambos?
- Qual decisão o usuário precisa tomar ao final?

### B. Módulos e composição

- O que constitui um módulo no novo escopo?
- Um módulo é um asset visual, um produto, uma unidade fabricável ou os três?
- A composição é livre, guiada por conectores ou baseada em templates?
- Posição precisa em milímetros continua obrigatória no caminho principal?
- Quais transformações o usuário pode realizar?

### C. Configuração e regras

- Quais propriedades pertencem ao módulo, à instância e à montagem?
- Quais incompatibilidades bloqueiam e quais apenas alertam?
- Como representar dependências estruturais, elétricas, funcionais e comerciais?
- O sistema deve sugerir correções ou apenas diagnosticar?
- Campos obrigatórios surgem por módulo, feature, montagem ou etapa?

### D. Representação visual

- A faixa atual de yaw é suficiente?
- Pitch agrega valor ao fluxo prioritário?
- Quais variações exigem novos frames e quais podem ser compostas?
- Iluminação precisa ser coerente entre módulos ou pode ser aproximada?
- Qual nível de fidelidade é necessário em mobile?

### E. Semântica e fabricação

- BOM é saída central, complementar ou futura?
- Lista de corte, furos e ferragens pertencem ao MVP?
- Dados fabris vêm do Promob, de uma planilha, de autoria manual ou de integração externa?
- Qual nível de verificação é necessário antes de chamar uma saída de fabricável?

### F. Persistência e entrega

- Uma configuração precisa ser salva, compartilhada ou versionada?
- O sistema continua totalmente estático?
- Existe necessidade de conta, backend ou colaboração?
- Netlify permanece apenas demo ou torna-se canal formal?

## Entregáveis da fase

1. declaração do novo escopo;
2. mapa de atores e fluxos;
3. inventário de capacidades: reter, adaptar, adiar ou remover;
4. modelo de domínio preliminar;
5. contratos necessários e limites entre eles;
6. arquitetura documental aprovada;
7. backlog priorizado por resultados, não por componentes;
8. primeiro recorte implementável com gates mensuráveis.

## Critério de encerramento

A fase termina quando for possível responder sem ambiguidade:

> Qual é o menor fluxo completo que demonstra o valor do novo escopo, quais capacidades atuais ele reutiliza e quais riscos precisam ser eliminados antes da implementação?

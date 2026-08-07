# Escopo — Fixed View Modular Showcase

**Status:** aceito para a Variante I0.

## Problema

Apresentar rapidamente um conjunto de marcenaria pensado para um empreendimento específico, permitindo que a pessoa compreenda cada módulo, componha o conjunto comercialmente e visualize o resultado realista sem a complexidade de navegação 3D.

## Fluxo de valor

1. a cena fixa mostra o ambiente-base;
2. a área de catálogo lista módulos com checkbox, nome e miniatura realista;
3. o checkbox controla simultaneamente presença visual e seleção comercial;
4. o módulo mais recentemente ativado recebe destaque discreto;
5. clicar no nome ou no módulo da cena abre seu detalhamento;
6. a cena continua visível; somente a área de catálogo troca lista por detalhe;
7. presets e overrides alteram frentes, puxadores e aparência;
8. regras produzem recomendações, avisos, correções oferecidas ou bloqueios;
9. todos os módulos ativos reconstituem a composição completa de referência.

## Regiões estáveis da interface

- **catálogo/detalhe:** lista rápida ou detalhe do módulo, com botão voltar;
- **cena:** ambiente e módulos ativos, sempre visível;
- **configuração:** presets editáveis, cores, puxadores e modificadores;
- **empreendimento:** imagem e contexto do condomínio.

As cores do rascunho original servem apenas para identificar regiões, não são tokens visuais obrigatórios.

## Regras de aparência aceitas

- caixas/carcaças permanecem brancas;
- cores afetam somente as frentes;
- presets são editáveis;
- recomendação inicial:
  - inferiores: alças de dois furos;
  - superiores: puxador ponto de um furo ou abertura passante;
- a escolha final do cliente prevalece;
- divergências do preset recomendado podem gerar aviso, nunca alteração silenciosa.

## Natureza comercial

Marcar um módulo significa incluí-lo visualmente **e** comercialmente. Modificadores de valor podem existir no motor de configuração, mas preço não aparece no detalhamento do módulo.

## Realismo e geometria

- câmera fixa;
- render realista é prioridade;
- a primeira geometria pode ser provisória e baseada nas referências;
- cotas exatas serão incorporadas quando disponíveis;
- nada inferido deve ser rotulado como medida confirmada.

## Fora do I0

- UI funcional;
- render final;
- cálculo de preço;
- persistência de propostas;
- geração fabril;
- resolução definitiva das cotas conflitantes;
- estratégia final para evitar replicação integral de assets por cor.

# Fluxos e estados de interface

## Máquina de estados principal

```text
COMPOSITION_LIST
  catálogo: checklist + miniaturas
  cena: composição persistente
  configuração: presets
  empreendimento: contexto

      nome do módulo ou clique na cena

MODULE_DETAIL
  catálogo: detalhe + voltar
  cena: composição persistente + módulo selecionado
  configuração: presets/contexto do módulo
  empreendimento: contexto

      voltar

COMPOSITION_LIST
```

A transição lista ↔ detalhe pode usar fade restrito à região de catálogo. A cena não desaparece.

## Interações

### Checkbox

- alterna `enabled`;
- alterna inclusão comercial;
- revalida regras;
- atualiza a cena;
- define `lastEnabledModuleId` quando ativado;
- não abre detalhe por consequência.

### Nome ou miniatura

- define `selectedModuleId`;
- abre detalhe;
- preserva os checks atuais.

### Módulo na cena

- usa hit area/máscara;
- define o mesmo `selectedModuleId`;
- abre o mesmo detalhe;
- não altera automaticamente inclusão comercial.

### Voltar

- fecha detalhe;
- preserva seleção, composição e presets;
- devolve o catálogo à posição anterior de rolagem.

## Estados visuais de item

- disponível;
- ativo;
- selecionado;
- último ativado;
- com aviso;
- incompleto;
- bloqueado;
- indisponível por regra.

Os estados podem coexistir; prioridade visual deve impedir que um aviso apague a informação de seleção.

## Inicialização

O contrato mantém duas políticas:

- `empty`: ambiente-base sem módulos;
- `preset`: conjunto inicial pré-selecionado.

A escolha final permanece aberta. Testes futuros devem comparar compreensão, velocidade e sensação de controle.

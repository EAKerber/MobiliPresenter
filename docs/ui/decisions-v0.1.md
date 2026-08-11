# MobiliPresenter — UI/UX Decision Log 0.1

Status: **ativo**  
Branch de autoria original: `ui/style-guide-v0.1`  
Baseline inicial: `integration/viewer-parallel-v0.1` @ `277b0fc088f5e32de236782b293f39feea6e163e`

Este arquivo registra decisões de produto/UX que orientam a implementação visual. Ele evita que decisões já tomadas voltem a ser tratadas como questões em aberto por novos agentes.

Decisões de domínio, geometria, arquitetura de renderer ou contrato continuam pertencendo aos ADRs e contratos próprios.

## UI-D001 — Render permanece dominante

**Status:** accepted

**Decisão:** no estado sem detalhe aberto, o render ocupa toda a área disponível à direita da superfície compacta de navegação/configuração.

**Racional:** o produto é uma apresentação contextual do mobiliário; controles devem servir ao render e não competir com ele.

---

## UI-D002 — Detalhe abre abaixo do render

**Status:** superseded por `UI-D024`

**Decisão original:** selecionar um módulo revela a ficha técnica na parte inferior da coluna direita e reduz verticalmente o render.

**Motivo da substituição:** seleção e expansão da ficha agora são estados distintos. Selecionar ainda pode abrir a ficha como comportamento inicial, mas recolhê-la não deseleciona o módulo.

---

## UI-D003 — Abertura da ficha não move a câmera

**Status:** accepted

**Decisão:** abertura/fechamento da ficha é uma transição de layout da UI. Não altera câmera, pose ou enquadramento sem uma decisão de produto separada.

**Racional:** a câmera fixa é invariante e a inspeção técnica não deve parecer uma navegação 3D.

---

## UI-D004 — Checkbox e seleção são ações distintas

**Status:** accepted

**Decisão:** checkbox controla visibilidade; clicar na miniatura/nome/linha seleciona o módulo para detalhe.

**Racional:** ocultar e inspecionar são intenções ortogonais.

**Gate:** evento do checkbox não pode propagar para seleção da linha.

---

## UI-D005 — Sidebar possui três páginas

**Status:** superseded por `UI-D022`

**Decisão original:** `Módulos`, `Cores` e `Acessórios` são páginas irmãs de uma sidebar persistente com navegação no rodapé.

**Motivo da substituição:** as três páginas continuam irmãs, mas passam a ser acessadas por rail compacto + drawer recolhível para devolver largura ao render e à apresentação técnica.

---

## UI-D006 — Ficha é construída com dados do TPC

**Status:** accepted

**Decisão:** a UI consome `selectedTechnicalPresentation` e `selectedTechnicalViewAssets` do `ViewerUiContract`.

**Racional:** a UI deve compor e hierarquizar, não redescobrir fatos técnicos.

**Não fazer:** recalcular cotas, inferir divisões por pixels, reconstruir vistas técnicas com heurísticas de layout.

---

## UI-D007 — Referências são linguagem editorial, não template rígido

**Status:** accepted

**Decisão:** as folhas técnicas comerciais fornecidas pelo usuário orientam hierarquia, densidade, cor, relação imagem/texto e composição de blocos. Elas não devem virar uma imagem estática ou um layout A4 literal dentro do viewer.

**Racional:** preservar a qualidade editorial sem perder responsividade, acessibilidade e interatividade.

---

## UI-D008 — Paleta neutra quente é baseline

**Status:** accepted

**Decisão:** superfícies usam off-white/ivory, taupes e texto carvão. Acento de interação inicial é dourado/latão discreto.

**Racional:** aproxima a linguagem das referências e reduz competição com materiais do render.

**Nota:** o acento de UI não define a cor do highlight 3D.

---

## UI-D009 — Vermelho não é cor decorativa padrão

**Status:** accepted

**Decisão:** vermelho é reservado a erro, aviso/risco real ou decisão futura explícita de highlight no render.

**Racional:** nas referências, vermelho marca o módulo em uma arte explicativa; reproduzi-lo como acento geral confundiria seleção com semântica de erro e criaria competição visual.

---

## UI-D010 — Tipografia tem duas funções

**Status:** accepted

**Decisão:** corpo/interface usa sans legível baseada em Inter/system; títulos editoriais podem usar uma família condensada empacotada localmente.

**Racional:** as referências dependem de contraste entre display condensado e texto técnico limpo.

**Restrição:** nenhuma fonte externa por CDN é dependência implícita do runtime.

---

## UI-D011 — Vistas técnicas são dominantes dentro da ficha

**Status:** accepted

**Decisão:** após identidade/medidas, as vistas técnicas ocupam a maior parcela visual da ficha.

**Racional:** elas comunicam geometria e composição mais rapidamente que longos blocos de texto.

**Refino v0.2:** priorizar uma vista dominante com seletor compacto das demais antes de recorrer a várias miniaturas simultâneas ou carrossel com scroll.

---

## UI-D012 — Blocos técnicos aparecem somente quando há conteúdo

**Status:** superseded por `UI-D021`

**Decisão original:** blocos técnicos sem dados eram omitidos para evitar caixas vazias.

**Motivo da substituição:** o usuário decidiu que lacunas relevantes devem preservar o espaço editorial por meio de placeholders explícitos, sem inventar conteúdo.

---

## UI-D013 — Proveniência é secundária, mas preservada

**Status:** accepted

**Decisão:** a UI pode ocultar proveniência detalhada por padrão, desde que não descarte a informação do pacote e possa expô-la quando necessário.

**Racional:** proveniência é essencial à confiabilidade, mas não deve dominar a experiência comercial principal.

---

## UI-D014 — Capacidade não ligada não é simulada

**Status:** accepted

**Decisão:** controles `declared-not-bound` podem ser omitidos ou mostrados como indisponíveis; não recebem estado paralelo local.

**Racional:** preservar Viewer Runtime como autoridade de estado.

---

## UI-D015 — A UI técnica VRC-02 é baseline funcional, não design final

**Status:** accepted

**Decisão:** preservar lifecycle, acessibilidade básica, montagem e integração já validados; substituir progressivamente organização e linguagem visual.

**Racional:** a UI técnica teve gate humano positivo como prova funcional, mas a própria PR registra que não é a linguagem final do produto.

---

## UI-D016 — Responsividade reduz colunas antes de reduzir legibilidade

**Status:** accepted

**Decisão:** em viewports menores, cards e vistas passam de múltiplas colunas para uma faixa/coluna antes de diminuir tipografia ou touch targets.

**Racional:** preservar leitura técnica e interação touch.

---

## UI-D017 — Motion explica estrutura

**Status:** accepted

**Decisão:** animações ficam concentradas em abertura/fechamento de ficha, drawer lateral e feedback de controles, com duração curta e `prefers-reduced-motion`.

**Racional:** motion deve tornar a mudança de layout compreensível, não criar personalidade ornamental que dispute atenção com o render.

---

## UI-D018 — Seleção visual dentro do render permanece fora do escopo atual

**Status:** deferred

**Decisão:** não consolidar neste incremento a linguagem final de highlight/outline/fill do módulo selecionado no render.

**Racional:** o usuário pediu que a frente atual foque shell, paginação lateral e ficha técnica; a infraestrutura de interação pode evoluir separadamente.

---

## UI-D019 — Estado oculto e estado selecionado são ortogonais

**Status:** accepted

**Decisão:** um módulo oculto pode continuar sendo selecionável pela lista quando o contrato permitir. A ficha deve indicar o estado sem impedir inspeção.

**Racional:** ocultar da composição não significa apagar o item da configuração.

---

## UI-D020 — A implementação da UI deve permanecer path-isolated

**Status:** accepted

**Decisão:** trabalho normal desta frente modifica `viewer-next/src/ui/**`, assets visuais exclusivos e testes de UI. Mudanças em `src/api/**`, runtime, renderer, presentation, fixtures ou Scene Core exigem transição coordenada.

**Racional:** cumprir o contrato de desenvolvimento paralelo UI × Engine e reduzir conflitos.

---

## UI-D021 — Ausência relevante usa placeholder explícito

**Status:** accepted

**Decisão:** quando uma informação esperada pela composição comercial estiver ausente, a UI preserva o espaço com placeholder neutro e claramente pendente.

**Exemplos:** `Descrição comercial a definir`, `Artes técnicas a definir`, `Componentes a definir`, `Acabamento a definir`.

**Racional:** manter consistência editorial sem inventar fatos e sem fazer layouts incompletos colapsarem de forma imprevisível.

**Não fazer:** preencher lacuna com inferência visual, texto comercial fabricado ou valor técnico aproximado.

---

## UI-D022 — Seletores usam rail compacto + drawer recolhível

**Status:** accepted

**Decisão:** `Módulos`, `Cores` e `Acessórios` permanecem destinos irmãos, mas a superfície persistente é um rail estreito. O conteúdo de configuração abre em drawer e pode ser recolhido.

**Racional:** devolver largura permanente ao render e às artes técnicas, reduzindo a aparência de painel administrativo.

**Comportamento preferido:** selecionar um módulo recolhe o drawer automaticamente e deixa o rail acessível.

---

## UI-D023 — Scroll é último recurso de layout

**Status:** accepted

**Decisão:** antes de adicionar overflow rolável, tentar nesta ordem: `reflow → disclosure → seleção/paginação → scroll`.

**Racional:** scrolls aninhados reduzem compreensão espacial, especialmente em mobile, e desperdiçam área que pode ser recuperada por hierarquia melhor.

**Gate:** evitar scroll dentro de cards; ficha técnica possui no máximo uma superfície vertical principal de scroll; listas laterais podem rolar quando o número de opções realmente exceder o drawer.

**Estilo:** quando necessário, scrollbar fina, discreta, com contraste maior em hover e sem track ornamental.

---

## UI-D024 — Seleção e expansão da ficha são estados independentes

**Status:** accepted

**Decisão:** um módulo pode permanecer selecionado com a ficha recolhida. Fechar a ficha não chama `selectModule(null)`.

**Racional:** o módulo selecionado continua sendo contexto para Cores/Acessórios e não deve ser perdido só porque o usuário quer recuperar espaço do render.

**Comportamento:** nova seleção pode abrir a ficha inicialmente; depois, `detailExpanded` é controlado localmente pela UI sem duplicar autoridade de domínio.

---

## UI-D025 — Ficha assume intenção promocional sem inventar marketing

**Status:** accepted

**Decisão:** a ficha deve inspirar visualização e compra por composição, hierarquia, escala das artes e destaque de materiais/ferragens. Texto promocional só aparece quando houver fonte autoritativa; caso contrário, usa placeholder.

**Racional:** o produto não é apenas um inspetor técnico. As referências fornecidas são materiais comerciais e a UI deve refletir essa intenção, mantendo rigor factual.

**Consequência:** uma vista técnica dominante e uma composição editorial têm prioridade sobre grids densos de propriedades e controles permanentemente visíveis.

---

## Como alterar uma decisão

Uma decisão `accepted` só deve mudar quando:

1. houver novo input explícito do usuário, ou
2. um conflito mensurável de acessibilidade/usabilidade for demonstrado, ou
3. o contrato/arquitetura tornar a decisão inviável.

A mudança deve:

- manter o ID original;
- alterar status para `superseded` quando substituída;
- referenciar a nova decisão;
- registrar o motivo e a evidência.

Decisões visuais pequenas que não alteram comportamento, hierarquia ou contrato podem permanecer apenas no style guide/tokens, sem criar um novo ID.

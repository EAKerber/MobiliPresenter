import type {
  FrontPresetId,
  LightingPresetId,
  ModuleAlias,
  StonePresetId,
  TechnicalDiagramAsset,
  TechnicalPresentationPackage,
  ViewerUiApi
} from "../api/ui-contract.js";
import "./runtime-controls.css";

export interface RuntimeControlsUi {
  refresh(): void;
  dispose(): void;
}

type SidebarPage = "modules" | "colors" | "accessories";

type StatusElements = {
  readonly root: HTMLElement;
  readonly message: HTMLElement;
};

const SIDEBAR_PAGES: readonly { readonly id: SidebarPage; readonly label: string; readonly shortLabel: string }[] = [
  { id: "modules", label: "Módulos", shortLabel: "M" },
  { id: "colors", label: "Cores", shortLabel: "C" },
  { id: "accessories", label: "Acessórios", shortLabel: "A" }
];

function button(label: string, className: string): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.textContent = label;
  return element;
}

function paragraph(text: string, className: string): HTMLParagraphElement {
  const element = document.createElement("p");
  element.className = className;
  element.textContent = text;
  return element;
}

function formatTechnicalNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
}

function formatDimensions(pkg: TechnicalPresentationPackage): string | null {
  const dimensions = pkg.dimensions;
  if (!dimensions) return null;
  const values = dimensions.order.map(axis => formatTechnicalNumber(dimensions.primaryMm[axis]));
  return `${values.join(" × ")} mm`;
}

function currentFinishLabel(pkg: TechnicalPresentationPackage): string | null {
  for (const policy of pkg.finishes) {
    if (!policy.currentOptionId) continue;
    const option = policy.options.find(candidate => candidate.id === policy.currentOptionId);
    if (option) return option.label;
  }
  return null;
}

function humanModuleName(alias: ModuleAlias, pkg: TechnicalPresentationPackage | null): string {
  if (pkg && pkg.identity.alias === alias) return pkg.identity.title;
  return `Módulo ${alias}`;
}

function createStatus(): StatusElements {
  const root = document.createElement("div");
  root.className = "viewer-shell__status";
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");
  root.dataset.error = "false";
  const message = document.createElement("span");
  message.textContent = "Configuração sincronizada";
  root.append(message);
  return { root, message };
}

function createPlaceholder(title: string, text: string, className = "viewer-placeholder"): HTMLElement {
  const root = document.createElement("div");
  root.className = className;
  root.dataset.placeholder = "true";
  const heading = document.createElement("strong");
  heading.textContent = title;
  root.append(heading, paragraph(text, "viewer-placeholder__text"));
  return root;
}

function createDisclosure<T>(
  items: readonly T[],
  visibleCount: number,
  renderItem: (item: T) => HTMLElement,
  label: string
): readonly HTMLElement[] {
  const visible = items.slice(0, visibleCount).map(renderItem);
  const hidden = items.slice(visibleCount);
  if (hidden.length === 0) return visible;

  const details = document.createElement("details");
  details.className = "viewer-disclosure";
  const summary = document.createElement("summary");
  summary.textContent = `${label} +${hidden.length}`;
  const content = document.createElement("div");
  content.className = "viewer-disclosure__content";
  content.append(...hidden.map(renderItem));
  details.append(summary, content);
  return [...visible, details];
}

function createTechnicalFigure(
  pkg: TechnicalPresentationPackage,
  asset: TechnicalDiagramAsset,
  hero = false
): HTMLElement | null {
  if (asset.status !== "ready" || asset.svg === null) return null;
  const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
  if (!request) return null;

  const figure = document.createElement("figure");
  figure.className = hero ? "viewer-technical-view viewer-technical-view--hero" : "viewer-technical-view";
  figure.dataset.technicalView = asset.viewId;

  const media = document.createElement("div");
  media.className = "viewer-technical-view__media";
  media.innerHTML = asset.svg;

  const caption = document.createElement("figcaption");
  caption.textContent = request.label;
  figure.append(media, caption);
  return figure;
}

function createTechnicalGallery(
  pkg: TechnicalPresentationPackage | null,
  assets: readonly TechnicalDiagramAsset[],
  activeViewId: string | null,
  onSelect: (viewId: string) => void
): HTMLElement {
  const section = document.createElement("section");
  section.className = "viewer-technical-gallery";
  section.dataset.technicalGallery = "hero";

  const heading = document.createElement("div");
  heading.className = "viewer-technical-gallery__heading";
  const eyebrow = paragraph("DESENHO TÉCNICO", "viewer-technical-gallery__eyebrow");
  const title = document.createElement("h3");
  title.textContent = "Vistas do módulo";
  heading.append(eyebrow, title);
  section.append(heading);

  if (!pkg) {
    section.append(createPlaceholder(
      "Artes técnicas a definir",
      "As vistas dimensionais e internas serão exibidas aqui quando houver informação técnica publicada para este módulo.",
      "viewer-placeholder viewer-placeholder--technical"
    ));
    return section;
  }

  const ready = assets.filter(asset => asset.status === "ready" && asset.svg !== null);
  if (ready.length === 0) {
    section.append(createPlaceholder(
      "Artes técnicas a definir",
      "Nenhuma vista técnica renderizável foi publicada para este módulo.",
      "viewer-placeholder viewer-placeholder--technical"
    ));
    return section;
  }

  const active = ready.find(asset => asset.viewId === activeViewId) ?? ready[0]!;
  const hero = createTechnicalFigure(pkg, active, true);
  if (hero) section.append(hero);

  const selector = document.createElement("div");
  selector.className = "viewer-technical-gallery__selector";
  selector.setAttribute("aria-label", "Selecionar vista técnica");
  for (const asset of ready) {
    const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
    if (!request) continue;
    const item = button(request.label, "viewer-technical-gallery__option");
    item.dataset.technicalViewOption = asset.viewId;
    item.setAttribute("aria-pressed", asset.viewId === active.viewId ? "true" : "false");
    item.addEventListener("click", () => onSelect(asset.viewId));
    selector.append(item);
  }
  section.append(selector);

  const unavailable = assets.filter(asset => asset.status !== "ready" || asset.svg === null).length;
  if (unavailable > 0) {
    section.append(createPlaceholder(
      "Vista adicional pendente",
      `${unavailable} ${unavailable === 1 ? "vista depende" : "vistas dependem"} de informação externa ainda não disponível.`,
      "viewer-placeholder viewer-placeholder--inline"
    ));
  }
  return section;
}

function createSpecificationsCard(pkg: TechnicalPresentationPackage | null): HTMLElement {
  const section = document.createElement("section");
  section.className = "viewer-technical-card viewer-technical-card--wide";
  const heading = document.createElement("h3");
  heading.textContent = "Destaques técnicos";
  section.append(heading);

  const facts = pkg?.specifications.filter(fact => fact.category !== "function") ?? [];
  if (facts.length === 0) {
    section.append(createPlaceholder("Especificações a definir", "Nenhuma especificação adicional foi publicada para este módulo."));
    return section;
  }

  const list = document.createElement("ul");
  list.className = "viewer-technical-card__list";
  const renderItem = (fact: (typeof facts)[number]): HTMLElement => {
    const item = document.createElement("li");
    item.textContent = fact.text;
    return item;
  };
  list.append(...createDisclosure(facts, 4, renderItem, "Ver mais"));
  section.append(list);
  return section;
}

function createComponentsCard(pkg: TechnicalPresentationPackage | null): HTMLElement {
  const section = document.createElement("section");
  section.className = "viewer-technical-card";
  const heading = document.createElement("h3");
  heading.textContent = "Ferragens e componentes";
  section.append(heading);

  const components = pkg?.components ?? [];
  if (components.length === 0) {
    section.append(createPlaceholder("Componentes a definir", "Corrediças, dobradiças e demais componentes serão exibidos aqui quando informados."));
    return section;
  }

  const list = document.createElement("div");
  list.className = "viewer-technical-card__stack";
  const renderItem = (component: (typeof components)[number]): HTMLElement => {
    const item = document.createElement("div");
    item.className = "viewer-technical-card__stack-item";
    const name = document.createElement("strong");
    name.textContent = component.label;
    item.append(name);
    const detailParts: string[] = [];
    if (component.specification) detailParts.push(component.specification);
    if (component.quantity !== undefined) {
      detailParts.push(`${formatTechnicalNumber(component.quantity)}${component.unit ? ` ${component.unit}` : ""}`);
    }
    const detail = document.createElement("span");
    detail.textContent = detailParts.length > 0 ? detailParts.join(" · ") : "Detalhe técnico a definir";
    if (detailParts.length === 0) detail.dataset.placeholder = "true";
    item.append(detail);
    return item;
  };
  list.append(...createDisclosure(components, 3, renderItem, "Mais componentes"));
  section.append(list);
  return section;
}

function createFinishesCard(pkg: TechnicalPresentationPackage | null): HTMLElement {
  const section = document.createElement("section");
  section.className = "viewer-technical-card";
  const heading = document.createElement("h3");
  heading.textContent = "Materiais e acabamentos";
  section.append(heading);

  const finishes = pkg?.finishes ?? [];
  if (finishes.length === 0) {
    section.append(createPlaceholder("Acabamento a definir", "O acabamento comercial ainda não foi publicado para este módulo."));
    return section;
  }

  const list = document.createElement("div");
  list.className = "viewer-technical-card__stack";
  for (const finish of finishes) {
    const item = document.createElement("div");
    item.className = "viewer-technical-card__stack-item";
    const label = document.createElement("strong");
    label.textContent = finish.label;
    item.append(label);
    const current = finish.currentOptionId
      ? finish.options.find(candidate => candidate.id === finish.currentOptionId)
      : null;
    const value = document.createElement("span");
    value.textContent = current?.label ?? "Acabamento a definir";
    if (!current) value.dataset.placeholder = "true";
    item.append(value);
    list.append(item);
  }
  section.append(list);
  return section;
}

function createNoticesCard(pkg: TechnicalPresentationPackage | null): HTMLElement {
  const section = document.createElement("section");
  section.className = "viewer-technical-card viewer-technical-card--notice";
  const heading = document.createElement("h3");
  heading.textContent = "Instalação e observações";
  section.append(heading);

  if (!pkg) {
    section.append(createPlaceholder("Informações a definir", "Dependências e observações de instalação serão apresentadas aqui."));
    return section;
  }

  const unavailableDependencies = pkg.dependencies.filter(dependency => !dependency.effectiveVisible);
  if (pkg.notices.length === 0 && unavailableDependencies.length === 0) {
    section.append(createPlaceholder("Sem observações publicadas", "Não há informação adicional de instalação cadastrada para este módulo."));
    return section;
  }

  const list = document.createElement("div");
  list.className = "viewer-technical-card__notices";
  for (const notice of pkg.notices) {
    const item = document.createElement("div");
    item.className = "viewer-notice";
    item.dataset.severity = notice.severity;
    if (notice.title) {
      const title = document.createElement("strong");
      title.textContent = notice.title;
      item.append(title);
    }
    item.append(paragraph(notice.text, "viewer-notice__text"));
    list.append(item);
  }
  for (const dependency of unavailableDependencies) {
    const item = document.createElement("div");
    item.className = "viewer-notice";
    item.dataset.severity = "important";
    const title = document.createElement("strong");
    title.textContent = "Dependência";
    item.append(title, paragraph(`${dependency.label} não está disponível na composição atual.`, "viewer-notice__text"));
    list.append(item);
  }
  section.append(list);
  return section;
}

function renderTechnicalDetail(
  root: HTMLElement,
  snapshot: ReturnType<ViewerUiApi["getSnapshot"]>,
  expanded: boolean,
  activeViewId: string | null,
  onClose: () => void,
  onSelectView: (viewId: string) => void
): void {
  root.replaceChildren();
  const alias = snapshot.selectedModuleAlias;
  if (!alias || !expanded) {
    root.hidden = true;
    return;
  }

  const pkg = snapshot.selectedTechnicalPresentation;
  root.hidden = false;
  root.dataset.moduleAlias = alias;
  root.dataset.detailExpanded = "true";

  const header = document.createElement("header");
  header.className = "viewer-technical-detail__header";

  const headingWrap = document.createElement("div");
  headingWrap.className = "viewer-technical-detail__heading";
  headingWrap.append(paragraph(`MÓDULO ${alias}`, "viewer-technical-detail__eyebrow"));

  const title = document.createElement("h2");
  title.textContent = pkg?.identity.title ?? `Módulo ${alias}`;
  headingWrap.append(title);

  const summaryFact = pkg?.specifications.find(fact => fact.category === "function") ?? null;
  if (summaryFact) {
    headingWrap.append(paragraph(summaryFact.text, "viewer-technical-detail__summary"));
  } else {
    headingWrap.append(createPlaceholder(
      "Descrição comercial a definir",
      "O resumo promocional será exibido aqui quando houver texto autoritativo disponível.",
      "viewer-placeholder viewer-placeholder--summary"
    ));
  }

  const meta = document.createElement("div");
  meta.className = "viewer-technical-detail__meta";
  const dimensions = pkg ? formatDimensions(pkg) : null;
  const dimensionsElement = document.createElement("span");
  dimensionsElement.className = "viewer-technical-detail__dimensions";
  dimensionsElement.textContent = dimensions ?? "Dimensões a definir";
  if (!dimensions) dimensionsElement.dataset.placeholder = "true";
  meta.append(dimensionsElement);

  const finishLabel = pkg ? currentFinishLabel(pkg) : null;
  const finish = document.createElement("span");
  finish.className = "viewer-technical-detail__finish";
  finish.textContent = finishLabel ?? "Acabamento a definir";
  if (!finishLabel) finish.dataset.placeholder = "true";
  meta.append(finish);
  headingWrap.append(meta);

  const close = button("×", "viewer-icon-button viewer-technical-detail__close");
  close.setAttribute("aria-label", `Recolher detalhes do módulo ${alias}`);
  close.addEventListener("click", onClose);
  header.append(headingWrap, close);

  const body = document.createElement("div");
  body.className = "viewer-technical-detail__body viewer-scroll-surface";

  const showcase = document.createElement("div");
  showcase.className = "viewer-technical-detail__showcase";
  showcase.append(createTechnicalGallery(pkg, snapshot.selectedTechnicalViewAssets, activeViewId, onSelectView));

  const information = document.createElement("aside");
  information.className = "viewer-technical-detail__information";
  information.append(
    createSpecificationsCard(pkg),
    createComponentsCard(pkg),
    createFinishesCard(pkg),
    createNoticesCard(pkg)
  );

  body.append(showcase, information);
  root.append(header, body);
}

export function mountRuntimeControls(host: HTMLElement, api: ViewerUiApi): RuntimeControlsUi {
  const catalog = api.getCatalog();
  const initialSnapshot = api.getSnapshot();
  let activePage: SidebarPage = "modules";
  let sidebarExpanded = false;
  let detailExpanded = initialSnapshot.selectedModuleAlias !== null;
  let activeTechnicalViewId: string | null = null;
  let lastSelectedAlias = initialSnapshot.selectedModuleAlias;

  document.body.classList.add("viewer-product-ui");

  const sidebar = document.createElement("aside");
  sidebar.className = "viewer-shell";
  sidebar.setAttribute("aria-label", "Configuração do ambiente");
  sidebar.dataset.viewerRuntimeUi = "mounted";

  const rail = document.createElement("div");
  rail.className = "viewer-shell__rail";
  rail.dataset.sidebarRail = "true";

  const brand = document.createElement("div");
  brand.className = "viewer-shell__mark";
  brand.textContent = "MP";
  brand.setAttribute("aria-label", "MobiliPresenter");
  rail.append(brand);

  const nav = document.createElement("nav");
  nav.className = "viewer-shell__rail-nav";
  nav.setAttribute("aria-label", "Configurações");
  const pageButtons = new Map<SidebarPage, HTMLButtonElement>();
  for (const page of SIDEBAR_PAGES) {
    const item = button("", "viewer-shell__rail-button");
    item.dataset.sidebarPage = page.id;
    item.setAttribute("aria-label", page.label);
    const symbol = document.createElement("span");
    symbol.className = "viewer-shell__rail-symbol";
    symbol.textContent = page.shortLabel;
    symbol.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.className = "viewer-shell__rail-label";
    label.textContent = page.label;
    item.append(symbol, label);
    item.addEventListener("click", () => {
      if (activePage === page.id && sidebarExpanded) {
        sidebarExpanded = false;
      } else {
        activePage = page.id;
        sidebarExpanded = true;
      }
      refresh();
    });
    nav.append(item);
    pageButtons.set(page.id, item);
  }
  rail.append(nav);

  const railActions = document.createElement("div");
  railActions.className = "viewer-shell__rail-actions";
  const detailToggle = button("", "viewer-shell__rail-button viewer-shell__detail-toggle");
  detailToggle.setAttribute("aria-label", "Alternar ficha do módulo selecionado");
  const detailSymbol = document.createElement("span");
  detailSymbol.className = "viewer-shell__rail-symbol";
  detailSymbol.textContent = "D";
  detailSymbol.setAttribute("aria-hidden", "true");
  const detailLabel = document.createElement("span");
  detailLabel.className = "viewer-shell__rail-label";
  detailLabel.textContent = "Detalhes";
  detailToggle.append(detailSymbol, detailLabel);
  detailToggle.addEventListener("click", () => {
    if (!api.getSnapshot().selectedModuleAlias) return;
    detailExpanded = !detailExpanded;
    if (detailExpanded) sidebarExpanded = false;
    refresh();
  });

  const reset = button("", "viewer-shell__rail-button viewer-shell__reset");
  reset.setAttribute("aria-label", "Restaurar configuração");
  const resetSymbol = document.createElement("span");
  resetSymbol.className = "viewer-shell__rail-symbol";
  resetSymbol.textContent = "↺";
  resetSymbol.setAttribute("aria-hidden", "true");
  const resetLabel = document.createElement("span");
  resetLabel.className = "viewer-shell__rail-label";
  resetLabel.textContent = "Restaurar";
  reset.append(resetSymbol, resetLabel);
  reset.addEventListener("click", () => runAction(() => api.resetConfiguration()));
  railActions.append(detailToggle, reset);
  rail.append(railActions);

  const drawer = document.createElement("section");
  drawer.className = "viewer-shell__drawer";
  drawer.setAttribute("aria-label", "Seletores de configuração");

  const drawerHeader = document.createElement("header");
  drawerHeader.className = "viewer-shell__drawer-header";
  const drawerHeading = document.createElement("div");
  const drawerEyebrow = paragraph("CONFIGURAR", "viewer-shell__drawer-eyebrow");
  const drawerTitle = document.createElement("h2");
  drawerHeading.append(drawerEyebrow, drawerTitle);
  const drawerClose = button("×", "viewer-icon-button viewer-shell__drawer-close");
  drawerClose.setAttribute("aria-label", "Recolher seletores");
  drawerClose.addEventListener("click", () => {
    sidebarExpanded = false;
    refresh();
  });
  drawerHeader.append(drawerHeading, drawerClose);
  drawer.append(drawerHeader);

  const pageHost = document.createElement("div");
  pageHost.className = "viewer-shell__page-host viewer-scroll-surface";
  drawer.append(pageHost);

  const status = createStatus();
  drawer.append(status.root);
  sidebar.append(rail, drawer);

  const detail = document.createElement("section");
  detail.className = "viewer-technical-detail";
  detail.setAttribute("aria-label", "Detalhes técnicos do módulo");
  detail.hidden = true;

  function report(error: unknown): void {
    status.root.dataset.error = "true";
    status.message.textContent = error instanceof Error ? error.message : String(error);
  }

  function runAction(action: () => void, onSuccess?: () => void): void {
    try {
      action();
      onSuccess?.();
      status.root.dataset.error = "false";
      status.message.textContent = "Configuração sincronizada";
      refresh();
    } catch (error) {
      report(error);
    }
  }

  function renderModulesPage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--modules";
    page.dataset.sidebarPagePanel = "modules";
    page.append(paragraph("Mostre ou oculte módulos pelo checkbox. Clique no restante da linha para abrir a apresentação.", "viewer-sidebar-page__description"));

    const list = document.createElement("div");
    list.className = "viewer-module-list";
    for (const alias of catalog.modules) {
      const visible = snapshot.visibilityByModule[alias] !== "off";
      const selected = snapshot.selectedModuleAlias === alias;
      const row = document.createElement("div");
      row.className = "viewer-module-row";
      row.dataset.visible = visible ? "true" : "false";
      row.dataset.selected = selected ? "true" : "false";

      const visibilityLabel = document.createElement("label");
      visibilityLabel.className = "viewer-module-row__visibility";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = visible;
      checkbox.dataset.moduleVisibility = alias;
      checkbox.setAttribute("aria-label", `${visible ? "Ocultar" : "Mostrar"} módulo ${alias}`);
      checkbox.addEventListener("click", event => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        runAction(() => api.setModuleVisibility(alias, checkbox.checked ? "inherit" : "off"));
      });
      const checkmark = document.createElement("span");
      checkmark.className = "viewer-module-row__checkmark";
      checkmark.setAttribute("aria-hidden", "true");
      visibilityLabel.append(checkbox, checkmark);

      const inspect = button("", "viewer-module-row__inspect");
      inspect.dataset.moduleAlias = alias;
      inspect.setAttribute("aria-pressed", selected ? "true" : "false");
      inspect.setAttribute("aria-label", `Abrir apresentação do módulo ${alias}`);
      inspect.addEventListener("click", () => runAction(
        () => api.selectModule(alias),
        () => {
          detailExpanded = true;
          sidebarExpanded = false;
          activeTechnicalViewId = null;
        }
      ));

      const thumbnail = document.createElement("span");
      thumbnail.className = "viewer-module-row__thumbnail";
      thumbnail.setAttribute("aria-hidden", "true");
      const thumbnailNumber = document.createElement("span");
      thumbnailNumber.textContent = alias;
      thumbnail.append(thumbnailNumber);

      const copy = document.createElement("span");
      copy.className = "viewer-module-row__copy";
      const name = document.createElement("strong");
      name.textContent = `Módulo ${alias}`;
      const presentation = selected ? snapshot.selectedTechnicalPresentation : null;
      const subtitle = document.createElement("span");
      subtitle.textContent = presentation ? humanModuleName(alias, presentation) : "Informações a definir";
      subtitle.dataset.placeholder = presentation ? "false" : "true";
      copy.append(name, subtitle);
      inspect.append(thumbnail, copy);
      row.append(visibilityLabel, inspect);
      list.append(row);
    }
    page.append(list);
    return page;
  }

  function renderColorsPage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const selectedAlias = snapshot.selectedModuleAlias;
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--colors";
    page.dataset.sidebarPagePanel = "colors";
    page.append(paragraph(
      selectedAlias ? `Aplicando ao módulo ${selectedAlias}.` : "Selecione um módulo para alterar o acabamento das frentes.",
      "viewer-sidebar-page__description"
    ));

    const fronts = document.createElement("section");
    fronts.className = "viewer-option-section";
    const frontsHeading = document.createElement("h3");
    frontsHeading.textContent = "Frentes";
    const frontGrid = document.createElement("div");
    frontGrid.className = "viewer-finish-grid";

    const original = button("Original", "viewer-finish-option");
    original.dataset.frontPreset = "original";
    original.disabled = !selectedAlias;
    original.setAttribute("aria-pressed", selectedAlias && snapshot.frontPresetByModule[selectedAlias] === undefined ? "true" : "false");
    original.addEventListener("click", () => {
      const alias = api.getSnapshot().selectedModuleAlias;
      if (!alias) return;
      runAction(() => api.clearFrontPreset(alias));
    });
    frontGrid.append(original);

    for (const preset of catalog.frontPresets) {
      const option = button(preset.label, "viewer-finish-option");
      option.dataset.frontPreset = preset.id;
      option.disabled = !selectedAlias;
      const active = selectedAlias ? snapshot.frontPresetByModule[selectedAlias] === preset.id : false;
      option.setAttribute("aria-pressed", active ? "true" : "false");
      option.addEventListener("click", () => {
        const alias = api.getSnapshot().selectedModuleAlias;
        if (!alias) return;
        runAction(() => api.setFrontPreset(alias, preset.id as FrontPresetId));
      });
      frontGrid.append(option);
    }
    fronts.append(frontsHeading, frontGrid);

    const stone = document.createElement("section");
    stone.className = "viewer-option-section";
    const stoneHeading = document.createElement("h3");
    stoneHeading.textContent = "Pedra";
    const stoneGrid = document.createElement("div");
    stoneGrid.className = "viewer-finish-grid";
    for (const preset of catalog.stonePresets) {
      const option = button(preset.label, "viewer-finish-option");
      option.dataset.stonePreset = preset.id;
      option.setAttribute("aria-pressed", snapshot.stonePresetId === preset.id ? "true" : "false");
      option.addEventListener("click", () => runAction(() => api.setStonePreset(preset.id as StonePresetId)));
      stoneGrid.append(option);
    }
    stone.append(stoneHeading, stoneGrid);

    if (!selectedAlias) {
      page.append(createPlaceholder("Módulo alvo a definir", "A seleção de acabamento da frente será habilitada após escolher um módulo."));
    }
    page.append(fronts, stone);
    return page;
  }

  function renderAccessoriesPage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--accessories";
    page.dataset.sidebarPagePanel = "accessories";
    page.append(paragraph("A interface exibe apenas capacidades efetivamente publicadas pelo contrato atual.", "viewer-sidebar-page__description"));

    const lights = document.createElement("section");
    lights.className = "viewer-option-section";
    const lightsHeading = document.createElement("h3");
    lightsHeading.textContent = "Iluminação de apresentação";
    const lightGrid = document.createElement("div");
    lightGrid.className = "viewer-accessory-grid";
    for (const preset of catalog.lightingPresets) {
      const option = button(preset.label, "viewer-accessory-option");
      option.dataset.lightingPreset = preset.id;
      option.setAttribute("aria-pressed", snapshot.lightingPresetId === preset.id ? "true" : "false");
      option.addEventListener("click", () => runAction(() => api.setLightingPreset(preset.id as LightingPresetId)));
      lightGrid.append(option);
    }
    lights.append(lightsHeading, lightGrid);

    page.append(
      lights,
      createPlaceholder(
        "Acessórios a definir",
        "Puxadores e outros acessórios aparecerão aqui quando catálogo, compatibilidade e comandos forem publicados pelo ViewerUiContract."
      )
    );
    return page;
  }

  function renderSidebarPages(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): void {
    const pages: readonly [SidebarPage, HTMLElement][] = [
      ["modules", renderModulesPage(snapshot)],
      ["colors", renderColorsPage(snapshot)],
      ["accessories", renderAccessoriesPage(snapshot)]
    ];
    for (const [pageId, page] of pages) page.hidden = pageId !== activePage;
    pageHost.replaceChildren(...pages.map(([, page]) => page));
  }

  function refreshNavigation(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): void {
    const activeConfig = SIDEBAR_PAGES.find(page => page.id === activePage)!;
    drawerTitle.textContent = activeConfig.label;
    sidebar.dataset.expanded = sidebarExpanded ? "true" : "false";
    drawer.hidden = !sidebarExpanded;

    for (const [page, item] of pageButtons) {
      const active = page === activePage;
      item.setAttribute("aria-pressed", active ? "true" : "false");
      item.setAttribute("aria-expanded", active && sidebarExpanded ? "true" : "false");
      item.dataset.active = active ? "true" : "false";
    }

    detailToggle.hidden = snapshot.selectedModuleAlias === null;
    detailToggle.setAttribute("aria-pressed", detailExpanded ? "true" : "false");
  }

  function refresh(): void {
    const snapshot = api.getSnapshot();
    if (snapshot.selectedModuleAlias !== lastSelectedAlias) {
      if (snapshot.selectedModuleAlias === null) {
        detailExpanded = false;
      } else {
        detailExpanded = true;
        sidebarExpanded = false;
      }
      activeTechnicalViewId = null;
      lastSelectedAlias = snapshot.selectedModuleAlias;
    }

    renderSidebarPages(snapshot);
    refreshNavigation(snapshot);
    renderTechnicalDetail(
      detail,
      snapshot,
      detailExpanded,
      activeTechnicalViewId,
      () => {
        detailExpanded = false;
        refresh();
      },
      viewId => {
        activeTechnicalViewId = viewId;
        refresh();
      }
    );

    const detailOpen = snapshot.selectedModuleAlias !== null && detailExpanded;
    document.body.dataset.viewerDetailOpen = detailOpen ? "true" : "false";
    document.body.dataset.viewerSidebarOpen = sidebarExpanded ? "true" : "false";
  }

  host.append(sidebar, detail);
  refresh();

  return {
    refresh,
    dispose(): void {
      sidebar.remove();
      detail.remove();
      document.body.classList.remove("viewer-product-ui");
      delete document.body.dataset.viewerDetailOpen;
      delete document.body.dataset.viewerSidebarOpen;
    }
  };
}

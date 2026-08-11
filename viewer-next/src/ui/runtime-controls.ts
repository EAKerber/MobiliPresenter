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

const SIDEBAR_PAGES: readonly { readonly id: SidebarPage; readonly label: string }[] = [
  { id: "modules", label: "Módulos" },
  { id: "colors", label: "Cores" },
  { id: "accessories", label: "Acessórios" }
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

function createTechnicalView(
  pkg: TechnicalPresentationPackage,
  asset: TechnicalDiagramAsset
): HTMLElement | null {
  if (asset.status !== "ready" || asset.svg === null) return null;
  const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
  if (!request) return null;

  const figure = document.createElement("figure");
  figure.className = "viewer-technical-view";
  figure.dataset.technicalView = asset.viewId;

  const media = document.createElement("div");
  media.className = "viewer-technical-view__media";
  media.innerHTML = asset.svg;

  const caption = document.createElement("figcaption");
  caption.textContent = request.label;
  figure.append(media, caption);
  return figure;
}

function createFactList(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.specifications.length === 0) return null;
  const section = document.createElement("section");
  section.className = "viewer-technical-card viewer-technical-card--wide";
  const heading = document.createElement("h3");
  heading.textContent = "Especificação técnica";
  const list = document.createElement("ul");
  list.className = "viewer-technical-card__list";
  for (const fact of pkg.specifications) {
    const item = document.createElement("li");
    item.textContent = fact.text;
    list.append(item);
  }
  section.append(heading, list);
  return section;
}

function createComponentsCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.components.length === 0) return null;
  const section = document.createElement("section");
  section.className = "viewer-technical-card";
  const heading = document.createElement("h3");
  heading.textContent = "Componentes";
  const list = document.createElement("ul");
  list.className = "viewer-technical-card__stack";

  for (const component of pkg.components) {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = component.label;
    item.append(name);
    const detailParts: string[] = [];
    if (component.specification) detailParts.push(component.specification);
    if (component.quantity !== undefined) {
      detailParts.push(`${formatTechnicalNumber(component.quantity)}${component.unit ? ` ${component.unit}` : ""}`);
    }
    if (detailParts.length > 0) {
      const detail = document.createElement("span");
      detail.textContent = detailParts.join(" · ");
      item.append(detail);
    }
    list.append(item);
  }

  section.append(heading, list);
  return section;
}

function createFinishesCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.finishes.length === 0) return null;
  const section = document.createElement("section");
  section.className = "viewer-technical-card";
  const heading = document.createElement("h3");
  heading.textContent = "Acabamentos";
  const list = document.createElement("ul");
  list.className = "viewer-technical-card__stack";

  for (const finish of pkg.finishes) {
    const item = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = finish.label;
    item.append(label);
    const current = finish.currentOptionId
      ? finish.options.find(candidate => candidate.id === finish.currentOptionId)
      : null;
    if (current) {
      const value = document.createElement("span");
      value.textContent = current.label;
      item.append(value);
    }
    list.append(item);
  }
  section.append(heading, list);
  return section;
}

function createNoticesCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  const visibleNotices = pkg.notices;
  const unavailableDependencies = pkg.dependencies.filter(dependency => !dependency.effectiveVisible);
  if (visibleNotices.length === 0 && unavailableDependencies.length === 0) return null;

  const section = document.createElement("section");
  section.className = "viewer-technical-card viewer-technical-card--notice";
  const heading = document.createElement("h3");
  heading.textContent = "Observações";
  const list = document.createElement("div");
  list.className = "viewer-technical-card__notices";

  for (const notice of visibleNotices) {
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

  section.append(heading, list);
  return section;
}

function renderTechnicalDetail(
  root: HTMLElement,
  snapshot: ReturnType<ViewerUiApi["getSnapshot"]>,
  onClose: () => void
): void {
  root.replaceChildren();
  const pkg = snapshot.selectedTechnicalPresentation;
  if (!pkg) {
    root.hidden = true;
    return;
  }

  root.hidden = false;
  root.dataset.moduleAlias = snapshot.selectedModuleAlias ?? pkg.identity.alias;

  const header = document.createElement("header");
  header.className = "viewer-technical-detail__header";
  const headingWrap = document.createElement("div");
  headingWrap.className = "viewer-technical-detail__heading";
  const eyebrow = paragraph(`MÓDULO ${pkg.identity.alias}`, "viewer-technical-detail__eyebrow");
  const title = document.createElement("h2");
  title.textContent = pkg.identity.title;
  headingWrap.append(eyebrow, title);

  const meta = document.createElement("div");
  meta.className = "viewer-technical-detail__meta";
  const dimensions = formatDimensions(pkg);
  if (dimensions) {
    const dimensionsElement = document.createElement("span");
    dimensionsElement.className = "viewer-technical-detail__dimensions";
    dimensionsElement.textContent = dimensions;
    meta.append(dimensionsElement);
  }
  const finishLabel = currentFinishLabel(pkg);
  if (finishLabel) {
    const finish = document.createElement("span");
    finish.className = "viewer-technical-detail__finish";
    finish.textContent = finishLabel;
    meta.append(finish);
  }
  headingWrap.append(meta);

  const close = button("×", "viewer-icon-button viewer-technical-detail__close");
  close.setAttribute("aria-label", `Fechar detalhes do módulo ${pkg.identity.alias}`);
  close.addEventListener("click", onClose);
  header.append(headingWrap, close);

  const content = document.createElement("div");
  content.className = "viewer-technical-detail__content";

  const readyViews = snapshot.selectedTechnicalViewAssets
    .map(asset => createTechnicalView(pkg, asset))
    .filter((view): view is HTMLElement => view !== null);
  if (readyViews.length > 0) {
    const viewsSection = document.createElement("section");
    viewsSection.className = "viewer-technical-detail__views";
    const viewsHeading = document.createElement("h3");
    viewsHeading.textContent = "Vistas técnicas";
    const views = document.createElement("div");
    views.className = "viewer-technical-views";
    views.append(...readyViews);
    viewsSection.append(viewsHeading, views);
    content.append(viewsSection);
  }

  const cards = document.createElement("div");
  cards.className = "viewer-technical-detail__cards";
  for (const card of [
    createFactList(pkg),
    createComponentsCard(pkg),
    createFinishesCard(pkg),
    createNoticesCard(pkg)
  ]) {
    if (card) cards.append(card);
  }
  if (cards.childElementCount > 0) content.append(cards);

  root.append(header, content);
}

export function mountRuntimeControls(host: HTMLElement, api: ViewerUiApi): RuntimeControlsUi {
  const catalog = api.getCatalog();
  let activePage: SidebarPage = "modules";

  document.body.classList.add("viewer-product-ui");

  const sidebar = document.createElement("aside");
  sidebar.className = "viewer-shell";
  sidebar.setAttribute("aria-label", "Configuração do ambiente");
  sidebar.dataset.viewerRuntimeUi = "mounted";

  const header = document.createElement("header");
  header.className = "viewer-shell__header";
  const brand = document.createElement("div");
  brand.className = "viewer-shell__brand";
  brand.append(
    paragraph("MobiliPresenter", "viewer-shell__brand-name"),
    paragraph("Apresentação do ambiente", "viewer-shell__brand-subtitle")
  );
  const reset = button("Restaurar", "viewer-button viewer-button--ghost viewer-shell__reset");
  reset.addEventListener("click", () => runAction(() => api.resetConfiguration()));
  header.append(brand, reset);
  sidebar.append(header);

  const pageHost = document.createElement("div");
  pageHost.className = "viewer-shell__page-host";
  sidebar.append(pageHost);

  const status = createStatus();
  sidebar.append(status.root);

  const nav = document.createElement("nav");
  nav.className = "viewer-shell__nav";
  nav.setAttribute("aria-label", "Configurações");
  const pageButtons = new Map<SidebarPage, HTMLButtonElement>();
  for (const page of SIDEBAR_PAGES) {
    const item = button(page.label, "viewer-shell__nav-button");
    item.dataset.sidebarPage = page.id;
    item.addEventListener("click", () => {
      activePage = page.id;
      refresh();
    });
    nav.append(item);
    pageButtons.set(page.id, item);
  }
  sidebar.append(nav);

  const detail = document.createElement("section");
  detail.className = "viewer-technical-detail";
  detail.setAttribute("aria-label", "Detalhes técnicos do módulo");
  detail.hidden = true;

  function report(error: unknown): void {
    status.root.dataset.error = "true";
    status.message.textContent = error instanceof Error ? error.message : String(error);
  }

  function runAction(action: () => void): void {
    try {
      action();
      status.root.dataset.error = "false";
      status.message.textContent = "Configuração sincronizada";
      refresh();
    } catch (error) {
      report(error);
    }
  }

  function renderModulesPage(): HTMLElement {
    const snapshot = api.getSnapshot();
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--modules";
    page.dataset.sidebarPagePanel = "modules";

    const intro = document.createElement("div");
    intro.className = "viewer-sidebar-page__heading";
    const title = document.createElement("h2");
    title.textContent = "Módulos";
    intro.append(title, paragraph("Mostre, oculte ou abra os detalhes de cada módulo.", "viewer-sidebar-page__description"));
    page.append(intro);

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
      inspect.setAttribute("aria-label", `Abrir detalhes do módulo ${alias}`);
      inspect.addEventListener("click", () => runAction(() => api.selectModule(alias)));

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
      subtitle.textContent = presentation ? humanModuleName(alias, presentation) : visible ? "visível" : "oculto";
      copy.append(name, subtitle);
      inspect.append(thumbnail, copy);
      row.append(visibilityLabel, inspect);
      list.append(row);
    }
    page.append(list);
    return page;
  }

  function renderColorsPage(): HTMLElement {
    const snapshot = api.getSnapshot();
    const selectedAlias = snapshot.selectedModuleAlias;
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--colors";
    page.dataset.sidebarPagePanel = "colors";

    const intro = document.createElement("div");
    intro.className = "viewer-sidebar-page__heading";
    const title = document.createElement("h2");
    title.textContent = "Cores";
    const context = selectedAlias
      ? `Acabamento do módulo ${selectedAlias}`
      : "Selecione um módulo para alterar o acabamento da frente.";
    intro.append(title, paragraph(context, "viewer-sidebar-page__description"));
    page.append(intro);

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
    page.append(fronts, stone);
    return page;
  }

  function renderAccessoriesPage(): HTMLElement {
    const snapshot = api.getSnapshot();
    const page = document.createElement("section");
    page.className = "viewer-sidebar-page viewer-sidebar-page--accessories";
    page.dataset.sidebarPagePanel = "accessories";

    const intro = document.createElement("div");
    intro.className = "viewer-sidebar-page__heading";
    const title = document.createElement("h2");
    title.textContent = "Acessórios";
    intro.append(title, paragraph("Opções disponíveis pelo contrato atual do viewer.", "viewer-sidebar-page__description"));
    page.append(intro);

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

    const pending = document.createElement("div");
    pending.className = "viewer-contract-note";
    const pendingTitle = document.createElement("strong");
    pendingTitle.textContent = "Demais acessórios";
    pending.append(
      pendingTitle,
      paragraph("A seleção de puxadores e outros acessórios será exibida aqui quando essas opções forem publicadas pelo contrato da UI.", "viewer-contract-note__text")
    );

    page.append(lights, pending);
    return page;
  }

  function renderSidebarPages(): void {
    const pages: readonly [SidebarPage, HTMLElement][] = [
      ["modules", renderModulesPage()],
      ["colors", renderColorsPage()],
      ["accessories", renderAccessoriesPage()]
    ];
    for (const [pageId, page] of pages) page.hidden = pageId !== activePage;
    pageHost.replaceChildren(...pages.map(([, page]) => page));
  }

  function refreshNav(): void {
    for (const [page, item] of pageButtons) {
      const active = page === activePage;
      item.setAttribute("aria-current", active ? "page" : "false");
      item.dataset.active = active ? "true" : "false";
    }
  }

  function refresh(): void {
    const snapshot = api.getSnapshot();
    renderSidebarPages();
    refreshNav();
    renderTechnicalDetail(detail, snapshot, () => runAction(() => api.selectModule(null)));
    document.body.dataset.viewerDetailOpen = snapshot.selectedTechnicalPresentation ? "true" : "false";
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
    }
  };
}

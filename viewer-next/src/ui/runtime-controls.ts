import type {
  FrontPresetId,
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

type ConfiguratorStep = "modules" | "finishes" | "accessories" | "summary";

type StatusElements = {
  readonly root: HTMLElement;
  readonly message: HTMLElement;
};

const STEPS: readonly {
  readonly id: ConfiguratorStep;
  readonly index: number;
  readonly label: string;
  readonly compactLabel: string;
}[] = [
  { id: "modules", index: 1, label: "Módulos", compactLabel: "Módulos" },
  { id: "finishes", index: 2, label: "Acabamentos", compactLabel: "Acab." },
  { id: "accessories", index: 3, label: "Acessórios", compactLabel: "Acess." },
  { id: "summary", index: 4, label: "Resumo", compactLabel: "Resumo" }
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

function optionLabel<TId extends string>(
  options: readonly { readonly id: TId; readonly label: string }[],
  id: TId
): string {
  return options.find(option => option.id === id)?.label ?? id;
}

function createStatus(): StatusElements {
  const root = document.createElement("div");
  root.className = "viewer-configurator__status";
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");
  root.dataset.error = "false";
  const message = document.createElement("span");
  message.textContent = "Configuração sincronizada";
  root.append(message);
  return { root, message };
}

function currentFinishLabel(pkg: TechnicalPresentationPackage): string | null {
  for (const policy of pkg.finishes) {
    if (!policy.currentOptionId) continue;
    const option = policy.options.find(candidate => candidate.id === policy.currentOptionId);
    if (option) return option.label;
  }
  return null;
}

function createTechnicalFigure(
  pkg: TechnicalPresentationPackage,
  asset: TechnicalDiagramAsset
): HTMLElement | null {
  if (asset.status !== "ready" || asset.svg === null) return null;
  const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
  if (!request) return null;

  const figure = document.createElement("figure");
  figure.className = "viewer-product-detail__figure";
  figure.dataset.technicalView = asset.viewId;
  figure.dataset.technicalFidelity = asset.fidelity ?? "unknown";

  const media = document.createElement("div");
  media.className = "viewer-product-detail__figure-media";
  media.innerHTML = asset.svg;

  const caption = document.createElement("figcaption");
  const label = document.createElement("span");
  label.textContent = request.label;
  const fidelity = document.createElement("span");
  fidelity.className = "viewer-product-detail__fidelity";
  fidelity.textContent = asset.fidelity === "geometry-derived"
    ? "derivada da geometria"
    : asset.fidelity === "authored"
      ? "vista autorada"
      : "esquema dimensional";
  caption.append(label, fidelity);
  figure.append(media, caption);
  return figure;
}

function createInfoCard(titleText: string, className = ""): HTMLElement {
  const section = document.createElement("section");
  section.className = `viewer-product-card${className ? ` ${className}` : ""}`;
  const heading = document.createElement("h3");
  heading.textContent = titleText;
  section.append(heading);
  return section;
}

function createSpecificationCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.specifications.length === 0) return null;
  const section = createInfoCard("Especificações", "viewer-product-card--wide");
  const list = document.createElement("ul");
  list.className = "viewer-product-card__list";
  for (const fact of pkg.specifications) {
    const item = document.createElement("li");
    item.textContent = fact.text;
    list.append(item);
  }
  section.append(list);
  return section;
}

function createComponentsCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.components.length === 0) return null;
  const section = createInfoCard("Componentes");
  const list = document.createElement("ul");
  list.className = "viewer-product-card__stack";
  for (const component of pkg.components) {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = component.label;
    item.append(name);
    const details: string[] = [];
    if (component.specification) details.push(component.specification);
    if (component.quantity !== undefined) {
      details.push(`${formatTechnicalNumber(component.quantity)}${component.unit ? ` ${component.unit}` : ""}`);
    }
    if (details.length > 0) {
      const detail = document.createElement("span");
      detail.textContent = details.join(" · ");
      item.append(detail);
    }
    list.append(item);
  }
  section.append(list);
  return section;
}

function createDependencyCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.dependencies.length === 0) return null;
  const section = createInfoCard("Dependências");
  const list = document.createElement("ul");
  list.className = "viewer-product-card__stack";
  for (const dependency of pkg.dependencies) {
    const item = document.createElement("li");
    item.dataset.satisfied = dependency.effectiveVisible ? "true" : "false";
    const label = document.createElement("strong");
    label.textContent = dependency.label;
    const state = document.createElement("span");
    state.textContent = dependency.effectiveVisible ? "disponível na composição" : "requer atenção na composição";
    item.append(label, state);
    list.append(item);
  }
  section.append(list);
  return section;
}

function createNoticesCard(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.notices.length === 0) return null;
  const section = createInfoCard("Avisos", "viewer-product-card--notice");
  const list = document.createElement("div");
  list.className = "viewer-product-card__notices";
  for (const notice of pkg.notices) {
    const item = document.createElement("div");
    item.className = "viewer-product-notice";
    item.dataset.severity = notice.severity;
    if (notice.title) {
      const title = document.createElement("strong");
      title.textContent = notice.title;
      item.append(title);
    }
    item.append(paragraph(notice.text, "viewer-product-notice__text"));
    list.append(item);
  }
  section.append(list);
  return section;
}

function createFinishesSummary(pkg: TechnicalPresentationPackage): HTMLElement | null {
  if (pkg.finishes.length === 0) return null;
  const section = createInfoCard("Acabamento atual");
  const list = document.createElement("ul");
  list.className = "viewer-product-card__stack";
  for (const finish of pkg.finishes) {
    const item = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = finish.label;
    const current = finish.currentOptionId
      ? finish.options.find(candidate => candidate.id === finish.currentOptionId)
      : null;
    const value = document.createElement("span");
    value.textContent = current?.label ?? "padrão do ambiente";
    item.append(label, value);
    list.append(item);
  }
  section.append(list);
  return section;
}

export function mountRuntimeControls(host: HTMLElement, api: ViewerUiApi): RuntimeControlsUi {
  const catalog = api.getCatalog();
  let currentStep: ConfiguratorStep = "modules";
  const visitedSteps = new Set<ConfiguratorStep>(["modules"]);
  let detailExpanded = false;
  let moduleEditorExpanded = false;
  let activeTechnicalViewId: string | null = null;
  let lastSelectedAlias: ModuleAlias | null = null;

  document.body.classList.add("viewer-product-ui");

  const root = document.createElement("div");
  root.className = "viewer-configurator";
  root.dataset.viewerRuntimeUi = "mounted";
  root.dataset.currentStep = currentStep;

  const topbar = document.createElement("header");
  topbar.className = "viewer-configurator__topbar";

  const context = document.createElement("div");
  context.className = "viewer-configurator__context";
  const contextTitle = document.createElement("strong");
  contextTitle.textContent = "Configuração do ambiente";
  const contextSubtitle = document.createElement("span");
  contextSubtitle.textContent = "Cena persistente · fluxo guiado";
  context.append(contextTitle, contextSubtitle);

  const stepNav = document.createElement("nav");
  stepNav.className = "viewer-step-nav";
  stepNav.setAttribute("aria-label", "Etapas da configuração");
  const stepButtons = new Map<ConfiguratorStep, HTMLButtonElement>();
  for (const step of STEPS) {
    const item = button("", "viewer-step-nav__item");
    item.dataset.configuratorStep = step.id;
    const number = document.createElement("span");
    number.className = "viewer-step-nav__number";
    number.textContent = String(step.index);
    const labels = document.createElement("span");
    labels.className = "viewer-step-nav__labels";
    const full = document.createElement("span");
    full.className = "viewer-step-nav__label viewer-step-nav__label--full";
    full.textContent = step.label;
    const compact = document.createElement("span");
    compact.className = "viewer-step-nav__label viewer-step-nav__label--compact";
    compact.textContent = step.compactLabel;
    labels.append(full, compact);
    item.append(number, labels);
    item.addEventListener("click", () => setStep(step.id));
    stepNav.append(item);
    stepButtons.set(step.id, item);
  }

  const utilities = document.createElement("div");
  utilities.className = "viewer-configurator__utilities";
  const reset = button("Restaurar", "viewer-button viewer-button--ghost");
  reset.addEventListener("click", () => runAction(() => api.resetConfiguration()));
  utilities.append(reset);
  topbar.append(context, stepNav, utilities);

  const stagePanel = document.createElement("aside");
  stagePanel.className = "viewer-configurator__stage";
  stagePanel.setAttribute("aria-label", "Etapa atual da configuração");

  const stageHost = document.createElement("div");
  stageHost.className = "viewer-configurator__stage-content";
  stagePanel.append(stageHost);

  const status = createStatus();
  stagePanel.append(status.root);

  const detail = document.createElement("section");
  detail.className = "viewer-product-detail";
  detail.setAttribute("aria-label", "Detalhes do módulo selecionado");
  detail.hidden = true;

  const moduleEditor = document.createElement("aside");
  moduleEditor.className = "viewer-module-editor";
  moduleEditor.setAttribute("aria-label", "Editar módulos da composição");
  moduleEditor.hidden = true;

  const actions = document.createElement("footer");
  actions.className = "viewer-configurator__actions";
  const back = button("← Voltar", "viewer-button viewer-button--secondary");
  const next = button("Continuar →", "viewer-button viewer-button--primary");
  back.addEventListener("click", () => moveStep(-1));
  next.addEventListener("click", () => moveStep(1));
  actions.append(back, next);

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

  function setStep(step: ConfiguratorStep): void {
    currentStep = step;
    visitedSteps.add(step);
    moduleEditorExpanded = false;
    refresh();
  }

  function moveStep(direction: -1 | 1): void {
    const index = STEPS.findIndex(step => step.id === currentStep);
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= STEPS.length) return;
    setStep(STEPS[nextIndex]!.id);
  }

  function visibleModuleCount(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): number {
    return catalog.modules.filter(alias => snapshot.visibilityByModule[alias] !== "off").length;
  }

  function createModuleList(
    snapshot: ReturnType<ViewerUiApi["getSnapshot"]>,
    compact = false
  ): HTMLElement {
    const list = document.createElement("div");
    list.className = compact ? "viewer-module-list viewer-module-list--compact" : "viewer-module-list";

    for (const alias of catalog.modules) {
      const visible = snapshot.visibilityByModule[alias] !== "off";
      const selected = snapshot.selectedModuleAlias === alias;
      const presentation = selected ? snapshot.selectedTechnicalPresentation : null;

      const row = document.createElement("article");
      row.className = "viewer-module-card";
      row.dataset.moduleAlias = alias;
      row.dataset.visible = visible ? "true" : "false";
      row.dataset.selected = selected ? "true" : "false";

      const visibilityLabel = document.createElement("label");
      visibilityLabel.className = "viewer-module-card__visibility";
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
      checkmark.className = "viewer-module-card__checkmark";
      checkmark.setAttribute("aria-hidden", "true");
      visibilityLabel.append(checkbox, checkmark);

      const thumbnail = document.createElement("span");
      thumbnail.className = "viewer-module-card__thumbnail";
      thumbnail.setAttribute("aria-hidden", "true");
      const thumbnailNumber = document.createElement("span");
      thumbnailNumber.textContent = alias;
      thumbnail.append(thumbnailNumber);

      const copy = document.createElement("div");
      copy.className = "viewer-module-card__copy";
      const title = document.createElement("strong");
      title.textContent = presentation?.identity.title ?? `Módulo ${alias}`;
      const meta = document.createElement("span");
      const dimensions = presentation ? formatDimensions(presentation) : null;
      meta.textContent = dimensions ?? (visible ? "incluído na composição" : "fora da composição");
      copy.append(title, meta);

      const inspect = button("Detalhes →", "viewer-module-card__inspect");
      inspect.setAttribute("aria-label", `Abrir detalhes do módulo ${alias}`);
      inspect.setAttribute("aria-pressed", selected && detailExpanded ? "true" : "false");
      inspect.addEventListener("click", () => {
        if (snapshot.selectedModuleAlias === alias) {
          detailExpanded = true;
          refresh();
          return;
        }
        detailExpanded = true;
        activeTechnicalViewId = null;
        runAction(() => api.selectModule(alias));
      });

      row.append(visibilityLabel, thumbnail, copy, inspect);
      list.append(row);
    }
    return list;
  }

  function createStageHeading(titleText: string, description: string): HTMLElement {
    const heading = document.createElement("header");
    heading.className = "viewer-stage-heading";
    const copy = document.createElement("div");
    const eyebrow = paragraph(`ETAPA ${STEPS.find(step => step.id === currentStep)!.index} DE 4`, "viewer-stage-heading__eyebrow");
    const title = document.createElement("h2");
    title.textContent = titleText;
    const body = paragraph(description, "viewer-stage-heading__description");
    copy.append(eyebrow, title, body);
    heading.append(copy);
    return heading;
  }

  function createEditModulesShortcut(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLButtonElement {
    const count = visibleModuleCount(snapshot);
    const edit = button(`${count} ${count === 1 ? "módulo" : "módulos"} · Editar`, "viewer-edit-modules");
    edit.addEventListener("click", () => {
      moduleEditorExpanded = true;
      refresh();
    });
    return edit;
  }

  function renderModulesStage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-stage viewer-stage--modules";
    page.dataset.stagePanel = "modules";
    page.append(createStageHeading(
      "Módulos",
      "Defina quais módulos fazem parte do ambiente. O checkbox controla somente inclusão e visibilidade."
    ));
    page.append(createModuleList(snapshot));
    return page;
  }

  function renderFinishesStage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-stage viewer-stage--finishes";
    page.dataset.stagePanel = "finishes";
    const heading = createStageHeading(
      "Acabamentos",
      "Ajuste os acabamentos publicados pelo contrato e acompanhe o resultado diretamente na cena."
    );
    heading.append(createEditModulesShortcut(snapshot));
    page.append(heading);

    const selectedAlias = snapshot.selectedModuleAlias;
    const contextBlock = document.createElement("div");
    contextBlock.className = "viewer-stage-context";
    contextBlock.textContent = selectedAlias
      ? `Módulo em foco: ${selectedAlias}`
      : "Selecione um módulo na cena ou na etapa Módulos para alterar suas frentes.";
    page.append(contextBlock);

    const fronts = document.createElement("section");
    fronts.className = "viewer-option-group";
    const frontsHeading = document.createElement("h3");
    frontsHeading.textContent = "Frentes do módulo";
    const frontGrid = document.createElement("div");
    frontGrid.className = "viewer-option-grid";

    const original = button("Original", "viewer-choice-card");
    original.dataset.frontPreset = "original";
    original.disabled = !selectedAlias;
    original.setAttribute(
      "aria-pressed",
      selectedAlias && snapshot.frontPresetByModule[selectedAlias] === undefined ? "true" : "false"
    );
    original.addEventListener("click", () => {
      const alias = api.getSnapshot().selectedModuleAlias;
      if (!alias) return;
      runAction(() => api.clearFrontPreset(alias));
    });
    frontGrid.append(original);

    for (const preset of catalog.frontPresets) {
      const option = button(preset.label, "viewer-choice-card");
      option.dataset.frontPreset = preset.id;
      option.disabled = !selectedAlias;
      option.setAttribute(
        "aria-pressed",
        selectedAlias && snapshot.frontPresetByModule[selectedAlias] === preset.id ? "true" : "false"
      );
      option.addEventListener("click", () => {
        const alias = api.getSnapshot().selectedModuleAlias;
        if (!alias) return;
        runAction(() => api.setFrontPreset(alias, preset.id as FrontPresetId));
      });
      frontGrid.append(option);
    }
    fronts.append(frontsHeading, frontGrid);

    const stone = document.createElement("section");
    stone.className = "viewer-option-group";
    const stoneHeading = document.createElement("h3");
    stoneHeading.textContent = "Bancada / pedra";
    const stoneGrid = document.createElement("div");
    stoneGrid.className = "viewer-option-grid";
    for (const preset of catalog.stonePresets) {
      const option = button(preset.label, "viewer-choice-card");
      option.dataset.stonePreset = preset.id;
      option.setAttribute("aria-pressed", snapshot.stonePresetId === preset.id ? "true" : "false");
      option.addEventListener("click", () => runAction(() => api.setStonePreset(preset.id as StonePresetId)));
      stoneGrid.append(option);
    }
    stone.append(stoneHeading, stoneGrid);
    page.append(fronts, stone);
    return page;
  }

  function renderAccessoriesStage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-stage viewer-stage--accessories";
    page.dataset.stagePanel = "accessories";
    const heading = createStageHeading(
      "Acessórios",
      "Esta etapa recebe apenas opções comerciais realmente configuráveis publicadas pelo contrato."
    );
    heading.append(createEditModulesShortcut(snapshot));
    page.append(heading);

    const empty = document.createElement("div");
    empty.className = "viewer-empty-state";
    const symbol = document.createElement("span");
    symbol.className = "viewer-empty-state__symbol";
    symbol.setAttribute("aria-hidden", "true");
    symbol.textContent = "+";
    const title = document.createElement("strong");
    title.textContent = "Opções configuráveis ainda não publicadas";
    const copy = paragraph(
      "Puxadores, upgrades e outros acessórios aparecerão aqui quando o catálogo público informar opções, compatibilidade e binding de runtime. Especificações e dependências permanecem nos detalhes dos módulos.",
      "viewer-empty-state__text"
    );
    empty.append(symbol, title, copy);
    page.append(empty);
    return page;
  }

  function renderSummaryStage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): HTMLElement {
    const page = document.createElement("section");
    page.className = "viewer-stage viewer-stage--summary";
    page.dataset.stagePanel = "summary";
    const heading = createStageHeading(
      "Resumo",
      "Revise a composição e retorne a qualquer etapa sem perder as escolhas atuais."
    );
    heading.append(createEditModulesShortcut(snapshot));
    page.append(heading);

    const summary = document.createElement("div");
    summary.className = "viewer-summary";

    const modulesCard = document.createElement("section");
    modulesCard.className = "viewer-summary__card";
    const modulesHeading = document.createElement("div");
    modulesHeading.className = "viewer-summary__card-heading";
    const modulesTitle = document.createElement("h3");
    modulesTitle.textContent = "Módulos do ambiente";
    const editModules = button("Editar", "viewer-text-button");
    editModules.addEventListener("click", () => {
      moduleEditorExpanded = true;
      refresh();
    });
    modulesHeading.append(modulesTitle, editModules);
    const moduleList = document.createElement("ul");
    moduleList.className = "viewer-summary__list";
    for (const alias of catalog.modules) {
      if (snapshot.visibilityByModule[alias] === "off") continue;
      const item = document.createElement("li");
      const label = document.createElement("strong");
      label.textContent = `Módulo ${alias}`;
      const finishId = snapshot.frontPresetByModule[alias];
      const finish = document.createElement("span");
      finish.textContent = finishId
        ? optionLabel(catalog.frontPresets, finishId)
        : "acabamento original";
      item.append(label, finish);
      moduleList.append(item);
    }
    modulesCard.append(modulesHeading, moduleList);

    const finishesCard = document.createElement("section");
    finishesCard.className = "viewer-summary__card";
    const finishesHeading = document.createElement("div");
    finishesHeading.className = "viewer-summary__card-heading";
    const finishesTitle = document.createElement("h3");
    finishesTitle.textContent = "Acabamentos";
    const editFinishes = button("Editar", "viewer-text-button");
    editFinishes.addEventListener("click", () => setStep("finishes"));
    finishesHeading.append(finishesTitle, editFinishes);
    const finishesList = document.createElement("ul");
    finishesList.className = "viewer-summary__list";
    const stoneItem = document.createElement("li");
    const stoneName = document.createElement("strong");
    stoneName.textContent = "Bancada / pedra";
    const stoneValue = document.createElement("span");
    stoneValue.textContent = optionLabel(catalog.stonePresets, snapshot.stonePresetId);
    stoneItem.append(stoneName, stoneValue);
    finishesList.append(stoneItem);
    finishesCard.append(finishesHeading, finishesList);

    const accessoriesCard = document.createElement("section");
    accessoriesCard.className = "viewer-summary__card";
    const accessoriesHeading = document.createElement("div");
    accessoriesHeading.className = "viewer-summary__card-heading";
    const accessoriesTitle = document.createElement("h3");
    accessoriesTitle.textContent = "Acessórios";
    const editAccessories = button("Revisar", "viewer-text-button");
    editAccessories.addEventListener("click", () => setStep("accessories"));
    accessoriesHeading.append(accessoriesTitle, editAccessories);
    accessoriesCard.append(
      accessoriesHeading,
      paragraph("Nenhuma opção comercial configurável foi publicada pelo contrato atual.", "viewer-summary__muted")
    );

    const valueCard = document.createElement("section");
    valueCard.className = "viewer-summary__card viewer-summary__card--value";
    const valueLabel = paragraph("Valor estimado do ambiente", "viewer-summary__value-label");
    const value = document.createElement("strong");
    value.textContent = "Aguardando fonte comercial";
    const valueCopy = paragraph(
      "O valor será apresentado nesta etapa quando existir uma autoridade comercial publicada. Nenhum preço é inferido pela interface.",
      "viewer-summary__muted"
    );
    valueCard.append(valueLabel, value, valueCopy);

    summary.append(modulesCard, finishesCard, accessoriesCard, valueCard);
    page.append(summary);
    return page;
  }

  function renderStage(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): void {
    const page = currentStep === "modules"
      ? renderModulesStage(snapshot)
      : currentStep === "finishes"
        ? renderFinishesStage(snapshot)
        : currentStep === "accessories"
          ? renderAccessoriesStage(snapshot)
          : renderSummaryStage(snapshot);
    stageHost.replaceChildren(page);
  }

  function renderModuleEditor(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): void {
    moduleEditor.replaceChildren();
    moduleEditor.hidden = !moduleEditorExpanded;
    if (!moduleEditorExpanded) return;

    const header = document.createElement("header");
    header.className = "viewer-module-editor__header";
    const copy = document.createElement("div");
    const title = document.createElement("h2");
    title.textContent = "Editar módulos";
    copy.append(title, paragraph(
      "Ajuste a composição sem sair da etapa atual.",
      "viewer-module-editor__description"
    ));
    const close = button("×", "viewer-icon-button");
    close.setAttribute("aria-label", "Fechar edição de módulos");
    close.addEventListener("click", () => {
      moduleEditorExpanded = false;
      refresh();
    });
    header.append(copy, close);

    const body = document.createElement("div");
    body.className = "viewer-module-editor__body";
    body.append(createModuleList(snapshot, true));

    const footer = document.createElement("footer");
    footer.className = "viewer-module-editor__footer";
    const done = button("Concluir edição", "viewer-button viewer-button--primary");
    done.addEventListener("click", () => {
      moduleEditorExpanded = false;
      refresh();
    });
    footer.append(done);
    moduleEditor.append(header, body, footer);
  }

  function renderDetail(snapshot: ReturnType<ViewerUiApi["getSnapshot"]>): void {
    detail.replaceChildren();
    const alias = snapshot.selectedModuleAlias;
    if (!detailExpanded || alias === null) {
      detail.hidden = true;
      return;
    }

    detail.hidden = false;
    detail.dataset.moduleAlias = alias;
    detail.dataset.presentationStatus = snapshot.selectedTechnicalPresentationAvailability.status;

    const header = document.createElement("header");
    header.className = "viewer-product-detail__header";
    const heading = document.createElement("div");
    heading.className = "viewer-product-detail__heading";
    const eyebrow = paragraph(`MÓDULO ${alias}`, "viewer-product-detail__eyebrow");
    const title = document.createElement("h2");
    title.textContent = snapshot.selectedTechnicalPresentation?.identity.title ?? `Módulo ${alias}`;
    heading.append(eyebrow, title);

    const pkg = snapshot.selectedTechnicalPresentation;
    if (pkg) {
      const meta = document.createElement("div");
      meta.className = "viewer-product-detail__meta";
      const dimensions = formatDimensions(pkg);
      if (dimensions) {
        const item = document.createElement("span");
        item.textContent = dimensions;
        meta.append(item);
      }
      const finish = currentFinishLabel(pkg);
      if (finish) {
        const item = document.createElement("span");
        item.textContent = finish;
        meta.append(item);
      }
      heading.append(meta);
    }

    const close = button("×", "viewer-icon-button");
    close.setAttribute("aria-label", `Fechar detalhes do módulo ${alias}`);
    close.addEventListener("click", () => {
      detailExpanded = false;
      refresh();
    });
    header.append(heading, close);
    detail.append(header);

    if (snapshot.selectedTechnicalPresentationAvailability.status === "unavailable" || pkg === null) {
      const unavailable = document.createElement("div");
      unavailable.className = "viewer-product-detail__unavailable";
      const symbol = document.createElement("span");
      symbol.setAttribute("aria-hidden", "true");
      symbol.textContent = "i";
      const unavailableTitle = document.createElement("strong");
      unavailableTitle.textContent = "Detalhes técnicos ainda não publicados";
      const unavailableCopy = paragraph(
        "O módulo continua selecionável e configurável dentro das capacidades públicas disponíveis. Informações técnicas ausentes não são inferidas pela interface.",
        "viewer-product-detail__unavailable-text"
      );
      unavailable.append(symbol, unavailableTitle, unavailableCopy);
      detail.append(unavailable);
      return;
    }

    const body = document.createElement("div");
    body.className = "viewer-product-detail__body";

    const readyAssets = snapshot.selectedTechnicalViewAssets.filter(
      asset => asset.status === "ready" && asset.svg !== null
    );
    if (readyAssets.length > 0) {
      if (!activeTechnicalViewId || !readyAssets.some(asset => asset.viewId === activeTechnicalViewId)) {
        activeTechnicalViewId = readyAssets.find(asset => asset.fidelity === "geometry-derived")?.viewId ?? readyAssets[0]!.viewId;
      }
      const gallery = document.createElement("section");
      gallery.className = "viewer-product-detail__gallery";
      const selector = document.createElement("div");
      selector.className = "viewer-product-detail__view-selector";
      selector.setAttribute("aria-label", "Vistas do módulo");
      for (const asset of readyAssets) {
        const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
        const option = button(request?.label ?? asset.viewId, "viewer-product-detail__view-button");
        option.dataset.technicalViewOption = asset.viewId;
        option.setAttribute("aria-pressed", asset.viewId === activeTechnicalViewId ? "true" : "false");
        option.addEventListener("click", () => {
          activeTechnicalViewId = asset.viewId;
          refresh();
        });
        selector.append(option);
      }
      const activeAsset = readyAssets.find(asset => asset.viewId === activeTechnicalViewId) ?? readyAssets[0]!;
      const figure = createTechnicalFigure(pkg, activeAsset);
      if (figure) gallery.append(selector, figure);
      body.append(gallery);
    }

    const cards = document.createElement("div");
    cards.className = "viewer-product-detail__cards";
    for (const card of [
      createSpecificationCard(pkg),
      createComponentsCard(pkg),
      createFinishesSummary(pkg),
      createDependencyCard(pkg),
      createNoticesCard(pkg)
    ]) {
      if (card) cards.append(card);
    }
    if (cards.childElementCount > 0) body.append(cards);

    const fidelityNotes = snapshot.selectedTechnicalViewAssets.filter(
      asset => asset.status === "ready" && (asset.omitted.length > 0 || asset.coverage.length > 0)
    );
    if (fidelityNotes.length > 0) {
      const disclosure = document.createElement("details");
      disclosure.className = "viewer-product-detail__evidence";
      const summary = document.createElement("summary");
      summary.textContent = "Cobertura das representações";
      const list = document.createElement("ul");
      for (const asset of fidelityNotes) {
        const request = pkg.technicalViews.find(candidate => candidate.id === asset.viewId);
        const item = document.createElement("li");
        const omissions = asset.omitted.length > 0 ? ` · omite: ${asset.omitted.join(", ")}` : "";
        item.textContent = `${request?.label ?? asset.viewId}: ${asset.coverage.join(", ") || "cobertura não declarada"}${omissions}`;
        list.append(item);
      }
      disclosure.append(summary, list);
      body.append(disclosure);
    }

    detail.append(body);
  }

  function refreshStepNav(): void {
    for (const step of STEPS) {
      const item = stepButtons.get(step.id)!;
      const active = step.id === currentStep;
      item.setAttribute("aria-current", active ? "step" : "false");
      item.dataset.active = active ? "true" : "false";
      item.dataset.visited = visitedSteps.has(step.id) ? "true" : "false";
    }
  }

  function refreshActions(): void {
    const index = STEPS.findIndex(step => step.id === currentStep);
    back.hidden = index === 0;
    next.hidden = index === STEPS.length - 1;
    if (!next.hidden) next.textContent = `Continuar para ${STEPS[index + 1]!.label.toLowerCase()} →`;
  }

  function refresh(): void {
    const snapshot = api.getSnapshot();
    if (snapshot.selectedModuleAlias !== lastSelectedAlias) {
      activeTechnicalViewId = null;
      if (snapshot.selectedModuleAlias !== null) detailExpanded = true;
      if (snapshot.selectedModuleAlias === null) detailExpanded = false;
      lastSelectedAlias = snapshot.selectedModuleAlias;
    }

    root.dataset.currentStep = currentStep;
    root.dataset.detailOpen = detailExpanded && snapshot.selectedModuleAlias !== null ? "true" : "false";
    root.dataset.moduleEditorOpen = moduleEditorExpanded ? "true" : "false";
    document.body.dataset.viewerCurrentStep = currentStep;
    document.body.dataset.viewerDetailOpen = root.dataset.detailOpen;
    document.body.dataset.viewerModuleEditorOpen = root.dataset.moduleEditorOpen;

    renderStage(snapshot);
    renderDetail(snapshot);
    renderModuleEditor(snapshot);
    refreshStepNav();
    refreshActions();
  }

  root.append(topbar, stagePanel, detail, moduleEditor, actions);
  host.append(root);
  refresh();

  return {
    refresh,
    dispose(): void {
      root.remove();
      document.body.classList.remove("viewer-product-ui");
      delete document.body.dataset.viewerCurrentStep;
      delete document.body.dataset.viewerDetailOpen;
      delete document.body.dataset.viewerModuleEditorOpen;
    }
  };
}

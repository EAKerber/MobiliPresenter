import type { TechnicalPresentationPackage, ViewerUiApi } from "../api/ui-contract.js";
import "./editorial-overrides.css";

export interface EditorialEnhancements {
  refresh(): void;
  dispose(): void;
}

type IconName =
  | "modules"
  | "colors"
  | "accessories"
  | "details"
  | "reset"
  | "specs"
  | "outlet"
  | "plug"
  | "cable"
  | "drawer"
  | "hinge"
  | "switch"
  | "hardware"
  | "panel"
  | "component"
  | "finish"
  | "installation";

const svg = (body: string): string =>
  `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;

const ICONS: Readonly<Record<IconName, string>> = {
  modules: svg('<rect x="3.5" y="3.5" width="7" height="7" rx="1"/><rect x="13.5" y="3.5" width="7" height="7" rx="1"/><rect x="3.5" y="13.5" width="7" height="7" rx="1"/><rect x="13.5" y="13.5" width="7" height="7" rx="1"/>'),
  colors: svg('<path d="M12 3.25c2.8 3.55 5.2 6.35 5.2 9.45A5.2 5.2 0 1 1 6.8 12.7C6.8 9.6 9.2 6.8 12 3.25Z"/><path d="M9.2 15.2c.65 1.05 1.55 1.55 2.8 1.55"/>'),
  accessories: svg('<path d="M5 8.5v7M19 8.5v7M5 12h14"/><circle cx="5" cy="7" r="1.5"/><circle cx="19" cy="7" r="1.5"/>'),
  details: svg('<path d="M6 3.5h9l3 3v14H6z"/><path d="M15 3.5v3h3M9 11h6M9 14.5h6M9 18h4"/>'),
  reset: svg('<path d="M5.2 8.2A7.2 7.2 0 1 1 4.9 15"/><path d="M5.2 4.8v3.4H1.8"/>'),
  specs: svg('<path d="M4 17.5 17.5 4 20 6.5 6.5 20 4 20Z"/><path d="m13.2 8.3 2.5 2.5M10.4 11.1l1.6 1.6M7.6 13.9l2.5 2.5"/>'),
  outlet: svg('<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M9 8v4M15 8v4M12 15v2"/>'),
  plug: svg('<path d="M8 3.5v5M16 3.5v5M6.5 8.5h11v2.2A5.5 5.5 0 0 1 12 16.2v4.3"/>'),
  cable: svg('<path d="M4 6.5h6.5c5.5 0 3 11 9.5 11M4 4.5v4M20 15.5v4"/>'),
  drawer: svg('<rect x="3.5" y="4" width="17" height="16" rx="1.5"/><path d="M3.5 9.3h17M3.5 14.7h17M9.5 6.7h5M9.5 12h5M9.5 17.3h5"/>'),
  hinge: svg('<rect x="3.5" y="4" width="6" height="16" rx="1"/><rect x="14.5" y="4" width="6" height="16" rx="1"/><path d="M9.5 8h5M9.5 16h5"/><circle cx="12" cy="12" r="1.5"/>'),
  switch: svg('<rect x="4" y="3" width="16" height="18" rx="3"/><rect x="8" y="7" width="8" height="7" rx="1.5"/><path d="M12 14v3"/>'),
  hardware: svg('<path d="m8 5 8 14M16 5 8 19"/><circle cx="8" cy="5" r="2"/><circle cx="16" cy="5" r="2"/>'),
  panel: svg('<path d="M5 5h14v14H5zM8 2.5h14v14"/>'),
  component: svg('<path d="m8 4-4 7 4 7h8l4-7-4-7Z"/><circle cx="12" cy="11" r="2.5"/>'),
  finish: svg('<path d="M12 3.2c2.7 3.5 5 6.2 5 9.2a5 5 0 1 1-10 0c0-3 2.3-5.7 5-9.2Z"/><path d="M8.7 17.2c1.7.9 4.1.8 5.8-.2"/>'),
  installation: svg('<path d="m14.5 5.5 4 4M13 7l4 4M6 18l8.2-8.2 2 2L8 20H4v-4Z"/>')
};

function setIcon(target: HTMLElement, icon: IconName): void {
  if (target.dataset.uiIcon === icon) return;
  target.dataset.uiIcon = icon;
  target.innerHTML = ICONS[icon];
  target.setAttribute("aria-hidden", "true");
}

function ensureSemanticIcon(parent: HTMLElement, icon: IconName): HTMLElement {
  let marker = Array.from(parent.children).find(child => child.classList.contains("viewer-semantic-icon")) as HTMLElement | undefined;
  if (!marker) {
    marker = document.createElement("span");
    marker.className = "viewer-semantic-icon";
    parent.prepend(marker);
  }
  setIcon(marker, icon);
  return marker;
}

function componentIcon(component: TechnicalPresentationPackage["components"][number]): IconName {
  switch (component.id) {
    case "module02/component/outlet-20a": return "outlet";
    case "module02/component/pp-cable": return "cable";
    case "module03/component/runner-h45": return "drawer";
    case "module03/component/damped-hinge": return "hinge";
    case "module04/interface/light-switch-fixing": return "switch";
  }

  switch (component.kind) {
    case "electrical": return "plug";
    case "hardware": return "hardware";
    case "panel": return "panel";
    case "interface": return "switch";
    default: return "component";
  }
}

function factIcon(category: TechnicalPresentationPackage["specifications"][number]["category"]): IconName {
  switch (category) {
    case "electrical": return "outlet";
    case "hardware": return "hardware";
    case "construction": return "panel";
    case "installation": return "installation";
    case "finish": return "finish";
    default: return "specs";
  }
}

function enhanceRail(host: HTMLElement): void {
  host.querySelector<HTMLElement>(".viewer-shell__mark")?.remove();

  for (const button of host.querySelectorAll<HTMLElement>(".viewer-shell__rail-button")) {
    const symbol = button.querySelector<HTMLElement>(".viewer-shell__rail-symbol");
    if (!symbol) continue;
    const page = button.dataset.sidebarPage;
    if (page === "modules" || page === "colors" || page === "accessories") {
      setIcon(symbol, page);
    } else if (button.classList.contains("viewer-shell__detail-toggle")) {
      setIcon(symbol, "details");
    } else if (button.classList.contains("viewer-shell__reset")) {
      setIcon(symbol, "reset");
    }
  }
}

function enhanceTechnicalLanguage(host: HTMLElement): void {
  const gallery = host.querySelector<HTMLElement>(".viewer-technical-gallery");
  if (!gallery) return;
  gallery.dataset.technicalFidelity = "schematic";

  const eyebrow = gallery.querySelector<HTMLElement>(".viewer-technical-gallery__eyebrow");
  if (eyebrow && eyebrow.textContent !== "ESQUEMA DIMENSIONAL") eyebrow.textContent = "ESQUEMA DIMENSIONAL";

  const heading = gallery.querySelector<HTMLElement>(".viewer-technical-gallery__heading");
  if (heading && !heading.querySelector(".viewer-technical-gallery__fidelity-note")) {
    const note = document.createElement("p");
    note.className = "viewer-technical-gallery__fidelity-note";
    note.textContent = "Representação dimensional esquemática.";
    heading.append(note);
  }
}

function enhanceTechnicalContent(host: HTMLElement, api: ViewerUiApi): void {
  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  if (!pkg) return;

  const information = host.querySelector<HTMLElement>(".viewer-technical-detail__information");
  if (!information) return;
  const cards = Array.from(information.querySelectorAll<HTMLElement>(":scope > .viewer-technical-card"));
  const specificationCard = cards[0];
  const componentCard = cards[1];
  const finishCard = cards[2];
  const noticeCard = cards[3];

  const specificationHeading = specificationCard?.querySelector<HTMLElement>(":scope > h3");
  if (specificationHeading) ensureSemanticIcon(specificationHeading, "specs");
  const componentHeading = componentCard?.querySelector<HTMLElement>(":scope > h3");
  if (componentHeading) ensureSemanticIcon(componentHeading, "hardware");
  const finishHeading = finishCard?.querySelector<HTMLElement>(":scope > h3");
  if (finishHeading) ensureSemanticIcon(finishHeading, "finish");
  const noticeHeading = noticeCard?.querySelector<HTMLElement>(":scope > h3");
  if (noticeHeading) ensureSemanticIcon(noticeHeading, "installation");

  const facts = pkg.specifications.filter(fact => fact.category !== "function");
  const factRows = specificationCard
    ? Array.from(specificationCard.querySelectorAll<HTMLElement>(".viewer-technical-card__list li"))
    : [];
  for (let index = 0; index < facts.length; index += 1) {
    const row = factRows[index];
    const fact = facts[index];
    if (!row || !fact) continue;
    row.dataset.factCategory = fact.category;
    ensureSemanticIcon(row, factIcon(fact.category));
  }

  const componentRows = componentCard
    ? Array.from(componentCard.querySelectorAll<HTMLElement>(".viewer-technical-card__stack-item"))
    : [];
  for (let index = 0; index < pkg.components.length; index += 1) {
    const row = componentRows[index];
    const component = pkg.components[index];
    if (!row || !component) continue;
    row.classList.add("viewer-technical-card__stack-item--icon");
    row.dataset.componentKind = component.kind;
    row.dataset.componentId = component.id;
    ensureSemanticIcon(row, componentIcon(component));
  }

  if (finishCard) {
    for (const row of finishCard.querySelectorAll<HTMLElement>(".viewer-technical-card__stack-item")) {
      row.classList.add("viewer-technical-card__stack-item--icon");
      ensureSemanticIcon(row, "finish");
    }
  }
}

export function mountEditorialEnhancements(host: HTMLElement, api: ViewerUiApi): EditorialEnhancements {
  let scheduled = false;

  const refresh = (): void => {
    scheduled = false;
    enhanceRail(host);
    enhanceTechnicalLanguage(host);
    enhanceTechnicalContent(host, api);
  };

  const schedule = (): void => {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(refresh);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(host, { childList: true, subtree: true });
  refresh();

  return {
    refresh,
    dispose(): void {
      observer.disconnect();
    }
  };
}

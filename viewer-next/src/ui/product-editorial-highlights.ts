import type { ViewerUiApi } from "../api/ui-contract.js";

export interface ProductEditorialHighlights {
  dispose(): void;
}

const MAX_HIGHLIGHTS = 2;

function renderHighlights(api: ViewerUiApi): void {
  const detail = document.querySelector<HTMLElement>(".viewer-product-detail[data-module-alias]");
  if (!detail || detail.hidden) return;

  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  if (!pkg) return;

  const facts = pkg.specifications
    .filter(fact => fact.category === "function")
    .slice(0, MAX_HIGHLIGHTS);

  const existing = detail.querySelector<HTMLElement>('[data-product-highlights="published-facts"]');
  if (facts.length === 0) {
    existing?.remove();
    return;
  }

  const signature = facts.map(fact => `${fact.id}:${fact.text}`).join("|");
  if (existing?.dataset.productHighlightsSignature === signature) return;

  const section = document.createElement("section");
  section.className = "viewer-product-detail__highlights";
  section.dataset.productHighlights = "published-facts";
  section.dataset.productHighlightsSignature = signature;

  const heading = document.createElement("h3");
  heading.textContent = "Destaques";

  const list = document.createElement("ul");
  for (const fact of facts) {
    const item = document.createElement("li");
    item.dataset.productHighlightFactId = fact.id;
    item.textContent = fact.text;
    list.append(item);
  }

  section.append(heading, list);
  const header = detail.querySelector<HTMLElement>(".viewer-product-detail__header");
  if (header) header.after(section);
  else detail.prepend(section);
  existing?.remove();
}

export function installProductEditorialHighlights(api: ViewerUiApi): ProductEditorialHighlights {
  let disposed = false;
  let scheduled = false;

  const decorate = (): void => {
    scheduled = false;
    if (disposed) return;
    renderHighlights(api);
  };

  const schedule = (): void => {
    if (disposed || scheduled) return;
    scheduled = true;
    queueMicrotask(decorate);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.body, { childList: true, subtree: true });
  decorate();

  return {
    dispose(): void {
      disposed = true;
      observer.disconnect();
    }
  };
}

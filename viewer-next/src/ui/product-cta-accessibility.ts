export interface ProductCtaAccessibility {
  dispose(): void;
}

const STYLE_ID = "viewer-product-cta-accessibility";
const WIDE_DESKTOP_QUERY = "(min-width: 1180px)";
const ACCESSIBLE_LABELS: Readonly<Record<string, string>> = {
  modules: "Continuar para acabamentos",
  finishes: "Continuar para acessórios",
  accessories: "Continuar para resumo"
};

const STYLE = `
.viewer-product-cta__sr-label {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
`;

export function installProductCtaAccessibility(): ProductCtaAccessibility {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = STYLE;
  document.head.append(style);

  const wideDesktop = matchMedia(WIDE_DESKTOP_QUERY);
  let frame: number | null = null;
  let disposed = false;

  const decorate = (): void => {
    frame = null;
    if (disposed || !wideDesktop.matches) return;
    const step = document.body.dataset.viewerCurrentStep;
    const label = step ? ACCESSIBLE_LABELS[step] : undefined;
    const button = document.querySelector<HTMLButtonElement>(".viewer-configurator__actions .viewer-button--primary");
    if (!button || button.hidden || !label) return;
    button.setAttribute("aria-label", label);
    let hidden = button.querySelector<HTMLElement>(".viewer-product-cta__sr-label");
    if (!hidden) {
      hidden = document.createElement("span");
      hidden.className = "viewer-product-cta__sr-label";
      button.prepend(hidden);
    }
    if (hidden.textContent !== label) hidden.textContent = label;
  };

  const schedule = (): void => {
    if (disposed || frame !== null) return;
    frame = requestAnimationFrame(decorate);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.body, { childList: true, subtree: true });
  wideDesktop.addEventListener("change", schedule);
  schedule();

  return {
    dispose(): void {
      disposed = true;
      observer.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
      wideDesktop.removeEventListener("change", schedule);
      style.remove();
    }
  };
}

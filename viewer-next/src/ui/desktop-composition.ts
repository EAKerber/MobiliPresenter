export interface DesktopCompositionEnhancement {
  dispose(): void;
}

const STYLE_ID = "viewer-desktop-composition-v1";

const DESKTOP_COMPOSITION_CSS = `
@media (min-width: 1180px) {
  html:root {
    --ui-stage-width: clamp(320px, 26vw, 400px);
    --ui-detail-width: clamp(350px, 30vw, 470px);
    --ui-detail-bottom-height: clamp(176px, 24vh, 232px);
    --ui-actions-height: 58px;
  }

  body.viewer-product-ui[data-viewer-detail-open="true"] #app {
    right: var(--ui-detail-width) !important;
    bottom: calc(var(--ui-actions-height) + var(--ui-detail-bottom-height)) !important;
  }

  body.viewer-product-ui .viewer-product-detail {
    top: var(--ui-topbar-height) !important;
    right: 0 !important;
    bottom: var(--ui-actions-height) !important;
    width: var(--ui-detail-width) !important;
    border: 0 !important;
    border-left: 1px solid var(--ui-border) !important;
    border-radius: 0 !important;
    box-shadow: -18px 0 44px rgba(35, 31, 28, .07) !important;
    overflow: hidden !important;
  }

  body.viewer-product-ui .viewer-product-detail__header {
    min-height: 88px;
    padding: 17px 20px 13px;
  }

  body.viewer-product-ui .viewer-product-detail__body {
    min-height: 0;
    overflow-y: auto;
    padding: 16px 18px 22px;
  }

  body.viewer-product-ui .viewer-product-detail__gallery {
    min-height: 0;
  }

  body.viewer-product-ui .viewer-product-detail__figure-media {
    min-height: clamp(260px, 38vh, 390px);
  }

  body.viewer-product-ui .viewer-product-detail__cards {
    position: fixed !important;
    z-index: 30014;
    left: var(--ui-stage-width) !important;
    right: var(--ui-detail-width) !important;
    bottom: var(--ui-actions-height) !important;
    height: var(--ui-detail-bottom-height) !important;
    display: flex !important;
    align-items: stretch;
    gap: 10px;
    margin: 0 !important;
    padding: 10px 12px !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    border-top: 1px solid var(--ui-border);
    border-right: 1px solid var(--ui-border);
    background: color-mix(in srgb, var(--ui-surface) 97%, transparent);
    box-shadow: 0 -12px 30px rgba(35, 31, 28, .05);
    backdrop-filter: blur(14px);
    scrollbar-gutter: stable;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card--wide {
    flex: 0 0 270px !important;
    min-width: 0;
    min-height: 0;
    margin: 0 !important;
    padding: 12px 14px;
    overflow: visible !important;
    border-radius: 12px;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="specifications"] {
    flex-basis: 420px !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="components"] {
    flex-basis: 320px !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="finishes"] {
    flex-basis: 240px !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="dependencies"],
  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="notices"] {
    flex-basis: 300px !important;
  }

  body.viewer-product-ui .viewer-configurator__actions {
    left: var(--ui-stage-width) !important;
    height: var(--ui-actions-height) !important;
    padding: 8px 16px !important;
    justify-content: flex-end;
    gap: 8px;
    border-top: 1px solid var(--ui-border);
    background: color-mix(in srgb, var(--ui-surface) 96%, transparent);
    box-shadow: 0 -8px 24px rgba(35, 31, 28, .04);
  }

  body.viewer-product-ui .viewer-configurator__actions::before {
    content: "Etapa 1 de 4 · Módulos";
    margin-right: auto;
    color: var(--ui-text-muted);
    font-size: 11px;
    font-weight: 650;
    letter-spacing: .01em;
  }

  body.viewer-product-ui[data-viewer-current-step="finishes"] .viewer-configurator__actions::before {
    content: "Etapa 2 de 4 · Acabamentos";
  }

  body.viewer-product-ui[data-viewer-current-step="accessories"] .viewer-configurator__actions::before {
    content: "Etapa 3 de 4 · Acessórios";
  }

  body.viewer-product-ui[data-viewer-current-step="summary"] .viewer-configurator__actions::before {
    content: "Etapa 4 de 4 · Resumo";
  }

  body.viewer-product-ui .viewer-configurator__actions .viewer-button {
    min-height: 38px;
    width: auto !important;
    min-width: 0 !important;
    padding: 8px 13px;
    border-radius: 8px;
    white-space: nowrap;
  }

  body.viewer-product-ui .viewer-configurator__actions .viewer-button--primary {
    padding-inline: 15px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card {
    cursor: pointer;
  }
}

@media (min-width: 1180px) and (max-height: 760px) {
  html:root {
    --ui-detail-bottom-height: 164px;
    --ui-actions-height: 54px;
  }

  body.viewer-product-ui .viewer-product-detail__figure-media {
    min-height: 220px;
  }
}
`;

function isInteractiveTarget(target: Element): boolean {
  return target.closest("button, input, label, a, select, textarea") !== null;
}

function moduleCardFromTarget(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null;
  const card = target.closest<HTMLElement>(".viewer-stage--modules .viewer-module-card");
  if (!card || !card.closest(".viewer-configurator__stage-content")) return null;
  return card;
}

function openCardDetail(card: HTMLElement): void {
  const inspect = card.querySelector<HTMLButtonElement>(".viewer-module-card__inspect");
  inspect?.click();
}

export function installDesktopCompositionEnhancement(): DesktopCompositionEnhancement {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = DESKTOP_COMPOSITION_CSS;
  document.head.append(style);

  const onClick = (event: MouseEvent): void => {
    const card = moduleCardFromTarget(event.target);
    if (!card || !(event.target instanceof Element) || isInteractiveTarget(event.target)) return;
    openCardDetail(card);
  };

  document.addEventListener("click", onClick);

  return {
    dispose(): void {
      document.removeEventListener("click", onClick);
      style.remove();
    }
  };
}

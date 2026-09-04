# Netlify Product UI 0.1

Status: implementation slice on `work/ui/netlify-guided-configurator-current`

## Objective

Make the current Guided Configurator usable as the default product experience on Netlify without changing domain authority, camera behavior, Technical Presentation semantics, or the four-stage flow.

The product flow remains:

1. `Módulos`
2. `Acabamentos`
3. `Acessórios`
4. `Resumo`

The scene remains persistent and the fixed PresentationFrame remains authoritative for framing.

## Netlify activation

Netlify builds set:

```text
VITE_DEFAULT_UI_MODE=product
```

`viewer-next/src/bootstrap.ts` resolves the effective UI mode as follows:

- `?fidelity=1` -> renderer/fidelity mode, product UI disabled;
- `?controls=0` -> explicit renderer-only mode;
- `?controls=1` -> explicit product UI mode;
- otherwise -> use the build default; Netlify uses `product`, local/CI builds remain renderer-only unless explicitly enabled.

This preserves existing fidelity/browser baselines while making a Netlify branch deploy immediately usable without a special query string.

## Presentation refinement

`product-presentation.css` is a UI-only finishing layer over the integrated Guided Configurator and Responsive Fixed-Frame rules. It does not change scene framing or camera state. It:

- removes the persistent success-status strip while preserving errors;
- slightly increases product/readability emphasis in module cards and stage copy;
- keeps the editorial product-detail surface prominent on desktop;
- gives the mobile scene a little more vertical room while preserving the Responsive Fixed-Frame allocation contract;
- keeps reduced-motion behavior and the existing responsive modes intact.

## Honest unavailable states

This slice does not create missing domain capability. In particular:

- generic configurable accessories remain dependent on the public contract;
- module thumbnails/editorial metadata are not inferred from renderer pixels;
- technical packages that are unavailable remain unavailable;
- no commercial price is invented.

## Gates

The slice should preserve all existing Viewer Next gates and additionally prove:

- Netlify configuration declares `VITE_DEFAULT_UI_MODE = "product"`;
- bootstrap keeps explicit `controls=0`, `controls=1`, and `fidelity=1` overrides;
- the product presentation stylesheet is loaded by the application shell;
- the internal project codename remains absent from product-facing UI source;
- `1366x768`, `1024x768`, `768x1024`, and `390x844` Responsive Fixed-Frame evidence remains green.

## Non-goals

- no change to ProjectState or publication authority;
- no merge to `main` in this slice;
- no new accessories/catalog schema;
- no price or quote backend;
- no camera pan, zoom, focus or heuristic reframe;
- no changes to Scene Core, renderer, runtime state, TPC compiler or technical facts.

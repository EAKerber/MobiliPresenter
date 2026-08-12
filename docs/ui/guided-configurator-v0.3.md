# Guided Configurator UI 0.3

Status: implementation slice / human UX gate pending

## Objective

Replace the previous parallel `Módulos / Cores / Acessórios` navigation model with the approved guided configuration architecture while preserving the fixed-camera viewer and the UI × API ownership boundary.

The scene remains persistent. The flow progresses around it.

## Canonical flow

1. **Módulos** — define which modules belong to the composition. Visibility/inclusion remains a checkbox operation and is independent from inspection/focus.
2. **Acabamentos** — configure published finish policies and existing viewer finish controls.
3. **Acessórios** — host only real configurable product choices when they are published by the public contract. Requirements/specifications/dependencies must not be promoted to choices by UI heuristics.
4. **Resumo** — consolidate current modules and configuration. Commercial value/action remains absent or explicitly unavailable until an authoritative source exists.

The step navigation is both progress indicator and global navigation. `Voltar / Continuar` provides the linear path; direct step navigation allows review without resetting state.

## Persistent scene

The renderer remains visible through all four stages. UI may allocate viewport area but must not implement camera changes, free pan, focus-to-module or heuristic zoom. Responsive camera/frame behavior remains a shared contract dependency.

## Modules

- checkbox = inclusion/visibility only;
- inspection/focus is a separate target;
- module details are contextual, not a fifth step;
- modules remain editable from Acabamentos, Acessórios and Resumo through an explicit `N módulos · Editar` shortcut;
- editing modules must preserve compatible state and must not silently fabricate or erase domain information.

## Module detail

### Mobile

Contextual bottom sheet over the configurator, preserving the scene above/behind it.

### Desktop

A large editorial/product surface that shares the screen with the scene and acts as a point-of-sale presentation rather than an enlarged drawer.

The detail is data-driven. Blocks are materialized only when supported by the selected module package:

- identity;
- dimensions;
- technical views;
- specifications;
- components;
- dependencies;
- notices;
- current finishes.

A selected module with unavailable TPC must remain selectable and show an honest unavailable state using `ViewerUiContract 0.1.1`; no catch/hardcode or inferred facts in `src/ui/**`.

## Technical view fidelity

`TechnicalDiagramAsset.fidelity` controls presentation semantics:

- `geometry-derived` → technical view with geometry-traceable coverage;
- `schematic` → explicitly labelled schematic/dimensional representation;
- `external-required` → unavailable asset state, never reconstructed by UI.

`coverage` and `omitted` are presentation evidence and must not be hidden when their omission materially affects interpretation.

## Accessories boundary

The current public contract does not yet expose a generic product-option catalog. Therefore this slice implements the **stage and empty/unavailable state**, not a parallel accessory catalog.

Presentation-light presets are not reclassified as commercial accessories.

The future contract must let UI distinguish `choice` from `specification`, `component`, `dependency`, `notice` and other semantic roles without parsing free text. This dependency remains tracked in issue #22.

## Responsive composition

Desktop target gate: 1366×768.

Mobile target gate: 390×844.

The same information architecture is preserved across both viewports, but geometry differs:

- desktop: persistent left stage panel, dominant scene, contextual product surface on the right when focused;
- mobile: scene upper region, guided stage panel below, contextual product detail as sheet.

## Reuse from promotional-detail-v0.2

Selective concepts may be ported when still valid:

- flat editorial controls;
- restrained warm-neutral palette;
- semantic technical icon language;
- selection independent from detail expansion;
- one dominant technical view plus compact selector;
- disclosures before nested scroll;
- no user-visible internal codename/brand.

The old rail/page architecture is superseded by the four-stage flow.

## Gates

Structural:

- four navigable steps;
- `aria-current` on the active step;
- visibility checkbox independent from inspection;
- module editor reachable from later stages;
- closing detail preserves selected module;
- valid module without TPC renders an unavailable state;
- technical fidelity labels follow the public asset contract;
- no UI-owned domain catalogs or inferred technical/commercial facts.

Visual evidence:

- desktop modules / no focus;
- desktop module detail;
- desktop finishes;
- mobile modules;
- mobile module detail;
- mobile finishes.

All existing Viewer Next/Fidelity gates must remain green.

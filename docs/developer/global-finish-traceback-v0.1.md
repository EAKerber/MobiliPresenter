# Global Furniture Finish Traceback v0.1

## Status

`CONFIRMED:LEGACY_FRONT_QUERY_LOCAL_OVERRIDES_SHADOW_GLOBAL_FINISH`

This slice is diagnostic only. It does not change finish behavior, precedence, URL parsing, renderer synchronization, Scene Core, or production publication.

## Symptom

In an affected browser session:

1. choosing a global MDF finish changes the control state but the furniture can remain visually neutral;
2. clicking `Restaurar` makes subsequent global finish selection work;
3. the defect appeared historically around the work that corrected module 03 diverging from the intended neutral furniture color.

A clean `?controls=1` CI session does not reproduce the symptom.

## Historical traceback

The causal transition is the move from per-module compatibility state to the first-class global furniture-finish contract.

### 1. Historical neutral bootstrap bridge

Commit `659394b8617e906e4fa552f0a8b8771bc4f91e73`
(`ui: seed neutral global finish before viewer boot`) implemented the neutral product default by writing this shape into the browser URL before viewer bootstrap:

```text
front=01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige,07:neutral-greige
```

It used `window.history.replaceState`, so the compatibility state became part of the live tab URL.

### 2. First-class global finish introduced later

PR #220 subsequently introduced `furnitureFinishPresetId` and changed product UI selection to call `setFurnitureFinishPreset`.

The bootstrap bridge was removed in commit
`476406594ec4f1ab4376029ad6dc8942567036ad`
(`refactor(ui): remove neutral finish bootstrap bridge`).

Removing the writer did not remove the legacy URL reader.

### 3. Current query parser still materializes legacy local overrides

`parseViewerConfiguration()` still accepts `front=` and translates each assignment into `set-front-preset`, populating `frontPresetByModule`.

### 4. Current precedence makes local overrides stronger than global finish

`deriveViewerAppearance()` applies:

```text
global furniture finish
        ↓
frontPresetByModule overrides
```

Therefore an old all-neutral `front=` query shadows a later `warm-wood` global selection.

### 5. Reset clears state but does not migrate the URL

`reset-configuration` returns `createDefaultViewerConfiguration()`, which clears `frontPresetByModule`.

The browser trace confirms:

```text
legacy URL load
  -> local neutral overrides exist
  -> global warm selection changes global state
  -> local neutral overrides still win
  -> Restaurar clears local overrides in memory
  -> global warm selection now works
  -> URL still contains front=
  -> reload materializes the legacy overrides again
```

## Confirmed evidence

PR #229 executed the traceback against the current viewer without changing runtime behavior.

All three workflows completed successfully:

- `Coordination Guard`
- `Viewer Next`
- `Product UI Evidence`

The clean global-finish smoke passed first, proving the first-class global path itself remains healthy on a clean URL.

The dedicated browser traceback then returned:

```text
status = PASS
classification = KNOWN_BUG_REPRODUCED
hypothesis = legacy-front-query-local-overrides-shadow-global-finish
```

Observed states:

```text
legacy-load
  finish = neutral-greige
  module03 = front-primary

legacy-first-warm
  finish = warm-wood
  module03 = front-primary

after-reset
  finish = neutral-greige
  module03 = front-primary

warm-after-reset
  finish = warm-wood
  module03 = front-wood

reload-from-legacy-url
  finish = neutral-greige
  module03 = front-primary

warm-after-reload
  finish = warm-wood
  module03 = front-primary
```

The emitted signature was fully true:

```text
firstClickChangesGlobalStateButNotModule03 = true
resetClearsInMemoryShadowing = true
legacyUrlSurvivesReset = true
reloadRestoresShadowing = true
```

Artifact:

```text
product-ui-evidence
artifact id = 9814965406
digest = sha256:f089d58ecb9cee6491609f9d2313cf86a8eccf0ad7211cebfa7bdd15a16ece1b
viewer-next/artifacts/global-finish-traceback/trace.json
```

This closes the causal chain. The defect is not renderer synchronization or click ownership. It is stale compatibility state with stronger precedence than the global contract.

## Why the previous gate could pass

`global_finish_browser_smoke.mjs` starts from a clean `?controls=1` URL. It therefore proves the first-class global path on clean state, but does not exercise compatibility state left by the historical `front=` bridge.

The earlier diagnosis focused on DOM readiness and click ownership. Those were real integration debts, but a clean URL could not falsify this legacy-state mechanism.

## Correction contract

The correction must be a separate slice.

Required migration semantics:

- an all-modules-equal legacy `front=` query is compatibility state representing the old global bridge and must collapse into `furnitureFinishPresetId`;
- intentional partial `front=` assignments retain local-override meaning;
- mixed per-module assignments retain local-override meaning;
- migrated uniform compatibility state must be removed from the live URL so reload cannot resurrect it;
- clean URL, uniform legacy URL, partial override URL, mixed override URL, reset, and reload each require explicit gates.

No renderer, Scene Core geometry, material definitions, or module-specific finish precedence should be changed to solve this defect.

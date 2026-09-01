# Global Furniture Finish Traceback v0.1

## Status

`HYPOTHESIS_UNDER_TEST`

This slice is diagnostic only. It does not change finish behavior, precedence, URL parsing, renderer synchronization, Scene Core, or production publication.

## Symptom

In an affected browser session:

1. choosing a global MDF finish changes the control state but the furniture can remain visually neutral;
2. clicking `Restaurar` makes subsequent global finish selection work;
3. the defect appeared historically around the work that corrected module 03 diverging from the intended neutral furniture color.

A clean `?controls=1` CI session does not reproduce the symptom.

## Historical traceback

The strongest causal candidate is the transition from per-module compatibility state to the first-class global furniture-finish contract.

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

Therefore an old all-neutral `front=` query can shadow a later `warm-wood` global selection.

### 5. Reset clears state but does not migrate the URL

`reset-configuration` returns `createDefaultViewerConfiguration()`, which clears `frontPresetByModule`.

This predicts the reported behavior:

```text
legacy URL load
  -> local neutral overrides exist
  -> global warm selection changes global state
  -> local neutral overrides still win
  -> Restaurar clears local overrides in memory
  -> global warm selection now works
```

Because reset does not rewrite the query string, reload should materialize the legacy overrides again.

## Falsifiable signature

The hypothesis is considered confirmed only if both layers reproduce the same chain.

### State-level trace

Given the exact historical all-module `front=` query:

- parsed `furnitureFinishPresetId` is `neutral-greige`;
- `frontPresetByModule` contains seven neutral overrides;
- setting global `warm-wood` leaves module 03 resolved as `front-primary`;
- reset empties `frontPresetByModule`;
- setting global `warm-wood` after reset resolves module 03 as `front-wood`.

### Browser trace

Using a real Chrome against the current viewer:

1. load the exact legacy URL;
2. first warm selection:
   - global finish becomes `warm-wood`;
   - module 03 remains `front-primary`;
3. click `Restaurar`;
4. the URL must still contain `front=`;
5. warm selection now resolves module 03 to `front-wood`;
6. reload the same URL;
7. warm selection is shadowed again and module 03 remains `front-primary`.

The browser trace writes:

```text
viewer-next/artifacts/global-finish-traceback/trace.json
```

## Why the previous gate could pass

`global_finish_browser_smoke.mjs` starts from a clean `?controls=1` URL. It therefore proves the first-class global path on clean state, but does not exercise compatibility state left by the historical `front=` bridge.

The earlier diagnosis focused on DOM readiness and click ownership. Those were real integration debts, but a clean URL cannot falsify this legacy-state hypothesis.

## Next decision

Do not implement migration in this slice.

If the state and browser traces both reproduce the signature, classify the root cause as:

`CONFIRMED:LEGACY_FRONT_QUERY_LOCAL_OVERRIDES_SHADOW_GLOBAL_FINISH`

A separate correction slice should then define migration semantics carefully:

- an all-modules-equal legacy `front=` query can be collapsed into `furnitureFinishPresetId`;
- intentional partial/per-module `front=` assignments must retain their local-override meaning;
- migrated compatibility state should not survive invisibly in the URL;
- clean URL, legacy uniform URL, partial override URL, reset, and reload each need explicit gates.

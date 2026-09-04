# Product UI polish v0.3 — readback

Status: branch-local UI checkpoint on `work/ui/netlify-guided-configurator-current`.

## UI-owned work completed

- Wider desktop module rail is enforced by `responsive-allocation.css` with specificity above the base runtime tokens.
- Desktop module detail remains split between the right technical surface and the lower factual surface.
- Lower factual surface owns its scroll; semantic cards no longer create nested scrollbars on wide desktop.
- Product scrollbars are styled consistently across stage/detail/editor surfaces.
- Typography hierarchy was refined without adding CDN/font-file dependencies; technical dimensions use tabular numerals.
- Semantic iconography is generated only from already-published TPC categories/kinds (`function`, `construction`, `installation`, `finish`, `hardware`, `electrical`, component kinds, dependency, notice severity). No text-content inference was added.
- Technical SVGs keep their published geometry/fidelity. UI treatment improves line hierarchy, openings, backgrounds, dimension-label readability and isometric W/H/D dimensions without recomputing technical facts.
- Product startup seeds the existing `front` query with `neutral-greige` for all seven modules **before viewer bootstrap**, only when product mode is active and the caller did not provide an explicit `front` query. This replaces the rejected seven-runtime-write startup bridge and avoids repeated material syncs.

## Readback

Head represented by this note: `6048383c77a7eea300ba6822798ab989ed0042b1` plus this documentation commit.

Observed gates on `6048383…`:

- Coordination Guard: PASS.
- Module Thumbnails: PASS.
- Product UI Evidence: PASS, including responsive captures and real stage navigation.
- Netlify branch deploy: `ready` on exact commit `6048383…`.
- Viewer Next: verify/build PASS; full WebGL/fidelity/readability suite was still running at the time this note was written and must be read back before treating this head as fully validated.

Visual readback confirms:

- left rail width is materially increased at 1366×768;
- the no-explicit-front product scenario opens with all cabinet fronts neutral/gray;
- the lower factual strip no longer nests scrollbars inside each card;
- semantic icons and technical drawing styling are visible but restrained.

## Deliberately waiting on Developer contract

The requested promotional **module view with its associated appliances/items** is intentionally not inferred by UI. The real-renderer isolation/crop pipeline already exists, but UI requires an authoritative module → companion-entities relation. This is tracked in Developer handoff PR #215 (`docs/ui/developer-ui-contract-needs-v0.2.md`).

When that relation is available, the expected implementation is:

1. isolate module + declared companion entities in the current viewer renderer;
2. preserve current material/lighting/camera policy;
3. capture/crop using the existing renderer-derived tooling;
4. expose the resulting visual in module details without creating a second renderer or guessing spatial relationships.

## Remaining UI-owned opportunities

Further layout/icon polish can continue, but should not encode domain-specific semantic guesses. In particular, a specific outlet/tomada glyph should wait for a semantic key if it must be distinguished from generic electrical content.

"""Temporary branch-local repair helper for post-integration semantic coverage.

This module intentionally exposes no CLI entrypoint. It is invoked only by the
exact branch-scoped Agent Ops scaffold and is removed after the registry patch
is materialized and validated.
"""
from __future__ import annotations

import json

from tools.semantics.coverage import build_inspection
from tools.semantics.registry import REGISTRY_PATH, load_registry, validate_registry

TARGETS = {
    ".github/workflows/module-thumbnails.yml": {
        "owner": "operations-core",
        "reason": "Product-domain CI is outside the operational tool-surface map.",
        "deathCondition": "Remove when Module Thumbnails CI becomes an explicit operational capability surface.",
    },
    ".github/workflows/product-ui-evidence.yml": {
        "owner": "operations-core",
        "reason": "Product-domain CI is outside the operational tool-surface map.",
        "deathCondition": "Remove when Product UI Evidence CI becomes an explicit operational capability surface.",
    },
}


def apply() -> bool:
    registry = load_registry()
    exclusions = registry["coveragePolicy"]["exclusions"]
    existing = {item["path"] for item in exclusions}
    changed = False
    for path, metadata in TARGETS.items():
        if path in existing:
            continue
        exclusions.append({"path": path, **metadata})
        changed = True
    exclusions.sort(key=lambda item: item["path"])

    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(f"SEMANTIC_REGISTRY_INVALID:{errors[0]}")
    inspection = build_inspection(registry)
    if inspection["coverageComplete"] is not True:
        raise RuntimeError(
            "SEMANTIC_COVERAGE_STILL_INCOMPLETE:"
            + json.dumps(inspection["findings"], sort_keys=True, separators=(",", ":"))
        )

    if changed:
        REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed

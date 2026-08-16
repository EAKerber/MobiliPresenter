from __future__ import annotations

ARTIFACT_KINDS = frozenset({
    "inspection",
    "recommendation",
    "routing-plan",
    "transition-plan",
    "sanitization-plan",
    "receipt",
})


def require_artifact_kind(value: str) -> str:
    if value not in ARTIFACT_KINDS:
        raise RuntimeError("SEMANTIC_ARTIFACT_KIND_INVALID")
    return value

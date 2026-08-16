from __future__ import annotations

import re
from typing import Any

from tools.semantics.registry import load_registry, validate_registry

_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


def _registry_grammar() -> dict[str, Any]:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(errors[0])
    return registry["branchGrammar"]


def parse_branch_name(name: str) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise RuntimeError("BRANCH_NAME_INVALID")
    grammar = _registry_grammar()
    if name in set(grammar["controlBranches"]):
        return {
            "name": name,
            "grammar": "canonical",
            "namespace": None,
            "declaredClass": "control",
            "domain": None,
            "slug": name,
        }

    parts = name.split("/")
    if any(not part or not _SEGMENT_RE.fullmatch(part) for part in parts):
        raise RuntimeError("BRANCH_NAME_INVALID")

    if len(parts) == 3 and parts[0] in set(grammar["canonical"]):
        return {
            "name": name,
            "grammar": "canonical",
            "namespace": parts[0],
            "declaredClass": parts[0],
            "domain": parts[1],
            "slug": parts[2],
        }

    namespace = parts[0] if len(parts) > 1 else None
    known_legacy = namespace in set(grammar["legacyNamespaces"]) if namespace is not None else False
    return {
        "name": name,
        "grammar": "legacy" if known_legacy else "legacy-unknown",
        "namespace": namespace,
        "declaredClass": None,
        "domain": None,
        "slug": None,
    }

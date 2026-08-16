from __future__ import annotations

import re
from typing import Any

from tools.semantics.registry import load_registry

_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


def _registry_grammar() -> dict[str, Any]:
    registry = load_registry()
    grammar = registry.get("branchGrammar")
    if not isinstance(grammar, dict) or set(grammar) != {"controlBranches", "canonical", "legacyNamespaces"}:
        raise RuntimeError("SEMANTIC_BRANCH_GRAMMAR_INVALID")
    controls = grammar.get("controlBranches")
    legacy = grammar.get("legacyNamespaces")
    canonical = grammar.get("canonical")
    if not isinstance(controls, list) or not controls or any(not isinstance(item, str) or not item for item in controls) or len(controls) != len(set(controls)):
        raise RuntimeError("SEMANTIC_CONTROL_BRANCHES_INVALID")
    if not isinstance(legacy, list) or any(not isinstance(item, str) or not item for item in legacy) or len(legacy) != len(set(legacy)):
        raise RuntimeError("SEMANTIC_LEGACY_NAMESPACES_INVALID")
    if not isinstance(canonical, dict) or set(canonical) != {"authority", "experiment", "work"}:
        raise RuntimeError("SEMANTIC_CANONICAL_BRANCHES_INVALID")
    return grammar


def _semantic_domain(term: str, *, legacy: bool) -> tuple[str | None, bool]:
    if not term:
        return None, False
    registry = load_registry()
    for item in registry.get("concepts", {}).values():
        if not isinstance(item, dict) or item.get("kind") != "branch-domain":
            continue
        if item.get("term") == term:
            return str(item["term"]), False
        if legacy:
            for alias in item.get("aliases", []):
                if isinstance(alias, dict) and alias.get("scope") == "legacy-branch-namespace" and alias.get("term") == term:
                    return str(item.get("term")), True
    return None, False


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
            "semanticDomain": None,
            "legacyAlias": False,
            "slug": name,
        }

    parts = name.split("/")
    if any(not part or not _SEGMENT_RE.fullmatch(part) for part in parts):
        raise RuntimeError("BRANCH_NAME_INVALID")

    if len(parts) == 3 and parts[0] in set(grammar["canonical"]):
        semantic_domain, legacy_alias = _semantic_domain(parts[1], legacy=False)
        return {
            "name": name,
            "grammar": "canonical",
            "namespace": parts[0],
            "declaredClass": parts[0],
            "domain": parts[1],
            "semanticDomain": semantic_domain,
            "legacyAlias": legacy_alias,
            "slug": parts[2],
        }

    namespace = parts[0] if len(parts) > 1 else None
    known_legacy = namespace in set(grammar["legacyNamespaces"]) if namespace is not None else False
    semantic_domain, legacy_alias = _semantic_domain(namespace or "", legacy=True) if known_legacy else (None, False)
    return {
        "name": name,
        "grammar": "legacy" if known_legacy else "legacy-unknown",
        "namespace": namespace,
        "declaredClass": None,
        "domain": None,
        "semanticDomain": semantic_domain,
        "legacyAlias": legacy_alias,
        "slug": None,
    }

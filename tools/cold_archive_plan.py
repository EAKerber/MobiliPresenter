#!/usr/bin/env python3
"""Deterministic plan-only contract for Git cold-archive anchors.

A ColdArchivePlan never performs Git mutations and never authorizes them. It
binds exact source branch heads to one synthetic archive commit shape so an
executor can create an auditable multi-parent anchor and verify it by readback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import canonical_json, stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
SCHEMA_VERSION = "ColdArchivePlan 0.1"
INDEX_SCHEMA_VERSION = "ColdArchiveIndex 0.1"
DEFAULT_ARCHIVE_BRANCH = "archive/cold"
DEFAULT_CONTROL_BRANCH = "main"
DEFAULT_INDEX_PATH = "COLD_ARCHIVE.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SOURCE_FIELDS = {"branch", "headSha", "classification", "evidencePath"}
PLAN_FIELDS = {
    "schemaVersion",
    "repository",
    "controlBranch",
    "controlSha",
    "archiveBranch",
    "previousArchiveHead",
    "sources",
    "parentShas",
    "indexPath",
    "indexSha256",
    "readback",
    "authorizesMutation",
    "planHash",
}


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _normalize_sources(
    sources: Any,
    *,
    control_branch: str,
    archive_branch: str,
) -> list[dict[str, str]]:
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("COLD_ARCHIVE_SOURCES_REQUIRED")

    normalized: list[dict[str, str]] = []
    seen_branches: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict) or set(raw) != SOURCE_FIELDS:
            raise RuntimeError("COLD_ARCHIVE_SOURCE_FIELDS_INVALID")
        branch = _nonempty(raw.get("branch"), "COLD_ARCHIVE_SOURCE_BRANCH_INVALID")
        if branch in {control_branch, archive_branch}:
            raise RuntimeError(f"COLD_ARCHIVE_SOURCE_FORBIDDEN:{branch}")
        if branch in seen_branches:
            raise RuntimeError(f"COLD_ARCHIVE_SOURCE_DUPLICATE:{branch}")
        seen_branches.add(branch)
        normalized.append(
            {
                "branch": branch,
                "headSha": _sha(raw.get("headSha"), "COLD_ARCHIVE_SOURCE_SHA_INVALID"),
                "classification": _nonempty(
                    raw.get("classification"), "COLD_ARCHIVE_SOURCE_CLASSIFICATION_INVALID"
                ),
                "evidencePath": _nonempty(
                    raw.get("evidencePath"), "COLD_ARCHIVE_SOURCE_EVIDENCE_INVALID"
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["branch"])


def _index(
    *,
    archive_branch: str,
    control_sha: str,
    sources: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "archiveBranch": archive_branch,
        "controlSha": control_sha,
        "entries": sources,
    }


def render_index(plan: dict[str, Any]) -> str:
    validate_plan(plan)
    value = _index(
        archive_branch=plan["archiveBranch"],
        control_sha=plan["controlSha"],
        sources=plan["sources"],
    )
    return canonical_json(value) + "\n"


def build_plan(
    *,
    control_sha: str,
    sources: Any,
    previous_archive_head: str | None = None,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    archive_branch: str = DEFAULT_ARCHIVE_BRANCH,
    index_path: str = DEFAULT_INDEX_PATH,
) -> dict[str, Any]:
    control_branch = _nonempty(control_branch, "COLD_ARCHIVE_CONTROL_BRANCH_INVALID")
    archive_branch = _nonempty(archive_branch, "COLD_ARCHIVE_BRANCH_INVALID")
    if archive_branch == control_branch:
        raise RuntimeError("COLD_ARCHIVE_BRANCH_COLLIDES_WITH_CONTROL")
    control_sha = _sha(control_sha, "COLD_ARCHIVE_CONTROL_SHA_INVALID")
    if previous_archive_head is not None:
        previous_archive_head = _sha(
            previous_archive_head, "COLD_ARCHIVE_PREVIOUS_HEAD_INVALID"
        )
    index_path = _nonempty(index_path, "COLD_ARCHIVE_INDEX_PATH_INVALID")
    if index_path.startswith("/") or index_path.endswith("/") or ".." in index_path.split("/"):
        raise RuntimeError("COLD_ARCHIVE_INDEX_PATH_INVALID")

    normalized = _normalize_sources(
        sources,
        control_branch=control_branch,
        archive_branch=archive_branch,
    )

    parent_shas: list[str] = []
    if previous_archive_head is not None:
        parent_shas.append(previous_archive_head)
    for source in normalized:
        sha = source["headSha"]
        if sha not in parent_shas:
            parent_shas.append(sha)

    index_value = _index(
        archive_branch=archive_branch,
        control_sha=control_sha,
        sources=normalized,
    )
    index_content = canonical_json(index_value) + "\n"
    index_sha256 = hashlib.sha256(index_content.encode("utf-8")).hexdigest()

    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": REPOSITORY,
        "controlBranch": control_branch,
        "controlSha": control_sha,
        "archiveBranch": archive_branch,
        "previousArchiveHead": previous_archive_head,
        "sources": normalized,
        "parentShas": parent_shas,
        "indexPath": index_path,
        "indexSha256": index_sha256,
        "readback": {
            "kind": "cold-archive-anchor",
            "branch": archive_branch,
            "expectedParents": parent_shas,
            "indexPath": index_path,
            "expectedIndexSha256": index_sha256,
        },
        "authorizesMutation": False,
    }
    return {**body, "planHash": stable_hash(body)}


def validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS:
        raise RuntimeError("COLD_ARCHIVE_PLAN_FIELDS_INVALID")
    if plan.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("COLD_ARCHIVE_PLAN_SCHEMA_UNSUPPORTED")
    if plan.get("repository") != REPOSITORY:
        raise RuntimeError("COLD_ARCHIVE_REPOSITORY_INVALID")
    if plan.get("authorizesMutation") is not False:
        raise RuntimeError("COLD_ARCHIVE_PLAN_MUST_NOT_AUTHORIZE_MUTATION")

    rebuilt = build_plan(
        control_sha=plan.get("controlSha"),
        sources=plan.get("sources"),
        previous_archive_head=plan.get("previousArchiveHead"),
        control_branch=plan.get("controlBranch"),
        archive_branch=plan.get("archiveBranch"),
        index_path=plan.get("indexPath"),
    )
    if plan != rebuilt:
        raise RuntimeError("COLD_ARCHIVE_PLAN_MISMATCH")
    return plan


def _load_sources(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"COLD_ARCHIVE_SOURCES_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"COLD_ARCHIVE_SOURCES_JSON_INVALID:{path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one deterministic cold-archive anchor plan")
    parser.add_argument("--control-sha", required=True)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--previous-archive-head")
    parser.add_argument("--archive-branch", default=DEFAULT_ARCHIVE_BRANCH)
    parser.add_argument("--control-branch", default=DEFAULT_CONTROL_BRANCH)
    parser.add_argument("--index-path", default=DEFAULT_INDEX_PATH)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        plan = build_plan(
            control_sha=args.control_sha,
            sources=_load_sources(args.sources),
            previous_archive_head=args.previous_archive_head,
            archive_branch=args.archive_branch,
            control_branch=args.control_branch,
            index_path=args.index_path,
        )
        validate_plan(plan)
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}")
        return 2

    if args.as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print("COLD ARCHIVE PLAN 0.1")
        print(f"  archive: {plan['archiveBranch']}")
        print(f"  sources: {len(plan['sources'])}")
        print(f"  parents: {len(plan['parentShas'])}")
        print(f"  planHash: {plan['planHash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

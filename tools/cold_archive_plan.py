#!/usr/bin/env python3
"""Deterministic plan-only contract for Git cold-archive anchors.

ColdArchivePlan 0.2 preserves a cumulative index. The plan never performs Git
mutations and never authorizes them. It binds exact source branch heads and the
previous cumulative archive projection to one synthetic archive commit shape so
an executor can create an auditable anchor and verify it by readback.
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
SCHEMA_VERSION = "ColdArchivePlan 0.2"
INDEX_SCHEMA_VERSION = "ColdArchiveIndex 0.2"
LEGACY_INDEX_SCHEMA_VERSION = "ColdArchiveIndex 0.1"
DEFAULT_ARCHIVE_BRANCH = "archive/cold"
DEFAULT_CONTROL_BRANCH = "main"
DEFAULT_INDEX_PATH = "COLD_ARCHIVE.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
OPERATIONS = {"append", "reindex"}
ENTRY_FIELDS = {"branch", "headSha", "classification", "evidencePath"}
PLAN_FIELDS = {
    "schemaVersion",
    "repository",
    "controlBranch",
    "controlSha",
    "archiveBranch",
    "previousArchiveHead",
    "operation",
    "existingEntries",
    "existingEntriesHash",
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


def _entry(raw: Any, *, control_branch: str, archive_branch: str, code: str) -> dict[str, str]:
    if not isinstance(raw, dict) or set(raw) != ENTRY_FIELDS:
        raise RuntimeError(f"{code}_FIELDS_INVALID")
    branch = _nonempty(raw.get("branch"), f"{code}_BRANCH_INVALID")
    if branch in {control_branch, archive_branch}:
        raise RuntimeError(f"COLD_ARCHIVE_ENTRY_FORBIDDEN:{branch}")
    return {
        "branch": branch,
        "headSha": _sha(raw.get("headSha"), f"{code}_SHA_INVALID"),
        "classification": _nonempty(raw.get("classification"), f"{code}_CLASSIFICATION_INVALID"),
        "evidencePath": _nonempty(raw.get("evidencePath"), f"{code}_EVIDENCE_INVALID"),
    }


def _normalize_entries(
    entries: Any,
    *,
    control_branch: str,
    archive_branch: str,
    allow_empty: bool,
    code: str,
) -> list[dict[str, str]]:
    if not isinstance(entries, list) or (not entries and not allow_empty):
        raise RuntimeError(f"{code}_REQUIRED")

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in entries:
        item = _entry(
            raw,
            control_branch=control_branch,
            archive_branch=archive_branch,
            code=code,
        )
        identity = (item["branch"], item["headSha"])
        if identity in seen:
            raise RuntimeError(
                f"COLD_ARCHIVE_ENTRY_DUPLICATE:{item['branch']}:{item['headSha']}"
            )
        seen.add(identity)
        normalized.append(item)
    return sorted(normalized, key=lambda item: (item["branch"], item["headSha"]))


def merge_entries(
    existing: list[dict[str, str]],
    sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    merged: dict[tuple[str, str], dict[str, str]] = {}
    for item in [*existing, *sources]:
        identity = (item["branch"], item["headSha"])
        previous = merged.get(identity)
        if previous is None:
            merged[identity] = item
        elif previous != item:
            raise RuntimeError(
                f"COLD_ARCHIVE_ENTRY_CONFLICT:{item['branch']}:{item['headSha']}"
            )
    return sorted(merged.values(), key=lambda item: (item["branch"], item["headSha"]))


def _index(
    *,
    archive_branch: str,
    control_sha: str,
    entries: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "archiveBranch": archive_branch,
        "controlSha": control_sha,
        "entries": entries,
    }


def _final_entries(plan: dict[str, Any]) -> list[dict[str, str]]:
    return merge_entries(plan["existingEntries"], plan["sources"])


def render_index(plan: dict[str, Any]) -> str:
    validate_plan(plan)
    value = _index(
        archive_branch=plan["archiveBranch"],
        control_sha=plan["controlSha"],
        entries=_final_entries(plan),
    )
    return canonical_json(value) + "\n"


def build_plan(
    *,
    control_sha: str,
    sources: Any,
    existing_entries: Any | None = None,
    previous_archive_head: str | None = None,
    operation: str = "append",
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
    if operation not in OPERATIONS:
        raise RuntimeError("COLD_ARCHIVE_OPERATION_UNSUPPORTED")
    index_path = _nonempty(index_path, "COLD_ARCHIVE_INDEX_PATH_INVALID")
    if index_path.startswith("/") or index_path.endswith("/") or ".." in index_path.split("/"):
        raise RuntimeError("COLD_ARCHIVE_INDEX_PATH_INVALID")

    existing = _normalize_entries(
        [] if existing_entries is None else existing_entries,
        control_branch=control_branch,
        archive_branch=archive_branch,
        allow_empty=True,
        code="COLD_ARCHIVE_EXISTING_ENTRIES",
    )
    normalized_sources = _normalize_entries(
        sources,
        control_branch=control_branch,
        archive_branch=archive_branch,
        allow_empty=operation == "reindex",
        code="COLD_ARCHIVE_SOURCES",
    )

    if operation == "append":
        if previous_archive_head is None:
            if existing:
                raise RuntimeError("COLD_ARCHIVE_INITIAL_EXISTING_ENTRIES_FORBIDDEN")
        elif not existing:
            raise RuntimeError("COLD_ARCHIVE_EXISTING_ENTRIES_REQUIRED")
    else:
        if previous_archive_head is None:
            raise RuntimeError("COLD_ARCHIVE_REINDEX_PREVIOUS_HEAD_REQUIRED")
        if not existing:
            raise RuntimeError("COLD_ARCHIVE_REINDEX_EXISTING_ENTRIES_REQUIRED")
        if normalized_sources:
            raise RuntimeError("COLD_ARCHIVE_REINDEX_SOURCES_FORBIDDEN")

    final_entries = merge_entries(existing, normalized_sources)

    parent_shas: list[str] = []
    if previous_archive_head is not None:
        parent_shas.append(previous_archive_head)
    for source in normalized_sources:
        sha = source["headSha"]
        if sha not in parent_shas:
            parent_shas.append(sha)

    index_value = _index(
        archive_branch=archive_branch,
        control_sha=control_sha,
        entries=final_entries,
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
        "operation": operation,
        "existingEntries": existing,
        "existingEntriesHash": stable_hash(existing),
        "sources": normalized_sources,
        "parentShas": parent_shas,
        "indexPath": index_path,
        "indexSha256": index_sha256,
        "readback": {
            "kind": "cold-archive-anchor",
            "branch": archive_branch,
            "expectedParents": parent_shas,
            "indexPath": index_path,
            "expectedIndexSha256": index_sha256,
            "expectedEntryCount": len(final_entries),
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
        existing_entries=plan.get("existingEntries"),
        previous_archive_head=plan.get("previousArchiveHead"),
        operation=plan.get("operation"),
        control_branch=plan.get("controlBranch"),
        archive_branch=plan.get("archiveBranch"),
        index_path=plan.get("indexPath"),
    )
    if plan != rebuilt:
        raise RuntimeError("COLD_ARCHIVE_PLAN_MISMATCH")
    return plan


def _load_json(path: Path, *, missing_code: str, invalid_code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"{missing_code}:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{invalid_code}:{path}") from exc


def _load_sources(path: Path | None) -> Any:
    if path is None:
        return []
    return _load_json(
        path,
        missing_code="COLD_ARCHIVE_SOURCES_FILE_MISSING",
        invalid_code="COLD_ARCHIVE_SOURCES_JSON_INVALID",
    )


def _load_existing_index(
    path: Path | None,
    *,
    archive_branch: str,
) -> list[dict[str, str]]:
    if path is None:
        return []
    value = _load_json(
        path,
        missing_code="COLD_ARCHIVE_INDEX_FILE_MISSING",
        invalid_code="COLD_ARCHIVE_INDEX_JSON_INVALID",
    )
    if not isinstance(value, dict):
        raise RuntimeError("COLD_ARCHIVE_EXISTING_INDEX_INVALID")
    if value.get("schemaVersion") not in {LEGACY_INDEX_SCHEMA_VERSION, INDEX_SCHEMA_VERSION}:
        raise RuntimeError("COLD_ARCHIVE_EXISTING_INDEX_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY or value.get("archiveBranch") != archive_branch:
        raise RuntimeError("COLD_ARCHIVE_EXISTING_INDEX_IDENTITY_INVALID")
    return value.get("entries")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build one deterministic cumulative cold-archive anchor plan"
    )
    parser.add_argument("--control-sha", required=True)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--existing-index", type=Path)
    parser.add_argument("--previous-archive-head")
    parser.add_argument("--operation", choices=sorted(OPERATIONS), default="append")
    parser.add_argument("--archive-branch", default=DEFAULT_ARCHIVE_BRANCH)
    parser.add_argument("--control-branch", default=DEFAULT_CONTROL_BRANCH)
    parser.add_argument("--index-path", default=DEFAULT_INDEX_PATH)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        plan = build_plan(
            control_sha=args.control_sha,
            sources=_load_sources(args.sources),
            existing_entries=_load_existing_index(
                args.existing_index,
                archive_branch=args.archive_branch,
            ),
            previous_archive_head=args.previous_archive_head,
            operation=args.operation,
            archive_branch=args.archive_branch,
            control_branch=args.control_branch,
            index_path=args.index_path,
        )
        validate_plan(plan)
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        print(
            json.dumps(payload, ensure_ascii=False)
            if args.as_json
            else f"BLOCKED\n{exc}"
        )
        return 2

    if args.as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print("COLD ARCHIVE PLAN 0.2")
        print(f"  operation: {plan['operation']}")
        print(f"  archive: {plan['archiveBranch']}")
        print(f"  existing: {len(plan['existingEntries'])}")
        print(f"  sources: {len(plan['sources'])}")
        print(f"  final entries: {plan['readback']['expectedEntryCount']}")
        print(f"  parents: {len(plan['parentShas'])}")
        print(f"  planHash: {plan['planHash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only coverage guard for ProjectState checkpoint and direction changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_state
from tools.canonical import stable_hash

COVERAGE_PATH = ROOT / "ops" / "semantics" / "roadmap-freshness-coverage.json"
PROJECT_STATE_PATH = "ops/state/project.json"
SCHEMA_VERSION = "RoadmapFreshnessCoverage 0.1"
INSPECTION_VERSION = "RoadmapFreshnessInspection 0.1"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TRACKED_FIELDS = ("development.checkpoint", "development.nextTransition")
ALWAYS_CONSUMERS = {"docs/plans/autonomous-evolution-roadmap-2026-08.md"}
TOP_FIELDS = {
    "schemaVersion",
    "projectState",
    "consumers",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
}


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"ROADMAP_FRESHNESS_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ROADMAP_FRESHNESS_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("ROADMAP_FRESHNESS_ROOT_INVALID")
    return value


def load_coverage(path: Path = COVERAGE_PATH) -> dict[str, Any]:
    return _json(path)


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _state_hash(value: dict[str, Any]) -> str:
    return stable_hash(value)


def _state_errors(value: dict[str, Any]) -> list[str]:
    errors = project_state.validate_current(value)
    return [f"ROADMAP_FRESHNESS_PROJECT_STATE_INVALID:{item['code']}" for item in errors]


def _changed_fields(base: dict[str, Any], head: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    if base["development"]["checkpoint"] != head["development"]["checkpoint"]:
        changed.append("development.checkpoint")
    if base["development"]["nextTransition"] != head["development"]["nextTransition"]:
        changed.append("development.nextTransition")
    return changed


def discover_consumers(state: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    consumers = set(ALWAYS_CONSUMERS)
    needles = {
        state["development"]["checkpoint"],
        state["development"]["nextTransition"],
    }
    roles = root / "docs" / "kickstarts" / "roles"
    for path in sorted(roles.glob("*-current.md")):
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in needles):
            consumers.add(path.relative_to(root).as_posix())
    return sorted(consumers)


def _validate_shape(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict) or set(value) != TOP_FIELDS:
        return ["ROADMAP_FRESHNESS_FIELDS_INVALID"]
    if value.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("ROADMAP_FRESHNESS_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True:
        errors.append("ROADMAP_FRESHNESS_READ_ONLY_REQUIRED")
    if value.get("semanticAuthority") is not False:
        errors.append("ROADMAP_FRESHNESS_SEMANTIC_AUTHORITY_FORBIDDEN")
    if value.get("authorizesMutation") is not False:
        errors.append("ROADMAP_FRESHNESS_MUTATION_AUTHORITY_FORBIDDEN")

    state = value.get("projectState")
    if not isinstance(state, dict) or set(state) != {"baseHash", "currentHash", "changedFields"}:
        errors.append("ROADMAP_FRESHNESS_STATE_BINDING_INVALID")
    else:
        for field in ("baseHash", "currentHash"):
            if not isinstance(state.get(field), str) or not HASH_RE.fullmatch(state[field]):
                errors.append("ROADMAP_FRESHNESS_STATE_HASH_INVALID")
        changed = state.get("changedFields")
        if (
            not isinstance(changed, list)
            or changed != sorted(set(changed))
            or not set(changed).issubset(TRACKED_FIELDS)
        ):
            errors.append("ROADMAP_FRESHNESS_CHANGED_FIELDS_INVALID")

    consumers = value.get("consumers")
    if not isinstance(consumers, list) or not consumers:
        errors.append("ROADMAP_FRESHNESS_CONSUMERS_INVALID")
    else:
        paths: list[str] = []
        for item in consumers:
            if not isinstance(item, dict) or set(item) != {"path", "disposition", "contentHash"}:
                errors.append("ROADMAP_FRESHNESS_CONSUMER_INVALID")
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
                errors.append("ROADMAP_FRESHNESS_CONSUMER_PATH_INVALID")
            else:
                paths.append(path)
            if item.get("disposition") not in {"UPDATED", "NO_CHANGE"}:
                errors.append("ROADMAP_FRESHNESS_DISPOSITION_INVALID")
            content_hash = item.get("contentHash")
            if not isinstance(content_hash, str) or not HASH_RE.fullmatch(content_hash):
                errors.append("ROADMAP_FRESHNESS_CONTENT_HASH_INVALID")
        if paths != sorted(set(paths)):
            errors.append("ROADMAP_FRESHNESS_CONSUMERS_NOT_SORTED")
    return errors


def validate_coverage(value: dict[str, Any] | None = None, *, root: Path = ROOT) -> list[str]:
    coverage = load_coverage() if value is None else value
    errors = _validate_shape(coverage)
    if errors:
        return errors
    state = _json(root / PROJECT_STATE_PATH)
    errors.extend(_state_errors(state))
    if errors:
        return errors
    if coverage["projectState"]["currentHash"] != _state_hash(state):
        errors.append("ROADMAP_FRESHNESS_CURRENT_STATE_HASH_MISMATCH")
    expected = discover_consumers(state, root=root)
    observed = [item["path"] for item in coverage["consumers"]]
    if observed != expected:
        errors.append("ROADMAP_FRESHNESS_CONSUMER_COVERAGE_MISMATCH")
    for item in coverage["consumers"]:
        path = root / item["path"]
        if not path.is_file():
            errors.append("ROADMAP_FRESHNESS_CONSUMER_MISSING")
        elif item["contentHash"] != _content_hash(path.read_bytes()):
            errors.append("ROADMAP_FRESHNESS_CONSUMER_HASH_MISMATCH")
    return errors


def inspect_transition(
    base_state: dict[str, Any],
    head_state: dict[str, Any],
    base_contents: dict[str, bytes],
    head_contents: dict[str, bytes],
    coverage: dict[str, Any],
    required_consumers: list[str],
) -> dict[str, Any]:
    errors = _validate_shape(coverage)
    errors.extend(_state_errors(base_state))
    errors.extend(_state_errors(head_state))
    changed = _changed_fields(base_state, head_state) if not errors else []
    details: list[dict[str, Any]] = []

    if not changed:
        payload = {
            "schemaVersion": INSPECTION_VERSION,
            "status": "PASS" if not errors else "FAIL",
            "code": "NO_TRANSITION" if not errors else errors[0],
            "changedFields": [],
            "consumers": [],
            "errors": errors,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    else:
        binding = coverage.get("projectState") if isinstance(coverage, dict) else {}
        if binding.get("baseHash") != _state_hash(base_state):
            errors.append("ROADMAP_FRESHNESS_BASE_STATE_HASH_MISMATCH")
        if binding.get("currentHash") != _state_hash(head_state):
            errors.append("ROADMAP_FRESHNESS_CURRENT_STATE_HASH_MISMATCH")
        if binding.get("changedFields") != changed:
            errors.append("ROADMAP_FRESHNESS_CHANGED_FIELDS_MISMATCH")
        by_path = {
            item.get("path"): item
            for item in coverage.get("consumers", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        if sorted(by_path) != sorted(required_consumers):
            errors.append("ROADMAP_FRESHNESS_CONSUMER_COVERAGE_MISMATCH")
        for path in sorted(required_consumers):
            item = by_path.get(path)
            before = base_contents.get(path)
            after = head_contents.get(path)
            if item is None or after is None:
                errors.append("ROADMAP_FRESHNESS_CONSUMER_MISSING")
                continue
            expected = "UPDATED" if before != after else "NO_CHANGE"
            detail = {
                "path": path,
                "disposition": item.get("disposition"),
                "expectedDisposition": expected,
                "contentHash": _content_hash(after),
            }
            details.append(detail)
            if item.get("disposition") != expected:
                errors.append("ROADMAP_FRESHNESS_DISPOSITION_MISMATCH")
            if item.get("contentHash") != detail["contentHash"]:
                errors.append("ROADMAP_FRESHNESS_CONSUMER_HASH_MISMATCH")
        payload = {
            "schemaVersion": INSPECTION_VERSION,
            "status": "PASS" if not errors else "FAIL",
            "code": "COVERAGE_COMPLETE" if not errors else errors[0],
            "changedFields": changed,
            "consumers": details,
            "errors": errors,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    payload["inspectionHash"] = stable_hash(payload)
    return payload


def _git_bytes(ref: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def _git_json(ref: str, path: str) -> dict[str, Any]:
    content = _git_bytes(ref, path)
    if content is None:
        raise RuntimeError(f"ROADMAP_FRESHNESS_GIT_OBJECT_MISSING:{ref}:{path}")
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ROADMAP_FRESHNESS_GIT_JSON_INVALID:{ref}:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"ROADMAP_FRESHNESS_GIT_JSON_INVALID:{ref}:{path}")
    return value


def command_inspect(base_sha: str, head_sha: str, coverage_path: Path) -> dict[str, Any]:
    coverage = load_coverage(coverage_path)
    base_state = _git_json(base_sha, PROJECT_STATE_PATH)
    head_state = _git_json(head_sha, PROJECT_STATE_PATH)
    required = discover_consumers(head_state)
    base_contents = {path: _git_bytes(base_sha, path) for path in required}
    head_contents = {path: _git_bytes(head_sha, path) for path in required}
    return inspect_transition(base_state, head_state, base_contents, head_contents, coverage, required)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only roadmap freshness coverage guard")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--base-sha", required=True)
    inspect.add_argument("--head-sha", required=True)
    inspect.add_argument("--coverage", default=str(COVERAGE_PATH))
    inspect.add_argument("--json", action="store_true", dest="as_json")
    validate = sub.add_parser("validate")
    validate.add_argument("--coverage", default=str(COVERAGE_PATH))
    validate.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            payload = command_inspect(args.base_sha, args.head_sha, Path(args.coverage))
            ok = payload["status"] == "PASS"
        else:
            errors = validate_coverage(load_coverage(Path(args.coverage)))
            payload = {"ok": not errors, "schemaVersion": "RoadmapFreshnessCoverageCheck 0.1", "errors": errors}
            ok = not errors
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        ok = False
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.as_json else payload)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

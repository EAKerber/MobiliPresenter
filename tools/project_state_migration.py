"""Transient deterministic ProjectState 2.0 -> 2.1 migration planner.

This module exists only for the bounded M5C2 cutover. It does not make 2.1 a
current runtime contract and must be retired after the live authority reaches
ProjectState 2.1.
"""
from __future__ import annotations

import argparse
import copy
import json
from typing import Any

from tools import project_state
from tools import transition_protocol as protocol

SOURCE_SCHEMA_VERSION = "ProjectState 2.0"
TARGET_SCHEMA_VERSION = "ProjectState 2.1"
TARGET_TOP_FIELDS = {"schemaVersion", "project", "git", "published", "development"}
TARGET_PROJECT_FIELDS = {"id", "repository"}
TARGET_GIT_FIELDS = {"controlBranch", "protectedBranches"}
TARGET_PUBLISHED_FIELDS = {"url", "artifactManifest"}
TARGET_DEVELOPMENT_FIELDS = {"initiative", "phase", "checkpoint", "nextTransition"}
REMOVED_FIELDS = (
    "git.activeDevelopmentBranch",
    "development.prNumber",
    "development.blockers",
)
PROJECT_STATE_SUBJECT = {"kind": "project-state", "id": "mobilipresenter"}
PROJECT_STATE_AUTHORITY = {"kind": "repository-file", "locator": {"path": "ops/state/project.json"}}


def _error(errors: list[dict[str, str]], code: str, detail: str) -> None:
    errors.append({"code": code, "detail": detail})


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, unique: bool = False) -> bool:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return False
    return not unique or len(value) == len(set(value))


def validate_target(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(state, dict):
        return [{"code": "STATE_SCHEMA_INVALID", "detail": "state must be an object"}]
    if state.get("schemaVersion") != TARGET_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {TARGET_SCHEMA_VERSION}"}]
    if set(state) != TARGET_TOP_FIELDS:
        _error(errors, "STATE_SCHEMA_INVALID", "ProjectState 2.1 top-level fields are invalid")
    for key in ("project", "git", "published", "development"):
        if not isinstance(state.get(key), dict):
            _error(errors, "STATE_SCHEMA_INVALID", f"{key} has invalid type")
    if errors:
        return errors

    project = state["project"]
    if set(project) != TARGET_PROJECT_FIELDS:
        _error(errors, "STATE_SCHEMA_INVALID", "project fields are invalid for ProjectState 2.1")
    if project.get("id") != project_state.PROJECT_ID:
        _error(errors, "PROJECT_ID_MISMATCH", f"project.id must be {project_state.PROJECT_ID}")
    if project.get("repository") != project_state.REPOSITORY:
        _error(errors, "REPOSITORY_ID_MISMATCH", f"project.repository must be {project_state.REPOSITORY}")

    git_state = state["git"]
    if set(git_state) != TARGET_GIT_FIELDS:
        _error(errors, "STATE_SCHEMA_INVALID", "git fields are invalid for ProjectState 2.1")
    if not _nonempty_string(git_state.get("controlBranch")):
        _error(errors, "STATE_SCHEMA_INVALID", "git.controlBranch must be a non-empty string")
    protected = git_state.get("protectedBranches")
    if not _string_list(protected, unique=True) or any(not item for item in protected or []):
        _error(errors, "STATE_SCHEMA_INVALID", "git.protectedBranches must contain unique non-empty strings")

    published = state["published"]
    if set(published) != TARGET_PUBLISHED_FIELDS:
        _error(errors, "STATE_SCHEMA_INVALID", "published fields are invalid for ProjectState 2.1")
    for key in ("url", "artifactManifest"):
        if not _nonempty_string(published.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"published.{key} must be a non-empty string")

    development = state["development"]
    if set(development) != TARGET_DEVELOPMENT_FIELDS:
        _error(errors, "STATE_SCHEMA_INVALID", "development fields are invalid for ProjectState 2.1")
    for key in ("initiative", "phase", "checkpoint", "nextTransition"):
        if not _nonempty_string(development.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"development.{key} must be a non-empty string")
    return errors


def require_empty_legacy_execution(before: dict[str, Any]) -> None:
    errors = project_state.validate_current(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    if before["git"]["activeDevelopmentBranch"] is not None:
        raise RuntimeError("PROJECT_STATE_MIGRATION_LEGACY_EXECUTION_NOT_EMPTY:git.activeDevelopmentBranch")
    if before["development"]["prNumber"] is not None:
        raise RuntimeError("PROJECT_STATE_MIGRATION_LEGACY_EXECUTION_NOT_EMPTY:development.prNumber")
    if before["development"]["blockers"] != []:
        raise RuntimeError("PROJECT_STATE_MIGRATION_LEGACY_EXECUTION_NOT_EMPTY:development.blockers")


def candidate_from_v20(before: dict[str, Any]) -> dict[str, Any]:
    require_empty_legacy_execution(before)
    candidate = copy.deepcopy(before)
    candidate["schemaVersion"] = TARGET_SCHEMA_VERSION
    candidate["git"].pop("activeDevelopmentBranch")
    candidate["development"].pop("prNumber")
    candidate["development"].pop("blockers")
    errors = validate_target(candidate)
    if errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_CANDIDATE_INVALID:{errors[0]['detail']}")
    return candidate


def build_plan(before: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate_from_v20(before)
    intent = {
        "fromSchema": SOURCE_SCHEMA_VERSION,
        "toSchema": TARGET_SCHEMA_VERSION,
        "removedFields": list(REMOVED_FIELDS),
    }
    return protocol.build_plan(
        domain="project-state",
        action="migrate-schema",
        subject=PROJECT_STATE_SUBJECT,
        authority=PROJECT_STATE_AUTHORITY,
        before=before,
        candidate=candidate,
        intent=intent,
        reversibility="revertible",
    )


def validate_plan(plan: dict[str, Any], *, before: dict[str, Any] | None = None) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state" or plan["action"] != "migrate-schema":
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_DOMAIN_INVALID")
    if plan["subject"] != PROJECT_STATE_SUBJECT:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_SUBJECT_INVALID")
    if plan["authority"] != PROJECT_STATE_AUTHORITY:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_AUTHORITY_INVALID")
    expected_intent = {
        "fromSchema": SOURCE_SCHEMA_VERSION,
        "toSchema": TARGET_SCHEMA_VERSION,
        "removedFields": list(REMOVED_FIELDS),
    }
    if plan["intent"] != expected_intent:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_INTENT_INVALID")
    errors = validate_target(plan["candidate"])
    if errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_CANDIDATE_INVALID:{errors[0]['detail']}")
    if before is not None:
        protocol.verify_before_state(plan, before)
        expected_candidate = candidate_from_v20(before)
        if plan["candidate"] != expected_candidate:
            raise RuntimeError("PROJECT_STATE_MIGRATION_CANDIDATE_DRIFT")
    return plan


def command_plan(as_json: bool) -> int:
    before = project_state.load_state()
    plan = build_plan(before)
    validate_plan(plan, before=before)
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print("PROJECT STATE MIGRATION PLAN")
        print(f"  {SOURCE_SCHEMA_VERSION} -> {TARGET_SCHEMA_VERSION}")
        print(f"  planHash: {plan['planHash']}")
        print(f"  beforeStateHash: {plan['beforeStateHash']}")
        print(f"  afterStateHash: {plan['afterStateHash']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan the bounded ProjectState 2.0 -> 2.1 migration")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.command == "plan":
        return command_plan(args.as_json)
    raise RuntimeError("PROJECT_STATE_MIGRATION_COMMAND_INVALID")


if __name__ == "__main__":
    raise SystemExit(main())

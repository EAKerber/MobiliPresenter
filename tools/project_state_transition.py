"""Pure ProjectState transition planners built on Transition Protocol 0.1."""
from __future__ import annotations

import copy
import re
from typing import Any, Callable

from tools import transition_protocol as protocol

Validator = Callable[[dict[str, Any]], list[dict[str, str]]]
Migration = Callable[[dict[str, Any]], dict[str, Any]]
MigrationMapValidator = Callable[[dict[str, Any], dict[str, Any]], list[str]]

PROJECT_STATE_SUBJECT = {"kind": "project-state", "id": "mobilipresenter"}
PROJECT_STATE_AUTHORITY = {"kind": "repository-file", "locator": {"path": "ops/state/project.json"}}
MIGRATION_INTENT_FIELDS = {
    "fromSchemaVersion",
    "toSchemaVersion",
    "sourceControlHead",
    "sourceStateBlobSha",
    "migrationMapPath",
    "migrationMapHash",
    "workBranch",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def checkpoint(
    before: dict[str, Any],
    checkpoint_name: str,
    next_transition: str,
    phase: str | None,
    *,
    validator: Validator,
) -> dict[str, Any]:
    errors = validator(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    if not isinstance(checkpoint_name, str) or not checkpoint_name.strip():
        raise RuntimeError("CHECKPOINT_NAME_INVALID")
    if not isinstance(next_transition, str) or not next_transition.strip():
        raise RuntimeError("CHECKPOINT_NEXT_TRANSITION_INVALID")
    if phase is not None and (not isinstance(phase, str) or not phase.strip()):
        raise RuntimeError("CHECKPOINT_PHASE_INVALID")

    candidate = copy.deepcopy(before)
    candidate["development"]["checkpoint"] = checkpoint_name.strip()
    candidate["development"]["nextTransition"] = next_transition.strip()
    if phase is not None:
        candidate["development"]["phase"] = phase.strip()

    candidate_errors = validator(candidate)
    if candidate_errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{candidate_errors[0]['detail']}")

    intent = {
        "checkpoint": checkpoint_name.strip(),
        "nextTransition": next_transition.strip(),
        "phase": phase.strip() if phase is not None else None,
    }
    return protocol.build_plan(
        domain="project-state",
        action="checkpoint",
        subject={"kind": "project-state", "id": str(before["project"]["id"])},
        authority=PROJECT_STATE_AUTHORITY,
        before=before,
        candidate=candidate,
        intent=intent,
        reversibility="revertible",
    )


def validate_checkpoint_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state" or plan["action"] != "checkpoint":
        raise RuntimeError("CHECKPOINT_PLAN_DOMAIN_INVALID")
    if plan["subject"] != PROJECT_STATE_SUBJECT:
        raise RuntimeError("CHECKPOINT_PLAN_SUBJECT_INVALID")
    if plan["authority"] != PROJECT_STATE_AUTHORITY:
        raise RuntimeError("CHECKPOINT_PLAN_AUTHORITY_INVALID")
    intent = plan["intent"]
    if set(intent) != {"checkpoint", "nextTransition", "phase"}:
        raise RuntimeError("CHECKPOINT_PLAN_INTENT_INVALID")
    errors = validator(plan["candidate"])
    if errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{errors[0]['detail']}")
    development = plan["candidate"]["development"]
    if development["checkpoint"] != intent["checkpoint"] or development["nextTransition"] != intent["nextTransition"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    if intent["phase"] is not None and development["phase"] != intent["phase"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan


def schema_migration(
    before: dict[str, Any],
    migration_map: dict[str, Any],
    *,
    source_control_head: str,
    source_state_blob_sha: str,
    work_branch: str,
    source_validator: Validator,
    target_validator: Validator,
    migrate: Migration,
    validate_migration_map: MigrationMapValidator,
    migration_map_path: str = "ops/migrations/project-state-2.0.json",
) -> dict[str, Any]:
    errors = source_validator(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    map_errors = validate_migration_map(migration_map, before)
    if map_errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_MAP_INVALID:{map_errors[0]}")
    if not HEX40.fullmatch(source_control_head):
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_HEAD_INVALID")
    if not HEX40.fullmatch(source_state_blob_sha):
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_BLOB_INVALID")
    if not isinstance(work_branch, str) or not work_branch.strip():
        raise RuntimeError("PROJECT_STATE_MIGRATION_WORK_BRANCH_INVALID")
    if not isinstance(migration_map_path, str) or not migration_map_path.strip():
        raise RuntimeError("PROJECT_STATE_MIGRATION_MAP_PATH_INVALID")

    candidate = migrate(before)
    target_errors = target_validator(candidate)
    if target_errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_CANDIDATE_INVALID:{target_errors[0]['detail']}")
    intent = {
        "fromSchemaVersion": before["schemaVersion"],
        "toSchemaVersion": candidate["schemaVersion"],
        "sourceControlHead": source_control_head,
        "sourceStateBlobSha": source_state_blob_sha,
        "migrationMapPath": migration_map_path,
        "migrationMapHash": protocol.stable_hash(migration_map),
        "workBranch": work_branch.strip(),
    }
    return protocol.build_plan(
        domain="project-state",
        action="schema-migration",
        subject=PROJECT_STATE_SUBJECT,
        authority=PROJECT_STATE_AUTHORITY,
        before=before,
        candidate=candidate,
        intent=intent,
        reversibility="revertible",
    )


def validate_schema_migration_plan(plan: dict[str, Any], *, target_validator: Validator) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state" or plan["action"] != "schema-migration":
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_DOMAIN_INVALID")
    if plan["subject"] != PROJECT_STATE_SUBJECT:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_SUBJECT_INVALID")
    if plan["authority"] != PROJECT_STATE_AUTHORITY:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_AUTHORITY_INVALID")
    intent = plan["intent"]
    if not isinstance(intent, dict) or set(intent) != MIGRATION_INTENT_FIELDS:
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_INTENT_INVALID")
    if intent.get("fromSchemaVersion") != "ProjectState 1.0" or intent.get("toSchemaVersion") != "ProjectState 2.0":
        raise RuntimeError("PROJECT_STATE_MIGRATION_PLAN_VERSION_INVALID")
    if not HEX40.fullmatch(str(intent.get("sourceControlHead") or "")):
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_HEAD_INVALID")
    if not HEX40.fullmatch(str(intent.get("sourceStateBlobSha") or "")):
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_BLOB_INVALID")
    if not HEX64.fullmatch(str(intent.get("migrationMapHash") or "")):
        raise RuntimeError("PROJECT_STATE_MIGRATION_MAP_HASH_INVALID")
    if not isinstance(intent.get("migrationMapPath"), str) or not intent["migrationMapPath"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_MAP_PATH_INVALID")
    if not isinstance(intent.get("workBranch"), str) or not intent["workBranch"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_WORK_BRANCH_INVALID")
    target_errors = target_validator(plan["candidate"])
    if target_errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_CANDIDATE_INVALID:{target_errors[0]['detail']}")
    return plan

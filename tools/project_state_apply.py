"""Fail-closed ProjectState executor for Transition Protocol 0.1 plans."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from tools import project_state_transition as transition
from tools import transition_protocol as protocol
from tools.semantics.branches import parse_branch_name

Loader = Callable[[], dict[str, Any]]
Validator = Callable[[dict[str, Any]], list[dict[str, str]]]
GitObserver = Callable[[], dict[str, Any]]
StringObserver = Callable[[], str]
MigrationMapLoader = Callable[[], dict[str, Any]]
Migration = Callable[[dict[str, Any]], dict[str, Any]]
MigrationMapValidator = Callable[[dict[str, Any], dict[str, Any]], list[str]]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _restore_bytes(path: Path, previous_bytes: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(previous_bytes)
        restore_tmp = Path(handle.name)
    try:
        os.replace(restore_tmp, path)
    finally:
        if restore_tmp.exists():
            restore_tmp.unlink()


def apply(
    plan: dict[str, Any],
    expected_plan: str | None,
    *,
    state_path: Path,
    load_state: Loader,
    validator: Validator,
    observe_git: GitObserver,
) -> dict[str, Any]:
    transition.validate_checkpoint_plan(plan, validator=validator)
    protocol.require_expected_plan(plan, expected_plan)

    current = load_state()
    errors = validator(current)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    protocol.verify_before_state(plan, current)

    active = current["git"].get("activeDevelopmentBranch")
    if active is None:
        raise RuntimeError("CHECKPOINT_NO_ACTIVE_DEVELOPMENT")
    git = observe_git()
    if not git.get("worktree"):
        raise RuntimeError("CHECKPOINT_NOT_A_WORKTREE")
    if git.get("branch") != active:
        raise RuntimeError(f"CHECKPOINT_WRONG_BRANCH:{git.get('branch')}")
    if git.get("dirty"):
        raise RuntimeError("CHECKPOINT_DIRTY_WORKTREE")

    previous_bytes = state_path.read_bytes()
    wrote = False
    try:
        _atomic_write(state_path, plan["candidate"])
        wrote = True
        readback = load_state()
        errors = validator(readback)
        if errors:
            raise RuntimeError(f"STATE_READBACK_INVALID:{errors[0]['detail']}")
        receipt = protocol.build_receipt(plan, readback)
        protocol.validate_receipt(receipt, plan)
        return receipt
    except Exception:
        if wrote:
            _restore_bytes(state_path, previous_bytes)
            restored = load_state()
            if protocol.state_hash(restored) != plan["beforeStateHash"]:
                raise RuntimeError("PROJECT_STATE_ROLLBACK_FAILED")
        raise


def apply_schema_migration(
    plan: dict[str, Any],
    expected_plan: str | None,
    *,
    authorized: bool,
    state_path: Path,
    load_state: Loader,
    source_validator: Validator,
    target_validator: Validator,
    migration_map_loader: MigrationMapLoader,
    validate_migration_map: MigrationMapValidator,
    migrate: Migration,
    observe_git: GitObserver,
    observe_control_head: StringObserver,
    observe_state_blob: StringObserver,
) -> dict[str, Any]:
    transition.validate_schema_migration_plan(plan, target_validator=target_validator)
    protocol.require_expected_plan(plan, expected_plan)
    if authorized is not True:
        raise RuntimeError("PROJECT_STATE_SCHEMA_MIGRATION_AUTHORIZATION_REQUIRED")

    current = load_state()
    errors = source_validator(current)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    protocol.verify_before_state(plan, current)
    intent = plan["intent"]

    if current.get("schemaVersion") != intent["fromSchemaVersion"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_VERSION_DRIFT")
    development = current.get("development") if isinstance(current.get("development"), dict) else {}
    git_state = current.get("git") if isinstance(current.get("git"), dict) else {}
    if development.get("phase") != "between-increments":
        raise RuntimeError("PROJECT_STATE_MIGRATION_PHASE_BLOCKED")
    if git_state.get("activeDevelopmentBranch") is not None or development.get("prNumber") is not None:
        raise RuntimeError("PROJECT_STATE_MIGRATION_ACTIVE_DEVELOPMENT")

    git = observe_git()
    if not git.get("worktree"):
        raise RuntimeError("PROJECT_STATE_MIGRATION_NOT_A_WORKTREE")
    branch = git.get("branch")
    if branch != intent["workBranch"]:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_WRONG_BRANCH:{branch}")
    branch_identity = parse_branch_name(str(branch))
    if not (
        branch_identity.get("grammar") == "canonical"
        and branch_identity.get("declaredClass") == "work"
        and branch_identity.get("semanticDomain") == "operations"
    ):
        raise RuntimeError("PROJECT_STATE_MIGRATION_BRANCH_SEMANTICS_INVALID")
    if git.get("dirty"):
        raise RuntimeError("PROJECT_STATE_MIGRATION_DIRTY_WORKTREE")

    if observe_control_head() != intent["sourceControlHead"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_CONTROL_HEAD_DRIFT")
    if observe_state_blob() != intent["sourceStateBlobSha"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_SOURCE_STATE_BLOB_DRIFT")

    migration_map = migration_map_loader()
    map_errors = validate_migration_map(migration_map, current)
    if map_errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_MAP_INVALID:{map_errors[0]}")
    if protocol.stable_hash(migration_map) != intent["migrationMapHash"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_MAP_HASH_DRIFT")

    rebuilt = migrate(current)
    target_errors = target_validator(rebuilt)
    if target_errors:
        raise RuntimeError(f"PROJECT_STATE_MIGRATION_CANDIDATE_INVALID:{target_errors[0]['detail']}")
    if rebuilt != plan["candidate"] or protocol.state_hash(rebuilt) != plan["afterStateHash"]:
        raise RuntimeError("PROJECT_STATE_MIGRATION_CANDIDATE_REBUILD_MISMATCH")

    previous_bytes = state_path.read_bytes()
    wrote = False
    try:
        _atomic_write(state_path, rebuilt)
        wrote = True
        readback = load_state()
        readback_errors = target_validator(readback)
        if readback_errors:
            raise RuntimeError(f"STATE_READBACK_INVALID:{readback_errors[0]['detail']}")
        receipt = protocol.build_receipt(plan, readback)
        protocol.validate_receipt(receipt, plan)
        return receipt
    except Exception:
        if wrote:
            _restore_bytes(state_path, previous_bytes)
            restored = load_state()
            if protocol.state_hash(restored) != plan["beforeStateHash"]:
                raise RuntimeError("PROJECT_STATE_ROLLBACK_FAILED")
        raise

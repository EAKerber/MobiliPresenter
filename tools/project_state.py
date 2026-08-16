"""ProjectState contract, compatibility projection, and deterministic V1→V2 migration."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
CURRENT_SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"
CANDIDATE_V2_SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state-2.0.schema.json"
MIGRATION_MAP_PATH = ROOT / "ops" / "migrations" / "project-state-2.0.json"
CURRENT_SCHEMA_VERSION = "ProjectState 1.0"
V2_SCHEMA_VERSION = "ProjectState 2.0"
REPOSITORY = "EAKerber/MobiliPresenter"
PROJECT_ID = "mobilipresenter"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"STATE_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STATE_JSON_INVALID:{path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"STATE_ROOT_INVALID:{path}")
    return value


def load_state() -> dict[str, Any]:
    return load_json(STATE_PATH)


def _error(errors: list[dict[str, str]], code: str, detail: str) -> None:
    errors.append({"code": code, "detail": detail})


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, unique: bool = False) -> bool:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return False
    return not unique or len(value) == len(set(value))


def _common_identity_errors(state: dict[str, Any], errors: list[dict[str, str]]) -> None:
    project = state.get("project")
    if not isinstance(project, dict):
        _error(errors, "STATE_SCHEMA_INVALID", "project has invalid type")
        return
    if project.get("id") != PROJECT_ID:
        _error(errors, "PROJECT_ID_MISMATCH", f"project.id must be {PROJECT_ID}")
    if project.get("repository") != REPOSITORY:
        _error(errors, "REPOSITORY_ID_MISMATCH", f"project.repository must be {REPOSITORY}")


def _development_identity_errors(git_state: dict[str, Any], development: dict[str, Any], errors: list[dict[str, str]]) -> None:
    active = git_state.get("activeDevelopmentBranch")
    pr_number = development.get("prNumber")
    if active is not None and not _nonempty_string(active):
        _error(errors, "STATE_SCHEMA_INVALID", "git.activeDevelopmentBranch must be null or a non-empty string")
    if pr_number is not None and (not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0):
        _error(errors, "STATE_SCHEMA_INVALID", "development.prNumber must be null or a positive integer")
    if (active is None) != (pr_number is None):
        _error(errors, "DEVELOPMENT_IDENTITY_INCOMPLETE", "activeDevelopmentBranch and prNumber must both be set or both be null")


def validate_v1(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(state, dict):
        return [{"code": "STATE_SCHEMA_INVALID", "detail": "state must be an object"}]
    if state.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {CURRENT_SCHEMA_VERSION}"}]
    for key in ("project", "git", "published", "development", "operations"):
        if not isinstance(state.get(key), dict):
            _error(errors, "STATE_SCHEMA_INVALID", f"{key} has invalid type")
    if errors:
        return errors
    _common_identity_errors(state, errors)
    project = state["project"]
    if not isinstance(project.get("productInvariants"), dict):
        _error(errors, "STATE_SCHEMA_INVALID", "project.productInvariants must be an object")
    git_state = state["git"]
    for key in ("controlBranch", "publishedBranch"):
        if not _nonempty_string(git_state.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"git.{key} must be a non-empty string")
    preserve = git_state.get("preserveBranches")
    if not _string_list(preserve, unique=True) or any(not item for item in preserve or []):
        _error(errors, "STATE_SCHEMA_INVALID", "git.preserveBranches must contain unique non-empty strings")
    published = state["published"]
    for key in ("release", "url", "artifactManifest"):
        if not _nonempty_string(published.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"published.{key} must be a non-empty string")
    sha = published.get("artifactSha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha):
        _error(errors, "ARTIFACT_SHA_INVALID", "published.artifactSha256 must be lowercase sha256")
    development = state["development"]
    for key in ("initiative", "phase", "checkpoint", "nextTransition", "plan"):
        if not _nonempty_string(development.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"development.{key} must be a non-empty string")
    if not _string_list(development.get("blockers")):
        _error(errors, "STATE_SCHEMA_INVALID", "development.blockers must be a string list")
    if not _string_list(development.get("constraints"), unique=True):
        _error(errors, "STATE_SCHEMA_INVALID", "development.constraints must be a unique string list")
    _development_identity_errors(git_state, development, errors)
    operations = state["operations"]
    if operations.get("canonicalState") != "ops/state/project.json":
        _error(errors, "CANONICAL_STATE_MISMATCH", "operations.canonicalState is unexpected")
    commands = operations.get("commands")
    expected_commands = {"status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"}
    if not isinstance(commands, list) or set(commands) != expected_commands:
        _error(errors, "TOOLBOX_COMMANDS_MISMATCH", "operations.commands must contain the legacy ProjectState 1.0 command inventory")
    if operations.get("toolboxPhase") not in {"phase-1.1-coherence", "phase-1.2-branch-hygiene"}:
        _error(errors, "STATE_SCHEMA_INVALID", "operations.toolboxPhase is invalid for ProjectState 1.0")
    return errors


def validate_v2(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(state, dict):
        return [{"code": "STATE_SCHEMA_INVALID", "detail": "state must be an object"}]
    if state.get("schemaVersion") != V2_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {V2_SCHEMA_VERSION}"}]
    expected_top = {"schemaVersion", "project", "git", "published", "development"}
    if set(state) != expected_top:
        _error(errors, "STATE_SCHEMA_INVALID", "ProjectState 2.0 top-level fields are invalid")
    for key in ("project", "git", "published", "development"):
        if not isinstance(state.get(key), dict):
            _error(errors, "STATE_SCHEMA_INVALID", f"{key} has invalid type")
    if errors:
        return errors
    _common_identity_errors(state, errors)
    project = state["project"]
    if set(project) != {"id", "repository"}:
        _error(errors, "STATE_SCHEMA_INVALID", "project fields are invalid for ProjectState 2.0")
    git_state = state["git"]
    if set(git_state) != {"controlBranch", "activeDevelopmentBranch", "protectedBranches"}:
        _error(errors, "STATE_SCHEMA_INVALID", "git fields are invalid for ProjectState 2.0")
    if not _nonempty_string(git_state.get("controlBranch")):
        _error(errors, "STATE_SCHEMA_INVALID", "git.controlBranch must be a non-empty string")
    protected = git_state.get("protectedBranches")
    if not _string_list(protected, unique=True) or any(not item for item in protected or []):
        _error(errors, "STATE_SCHEMA_INVALID", "git.protectedBranches must contain unique non-empty strings")
    published = state["published"]
    if set(published) != {"url", "artifactManifest"}:
        _error(errors, "STATE_SCHEMA_INVALID", "published fields are invalid for ProjectState 2.0")
    for key in ("url", "artifactManifest"):
        if not _nonempty_string(published.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"published.{key} must be a non-empty string")
    development = state["development"]
    expected_development = {"initiative", "phase", "checkpoint", "nextTransition", "blockers", "prNumber"}
    if set(development) != expected_development:
        _error(errors, "STATE_SCHEMA_INVALID", "development fields are invalid for ProjectState 2.0")
    for key in ("initiative", "phase", "checkpoint", "nextTransition"):
        if not _nonempty_string(development.get(key)):
            _error(errors, "STATE_SCHEMA_INVALID", f"development.{key} must be a non-empty string")
    if not _string_list(development.get("blockers")):
        _error(errors, "STATE_SCHEMA_INVALID", "development.blockers must be a string list")
    _development_identity_errors(git_state, development, errors)
    return errors


def validate_current(state: dict[str, Any]) -> list[dict[str, str]]:
    if state.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"current authority must remain {CURRENT_SCHEMA_VERSION} during M4A"}]
    return validate_v1(state)


def validate_compatible(state: dict[str, Any]) -> list[dict[str, str]]:
    version = state.get("schemaVersion")
    if version == CURRENT_SCHEMA_VERSION:
        return validate_v1(state)
    if version == V2_SCHEMA_VERSION:
        return validate_v2(state)
    return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"unsupported ProjectState schemaVersion: {version}"}]


def operational_view(state: dict[str, Any]) -> dict[str, Any]:
    errors = validate_compatible(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    if state["schemaVersion"] == CURRENT_SCHEMA_VERSION:
        protected = copy.deepcopy(state["git"]["preserveBranches"])
    else:
        protected = copy.deepcopy(state["git"]["protectedBranches"])
    return {
        "project": {
            "id": state["project"]["id"],
            "repository": state["project"]["repository"],
        },
        "git": {
            "controlBranch": state["git"]["controlBranch"],
            "activeDevelopmentBranch": state["git"].get("activeDevelopmentBranch"),
            "protectedBranches": protected,
        },
        "published": {
            "url": state["published"]["url"],
            "artifactManifest": state["published"]["artifactManifest"],
        },
        "development": {
            "initiative": state["development"]["initiative"],
            "phase": state["development"]["phase"],
            "checkpoint": state["development"]["checkpoint"],
            "nextTransition": state["development"]["nextTransition"],
            "blockers": copy.deepcopy(state["development"].get("blockers") or []),
            "prNumber": state["development"].get("prNumber"),
        },
    }


def migrate_v1_to_v2(state: dict[str, Any]) -> dict[str, Any]:
    errors = validate_v1(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    view = operational_view(state)
    return {
        "schemaVersion": V2_SCHEMA_VERSION,
        "project": copy.deepcopy(view["project"]),
        "git": copy.deepcopy(view["git"]),
        "published": copy.deepcopy(view["published"]),
        "development": copy.deepcopy(view["development"]),
    }


def validate_migration_map(value: dict[str, Any], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict) or value.get("schemaVersion") != "ProjectStateMigrationMap 0.1":
        return ["PROJECT_STATE_MIGRATION_MAP_SCHEMA_INVALID"]
    if value.get("sourceVersion") != CURRENT_SCHEMA_VERSION or value.get("targetVersion") != V2_SCHEMA_VERSION:
        errors.append("PROJECT_STATE_MIGRATION_MAP_VERSION_INVALID")
    field_mappings = value.get("fieldMappings")
    if not isinstance(field_mappings, list) or not field_mappings:
        errors.append("PROJECT_STATE_MIGRATION_FIELD_MAP_INVALID")
    else:
        seen: set[str] = set()
        for item in field_mappings:
            if not isinstance(item, dict):
                errors.append("PROJECT_STATE_MIGRATION_FIELD_ENTRY_INVALID")
                continue
            source = item.get("sourceField")
            if not _nonempty_string(source) or source in seen:
                errors.append("PROJECT_STATE_MIGRATION_FIELD_SOURCE_INVALID")
            else:
                seen.add(source)
            if item.get("disposition") not in {"retain", "rename", "derive", "remove"}:
                errors.append("PROJECT_STATE_MIGRATION_FIELD_DISPOSITION_INVALID")
            if not _nonempty_string(item.get("reason")) or not _nonempty_string(item.get("destination")):
                errors.append("PROJECT_STATE_MIGRATION_FIELD_DESTINATION_INVALID")
    mappings = value.get("constraintMappings")
    expected = state.get("development", {}).get("constraints")
    if not isinstance(mappings, list) or not isinstance(expected, list):
        errors.append("PROJECT_STATE_MIGRATION_CONSTRAINT_MAP_INVALID")
        return errors
    sources: list[str] = []
    allowed_classes = {"contract", "executable-contract", "implementation-authority", "evidence", "history"}
    for item in mappings:
        if not isinstance(item, dict):
            errors.append("PROJECT_STATE_MIGRATION_CONSTRAINT_ENTRY_INVALID")
            continue
        source = item.get("sourceValue")
        if not _nonempty_string(source):
            errors.append("PROJECT_STATE_MIGRATION_CONSTRAINT_SOURCE_INVALID")
            continue
        sources.append(source)
        if item.get("class") not in allowed_classes:
            errors.append(f"PROJECT_STATE_MIGRATION_CONSTRAINT_CLASS_INVALID:{source}")
        if item.get("status") != "resolved":
            errors.append(f"PROJECT_STATE_MIGRATION_CONSTRAINT_UNRESOLVED:{source}")
        if not _nonempty_string(item.get("destination")) or not _nonempty_string(item.get("evidence")):
            errors.append(f"PROJECT_STATE_MIGRATION_CONSTRAINT_DESTINATION_INVALID:{source}")
    if len(sources) != len(set(sources)):
        errors.append("PROJECT_STATE_MIGRATION_CONSTRAINT_DUPLICATE")
    if sources != expected:
        errors.append("PROJECT_STATE_MIGRATION_CONSTRAINT_COVERAGE_MISMATCH")
    return errors

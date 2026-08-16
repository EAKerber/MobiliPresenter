"""ProjectState 2.0 current operational contract."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
CURRENT_SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"
CURRENT_SCHEMA_VERSION = "ProjectState 2.0"
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


def validate_current(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(state, dict):
        return [{"code": "STATE_SCHEMA_INVALID", "detail": "state must be an object"}]
    if state.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        return [{"code": "STATE_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {CURRENT_SCHEMA_VERSION}"}]
    expected_top = {"schemaVersion", "project", "git", "published", "development"}
    if set(state) != expected_top:
        _error(errors, "STATE_SCHEMA_INVALID", "ProjectState 2.0 top-level fields are invalid")
    for key in ("project", "git", "published", "development"):
        if not isinstance(state.get(key), dict):
            _error(errors, "STATE_SCHEMA_INVALID", f"{key} has invalid type")
    if errors:
        return errors

    project = state["project"]
    if set(project) != {"id", "repository"}:
        _error(errors, "STATE_SCHEMA_INVALID", "project fields are invalid for ProjectState 2.0")
    if project.get("id") != PROJECT_ID:
        _error(errors, "PROJECT_ID_MISMATCH", f"project.id must be {PROJECT_ID}")
    if project.get("repository") != REPOSITORY:
        _error(errors, "REPOSITORY_ID_MISMATCH", f"project.repository must be {REPOSITORY}")

    git_state = state["git"]
    if set(git_state) != {"controlBranch", "activeDevelopmentBranch", "protectedBranches"}:
        _error(errors, "STATE_SCHEMA_INVALID", "git fields are invalid for ProjectState 2.0")
    if not _nonempty_string(git_state.get("controlBranch")):
        _error(errors, "STATE_SCHEMA_INVALID", "git.controlBranch must be a non-empty string")
    active = git_state.get("activeDevelopmentBranch")
    if active is not None and not _nonempty_string(active):
        _error(errors, "STATE_SCHEMA_INVALID", "git.activeDevelopmentBranch must be null or a non-empty string")
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
    pr_number = development.get("prNumber")
    if pr_number is not None and (not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0):
        _error(errors, "STATE_SCHEMA_INVALID", "development.prNumber must be null or a positive integer")
    if (active is None) != (pr_number is None):
        _error(errors, "DEVELOPMENT_IDENTITY_INCOMPLETE", "activeDevelopmentBranch and prNumber must both be set or both be null")
    return errors


def operational_view(state: dict[str, Any]) -> dict[str, Any]:
    errors = validate_current(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return {
        "project": copy.deepcopy(state["project"]),
        "git": copy.deepcopy(state["git"]),
        "published": copy.deepcopy(state["published"]),
        "development": copy.deepcopy(state["development"]),
    }

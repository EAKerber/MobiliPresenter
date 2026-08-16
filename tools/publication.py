"""Read-only SourceBuild publication contract and derived publication projection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "SourceBuild 1.1"
FINGERPRINT_KIND = "sha256(sourceBase|sourcePaths|buildCommand|publishPath)"
TOP_FIELDS = {
    "schemaVersion", "release", "sha256", "fingerprintKind", "sourceBranch", "sourceBase",
    "sourcePaths", "buildCommand", "publishPath", "defaultUiMode", "uiPreviewQuery",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(char in "0123456789abcdef" for char in value)


def validate_manifest(value: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"code": "SOURCE_BUILD_INVALID", "detail": "manifest must be an object"}]
    if set(value) != TOP_FIELDS:
        errors.append({"code": "SOURCE_BUILD_FIELDS_INVALID", "detail": f"SourceBuild fields do not match {SCHEMA_VERSION}"})
    if value.get("schemaVersion") != SCHEMA_VERSION:
        errors.append({"code": "SOURCE_BUILD_SCHEMA_UNSUPPORTED", "detail": f"schemaVersion must be {SCHEMA_VERSION}"})
    for key in ("release", "sourceBranch", "buildCommand", "publishPath", "defaultUiMode"):
        if not _nonempty(value.get(key)):
            errors.append({"code": "SOURCE_BUILD_FIELD_INVALID", "detail": f"{key} must be a non-empty string"})
    if not isinstance(value.get("uiPreviewQuery"), str):
        errors.append({"code": "SOURCE_BUILD_FIELD_INVALID", "detail": "uiPreviewQuery must be a string"})
    if not _hex(value.get("sha256"), 64):
        errors.append({"code": "SOURCE_BUILD_FINGERPRINT_INVALID", "detail": "sha256 must be lowercase sha256"})
    if value.get("fingerprintKind") != FINGERPRINT_KIND:
        errors.append({"code": "SOURCE_BUILD_FINGERPRINT_KIND_INVALID", "detail": "fingerprintKind is unsupported"})
    if not _hex(value.get("sourceBase"), 40):
        errors.append({"code": "SOURCE_BUILD_SOURCE_BASE_INVALID", "detail": "sourceBase must be a lowercase git SHA"})
    source_paths = value.get("sourcePaths")
    if not isinstance(source_paths, list) or not source_paths or any(not _nonempty(item) for item in source_paths) or len(source_paths) != len(set(source_paths)):
        errors.append({"code": "SOURCE_BUILD_SOURCE_PATHS_INVALID", "detail": "sourcePaths must contain unique non-empty strings"})
    return errors


def load_manifest(relative_path: str) -> dict[str, Any]:
    if not _nonempty(relative_path):
        raise RuntimeError("SOURCE_BUILD_PATH_INVALID")
    path = ROOT / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"SOURCE_BUILD_MISSING:{relative_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SOURCE_BUILD_JSON_INVALID:{relative_path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SOURCE_BUILD_INVALID")
    errors = validate_manifest(value)
    if errors:
        raise RuntimeError(f"SOURCE_BUILD_INVALID:{errors[0]['code']}:{errors[0]['detail']}")
    return value


def publication_view(project_view: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError(f"SOURCE_BUILD_INVALID:{errors[0]['code']}:{errors[0]['detail']}")
    published = project_view.get("published") if isinstance(project_view, dict) else None
    if not isinstance(published, dict) or not _nonempty(published.get("url")) or not _nonempty(published.get("artifactManifest")):
        raise RuntimeError("PROJECT_PUBLICATION_POINTER_INVALID")
    return {
        "url": published["url"],
        "artifactManifest": published["artifactManifest"],
        "release": manifest["release"],
        "sourceBranch": manifest["sourceBranch"],
        "sourceBuildFingerprint": manifest["sha256"],
        "fingerprintKind": manifest["fingerprintKind"],
        "sourceBase": manifest["sourceBase"],
        "sourcePaths": list(manifest["sourcePaths"]),
        "publishPath": manifest["publishPath"],
    }

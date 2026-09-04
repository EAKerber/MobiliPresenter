"""Read-only SourceBuild publication contract and derived publication projection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.canonical import stable_hash

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "SourceBuild 1.2"
FINGERPRINT_PAYLOAD_VERSION = "SourceBuildFingerprint 1.0"
FINGERPRINT_KIND = "sha256(canonical-json(SourceBuildFingerprint 1.0))"
TOP_FIELDS = {
    "schemaVersion", "release", "sha256", "fingerprintKind", "sourceBranch", "sourceBase",
    "sourcePaths", "buildCommand", "publishPath", "defaultUiMode", "uiPreviewQuery",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(char in "0123456789abcdef" for char in value)


def fingerprint_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the exact canonical payload bound by the SourceBuild fingerprint."""
    return {
        "schemaVersion": FINGERPRINT_PAYLOAD_VERSION,
        "sourceBase": value.get("sourceBase"),
        "sourcePaths": list(value.get("sourcePaths") or []),
        "buildCommand": value.get("buildCommand"),
        "publishPath": value.get("publishPath"),
    }


def compute_fingerprint(value: dict[str, Any]) -> str:
    """Compute a reproducible sha256 over the versioned canonical JSON payload."""
    return stable_hash(fingerprint_payload(value))


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
    fingerprint_valid = _hex(value.get("sha256"), 64)
    if not fingerprint_valid:
        errors.append({"code": "SOURCE_BUILD_FINGERPRINT_INVALID", "detail": "sha256 must be lowercase sha256"})
    if value.get("fingerprintKind") != FINGERPRINT_KIND:
        errors.append({"code": "SOURCE_BUILD_FINGERPRINT_KIND_INVALID", "detail": "fingerprintKind is unsupported"})
    source_base_valid = _hex(value.get("sourceBase"), 40)
    if not source_base_valid:
        errors.append({"code": "SOURCE_BUILD_SOURCE_BASE_INVALID", "detail": "sourceBase must be a lowercase git SHA"})
    source_paths = value.get("sourcePaths")
    source_paths_valid = (
        isinstance(source_paths, list)
        and bool(source_paths)
        and all(_nonempty(item) for item in source_paths)
        and len(source_paths) == len(set(source_paths))
    )
    if not source_paths_valid:
        errors.append({"code": "SOURCE_BUILD_SOURCE_PATHS_INVALID", "detail": "sourcePaths must contain unique non-empty strings"})
    fingerprint_inputs_valid = (
        source_base_valid
        and source_paths_valid
        and _nonempty(value.get("buildCommand"))
        and _nonempty(value.get("publishPath"))
    )
    if fingerprint_valid and fingerprint_inputs_valid and value.get("fingerprintKind") == FINGERPRINT_KIND:
        expected = compute_fingerprint(value)
        if value["sha256"] != expected:
            errors.append({
                "code": "SOURCE_BUILD_FINGERPRINT_MISMATCH",
                "detail": f"sha256 does not match canonical SourceBuild payload; expected {expected}",
            })
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

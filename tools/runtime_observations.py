#!/usr/bin/env python3
"""Closed read-only observation bundle accepted by ProjectMachine live inspection.

The bundle records factual observations obtained by an external runtime/provider.
It never selects a provider, reobserves authorities, authorizes mutation, or assigns
semantic authority to transport evidence.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash

SCHEMA_VERSION = "RuntimeObservationBundle 0.1"
REPOSITORY = "EAKerber/MobiliPresenter"
OBSERVATION_IDS = ("control", "coordination", "continuations", "pullRequests")
STATUSES = {"PASS", "UNKNOWN", "FAIL"}
PROVIDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
OBSERVATION_FIELDS = {"status", "code", "source", "data"}
SOURCE_FIELDS = {"providerId", "capability"}
TOP_FIELDS = {
    "schemaVersion",
    "repository",
    "observations",
    "readOnly",
    "semanticAuthority",
    "bundleHash",
}
ERROR_EXIT = 2


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _source(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != SOURCE_FIELDS:
        raise RuntimeError("RUNTIME_OBSERVATION_SOURCE_INVALID")
    provider_id = _text(value.get("providerId"), "RUNTIME_OBSERVATION_PROVIDER_INVALID")
    if not PROVIDER_ID_RE.fullmatch(provider_id):
        raise RuntimeError("RUNTIME_OBSERVATION_PROVIDER_INVALID")
    capability = _text(value.get("capability"), "RUNTIME_OBSERVATION_CAPABILITY_INVALID")
    return {"providerId": provider_id, "capability": capability}


def _observation(value: Any, observation_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        raise RuntimeError(f"RUNTIME_OBSERVATION_FIELDS_INVALID:{observation_id}")
    status = str(value.get("status") or "").upper()
    if status not in STATUSES:
        raise RuntimeError(f"RUNTIME_OBSERVATION_STATUS_INVALID:{observation_id}")
    code = value.get("code")
    if status == "PASS":
        if code is not None:
            raise RuntimeError(f"RUNTIME_OBSERVATION_PASS_CODE_INVALID:{observation_id}")
    else:
        code = _text(code, f"RUNTIME_OBSERVATION_CODE_REQUIRED:{observation_id}")
    data = value.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"RUNTIME_OBSERVATION_DATA_INVALID:{observation_id}")
    return {
        "status": status,
        "code": code,
        "source": _source(value.get("source")),
        "data": copy.deepcopy(data),
    }


def _body(repository: str, observations: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "repository": repository,
        "observations": observations,
        "readOnly": True,
        "semanticAuthority": False,
    }


def build_bundle(repository: str, observations: dict[str, Any]) -> dict[str, Any]:
    repository = _text(repository, "RUNTIME_OBSERVATION_REPOSITORY_INVALID")
    if repository != REPOSITORY:
        raise RuntimeError("RUNTIME_OBSERVATION_REPOSITORY_MISMATCH")
    if not isinstance(observations, dict) or set(observations) != set(OBSERVATION_IDS):
        raise RuntimeError("RUNTIME_OBSERVATION_COVERAGE_INVALID")
    normalized = {
        observation_id: _observation(observations[observation_id], observation_id)
        for observation_id in OBSERVATION_IDS
    }
    body = _body(repository, normalized)
    return {**body, "bundleHash": stable_hash(body)}


def validate_bundle(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != TOP_FIELDS:
        raise RuntimeError("RUNTIME_OBSERVATION_BUNDLE_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("RUNTIME_OBSERVATION_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False:
        raise RuntimeError("RUNTIME_OBSERVATION_BOUNDARY_INVALID")
    expected = build_bundle(value.get("repository"), value.get("observations"))
    if value != expected:
        raise RuntimeError("RUNTIME_OBSERVATION_BUNDLE_MISMATCH")
    return value


def load_bundle(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("RUNTIME_OBSERVATION_BUNDLE_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("RUNTIME_OBSERVATION_BUNDLE_JSON_INVALID") from exc
    return validate_bundle(value)


def observation(bundle: dict[str, Any], observation_id: str) -> dict[str, Any]:
    validate_bundle(bundle)
    if observation_id not in OBSERVATION_IDS:
        raise RuntimeError("RUNTIME_OBSERVATION_ID_UNKNOWN")
    return copy.deepcopy(bundle["observations"][observation_id])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="runtime-observations",
        description="Validate closed read-only external runtime observations",
    )
    parser.add_argument("command", choices=("validate",))
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = load_bundle(args.path)
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"PASS RuntimeObservationBundle {payload['bundleHash']}")
        return 0
    except (RuntimeError, OSError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

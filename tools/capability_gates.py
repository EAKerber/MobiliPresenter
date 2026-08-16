#!/usr/bin/env python3
"""Read-only capability gate discovery and review planning for MobiliPresenter."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash  # noqa: E402

CAPABILITY_DIR = ROOT / "ops" / "capabilities"
ERROR_EXIT = 2
SUPPORTED_SCHEMA = "CapabilityGates 0.1"
POLICIES = {"experimental", "canonical", "deprecated", "disabled"}
SUPERVISOR_PARTICIPATION = {"active", "isolated"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")



def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"CAPABILITY_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CAPABILITY_JSON_INVALID:{path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CAPABILITY_ROOT_INVALID:{path}")
    return value


def supervisor_participation(value: dict[str, Any]) -> str:
    return value.get("supervisorParticipation", "active")


def validate_capability(value: dict[str, Any], expected_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if value.get("schemaVersion") != SUPPORTED_SCHEMA:
        errors.append("CAPABILITY_SCHEMA_UNSUPPORTED")

    capability_id = value.get("id")
    if not isinstance(capability_id, str) or not ID_RE.fullmatch(capability_id):
        errors.append("CAPABILITY_ID_INVALID")
    elif expected_id is not None and capability_id != expected_id:
        errors.append("CAPABILITY_ID_PATH_MISMATCH")

    if value.get("policy") not in POLICIES:
        errors.append("CAPABILITY_POLICY_INVALID")

    participation = value.get("supervisorParticipation")
    if participation is not None and participation not in SUPERVISOR_PARTICIPATION:
        errors.append("CAPABILITY_SUPERVISOR_PARTICIPATION_INVALID")

    gates = value.get("gates")
    if not isinstance(gates, dict):
        errors.append("CAPABILITY_GATES_INVALID")
        return errors

    backlog = gates.get("backlog")
    next_gates = gates.get("next")
    if not isinstance(backlog, list):
        errors.append("CAPABILITY_BACKLOG_INVALID")
        backlog = []
    if not isinstance(next_gates, list) or any(not isinstance(item, str) or not item for item in next_gates):
        errors.append("CAPABILITY_NEXT_GATES_INVALID")
        next_gates = []

    gate_ids: list[str] = []
    for gate in backlog:
        if not isinstance(gate, dict):
            errors.append("CAPABILITY_GATE_INVALID")
            continue
        gate_id = gate.get("id")
        test = gate.get("test")
        if not isinstance(gate_id, str) or not ID_RE.fullmatch(gate_id):
            errors.append("CAPABILITY_GATE_ID_INVALID")
        else:
            gate_ids.append(gate_id)
        if not isinstance(test, str) or not test.strip():
            errors.append("CAPABILITY_GATE_TEST_INVALID")
        if set(gate) != {"id", "test"}:
            errors.append("CAPABILITY_GATE_FIELDS_INVALID")

    if len(gate_ids) != len(set(gate_ids)):
        errors.append("CAPABILITY_GATE_ID_DUPLICATE")
    if len(next_gates) != len(set(next_gates)):
        errors.append("CAPABILITY_NEXT_GATE_DUPLICATE")
    if any(item not in set(gate_ids) for item in next_gates):
        errors.append("CAPABILITY_NEXT_GATE_NOT_IN_BACKLOG")

    rounds = value.get("roundsWithoutActiveGates")
    maximum = value.get("maxRoundsWithoutActiveGates")
    if type(rounds) is not int or rounds < 0:
        errors.append("CAPABILITY_EMPTY_ROUNDS_INVALID")
    if type(maximum) is not int or maximum < 1:
        errors.append("CAPABILITY_MAX_EMPTY_ROUNDS_INVALID")
    if next_gates and type(rounds) is int and rounds != 0:
        errors.append("CAPABILITY_ACTIVE_GATES_REQUIRE_ZERO_EMPTY_ROUNDS")

    reason = value.get("deferReason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        errors.append("CAPABILITY_DEFER_REASON_INVALID")

    expected_fields = {
        "schemaVersion",
        "id",
        "policy",
        "gates",
        "roundsWithoutActiveGates",
        "maxRoundsWithoutActiveGates",
        "deferReason",
    }
    actual_fields = set(value)
    if actual_fields not in (expected_fields, expected_fields | {"supervisorParticipation"}):
        errors.append("CAPABILITY_FIELDS_INVALID")
    if set(gates) != {"backlog", "next"}:
        errors.append("CAPABILITY_GATES_FIELDS_INVALID")
    return errors


def load_capability(capability_id: str) -> dict[str, Any]:
    if not ID_RE.fullmatch(capability_id):
        raise RuntimeError("CAPABILITY_ID_INVALID")
    path = CAPABILITY_DIR / f"{capability_id}.json"
    value = load_json(path)
    errors = validate_capability(value, expected_id=capability_id)
    if errors:
        raise RuntimeError(f"{errors[0]}:{capability_id}")
    return value


def discover_capabilities() -> list[dict[str, Any]]:
    if not CAPABILITY_DIR.is_dir():
        return []
    discovered: list[dict[str, Any]] = []
    for path in sorted(CAPABILITY_DIR.glob("*.json")):
        value = load_json(path)
        errors = validate_capability(value, expected_id=path.stem)
        if errors:
            raise RuntimeError(f"{errors[0]}:{path.name}")
        discovered.append(value)
    return discovered


def build_review_plan(capability: dict[str, Any]) -> dict[str, Any]:
    errors = validate_capability(capability)
    if errors:
        raise RuntimeError(errors[0])

    next_gates = capability["gates"]["next"]
    rounds = capability["roundsWithoutActiveGates"]
    maximum = capability["maxRoundsWithoutActiveGates"]

    if capability["policy"] != "experimental":
        action = "NO_EXPERIMENTAL_REVIEW"
        reason = "capability policy is not experimental"
    elif next_gates:
        action = "TEST_NEXT_GATES"
        reason = "one or more gates are explicitly active for the next responsible review"
    elif rounds >= maximum:
        action = "REVIEW_EMPTY_LIMIT"
        reason = "maximum consecutive formal reviews without active gates has been reached"
    else:
        action = "REVIEW_EMPTY_ROUND"
        reason = "no gate is active; re-check whether the reason for deferral is still valid"

    body = {
        "schemaVersion": "CapabilityReviewPlan 0.1",
        "id": capability["id"],
        "policy": capability["policy"],
        "action": action,
        "reason": reason,
        "backlog": capability["gates"]["backlog"],
        "nextGates": next_gates,
        "roundsWithoutActiveGates": rounds,
        "maxRoundsWithoutActiveGates": maximum,
        "deferReason": capability["deferReason"],
        "readOnly": True,
    }
    return {**body, "planHash": stable_hash(body)}


def command_list(as_json: bool) -> int:
    values = discover_capabilities()
    payload = {
        "schemaVersion": "CapabilityDiscovery 0.1",
        "capabilities": [
            {
                "id": value["id"],
                "policy": value["policy"],
                "supervisorParticipation": supervisor_participation(value),
                "backlogCount": len(value["gates"]["backlog"]),
                "nextGates": value["gates"]["next"],
                "roundsWithoutActiveGates": value["roundsWithoutActiveGates"],
                "maxRoundsWithoutActiveGates": value["maxRoundsWithoutActiveGates"],
            }
            for value in values
        ],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if not payload["capabilities"]:
            print("CAPABILITIES\n  none")
        for item in payload["capabilities"]:
            print(
                f"{item['id']}: policy={item['policy']} supervisor={item['supervisorParticipation']} "
                f"backlog={item['backlogCount']} next={len(item['nextGates'])} "
                f"empty={item['roundsWithoutActiveGates']}/{item['maxRoundsWithoutActiveGates']}"
            )
    return 0


def command_review_plan(capability_id: str, as_json: bool) -> int:
    plan = build_review_plan(load_capability(capability_id))
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(f"CAPABILITY REVIEW PLAN\n  id: {plan['id']}\n  action: {plan['action']}")
        print(f"  empty rounds: {plan['roundsWithoutActiveGates']}/{plan['maxRoundsWithoutActiveGates']}")
        print(f"  planHash: {plan['planHash']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="capability-gates", description="Read-only capability gate discovery")
    parser.add_argument("command", choices=("list", "review-plan"))
    parser.add_argument("capability_id", nargs="?")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        if args.command == "list":
            if args.capability_id is not None:
                raise RuntimeError("UNEXPECTED_CAPABILITY_ID")
            return command_list(args.as_json)
        if not args.capability_id:
            raise RuntimeError("CAPABILITY_ID_REQUIRED")
        return command_review_plan(args.capability_id, args.as_json)
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

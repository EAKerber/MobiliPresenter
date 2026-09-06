from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from tools import (
    agent_cycle,
    operational_quiescence,
    project_machine,
    reflection_eligibility,
    scheduler_snapshot,
)

APPLICABLE_ROLE = "manager-gitops"
APPLICABLE_INTENT = "inspect-and-plan"
ERROR_EXIT = 2


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("HOSTED_QUIESCENCE_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("HOSTED_QUIESCENCE_INPUT_INVALID")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _slot(context: dict[str, Any], name: str) -> dict[str, Any]:
    slot = context.get(name)
    if (
        not isinstance(slot, dict)
        or slot.get("status") != "PASS"
        or not isinstance(slot.get("value"), dict)
    ):
        raise RuntimeError(f"HOSTED_QUIESCENCE_{name.upper()}_UNAVAILABLE")
    return copy.deepcopy(slot["value"])


def is_applicable(context: dict[str, Any]) -> bool:
    agent_cycle.validate_context(context)
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict):
        raise RuntimeError("HOSTED_QUIESCENCE_SEMANTIC_CONTEXT_INVALID")
    return (
        semantic.get("role") == APPLICABLE_ROLE
        and semantic.get("declaredIntent") == APPLICABLE_INTENT
    )


def build_snapshot_from_context(context: dict[str, Any]) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        raise RuntimeError("HOSTED_QUIESCENCE_NOT_APPLICABLE")
    source_machine = copy.deepcopy(context["projectMachine"])
    routine = _slot(context, "routineInspection")
    maintenance = _slot(context, "maintenanceInspection")
    plan = _slot(context, "schedulerPlan")
    return scheduler_snapshot.build_snapshot(
        source_machine,
        routine,
        maintenance,
        plan,
    )


def derive_sample(
    context: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    readback_machine: dict[str, Any],
    observation_id: str,
    sequence: int,
) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        raise RuntimeError("HOSTED_QUIESCENCE_NOT_APPLICABLE")
    source_machine = copy.deepcopy(context["projectMachine"])
    routine = _slot(context, "routineInspection")
    scheduler_snapshot.validate_snapshot(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
    )
    reflection = reflection_eligibility.build_inspection(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
    )
    sample = operational_quiescence.build_sample(
        snapshot=snapshot,
        reflection=reflection,
        source_machine=source_machine,
        routine_inspection=routine,
        readback_machine=readback_machine,
        observation_id=observation_id,
        sequence=sequence,
    )
    return {
        "snapshot": snapshot,
        "readbackMachine": copy.deepcopy(readback_machine),
        "reflectionEligibility": reflection,
        "sample": sample,
    }


def materialize(
    context: dict[str, Any],
    *,
    observation_id: str,
    sequence: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    if not is_applicable(context):
        return {
            "ok": True,
            "applicable": False,
            "role": context["semanticContext"]["role"],
            "declaredIntent": context["semanticContext"]["declaredIntent"],
        }

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Preserve the same trust boundary as Supervisor Snapshot:
    # source-derived immutable snapshot first, then a fresh live readback.
    snapshot = build_snapshot_from_context(context)
    _write_json(root / "scheduler-snapshot.json", snapshot)

    readback = project_machine.inspect_live()
    _write_json(root / "project-machine-readback.json", readback)

    derived = derive_sample(
        context,
        snapshot=snapshot,
        readback_machine=readback,
        observation_id=observation_id,
        sequence=sequence,
    )
    _write_json(root / "reflection-eligibility.json", derived["reflectionEligibility"])
    _write_json(root / "operational-quiescence-sample.json", derived["sample"])

    sample = derived["sample"]
    return {
        "ok": True,
        "applicable": True,
        "sampleHash": sample["sampleHash"],
        "sampleEligible": sample["sampleEligible"],
        "reflectionStatus": sample["reflectionStatus"],
        "baselineHash": sample["baselineHash"],
        "observationId": sample["observationId"],
        "sequence": sample["sequence"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-quiescence-sampling")
    parser.add_argument("--context", required=True)
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--sequence", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        context = _load_json(args.context)
        value = materialize(
            context,
            observation_id=args.observation_id,
            sequence=args.sequence,
            output_dir=args.output_dir,
        )
        print(json.dumps(value, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "readOnly": True,
                    "semanticAuthority": False,
                    "authorizesMutation": False,
                },
                ensure_ascii=False,
            )
        )
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(run())

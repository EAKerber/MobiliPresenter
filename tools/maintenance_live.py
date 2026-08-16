#!/usr/bin/env python3
"""Compatibility entrypoint: live Maintenance over ProjectMachineInspection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import maintenance_inspect, project_machine

ERROR_EXIT = 2


def inspect():
    machine = project_machine.inspect_live()
    payload = maintenance_inspect.from_project_inspection(machine)
    continuation_data = machine["sensors"]["continuations"]["data"]
    payload["continuationAuthority"] = {
        "available": bool(continuation_data.get("available")),
        "authorityBranch": continuation_data.get("authorityBranch"),
        "authorityHead": continuation_data.get("authorityHead"),
        "count": len(continuation_data.get("items") or []),
    }
    body = {key: value for key, value in payload.items() if key != "inspectionHash"}
    payload["inspectionHash"] = maintenance_inspect.capability_gates.stable_hash(body)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(prog="maintenance-live")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = inspect()
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FAILURE_SCHEMA = "HostedAgentCycleFailure 0.2"
FAILURE_CORE_SCHEMA = "AgentFailureCore 0.1"
ELIGIBLE_CAUSE = {
    "code": "HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID",
    "source": "hosted-agent-cycle-trace",
    "phase": "CLOSE",
}


def qualifies_close_compatibility_recovery(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schemaVersion") != FAILURE_SCHEMA:
        return False
    if value.get("status") not in {"BLOCKED", "UNKNOWN"}:
        return False

    core = value.get("failureCore")
    if not isinstance(core, dict):
        return False
    if core.get("schemaVersion") != FAILURE_CORE_SCHEMA:
        return False
    if core.get("surface") != "AGENT_CYCLE" or core.get("phase") != "CLOSE":
        return False
    if core.get("status") not in {"BLOCKED", "UNKNOWN"}:
        return False
    if core.get("causes") != [ELIGIBLE_CAUSE]:
        return False

    recovery = core.get("recovery")
    if not isinstance(recovery, dict):
        return False
    if recovery.get("observationRetry") != "UNKNOWN":
        return False
    if recovery.get("operationReplay") != "NOT_APPLICABLE":
        return False
    if core.get("mutationState") != "NOT_APPLICABLE":
        return False
    if core.get("lossyProjection") is not False:
        return False
    if core.get("readOnly") is not True:
        return False
    if core.get("semanticAuthority") is not False:
        return False
    if core.get("authorizesMutation") is not False:
        return False
    return True


def _load(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-cycle-close-compat-recovery")
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    return 0 if qualifies_close_compatibility_recovery(_load(args.result)) else 2


if __name__ == "__main__":
    raise SystemExit(main())

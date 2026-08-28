from __future__ import annotations

import copy
import re
from typing import Any

from tools.canonical import stable_hash

FAILURE_CORE_SCHEMA = "AgentFailureCore 0.1"
FAILURE_CORE_FIELDS = {
    "schemaVersion",
    "surface",
    "phase",
    "status",
    "causes",
    "recovery",
    "mutationState",
    "lossyProjection",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "failureCoreHash",
}
CAUSE_FIELDS = {"code", "source", "phase"}
RECOVERY_FIELDS = {"observationRetry", "operationReplay"}

HOSTED_CYCLE_FAILURE_SCHEMA = "HostedAgentCycleFailure 0.2"
HOSTED_CYCLE_FAILURE_FIELDS = {
    "schemaVersion",
    "requestId",
    "commandHash",
    "status",
    "failureCore",
    "failureHash",
}

SURFACES = {
    "AGENT_CYCLE",
    "AGENT_TOOL",
    "REMOTE_CANONICAL",
    "AGENT_WRITE_LEASE",
}
PHASES = {
    "PARSE",
    "BEGIN",
    "RESOLVE",
    "ADMIT",
    "DISPATCH",
    "APPLY",
    "READBACK",
    "CLOSE",
    "TRANSPORT",
}
FAILURE_STATUSES = {"BLOCKED", "UNKNOWN"}
RECOVERY_STATUSES = {"SAFE", "UNSAFE", "UNKNOWN", "NOT_APPLICABLE"}
MUTATION_STATES = {"NOT_APPLICABLE", "NOT_APPLIED", "APPLIED", "UNKNOWN"}

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
SOURCE_RE = re.compile(r"^[a-z][a-z0-9.-]*$")

LEGACY_FAILURES = {
    "HostedAgentCycleFailure 0.1": {
        "surface": "AGENT_CYCLE",
        "source": "hosted-agent-cycle",
        "mutationState": "NOT_APPLICABLE",
        "fields": {
            "schemaVersion", "requestId", "commandHash", "status", "blockers",
            "detail", "semanticAuthority", "authorizesMutation", "failureHash",
        },
    },
    "HostedAgentToolFailure 0.1": {
        "surface": "AGENT_TOOL",
        "source": "hosted-agent-tool",
        "mutationState": "NOT_APPLIED",
        "fields": {
            "schemaVersion", "requestId", "requestHash", "begin", "actor",
            "toolId", "status", "blockers", "detail", "semanticAuthority",
            "authorizesMutation", "failureHash",
        },
    },
    "RemoteCanonicalExecutionFailure 0.1": {
        "surface": "REMOTE_CANONICAL",
        "source": "remote-canonical",
        "mutationState": "UNKNOWN",
        "fields": {
            "schemaVersion", "executionId", "commandHash", "status", "blockers",
            "detail", "semanticAuthority", "authorizesMutation", "failureHash",
        },
    },
    "AgentWriteLeaseFailure 0.1": {
        "surface": "AGENT_WRITE_LEASE",
        "source": "agent-write-lease",
        "mutationState": None,
        "fields": {
            "schemaVersion", "requestId", "requestHash", "action", "begin",
            "actor", "branch", "authorityHead", "status", "blockers",
            "semanticAuthority", "authorizesMutation", "failureHash",
        },
    },
}


class AgentFailureError(RuntimeError):
    pass


def _text(value: Any, pattern: re.Pattern[str], code: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise AgentFailureError(code)
    return value


def _cause(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != CAUSE_FIELDS:
        raise AgentFailureError("AGENT_FAILURE_CAUSE_FIELDS_INVALID")
    code = _text(value.get("code"), CODE_RE, "AGENT_FAILURE_CAUSE_CODE_INVALID")
    source = _text(
        value.get("source"), SOURCE_RE, "AGENT_FAILURE_CAUSE_SOURCE_INVALID"
    )
    phase = value.get("phase")
    if phase not in PHASES:
        raise AgentFailureError("AGENT_FAILURE_CAUSE_PHASE_INVALID")
    return {"code": code, "source": source, "phase": phase}


def validate_failure_core(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FAILURE_CORE_FIELDS:
        raise AgentFailureError("AGENT_FAILURE_CORE_FIELDS_INVALID")
    if value.get("schemaVersion") != FAILURE_CORE_SCHEMA:
        raise AgentFailureError("AGENT_FAILURE_CORE_SCHEMA_UNSUPPORTED")
    if value.get("surface") not in SURFACES:
        raise AgentFailureError("AGENT_FAILURE_CORE_SURFACE_INVALID")
    if value.get("phase") not in PHASES:
        raise AgentFailureError("AGENT_FAILURE_CORE_PHASE_INVALID")
    if value.get("status") not in FAILURE_STATUSES:
        raise AgentFailureError("AGENT_FAILURE_CORE_STATUS_INVALID")

    raw_causes = value.get("causes")
    if not isinstance(raw_causes, list) or not raw_causes:
        raise AgentFailureError("AGENT_FAILURE_CORE_CAUSES_INVALID")
    causes = [_cause(item) for item in raw_causes]
    identities = [(item["code"], item["source"], item["phase"]) for item in causes]
    if len(identities) != len(set(identities)):
        raise AgentFailureError("AGENT_FAILURE_CORE_CAUSES_DUPLICATE")
    if causes != raw_causes:
        raise AgentFailureError("AGENT_FAILURE_CORE_CAUSES_NOT_CANONICAL")

    recovery = value.get("recovery")
    if not isinstance(recovery, dict) or set(recovery) != RECOVERY_FIELDS:
        raise AgentFailureError("AGENT_FAILURE_CORE_RECOVERY_FIELDS_INVALID")
    if any(recovery.get(field) not in RECOVERY_STATUSES for field in RECOVERY_FIELDS):
        raise AgentFailureError("AGENT_FAILURE_CORE_RECOVERY_INVALID")

    mutation_state = value.get("mutationState")
    if mutation_state not in MUTATION_STATES:
        raise AgentFailureError("AGENT_FAILURE_CORE_MUTATION_STATE_INVALID")
    if mutation_state == "UNKNOWN" and value["status"] != "UNKNOWN":
        raise AgentFailureError("AGENT_FAILURE_CORE_POST_WRITE_STATUS_INVALID")
    if (
        recovery["operationReplay"] == "SAFE"
        and mutation_state in {"APPLIED", "UNKNOWN"}
    ):
        raise AgentFailureError("AGENT_FAILURE_CORE_REPLAY_UNSAFE_STATE")

    if not isinstance(value.get("lossyProjection"), bool):
        raise AgentFailureError("AGENT_FAILURE_CORE_LOSSY_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise AgentFailureError("AGENT_FAILURE_CORE_BOUNDARY_INVALID")
    if not isinstance(value.get("failureCoreHash"), str) or not HASH_RE.fullmatch(
        value["failureCoreHash"]
    ):
        raise AgentFailureError("AGENT_FAILURE_CORE_HASH_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "failureCoreHash"
    }
    if value["failureCoreHash"] != stable_hash(core):
        raise AgentFailureError("AGENT_FAILURE_CORE_HASH_MISMATCH")
    return value


def build_failure_core(
    *,
    surface: str,
    phase: str,
    status: str,
    causes: list[dict[str, str]],
    observation_retry: str,
    operation_replay: str,
    mutation_state: str,
    lossy_projection: bool = False,
) -> dict[str, Any]:
    core = {
        "schemaVersion": FAILURE_CORE_SCHEMA,
        "surface": surface,
        "phase": phase,
        "status": status,
        "causes": copy.deepcopy(causes),
        "recovery": {
            "observationRetry": observation_retry,
            "operationReplay": operation_replay,
        },
        "mutationState": mutation_state,
        "lossyProjection": lossy_projection,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "failureCoreHash": stable_hash(core)}
    return validate_failure_core(value)


def _validate_legacy_hash(value: dict[str, Any]) -> None:
    digest = value.get("failureHash")
    if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
        raise AgentFailureError("AGENT_FAILURE_LEGACY_HASH_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "failureHash"
    }
    if digest != stable_hash(core):
        raise AgentFailureError("AGENT_FAILURE_LEGACY_HASH_MISMATCH")


def validate_hosted_cycle_failure(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != HOSTED_CYCLE_FAILURE_FIELDS:
        raise AgentFailureError("HOSTED_AGENT_FAILURE_FIELDS_INVALID")
    if value.get("schemaVersion") != HOSTED_CYCLE_FAILURE_SCHEMA:
        raise AgentFailureError("HOSTED_AGENT_FAILURE_SCHEMA_UNSUPPORTED")
    request_id = value.get("requestId")
    command_hash = value.get("commandHash")
    if request_id is None or command_hash is None:
        if request_id is not None or command_hash is not None:
            raise AgentFailureError("HOSTED_AGENT_FAILURE_CORRELATION_INVALID")
    else:
        if not isinstance(request_id, str) or not request_id.strip():
            raise AgentFailureError("HOSTED_AGENT_FAILURE_REQUEST_ID_INVALID")
        if not isinstance(command_hash, str) or not HASH_RE.fullmatch(command_hash):
            raise AgentFailureError("HOSTED_AGENT_FAILURE_COMMAND_HASH_INVALID")
    if value.get("status") != "BLOCKED":
        raise AgentFailureError("HOSTED_AGENT_FAILURE_STATUS_INVALID")
    failure_core = validate_failure_core(value.get("failureCore"))
    if failure_core["surface"] != "AGENT_CYCLE":
        raise AgentFailureError("HOSTED_AGENT_FAILURE_SURFACE_INVALID")
    digest = value.get("failureHash")
    if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
        raise AgentFailureError("HOSTED_AGENT_FAILURE_HASH_INVALID")
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "failureHash"
    }
    if digest != stable_hash(body):
        raise AgentFailureError("HOSTED_AGENT_FAILURE_HASH_MISMATCH")
    return value


def normalize_legacy_failure(value: Any, *, phase: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentFailureError("AGENT_FAILURE_LEGACY_INVALID")
    descriptor = LEGACY_FAILURES.get(value.get("schemaVersion"))
    if descriptor is None:
        raise AgentFailureError("AGENT_FAILURE_LEGACY_SCHEMA_UNSUPPORTED")
    if set(value) != descriptor["fields"]:
        raise AgentFailureError("AGENT_FAILURE_LEGACY_FIELDS_INVALID")
    if phase not in PHASES:
        raise AgentFailureError("AGENT_FAILURE_CORE_PHASE_INVALID")
    _validate_legacy_hash(value)
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise AgentFailureError("AGENT_FAILURE_LEGACY_BOUNDARY_INVALID")

    raw_status = value.get("status")
    status = raw_status if raw_status in FAILURE_STATUSES else "UNKNOWN"
    mutation_state = descriptor["mutationState"]
    if mutation_state is None:
        mutation_state = "UNKNOWN" if status == "UNKNOWN" else "NOT_APPLIED"
    if mutation_state == "UNKNOWN":
        status = "UNKNOWN"

    raw_blockers = value.get("blockers")
    if (
        isinstance(raw_blockers, list)
        and raw_blockers
        and all(isinstance(item, str) and CODE_RE.fullmatch(item) for item in raw_blockers)
    ):
        codes = list(dict.fromkeys(raw_blockers))
    else:
        codes = ["LEGACY_FAILURE_BLOCKERS_INVALID"]
    causes = [
        {"code": code, "source": descriptor["source"], "phase": phase}
        for code in codes
    ]
    operation_replay = (
        "NOT_APPLICABLE" if mutation_state == "NOT_APPLICABLE" else "UNKNOWN"
    )
    return build_failure_core(
        surface=descriptor["surface"],
        phase=phase,
        status=status,
        causes=causes,
        observation_retry="UNKNOWN",
        operation_replay=operation_replay,
        mutation_state=mutation_state,
        lossy_projection=True,
    )


def normalize_failure(value: Any, *, phase: str | None = None) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("schemaVersion") == FAILURE_CORE_SCHEMA:
        validated = validate_failure_core(value)
        if phase is not None and validated["phase"] != phase:
            raise AgentFailureError("AGENT_FAILURE_CORE_PHASE_MISMATCH")
        return validated
    if isinstance(value, dict) and value.get("schemaVersion") == HOSTED_CYCLE_FAILURE_SCHEMA:
        validated = validate_hosted_cycle_failure(value)
        core = validated["failureCore"]
        if phase is not None and core["phase"] != phase:
            raise AgentFailureError("AGENT_FAILURE_CORE_PHASE_MISMATCH")
        return core
    if phase is None:
        raise AgentFailureError("AGENT_FAILURE_LEGACY_PHASE_REQUIRED")
    return normalize_legacy_failure(value, phase=phase)

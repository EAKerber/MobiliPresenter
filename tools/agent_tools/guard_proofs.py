from __future__ import annotations

import copy
import re
from typing import Any, Callable

from tools import agent_write_lifecycle_guard
from tools import agent_write_ownership
from tools import git_observation
from tools import remote_canonical_execution as remote
from tools.agent_tools import contracts
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

GIT_CAS_SCHEMA = "GitCasGuardProof 0.1"
PROOF_SET_SCHEMA = "AgentToolGuardProofSet 0.1"
_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _require_hash(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise RuntimeError(code)
    return value


def _require_git_sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _command_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    contracts.validate_plan(plan)
    concrete = plan.get("concrete")
    if (
        not isinstance(concrete, dict)
        or concrete.get("kind") != "remote-canonical-command"
    ):
        raise RuntimeError("AGENT_TOOL_GUARD_COMMAND_REQUIRED")
    command = concrete.get("command")
    if not isinstance(command, dict):
        raise RuntimeError("AGENT_TOOL_GUARD_COMMAND_REQUIRED")
    remote.validate_command(command)
    if concrete.get("commandHash") != remote.command_hash(command):
        raise RuntimeError("AGENT_TOOL_GUARD_COMMAND_HASH_MISMATCH")
    return command


def validate_git_cas_proof(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "requestHash",
        "planHash",
        "commandHash",
        "actor",
        "target",
        "expected",
        "observed",
        "status",
        "readOnly",
        "semanticAuthority",
        "authorizesMutation",
        "proofHash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_FIELDS_INVALID")
    if value.get("schemaVersion") != GIT_CAS_SCHEMA:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_SCHEMA_UNSUPPORTED")
    for field in ("requestHash", "planHash", "commandHash", "proofHash"):
        _require_hash(value.get(field), "GIT_CAS_GUARD_PROOF_HASH_INVALID")
    actor = value.get("actor")
    if not isinstance(actor, dict) or set(actor) != {
        "role",
        "workerId",
        "sessionId",
    }:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_ACTOR_INVALID")
    if any(not isinstance(actor[item], str) or not actor[item] for item in actor):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_ACTOR_INVALID")
    target = value.get("target")
    if not isinstance(target, dict) or set(target) != {"branch", "path"}:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_TARGET_INVALID")
    if not isinstance(target["branch"], str) or not isinstance(target["path"], str):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_TARGET_INVALID")
    expected = value.get("expected")
    observed = value.get("observed")
    if not isinstance(expected, dict) or not isinstance(observed, dict):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_OBSERVATION_INVALID")
    if set(expected) not in ({"branchHead"}, {"branchHead", "blobSha"}):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_EXPECTED_INVALID")
    if set(observed) != {"branchHead", "blobSha"}:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_OBSERVATION_INVALID")
    _require_git_sha(
        expected.get("branchHead"), "GIT_CAS_GUARD_PROOF_EXPECTED_INVALID"
    )
    _require_git_sha(
        observed.get("branchHead"), "GIT_CAS_GUARD_PROOF_OBSERVATION_INVALID"
    )
    if expected.get("blobSha") is not None:
        _require_git_sha(
            expected.get("blobSha"), "GIT_CAS_GUARD_PROOF_EXPECTED_INVALID"
        )
    if observed.get("blobSha") is not None:
        _require_git_sha(
            observed.get("blobSha"), "GIT_CAS_GUARD_PROOF_OBSERVATION_INVALID"
        )
    if value.get("status") != "PASS" or value.get("readOnly") is not True:
        raise RuntimeError("GIT_CAS_GUARD_PROOF_STATUS_INVALID")
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_MUST_NOT_AUTHORIZE")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "proofHash"
    }
    if value["proofHash"] != stable_hash(core):
        raise RuntimeError("GIT_CAS_GUARD_PROOF_HASH_MISMATCH")
    return value


def validate_agent_write_lease_proof(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "policy",
        "actor",
        "branch",
        "requiredOwnedResources",
        "conflictCheckedResources",
        "authorityHead",
        "authorityNow",
        "matchedLeases",
        "status",
        "readOnly",
        "semanticAuthority",
        "authorizesMutation",
        "proofHash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_FIELDS_INVALID")
    if value.get("schemaVersion") != agent_write_ownership.PROOF_SCHEMA:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_SCHEMA_UNSUPPORTED")
    if value.get("policy") != agent_write_ownership.POLICY_ID:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_POLICY_INVALID")
    actor = value.get("actor")
    if not isinstance(actor, dict) or set(actor) != {
        "role",
        "workerId",
        "sessionId",
    }:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_ACTOR_INVALID")
    if not isinstance(value.get("branch"), str) or not value["branch"]:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_BRANCH_INVALID")
    for field in (
        "requiredOwnedResources",
        "conflictCheckedResources",
        "matchedLeases",
    ):
        if not isinstance(value.get(field), list):
            raise RuntimeError("AGENT_WRITE_LEASE_PROOF_COLLECTION_INVALID")
    _require_git_sha(
        value.get("authorityHead"), "AGENT_WRITE_LEASE_PROOF_AUTHORITY_INVALID"
    )
    if not isinstance(value.get("authorityNow"), str) or not value["authorityNow"]:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_AUTHORITY_INVALID")
    if value.get("status") != "PASS" or value.get("readOnly") is not True:
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_STATUS_INVALID")
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_MUST_NOT_AUTHORIZE")
    _require_hash(value.get("proofHash"), "AGENT_WRITE_LEASE_PROOF_HASH_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "proofHash"
    }
    if value["proofHash"] != stable_hash(core):
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_HASH_MISMATCH")
    return value


def prove_git_cas(
    plan: dict[str, Any], *, transport: Any | None = None
) -> dict[str, Any]:
    command = _command_from_plan(plan)
    if (
        command["kind"] != "git-direct"
        or command["target"]["operation"] == "create-branch"
    ):
        raise RuntimeError("AGENT_TOOL_GIT_CAS_ROUTE_UNSUPPORTED")
    target = command["target"]
    observed_full = git_observation.observe_file(
        target["branch"], target["path"], transport=transport
    )
    expected = copy.deepcopy(command["expected"])
    observed = {
        "branchHead": observed_full["branchHead"],
        "blobSha": observed_full["blobSha"],
    }
    if observed["branchHead"] != expected["branchHead"]:
        raise RuntimeError("AGENT_TOOL_GIT_CAS_BRANCH_DRIFT")
    operation = target["operation"]
    if operation == "create-file":
        if observed["blobSha"] is not None:
            raise RuntimeError("AGENT_TOOL_GIT_CAS_PATH_EXISTS")
    elif observed["blobSha"] != expected.get("blobSha"):
        raise RuntimeError("AGENT_TOOL_GIT_CAS_BLOB_DRIFT")
    core = {
        "schemaVersion": GIT_CAS_SCHEMA,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "commandHash": remote.command_hash(command),
        "actor": copy.deepcopy(plan["actor"]),
        "target": {"branch": target["branch"], "path": target["path"]},
        "expected": expected,
        "observed": observed,
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    proof = {**core, "proofHash": stable_hash(core)}
    return validate_git_cas_proof(proof)


def prove_coordination_lease_owned(
    plan: dict[str, Any],
    *,
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    command = _command_from_plan(plan)
    carrier = transport or GhApiTransport()
    authority = (
        authority_factory(carrier)
        if authority_factory is not None
        else GitHubCoordinationAuthority(transport=carrier)
    )
    proof = agent_write_ownership.prove_agent_write_ownership(command, authority)
    validate_agent_write_lease_proof(proof)
    if (
        proof["actor"] != plan["actor"]
        or proof["branch"] != plan["target"].get("branch")
    ):
        raise RuntimeError("AGENT_WRITE_LEASE_PROOF_PLAN_MISMATCH")
    return proof


def validate_proof_set(
    value: Any, *, plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "requestHash",
        "planHash",
        "actor",
        "target",
        "proofs",
        "status",
        "readOnly",
        "semanticAuthority",
        "authorizesMutation",
        "proofSetHash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_FIELDS_INVALID")
    if value.get("schemaVersion") != PROOF_SET_SCHEMA:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_SCHEMA_UNSUPPORTED")
    for field in ("requestHash", "planHash", "proofSetHash"):
        _require_hash(value.get(field), "AGENT_TOOL_GUARD_PROOF_SET_HASH_INVALID")
    if not isinstance(value.get("actor"), dict) or not isinstance(
        value.get("target"), dict
    ):
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_BINDING_INVALID")
    proofs = value.get("proofs")
    if not isinstance(proofs, dict):
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PROOFS_INVALID")
    for guard, proof in proofs.items():
        if guard == "agent-write-lifecycle-bound":
            agent_write_lifecycle_guard.validate_active_binding_proof(proof)
        elif guard == "git-cas":
            validate_git_cas_proof(proof)
        elif guard == "coordination-lease-owned":
            validate_agent_write_lease_proof(proof)
        else:
            raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_GUARD_UNKNOWN")
    if value.get("status") != "PASS" or value.get("readOnly") is not True:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_STATUS_INVALID")
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_MUST_NOT_AUTHORIZE")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "proofSetHash"
    }
    if value["proofSetHash"] != stable_hash(core):
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_HASH_MISMATCH")
    if plan is not None:
        contracts.validate_plan(plan)
        if (
            value["requestHash"] != plan["requestHash"]
            or value["planHash"] != plan["planHash"]
        ):
            raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH")
        if value["actor"] != plan["actor"] or value["target"] != plan["target"]:
            raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH")
        if set(proofs) != set(plan["guards"]):
            raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_GUARDS_MISMATCH")
        command = _command_from_plan(plan)
        if "git-cas" in proofs:
            cas = proofs["git-cas"]
            if (
                cas["requestHash"] != plan["requestHash"]
                or cas["planHash"] != plan["planHash"]
                or cas["commandHash"] != remote.command_hash(command)
                or cas["actor"] != plan["actor"]
            ):
                raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH")
        if "coordination-lease-owned" in proofs:
            lease = proofs["coordination-lease-owned"]
            if (
                lease["actor"] != plan["actor"]
                or lease["branch"] != plan["target"].get("branch")
            ):
                raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH")
        if "agent-write-lifecycle-bound" in proofs:
            lifecycle_proof = proofs["agent-write-lifecycle-bound"]
            if (
                lifecycle_proof["requestHash"] != plan["requestHash"]
                or lifecycle_proof["planHash"] != plan["planHash"]
                or lifecycle_proof["actor"] != plan["actor"]
                or lifecycle_proof["branch"] != plan["target"].get("branch")
            ):
                raise RuntimeError("AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH")
    return value

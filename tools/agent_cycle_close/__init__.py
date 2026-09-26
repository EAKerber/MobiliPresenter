from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from tools import (
    agent_cycle, git_mutation_bundle, git_mutation_plan, project_machine,
    runtime_capabilities, runtime_observations, transition_protocol,
)
from tools.canonical import stable_hash

DELTA_SCHEMA = "AgentCycleDelta 0.1"
RECEIPT_SCHEMA = "AgentCycleReceipt 0.1"
READBACK_SCHEMA = "AgentCycleAggregateReadback 0.1"
CLOSURE_SCHEMA = "AgentCycleClosure 0.1"
EVIDENCE_KINDS = {
    "transition-receipt",
    "git-mutation-bundle-readback",
    "git-mutation-plan-readback",
    "agent-cycle-noninterference-readback",
}
NONINTERFERENCE_SCHEMA = "AgentCycleNonInterferenceReadback 0.2"
LEGACY_NONINTERFERENCE_SCHEMA = "AgentCycleNonInterferenceReadback 0.1"
RECEIPT_STATUSES = {"PASS", "UNKNOWN", "BLOCKED"}


def _hash_body(value: dict[str, Any], hash_field: str) -> str:
    return stable_hash({key: deepcopy(item) for key, item in value.items() if key != hash_field})


def _sorted_unique_strings(value: Any, code: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RuntimeError(code)
    if len(value) != len(set(value)):
        raise RuntimeError(code)
    return sorted(value)


def build_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    agent_cycle.validate_context(before)
    agent_cycle.validate_context(after)
    if before["repository"] != after["repository"]:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REPOSITORY_MISMATCH")
    if before["semanticContext"] != after["semanticContext"]:
        raise RuntimeError("AGENT_CYCLE_CLOSE_CONTEXT_MISMATCH")
    if before["projectMachine"]["scope"] != after["projectMachine"]["scope"]:
        raise RuntimeError("AGENT_CYCLE_CLOSE_SCOPE_MISMATCH")
    if (
        before.get("schemaVersion") == agent_cycle.SCHEMA_VERSION
        and after.get("schemaVersion") == agent_cycle.SCHEMA_VERSION
        and before.get("workRef") != after.get("workRef")
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_WORK_REF_MISMATCH")

    durable: list[dict[str, Any]] = []
    if before["baseline"]["projectStateHash"] != after["baseline"]["projectStateHash"]:
        durable.append({
            "kind": "project-state",
            "before": before["baseline"]["projectStateHash"],
            "after": after["baseline"]["projectStateHash"],
        })
    before_heads = before["baseline"]["sourceHeads"]
    after_heads = after["baseline"]["sourceHeads"]
    for name in sorted(set(before_heads) | set(after_heads)):
        left = before_heads.get(name) or {}
        right = after_heads.get(name) or {}
        if left != right:
            durable.append({
                "kind": "source-head",
                "name": name,
                "branch": right.get("branch") or left.get("branch"),
                "before": left.get("sha"),
                "after": right.get("sha"),
            })

    derived: list[dict[str, Any]] = []
    ignored = {"baselineHash", "projectStateHash", "sourceHeads"}
    for key in sorted((set(before["baseline"]) | set(after["baseline"])) - ignored):
        left = before["baseline"].get(key)
        right = after["baseline"].get(key)
        if left != right:
            derived.append({"artifact": key, "before": left, "after": right})

    before_unknowns = set(before["blockingUnknowns"])
    after_unknowns = set(after["blockingUnknowns"])
    body = {
        "schemaVersion": DELTA_SCHEMA,
        "cycleId": before["cycleId"],
        "beforeContextHash": before["contextHash"],
        "afterContextHash": after["contextHash"],
        "beforeBaselineHash": before["baseline"]["baselineHash"],
        "afterBaselineHash": after["baseline"]["baselineHash"],
        "durableChanges": durable,
        "derivedChanges": derived,
        "blockingUnknownsAdded": sorted(after_unknowns - before_unknowns),
        "blockingUnknownsResolved": sorted(before_unknowns - after_unknowns),
        "beforeStatus": before["status"],
        "afterStatus": after["status"],
        "changed": bool(
            durable
            or derived
            or before_unknowns != after_unknowns
            or before["status"] != after["status"]
        ),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "deltaHash": stable_hash(body)}


def validate_delta(value: Any, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_DELTA_INVALID")
    expected = build_delta(before, after)
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_DELTA_MISMATCH")
    return value


def _validate_git_plan_readback(plan: dict[str, Any], observed: Any) -> dict[str, Any]:
    git_mutation_plan.validate(plan)
    if not isinstance(observed, dict):
        raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_INVALID")
    expected = plan["readback"]
    kind = expected["kind"]
    if observed.get("kind") != kind or observed.get("status") != "PASS":
        raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_INVALID")
    if kind == "branch-head":
        if observed.get("branch") != expected["branch"] or observed.get("sha") != expected["expectedSha"]:
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "open-pr":
        if (
            observed.get("head") != expected["head"]
            or observed.get("base") != expected["base"]
            or observed.get("headSha") != expected["expectedHeadSha"]
            or observed.get("state") != "open"
        ):
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "merged-pr":
        if (
            observed.get("prNumber") != expected["prNumber"]
            or observed.get("headSha") != expected["expectedHeadSha"]
            or observed.get("base") != expected["expectedBase"]
            or observed.get("merged") is not True
        ):
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
        merge_sha = observed.get("mergeCommitSha")
        if not isinstance(merge_sha, str) or not merge_sha:
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "file-content":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("path") != expected["path"]
            or observed.get("contentSha256") != expected["expectedContentSha256"]
        ):
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "file-absent":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("path") != expected["path"]
            or observed.get("absent") is not True
        ):
            raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_MISMATCH")
    else:
        raise RuntimeError("AGENT_CYCLE_GIT_PLAN_READBACK_KIND_UNSUPPORTED")
    return observed



def _source_head_change(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "name", "branch", "before", "after"}:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_CHANGE_INVALID")
    if value.get("kind") != "source-head":
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_CHANGE_INVALID")
    for key in ("name", "branch", "before", "after"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_CHANGE_INVALID")
    return deepcopy(value)


def _verify_noninterference_evidence(item: dict[str, Any]) -> dict[str, Any]:
    schema = item.get("schemaVersion")
    base_fields = {
        "kind", "schemaVersion", "cycleId", "workId", "workBranch",
        "workPrNumber", "workStateHash", "coveredChanges",
        "continuationReadback", "controlReadback", "readOnly",
        "semanticAuthority", "authorizesMutation", "evidenceHash",
    }
    fields = base_fields if schema == LEGACY_NONINTERFERENCE_SCHEMA else base_fields | {"coordinationReadback"}
    if set(item) != fields or schema not in {LEGACY_NONINTERFERENCE_SCHEMA, NONINTERFERENCE_SCHEMA}:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    if (
        item.get("kind") != "agent-cycle-noninterference-readback"
        or not isinstance(item.get("cycleId"), str)
        or not isinstance(item.get("workId"), str)
        or not isinstance(item.get("workBranch"), str)
        or item.get("workBranch") == "main"
        or not isinstance(item.get("workStateHash"), str)
        or len(item["workStateHash"]) != 64
        or item.get("readOnly") is not True
        or item.get("semanticAuthority") is not False
        or item.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    work_pr = item.get("workPrNumber")
    if work_pr is not None and (
        not isinstance(work_pr, int) or isinstance(work_pr, bool) or work_pr <= 0
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")

    covered = item.get("coveredChanges")
    if not isinstance(covered, list):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    changes = [_source_head_change(change) for change in covered]
    by_name = {change["name"]: change for change in changes}
    expected = {"continuation", "control", "inspection"}
    coordination_readback = None if schema == LEGACY_NONINTERFERENCE_SCHEMA else item.get("coordinationReadback")
    if coordination_readback is not None:
        expected.add("coordination")
    if len(by_name) != len(changes) or set(by_name) != expected or len(changes) != len(expected):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    continuation = by_name["continuation"]
    control = by_name["control"]
    inspection = by_name["inspection"]
    coordination = by_name.get("coordination")
    if (
        continuation["branch"] != "coordination/continuations"
        or control["branch"] != "main"
        or inspection["branch"] != "main"
        or (coordination is not None and coordination["branch"] != "coordination/leases")
        or control["before"] != inspection["before"]
        or control["after"] != inspection["after"]
        or control["before"] == control["after"]
        or continuation["before"] == continuation["after"]
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")

    continuation_readback = item.get("continuationReadback")
    if not isinstance(continuation_readback, dict) or set(continuation_readback) != {
        "branch", "before", "after", "workPath", "changedPaths"
    }:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    changed_paths = continuation_readback.get("changedPaths")
    expected_work_path = f"ops/continuations/{item['workId']}.json"
    if (
        continuation_readback.get("branch") != continuation["branch"]
        or continuation_readback.get("before") != continuation["before"]
        or continuation_readback.get("after") != continuation["after"]
        or continuation_readback.get("workPath") != expected_work_path
        or not isinstance(changed_paths, list)
        or any(not isinstance(path, str) or not path for path in changed_paths)
        or changed_paths != sorted(set(changed_paths))
        or expected_work_path in changed_paths
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")

    if schema == NONINTERFERENCE_SCHEMA:
        if coordination is None:
            if coordination_readback is not None:
                raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
        else:
            if not isinstance(coordination_readback, dict) or set(coordination_readback) != {
                "branch", "before", "after", "workBranch", "states"
            }:
                raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
            states = coordination_readback.get("states")
            if (
                coordination_readback.get("branch") != coordination["branch"]
                or coordination_readback.get("before") != coordination["before"]
                or coordination_readback.get("after") != coordination["after"]
                or coordination_readback.get("workBranch") != item["workBranch"]
                or not isinstance(states, list)
                or len(states) < 2
                or any(
                    not isinstance(state, dict)
                    or set(state) != {"sha", "bindingHash"}
                    or not isinstance(state.get("sha"), str)
                    or not isinstance(state.get("bindingHash"), str)
                    or len(state["bindingHash"]) != 64
                    for state in states
                )
                or states[0]["sha"] != coordination["before"]
                or states[-1]["sha"] != coordination["after"]
                or len({state["bindingHash"] for state in states}) != 1
            ):
                raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")

    control_readback = item.get("controlReadback")
    if not isinstance(control_readback, dict) or set(control_readback) != {
        "branch", "before", "after", "mergedPullRequests"
    }:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    pulls = control_readback.get("mergedPullRequests")
    if (
        control_readback.get("branch") != "main"
        or control_readback.get("before") != control["before"]
        or control_readback.get("after") != control["after"]
        or not isinstance(pulls, list)
        or not pulls
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
    for pull in pulls:
        if not isinstance(pull, dict) or set(pull) != {
            "commitSha", "prNumber", "headBranch", "baseSha"
        }:
            raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")
        if (
            not isinstance(pull.get("commitSha"), str)
            or not isinstance(pull.get("baseSha"), str)
            or not isinstance(pull.get("headBranch"), str)
            or not pull["headBranch"]
            or pull["headBranch"] == item["workBranch"]
            or not isinstance(pull.get("prNumber"), int)
            or isinstance(pull.get("prNumber"), bool)
            or pull["prNumber"] <= 0
            or (work_pr is not None and pull["prNumber"] == work_pr)
        ):
            raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_INVALID")

    body = {key: deepcopy(value) for key, value in item.items() if key != "evidenceHash"}
    if item.get("evidenceHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_EVIDENCE_HASH_MISMATCH")
    return deepcopy(item)

def _context_work_item(context: Any, work_id: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_CONTEXT_INVALID")
    machine = context.get("projectMachine")
    sensors = machine.get("sensors") if isinstance(machine, dict) else None
    continuation_sensor = sensors.get("continuations") if isinstance(sensors, dict) else None
    data = continuation_sensor.get("data") if isinstance(continuation_sensor, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_WORK_UNAVAILABLE")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == work_id]
    if len(matches) != 1:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_WORK_UNAVAILABLE")
    return deepcopy(matches[0])


def _validate_noninterference_binding(
    evidence: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    if evidence.get("kind") != "agent-cycle-noninterference-readback":
        return
    before_ref = before.get("workRef")
    after_ref = after.get("workRef")
    work_id = evidence["workId"]
    if (
        not isinstance(before_ref, dict)
        or before_ref.get("workId") != work_id
        or after_ref != before_ref
        or evidence.get("cycleId") != before.get("cycleId")
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_BINDING_MISMATCH")
    before_work = _context_work_item(before, work_id)
    after_work = _context_work_item(after, work_id)
    if before_work != after_work:
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_WORK_CHANGED")
    if (
        before_work.get("branch") != evidence.get("workBranch")
        or before_work.get("prNumber") != evidence.get("workPrNumber")
        or stable_hash(before_work) != evidence.get("workStateHash")
    ):
        raise RuntimeError("AGENT_CYCLE_NONINTERFERENCE_BINDING_MISMATCH")


def verify_evidence(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict) or item.get("kind") not in EVIDENCE_KINDS:
        raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_INVALID")
    kind = item["kind"]
    if kind == "agent-cycle-noninterference-readback":
        return _verify_noninterference_evidence(item)
    if kind == "transition-receipt":
        if set(item) != {"kind", "plan", "receipt"}:
            raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_FIELDS_INVALID")
        plan = transition_protocol.validate_plan(item["plan"])
        receipt = transition_protocol.validate_receipt(item["receipt"], plan)
        body = {
            "kind": kind,
            "domain": receipt["domain"],
            "action": receipt["action"],
            "authority": deepcopy(receipt["authority"]),
            "planHash": receipt["planHash"],
            "readbackHash": receipt["receiptHash"],
        }
    elif kind == "git-mutation-bundle-readback":
        if set(item) != {"kind", "bundle", "providerReadback"}:
            raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_FIELDS_INVALID")
        bundle = git_mutation_bundle.validate_bundle(item["bundle"])
        readback = git_mutation_bundle.verify_readback(bundle, item["providerReadback"])
        body = {
            "kind": kind,
            "branch": readback["branch"],
            "changedPaths": readback["changedPaths"],
            "bundleHash": readback["bundleHash"],
            "readbackHash": readback["readbackHash"],
        }
    else:
        if set(item) != {"kind", "plan", "observed"}:
            raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_FIELDS_INVALID")
        plan = git_mutation_plan.validate(item["plan"])
        observed = _validate_git_plan_readback(plan, item["observed"])
        body = {
            "kind": kind,
            "operation": plan["operation"],
            "target": deepcopy(plan["target"]),
            "base": plan["preconditions"].get("expectedBase"),
            "planHash": plan["planHash"],
            "observedHash": stable_hash(observed),
        }
    return {**body, "evidenceHash": stable_hash(body)}


def _authority_contains_branch(authority: Any, branch: str | None) -> bool:
    if not branch or not isinstance(authority, dict):
        return False
    locator = authority.get("locator")
    return isinstance(locator, dict) and branch in {value for value in locator.values() if isinstance(value, str)}


def _evidence_covers(change: dict[str, Any], evidence: dict[str, Any]) -> bool:
    if evidence.get("kind") == "agent-cycle-noninterference-readback":
        return any(change == item for item in evidence["coveredChanges"])
    if change["kind"] == "project-state":
        return evidence.get("kind") == "transition-receipt" and evidence.get("domain") == "project-state"
    branch = change.get("branch")
    if evidence.get("kind") == "transition-receipt":
        return _authority_contains_branch(evidence.get("authority"), branch)
    if evidence.get("kind") == "git-mutation-bundle-readback":
        return evidence.get("branch") == branch
    if evidence.get("kind") != "git-mutation-plan-readback":
        return False
    operation = evidence.get("operation")
    target = evidence.get("target") or {}
    if operation in {
        "create-branch",
        "update-ref",
        "create-file",
        "update-file",
        "delete-file",
        "mutate-files",
    }:
        return target.get("branch") == branch
    if operation == "merge-pr":
        # A successful merge is the direct readback for the PR base branch movement.
        return branch is not None and branch == evidence.get("base")
    return False


def build_receipt(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    delta = build_delta(before, after)
    verified = [verify_evidence(item) for item in (evidence or [])]
    verified.sort(key=lambda item: item["evidenceHash"])
    if len({item["evidenceHash"] for item in verified}) != len(verified):
        raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_DUPLICATE")
    for item in verified:
        _validate_noninterference_binding(item, before, after)

    uncovered: list[str] = []
    covered: list[str] = []
    for index, change in enumerate(delta["durableChanges"]):
        change_id = f"{change['kind']}:{change.get('name') or 'project-state'}:{index}"
        if any(_evidence_covers(change, item) for item in verified):
            covered.append(change_id)
        else:
            uncovered.append(change_id)

    blockers: list[str] = []
    if uncovered:
        blockers.append("UNATTRIBUTED_DURABLE_DELTA")
    if after["status"] == "UNKNOWN":
        blockers.append("AFTER_CONTEXT_UNKNOWN")
    elif after["status"] == "BLOCKED":
        blockers.append("AFTER_CONTEXT_BLOCKED")
    status = (
        "BLOCKED"
        if after["status"] == "BLOCKED"
        else ("UNKNOWN" if blockers else "PASS")
    )
    readback_core = {
        "schemaVersion": READBACK_SCHEMA,
        "projectStateHash": after["baseline"]["projectStateHash"],
        "sourceHeads": deepcopy(after["baseline"]["sourceHeads"]),
        "coveredDurableChanges": covered,
        "uncoveredDurableChanges": uncovered,
        "evidenceCount": len(verified),
        "status": "PASS" if not uncovered else "UNKNOWN",
    }
    aggregate = {**readback_core, "readbackHash": stable_hash(readback_core)}
    body = {
        "schemaVersion": RECEIPT_SCHEMA,
        "cycleId": before["cycleId"],
        "beforeContextHash": before["contextHash"],
        "afterContextHash": after["contextHash"],
        "delta": delta,
        "evidence": verified,
        "aggregateReadback": aggregate,
        "status": status,
        "blockers": sorted(set(blockers)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "receiptHash": stable_hash(body)}


def validate_receipt(
    value: Any,
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_RECEIPT_INVALID")
    expected = build_receipt(before, after, evidence=evidence)
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_RECEIPT_MISMATCH")
    return value


def _load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_INPUT_INVALID") from exc


def _runtime_inspection(runtime_providers: str | None = None) -> dict[str, Any]:
    providers = runtime_capabilities.local_provider_observations()
    if runtime_providers:
        providers = runtime_capabilities.merge_provider_observations(
            providers,
            runtime_capabilities.load_provider_observations(Path(runtime_providers)),
        )
    return runtime_capabilities.build_inspection(providers)


def _machine(scope: str, observations_path: str | None = None) -> dict[str, Any]:
    if scope == "local":
        if observations_path:
            raise RuntimeError("AGENT_CLOSE_OBSERVATIONS_REQUIRE_LIVE")
        return project_machine.inspect_local()
    if scope == "base":
        if observations_path:
            raise RuntimeError("AGENT_CLOSE_OBSERVATIONS_REQUIRE_LIVE")
        return project_machine.inspect_base()
    if scope != "live":
        raise RuntimeError("AGENT_CLOSE_MACHINE_SCOPE_INVALID")
    observations = runtime_observations.load_bundle(observations_path) if observations_path else None
    return project_machine.inspect_live(observations)


def load_evidence(paths: list[str] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths or []:
        value = _load_json(path)
        if isinstance(value, dict):
            items.append(value)
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            items.extend(value)
        else:
            raise RuntimeError("AGENT_CYCLE_CLOSE_EVIDENCE_DOCUMENT_INVALID")
    return items


def close_from_files(
    *,
    context_path: str,
    machine_scope: str | None = None,
    observations_path: str | None = None,
    runtime_providers: str | None = None,
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    before = _load_json(context_path)
    agent_cycle.validate_context(before)
    observed_scope = before["projectMachine"]["scope"]
    scope = machine_scope or observed_scope
    if scope != observed_scope:
        raise RuntimeError("AGENT_CYCLE_CLOSE_SCOPE_MISMATCH")
    machine = _machine(scope, observations_path)
    runtime = _runtime_inspection(runtime_providers)
    semantic = before["semanticContext"]
    after = agent_cycle.build_context(
        role=semantic["role"],
        declared_intent=semantic["declaredIntent"],
        lifecycle_phase=semantic["lifecyclePhase"],
        objects=semantic["objects"],
        operations=semantic["operations"],
        scopes=semantic["scope"],
        machine=machine,
        runtime_inspection=runtime,
        work_ref=(
            before.get("workRef")
            if before.get("schemaVersion") == agent_cycle.SCHEMA_VERSION
            else None
        ),
    )
    evidence = load_evidence(evidence_paths)
    receipt = build_receipt(before, after, evidence=evidence)
    body = {
        "schemaVersion": CLOSURE_SCHEMA,
        "cycleId": before["cycleId"],
        "beforeContextHash": before["contextHash"],
        "afterContext": after,
        "receipt": receipt,
        "status": receipt["status"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "closureHash": stable_hash(body)}


def validate_closure(value: Any, before: dict[str, Any], *, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_CLOSURE_INVALID")
    if value.get("schemaVersion") != CLOSURE_SCHEMA:
        raise RuntimeError("AGENT_CYCLE_CLOSURE_SCHEMA_UNSUPPORTED")
    after = value.get("afterContext")
    agent_cycle.validate_context(before); agent_cycle.validate_context(after)
    validate_receipt(value.get("receipt"), before, after, evidence=evidence)
    if value.get("cycleId") != before["cycleId"] or value.get("beforeContextHash") != before["contextHash"]:
        raise RuntimeError("AGENT_CYCLE_CLOSURE_CONTEXT_MISMATCH")
    if value.get("status") != value["receipt"]["status"]:
        raise RuntimeError("AGENT_CYCLE_CLOSURE_STATUS_MISMATCH")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_CYCLE_CLOSURE_BOUNDARY_INVALID")
    if value.get("closureHash") != _hash_body(value, "closureHash"):
        raise RuntimeError("AGENT_CYCLE_CLOSURE_HASH_MISMATCH")
    return value


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="agent close")
    parser.add_argument("--context", required=True)
    parser.add_argument("--machine-scope", choices=("local", "base", "live"))
    parser.add_argument("--observations")
    parser.add_argument("--runtime-providers")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = close_from_files(
            context_path=args.context,
            machine_scope=args.machine_scope,
            observations_path=args.observations,
            runtime_providers=args.runtime_providers,
            evidence_paths=args.evidence,
        )
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            receipt = payload["receipt"]
            print(
                "AGENT CYCLE CLOSE\n"
                f"  cycle: {payload['cycleId']}\n"
                f"  status: {payload['status']}\n"
                f"  durable-changes: {len(receipt['delta']['durableChanges'])}\n"
                f"  uncovered: {len(receipt['aggregateReadback']['uncoveredDurableChanges'])}\n"
                f"  receipt: {receipt['receiptHash']}"
            )
        if payload["status"] == "BLOCKED":
            return 2
        if payload["status"] == "UNKNOWN":
            return 1
        return 0
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

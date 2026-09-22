#!/usr/bin/env python3
"""In-house governed mutation counter with pull-based evidence windows.

This module adds no authority. It composes canonical Work re-entry, an exact
AgentCycleHandle, the existing Agent Tool policy/resolver, the existing write
lifecycle guard and the shared governed mutation host. Detailed evidence is
materialized as a workflow artifact; the service result carries only summary
and hash-bound window locators.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    agent_cycle,
    agent_reentry_guidance,
    git_observation,
    hosted_agent_cycle,
    hosted_agent_tool,
    hosted_cycle_handle,
    hosted_issue_bus,
    remote_canonical_execution as remote,
)
from tools.agent_tools import contracts, mutation_host, resolver, target_policy
from tools.canonical import stable_hash
from tools.coordination_remote import ApiError, GhApiTransport

REPOSITORY = "EAKerber/MobiliPresenter"
BUS_TITLE = hosted_agent_cycle.BUS_TITLE
REQUEST_MARKER = "MOBILIPRESENTER_GOVERNED_MUTATION_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_GOVERNED_MUTATION_RESULT_V0_1"
REQUEST_SCHEMA = "GovernedMutationServiceRequest 0.1"
PREPARATION_SCHEMA = "GovernedMutationServicePreparation 0.1"
RESULT_SCHEMA = "GovernedMutationServiceResult 0.1"
WINDOW_SCHEMA = "GovernedMutationWindowRef 0.1"
EVIDENCE_SCHEMA = "GovernedMutationEvidenceRef 0.1"
WINDOW_NAMES = ("work", "cycle", "decision", "authority", "execution", "git")
REQUEST_FIELDS = {
    "schemaVersion", "workId", "branch", "changes", "message",
    "semanticAuthority", "authorizesMutation",
}
PREPARATION_FIELDS = {
    "schemaVersion", "requestHash", "state", "blockers", "nextSafeAction",
    "work", "reentry", "handle", "locator", "busIssueNumber",
    "semanticHostSupported", "readOnly", "semanticAuthority",
    "authorizesMutation", "preparationHash",
}
RESULT_FIELDS = {
    "schemaVersion", "requestHash", "status", "summary", "blockers",
    "nextSafeAction", "evidence", "windows", "readOnly",
    "semanticAuthority", "authorizesMutation", "resultHash",
}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class GovernedMutationServiceError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _code(exc: BaseException) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value
    text = str(exc)
    return text.split(":", 1)[0] if text else exc.__class__.__name__


def _positive(value: Any, code: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise GovernedMutationServiceError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise GovernedMutationServiceError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise GovernedMutationServiceError(code)
    return value


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_ARTIFACT_INVALID")
    return value


def _write(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_after_marker(body: Any, marker: str) -> dict[str, Any]:
    if not isinstance(body, str) or not body.startswith(marker + "\n"):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_MARKER_INVALID")
    raw = body[len(marker):].strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise GovernedMutationServiceError("GOVERNED_MUTATION_JSON_INVALID")
        raw = "\n".join(lines[1:-1])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_JSON_INVALID")
    return value


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_REQUEST_SCHEMA_UNSUPPORTED")
    work_id = value.get("workId")
    try:
        agent_cycle.validate_work_ref({"workId": work_id})
    except RuntimeError as exc:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_WORK_REF_INVALID") from exc
    branch = value.get("branch")
    try:
        canonical_branch = git_observation.canonical_branch(branch)
    except RuntimeError as exc:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_BRANCH_INVALID") from exc
    if canonical_branch != branch:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_BRANCH_NOT_CANONICAL")
    target_policy.change_paths(
        {"changes": value.get("changes"), "message": value.get("message")}
    )
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_REQUEST_MUST_NOT_AUTHORIZE")
    return value


def request_hash(value: dict[str, Any]) -> str:
    return stable_hash(validate_request(value))


def _transport_meta(event: Any) -> dict[str, int]:
    if not isinstance(event, dict):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_EVENT_INVALID")
    issue = event.get("issue")
    comment = event.get("comment")
    repository = event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_EVENT_INVALID")
    if issue.get("pull_request") is not None or issue.get("title") != BUS_TITLE:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise GovernedMutationServiceError("GOVERNED_MUTATION_ACTOR_FORBIDDEN")
    if repository.get("full_name") != REPOSITORY:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_REPOSITORY_MISMATCH")
    return {
        "issueNumber": _positive(issue.get("number"), "GOVERNED_MUTATION_ISSUE_INVALID"),
        "commentId": _positive(comment.get("id"), "GOVERNED_MUTATION_COMMENT_INVALID"),
    }


def parse_event(event: Any) -> tuple[dict[str, Any], dict[str, int]]:
    meta = _transport_meta(event)
    request = validate_request(
        _json_after_marker((event.get("comment") or {}).get("body"), REQUEST_MARKER)
    )
    return request, meta


def _semantic_host_supports_service(source_sha: str, transport: Any) -> bool:
    source_sha = _sha(source_sha, "GOVERNED_MUTATION_SEMANTIC_HOST_INVALID")
    try:
        transport.request(
            "GET",
            f"repos/{REPOSITORY}/contents/tools/governed_mutation_service.py?ref={source_sha}",
        )
        return True
    except ApiError as exc:
        if exc.status == 404:
            return False
        raise GovernedMutationServiceError(
            "GOVERNED_MUTATION_SEMANTIC_HOST_UNKNOWN", exc.detail
        ) from exc


def _preparation(
    request: dict[str, Any],
    *,
    state: str,
    blockers: list[str],
    next_safe_action: str | None,
    work: dict[str, Any] | None,
    reentry: dict[str, Any] | None,
    handle: dict[str, Any] | None,
    locator: dict[str, Any] | None,
    bus_issue_number: int | None,
    semantic_host_supported: bool | None,
) -> dict[str, Any]:
    core = {
        "schemaVersion": PREPARATION_SCHEMA,
        "requestHash": request_hash(request),
        "state": state,
        "blockers": sorted(set(blockers)),
        "nextSafeAction": next_safe_action,
        "work": copy.deepcopy(work),
        "reentry": copy.deepcopy(reentry),
        "handle": copy.deepcopy(handle),
        "locator": copy.deepcopy(locator),
        "busIssueNumber": bus_issue_number,
        "semanticHostSupported": semantic_host_supported,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "preparationHash": stable_hash(core)}
    return validate_preparation(value)


def validate_preparation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PREPARATION_FIELDS:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    if value.get("schemaVersion") != PREPARATION_SCHEMA:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    _hash(value.get("requestHash"), "GOVERNED_MUTATION_PREPARATION_INVALID")
    _hash(value.get("preparationHash"), "GOVERNED_MUTATION_PREPARATION_INVALID")
    if value.get("state") not in {"READY", "BLOCKED", "UNKNOWN"}:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    blockers = value.get("blockers")
    if (
        not isinstance(blockers, list)
        or blockers != sorted(set(blockers))
        or any(not isinstance(item, str) or not item for item in blockers)
    ):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    if value["state"] == "READY":
        if blockers or value.get("nextSafeAction") != "EXECUTE_MUTATION":
            raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
        hosted_cycle_handle.decode_handle(value.get("handle"), repository=REPOSITORY)
        if not isinstance(value.get("locator"), dict) or value.get("semanticHostSupported") is not True:
            raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
        _positive(value.get("busIssueNumber"), "GOVERNED_MUTATION_PREPARATION_INVALID")
    elif not blockers:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "preparationHash"}
    if value["preparationHash"] != stable_hash(core):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_HASH_MISMATCH")
    return value


def prepare_request(request: dict[str, Any], *, transport: Any | None = None) -> dict[str, Any]:
    request = validate_request(request)
    if transport is None:
        raise GovernedMutationServiceError("BLOCKED_EXECUTION_SURFACE")
    try:
        turnover = agent_reentry_guidance.observe_turnover_context(
            request["workId"], repository=REPOSITORY, transport=transport
        )
    except Exception as exc:
        code = _code(exc)
        state = "UNKNOWN" if "UNKNOWN" in code or "UNAVAILABLE" in code else "BLOCKED"
        return _preparation(
            request,
            state=state,
            blockers=[code],
            next_safe_action="INSPECT_WORK",
            work=None,
            reentry=None,
            handle=None,
            locator=None,
            bus_issue_number=None,
            semantic_host_supported=None,
        )

    work = turnover["work"]
    reentry = turnover["reentry"]
    handle = turnover["handle"]
    bus_issue_number = turnover["busIssueNumber"]
    if work.get("branch") != request["branch"]:
        return _preparation(
            request,
            state="BLOCKED",
            blockers=["GOVERNED_MUTATION_WORK_BRANCH_MISMATCH"],
            next_safe_action="ALIGN_WORK_BRANCH",
            work=work,
            reentry=reentry,
            handle=handle,
            locator=None,
            bus_issue_number=bus_issue_number,
            semantic_host_supported=None,
        )
    if reentry.get("nextSafeAction") != "RESUME_EXACT_CYCLE" or handle is None:
        return _preparation(
            request,
            state="BLOCKED",
            blockers=["GOVERNED_MUTATION_EXACT_CYCLE_REQUIRED"],
            next_safe_action=reentry.get("nextSafeAction") or "INSPECT_WORK",
            work=work,
            reentry=reentry,
            handle=handle,
            locator=None,
            bus_issue_number=bus_issue_number,
            semantic_host_supported=None,
        )
    try:
        _, locator = hosted_cycle_handle.decode_handle(handle, repository=REPOSITORY)
        supported = _semantic_host_supports_service(locator["sourceSha"], transport)
    except Exception as exc:
        return _preparation(
            request,
            state="UNKNOWN",
            blockers=[_code(exc)],
            next_safe_action="INSPECT_CYCLE",
            work=work,
            reentry=reentry,
            handle=handle,
            locator=None,
            bus_issue_number=bus_issue_number,
            semantic_host_supported=None,
        )
    if not supported:
        return _preparation(
            request,
            state="BLOCKED",
            blockers=["GOVERNED_MUTATION_CYCLE_HOST_PREDATES_SERVICE"],
            next_safe_action="BEGIN_NEW_CYCLE",
            work=work,
            reentry=reentry,
            handle=handle,
            locator=locator,
            bus_issue_number=bus_issue_number,
            semantic_host_supported=False,
        )
    return _preparation(
        request,
        state="READY",
        blockers=[],
        next_safe_action="EXECUTE_MUTATION",
        work=work,
        reentry=reentry,
        handle=handle,
        locator=locator,
        bus_issue_number=bus_issue_number,
        semantic_host_supported=True,
    )


def _window_ref(member: str, payload: Any) -> dict[str, Any]:
    return {
        "schemaVersion": WINDOW_SCHEMA,
        "kind": "artifact-member",
        "member": member,
        "hash": stable_hash(payload),
    }


def _evidence_ref(run_id: int, run_attempt: int) -> dict[str, Any]:
    run_id = _positive(run_id, "GOVERNED_MUTATION_RUN_ID_INVALID")
    run_attempt = _positive(run_attempt, "GOVERNED_MUTATION_RUN_ATTEMPT_INVALID")
    return {
        "schemaVersion": EVIDENCE_SCHEMA,
        "kind": "github-actions-artifact",
        "runId": run_id,
        "runAttempt": run_attempt,
        "artifactName": f"governed-mutation-{run_id}-{run_attempt}",
    }


def _materialize_windows(
    evidence_dir: str | Path,
    payloads: dict[str, Any | None],
) -> dict[str, Any | None]:
    root = Path(evidence_dir)
    root.mkdir(parents=True, exist_ok=True)
    windows: dict[str, Any | None] = {}
    for name in WINDOW_NAMES:
        payload = payloads.get(name)
        if payload is None:
            windows[name] = None
            continue
        member = f"{name}.json"
        _write(root / member, payload)
        windows[name] = _window_ref(member, payload)
    return windows


def _next_safe_action(status: str, blockers: list[str]) -> str:
    if status == "PASS":
        return "CONTINUE"
    if status == "UNKNOWN":
        return "INSPECT_EXECUTION"
    if any(
        item in {
            "AGENT_WRITE_LIFECYCLE_BINDING_REQUIRED",
            "AGENT_WRITE_LIFECYCLE_NOT_ACTIVE",
            "AGENT_WRITE_LIFECYCLE_BINDING_EXPIRED",
        }
        for item in blockers
    ):
        return "ACQUIRE_WRITE_BINDING"
    if any("LIFECYCLE" in item or "LEASE" in item for item in blockers):
        return "INSPECT_AUTHORITY"
    return "RESOLVE_BLOCKERS"


def _result(
    *,
    request: dict[str, Any] | None,
    status: str,
    summary: dict[str, Any],
    blockers: list[str],
    next_safe_action: str,
    evidence: dict[str, Any],
    windows: dict[str, Any | None],
) -> dict[str, Any]:
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "requestHash": request_hash(request) if request is not None else None,
        "status": status,
        "summary": copy.deepcopy(summary),
        "blockers": sorted(set(blockers)),
        "nextSafeAction": next_safe_action,
        "evidence": copy.deepcopy(evidence),
        "windows": copy.deepcopy(windows),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "resultHash": stable_hash(core)}
    return validate_result(value)


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    if value.get("schemaVersion") != RESULT_SCHEMA:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    request_digest = value.get("requestHash")
    if request_digest is not None:
        _hash(request_digest, "GOVERNED_MUTATION_RESULT_INVALID")
    if value.get("status") not in {"PASS", "BLOCKED", "UNKNOWN"}:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    summary = value.get("summary")
    if not isinstance(summary, dict) or set(summary) != {
        "branch", "parentHead", "branchHead", "changedPaths"
    }:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    for field in ("parentHead", "branchHead"):
        raw = summary.get(field)
        if raw is not None:
            _sha(raw, "GOVERNED_MUTATION_RESULT_INVALID")
    paths = summary.get("changedPaths")
    if not isinstance(paths, list) or paths != sorted(set(paths)):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    blockers = value.get("blockers")
    if (
        not isinstance(blockers, list)
        or blockers != sorted(set(blockers))
        or any(not isinstance(item, str) or not item for item in blockers)
    ):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    if value["status"] == "PASS" and blockers:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    evidence = value.get("evidence")
    if (
        not isinstance(evidence, dict)
        or evidence.get("schemaVersion") != EVIDENCE_SCHEMA
        or evidence.get("kind") != "github-actions-artifact"
    ):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    _positive(evidence.get("runId"), "GOVERNED_MUTATION_RESULT_INVALID")
    _positive(evidence.get("runAttempt"), "GOVERNED_MUTATION_RESULT_INVALID")
    windows = value.get("windows")
    if not isinstance(windows, dict) or set(windows) != set(WINDOW_NAMES):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    for item in windows.values():
        if item is None:
            continue
        if (
            not isinstance(item, dict)
            or item.get("schemaVersion") != WINDOW_SCHEMA
            or item.get("kind") != "artifact-member"
            or not isinstance(item.get("member"), str)
        ):
            raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
        _hash(item.get("hash"), "GOVERNED_MUTATION_RESULT_INVALID")
    if not isinstance(value.get("nextSafeAction"), str) or not value["nextSafeAction"]:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_INVALID")
    _hash(value.get("resultHash"), "GOVERNED_MUTATION_RESULT_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value["resultHash"] != stable_hash(core):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_RESULT_HASH_MISMATCH")
    return value


def _summary_from_preparation(request: dict[str, Any]) -> dict[str, Any]:
    paths = target_policy.change_paths(
        {"changes": request["changes"], "message": request["message"]}
    )
    return {
        "branch": request["branch"],
        "parentHead": None,
        "branchHead": None,
        "changedPaths": paths,
    }


def result_from_preparation(
    request: dict[str, Any],
    preparation: dict[str, Any],
    *,
    run_id: int,
    run_attempt: int,
    evidence_dir: str | Path,
) -> dict[str, Any]:
    request = validate_request(request)
    preparation = validate_preparation(preparation)
    if preparation["state"] == "READY":
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_NOT_TERMINAL")
    payloads = {
        "work": {
            "work": copy.deepcopy(preparation["work"]),
            "reentry": copy.deepcopy(preparation["reentry"]),
        },
        "cycle": {
            "handle": copy.deepcopy(preparation["handle"]),
            "locator": copy.deepcopy(preparation["locator"]),
        } if preparation["handle"] is not None else None,
        "decision": None,
        "authority": None,
        "execution": None,
        "git": None,
    }
    windows = _materialize_windows(evidence_dir, payloads)
    return _result(
        request=request,
        status=preparation["state"],
        summary=_summary_from_preparation(request),
        blockers=preparation["blockers"],
        next_safe_action=preparation["nextSafeAction"] or "INSPECT_WORK",
        evidence=_evidence_ref(run_id, run_attempt),
        windows=windows,
    )


def execute_prepared(
    request: dict[str, Any],
    meta: dict[str, Any],
    preparation: dict[str, Any],
    *,
    begin_dir: str | Path,
    run_id: int,
    run_attempt: int,
    evidence_dir: str | Path,
    transport: Any | None = None,
) -> dict[str, Any]:
    request = validate_request(request)
    preparation = validate_preparation(preparation)
    if preparation["requestHash"] != request_hash(request):
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PREPARATION_REQUEST_MISMATCH")
    if preparation["state"] != "READY":
        return result_from_preparation(
            request,
            preparation,
            run_id=run_id,
            run_attempt=run_attempt,
            evidence_dir=evidence_dir,
        )
    if transport is None:
        raise GovernedMutationServiceError("BLOCKED_EXECUTION_SURFACE")
    issue_number = _positive(meta.get("issueNumber"), "GOVERNED_MUTATION_ISSUE_INVALID")
    comment_id = _positive(meta.get("commentId"), "GOVERNED_MUTATION_COMMENT_INVALID")
    root = Path(begin_dir)
    context = _load(root / "context.json")
    manifest = _load(root / "manifest.json")
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    binding = hosted_cycle_handle.bind(
        preparation["handle"],
        context=context,
        manifest=manifest,
        repository=REPOSITORY,
    )
    if binding["locator"] != preparation["locator"]:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_CYCLE_LOCATOR_DRIFT")
    outer = {
        "schemaVersion": hosted_agent_tool.HANDLE_REQUEST_SCHEMA,
        "requestId": "agent-tool-" + stable_hash(
            {"serviceRequest": request, "commentId": comment_id}
        )[:24],
        "handle": copy.deepcopy(preparation["handle"]),
        "toolId": "git.files.mutate",
        "target": {"branch": request["branch"]},
        "input": {
            "changes": copy.deepcopy(request["changes"]),
            "message": request["message"],
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    canonical_request = hosted_agent_tool.derive_handle_request(outer, manifest, context)
    resolved = resolver.resolve_request(
        canonical_request,
        context,
        transport=transport,
        execute=False,
    )
    plan = resolved["plan"]
    if plan["mode"] != "mutation-execute" or plan["status"] != "READY":
        raise GovernedMutationServiceError("GOVERNED_MUTATION_PLAN_NOT_EXECUTABLE")
    source = remote.build_hosted_comment_source(
        host="governed-mutation-service",
        source_sha=manifest["source"]["sourceSha"],
        invocation_id=str(_positive(run_id, "GOVERNED_MUTATION_RUN_ID_INVALID")),
        issue_number=issue_number,
        comment_id=comment_id,
    )
    outcome = mutation_host.execute_plan(
        plan,
        source=source,
        transport=transport,
        lifecycle_context={
            "cycleInstanceId": manifest["cycleInstanceId"],
            "issueNumber": issue_number,
            "beforeCommentId": comment_id,
        },
    )
    command = plan["concrete"]["command"]
    parent_head = command["expected"].get("branchHead")
    branch_head = outcome.get("observedBranchHead")
    receipt = outcome.get("remoteReceipt")
    if outcome["status"] == "PASS":
        branch_head = receipt["aggregateReadback"]["branchHead"]
        changed_paths = receipt["aggregateReadback"]["changedPaths"]
    else:
        changed_paths = target_policy.change_paths(plan["input"])
    payloads = {
        "work": {
            "work": copy.deepcopy(preparation["work"]),
            "reentry": copy.deepcopy(preparation["reentry"]),
        },
        "cycle": {
            "handle": copy.deepcopy(preparation["handle"]),
            "locator": copy.deepcopy(preparation["locator"]),
            "manifest": copy.deepcopy(manifest),
            "contextHash": context.get("contextHash"),
        },
        "decision": {
            "request": copy.deepcopy(canonical_request),
            "plan": copy.deepcopy(plan),
        },
        "authority": {
            "proofSet": copy.deepcopy(outcome.get("executionProofSet")),
        } if outcome.get("executionProofSet") is not None else None,
        "execution": {"outcome": copy.deepcopy(outcome)},
        "git": {"receipt": copy.deepcopy(receipt)} if receipt is not None else None,
    }
    windows = _materialize_windows(evidence_dir, payloads)
    return _result(
        request=request,
        status=outcome["status"],
        summary={
            "branch": request["branch"],
            "parentHead": parent_head,
            "branchHead": branch_head,
            "changedPaths": changed_paths,
        },
        blockers=outcome["blockers"],
        next_safe_action=_next_safe_action(outcome["status"], outcome["blockers"]),
        evidence=_evidence_ref(run_id, run_attempt),
        windows=windows,
    )


def event_failure_result(
    event: dict[str, Any],
    *,
    blocker: str,
    run_id: int,
    run_attempt: int,
    evidence_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, int]]:
    meta = _transport_meta(event)
    windows = _materialize_windows(
        evidence_dir,
        {name: None for name in WINDOW_NAMES},
    )
    value = _result(
        request=None,
        status="BLOCKED",
        summary={
            "branch": None,
            "parentHead": None,
            "branchHead": None,
            "changedPaths": [],
        },
        blockers=[blocker],
        next_safe_action="FIX_REQUEST",
        evidence=_evidence_ref(run_id, run_attempt),
        windows=windows,
    )
    return value, meta


def transport_failure_result(
    request: dict[str, Any],
    preparation: dict[str, Any],
    *,
    blocker: str,
    run_id: int,
    run_attempt: int,
    evidence_dir: str | Path,
) -> dict[str, Any]:
    request = validate_request(request)
    preparation = validate_preparation(preparation)
    payloads = {
        "work": {
            "work": copy.deepcopy(preparation["work"]),
            "reentry": copy.deepcopy(preparation["reentry"]),
        },
        "cycle": {
            "handle": copy.deepcopy(preparation["handle"]),
            "locator": copy.deepcopy(preparation["locator"]),
        } if preparation["handle"] is not None else None,
        "decision": None,
        "authority": None,
        "execution": {"transportFailure": blocker},
        "git": None,
    }
    return _result(
        request=request,
        status="BLOCKED",
        summary=_summary_from_preparation(request),
        blockers=[blocker],
        next_safe_action="INSPECT_EXECUTION",
        evidence=_evidence_ref(run_id, run_attempt),
        windows=_materialize_windows(evidence_dir, payloads),
    )


def inspect_window(
    result: dict[str, Any],
    *,
    window: str,
    evidence_dir: str | Path,
) -> Any:
    result = validate_result(result)
    if window not in WINDOW_NAMES:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_WINDOW_UNKNOWN")
    ref = result["windows"][window]
    if ref is None:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_WINDOW_UNAVAILABLE")
    payload = _load(Path(evidence_dir) / ref["member"])
    if stable_hash(payload) != ref["hash"]:
        raise GovernedMutationServiceError("GOVERNED_MUTATION_WINDOW_HASH_MISMATCH")
    return payload


def publish_result(
    result: dict[str, Any],
    *,
    issue_number: int,
    transport: Any | None = None,
) -> int:
    if transport is None:
        raise GovernedMutationServiceError("BLOCKED_EXECUTION_SURFACE")
    value = validate_result(result)
    body = (
        RESULT_MARKER
        + "\n```json\n"
        + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n```"
    )
    return hosted_issue_bus.post_comment(
        transport,
        repository=REPOSITORY,
        issue_number=issue_number,
        body=body,
    )


def _emit(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command_name", required=True)

    parse = sub.add_parser("parse-event")
    parse.add_argument("--event", required=True)
    parse.add_argument("--request-out", required=True)
    parse.add_argument("--meta-out", required=True)
    parse.add_argument("--github-output")

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--request", required=True)
    prepare.add_argument("--preparation", required=True)
    prepare.add_argument("--github-output")

    execute = sub.add_parser("execute")
    execute.add_argument("--request", required=True)
    execute.add_argument("--meta", required=True)
    execute.add_argument("--preparation", required=True)
    execute.add_argument("--begin-dir")
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--run-attempt", required=True)
    execute.add_argument("--evidence-dir", required=True)
    execute.add_argument("--result", required=True)

    event_failure = sub.add_parser("event-failure")
    event_failure.add_argument("--event", required=True)
    event_failure.add_argument("--blocker", required=True)
    event_failure.add_argument("--run-id", required=True)
    event_failure.add_argument("--run-attempt", required=True)
    event_failure.add_argument("--evidence-dir", required=True)
    event_failure.add_argument("--meta-out", required=True)
    event_failure.add_argument("--result", required=True)

    failure = sub.add_parser("transport-failure")
    failure.add_argument("--request", required=True)
    failure.add_argument("--preparation", required=True)
    failure.add_argument("--blocker", required=True)
    failure.add_argument("--run-id", required=True)
    failure.add_argument("--run-attempt", required=True)
    failure.add_argument("--evidence-dir", required=True)
    failure.add_argument("--result", required=True)

    publish = sub.add_parser("publish")
    publish.add_argument("--meta", required=True)
    publish.add_argument("--result", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--result", required=True)
    inspect.add_argument("--evidence-dir", required=True)
    inspect.add_argument("--window", choices=WINDOW_NAMES, required=True)
    inspect.add_argument("--output")

    check = sub.add_parser("check-result")
    check.add_argument("--result", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    transport = GhApiTransport()
    if args.command_name == "parse-event":
        request, meta = parse_event(_load(args.event))
        _write(args.request_out, request)
        _write(args.meta_out, meta)
        _emit(args.github_output, "request_hash", request_hash(request))
        return 0
    if args.command_name == "prepare":
        request = _load(args.request)
        value = prepare_request(request, transport=transport)
        _write(args.preparation, value)
        _emit(args.github_output, "state", value["state"])
        if value.get("locator") is not None:
            _emit(args.github_output, "begin_run_id", str(value["locator"]["runId"]))
            _emit(args.github_output, "begin_source_sha", value["locator"]["sourceSha"])
            _emit(args.github_output, "begin_artifact_name", value["locator"]["artifactName"])
        return 0
    if args.command_name == "execute":
        request = _load(args.request)
        meta = _load(args.meta)
        preparation = _load(args.preparation)
        if preparation.get("state") == "READY":
            if not args.begin_dir:
                raise GovernedMutationServiceError("GOVERNED_MUTATION_BEGIN_DIR_REQUIRED")
            value = execute_prepared(
                request,
                meta,
                preparation,
                begin_dir=args.begin_dir,
                run_id=_positive(args.run_id, "GOVERNED_MUTATION_RUN_ID_INVALID"),
                run_attempt=_positive(args.run_attempt, "GOVERNED_MUTATION_RUN_ATTEMPT_INVALID"),
                evidence_dir=args.evidence_dir,
                transport=transport,
            )
        else:
            value = result_from_preparation(
                request,
                preparation,
                run_id=_positive(args.run_id, "GOVERNED_MUTATION_RUN_ID_INVALID"),
                run_attempt=_positive(args.run_attempt, "GOVERNED_MUTATION_RUN_ATTEMPT_INVALID"),
                evidence_dir=args.evidence_dir,
            )
        _write(args.result, value)
        return 0
    if args.command_name == "event-failure":
        value, meta = event_failure_result(
            _load(args.event),
            blocker=args.blocker,
            run_id=_positive(args.run_id, "GOVERNED_MUTATION_RUN_ID_INVALID"),
            run_attempt=_positive(args.run_attempt, "GOVERNED_MUTATION_RUN_ATTEMPT_INVALID"),
            evidence_dir=args.evidence_dir,
        )
        _write(args.meta_out, meta)
        _write(args.result, value)
        return 0
    if args.command_name == "transport-failure":
        value = transport_failure_result(
            _load(args.request),
            _load(args.preparation),
            blocker=args.blocker,
            run_id=_positive(args.run_id, "GOVERNED_MUTATION_RUN_ID_INVALID"),
            run_attempt=_positive(args.run_attempt, "GOVERNED_MUTATION_RUN_ATTEMPT_INVALID"),
            evidence_dir=args.evidence_dir,
        )
        _write(args.result, value)
        return 0
    if args.command_name == "publish":
        meta = _load(args.meta)
        publish_result(
            _load(args.result),
            issue_number=_positive(meta.get("issueNumber"), "GOVERNED_MUTATION_ISSUE_INVALID"),
            transport=transport,
        )
        return 0
    if args.command_name == "inspect":
        payload = inspect_window(
            _load(args.result),
            window=args.window,
            evidence_dir=args.evidence_dir,
        )
        if args.output:
            _write(args.output, payload)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command_name == "check-result":
        status = validate_result(_load(args.result))["status"]
        return 0 if status == "PASS" else 3 if status == "UNKNOWN" else 2
    raise GovernedMutationServiceError("GOVERNED_MUTATION_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GovernedMutationServiceError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

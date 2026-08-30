from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools import agent_cycle_identity, agent_write_lifecycle as lifecycle, hosted_cycle_records
from tools import agent_write_lifecycle_host as host
from tools.agent_tools import contracts

TARGET = "623adc8297ca84cdee02706ef846e2dcbea107d2"
QUALIFICATION_BRANCH = "work/operations/m12-at3d-r4c-hosted-qualification-20260830"
REPOSITORY = "EAKerber/MobiliPresenter"
BRANCH = "work/operations/r4c-hosted-target"
OTHER_BRANCH = "work/operations/r4c-hosted-disjoint"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "interactive-manager-gitops",
    "sessionId": "r4c-hosted-qualification-20260830",
}
CONTEXT_HASH = "b" * 64


def manifest() -> dict[str, Any]:
    source = {
        "workflow": "hosted-agent-cycle",
        "runId": 4401,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "commentId": 100,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(
        source, ACTOR, CONTEXT_HASH
    )
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "r4c-hosted-begin-20260830",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-r4c-hosted-qualification",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": [
            "agent-write-lease-lifecycle-0.1",
            "execution-trace-0.1",
        ],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def begin_ref(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": current["source"]["runId"],
        "sourceSha": current["source"]["sourceSha"],
        "contextHash": current["contextHash"],
    }


def owner(comment_id: int, marker: str | None = None, payload: dict | None = None) -> dict:
    if marker is None:
        body = "qualification-boundary"
    else:
        body = marker + "\n" + json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": body,
    }


def bot(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload, sort_keys=True) + "\n```",
    }


def tool_request(current: dict[str, Any], *, branch: str = BRANCH) -> dict[str, Any]:
    return contracts.validate_request(
        {
            "schemaVersion": contracts.REQUEST_SCHEMA,
            "requestId": "agent-tool-r4c-hosted",
            "begin": begin_ref(current),
            "actor": copy.deepcopy(ACTOR),
            "toolId": "git.files.mutate",
            "target": {"branch": branch, "path": "docs/r4c-hosted.txt"},
            "input": {"content": "qualification"},
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    )


def release_bundle(current: dict[str, Any]) -> dict[str, Any]:
    request = lifecycle.validate_request(
        {
            "schemaVersion": lifecycle.REQUEST_SCHEMA,
            "requestId": "release-r4c-hosted",
            "action": "release",
            "begin": begin_ref(current),
            "actor": copy.deepcopy(ACTOR),
            "branch": BRANCH,
            "expectedAuthorityHead": "1" * 40,
            "expectedBranchHead": "2" * 40,
            "expectedBindingHash": "3" * 64,
            "ttlSeconds": None,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    )
    return {
        "request": request,
        "dispatch": {
            "action": "release",
            "begin": copy.deepcopy(request["begin"]),
            "actor": copy.deepcopy(request["actor"]),
            "branch": BRANCH,
            "authorityHead": request["expectedAuthorityHead"],
            "source": {
                "issueNumber": 145,
                "requestCommentId": 150,
                "hostedRunId": 5501,
                "semanticHostSha": TARGET,
            },
        },
        "context": {
            "semanticContext": {
                "declaredIntent": "governed-mutation",
            }
        },
        "manifest": current,
    }


def tool_result(request: dict[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "requestHash": contracts.request_hash(request),
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "toolId": request["toolId"],
        "status": status,
    }


class NoMutationTransport:
    def __init__(self) -> None:
        self.mutable_calls: list[tuple[str, str]] = []

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        if method.upper() in {"POST", "PATCH", "PUT", "DELETE"}:
            self.mutable_calls.append((method.upper(), endpoint))
            raise RuntimeError("QUALIFICATION_MUTATION_FORBIDDEN")
        raise RuntimeError("QUALIFICATION_UNEXPECTED_TRANSPORT_READ")


def main() -> None:
    if os.environ.get("GITHUB_REF_NAME") != QUALIFICATION_BRANCH:
        raise SystemExit("QUALIFICATION_BRANCH_MISMATCH")
    if not os.environ.get("GITHUB_SHA"):
        raise SystemExit("QUALIFICATION_HOST_SHA_MISSING")

    changed = sorted(
        line.strip()
        for line in subprocess.check_output(
            ["git", "diff", "--name-only", f"{TARGET}..HEAD"], text=True
        ).splitlines()
        if line.strip()
    )
    expected_delta = [
        ".github/qualification/r4c_predecessor_fence.py",
        ".github/workflows/agent-ops.yml",
    ]
    if changed != expected_delta:
        raise SystemExit(f"QUALIFICATION_DELTA_INVALID:{changed}")

    current = manifest()
    request = tool_request(current)
    bundle = release_bundle(current)
    begin = owner(100)
    predecessor = owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, request)
    release_frontier = owner(150)
    waiting_comments = [begin, predecessor, release_frontier]
    pass_comments = waiting_comments + [
        bot(
            170,
            hosted_cycle_records.AGENT_TOOL_RESULT_MARKER,
            tool_result(request, status="PASS"),
        )
    ]
    blocked_comments = waiting_comments + [
        bot(
            171,
            hosted_cycle_records.AGENT_TOOL_RESULT_MARKER,
            tool_result(request, status="BLOCKED"),
        )
    ]
    unknown_comments = waiting_comments + [
        bot(
            172,
            hosted_cycle_records.AGENT_TOOL_RESULT_MARKER,
            tool_result(request, status="UNKNOWN"),
        )
    ]

    waiting = host._mutation_predecessor_fence(waiting_comments, bundle)
    if waiting.get("state") != host.PREDECESSOR_WAITING:
        raise SystemExit(f"QUALIFICATION_WAITING_INVALID:{waiting}")
    if waiting.get("waitingPredecessorRequestCommentIds") != [110]:
        raise SystemExit("QUALIFICATION_PREDECESSOR_FRONTIER_INVALID")

    # Exercise the productive inspect ordering: predecessor fence must return
    # before lifecycle.build_attempt and before any transport mutation.
    transport = NoMutationTransport()
    original_validate = host._validate_bundle
    original_comments = host._comments
    original_build_attempt = lifecycle.build_attempt
    attempt_count = 0

    def forbidden_attempt(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise RuntimeError("QUALIFICATION_ATTEMPT_MUST_NOT_EXIST")

    try:
        host._validate_bundle = lambda *args, **kwargs: bundle
        host._comments = lambda *args, **kwargs: copy.deepcopy(waiting_comments)
        lifecycle.build_attempt = forbidden_attempt
        inspected = host.inspect_protocol(
            bundle,
            host_sha=TARGET,
            hosted_run_id=5501,
            run_id=6601,
            transport=transport,
        )
    finally:
        host._validate_bundle = original_validate
        host._comments = original_comments
        lifecycle.build_attempt = original_build_attempt

    if inspected.get("state") != host.PREDECESSOR_WAITING:
        raise SystemExit(f"QUALIFICATION_INSPECT_WAITING_INVALID:{inspected}")
    if attempt_count != 0:
        raise SystemExit(f"QUALIFICATION_ATTEMPT_OBSERVED:{attempt_count}")
    if transport.mutable_calls:
        raise SystemExit(f"QUALIFICATION_MUTATION_OBSERVED:{transport.mutable_calls}")

    late_pass = host._mutation_predecessor_fence(pass_comments, bundle)
    if late_pass.get("state") != "CLEAR":
        raise SystemExit(f"QUALIFICATION_LATE_PASS_DID_NOT_CLEAR:{late_pass}")

    terminal_blocked = host._mutation_predecessor_fence(blocked_comments, bundle)
    if terminal_blocked.get("state") != "CLEAR":
        raise SystemExit(f"QUALIFICATION_BLOCKED_DID_NOT_CLEAR:{terminal_blocked}")

    ambiguous = host._mutation_predecessor_fence(unknown_comments, bundle)
    if ambiguous.get("state") != host.PREDECESSOR_UNKNOWN:
        raise SystemExit(f"QUALIFICATION_UNKNOWN_INVALID:{ambiguous}")
    if ambiguous.get("terminal", {}).get("status") != "UNKNOWN":
        raise SystemExit("QUALIFICATION_UNKNOWN_TERMINAL_INVALID")
    if ambiguous.get("terminal", {}).get("blockers") != [
        "AGENT_WRITE_LIFECYCLE_MUTATION_PREDECESSOR_UNKNOWN"
    ]:
        raise SystemExit("QUALIFICATION_UNKNOWN_BLOCKER_INVALID")

    disjoint_request = tool_request(current, branch=OTHER_BRANCH)
    disjoint_comments = [
        begin,
        owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, disjoint_request),
        release_frontier,
    ]
    disjoint = host._mutation_predecessor_fence(disjoint_comments, bundle)
    if disjoint.get("state") != "CLEAR":
        raise SystemExit(f"QUALIFICATION_DISJOINT_SERIALIZED:{disjoint}")

    summary = {
        "schemaVersion": "R4CHostedMutationPredecessorFenceQualification 0.1",
        "targetHead": TARGET,
        "harnessHead": os.environ["GITHUB_SHA"],
        "harnessDelta": changed,
        "waitingState": waiting["state"],
        "waitingPredecessorRequestCommentIds": waiting[
            "waitingPredecessorRequestCommentIds"
        ],
        "inspectState": inspected["state"],
        "attemptCreationCountWhileWaiting": attempt_count,
        "mutableTransportCallCountWhileWaiting": len(transport.mutable_calls),
        "latePassState": late_pass["state"],
        "blockedTerminalState": terminal_blocked["state"],
        "unknownState": ambiguous["state"],
        "unknownTerminalStatus": ambiguous["terminal"]["status"],
        "disjointBranchState": disjoint["state"],
        "pollingSleepCount": 0,
        "operationReplayCount": 0,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    root = Path("/tmp/r4c-hosted-qualification")
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

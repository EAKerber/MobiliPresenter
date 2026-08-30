from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import hosted_agent_cycle
from tools.agent_tools import contracts, trace_collect

TARGET = "7aa37ef70ca70b51bfbeb3ad3916ad6aa6a3c947"
EXPECTED_DELTA = [
    ".github/qualification/r4a_delayed_result.py",
    ".github/workflows/agent-ops.yml",
]


def owner(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def main() -> None:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", f"{TARGET}..HEAD"], text=True
    ).splitlines()
    if changed != EXPECTED_DELTA:
        raise SystemExit(f"QUALIFICATION_DELTA_INVALID:{changed}")

    root = Path("/tmp/r4a-hosted-qualification")
    begin_root = root / "begin"
    first_root = root / "close-first"
    retry_root = root / "close-retry"
    for path in (begin_root, first_root, retry_root):
        path.mkdir(parents=True, exist_ok=True)

    actor = {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": "r4a-hosted-qualification-20260830-01",
    }
    begin_command = {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": "r4a-hosted-begin-20260830-01",
        "action": "begin",
        "actor": actor,
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": None,
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    begin_result = hosted_agent_cycle.begin_from_envelope(
        begin_command,
        {"issueNumber": 145, "commentId": 100},
        context_path=str(begin_root / "context.json"),
        manifest_path=str(begin_root / "manifest.json"),
    )
    if begin_result.get("status") != "READY":
        raise SystemExit("QUALIFICATION_BEGIN_NOT_READY")

    manifest = json.loads((begin_root / "manifest.json").read_text(encoding="utf-8"))
    begin_ref = {
        "runId": manifest["source"]["runId"],
        "sourceSha": manifest["source"]["sourceSha"],
        "contextHash": manifest["contextHash"],
    }
    request = contracts.validate_request({
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": "r4a-delayed-project-inspect",
        "begin": begin_ref,
        "actor": copy.deepcopy(actor),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    })
    close_one = {
        "schemaVersion": "HostedAgentCycleCommand 0.2",
        "requestId": "r4a-hosted-close-one-20260830-01",
        "action": "close",
        "handle": copy.deepcopy(begin_result["handle"]),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    close_two = {**copy.deepcopy(close_one), "requestId": "r4a-hosted-close-two-20260830-01"}

    begin_boundary = {
        "id": 100,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": "synthetic-r4a-begin-boundary",
    }
    request_comment = owner(110, trace_collect.AGENT_TOOL_REQUEST_MARKER, request)
    first_close_comment = owner(
        200, "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2", close_one
    )
    late_result = bot(
        230,
        trace_collect.AGENT_TOOL_RESULT_MARKER,
        {
            "requestHash": contracts.request_hash(request),
            "begin": begin_ref,
            "actor": copy.deepcopy(actor),
            "status": "PASS",
            "blockers": [],
        },
    )
    retry_close_comment = owner(
        260, "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2", close_two
    )
    first_comments = [begin_boundary, request_comment, first_close_comment]
    retry_comments = [
        begin_boundary,
        request_comment,
        first_close_comment,
        late_result,
        retry_close_comment,
    ]

    original_fetch = trace_collect.fetch_issue_comments
    try:
        trace_collect.fetch_issue_comments = lambda repository, issue: copy.deepcopy(first_comments)
        first_error = None
        try:
            hosted_agent_cycle.close_from_envelope(
                close_one,
                {"issueNumber": 145, "commentId": 200},
                begin_dir=str(begin_root),
                output_path=str(first_root / "closure.json"),
                evidence_dir=str(first_root / "evidence"),
            )
        except hosted_agent_cycle.HostedAgentCycleError as exc:
            first_error = exc.code
        if first_error != "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE":
            raise SystemExit(f"QUALIFICATION_FIRST_CLOSE_UNEXPECTED:{first_error}")

        trace_collect.fetch_issue_comments = lambda repository, issue: copy.deepcopy(retry_comments)
        retry_result = hosted_agent_cycle.close_from_envelope(
            close_two,
            {"issueNumber": 145, "commentId": 260},
            begin_dir=str(begin_root),
            output_path=str(retry_root / "closure.json"),
            evidence_dir=str(retry_root / "evidence"),
        )
    finally:
        trace_collect.fetch_issue_comments = original_fetch

    if retry_result.get("status") != "PASS":
        raise SystemExit("QUALIFICATION_RETRY_CLOSE_NOT_PASS")
    trace = json.loads((retry_root / "execution-trace.json").read_text(encoding="utf-8"))
    attempts = trace.get("attempts") or []
    if trace.get("traceStatus") != "PASS":
        raise SystemExit("QUALIFICATION_TRACE_NOT_PASS")
    if trace.get("window", {}).get("closeCommentId") != 200:
        raise SystemExit("QUALIFICATION_SEAL_MOVED")
    if len(attempts) != 1:
        raise SystemExit(f"QUALIFICATION_REQUEST_SET_CHANGED:{len(attempts)}")
    if attempts[0].get("requestCommentId") != 110:
        raise SystemExit("QUALIFICATION_REQUEST_FRONTIER_CHANGED")
    if attempts[0].get("resultCommentId") != 230:
        raise SystemExit("QUALIFICATION_LATE_RESULT_NOT_OBSERVED")

    summary = {
        "schemaVersion": "R4AHostedDelayedResultQualification 0.1",
        "targetHead": TARGET,
        "harnessHead": os.environ["GITHUB_SHA"],
        "harnessDelta": changed,
        "firstCloseStatus": "BLOCKED",
        "firstCloseError": first_error,
        "retryCloseStatus": retry_result["status"],
        "sealCommentId": trace["window"]["closeCommentId"],
        "observationCommentId": 260,
        "requestCommentId": attempts[0]["requestCommentId"],
        "lateResultCommentId": attempts[0]["resultCommentId"],
        "operationReplayCount": 0,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

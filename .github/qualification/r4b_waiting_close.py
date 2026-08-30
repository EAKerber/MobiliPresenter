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
from tools import hosted_agent_cycle_trace
from tools import hosted_agent_cycle_waiting
from tools.agent_tools import contracts, trace_collect

TARGET = "83ef86dde0e152032200d58d2cf5ba432d12c692"
EXPECTED_DELTA = [
    ".github/qualification/r4b_waiting_close.py",
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


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", f"{TARGET}..HEAD"], text=True
    ).splitlines()
    if changed != EXPECTED_DELTA:
        raise SystemExit(f"QUALIFICATION_DELTA_INVALID:{changed}")

    root = Path("/tmp/r4b-hosted-qualification")
    begin_root = root / "begin"
    first_root = root / "close-first"
    retry_root = root / "close-retry"
    for path in (begin_root, first_root, retry_root):
        path.mkdir(parents=True, exist_ok=True)

    actor = {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": "r4b-hosted-qualification-20260830-01",
    }
    begin_command = {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": "r4b-hosted-begin-20260830-01",
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
        "requestId": "r4b-delayed-project-inspect",
        "begin": begin_ref,
        "actor": copy.deepcopy(actor),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    })
    post_seal_request = contracts.validate_request({
        **copy.deepcopy(request),
        "requestId": "r4b-post-seal-project-inspect",
    })

    close_one = {
        "schemaVersion": "HostedAgentCycleCommand 0.2",
        "requestId": "r4b-hosted-close-one-20260830-01",
        "action": "close",
        "handle": copy.deepcopy(begin_result["handle"]),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    close_two = {**copy.deepcopy(close_one), "requestId": "r4b-hosted-close-two-20260830-01"}

    begin_boundary = {
        "id": 100,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": "synthetic-r4b-begin-boundary",
    }
    request_comment = owner(110, trace_collect.AGENT_TOOL_REQUEST_MARKER, request)
    first_close_comment = owner(200, "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2", close_one)
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
    post_seal_comment = owner(
        240, trace_collect.AGENT_TOOL_REQUEST_MARKER, post_seal_request
    )
    retry_close_comment = owner(260, "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2", close_two)

    first_comments = [begin_boundary, request_comment, first_close_comment]
    retry_comments = [
        begin_boundary,
        request_comment,
        first_close_comment,
        late_result,
        post_seal_comment,
        retry_close_comment,
    ]

    first_command_path = first_root / "command.json"
    first_meta_path = first_root / "meta.json"
    first_result_path = first_root / "result.json"
    retry_command_path = retry_root / "command.json"
    retry_meta_path = retry_root / "meta.json"
    retry_result_path = retry_root / "result.json"
    write_json(first_command_path, close_one)
    write_json(first_meta_path, {"issueNumber": 145, "commentId": 200})
    write_json(retry_command_path, close_two)
    write_json(retry_meta_path, {"issueNumber": 145, "commentId": 260})

    original_fetch = trace_collect.fetch_issue_comments
    original_sleep = hosted_agent_cycle_trace.time.sleep
    sleep_count = 0

    def forbidden_sleep(seconds: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        raise RuntimeError(f"QUALIFICATION_POLLING_FORBIDDEN:{seconds}")

    try:
        hosted_agent_cycle_trace.time.sleep = forbidden_sleep
        trace_collect.fetch_issue_comments = lambda repository, issue: copy.deepcopy(first_comments)
        first_rc = hosted_agent_cycle.main([
            "close",
            "--command", str(first_command_path),
            "--meta", str(first_meta_path),
            "--begin-dir", str(begin_root),
            "--closure", str(first_root / "closure.json"),
            "--evidence-dir", str(first_root / "evidence"),
            "--result", str(first_result_path),
        ])
        if first_rc == 0:
            raise SystemExit("QUALIFICATION_FIRST_CLOSE_UNEXPECTED_PASS")
        if not hosted_agent_cycle_waiting.promote_close_result(
            command_path=str(first_command_path),
            meta_path=str(first_meta_path),
            begin_dir=str(begin_root),
            closure_path=str(first_root / "closure.json"),
            result_path=str(first_result_path),
        ):
            raise SystemExit("QUALIFICATION_FIRST_CLOSE_NOT_PROMOTED")
        waiting = json.loads(first_result_path.read_text(encoding="utf-8"))
        hosted_agent_cycle_waiting.validate_waiting(waiting)
        if waiting.get("status") != "WAITING":
            raise SystemExit("QUALIFICATION_FIRST_CLOSE_NOT_WAITING")
        if waiting.get("waitingFor") != ["AGENT_TOOL_RESULT"]:
            raise SystemExit(f"QUALIFICATION_WAITING_TARGET_INVALID:{waiting.get('waitingFor')}")

        trace_collect.fetch_issue_comments = lambda repository, issue: copy.deepcopy(retry_comments)
        retry_rc = hosted_agent_cycle.main([
            "close",
            "--command", str(retry_command_path),
            "--meta", str(retry_meta_path),
            "--begin-dir", str(begin_root),
            "--closure", str(retry_root / "closure.json"),
            "--evidence-dir", str(retry_root / "evidence"),
            "--result", str(retry_result_path),
        ])
    finally:
        trace_collect.fetch_issue_comments = original_fetch
        hosted_agent_cycle_trace.time.sleep = original_sleep

    if sleep_count != 0:
        raise SystemExit(f"QUALIFICATION_POLLING_OBSERVED:{sleep_count}")
    if retry_rc != 0:
        raise SystemExit(f"QUALIFICATION_RETRY_CLOSE_RC:{retry_rc}")
    retry_result = json.loads(retry_result_path.read_text(encoding="utf-8"))
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
    if any(item.get("requestCommentId") == 240 for item in attempts):
        raise SystemExit("QUALIFICATION_POST_SEAL_REQUEST_ADMITTED")

    summary = {
        "schemaVersion": "R4BHostedWaitingCloseQualification 0.1",
        "targetHead": TARGET,
        "harnessHead": os.environ["GITHUB_SHA"],
        "harnessDelta": changed,
        "firstCloseStatus": waiting["status"],
        "firstCloseWaitingFor": waiting["waitingFor"],
        "retryCloseStatus": retry_result["status"],
        "sealCommentId": trace["window"]["closeCommentId"],
        "observationCommentId": 260,
        "requestCommentId": attempts[0]["requestCommentId"],
        "lateResultCommentId": attempts[0]["resultCommentId"],
        "postSealRequestCommentId": 240,
        "postSealRequestAdmitted": False,
        "pollingSleepCount": sleep_count,
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

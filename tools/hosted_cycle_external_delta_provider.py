"""Provider observations for sealed-close external-delta recovery.

These adapters create no semantic authority. Their observations are revalidated
by the canonical close policy before any recovery certificate can be emitted.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from tools import hosted_agent_cycle, hosted_cycle_records

REPOSITORY = hosted_agent_cycle.REPOSITORY
WORKFLOW_ID = "hosted-agent-cycle.yml"
WORKFLOW_NAME = "Hosted Agent Cycle"


class HostedCycleExternalDeltaProviderError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _json(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise HostedCycleExternalDeltaProviderError(code) from exc


def _get(transport: Any, endpoint: str, code: str) -> Any:
    try:
        return _json(transport.request("GET", endpoint), code)
    except HostedCycleExternalDeltaProviderError:
        raise
    except Exception as exc:
        raise HostedCycleExternalDeltaProviderError(code) from exc


def continuation_readback(
    *, before_sha: str, work_id: str, transport: Any
) -> tuple[str, list[str]]:
    ref = _get(
        transport,
        f"repos/{REPOSITORY}/git/ref/heads/coordination/continuations",
        "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_UNAVAILABLE",
    )
    obj = ref.get("object") if isinstance(ref, dict) else None
    after_sha = obj.get("sha") if isinstance(obj, dict) else None
    if not isinstance(after_sha, str) or len(after_sha) != 40 or after_sha == before_sha:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_UNAVAILABLE"
        )
    comparison = _get(
        transport,
        f"repos/{REPOSITORY}/compare/{before_sha}...{after_sha}",
        "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_UNAVAILABLE",
    )
    files = comparison.get("files") if isinstance(comparison, dict) else None
    if comparison.get("status") != "ahead" or not isinstance(files, list):
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_UNAVAILABLE"
        )
    raw_paths = [
        item.get("filename")
        for item in files
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    ]
    paths = sorted(set(raw_paths))
    if len(paths) != len(raw_paths):
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_UNAVAILABLE"
        )
    if f"ops/continuations/{work_id}.json" in paths:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_CHANGED"
        )
    return after_sha, paths


def merged_pull_request_chain(
    *,
    before_sha: str,
    after_sha: str,
    work_branch: str,
    work_pr_number: int | None,
    transport: Any,
) -> list[dict[str, Any]]:
    """Walk the first-parent main chain and bind every step to one merged PR."""
    cursor = after_sha
    reverse: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(100):
        if cursor == before_sha:
            break
        if cursor in seen:
            raise HostedCycleExternalDeltaProviderError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INVALID"
            )
        seen.add(cursor)
        commit = _get(
            transport,
            f"repos/{REPOSITORY}/commits/{cursor}",
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INVALID",
        )
        parents = commit.get("parents") if isinstance(commit, dict) else None
        if not isinstance(parents, list) or len(parents) < 2:
            raise HostedCycleExternalDeltaProviderError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_NOT_MERGE_ONLY"
            )
        base_sha = parents[0].get("sha") if isinstance(parents[0], dict) else None
        if not isinstance(base_sha, str) or len(base_sha) != 40:
            raise HostedCycleExternalDeltaProviderError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INVALID"
            )
        pulls = _get(
            transport,
            f"repos/{REPOSITORY}/commits/{cursor}/pulls",
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INVALID",
        )
        if not isinstance(pulls, list):
            raise HostedCycleExternalDeltaProviderError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INVALID"
            )
        matches = []
        for pull in pulls:
            if not isinstance(pull, dict):
                continue
            head = pull.get("head")
            base = pull.get("base")
            number = pull.get("number")
            if (
                pull.get("merged_at") is not None
                and pull.get("merge_commit_sha") == cursor
                and isinstance(head, dict)
                and isinstance(head.get("ref"), str)
                and isinstance(base, dict)
                and base.get("ref") == "main"
                and isinstance(number, int)
                and not isinstance(number, bool)
                and head["ref"] != work_branch
                and (work_pr_number is None or number != work_pr_number)
            ):
                matches.append(pull)
        if len(matches) != 1:
            raise HostedCycleExternalDeltaProviderError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_AMBIGUOUS"
            )
        pull = matches[0]
        reverse.append({
            "commitSha": cursor,
            "prNumber": pull["number"],
            "headBranch": pull["head"]["ref"],
            "baseSha": base_sha,
        })
        cursor = base_sha
    else:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_TOO_DEEP"
        )
    if cursor != before_sha or not reverse:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INCOMPLETE"
        )
    return list(reversed(reverse))


def _created_at(comment: dict[str, Any]) -> datetime:
    value = comment.get("created_at")
    if not isinstance(value, str):
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSE_TIME_UNAVAILABLE"
        )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSE_TIME_UNAVAILABLE"
        ) from exc


def close_run_candidates(
    comments: list[dict[str, Any]],
    *, close_comment_id: int, transport: Any
) -> list[dict[str, Any]]:
    matches = [
        item for item in comments
        if hosted_cycle_records.comment_id(item) == close_comment_id
    ]
    if len(matches) != 1:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSE_COMMENT_INVALID"
        )
    when = _created_at(matches[0])
    start = (when - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    end = (when + timedelta(seconds=20)).isoformat().replace("+00:00", "Z")
    created = quote(f"{start}..{end}", safe=".:TZ-")
    payload = _get(
        transport,
        (
            f"repos/{REPOSITORY}/actions/workflows/{WORKFLOW_ID}/runs"
            f"?event=issue_comment&created={created}&per_page=100"
        ),
        "HOSTED_CYCLE_EXTERNAL_DELTA_RUNS_UNAVAILABLE",
    )
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_RUNS_UNAVAILABLE"
        )
    candidates: list[dict[str, Any]] = []
    for run in runs:
        if (
            not isinstance(run, dict)
            or run.get("name") != WORKFLOW_NAME
            or run.get("event") != "issue_comment"
            or not isinstance(run.get("id"), int)
        ):
            continue
        run_id = run["id"]
        artifacts_payload = _get(
            transport,
            f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts",
            "HOSTED_CYCLE_EXTERNAL_DELTA_ARTIFACT_UNAVAILABLE",
        )
        artifacts = (
            artifacts_payload.get("artifacts")
            if isinstance(artifacts_payload, dict)
            else None
        )
        if not isinstance(artifacts, list):
            continue
        exact = [
            item for item in artifacts
            if isinstance(item, dict)
            and item.get("name") == f"agent-cycle-close-{run_id}"
            and item.get("expired") is False
        ]
        if len(exact) == 1:
            candidates.append({
                "runId": run_id,
                "artifactId": exact[0].get("id"),
                "artifactName": exact[0]["name"],
            })
    if not candidates:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_ARTIFACT_UNAVAILABLE"
        )
    return candidates


def download_close_artifact(
    candidate: dict[str, Any], *, destination: str | Path
) -> Path:
    run_id = candidate.get("runId")
    name = candidate.get("artifactName")
    if not isinstance(run_id, int) or not isinstance(name, str) or not name:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_ARTIFACT_INVALID"
        )
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "gh", "run", "download", str(run_id), "-R", REPOSITORY,
            "-n", name, "-D", str(root),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_ARTIFACT_DOWNLOAD_FAILED"
        )
    if not (root / "closure.json").exists() or not (root / "result.json").exists():
        raise HostedCycleExternalDeltaProviderError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_ARTIFACT_INVALID"
        )
    return root

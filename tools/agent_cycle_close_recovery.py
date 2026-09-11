from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from tools import agent_cycle_close as _canonical
from tools import git_mutation_plan
from tools.coordination_remote import ApiError, CoordinationRemoteError, GhApiTransport

REPOSITORY = "EAKerber/MobiliPresenter"
CONTROL_BRANCH = "main"
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


def __getattr__(name: str) -> Any:
    return getattr(_canonical, name)


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise RuntimeError(code) from exc


def _get_json(transport: Any, endpoint: str, code: str) -> Any:
    try:
        response = transport.request("GET", endpoint)
    except (ApiError, CoordinationRemoteError) as exc:
        raise RuntimeError(code) from exc
    return _json_response(response, code)


def recoverable_main_delta(closure: Any) -> tuple[str, str] | None:
    if not isinstance(closure, dict) or closure.get("status") != "UNKNOWN":
        return None
    receipt = closure.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("blockers") != ["UNATTRIBUTED_DURABLE_DELTA"]:
        return None
    delta = receipt.get("delta")
    if not isinstance(delta, dict):
        return None
    changes = delta.get("durableChanges")
    if not isinstance(changes, list) or len(changes) != 1:
        return None
    change = changes[0]
    if not isinstance(change, dict):
        return None
    if (
        change.get("kind") != "source-head"
        or change.get("name") != "control"
        or change.get("branch") != CONTROL_BRANCH
    ):
        return None
    before = change.get("before")
    after = change.get("after")
    if (
        not isinstance(before, str)
        or not isinstance(after, str)
        or before == after
        or SHA_RE.fullmatch(before) is None
        or SHA_RE.fullmatch(after) is None
    ):
        return None
    aggregate = receipt.get("aggregateReadback")
    if not isinstance(aggregate, dict):
        return None
    uncovered = aggregate.get("uncoveredDurableChanges")
    if not isinstance(uncovered, list) or len(uncovered) != 1:
        return None
    return before, after


def merge_readback_evidence(
    before_sha: str,
    after_sha: str,
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    if SHA_RE.fullmatch(before_sha) is None or SHA_RE.fullmatch(after_sha) is None:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_SHA_INVALID")
    carrier = transport or GhApiTransport()

    ref = _get_json(
        carrier,
        f"repos/{REPOSITORY}/git/ref/heads/{CONTROL_BRANCH}",
        "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_MAIN_UNAVAILABLE",
    )
    observed_main = (ref.get("object") or {}).get("sha") if isinstance(ref, dict) else None
    if observed_main != after_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_MAIN_MISMATCH")

    commit = _get_json(
        carrier,
        f"repos/{REPOSITORY}/git/commits/{after_sha}",
        "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_COMMIT_UNAVAILABLE",
    )
    parents = commit.get("parents") if isinstance(commit, dict) else None
    if (
        not isinstance(parents, list)
        or len(parents) != 1
        or not isinstance(parents[0], dict)
        or parents[0].get("sha") != before_sha
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PARENT_MISMATCH")

    pulls = _get_json(
        carrier,
        f"repos/{REPOSITORY}/commits/{after_sha}/pulls",
        "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_UNAVAILABLE",
    )
    if not isinstance(pulls, list):
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_INVALID")
    candidates: list[dict[str, Any]] = []
    for item in pulls:
        if not isinstance(item, dict):
            continue
        base = item.get("base")
        head = item.get("head")
        if not isinstance(base, dict) or not isinstance(head, dict):
            continue
        if (
            item.get("state") == "closed"
            and isinstance(item.get("merged_at"), str)
            and item.get("merge_commit_sha") == after_sha
            and base.get("ref") == CONTROL_BRANCH
            and base.get("sha") == before_sha
            and isinstance(head.get("sha"), str)
            and SHA_RE.fullmatch(head["sha"]) is not None
            and isinstance(item.get("number"), int)
            and not isinstance(item.get("number"), bool)
            and item["number"] > 0
        ):
            candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_AMBIGUOUS")

    pull = candidates[0]
    head_sha = pull["head"]["sha"]
    plan = git_mutation_plan.merge_pr(
        pr_number=pull["number"],
        head_sha=head_sha,
        base=CONTROL_BRANCH,
        control_branch=CONTROL_BRANCH,
        merge_method="squash",
    )
    observed = {
        "kind": "merged-pr",
        "status": "PASS",
        "prNumber": pull["number"],
        "headSha": head_sha,
        "base": CONTROL_BRANCH,
        "merged": True,
        "mergeCommitSha": after_sha,
    }
    evidence = {
        "kind": "git-mutation-plan-readback",
        "plan": plan,
        "observed": observed,
    }
    _canonical.verify_evidence(evidence)
    return evidence


def recover_closure(
    closure: dict[str, Any],
    *,
    context_path: str,
    machine_scope: str | None,
    observations_path: str | None,
    runtime_providers: str | None,
    evidence_paths: list[str],
    transport: Any | None = None,
) -> dict[str, Any]:
    delta = recoverable_main_delta(closure)
    if delta is None:
        return closure
    try:
        evidence = merge_readback_evidence(*delta, transport=transport)
    except RuntimeError:
        return closure

    with tempfile.TemporaryDirectory(prefix="agent-close-merge-recovery-") as root:
        path = Path(root) / "merge-readback-evidence.json"
        path.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        recovered = _canonical.close_from_files(
            context_path=context_path,
            machine_scope=machine_scope,
            observations_path=observations_path,
            runtime_providers=runtime_providers,
            evidence_paths=[*evidence_paths, str(path)],
        )
    return recovered if recovered.get("status") == "PASS" else closure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent close")
    parser.add_argument("--context", required=True)
    parser.add_argument("--machine-scope", choices=("local", "base", "live"))
    parser.add_argument("--observations")
    parser.add_argument("--runtime-providers")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = _canonical.close_from_files(
            context_path=args.context,
            machine_scope=args.machine_scope,
            observations_path=args.observations,
            runtime_providers=args.runtime_providers,
            evidence_paths=args.evidence,
        )
        if payload.get("status") == "UNKNOWN":
            payload = recover_closure(
                payload,
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

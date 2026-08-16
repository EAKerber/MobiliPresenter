#!/usr/bin/env python3
"""Evidence-based branch prune planner for MobiliPresenter.

GitPrunePlan 0.2 is read-only. It classifies branch refs from explicit
ProjectState protection, complete PR history, and the current ref's ancestry
to the control branch. Names/prefixes never make a branch deletable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
ERROR_EXIT = 2


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_process(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout.strip()


def run_git(*args: str) -> tuple[bool, str]:
    if shutil.which("git") is None:
        return False, "git executable not found"
    return run_process(["git", *args])


def run_gh_json(endpoint: str) -> tuple[bool, Any]:
    if shutil.which("gh") is None:
        return False, "gh executable not found"
    ok, output = run_process(["gh", "api", endpoint])
    if not ok:
        return False, output
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return False, "gh returned non-JSON output"


def load_state() -> dict[str, Any]:
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("STATE_FILE_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("STATE_JSON_INVALID") from exc
    if not isinstance(state, dict) or state.get("schemaVersion") != "ProjectState 1.0":
        raise RuntimeError("STATE_SCHEMA_UNSUPPORTED")
    project = state.get("project")
    git_state = state.get("git")
    if not isinstance(project, dict) or project.get("repository") != "EAKerber/MobiliPresenter":
        raise RuntimeError("REPOSITORY_ID_MISMATCH")
    if not isinstance(git_state, dict) or not isinstance(git_state.get("controlBranch"), str):
        raise RuntimeError("STATE_GIT_INVALID")
    return state


def branch_refs_with_source() -> tuple[dict[str, str], str]:
    ok, output = run_git("for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/remotes/origin")
    refs: dict[str, str] = {}
    if ok:
        for line in output.splitlines():
            if not line.strip():
                continue
            name, sha = line.split("\t", 1)
            if name in {"origin", "origin/HEAD"} or not name.startswith("origin/"):
                continue
            refs[name.removeprefix("origin/")] = sha
    if refs:
        return refs, "remote-git-refs"

    ok, output = run_git("for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/heads")
    if not ok:
        raise RuntimeError(f"BRANCH_INVENTORY_FAILED:{output}")
    for line in output.splitlines():
        if not line.strip():
            continue
        name, sha = line.split("\t", 1)
        refs[name] = sha
    return refs, "local-heads"


def _normalize_pr(item: dict[str, Any], repository: str) -> dict[str, Any] | None:
    head = item.get("head")
    if not isinstance(head, dict):
        return None
    ref = head.get("ref")
    sha = head.get("sha")
    if not isinstance(ref, str) or not isinstance(sha, str):
        return None
    head_repo = head.get("repo")
    if isinstance(head_repo, dict):
        full_name = head_repo.get("full_name")
        if isinstance(full_name, str) and full_name.casefold() != repository.casefold():
            return None
    labels = item.get("labels") if isinstance(item.get("labels"), list) else []
    return {
        "number": item.get("number"),
        "state": item.get("state"),
        "draft": bool(item.get("draft")),
        "merged": bool(item.get("merged_at")),
        "mergedAt": item.get("merged_at"),
        "headRef": ref,
        "headSha": sha,
        "baseRef": item.get("base", {}).get("ref") if isinstance(item.get("base"), dict) else None,
        "title": item.get("title") if isinstance(item.get("title"), str) else "",
        "body": item.get("body") if isinstance(item.get("body"), str) else "",
        "labels": [label.get("name") for label in labels if isinstance(label, dict) and isinstance(label.get("name"), str)],
    }


def observe_pull_requests(state: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], str | None]:
    repository = state["project"]["repository"]
    normalized: list[dict[str, Any]] = []
    for page in range(1, 21):
        ok, payload = run_gh_json(f"repos/{repository}/pulls?state=all&per_page=100&page={page}")
        if not ok or not isinstance(payload, list):
            return False, [], "PR_HISTORY_READ_FAILED"
        for item in payload:
            if isinstance(item, dict):
                pr = _normalize_pr(item, repository)
                if pr is not None:
                    normalized.append(pr)
        if len(payload) < 100:
            return True, normalized, None
    return False, [], "PR_HISTORY_PAGINATION_LIMIT"


def ancestry_for_ref(sha: str, control_sha: str) -> str:
    if sha == control_sha:
        return "identical-to-control"
    ancestor, _ = run_git("merge-base", "--is-ancestor", sha, control_sha)
    if ancestor:
        return "ancestor-of-control"
    reverse, _ = run_git("merge-base", "--is-ancestor", control_sha, sha)
    if reverse:
        return "control-ancestor-of-branch"
    base_ok, base = run_git("merge-base", sha, control_sha)
    if base_ok and base:
        return "diverged"
    return "unknown"


def observe_ancestry(refs: dict[str, str], control_branch: str) -> tuple[dict[str, str], bool]:
    control_sha = refs.get(control_branch)
    if not control_sha:
        return {branch: "unknown" for branch in refs}, False
    result = {branch: ancestry_for_ref(sha, control_sha) for branch, sha in refs.items()}
    return result, all(value != "unknown" for value in result.values())


def _normalized_marker_text(value: str) -> str:
    value = value.casefold().replace("—", " ").replace("–", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def terminal_disposition(pr: dict[str, Any]) -> str | None:
    if pr.get("state") != "closed" or pr.get("merged"):
        return None
    title = _normalized_marker_text(str(pr.get("title") or ""))
    body = _normalized_marker_text(str(pr.get("body") or ""))
    if title.startswith("superseded") or body.startswith("superseded by"):
        return "superseded"
    if title.startswith("rejected"):
        return "rejected"
    if title.startswith("validation only"):
        return "validation-only"
    if title.startswith("closed preview only") or title.startswith("preview only"):
        return "preview-only"
    if body.startswith("substituido por") or body.startswith("substituído por"):
        return "superseded"
    return None


def _pr_index(pull_requests: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_branch: dict[str, list[dict[str, Any]]] = {}
    for pr in pull_requests:
        ref = pr.get("headRef")
        if isinstance(ref, str):
            by_branch.setdefault(ref, []).append(pr)
    for prs in by_branch.values():
        prs.sort(key=lambda pr: int(pr.get("number") or 0))
    return by_branch


def _protection_reasons(state: dict[str, Any], branch: str, open_pr_heads: set[str]) -> list[str]:
    git_state = state["git"]
    reasons: list[str] = []
    if branch == git_state.get("controlBranch"):
        reasons.append("control-branch")
    if branch == git_state.get("publishedBranch"):
        reasons.append("published-branch")
    if branch == git_state.get("activeDevelopmentBranch"):
        reasons.append("active-development")
    if branch in set(git_state.get("preserveBranches") or []):
        reasons.append("project-state-preserve")
    if branch in open_pr_heads:
        reasons.append("open-pr-head")
    return reasons


def build_prune_plan(
    state: dict[str, Any],
    refs: dict[str, str],
    pull_requests: list[dict[str, Any]] | None,
    ancestry: dict[str, str] | None,
    *,
    branch_inventory_complete: bool = True,
    ancestry_complete: bool = True,
) -> dict[str, Any]:
    git_state = state["git"]
    control_branch = git_state["controlBranch"]
    control_sha = refs.get(control_branch)
    pr_history_complete = pull_requests is not None
    pr_index = _pr_index(pull_requests or [])
    open_pr_heads = {
        str(pr["headRef"])
        for pr in (pull_requests or [])
        if pr.get("state") == "open" and isinstance(pr.get("headRef"), str)
    }

    entries: list[dict[str, Any]] = []
    for branch, sha in sorted(refs.items()):
        protections = _protection_reasons(state, branch, open_pr_heads)
        branch_prs = pr_index.get(branch, [])
        ancestry_status = ancestry.get(branch, "unknown") if ancestry is not None else "unknown"
        pr_provenance = []
        strong: list[str] = []
        for pr in branch_prs:
            head_matches = pr.get("headSha") == sha
            disposition = terminal_disposition(pr)
            provenance = {
                "number": pr.get("number"),
                "state": pr.get("state"),
                "merged": bool(pr.get("merged")),
                "headSha": pr.get("headSha"),
                "headMatchesCurrent": head_matches,
                "disposition": disposition,
            }
            pr_provenance.append(provenance)
            if head_matches and pr.get("merged"):
                strong.append(f"merged-pr:{pr.get('number')}")
            elif head_matches and disposition:
                strong.append(f"terminal-pr:{disposition}:{pr.get('number')}")

        if ancestry_status in {"ancestor-of-control", "identical-to-control"}:
            strong.append(ancestry_status)

        historical_anchor = branch.startswith(("archive/", "backup/"))
        if protections:
            action, reason, auto = "keep", "protected", False
        elif historical_anchor:
            action, reason, auto = "keep", "historical-or-rollback-anchor", False
        elif branch.startswith("variant/"):
            action, reason, auto = "archive-first", "legacy-variant-history", False
        elif strong:
            action, reason, auto = "delete-candidate", "strong-observed-evidence", True
        else:
            action, reason, auto = "review", "insufficient-delete-evidence", False

        entries.append({
            "branch": branch,
            "sha": sha,
            "action": action,
            "reason": reason,
            "autoDeleteEligible": auto,
            "protections": protections,
            "ancestryToControl": ancestry_status,
            "prProvenance": pr_provenance,
            "evidence": sorted(set(strong)),
            "duplicateOf": [],
        })

    by_sha: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_sha.setdefault(entry["sha"], []).append(entry)
    for same_sha_entries in by_sha.values():
        integrated = [entry for entry in same_sha_entries if entry["action"] == "delete-candidate"]
        if not integrated:
            continue
        integrated_names = sorted(entry["branch"] for entry in integrated)
        for entry in same_sha_entries:
            if entry["action"] != "review":
                continue
            duplicates = [name for name in integrated_names if name != entry["branch"]]
            if duplicates:
                entry["duplicateOf"] = duplicates
                entry["evidence"].append(f"duplicate-of-integrated-head:{duplicates[0]}")
                entry["action"] = "delete-candidate"
                entry["reason"] = "exact-duplicate-of-integrated-head"
                entry["autoDeleteEligible"] = True

    observations_complete = branch_inventory_complete and pr_history_complete and ancestry_complete and control_sha is not None
    body = {
        "schemaVersion": "GitPrunePlan 0.2",
        "repository": state["project"]["repository"],
        "controlBranch": control_branch,
        "controlSha": control_sha,
        "branchCount": len(refs),
        "observations": {
            "branchInventoryComplete": branch_inventory_complete,
            "prHistoryComplete": pr_history_complete,
            "ancestryComplete": ancestry_complete,
        },
        "openPrHeads": sorted(open_pr_heads),
        "entries": entries,
        "applyEligible": observations_complete,
        "destructiveApplySupported": False,
        "note": "Read-only evidence plan. Prefixes never authorize deletion. Current CLI has no destructive apply command; future apply must revalidate planHash and exact branch SHA immediately before each delete.",
    }
    return {**body, "planHash": stable_hash(body)}


def build_live_plan() -> dict[str, Any]:
    state = load_state()
    refs, source = branch_refs_with_source()
    prs_ok, prs, prs_error = observe_pull_requests(state)
    ancestry, ancestry_complete = observe_ancestry(refs, state["git"]["controlBranch"])
    branch_inventory_complete = source == "remote-git-refs"
    plan = build_prune_plan(
        state,
        refs,
        prs if prs_ok else None,
        ancestry,
        branch_inventory_complete=branch_inventory_complete,
        ancestry_complete=ancestry_complete,
    )
    plan["branchInventorySource"] = source
    if not prs_ok:
        plan["remoteObservationError"] = prs_error
    return plan


def command(as_json: bool) -> int:
    try:
        plan = build_live_plan()
    except RuntimeError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}")
        return ERROR_EXIT
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        counts: dict[str, int] = {}
        for entry in plan["entries"]:
            counts[entry["action"]] = counts.get(entry["action"], 0) + 1
        print("GIT PRUNE PLAN 0.2")
        print(f"  branches: {plan['branchCount']}")
        print(f"  keep: {counts.get('keep', 0)}")
        print(f"  delete-candidate: {counts.get('delete-candidate', 0)}")
        print(f"  archive-first: {counts.get('archive-first', 0)}")
        print(f"  review: {counts.get('review', 0)}")
        print(f"  apply eligible: {plan['applyEligible']}")
        print(f"  destructive apply supported: {plan['destructiveApplySupported']}")
        print(f"  planHash: {plan['planHash']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MobiliPresenter evidence-based branch prune planner")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        raise SystemExit("UNSUPPORTED_TRANSITION: GitPrunePlan 0.2 is read-only")
    return command(args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())

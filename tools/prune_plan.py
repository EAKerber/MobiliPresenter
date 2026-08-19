#!/usr/bin/env python3
"""Evidence-based branch sanitation planner for MobiliPresenter.

GitPrunePlan 0.4 is read-only. It classifies branch refs from explicit
protection and objective Git/PR/Work evidence. Branch names are descriptive
only: they never grant retention, protection, lifecycle state, or delete
eligibility.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import continuation, project_state, publication, work_graph
from tools.canonical import stable_hash
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority
from tools.semantics import registry as semantic_registry
from tools.semantics.branches import parse_branch_name

STATE_PATH = project_state.STATE_PATH
ERROR_EXIT = 2
SCHEMA_VERSION = "GitPrunePlan 0.4"
OBSERVATION_FLAGS = (
    "branchInventoryComplete",
    "prHistoryComplete",
    "ancestryComplete",
    "workAuthorityComplete",
)
EXECUTION_FLAGS = (
    "executorAvailable",
    "requiresPlanFile",
    "requiresExpectedPlan",
    "requiresExplicitAuthorization",
)
TOP_FIELDS = {
    "schemaVersion", "repository", "controlBranch", "controlSha", "branchCount",
    "observations", "execution", "openPrHeads", "openPrBases", "entries", "note", "planHash",
}
OBSERVATION_FIELDS = {
    "complete", "branchInventoryComplete", "branchInventorySource", "prHistoryComplete",
    "prHistoryError", "ancestryComplete", "workAuthorityComplete", "workAuthorityHead",
    "workAuthorityError",
}
EXECUTION_FIELDS = set(EXECUTION_FLAGS)
ENTRY_FIELDS = {
    "branch", "sha", "branchIdentity", "action", "reason", "autoDeleteEligible",
    "protections", "ancestryToControl", "prProvenance", "evidence", "duplicateOf",
}
ACTIONS = {"keep", "review", "delete-candidate"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")

COLD_ARCHIVE_BRANCH = "archive/cold"
COLD_ARCHIVE_INDEX_PATH = "COLD_ARCHIVE.json"
COLD_ARCHIVE_INDEX_SCHEMA = "ColdArchiveIndex 0.1"
COLD_ARCHIVE_INDEX_FIELDS = {"schemaVersion", "repository", "archiveBranch", "controlSha", "entries"}
COLD_ARCHIVE_ENTRY_FIELDS = {"branch", "headSha", "classification", "evidencePath"}
COLD_ARCHIVE_DELETE_CLASSES = {
    "DUPLICATE_HISTORY",
    "ARTIFACT_HISTORY",
    "HISTORICAL_EVIDENCE",
    "PROMOTE_KNOWLEDGE_THEN_HISTORICAL",
    "CURRENT_KNOWLEDGE_ALREADY_PROMOTED",
}


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
    state = project_state.load_state()
    errors = project_state.validate_current(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return state


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"PLAN_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PLAN_JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PLAN_ROOT_INVALID")
    return value


def _optional_nonempty(value: Any, code: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise RuntimeError(code)


def validate_plan(plan: Any, *, require_complete: bool = True) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != TOP_FIELDS:
        raise RuntimeError("PLAN_FIELDS_INVALID")
    if plan.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("PLAN_SCHEMA_UNSUPPORTED")
    if not isinstance(plan.get("repository"), str) or not plan["repository"]:
        raise RuntimeError("PLAN_IDENTITY_INVALID")
    if not isinstance(plan.get("controlBranch"), str) or not plan["controlBranch"]:
        raise RuntimeError("PLAN_IDENTITY_INVALID")
    if not isinstance(plan.get("controlSha"), str) or not SHA_RE.fullmatch(plan["controlSha"]):
        raise RuntimeError("PLAN_IDENTITY_INVALID")

    observations = plan.get("observations")
    if not isinstance(observations, dict) or set(observations) != OBSERVATION_FIELDS:
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    if type(observations.get("complete")) is not bool:
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    if any(type(observations.get(key)) is not bool for key in OBSERVATION_FLAGS):
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    source = observations.get("branchInventorySource")
    if not isinstance(source, str) or not source:
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    _optional_nonempty(observations.get("prHistoryError"), "PLAN_OBSERVATIONS_INVALID")
    _optional_nonempty(observations.get("workAuthorityError"), "PLAN_OBSERVATIONS_INVALID")
    work_head = observations.get("workAuthorityHead")
    if work_head is not None and (not isinstance(work_head, str) or not SHA_RE.fullmatch(work_head)):
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    if observations.get("workAuthorityComplete") is True and work_head is None:
        raise RuntimeError("PLAN_OBSERVATIONS_INVALID")
    if require_complete and (
        observations.get("complete") is not True
        or not all(observations.get(key) is True for key in OBSERVATION_FLAGS)
    ):
        raise RuntimeError("PLAN_OBSERVATION_INCOMPLETE")

    execution = plan.get("execution")
    if (
        not isinstance(execution, dict)
        or set(execution) != EXECUTION_FIELDS
        or not all(execution.get(key) is True for key in EXECUTION_FLAGS)
    ):
        raise RuntimeError("PLAN_EXECUTION_CONTRACT_INVALID")

    entries = plan.get("entries")
    if (
        not isinstance(entries, list)
        or type(plan.get("branchCount")) is not int
        or plan["branchCount"] != len(entries)
    ):
        raise RuntimeError("PLAN_ENTRIES_INVALID")
    for field in ("openPrHeads", "openPrBases"):
        values = plan.get(field)
        if (
            not isinstance(values, list)
            or len(values) != len(set(values))
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise RuntimeError("PLAN_PR_RELATIONS_INVALID")

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
            raise RuntimeError("PLAN_ENTRY_INVALID")
        branch, sha = entry.get("branch"), entry.get("sha")
        if (
            not isinstance(branch, str) or not branch or branch in seen
            or not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
        ):
            raise RuntimeError("PLAN_REF_INVALID")
        seen.add(branch)
        if entry.get("action") not in ACTIONS or type(entry.get("autoDeleteEligible")) is not bool:
            raise RuntimeError("PLAN_ENTRY_INVALID")
        for field in ("protections", "prProvenance", "evidence", "duplicateOf"):
            if not isinstance(entry.get(field), list):
                raise RuntimeError("PLAN_ENTRY_INVALID")
        if entry["protections"] and entry["action"] != "keep":
            raise RuntimeError(f"PROTECTED_CANDIDATE:{branch}")
        if entry["action"] == "delete-candidate" and entry["autoDeleteEligible"] is not True:
            raise RuntimeError("PLAN_ENTRY_INVALID")

    plan_hash = plan.get("planHash")
    if not isinstance(plan_hash, str) or not HASH_RE.fullmatch(plan_hash):
        raise RuntimeError("PLAN_HASH_MISSING")
    body = {key: value for key, value in plan.items() if key != "planHash"}
    if stable_hash(body) != plan_hash:
        raise RuntimeError("PLAN_HASH_MISMATCH")
    return plan


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
        if line.strip():
            name, sha = line.split("\t", 1)
            refs[name] = sha
    return refs, "local-heads"


def _normalize_pr(item: dict[str, Any], repository: str) -> dict[str, Any] | None:
    head = item.get("head")
    if not isinstance(head, dict):
        return None
    ref, sha = head.get("ref"), head.get("sha")
    if not isinstance(ref, str) or not isinstance(sha, str):
        return None
    head_repo = head.get("repo")
    if isinstance(head_repo, dict):
        full_name = head_repo.get("full_name")
        if isinstance(full_name, str) and full_name.casefold() != repository.casefold():
            return None
    base = item.get("base")
    return {
        "number": item.get("number"), "state": item.get("state"), "draft": bool(item.get("draft")),
        "merged": bool(item.get("merged_at")), "mergedAt": item.get("merged_at"),
        "headRef": ref, "headSha": sha, "baseRef": base.get("ref") if isinstance(base, dict) else None,
    }


def observe_pull_requests(state: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], str | None]:
    repository = project_state.operational_view(state)["project"]["repository"]
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


def observe_work(repository: str) -> tuple[bool, list[dict[str, Any]] | None, str | None, str | None]:
    try:
        observed = GitHubContinuationAuthority(repository=repository).observe()
        items = [continuation.operational_view(value) for _, value in sorted(observed.items.items())]
        work_graph.active_execution_bindings(items)
        return True, items, observed.head_sha, None
    except (ContinuationRemoteError, RuntimeError) as exc:
        code = getattr(exc, "code", str(exc).split(":", 1)[0])
        return False, None, None, str(code)


def managed_git_authority_branches() -> set[str]:
    registry = semantic_registry.load_registry()
    errors = semantic_registry.validate_registry(registry)
    if errors:
        raise RuntimeError(f"SEMANTIC_REGISTRY_INVALID:{errors[0]}")
    result: set[str] = set()
    authorities = registry.get("managedAuthorities")
    if not isinstance(authorities, dict):
        raise RuntimeError("SEMANTIC_REGISTRY_INVALID:SEMANTIC_AUTHORITIES_INVALID")
    for authority in authorities.values():
        locator = authority.get("locator") if isinstance(authority, dict) else None
        if not isinstance(locator, dict) or locator.get("kind") != "git-authority":
            continue
        branch = locator.get("branch")
        if not isinstance(branch, str) or not branch:
            raise RuntimeError("SEMANTIC_REGISTRY_INVALID:SEMANTIC_LOCATOR_FIELDS_INVALID")
        result.add(branch)
    return result


def observe_cold_archive(
    refs: dict[str, str], repository: str, *, control_branch: str,
) -> dict[str, str]:
    """Return strong evidence only for exact heads safely retained by archive/cold.

    Cold archive is optional evidence. Any malformed index, stale source head,
    non-historical classification, or failed reachability proof yields no
    delete evidence rather than blocking unrelated sanitation.
    """
    archive_head = refs.get(COLD_ARCHIVE_BRANCH)
    if not isinstance(archive_head, str) or not SHA_RE.fullmatch(archive_head):
        return {}
    ok, raw = run_git("show", f"{archive_head}:{COLD_ARCHIVE_INDEX_PATH}")
    if not ok:
        return {}
    try:
        index = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(index, dict) or set(index) != COLD_ARCHIVE_INDEX_FIELDS:
        return {}
    if index.get("schemaVersion") != COLD_ARCHIVE_INDEX_SCHEMA:
        return {}
    if index.get("repository") != repository or index.get("archiveBranch") != COLD_ARCHIVE_BRANCH:
        return {}
    control_sha = index.get("controlSha")
    if not isinstance(control_sha, str) or not SHA_RE.fullmatch(control_sha):
        return {}
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        return {}

    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != COLD_ARCHIVE_ENTRY_FIELDS:
            return {}
        branch = item.get("branch")
        head_sha = item.get("headSha")
        classification = item.get("classification")
        evidence_path = item.get("evidencePath")
        if (
            not isinstance(branch, str) or not branch or branch in seen
            or branch in {control_branch, COLD_ARCHIVE_BRANCH}
            or not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha)
            or classification not in COLD_ARCHIVE_DELETE_CLASSES
            or not isinstance(evidence_path, str) or not evidence_path
        ):
            return {}
        seen.add(branch)
        validated.append({
            "branch": branch,
            "headSha": head_sha,
            "classification": classification,
            "evidencePath": evidence_path,
        })

    evidence: dict[str, str] = {}
    for item in validated:
        branch, head_sha = item["branch"], item["headSha"]
        if refs.get(branch) != head_sha:
            continue
        reachable, _ = run_git("merge-base", "--is-ancestor", head_sha, archive_head)
        if reachable:
            evidence[branch] = f"cold-archive:{archive_head}"
    return evidence


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


def _pr_index(pull_requests: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_branch: dict[str, list[dict[str, Any]]] = {}
    for pr in pull_requests:
        ref = pr.get("headRef")
        if isinstance(ref, str):
            by_branch.setdefault(ref, []).append(pr)
    for prs in by_branch.values():
        prs.sort(key=lambda pr: int(pr.get("number") or 0))
    return by_branch


def _protection_reasons(
    view: dict[str, Any], branch: str, open_pr_heads: set[str], open_pr_bases: set[str],
    active_work_branches: set[str], managed_authority_branches: set[str], *,
    published_source_branch: str | None = None,
) -> list[str]:
    git_state = view["git"]
    reasons: list[str] = []
    if branch == git_state.get("controlBranch"):
        reasons.append("control-branch")
    if isinstance(published_source_branch, str) and branch == published_source_branch:
        reasons.append("published-branch")
    if branch in active_work_branches:
        reasons.append("active-work")
    if branch in managed_authority_branches:
        reasons.append("managed-authority")
    if branch in set(git_state.get("protectedBranches") or []):
        reasons.append("project-state-protected")
    if branch in open_pr_heads:
        reasons.append("open-pr-head")
    if branch in open_pr_bases:
        reasons.append("open-pr-base")
    return reasons


def build_prune_plan(
    state: dict[str, Any], refs: dict[str, str], pull_requests: list[dict[str, Any]] | None,
    ancestry: dict[str, str] | None, *, work_items: list[dict[str, Any]] | None,
    work_authority_complete: bool, work_authority_head: str | None,
    work_authority_error: str | None = None, branch_inventory_complete: bool = True,
    ancestry_complete: bool = True, branch_inventory_source: str = "fixture",
    remote_observation_error: str | None = None, published_source_branch: str | None = None,
    cold_archive_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    view = project_state.operational_view(state)
    git_state = view["git"]
    control_branch = git_state["controlBranch"]
    control_sha = refs.get(control_branch)
    pr_history_complete = pull_requests is not None
    pr_index = _pr_index(pull_requests or [])
    open_pr_heads = {
        str(pr["headRef"]) for pr in (pull_requests or [])
        if pr.get("state") == "open" and isinstance(pr.get("headRef"), str)
    }
    open_pr_bases = {
        str(pr["baseRef"]) for pr in (pull_requests or [])
        if pr.get("state") == "open" and isinstance(pr.get("baseRef"), str)
    }
    bindings = work_graph.active_execution_bindings(work_items) if work_items is not None else []
    active_work_branches = {
        binding["branch"] for binding in bindings
        if isinstance(binding.get("branch"), str) and binding["branch"]
    }
    managed_authority_branches = managed_git_authority_branches()
    cold_archive_evidence = cold_archive_evidence or {}

    entries: list[dict[str, Any]] = []
    for branch, sha in sorted(refs.items()):
        protections = _protection_reasons(
            view, branch, open_pr_heads, open_pr_bases, active_work_branches,
            managed_authority_branches, published_source_branch=published_source_branch,
        )
        branch_prs = pr_index.get(branch, [])
        ancestry_status = ancestry.get(branch, "unknown") if ancestry is not None else "unknown"
        provenance: list[dict[str, Any]] = []
        strong: list[str] = []
        for pr in branch_prs:
            head_matches = pr.get("headSha") == sha
            provenance.append({
                "number": pr.get("number"), "state": pr.get("state"), "merged": bool(pr.get("merged")),
                "headSha": pr.get("headSha"), "headMatchesCurrent": head_matches,
            })
            if head_matches and pr.get("merged"):
                strong.append(f"merged-pr:{pr.get('number')}")
        if ancestry_status in {"ancestor-of-control", "identical-to-control"}:
            strong.append(ancestry_status)
        archive_proof = cold_archive_evidence.get(branch)
        if isinstance(archive_proof, str) and archive_proof:
            strong.append(archive_proof)
        if protections:
            action, reason, auto = "keep", "protected", False
        elif strong:
            action, reason, auto = "delete-candidate", "strong-observed-evidence", True
        else:
            action, reason, auto = "review", "insufficient-delete-evidence", False
        try:
            identity = parse_branch_name(branch)
        except RuntimeError:
            identity = {
                "name": branch, "grammar": "invalid", "namespace": None, "declaredClass": None,
                "domain": None, "semanticDomain": None, "legacyAlias": False, "slug": None,
            }
        entries.append({
            "branch": branch, "sha": sha, "branchIdentity": identity, "action": action,
            "reason": reason, "autoDeleteEligible": auto, "protections": protections,
            "ancestryToControl": ancestry_status, "prProvenance": provenance,
            "evidence": sorted(set(strong)), "duplicateOf": [],
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

    work_complete = bool(work_authority_complete and work_items is not None and work_authority_head)
    observations_complete = bool(
        branch_inventory_complete and pr_history_complete and ancestry_complete
        and work_complete and control_sha is not None
    )
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": view["project"]["repository"],
        "controlBranch": control_branch,
        "controlSha": control_sha,
        "branchCount": len(refs),
        "observations": {
            "complete": observations_complete,
            "branchInventoryComplete": bool(branch_inventory_complete),
            "branchInventorySource": branch_inventory_source,
            "prHistoryComplete": pr_history_complete,
            "prHistoryError": remote_observation_error,
            "ancestryComplete": bool(ancestry_complete),
            "workAuthorityComplete": work_complete,
            "workAuthorityHead": work_authority_head,
            "workAuthorityError": work_authority_error,
        },
        "execution": {
            "executorAvailable": True, "requiresPlanFile": True,
            "requiresExpectedPlan": True, "requiresExplicitAuthorization": True,
        },
        "openPrHeads": sorted(open_pr_heads),
        "openPrBases": sorted(open_pr_bases),
        "entries": entries,
        "note": (
            "Evidence-only sanitation plan. Names never authorize retention or deletion; managed Git authority "
            "branches are derived from the Semantic Registry and active Work execution branches from the canonical "
            "Work authority; verified cold-archive reachability may retain exact historical heads while source refs "
            "converge; execution requires this exact materialized plan, explicit plan identity, authorization, drift "
            "checks, and readback."
        ),
    }
    return {**body, "planHash": stable_hash(body)}


def build_live_plan() -> dict[str, Any]:
    state = load_state()
    view = project_state.operational_view(state)
    repository = view["project"]["repository"]
    manifest = publication.load_manifest(view["published"]["artifactManifest"])
    published = publication.publication_view(view, manifest)
    refs, source = branch_refs_with_source()
    prs_ok, prs, prs_error = observe_pull_requests(state)
    ancestry, ancestry_complete = observe_ancestry(refs, view["git"]["controlBranch"])
    work_ok, work_items, work_head, work_error = observe_work(repository)
    cold_archive_evidence = observe_cold_archive(
        refs, repository, control_branch=view["git"]["controlBranch"],
    )
    return build_prune_plan(
        state, refs, prs if prs_ok else None, ancestry,
        work_items=work_items,
        work_authority_complete=work_ok,
        work_authority_head=work_head,
        work_authority_error=work_error,
        branch_inventory_complete=source == "remote-git-refs",
        ancestry_complete=ancestry_complete,
        branch_inventory_source=source,
        remote_observation_error=None if prs_ok else prs_error,
        published_source_branch=published["sourceBranch"],
        cold_archive_evidence=cold_archive_evidence,
    )


def command_generate(as_json: bool) -> int:
    try:
        plan = build_live_plan()
        validate_plan(plan, require_complete=False)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if as_json else f"BLOCKED\n{exc}")
        return ERROR_EXIT
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        counts: dict[str, int] = {}
        for entry in plan["entries"]:
            counts[entry["action"]] = counts.get(entry["action"], 0) + 1
        print("GIT PRUNE PLAN 0.4")
        print(f"  branches: {plan['branchCount']}")
        print(f"  keep: {counts.get('keep', 0)}")
        print(f"  delete-candidate: {counts.get('delete-candidate', 0)}")
        print(f"  review: {counts.get('review', 0)}")
        print(f"  observations complete: {plan['observations']['complete']}")
        print(f"  work authority: {plan['observations']['workAuthorityHead']}")
        print(f"  planHash: {plan['planHash']}")
    return 0


def command_validate(path: Path, as_json: bool) -> int:
    try:
        plan = validate_plan(load_plan(path), require_complete=True)
        payload = {"ok": True, "planHash": plan["planHash"]}
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        code = ERROR_EXIT
    else:
        code = 0
    print(
        json.dumps(payload, indent=2 if as_json else None, ensure_ascii=False)
        if as_json
        else (f"GIT PRUNE PLAN VALID\n  planHash: {payload['planHash']}" if code == 0 else f"BLOCKED\n{payload['error']}")
    )
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only evidence-based Git branch sanitation planner")
    parser.add_argument("command", nargs="?", choices=("generate", "validate"), default="generate")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.command == "validate":
        if args.path is None:
            parser.error("validate requires a plan path")
        return command_validate(args.path, args.as_json)
    if args.path is not None:
        parser.error("generate does not accept a plan path")
    return command_generate(args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())

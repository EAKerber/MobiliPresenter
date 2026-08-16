#!/usr/bin/env python3
"""Deterministic operational toolbox for MobiliPresenter agents.

Operational facts live in ProjectState and domain authorities. The toolbox
provides read-only observation/verification plus bounded transition helpers.
Branch pruning is planned separately and may be applied only by the guarded
Branch Hygiene executor after exact-plan validation and readback.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import prune_plan as git_prune_plan
except ModuleNotFoundError:
    from tools import prune_plan as git_prune_plan

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"
ERROR_EXIT = 2
TOOLBOX_COMMANDS = {"status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"STATE_FILE_MISSING: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STATE_JSON_INVALID: {path.relative_to(ROOT)}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"STATE_ROOT_INVALID: {path.relative_to(ROOT)} must contain an object")
    return value


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


def ci_branch_name() -> str | None:
    head_ref = os.environ.get("GITHUB_HEAD_REF")
    if head_ref:
        return head_ref
    if os.environ.get("GITHUB_REF_TYPE") == "branch":
        ref_name = os.environ.get("GITHUB_REF_NAME")
        return ref_name or None
    return None


def observed_git() -> dict[str, Any]:
    inside_ok, inside = run_git("rev-parse", "--is-inside-work-tree")
    if not inside_ok or inside != "true":
        return {"available": shutil.which("git") is not None, "worktree": False}
    branch_ok, branch = run_git("branch", "--show-current")
    observed_branch = branch if branch_ok and branch else ci_branch_name()
    head_ok, head = run_git("rev-parse", "HEAD")
    remote_ok, remote = run_git("remote", "get-url", "origin")
    dirty_ok, porcelain = run_git("status", "--porcelain")
    return {
        "available": True,
        "worktree": True,
        "branch": observed_branch,
        "head": head if head_ok else None,
        "origin": remote if remote_ok else None,
        "dirty": bool(porcelain) if dirty_ok else None,
    }


def validate_state_shape(state: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def require(path: str, value: Any, expected: type | tuple[type, ...]) -> None:
        if not isinstance(value, expected):
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"{path} has invalid type"})

    if state.get("schemaVersion") != "ProjectState 1.0":
        errors.append({"code": "STATE_SCHEMA_UNSUPPORTED", "detail": "schemaVersion must be ProjectState 1.0"})
    for key in ("project", "git", "published", "development", "operations"):
        require(key, state.get(key), dict)
    if errors:
        return errors

    if state["project"].get("id") != "mobilipresenter":
        errors.append({"code": "PROJECT_ID_MISMATCH", "detail": "project.id must be mobilipresenter"})
    if state["project"].get("repository") != "EAKerber/MobiliPresenter":
        errors.append({"code": "REPOSITORY_ID_MISMATCH", "detail": "unexpected canonical repository"})
    if state["operations"].get("canonicalState") != "ops/state/project.json":
        errors.append({"code": "CANONICAL_STATE_MISMATCH", "detail": "operations.canonicalState is unexpected"})

    sha = state["published"].get("artifactSha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        errors.append({"code": "ARTIFACT_SHA_INVALID", "detail": "published.artifactSha256 must be lowercase sha256"})

    git_state = state["git"]
    for key in ("controlBranch", "publishedBranch"):
        if not isinstance(git_state.get(key), str) or not git_state[key]:
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"git.{key} must be a non-empty string"})
    active = git_state.get("activeDevelopmentBranch")
    if active is not None and (not isinstance(active, str) or not active):
        errors.append({"code": "STATE_SCHEMA_INVALID", "detail": "git.activeDevelopmentBranch must be null or a non-empty string"})
    preserve = git_state.get("preserveBranches")
    if not isinstance(preserve, list) or any(not isinstance(item, str) or not item for item in preserve) or len(set(preserve or [])) != len(preserve or []):
        errors.append({"code": "STATE_SCHEMA_INVALID", "detail": "git.preserveBranches must contain unique non-empty strings"})

    development = state["development"]
    for key in ("initiative", "phase", "checkpoint", "nextTransition", "plan"):
        if not isinstance(development.get(key), str) or not development[key]:
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"development.{key} must be a non-empty string"})
    pr_number = development.get("prNumber")
    if pr_number is not None and (not isinstance(pr_number, int) or pr_number <= 0):
        errors.append({"code": "STATE_SCHEMA_INVALID", "detail": "development.prNumber must be null or a positive integer"})
    if (active is None) != (pr_number is None):
        errors.append({"code": "DEVELOPMENT_IDENTITY_INCOMPLETE", "detail": "activeDevelopmentBranch and prNumber must both be set or both be null"})

    commands = state["operations"].get("commands")
    if not isinstance(commands, list) or set(commands) != TOOLBOX_COMMANDS:
        errors.append({"code": "TOOLBOX_COMMANDS_MISMATCH", "detail": "operations.commands must contain Git Ops 1.2 commands"})
    return errors


def git_context_check(state: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    if not observed.get("worktree"):
        return {"name": "git-context", "status": "FAIL", "code": "NOT_A_GIT_WORKTREE"}
    branch = observed.get("branch")
    git_state = state["git"]
    active = git_state.get("activeDevelopmentBranch")
    control = git_state["controlBranch"]
    published = git_state["publishedBranch"]
    preserved = set(git_state.get("preserveBranches") or [])
    if active and branch == active:
        return {"name": "git-context", "status": "PASS", "code": None, "context": "active-development", "branch": branch}
    if branch in {control, published}:
        return {"name": "git-context", "status": "PASS", "code": None, "context": "control", "branch": branch}
    if branch in preserved:
        return {"name": "git-context", "status": "PASS", "code": None, "context": "preserved-parallel", "branch": branch}
    if isinstance(branch, str) and branch.startswith("ops/"):
        return {"name": "git-context", "status": "PASS", "code": None, "context": "operations", "branch": branch}
    return {"name": "git-context", "status": "FAIL", "code": "UNEXPECTED_BRANCH", "observed": branch, "expected": active}


def aggregate_ci(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "unknown"
    meaningful = [run for run in runs if run.get("name") != "Agent Ops"]
    if not meaningful:
        return "unknown"
    if any(str(run.get("status", "")).upper() != "COMPLETED" for run in meaningful):
        return "pending"
    conclusions = {str(run.get("conclusion") or "").upper() for run in meaningful}
    if conclusions <= {"SUCCESS", "NEUTRAL", "SKIPPED"}:
        return "green"
    if conclusions & {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
        return "failed"
    return "unknown"


def verification_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(check.get("status") or "UNKNOWN").upper() for check in checks]
    if any(status == "FAIL" for status in statuses):
        status = "FAIL"
    elif any(status == "UNKNOWN" for status in statuses):
        status = "UNKNOWN"
    else:
        status = "PASS"
    return {
        "status": status,
        "ok": status != "FAIL",
        "complete": status == "PASS",
    }


def observe_remote(state: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    active = state["git"].get("activeDevelopmentBranch")
    pr_number = state["development"].get("prNumber")
    if active is None and pr_number is None:
        return {"available": True, "developmentActive": False, "reason": "NO_ACTIVE_DEVELOPMENT", "ci": "unknown"}
    if shutil.which("gh") is None:
        return {"available": False, "reason": "GH_NOT_FOUND", "ci": "unknown"}
    if not isinstance(pr_number, int):
        return {"available": False, "reason": "PR_NUMBER_MISSING", "ci": "unknown"}
    repo = state["project"]["repository"]
    pr_ok, pr = run_gh_json(f"repos/{repo}/pulls/{pr_number}")
    if not pr_ok or not isinstance(pr, dict):
        return {"available": False, "reason": "PR_READ_FAILED", "detail": pr, "ci": "unknown"}
    head_sha = pr.get("head", {}).get("sha") if isinstance(pr.get("head"), dict) else None
    runs: list[dict[str, Any]] = []
    if isinstance(head_sha, str):
        runs_ok, workflow_payload = run_gh_json(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
        if runs_ok and isinstance(workflow_payload, dict) and isinstance(workflow_payload.get("workflow_runs"), list):
            runs = [
                {"name": item.get("name"), "status": item.get("status"), "conclusion": item.get("conclusion"), "id": item.get("id")}
                for item in workflow_payload["workflow_runs"] if isinstance(item, dict)
            ]
    return {
        "available": True,
        "developmentActive": True,
        "pr": {
            "number": pr.get("number"),
            "state": pr.get("state"),
            "draft": pr.get("draft"),
            "headRef": pr.get("head", {}).get("ref") if isinstance(pr.get("head"), dict) else None,
            "headSha": head_sha,
            "baseRef": pr.get("base", {}).get("ref") if isinstance(pr.get("base"), dict) else None,
        },
        "workflows": runs,
        "ci": aggregate_ci(runs),
        "observedHeadMatchesPr": observed.get("head") == head_sha if observed.get("head") else None,
    }


def remote_verification_checks(state: dict[str, Any], remote: dict[str, Any]) -> list[dict[str, Any]]:
    if remote.get("developmentActive") is False:
        return [{"name": "remote-development", "status": "PASS", "code": "NO_ACTIVE_DEVELOPMENT"}]
    if not remote.get("available"):
        return [{
            "name": "remote-observation",
            "status": "UNKNOWN",
            "code": "REMOTE_OBSERVATION_UNAVAILABLE",
            "observed": remote.get("reason"),
        }]

    pr = remote.get("pr", {})
    identity_ok = (
        pr.get("number") == state["development"].get("prNumber")
        and pr.get("headRef") == state["git"].get("activeDevelopmentBranch")
        and pr.get("baseRef") == state["git"].get("controlBranch")
        and pr.get("state") == "open"
    )
    checks = [{
        "name": "remote-pr-identity",
        "status": "PASS" if identity_ok else "FAIL",
        "code": None if identity_ok else "REMOTE_PR_DIVERGENCE",
    }]

    ci = str(remote.get("ci") or "unknown")
    if ci == "green":
        ci_status, ci_code = "PASS", None
    elif ci == "failed":
        ci_status, ci_code = "FAIL", "REMOTE_CI_FAILED"
    elif ci == "pending":
        ci_status, ci_code = "UNKNOWN", "REMOTE_CI_PENDING"
    else:
        ci_status, ci_code = "UNKNOWN", "REMOTE_CI_UNKNOWN"
    checks.append({"name": "remote-ci", "status": ci_status, "code": ci_code, "observed": ci})
    return checks


def verify_state(include_remote: bool = False) -> dict[str, Any]:
    state = load_json(STATE_PATH)
    checks: list[dict[str, Any]] = []
    errors = validate_state_shape(state)
    if errors:
        for error in errors:
            checks.append({"name": "project-state", "status": "FAIL", **error})
    else:
        checks.append({"name": "project-state", "status": "PASS", "code": None})

    checks.append({"name": "project-state-schema", "status": "PASS" if SCHEMA_PATH.is_file() else "FAIL",
                   "code": None if SCHEMA_PATH.is_file() else "SCHEMA_FILE_MISSING"})
    plan = state.get("development", {}).get("plan")
    plan_exists = isinstance(plan, str) and (ROOT / plan).is_file()
    checks.append({"name": "development-plan", "status": "PASS" if plan_exists else "FAIL",
                   "code": None if plan_exists else "DEVELOPMENT_PLAN_MISSING", "path": plan})

    manifest_rel = state.get("published", {}).get("artifactManifest") if isinstance(state.get("published"), dict) else None
    manifest_path = ROOT / manifest_rel if isinstance(manifest_rel, str) else None
    if manifest_path and manifest_path.is_file():
        manifest = load_json(manifest_path)
        expected_release = state["published"].get("release")
        expected_hash = state["published"].get("artifactSha256")
        match = manifest.get("release") == expected_release and manifest.get("sha256") == expected_hash
        checks.append({"name": "published-artifact-state", "status": "PASS" if match else "FAIL",
                       "code": None if match else "STATE_DIVERGENCE",
                       "observedRelease": manifest.get("release"), "observedSha256": manifest.get("sha256")})
    else:
        checks.append({"name": "published-artifact-state", "status": "FAIL", "code": "MANIFEST_MISSING"})

    for rel in ("AGENTS.md", "README.md", "deploy.py"):
        exists = (ROOT / rel).is_file()
        checks.append({"name": f"required:{rel}", "status": "PASS" if exists else "FAIL",
                       "code": None if exists else "REQUIRED_FILE_MISSING"})

    observed = observed_git()
    checks.append(git_context_check(state, observed))
    remote: dict[str, Any] | None = None
    if include_remote:
        remote = observe_remote(state, observed)
        checks.extend(remote_verification_checks(state, remote))

    summary = verification_summary(checks)
    return {**summary, "checks": checks, "remote": remote}


def checkpoint_candidate(state: dict[str, Any], checkpoint: str, next_transition: str, phase: str | None) -> dict[str, Any]:
    candidate = copy.deepcopy(state)
    candidate["development"]["checkpoint"] = checkpoint
    candidate["development"]["nextTransition"] = next_transition
    if phase:
        candidate["development"]["phase"] = phase
    return candidate


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temp_name = handle.name
    os.replace(temp_name, path)
    if path.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("STATE_READBACK_MISMATCH")


def command_status(as_json: bool, include_remote: bool) -> int:
    state = load_json(STATE_PATH)
    observed = observed_git()
    remote = observe_remote(state, observed) if include_remote else None
    payload = {
        "project": state["project"]["id"],
        "repository": state["project"]["repository"],
        "published": state["published"],
        "development": state["development"],
        "gitPolicy": state["git"],
        "observedGit": observed,
        "remote": remote,
        "next": state["development"]["nextTransition"],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        active = payload["gitPolicy"].get("activeDevelopmentBranch") or "(none)"
        print(f"PROJECT\n  id: {payload['project']}\n  repository: {payload['repository']}")
        print(f"\nPUBLISHED\n  release: {payload['published']['release']}\n  branch: {payload['gitPolicy']['publishedBranch']}\n  url: {payload['published']['url']}")
        print(f"\nDEVELOPMENT\n  initiative: {payload['development']['initiative']}\n  phase: {payload['development']['phase']}\n  checkpoint: {payload['development']['checkpoint']}\n  branch: {active}")
        blockers = payload["development"].get("blockers") or []
        print(f"\nBLOCKERS\n  {', '.join(blockers) if blockers else 'none'}")
        print(f"\nNEXT\n  {payload['next']}")
        if observed.get("worktree"):
            print(f"\nOBSERVED GIT\n  branch: {observed.get('branch')}\n  head: {observed.get('head')}\n  dirty: {observed.get('dirty')}")
        if remote:
            print(f"\nREMOTE\n  available: {remote.get('available')}\n  ci: {remote.get('ci')}")
    return 0


def command_doctor(as_json: bool) -> int:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "python", "status": "PASS" if sys.version_info >= (3, 10) else "FAIL",
                   "observed": sys.version.split()[0], "code": None if sys.version_info >= (3, 10) else "PYTHON_TOO_OLD"})
    checks.append({"name": "git-executable", "status": "PASS" if shutil.which("git") else "FAIL",
                   "code": None if shutil.which("git") else "GIT_NOT_FOUND"})
    checks.append({"name": "gh-executable", "status": "PASS" if shutil.which("gh") else "INFO",
                   "code": None if shutil.which("gh") else "GH_NOT_FOUND"})
    try:
        state = load_json(STATE_PATH)
        state_ok = not validate_state_shape(state)
        checks.append({"name": "project-state", "status": "PASS" if state_ok else "FAIL",
                       "code": None if state_ok else "STATE_SCHEMA_INVALID"})
    except RuntimeError as exc:
        checks.append({"name": "project-state", "status": "FAIL", "code": str(exc).split(":", 1)[0]})

    git = observed_git()
    if git.get("worktree"):
        expected_repo = "EAKerber/MobiliPresenter"
        origin = git.get("origin") or ""
        origin_ok = expected_repo.lower() in origin.lower()
        checks.append({"name": "git-origin", "status": "PASS" if origin_ok else "FAIL",
                       "observed": origin, "code": None if origin_ok else "WRONG_REPOSITORY"})
    else:
        checks.append({"name": "git-worktree", "status": "FAIL", "code": "NOT_A_GIT_WORKTREE"})

    ok = all(c["status"] in {"PASS", "INFO"} for c in checks)
    payload = {"ok": ok, "checks": checks}
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in checks:
            detail = f" ({check.get('observed')})" if check.get("observed") else ""
            code = f" [{check.get('code')}]" if check.get("code") else ""
            print(f"{check['status']:4} {check['name']}{detail}{code}")
        print("\nPASS" if ok else "\nBLOCKED")
    return 0 if ok else ERROR_EXIT


def command_verify(as_json: bool, include_remote: bool) -> int:
    payload = verify_state(include_remote=include_remote)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in payload["checks"]:
            code = f" [{check.get('code')}]" if check.get("code") else ""
            observed = f" ({check.get('observed')})" if check.get("observed") else ""
            print(f"{check['status']:7} {check['name']}{observed}{code}")
        print(f"\n{payload['status']}")
    return 0 if payload["status"] == "PASS" else ERROR_EXIT


def command_checkpoint(as_json: bool, args: argparse.Namespace) -> int:
    state = load_json(STATE_PATH)
    errors = validate_state_shape(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    candidate = checkpoint_candidate(state, args.checkpoint, args.next_transition, args.phase)
    candidate_errors = validate_state_shape(candidate)
    if candidate_errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{candidate_errors[0]['detail']}")
    change = {
        "from": {
            "phase": state["development"]["phase"],
            "checkpoint": state["development"]["checkpoint"],
            "nextTransition": state["development"]["nextTransition"],
        },
        "to": {
            "phase": candidate["development"]["phase"],
            "checkpoint": candidate["development"]["checkpoint"],
            "nextTransition": candidate["development"]["nextTransition"],
        },
        "applied": False,
    }
    if args.apply:
        active = state["git"].get("activeDevelopmentBranch")
        if active is None:
            raise RuntimeError("CHECKPOINT_NO_ACTIVE_DEVELOPMENT")
        git = observed_git()
        if not git.get("worktree"):
            raise RuntimeError("CHECKPOINT_NOT_A_WORKTREE")
        if git.get("branch") != active:
            raise RuntimeError(f"CHECKPOINT_WRONG_BRANCH:{git.get('branch')}")
        if git.get("dirty"):
            raise RuntimeError("CHECKPOINT_DIRTY_WORKTREE")
        atomic_write_json(STATE_PATH, candidate)
        readback = load_json(STATE_PATH)
        if readback != candidate:
            raise RuntimeError("STATE_READBACK_MISMATCH")
        change["applied"] = True
    if as_json:
        print(json.dumps(change, indent=2, ensure_ascii=False))
    else:
        mode = "APPLIED" if change["applied"] else "DRY-RUN"
        print(mode)
        print(f"  checkpoint: {change['from']['checkpoint']} -> {change['to']['checkpoint']}")
        print(f"  phase: {change['from']['phase']} -> {change['to']['phase']}")
        print(f"  next: {change['from']['nextTransition']} -> {change['to']['nextTransition']}")
    return 0


def recent_commits(control_branch: str) -> dict[str, Any]:
    ok, output = run_git("log", "--oneline", "--decorate=no", f"{control_branch}..HEAD", "-n", "20")
    if not ok:
        return {"available": False, "reason": output}
    return {"available": True, "entries": [line for line in output.splitlines() if line]}


def command_handoff(as_json: bool, include_remote: bool) -> int:
    state = load_json(STATE_PATH)
    observed = observed_git()
    verify = verify_state(include_remote=include_remote)
    payload = {
        "schemaVersion": "AgentHandoff 1.0",
        "projectState": state,
        "observedGit": observed,
        "verification": verify,
        "recentCommits": recent_commits(state["git"]["controlBranch"]) if observed.get("worktree") else {"available": False},
        "nextTransition": state["development"]["nextTransition"],
        "note": "Derived snapshot; not a new source of truth."
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        active = state["git"].get("activeDevelopmentBranch") or "(none)"
        print("HANDOFF")
        print(f"  initiative: {state['development']['initiative']}")
        print(f"  checkpoint: {state['development']['checkpoint']}")
        print(f"  branch: {active}")
        print(f"  verify: {verify['status']}")
        print(f"  next: {payload['nextTransition']}")
    return 0 if verify["status"] == "PASS" else ERROR_EXIT


def branch_refs() -> dict[str, str]:
    remote_ok, remote_output = run_git("for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/remotes/origin")
    refs: dict[str, str] = {}
    if remote_ok:
        for line in remote_output.splitlines():
            if not line.strip():
                continue
            name, sha = line.split("\t", 1)
            if name in {"origin/HEAD", "origin"} or not name.startswith("origin/"):
                continue
            refs[name.removeprefix("origin/")] = sha
    if refs:
        return refs

    local_ok, local_output = run_git("for-each-ref", "--format=%(refname:short)\t%(objectname)", "refs/heads")
    if not local_ok:
        raise RuntimeError(f"BRANCH_INVENTORY_FAILED:{local_output}")
    for line in local_output.splitlines():
        if not line.strip():
            continue
        name, sha = line.split("\t", 1)
        refs[name] = sha
    return refs


def observe_open_pr_heads(state: dict[str, Any]) -> tuple[bool, set[str], str | None]:
    if shutil.which("gh") is None:
        return False, set(), "GH_NOT_FOUND"
    repo = state["project"]["repository"]
    ok, payload = run_gh_json(f"repos/{repo}/pulls?state=open&per_page=100")
    if not ok or not isinstance(payload, list):
        return False, set(), "OPEN_PR_READ_FAILED"
    heads = {
        item.get("head", {}).get("ref")
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("head"), dict) and isinstance(item.get("head", {}).get("ref"), str)
    }
    return True, {head for head in heads if head}, None


def stable_plan_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_prune_plan(state: dict[str, Any], refs: dict[str, str], open_pr_heads: set[str] | None) -> dict[str, Any]:
    git_state = state["git"]
    protected = {git_state["controlBranch"], git_state["publishedBranch"]}
    active = git_state.get("activeDevelopmentBranch")
    if isinstance(active, str):
        protected.add(active)
    protected.update(git_state.get("preserveBranches") or [])
    if open_pr_heads is not None:
        protected.update(open_pr_heads)

    entries: list[dict[str, Any]] = []
    for branch, sha in sorted(refs.items()):
        if branch in protected:
            action, reason = "keep", "protected-or-open-pr"
        elif branch.startswith("archive/") or branch.startswith("backup/"):
            action, reason = "keep", "historical-or-rollback-anchor"
        elif branch.startswith("variant/"):
            action, reason = "archive-first", "legacy-variant-history"
        elif branch.startswith(("tmp/", "engine/", "deploy/", "agent/")):
            action, reason = "candidate", "ephemeral-or-slice-prefix"
        else:
            action, reason = "review", "no-safe-automatic-classification"
        entries.append({"branch": branch, "sha": sha, "action": action, "reason": reason})

    body = {
        "schemaVersion": "GitPrunePlan 0.1",
        "repository": state["project"]["repository"],
        "controlBranch": git_state["controlBranch"],
        "controlSha": refs.get(git_state["controlBranch"]),
        "branchCount": len(refs),
        "remoteOpenPrProtection": open_pr_heads is not None,
        "openPrHeads": sorted(open_pr_heads or []),
        "entries": entries,
        "applyEligible": open_pr_heads is not None,
        "note": "Legacy local planner retained for compatibility tests; the canonical command delegates to tools/prune_plan.py."
    }
    return {**body, "planHash": stable_plan_hash(body)}


def command_git_prune_plan(as_json: bool) -> int:
    return git_prune_plan.command(as_json)


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent", description="MobiliPresenter deterministic operational toolbox")
    parser.add_argument("command", choices=("status", "doctor", "verify", "checkpoint", "handoff", "git"))
    parser.add_argument("subcommand", nargs="?")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--remote", action="store_true", help="Observe PR/CI through gh when available")
    parser.add_argument("--to", dest="checkpoint")
    parser.add_argument("--next", dest="next_transition")
    parser.add_argument("--phase")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "status":
            return command_status(args.as_json, args.remote)
        if args.command == "doctor":
            return command_doctor(args.as_json)
        if args.command == "verify":
            return command_verify(args.as_json, args.remote)
        if args.command == "checkpoint":
            if not args.checkpoint or not args.next_transition:
                raise RuntimeError("CHECKPOINT_ARGS_REQUIRED: --to and --next")
            return command_checkpoint(args.as_json, args)
        if args.command == "git":
            if args.subcommand != "prune-plan":
                raise RuntimeError("GIT_SUBCOMMAND_REQUIRED: prune-plan")
            if args.apply:
                raise RuntimeError("UNSUPPORTED_TRANSITION: prune planning is read-only; destructive apply is a separately guarded operation")
            return command_git_prune_plan(args.as_json)
        if args.subcommand is not None:
            raise RuntimeError(f"UNEXPECTED_SUBCOMMAND:{args.subcommand}")
        return command_handoff(args.as_json, args.remote)
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

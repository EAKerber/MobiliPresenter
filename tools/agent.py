#!/usr/bin/env python3
"""Operational toolbox for MobiliPresenter agents.

Git Ops 1.1: read-only status/doctor/verify/handoff plus an explicit,
state-only checkpoint write. Uses the Python standard library and optional
`gh` CLI observation; it never performs push, merge, branch deletion or PR mutation.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"
ERROR_EXIT = 2
ALLOWED_COMMANDS = {"status", "doctor", "verify", "checkpoint", "handoff"}


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


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def run_process(args: list[str], *, cwd: Path = ROOT) -> tuple[bool, str]:
    try:
        proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout.strip()


def run_git(*args: str) -> tuple[bool, str]:
    if shutil.which("git") is None:
        return False, "git executable not found"
    return run_process(["git", *args])


def observed_git() -> dict[str, Any]:
    inside_ok, inside = run_git("rev-parse", "--is-inside-work-tree")
    if not inside_ok or inside != "true":
        return {"available": shutil.which("git") is not None, "worktree": False}
    branch_ok, branch = run_git("branch", "--show-current")
    if not branch:
        branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or None
    head_ok, head = run_git("rev-parse", "HEAD")
    remote_ok, remote = run_git("remote", "get-url", "origin")
    dirty_ok, porcelain = run_git("status", "--porcelain")
    return {
        "available": True,
        "worktree": True,
        "branch": branch if branch_ok or branch else None,
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
    if state["operations"].get("toolboxPhase") != "phase-1.1-coherence":
        errors.append({"code": "TOOLBOX_PHASE_MISMATCH", "detail": "toolboxPhase must be phase-1.1-coherence"})

    commands = state["operations"].get("commands")
    if not isinstance(commands, list) or set(commands) != ALLOWED_COMMANDS:
        errors.append({"code": "COMMAND_SET_MISMATCH", "detail": "operations.commands must list Git Ops 1.1 commands"})

    sha = state["published"].get("artifactSha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        errors.append({"code": "ARTIFACT_SHA_INVALID", "detail": "published.artifactSha256 must be lowercase sha256"})
    for key in ("controlBranch", "activeDevelopmentBranch", "publishedBranch"):
        if not isinstance(state["git"].get(key), str) or not state["git"][key]:
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"git.{key} must be a non-empty string"})
    for key in ("initiative", "phase", "checkpoint", "nextTransition", "plan"):
        if not isinstance(state["development"].get(key), str) or not state["development"][key]:
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"development.{key} must be a non-empty string"})
    if not isinstance(state["development"].get("prNumber"), int) or state["development"]["prNumber"] < 1:
        errors.append({"code": "STATE_SCHEMA_INVALID", "detail": "development.prNumber must be a positive integer"})
    return errors


def aggregate_ci(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "unknown"
    failed = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE"}
    pending = {None, "", "QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED"}
    saw_pending = False
    for check in checks:
        conclusion = check.get("conclusion")
        status = check.get("status")
        marker = str(conclusion or status or "").upper() or None
        if marker in failed:
            return "failed"
        if marker in pending:
            saw_pending = True
    return "pending" if saw_pending else "green"


def observe_remote(state: dict[str, Any]) -> dict[str, Any]:
    if shutil.which("gh") is None:
        return {"available": False, "status": "unknown", "reason": "GH_NOT_FOUND"}
    pr_number = state["development"].get("prNumber")
    repo = state["project"]["repository"]
    ok, output = run_process([
        "gh", "pr", "view", str(pr_number), "--repo", repo,
        "--json", "number,state,isDraft,headRefName,headRefOid,baseRefName,statusCheckRollup,url"
    ])
    if not ok:
        return {"available": False, "status": "unknown", "reason": "GH_PR_UNAVAILABLE", "detail": output}
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return {"available": False, "status": "unknown", "reason": "GH_JSON_INVALID"}
    checks = data.get("statusCheckRollup") if isinstance(data.get("statusCheckRollup"), list) else []
    return {
        "available": True,
        "status": aggregate_ci(checks),
        "pr": {
            "number": data.get("number"), "state": data.get("state"), "draft": data.get("isDraft"),
            "headBranch": data.get("headRefName"), "headSha": data.get("headRefOid"),
            "baseBranch": data.get("baseRefName"), "url": data.get("url")
        },
        "checks": checks,
    }


def git_context_check(state: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    if not observed.get("worktree"):
        return {"name": "git-branch-context", "status": "FAIL", "code": "NOT_A_GIT_WORKTREE"}
    branch = observed.get("branch")
    allowed = {state["git"]["activeDevelopmentBranch"], state["git"]["controlBranch"], state["git"]["publishedBranch"]}
    if branch not in allowed:
        return {"name": "git-branch-context", "status": "FAIL", "code": "UNEXPECTED_BRANCH", "observed": branch, "allowed": sorted(allowed)}
    context = "active" if branch == state["git"]["activeDevelopmentBranch"] else "control"
    return {"name": "git-branch-context", "status": "PASS", "code": None, "observed": branch, "context": context}


def verify_state(*, remote: bool = False) -> dict[str, Any]:
    state = load_json(STATE_PATH)
    checks: list[dict[str, Any]] = []
    errors = validate_state_shape(state)
    if errors:
        checks.extend({"name": "project-state", "status": "FAIL", **error} for error in errors)
    else:
        checks.append({"name": "project-state", "status": "PASS", "code": None})

    schema_exists = SCHEMA_PATH.is_file()
    checks.append({"name": "project-state-schema", "status": "PASS" if schema_exists else "FAIL", "code": None if schema_exists else "SCHEMA_FILE_MISSING"})

    plan = ROOT / state.get("development", {}).get("plan", "")
    checks.append({"name": "development-plan", "status": "PASS" if plan.is_file() else "FAIL", "code": None if plan.is_file() else "PLAN_FILE_MISSING"})

    manifest_rel = state.get("published", {}).get("artifactManifest") if isinstance(state.get("published"), dict) else None
    manifest_path = ROOT / manifest_rel if isinstance(manifest_rel, str) else None
    if manifest_path and manifest_path.is_file():
        manifest = load_json(manifest_path)
        match = manifest.get("release") == state["published"].get("release") and manifest.get("sha256") == state["published"].get("artifactSha256")
        checks.append({"name": "published-artifact-state", "status": "PASS" if match else "FAIL", "code": None if match else "STATE_DIVERGENCE"})
    else:
        checks.append({"name": "published-artifact-state", "status": "FAIL", "code": "MANIFEST_MISSING"})

    for rel in ("AGENTS.md", "README.md", "deploy.py"):
        exists = (ROOT / rel).is_file()
        checks.append({"name": f"required:{rel}", "status": "PASS" if exists else "FAIL", "code": None if exists else "REQUIRED_FILE_MISSING"})

    observed = observed_git()
    checks.append(git_context_check(state, observed))

    remote_payload: dict[str, Any] | None = None
    if remote:
        remote_payload = observe_remote(state)
        if not remote_payload.get("available"):
            checks.append({"name": "remote-pr", "status": "FAIL", "code": remote_payload.get("reason", "REMOTE_UNAVAILABLE")})
        else:
            pr = remote_payload["pr"]
            identity_ok = (
                pr.get("number") == state["development"].get("prNumber")
                and str(pr.get("state", "")).upper() == "OPEN"
                and pr.get("headBranch") == state["git"]["activeDevelopmentBranch"]
                and pr.get("baseBranch") == state["git"]["controlBranch"]
            )
            checks.append({"name": "remote-pr", "status": "PASS" if identity_ok else "FAIL", "code": None if identity_ok else "REMOTE_PR_DIVERGENCE"})
            if observed.get("branch") == state["git"]["activeDevelopmentBranch"] and observed.get("head"):
                head_ok = pr.get("headSha") == observed.get("head")
                checks.append({"name": "remote-head", "status": "PASS" if head_ok else "FAIL", "code": None if head_ok else "REMOTE_HEAD_DIVERGENCE"})
            checks.append({"name": "remote-ci", "status": "INFO", "code": remote_payload.get("status")})

    ok = all(check["status"] in {"PASS", "INFO"} for check in checks)
    payload: dict[str, Any] = {"ok": ok, "checks": checks, "observedGit": observed}
    if remote_payload is not None:
        payload["remote"] = remote_payload
    return payload


def command_status(as_json: bool, remote: bool) -> int:
    state = load_json(STATE_PATH)
    observed = observed_git()
    payload: dict[str, Any] = {
        "project": state["project"]["id"], "repository": state["project"]["repository"],
        "published": state["published"], "development": state["development"],
        "gitPolicy": state["git"], "observedGit": observed, "next": state["development"]["nextTransition"]
    }
    if remote:
        payload["remote"] = observe_remote(state)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"PROJECT\n  id: {payload['project']}\n  repository: {payload['repository']}")
        print(f"\nPUBLISHED\n  release: {payload['published']['release']}\n  branch: {payload['gitPolicy']['publishedBranch']}\n  url: {payload['published']['url']}")
        d = payload["development"]
        print(f"\nDEVELOPMENT\n  initiative: {d['initiative']}\n  phase: {d['phase']}\n  checkpoint: {d['checkpoint']}\n  branch: {payload['gitPolicy']['activeDevelopmentBranch']}\n  PR: #{d['prNumber']}\n  plan: {d['plan']}")
        print(f"\nBLOCKERS\n  {', '.join(d.get('blockers') or []) if d.get('blockers') else 'none'}")
        print(f"\nNEXT\n  {payload['next']}")
        if observed.get("worktree"):
            print(f"\nOBSERVED GIT\n  branch: {observed.get('branch')}\n  head: {observed.get('head')}\n  dirty: {observed.get('dirty')}")
        if remote and isinstance(payload.get("remote"), dict):
            r = payload["remote"]
            print(f"\nREMOTE\n  available: {r.get('available')}\n  ci: {r.get('status')}")
    return 0


def command_doctor(as_json: bool) -> int:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "python", "status": "PASS" if sys.version_info >= (3, 10) else "FAIL", "observed": sys.version.split()[0], "code": None if sys.version_info >= (3, 10) else "PYTHON_TOO_OLD"})
    checks.append({"name": "git-executable", "status": "PASS" if shutil.which("git") else "FAIL", "code": None if shutil.which("git") else "GIT_NOT_FOUND"})
    checks.append({"name": "github-cli", "status": "INFO", "observed": "available" if shutil.which("gh") else "unavailable", "code": None if shutil.which("gh") else "GH_OPTIONAL"})
    try:
        state = load_json(STATE_PATH)
        state_ok = not validate_state_shape(state)
        checks.append({"name": "project-state", "status": "PASS" if state_ok else "FAIL", "code": None if state_ok else "STATE_SCHEMA_INVALID"})
    except RuntimeError as exc:
        checks.append({"name": "project-state", "status": "FAIL", "code": str(exc).split(":", 1)[0]})
    git = observed_git()
    if git.get("worktree"):
        origin = git.get("origin") or ""
        origin_ok = "EAKerber/MobiliPresenter".lower() in origin.lower()
        checks.append({"name": "git-origin", "status": "PASS" if origin_ok else "FAIL", "observed": origin, "code": None if origin_ok else "WRONG_REPOSITORY"})
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


def checkpoint_candidate(state: dict[str, Any], *, checkpoint: str, next_transition: str, phase: str | None) -> dict[str, Any]:
    candidate = copy.deepcopy(state)
    candidate["development"]["checkpoint"] = checkpoint
    candidate["development"]["nextTransition"] = next_transition
    if phase:
        candidate["development"]["phase"] = phase
    return candidate


def command_checkpoint(as_json: bool, *, checkpoint: str, next_transition: str, phase: str | None, apply: bool) -> int:
    state = load_json(STATE_PATH)
    candidate = checkpoint_candidate(state, checkpoint=checkpoint, next_transition=next_transition, phase=phase)
    errors = validate_state_shape(candidate)
    if errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID: {errors[0]['detail']}")
    payload: dict[str, Any] = {
        "apply": apply, "from": state["development"], "to": candidate["development"], "path": str(STATE_PATH.relative_to(ROOT))
    }
    if apply:
        observed = observed_git()
        if not observed.get("worktree"):
            raise RuntimeError("CHECKPOINT_NO_WORKTREE")
        if observed.get("branch") != state["git"]["activeDevelopmentBranch"]:
            raise RuntimeError("CHECKPOINT_WRONG_BRANCH")
        if observed.get("dirty"):
            raise RuntimeError("CHECKPOINT_DIRTY_WORKTREE")
        atomic_write_json(STATE_PATH, candidate)
        readback = load_json(STATE_PATH)
        if readback != candidate:
            raise RuntimeError("CHECKPOINT_READBACK_MISMATCH")
        payload["readback"] = "PASS"
        payload["nextRequired"] = "commit/publish the state change using the repository Git protocol and perform independent readback"
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        mode = "APPLY" if apply else "DRY-RUN"
        print(f"{mode} {payload['path']}")
        print(f"  checkpoint: {state['development']['checkpoint']} -> {candidate['development']['checkpoint']}")
        print(f"  phase: {state['development']['phase']} -> {candidate['development']['phase']}")
        print(f"  next: {state['development']['nextTransition']} -> {candidate['development']['nextTransition']}")
        if apply:
            print("  readback: PASS")
    return 0


def command_handoff(as_json: bool, remote: bool) -> int:
    state = load_json(STATE_PATH)
    observed = observed_git()
    verify = verify_state(remote=remote)
    control = state["git"]["controlBranch"]
    diff_ok, diff = run_git("diff", "--name-status", f"{control}...HEAD") if observed.get("worktree") else (False, "")
    log_ok, log = run_git("log", "--oneline", "--no-decorate", "-20", f"{control}..HEAD") if observed.get("worktree") else (False, "")
    payload: dict[str, Any] = {
        "project": state["project"], "published": state["published"], "development": state["development"],
        "gitPolicy": state["git"], "observedGit": observed, "verify": verify,
        "changesSinceControl": diff.splitlines() if diff_ok and diff else [],
        "commitsSinceControl": log.splitlines() if log_ok and log else [],
    }
    if remote:
        payload["remote"] = verify.get("remote")
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"# Handoff — {state['project']['id']}")
        print(f"\n- initiative: {state['development']['initiative']}")
        print(f"- checkpoint: {state['development']['checkpoint']}")
        print(f"- next: {state['development']['nextTransition']}")
        print(f"- branch: {state['git']['activeDevelopmentBranch']}")
        print(f"- verify: {'PASS' if verify['ok'] else 'BLOCKED'}")
        print("\n## Changes since control")
        print("\n".join(payload["changesSinceControl"][:50]) or "none/unknown")
        print("\n## Recent commits")
        print("\n".join(payload["commitsSinceControl"][:20]) or "none/unknown")
    return 0 if verify["ok"] else ERROR_EXIT


def command_verify(as_json: bool, remote: bool) -> int:
    payload = verify_state(remote=remote)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in payload["checks"]:
            code = f" [{check.get('code')}]" if check.get("code") else ""
            print(f"{check['status']:4} {check['name']}{code}")
        print("\nPASS" if payload["ok"] else "\nBLOCKED")
    return 0 if payload["ok"] else ERROR_EXIT


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent", description="MobiliPresenter operational toolbox")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "doctor", "verify", "handoff"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true", dest="as_json")
        if name in {"status", "verify", "handoff"}:
            p.add_argument("--remote", action="store_true")

    cp = sub.add_parser("checkpoint")
    cp.add_argument("--to", required=True, dest="checkpoint")
    cp.add_argument("--next", required=True, dest="next_transition")
    cp.add_argument("--phase")
    cp.add_argument("--apply", action="store_true")
    cp.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args()
    try:
        if args.command == "status":
            return command_status(args.as_json, args.remote)
        if args.command == "doctor":
            return command_doctor(args.as_json)
        if args.command == "verify":
            return command_verify(args.as_json, args.remote)
        if args.command == "handoff":
            return command_handoff(args.as_json, args.remote)
        return command_checkpoint(args.as_json, checkpoint=args.checkpoint, next_transition=args.next_transition, phase=args.phase, apply=args.apply)
    except RuntimeError as exc:
        if getattr(args, "as_json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only operational toolbox for MobiliPresenter agents.

Phase 0/1 bootstrap: status, doctor and verify.
Uses only the Python standard library and never mutates the repository.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
SCHEMA_PATH = ROOT / "ops" / "schemas" / "project-state.schema.json"

ERROR_EXIT = 2


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


def run_git(*args: str) -> tuple[bool, str]:
    if shutil.which("git") is None:
        return False, "git executable not found"
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout.strip()


def observed_git() -> dict[str, Any]:
    inside_ok, inside = run_git("rev-parse", "--is-inside-work-tree")
    if not inside_ok or inside != "true":
        return {"available": shutil.which("git") is not None, "worktree": False}
    branch_ok, branch = run_git("branch", "--show-current")
    head_ok, head = run_git("rev-parse", "HEAD")
    remote_ok, remote = run_git("remote", "get-url", "origin")
    dirty_ok, porcelain = run_git("status", "--porcelain")
    return {
        "available": True,
        "worktree": True,
        "branch": branch if branch_ok else None,
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
    for key in ("controlBranch", "activeDevelopmentBranch", "publishedBranch"):
        if not isinstance(state["git"].get(key), str) or not state["git"][key]:
            errors.append({"code": "STATE_SCHEMA_INVALID", "detail": f"git.{key} must be a non-empty string"})
    return errors


def verify_state() -> dict[str, Any]:
    state = load_json(STATE_PATH)
    checks: list[dict[str, Any]] = []
    errors = validate_state_shape(state)
    if errors:
        for error in errors:
            checks.append({"name": "project-state", "status": "FAIL", **error})
    else:
        checks.append({"name": "project-state", "status": "PASS", "code": None})

    schema_exists = SCHEMA_PATH.is_file()
    checks.append({"name": "project-state-schema", "status": "PASS" if schema_exists else "FAIL",
                   "code": None if schema_exists else "SCHEMA_FILE_MISSING"})

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

    ok = all(check["status"] == "PASS" for check in checks)
    return {"ok": ok, "checks": checks}


def command_status(as_json: bool) -> int:
    state = load_json(STATE_PATH)
    observed = observed_git()
    payload = {
        "project": state["project"]["id"],
        "repository": state["project"]["repository"],
        "published": state["published"],
        "development": state["development"],
        "gitPolicy": state["git"],
        "observedGit": observed,
        "next": state["development"]["nextTransition"],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"PROJECT\n  id: {payload['project']}\n  repository: {payload['repository']}")
        print(f"\nPUBLISHED\n  release: {payload['published']['release']}\n  branch: {payload['gitPolicy']['publishedBranch']}\n  url: {payload['published']['url']}")
        print(f"\nDEVELOPMENT\n  initiative: {payload['development']['initiative']}\n  phase: {payload['development']['phase']}\n  checkpoint: {payload['development']['checkpoint']}\n  branch: {payload['gitPolicy']['activeDevelopmentBranch']}")
        blockers = payload['development'].get('blockers') or []
        print(f"\nBLOCKERS\n  {', '.join(blockers) if blockers else 'none'}")
        print(f"\nNEXT\n  {payload['next']}")
        if observed.get("worktree"):
            print(f"\nOBSERVED GIT\n  branch: {observed.get('branch')}\n  head: {observed.get('head')}\n  dirty: {observed.get('dirty')}")
    return 0


def command_doctor(as_json: bool) -> int:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "python", "status": "PASS" if sys.version_info >= (3, 10) else "FAIL",
                   "observed": sys.version.split()[0], "code": None if sys.version_info >= (3, 10) else "PYTHON_TOO_OLD"})
    checks.append({"name": "git-executable", "status": "PASS" if shutil.which("git") else "FAIL",
                   "code": None if shutil.which("git") else "GIT_NOT_FOUND"})
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

    ok = all(c["status"] == "PASS" for c in checks)
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


def command_verify(as_json: bool) -> int:
    payload = verify_state()
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in payload["checks"]:
            code = f" [{check.get('code')}]" if check.get("code") else ""
            print(f"{check['status']:4} {check['name']}{code}")
        print("\nPASS" if payload["ok"] else "\nBLOCKED")
    return 0 if payload["ok"] else ERROR_EXIT


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent", description="MobiliPresenter read-only operational toolbox")
    parser.add_argument("command", choices=("status", "doctor", "verify"))
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        if args.command == "status":
            return command_status(args.as_json)
        if args.command == "doctor":
            return command_doctor(args.as_json)
        return command_verify(args.as_json)
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

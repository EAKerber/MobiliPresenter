#!/usr/bin/env python3
"""Formal rollback probe for experimental Coordination Leases.

Proves two independent rollback properties:
1. leases created by the probe can be fully released without touching foreign sessions;
2. canonical GitOps commands still work when experimental coordination modules are absent.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUTPUT = Path(os.environ.get("COORDINATION_ROLLBACK_PROBE_OUTPUT", "/tmp/coordination-rollback-probe.json"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_json(args: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"COMMAND_FAILED:{' '.join(args)}:{proc.returncode}:"
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"COMMAND_NON_JSON:{' '.join(args)}:{proc.stdout!r}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"COMMAND_JSON_ROOT_INVALID:{' '.join(args)}")
    return payload


def canonical_without_coordination() -> dict[str, Any]:
    moved: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix="mobilipresenter-coordination-disabled-") as tmp:
        disabled = Path(tmp)
        candidates = sorted(TOOLS.glob("coordination*.py")) + [TOOLS / "lock.py"]
        pycache = TOOLS / "__pycache__"
        try:
            for source in candidates:
                if not source.exists():
                    continue
                target = disabled / source.name
                shutil.move(str(source), str(target))
                moved.append((source, target))
            if pycache.exists():
                target = disabled / "__pycache__"
                shutil.move(str(pycache), str(target))
                moved.append((pycache, target))

            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            doctor = run_json([sys.executable, "tools/agent.py", "doctor", "--json"], env=env)
            verify = run_json([sys.executable, "tools/agent.py", "verify", "--json"], env=env)
            if not doctor.get("ok") or not verify.get("ok"):
                raise RuntimeError("CANONICAL_PATH_FAILED_WITH_COORDINATION_DISABLED")
            return {
                "ok": True,
                "disabled": [source.relative_to(ROOT).as_posix() for source, _ in moved],
                "doctor": doctor,
                "verify": verify,
            }
        finally:
            for source, target in reversed(moved):
                if target.exists():
                    shutil.move(str(target), str(source))


def main() -> int:
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "ops/git-ops-1.3-coordination-leases"
    pr = os.environ.get("PR_NUMBER", "32")
    session = f"rollback-probe-{run_id}-{attempt}"
    resource = f"file:ops/evidence/rollback-probe-{run_id}-{attempt}.synthetic"

    stable_paths = [ROOT / "AGENTS.md", ROOT / "ops" / "state" / "project.json"]
    before_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in stable_paths}

    common = [
        "--role", "gitops",
        "--session", session,
        "--branch", branch,
        "--pr", pr,
        "--json",
    ]

    acquire = None
    guard = None
    release = None
    status = None
    try:
        acquire = run_json([
            sys.executable, "tools/lock.py", "acquire", resource,
            "--reason", "formal rollback probe",
            "--ttl", "120",
            "--transition-id", f"rollback-acquire-{run_id}-{attempt}",
            *common,
        ])
        guard = run_json([
            sys.executable, "tools/lock.py", "guard", resource,
            *common,
        ])
    finally:
        if acquire is not None:
            release = run_json([
                sys.executable, "tools/lock.py", "release", "--mine",
                "--transition-id", f"rollback-release-{run_id}-{attempt}",
                *common,
            ])

    status = run_json([sys.executable, "tools/lock.py", "status", "--json"])
    own_leases = [
        lease for lease in status.get("leases", [])
        if isinstance(lease, dict)
        and isinstance(lease.get("owner"), dict)
        and lease["owner"].get("session") == session
    ]
    if own_leases:
        raise RuntimeError("ROLLBACK_LEFT_OWN_LEASES")

    canonical = canonical_without_coordination()
    after_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in stable_paths}
    if before_hashes != after_hashes:
        raise RuntimeError("ROLLBACK_MUTATED_CANONICAL_STATE")

    git_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if git_status.returncode != 0:
        raise RuntimeError(f"ROLLBACK_GIT_STATUS_FAILED:{git_status.stderr.strip()}")
    if git_status.stdout.strip():
        raise RuntimeError(f"ROLLBACK_LEFT_DIRTY_WORKTREE:{git_status.stdout.strip()}")

    payload = {
        "schemaVersion": "CoordinationRollbackEvidence 0.1",
        "ok": True,
        "session": session,
        "resource": resource,
        "acquire": acquire,
        "guard": guard,
        "release": release,
        "postReleaseAuthorityHead": status.get("authorityHead"),
        "ownLeasesRemaining": 0,
        "canonicalStateHashesBefore": before_hashes,
        "canonicalStateHashesAfter": after_hashes,
        "canonicalWithoutCoordination": canonical,
        "worktreeCleanAfterRollback": True,
        "rollbackProven": True,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

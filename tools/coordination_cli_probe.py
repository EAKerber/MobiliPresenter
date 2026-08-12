#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority  # noqa: E402


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"ENV_REQUIRED:{name}")
    return value


def _run_lock(args: list[str], env: dict[str, str]) -> dict:
    proc = subprocess.run(
        [sys.executable, "tools/lock.py", *args, "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LOCK_CLI_NON_JSON:{proc.returncode}:{proc.stdout}:{proc.stderr}") from exc
    if proc.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(f"LOCK_CLI_FAILED:{proc.returncode}:{payload}:{proc.stderr}")
    return payload


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    session = f"gha-cli-restart:{run_id}:{attempt}"
    branch = "engine/cli-restart-probe"
    pr_number = "940001"
    resource = f"file:ops/coordination/probes/cli-restart-{run_id}-{attempt}.shared"
    env = os.environ.copy()
    env.update(
        {
            "MOBILIPRESENTER_AGENT_ROLE": "engine",
            "MOBILIPRESENTER_AGENT_SESSION": session,
            "MOBILIPRESENTER_AGENT_BRANCH": branch,
            "MOBILIPRESENTER_PR_NUMBER": pr_number,
        }
    )

    acquired = renewed = guarded = released = None
    try:
        acquired = _run_lock(
            [
                "acquire",
                resource,
                "--reason",
                "live CLI restart/session recovery probe",
                "--ttl",
                "120",
                "--transition-id",
                f"cli-acquire:{run_id}:{attempt}",
            ],
            env,
        )

        # Each call is a new Python process. Reusing only the explicit session id
        # proves that ownership can be recovered after process/chat restart.
        renewed = _run_lock(
            [
                "renew",
                "--mine",
                "--transition-id",
                f"cli-renew:{run_id}:{attempt}",
            ],
            env,
        )
        guarded = _run_lock(["guard", resource], env)
        released = _run_lock(
            [
                "release",
                "--mine",
                "--transition-id",
                f"cli-release:{run_id}:{attempt}",
            ],
            env,
        )
    finally:
        authority = GitHubCoordinationAuthority(GhApiTransport())
        observed = authority.observe()
        mine = [
            lease
            for lease in coordination.active_leases(observed.state, observed.authority_now)
            if lease["owner"]["session"] == session
        ]
        if mine:
            cleanup = subprocess.run(
                [
                    sys.executable,
                    "tools/lock.py",
                    "release",
                    "--mine",
                    "--transition-id",
                    f"cli-finally:{run_id}:{attempt}",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            if cleanup.returncode != 0:
                raise RuntimeError(f"LOCK_CLI_CLEANUP_FAILED:{cleanup.stdout}:{cleanup.stderr}")

    if any(item is None for item in (acquired, renewed, guarded, released)):
        raise RuntimeError("LOCK_CLI_RESTART_PROBE_INCOMPLETE")
    authority = GitHubCoordinationAuthority(GhApiTransport())
    final = authority.observe()
    if any(
        lease["owner"]["session"] == session
        for lease in coordination.active_leases(final.state, final.authority_now)
    ):
        raise RuntimeError("LOCK_CLI_RESTART_PROBE_LEASE_LEFT_ACTIVE")

    evidence = {
        "schemaVersion": "CoordinationCliRestartProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "owner": {
            "role": "engine",
            "session": session,
            "branch": branch,
            "pr": int(pr_number),
        },
        "resource": resource,
        "acquireHead": acquired["afterSha"],
        "renewHead": renewed["afterSha"],
        "guardAuthorityHead": guarded["authorityHead"],
        "releaseHead": released["afterSha"],
        "separateProcesses": True,
        "sameSessionRecovered": True,
        "ownerGuardPassedAfterRestart": True,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_CLI_PROBE_OUTPUT", "/tmp/coordination-cli-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

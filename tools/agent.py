#!/usr/bin/env python3
"""Stable public facade for MobiliPresenter agent operations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_commands as _commands
from tools.canonical import stable_hash

ERROR_EXIT = 2
TOOLBOX_COMMANDS = {
    "begin", "close", "status", "doctor", "verify", "checkpoint", "handoff",
    "git prune-plan", "git mutation-plan",
}


def __getattr__(name):
    """Lazily preserve the established toolbox/helper surface.

    project_sensors imports tools.agent while agent_commands is still being
    initialized. Avoid reading the implementation package during that cycle;
    later attribute access resolves against the completed implementation.
    """
    try:
        return getattr(_commands, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def _state_and_publication():
    return _commands._state_and_publication()


def project_summary(view):
    return _commands.project_summary(view)


def observed_git():
    return _commands.observed_git()


def verify_state():
    return _commands.verify_state()


def recent_commits(control_branch):
    return _commands.recent_commits(control_branch)


def command_status(as_json):
    state, view, published = _state_and_publication()
    payload = {
        "project": project_summary(view),
        "projectStateHash": stable_hash(state),
        "published": published,
        "observedGit": observed_git(),
        "next": view["development"]["nextTransition"],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            f"PROJECT\n"
            f"  id: {payload['project']['id']}\n"
            f"  repository: {payload['project']['repository']}\n"
            f"  phase: {payload['project']['phase']}\n"
            f"  checkpoint: {payload['project']['checkpoint']}\n\n"
            f"NEXT\n  {payload['next']}"
        )
    return 0


def command_handoff(as_json):
    state, view, published = _state_and_publication()
    observed = observed_git()
    verify = verify_state()
    project = project_summary(view)
    payload = {
        "schemaVersion": "AgentHandoff 2.1",
        "projectStateHash": stable_hash(state),
        "project": project,
        "publication": published,
        "observedGit": observed,
        "verification": verify,
        "recentCommits": (
            recent_commits(project["controlBranch"])
            if observed.get("worktree")
            else {"available": False}
        ),
        "nextTransition": project["nextTransition"],
        "note": "Derived snapshot; not a new source of truth.",
    }
    print(
        json.dumps(payload, indent=2, ensure_ascii=False)
        if as_json
        else f"HANDOFF\n  verify: {verify['status']}\n  next: {payload['nextTransition']}"
    )
    return 0 if verify["status"] == "PASS" else ERROR_EXIT


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "close":
        from tools import agent_cycle_close
        return agent_cycle_close.main(sys.argv[2:])
    return _commands.main()


if __name__ == "__main__":
    raise SystemExit(main())

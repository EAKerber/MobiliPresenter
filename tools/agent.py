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
from tools import agent_cycle_close

# Re-export the established toolbox surface. The command implementation moved as
# one blob so the public facade can grow without duplicating operational logic.
for _name in dir(_commands):
    if _name not in {"main"}:
        globals()[_name] = getattr(_commands, _name)

TOOLBOX_COMMANDS = set(_commands.TOOLBOX_COMMANDS) | {"close"}


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
        return agent_cycle_close.main(sys.argv[2:])
    return _commands.main()


if __name__ == "__main__":
    raise SystemExit(main())

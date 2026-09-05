#!/usr/bin/env python3
"""Stable public facade for MobiliPresenter agent operations."""
from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_commands as _commands
from tools import runtime_capabilities, runtime_provider_adapter
from tools.agent_tools import policy as agent_tool_policy
from tools.canonical import stable_hash

ERROR_EXIT = 2
TOOLBOX_COMMANDS = {
    "begin", "close", "status", "doctor", "verify", "checkpoint", "handoff",
    "git prune-plan", "git mutation-plan",
}
_RUNTIME_TOOL_SURFACE = "--runtime-tool-surface"
_RUNTIME_TOOL_SURFACES_COMPLETE = "--runtime-tool-surfaces-complete"


def __getattr__(name):
    """Lazily preserve the established toolbox/helper surface.

    project_sensors imports tools.agent while agent_commands is still being
    initialized. Avoid reading the implementation package during that cycle;
    later attribute access resolves against the completed implementation.
    """
    if name == "agent_cycle_close":
        return importlib.import_module("tools.agent_cycle_close")
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


def _bootstrap_projection() -> dict:
    policy = agent_tool_policy.load_policy()
    entry_profiles = {
        role: sorted(entries)
        for role, entries in policy["entryProfiles"].items()
    }
    return {
        "nextSafeAction": "BEGIN_AGENT_CYCLE",
        "commandTemplate": (
            "python3 tools/agent.py begin --role <role> --intent <intent> --json"
        ),
        "roleContractPattern": "docs/kickstarts/roles/<role>.md",
        "entryProfiles": entry_profiles,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _status_payload(state, view, published, observed) -> dict:
    return {
        "project": project_summary(view),
        "projectStateHash": stable_hash(state),
        "published": published,
        "observedGit": observed,
        "roadmapNextTransition": view["development"]["nextTransition"],
        "bootstrap": _bootstrap_projection(),
    }


def command_status(as_json):
    state, view, published = _state_and_publication()
    payload = _status_payload(state, view, published, observed_git())
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        roles = ", ".join(payload["bootstrap"]["entryProfiles"])
        print(
            f"PROJECT\n"
            f"  id: {payload['project']['id']}\n"
            f"  repository: {payload['project']['repository']}\n"
            f"  phase: {payload['project']['phase']}\n"
            f"  checkpoint: {payload['project']['checkpoint']}\n\n"
            f"ROADMAP NEXT\n  {payload['roadmapNextTransition']}\n\n"
            f"NEXT SAFE ACTION\n"
            f"  {payload['bootstrap']['nextSafeAction']}\n"
            f"  {payload['bootstrap']['commandTemplate']}\n"
            f"  roles: {roles}"
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


def _argument_value(argv: list[str], name: str) -> str | None:
    value = None
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == name:
            if index + 1 >= len(argv):
                raise RuntimeError(f"ARGUMENT_VALUE_REQUIRED:{name}")
            value = argv[index + 1]
            index += 2
            continue
        prefix = f"{name}="
        if token.startswith(prefix):
            value = token[len(prefix):]
        index += 1
    return value


def _extract_runtime_tool_surfaces(
    argv: list[str],
) -> tuple[list[str], list[str], bool, bool]:
    clean = [argv[0]] if argv else []
    surfaces: list[str] = []
    inventory_complete = False
    observed = False
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == _RUNTIME_TOOL_SURFACE:
            observed = True
            if index + 1 >= len(argv):
                raise RuntimeError("RUNTIME_TOOL_SURFACE_ID_REQUIRED")
            surfaces.append(argv[index + 1])
            index += 2
            continue
        prefix = f"{_RUNTIME_TOOL_SURFACE}="
        if token.startswith(prefix):
            observed = True
            surfaces.append(token[len(prefix):])
            index += 1
            continue
        if token == _RUNTIME_TOOL_SURFACES_COMPLETE:
            observed = True
            inventory_complete = True
            index += 1
            continue
        clean.append(token)
        index += 1
    return clean, surfaces, inventory_complete, observed


def _runtime_surface_base(
    argv: list[str],
    surfaces: list[str],
    *,
    inventory_complete: bool,
) -> dict:
    command = argv[1] if len(argv) > 1 else None
    if command not in {"begin", "doctor"}:
        raise RuntimeError("RUNTIME_TOOL_SURFACES_REQUIRE_BEGIN_OR_DOCTOR")
    derived = runtime_provider_adapter.observations_from_tool_surfaces(
        surfaces,
        inventory_complete=inventory_complete,
    )
    local = runtime_capabilities.local_provider_observations()
    claimed = set(local["providers"])
    runtime_providers = _argument_value(argv, "--runtime-providers")
    if runtime_providers:
        explicit = runtime_capabilities.load_provider_observations(Path(runtime_providers))
        claimed.update(explicit["providers"])
    overlap = sorted(claimed & set(derived["providers"]))
    if overlap:
        raise RuntimeError(
            f"RUNTIME_PROVIDER_OBSERVATION_SOURCE_CONFLICT:{overlap[0]}"
        )
    return runtime_capabilities.merge_provider_observations(local, derived)


def _run_with_runtime_tool_surfaces(argv: list[str]) -> int:
    clean, surfaces, inventory_complete, observed = _extract_runtime_tool_surfaces(argv)
    if not observed:
        if (
            len(clean) >= 2
            and clean[1] == "status"
            and all(token == "--json" for token in clean[2:])
        ):
            return command_status("--json" in clean)
        return _commands.main()
    base = _runtime_surface_base(
        clean,
        surfaces,
        inventory_complete=inventory_complete,
    )
    original_argv = sys.argv
    original_local_observations = runtime_capabilities.local_provider_observations
    try:
        sys.argv = clean
        runtime_capabilities.local_provider_observations = lambda: copy.deepcopy(base)
        return _commands.main()
    finally:
        runtime_capabilities.local_provider_observations = original_local_observations
        sys.argv = original_argv


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "close":
        return __getattr__("agent_cycle_close").main(sys.argv[2:])
    try:
        return _run_with_runtime_tool_surfaces(list(sys.argv))
    except RuntimeError as exc:
        as_json = "--json" in sys.argv
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            if as_json
            else f"BLOCKED\n{exc}",
            file=sys.stdout if as_json else sys.stderr,
        )
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

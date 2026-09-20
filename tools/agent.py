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
    "enter", "begin", "continue", "close", "close-review", "reflection-eligibility", "operational-quiescence", "status", "doctor", "verify", "checkpoint", "handoff",
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
        return importlib.import_module("tools.agent_cycle_close_recovery")
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


def _reentry_success(work_id: str, inspection: dict) -> dict:
    return {
        "status": "PASS",
        "workRef": {"workId": work_id},
        "reentryDisposition": inspection["state"],
        "nextSafeAction": inspection["nextSafeAction"],
        "reasonCodes": copy.deepcopy(inspection["reasonCodes"]),
        "targetCycle": copy.deepcopy(inspection.get("targetCycle")),
        "inspection": copy.deepcopy(inspection),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _reentry_unknown(work_id: str, error) -> dict:
    return {
        "status": "UNKNOWN",
        "workRef": {"workId": work_id},
        "reentryDisposition": "INSUFFICIENT_OBSERVATION",
        "nextSafeAction": "OBSERVE",
        "reasonCodes": [error.code],
        "targetCycle": None,
        "inspection": None,
        "detail": error.detail or None,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _bootstrap_projection(reentry: dict | None = None) -> dict:
    policy = agent_tool_policy.load_policy()
    entry_profiles = {
        role: sorted(entries)
        for role, entries in policy["entryProfiles"].items()
    }
    projection = {
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
    if reentry is None:
        return projection
    action = reentry["nextSafeAction"]
    projection.update({
        "nextSafeAction": action,
        "commandTemplate": (
            f"python3 tools/agent.py enter --work-id {reentry['workRef']['workId']} "
            "--role <role> --intent <intent> --runtime-tool-surface <surface> "
            "--runtime-tool-surfaces-complete --apply --json"
            if action == "BEGIN_NEW_CYCLE"
            else None
        ),
        "reentryDisposition": reentry["reentryDisposition"],
        "workRef": copy.deepcopy(reentry["workRef"]),
        "reasonCodes": copy.deepcopy(reentry["reasonCodes"]),
        "targetCycle": copy.deepcopy(reentry["targetCycle"]),
    })
    return projection


def _journey_projection(
    view: dict,
    published: dict,
    observed: dict,
    bootstrap: dict,
    reentry: dict | None = None,
) -> dict:
    """Derive a journey view without creating lifecycle authority."""
    next_safe_action = bootstrap["nextSafeAction"]
    stage = "ENTRY"
    if reentry is not None:
        stage = "QUIESCENT" if next_safe_action == "NONE" else "REENTRY"
        if next_safe_action == "BEGIN_NEW_CYCLE":
            stage = "ENTRY"

    blockers: list[str] = []
    if reentry is not None and (
        reentry["status"] == "UNKNOWN"
        or reentry["reentryDisposition"]
        in {
            "LEGITIMATE_WAIT",
            "PRIORITY_OPERATION_REQUIRED",
            "INSUFFICIENT_OBSERVATION",
        }
    ):
        blockers = copy.deepcopy(reentry["reasonCodes"])

    project = project_summary(view)
    git_facts = {
        key: copy.deepcopy(observed.get(key))
        for key in ("available", "worktree", "branch", "head", "dirty")
    }
    reentry_facts = None
    completed = [
        "OBSERVE_PROJECT_STATE",
        "OBSERVE_PUBLICATION",
        "OBSERVE_GIT",
    ]
    if reentry is not None:
        completed.append("OBSERVE_REENTRY")
        reentry_facts = {
            "status": reentry["status"],
            "workRef": copy.deepcopy(reentry["workRef"]),
            "disposition": reentry["reentryDisposition"],
            "reasonCodes": copy.deepcopy(reentry["reasonCodes"]),
        }

    return {
        "schemaVersion": "JourneyProjection 0.1",
        "stage": stage,
        "observedFacts": {
            "project": {
                "phase": project["phase"],
                "checkpoint": project["checkpoint"],
                "roadmapNextTransition": view["development"]["nextTransition"],
            },
            "publication": {"release": published.get("release")},
            "git": git_facts,
            "reentry": reentry_facts,
        },
        "completedResponsibilities": completed,
        "ownershipDisposition": "NOT_OBSERVED",
        "authoringDisposition": "NOT_OBSERVED",
        "candidateDisposition": "NOT_OBSERVED",
        "ciDisposition": "NOT_OBSERVED",
        "deliveryDisposition": "NOT_OBSERVED",
        "nextSafeAction": next_safe_action,
        "automaticTransitions": [],
        "semanticDecisionRequired": False,
        "blockers": blockers,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _status_payload(state, view, published, observed, reentry: dict | None = None) -> dict:
    next_transition = view["development"]["nextTransition"]
    bootstrap = _bootstrap_projection(reentry)
    payload = {
        "project": project_summary(view),
        "projectStateHash": stable_hash(state),
        "published": published,
        "observedGit": observed,
        "next": next_transition,
        "roadmapNextTransition": next_transition,
        "bootstrap": bootstrap,
        "journeyProjection": _journey_projection(
            view, published, observed, bootstrap, reentry
        ),
    }
    if reentry is not None:
        payload["reentry"] = copy.deepcopy(reentry)
    return payload


def command_status(as_json, work_id: str | None = None):
    state, view, published = _state_and_publication()
    reentry = None
    if work_id is not None:
        reentry_module = importlib.import_module("tools.agent_reentry_guidance")
        from tools.coordination_remote import GhApiTransport

        try:
            inspection = reentry_module.observe_live(
                work_id,
                transport=GhApiTransport(),
            )
            reentry = _reentry_success(work_id, inspection)
        except reentry_module.AgentReentryGuidanceError as exc:
            reentry = _reentry_unknown(work_id, exc)
    payload = _status_payload(state, view, published, observed_git(), reentry)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        roles = ", ".join(payload["bootstrap"]["entryProfiles"])
        lines = [
            "PROJECT",
            f"  id: {payload['project']['id']}",
            f"  repository: {payload['project']['repository']}",
            f"  phase: {payload['project']['phase']}",
            f"  checkpoint: {payload['project']['checkpoint']}",
            "",
            "ROADMAP NEXT",
            f"  {payload['roadmapNextTransition']}",
        ]
        if reentry is not None:
            reasons = ", ".join(reentry["reasonCodes"]) or "-"
            lines.extend([
                "",
                "RE-ENTRY",
                f"  work: {reentry['workRef']['workId']}",
                f"  observation: {reentry['status']}",
                f"  disposition: {reentry['reentryDisposition']}",
                f"  reasons: {reasons}",
            ])
        lines.extend([
            "",
            "JOURNEY",
            f"  stage: {payload['journeyProjection']['stage']}",
            f"  ownership: {payload['journeyProjection']['ownershipDisposition']}",
            f"  authoring: {payload['journeyProjection']['authoringDisposition']}",
            f"  candidate: {payload['journeyProjection']['candidateDisposition']}",
            f"  ci: {payload['journeyProjection']['ciDisposition']}",
            f"  delivery: {payload['journeyProjection']['deliveryDisposition']}",
            "",
            "NEXT SAFE ACTION",
            f"  {payload['bootstrap']['nextSafeAction']}",
        ])
        if payload["bootstrap"]["commandTemplate"] is not None:
            lines.append(f"  {payload['bootstrap']['commandTemplate']}")
        lines.append(f"  roles: {roles}")
        print("\n".join(lines))
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


def _status_arguments(argv: list[str]) -> tuple[bool, str | None]:
    as_json = False
    work_id = None
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--json":
            as_json = True
            index += 1
            continue
        if token == "--work-id":
            if index + 1 >= len(argv):
                raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--work-id")
            work_id = argv[index + 1]
            index += 2
            continue
        if token.startswith("--work-id="):
            work_id = token.split("=", 1)[1]
            index += 1
            continue
        raise RuntimeError(f"UNEXPECTED_STATUS_ARGUMENT:{token}")
    if work_id == "":
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--work-id")
    return as_json, work_id


def _enter_arguments(argv: list[str]) -> tuple[bool, str, str, str, bool]:
    as_json = False
    work_id = None
    role = None
    declared_intent = None
    apply = False
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--json":
            as_json = True
            index += 1
            continue
        if token == "--apply":
            apply = True
            index += 1
            continue
        if token in {"--work-id", "--role", "--intent"}:
            if index + 1 >= len(argv):
                raise RuntimeError(f"ARGUMENT_VALUE_REQUIRED:{token}")
            value = argv[index + 1]
            if token == "--work-id":
                work_id = value
            elif token == "--role":
                role = value
            else:
                declared_intent = value
            index += 2
            continue
        for name in ("--work-id", "--role", "--intent"):
            prefix = f"{name}="
            if token.startswith(prefix):
                value = token[len(prefix):]
                if name == "--work-id":
                    work_id = value
                elif name == "--role":
                    role = value
                else:
                    declared_intent = value
                break
        else:
            raise RuntimeError(f"UNEXPECTED_ENTER_ARGUMENT:{token}")
        index += 1
    if not isinstance(work_id, str) or not work_id:
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--work-id")
    if not isinstance(role, str) or not role:
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--role")
    if not isinstance(declared_intent, str) or not declared_intent:
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--intent")
    return as_json, work_id, role, declared_intent, apply


def command_enter(
    argv: list[str],
    *,
    tool_surfaces: list[str],
    inventory_complete: bool,
) -> int:
    as_json, work_id, role, declared_intent, apply = _enter_arguments(argv)
    journey_entry = importlib.import_module("tools.agent_tools.journey_entry")
    from tools.coordination_remote import GhApiTransport

    payload = journey_entry.compose_entry(
        role=role,
        declared_intent=declared_intent,
        work_id=work_id,
        tool_surfaces=sorted(set(tool_surfaces)),
        inventory_complete=inventory_complete,
        submit=apply,
        transport=GhApiTransport(),
    )
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "AGENT ENTER\n"
            f"  work: {work_id}\n"
            f"  status: {payload['status']}\n"
            f"  disposition: {payload['disposition']}\n"
            f"  submitted: {str(payload['submitted']).lower()}"
        )
        if payload.get("blockers"):
            print(f"  blockers: {', '.join(payload['blockers'])}")
    return ERROR_EXIT if payload["status"] in {"BLOCKED", "UNKNOWN"} else 0


def _continue_arguments(argv: list[str]) -> tuple[bool, str, str | None, bool]:
    as_json = False
    work_id = None
    target_intent = None
    apply = False
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--json":
            as_json = True
            index += 1
            continue
        if token == "--apply":
            apply = True
            index += 1
            continue
        if token in {"--work-id", "--intent"}:
            if index + 1 >= len(argv):
                raise RuntimeError(f"ARGUMENT_VALUE_REQUIRED:{token}")
            value = argv[index + 1]
            if token == "--work-id":
                work_id = value
            else:
                target_intent = value
            index += 2
            continue
        if token.startswith("--work-id="):
            work_id = token.split("=", 1)[1]
            index += 1
            continue
        if token.startswith("--intent="):
            target_intent = token.split("=", 1)[1]
            index += 1
            continue
        raise RuntimeError(f"UNEXPECTED_CONTINUE_ARGUMENT:{token}")
    if not isinstance(work_id, str) or not work_id:
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--work-id")
    if target_intent == "":
        raise RuntimeError("ARGUMENT_VALUE_REQUIRED:--intent")
    return as_json, work_id, target_intent, apply


def command_continue(
    argv: list[str],
    *,
    provider_observations: dict,
    tool_surfaces: list[str],
    inventory_complete: bool,
) -> int:
    as_json, work_id, target_intent, apply = _continue_arguments(argv)
    turnover_host = importlib.import_module("tools.agent_cycle_turnover_host")
    from tools.coordination_remote import GhApiTransport

    machine = _commands._machine_for_begin("live", None)
    runtime = runtime_capabilities.build_inspection(provider_observations)
    payload = turnover_host.continue_work(
        work_id=work_id,
        machine=machine,
        runtime_inspection=runtime,
        tool_surfaces=sorted(set(tool_surfaces)),
        inventory_complete=inventory_complete,
        target_intent=target_intent,
        submit=apply,
        transport=GhApiTransport(),
    )
    projection = payload["projection"]
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "AGENT CONTINUE\n"
            f"  work: {work_id}\n"
            f"  action: {projection['action']}\n"
            f"  target-intent: {projection['targetIntent'] or '-'}\n"
            f"  submitted: {str(payload['submitted']).lower()}"
        )
        if projection["reasonCodes"]:
            print(f"  reasons: {', '.join(projection['reasonCodes'])}")
    return ERROR_EXIT if projection["action"] == "BLOCKED" else 0


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
    if command not in {"enter", "begin", "continue", "doctor"}:
        raise RuntimeError("RUNTIME_TOOL_SURFACES_REQUIRE_ENTER_BEGIN_CONTINUE_OR_DOCTOR")
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
        if len(clean) >= 2 and clean[1] == "status":
            as_json, work_id = _status_arguments(clean)
            return command_status(as_json, work_id=work_id)
        if len(clean) >= 2 and clean[1] == "enter":
            raise RuntimeError("RUNTIME_TOOL_SURFACES_REQUIRED_FOR_ENTER")
        if len(clean) >= 2 and clean[1] == "continue":
            raise RuntimeError("RUNTIME_TOOL_SURFACES_REQUIRED_FOR_CONTINUE")
        return _commands.main()
    base = _runtime_surface_base(
        clean,
        surfaces,
        inventory_complete=inventory_complete,
    )
    if len(clean) >= 2 and clean[1] == "enter":
        return command_enter(
            clean,
            tool_surfaces=surfaces,
            inventory_complete=inventory_complete,
        )
    if len(clean) >= 2 and clean[1] == "continue":
        return command_continue(
            clean,
            provider_observations=base,
            tool_surfaces=surfaces,
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
    if len(sys.argv) >= 2 and sys.argv[1] == "close-review":
        return importlib.import_module("tools.agent_cycle_close_review").run(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "reflection-eligibility":
        return importlib.import_module("tools.reflection_eligibility").run(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "operational-quiescence":
        return importlib.import_module("tools.operational_quiescence").run(sys.argv[2:])
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

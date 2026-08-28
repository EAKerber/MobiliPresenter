from __future__ import annotations

from typing import Any

from tools import agent_cycle_resources, hosted_handle_requests, remote_canonical_execution
from tools.agent_tools import mutation_dispatch, trace_collect

CURRENT_REPOSITORY = "EAKerber/MobiliPresenter"


class AgentCycleResourceCollectionError(RuntimeError):
    pass


def _begin(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": manifest["source"]["runId"],
        "sourceSha": manifest["source"]["sourceSha"],
        "contextHash": manifest["contextHash"],
    }


def _resources_from_remote_receipt(payload: dict[str, Any]) -> list[dict[str, Any]]:
    remote_canonical_execution.validate_receipt(payload)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return []
    kind = evidence.get("kind")
    if kind == "transition-receipt":
        plan = evidence.get("plan")
        return agent_cycle_resources.resources_from_transition_plan(plan)
    if kind == "git-mutation-plan-readback":
        plan = evidence.get("plan")
        return agent_cycle_resources.resources_from_git_plan(plan)
    return []


def build_resource_set(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
    repository: str = CURRENT_REPOSITORY,
) -> dict[str, Any]:
    if repository != CURRENT_REPOSITORY:
        raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_REPOSITORY_INVALID")
    try:
        cycle_instance_id = trace_collect.cycle_instance_id(manifest)
        window = trace_collect._window(
            comments,
            manifest["source"]["commentId"],
            close_comment_id,
        )
    except RuntimeError as exc:
        raise AgentCycleResourceCollectionError(str(exc).split(":", 1)[0]) from exc

    expected_begin = _begin(manifest)
    expected_actor = manifest["actor"]
    resources: list[dict[str, Any]] = []

    # Agent Tool mutation dispatches are the strongest pre-apply declarations
    # already bound to the exact cycle instance.
    for comment in window:
        if not trace_collect._result_comment_allowed(comment):
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), trace_collect.AGENT_TOOL_DISPATCH_MARKER
        )
        if not isinstance(payload, dict):
            continue
        try:
            mutation_dispatch.validate_dispatch(payload)
        except RuntimeError as exc:
            raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_DISPATCH_INVALID") from exc
        if (
            payload.get("cycleInstanceId") != cycle_instance_id
            or trace_collect._canonical_begin(payload.get("begin")) != expected_begin
            or trace_collect._canonical_actor(payload.get("actor")) != expected_actor
        ):
            continue
        resources.extend(agent_cycle_resources.resources_from_agent_tool_dispatch(payload))

    # Direct Remote Canonical requests belong to the same trace window. They do
    # not carry a cycle id, so use the exact actor + bounded cycle window just as
    # AgentCycleExecutionTrace 0.1 already does.
    for comment in window:
        if not trace_collect._request_comment_allowed(comment):
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), trace_collect.REMOTE_REQUEST_MARKER
        )
        if not isinstance(payload, dict):
            continue
        try:
            remote_canonical_execution.validate_command(payload)
        except RuntimeError as exc:
            raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_REMOTE_COMMAND_INVALID") from exc
        if trace_collect._canonical_actor(payload.get("actor")) != expected_actor:
            continue
        resources.extend(agent_cycle_resources.resources_from_remote_command(payload))

    # Verified receipts may add stronger plan provenance and concrete identities
    # such as a PR number when the underlying plan exposes one.
    for comment in window:
        if not trace_collect._result_comment_allowed(comment):
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), trace_collect.REMOTE_RESULT_MARKER
        )
        if not isinstance(payload, dict):
            continue
        try:
            remote_canonical_execution.validate_receipt(payload)
        except RuntimeError as exc:
            raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_REMOTE_RECEIPT_INVALID") from exc
        command = payload.get("command")
        if not isinstance(command, dict) or trace_collect._canonical_actor(command.get("actor")) != expected_actor:
            continue
        resources.extend(_resources_from_remote_receipt(payload))

    # Lease requests provide the prospective scope before a leaseId exists;
    # results add the concrete Coordination lease identity afterwards.
    from tools import agent_write_lifecycle as lifecycle

    for comment in window:
        body = comment.get("body") if isinstance(comment, dict) else None
        if trace_collect._request_comment_allowed(comment):
            payload = trace_collect._json_after_marker(body, lifecycle.REQUEST_MARKER)
            request: dict[str, Any] | None = None
            if isinstance(payload, dict):
                try:
                    lifecycle.validate_request(payload)
                except RuntimeError as exc:
                    raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_LEASE_REQUEST_INVALID") from exc
                if (
                    trace_collect._canonical_begin(payload.get("begin")) == expected_begin
                    and trace_collect._canonical_actor(payload.get("actor")) == expected_actor
                ):
                    request = payload
            else:
                outer = trace_collect._json_after_marker(
                    body, hosted_handle_requests.WRITE_LEASE_MARKER_V02
                )
                if isinstance(outer, dict):
                    try:
                        hosted_handle_requests.validate_write_lease(
                            outer, repository=CURRENT_REPOSITORY
                        )
                    except RuntimeError as exc:
                        raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_LEASE_REQUEST_INVALID") from exc
                    if hosted_handle_requests.matches_manifest(
                        outer.get("handle"), manifest, repository=CURRENT_REPOSITORY
                    ):
                        request = hosted_handle_requests.build_write_lease_inner(
                            outer,
                            begin=expected_begin,
                            actor=expected_actor,
                        )
                        lifecycle.validate_request(request)
            if request is not None:
                resources.extend(agent_cycle_resources.resources_from_write_lease_request(request))

        if trace_collect._result_comment_allowed(comment):
            payload = trace_collect._json_after_marker(body, lifecycle.RESULT_MARKER)
            if not isinstance(payload, dict):
                continue
            try:
                lifecycle.validate_result(payload)
            except RuntimeError as exc:
                raise AgentCycleResourceCollectionError("AGENT_CYCLE_RESOURCE_LEASE_RESULT_INVALID") from exc
            if (
                payload.get("cycleInstanceId") != cycle_instance_id
                or trace_collect._canonical_begin(payload.get("begin")) != expected_begin
                or trace_collect._canonical_actor(payload.get("actor")) != expected_actor
            ):
                continue
            resources.extend(agent_cycle_resources.resources_from_write_lease_result(payload))

    try:
        return agent_cycle_resources.build_resource_set(
            repository=repository,
            cycle_instance_id=cycle_instance_id,
            resources=resources,
        )
    except RuntimeError as exc:
        raise AgentCycleResourceCollectionError(str(exc).split(":", 1)[0]) from exc

from __future__ import annotations

from typing import Any

from tools import (
    agent_cycle,
    agent_cycle_obligations,
    agent_cycle_resources,
    hosted_cycle_records,
    remote_canonical_execution,
)

CURRENT_REPOSITORY = hosted_cycle_records.CURRENT_REPOSITORY


class AgentCycleResourceCollectionError(RuntimeError):
    pass


def _resources_from_remote_receipt(payload: dict[str, Any]) -> list[dict[str, Any]]:
    remote_canonical_execution.validate_receipt(payload)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return []
    kind = evidence.get("kind")
    if kind == "transition-receipt":
        return agent_cycle_resources.resources_from_transition_plan(evidence.get("plan"))
    if kind == "git-mutation-plan-readback":
        return agent_cycle_resources.resources_from_git_plan(evidence.get("plan"))
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
        view = hosted_cycle_records.collect(
            comments, manifest, close_comment_id=close_comment_id
        )
    except hosted_cycle_records.HostedCycleRecordError as exc:
        raise AgentCycleResourceCollectionError(exc.code) from exc

    resources: list[dict[str, Any]] = []

    # R3B1 promotes only records with strong cycle-instance binding. Ambient
    # direct RemoteCanonical records remain observable in hosted_cycle_records
    # but cannot become semantic resources or obligations.
    for item in hosted_cycle_records.records_of(
        view, "agent-tool-dispatch", binding=hosted_cycle_records.STRONG
    ):
        resources.extend(
            agent_cycle_resources.resources_from_agent_tool_dispatch(item["normalized"])
        )

    for item in hosted_cycle_records.records_of(
        view, "remote-result", binding=hosted_cycle_records.STRONG
    ):
        try:
            resources.extend(_resources_from_remote_receipt(item["payload"]))
        except RuntimeError as exc:
            raise AgentCycleResourceCollectionError(
                "AGENT_CYCLE_RESOURCE_REMOTE_RECEIPT_INVALID"
            ) from exc

    for item in hosted_cycle_records.records_of(
        view, "write-lease-request", binding=hosted_cycle_records.STRONG
    ):
        resources.extend(
            agent_cycle_resources.resources_from_write_lease_request(item["normalized"])
        )

    for item in hosted_cycle_records.records_of(
        view, "write-lease-result", binding=hosted_cycle_records.STRONG
    ):
        resources.extend(
            agent_cycle_resources.resources_from_write_lease_result(item["normalized"])
        )

    try:
        return agent_cycle_resources.build_resource_set(
            repository=repository,
            cycle_instance_id=view["cycleInstanceId"],
            resources=resources,
        )
    except RuntimeError as exc:
        raise AgentCycleResourceCollectionError(str(exc).split(":", 1)[0]) from exc


def build_obligation_inventory(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    close_comment_id: int,
    repository: str = CURRENT_REPOSITORY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        agent_cycle.validate_context(context)
    except RuntimeError as exc:
        raise AgentCycleResourceCollectionError(
            "AGENT_CYCLE_OBLIGATION_CONTEXT_INVALID"
        ) from exc
    resource_set = build_resource_set(
        comments,
        manifest,
        close_comment_id=close_comment_id,
        repository=repository,
    )
    work_ref = context.get("workRef") if context.get("schemaVersion") == agent_cycle.SCHEMA_VERSION else None
    try:
        inventory = agent_cycle_obligations.build_inventory(
            resource_set,
            work_ref=work_ref,
        )
    except RuntimeError as exc:
        raise AgentCycleResourceCollectionError(str(exc).split(":", 1)[0]) from exc
    return resource_set, inventory

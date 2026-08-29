from __future__ import annotations

import copy
from typing import Any

from tools import (
    agent_cycle_obligations as obligations,
    agent_write_lifecycle_guard,
    continuation,
    git_observation,
    work_graph,
)
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority
from tools.coordination_remote import GhApiTransport

WORK_UNAVAILABLE = "AGENT_CYCLE_DISPOSITION_WORK_AUTHORITY_UNAVAILABLE"
GIT_UNAVAILABLE = "AGENT_CYCLE_DISPOSITION_GIT_REF_UNAVAILABLE"
LIFECYCLE_REPORT_UNAVAILABLE = "AGENT_CYCLE_DISPOSITION_LIFECYCLE_REPORT_UNAVAILABLE"
LIFECYCLE_SCOPE_AMBIGUOUS = "AGENT_CYCLE_DISPOSITION_LIFECYCLE_SCOPE_AMBIGUOUS"
LIFECYCLE_STATE_UNKNOWN = "AGENT_CYCLE_DISPOSITION_LIFECYCLE_STATE_UNKNOWN"


class AgentCycleObligationInspectError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _work_snapshot(
    inventory: dict[str, Any], carrier: Any
) -> tuple[str | None, dict[str, dict[str, Any]] | None, list[dict[str, Any]] | None]:
    needs_work = any(
        item["kind"] in {"work-disposition", "git-branch-disposition"}
        for item in inventory["obligations"]
    )
    if not needs_work:
        return None, {}, []
    try:
        observed = GitHubContinuationAuthority(transport=carrier).observe()
        views = [
            continuation.operational_view(value)
            for _, value in sorted(observed.items.items())
        ]
        bindings = work_graph.active_execution_bindings(views)
        return observed.head_sha, observed.items, bindings
    except (ContinuationRemoteError, RuntimeError):
        return None, None, None


def _work_disposition(
    obligation: dict[str, Any],
    *,
    authority_head: str | None,
    items: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if authority_head is None or items is None:
        return obligations.disposition(
            obligation,
            observation_status="UNKNOWN",
            reason_codes=[WORK_UNAVAILABLE],
            domain_state={"authorityHead": None, "exists": None, "status": None},
        )
    work_id = obligation["locator"]["workId"]
    item = items.get(work_id)
    return obligations.disposition(
        obligation,
        observation_status="PASS",
        reason_codes=[],
        domain_state={
            "authorityHead": authority_head,
            "exists": item is not None,
            "status": item["status"] if item is not None else None,
        },
    )


def _git_disposition(
    obligation: dict[str, Any],
    *,
    carrier: Any,
    work_authority_head: str | None,
    active_bindings: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    branch = obligation["locator"]["branch"]
    reasons: list[str] = []
    exists: bool | None
    head_sha: str | None
    try:
        head_sha = git_observation.ref_head(carrier, branch, missing_ok=True)
        exists = head_sha is not None
    except git_observation.GitObservationError:
        exists = None
        head_sha = None
        reasons.append(GIT_UNAVAILABLE)

    branch_bindings: list[dict[str, Any]] | None
    if work_authority_head is None or active_bindings is None:
        branch_bindings = None
        reasons.append(WORK_UNAVAILABLE)
    else:
        branch_bindings = sorted(
            (
                copy.deepcopy(item)
                for item in active_bindings
                if item.get("branch") == branch
            ),
            key=lambda item: item["workId"],
        )

    return obligations.disposition(
        obligation,
        observation_status="PASS" if not reasons else "UNKNOWN",
        reason_codes=sorted(set(reasons)),
        domain_state={
            "exists": exists,
            "headSha": head_sha,
            "workAuthorityHead": work_authority_head,
            "activeWorkBindings": branch_bindings,
        },
    )


def _lifecycle_dispositions(
    lifecycle_obligations: list[dict[str, Any]],
    *,
    lifecycle_report: dict[str, Any] | None,
    cycle_instance_id: str,
) -> list[dict[str, Any]]:
    if not lifecycle_obligations:
        return []
    report: dict[str, Any] | None = None
    if lifecycle_report is not None:
        try:
            report = agent_write_lifecycle_guard.validate_report(lifecycle_report)
        except RuntimeError:
            report = None
    if report is not None and report.get("cycleInstanceId") != cycle_instance_id:
        report = None

    if report is None:
        return [
            obligations.disposition(
                item,
                observation_status="UNKNOWN",
                reason_codes=[LIFECYCLE_REPORT_UNAVAILABLE],
                domain_state={"state": None, "reportHash": None},
            )
            for item in lifecycle_obligations
        ]

    report_state = report["state"]
    report_hash = report["reportHash"]
    if len(lifecycle_obligations) != 1:
        return [
            obligations.disposition(
                item,
                observation_status="UNKNOWN",
                reason_codes=[LIFECYCLE_SCOPE_AMBIGUOUS],
                domain_state={"state": report_state, "reportHash": report_hash},
            )
            for item in lifecycle_obligations
        ]

    item = lifecycle_obligations[0]
    actor = report.get("actor") or {}
    locator = item["locator"]
    if actor.get("role") != locator["role"] or actor.get("sessionId") != locator["sessionId"]:
        return [
            obligations.disposition(
                item,
                observation_status="UNKNOWN",
                reason_codes=[LIFECYCLE_REPORT_UNAVAILABLE],
                domain_state={"state": report_state, "reportHash": report_hash},
            )
        ]
    reasons = [LIFECYCLE_STATE_UNKNOWN] if report_state == "UNKNOWN" else []
    return [
        obligations.disposition(
            item,
            observation_status="UNKNOWN" if reasons else "PASS",
            reason_codes=reasons,
            domain_state={"state": report_state, "reportHash": report_hash},
        )
    ]


def inspect_inventory(
    inventory: dict[str, Any],
    *,
    lifecycle_report: dict[str, Any] | None = None,
    transport: Any | None = None,
) -> dict[str, Any]:
    inventory = obligations.validate_inventory(inventory)
    carrier = transport or GhApiTransport()
    work_head, work_items, active_bindings = _work_snapshot(inventory, carrier)

    dispositions: list[dict[str, Any]] = []
    lifecycle: list[dict[str, Any]] = []
    for item in inventory["obligations"]:
        kind = item["kind"]
        if kind == "work-disposition":
            dispositions.append(
                _work_disposition(
                    item,
                    authority_head=work_head,
                    items=work_items,
                )
            )
        elif kind == "git-branch-disposition":
            dispositions.append(
                _git_disposition(
                    item,
                    carrier=carrier,
                    work_authority_head=work_head,
                    active_bindings=active_bindings,
                )
            )
        elif kind == "write-lifecycle-disposition":
            lifecycle.append(item)
        else:
            raise AgentCycleObligationInspectError(
                "AGENT_CYCLE_DISPOSITION_OBLIGATION_KIND_UNSUPPORTED"
            )
    dispositions.extend(
        _lifecycle_dispositions(
            lifecycle,
            lifecycle_report=lifecycle_report,
            cycle_instance_id=inventory["cycleInstanceId"],
        )
    )
    return obligations.build_disposition_set(inventory, dispositions)

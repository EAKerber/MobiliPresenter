"""Deterministic read-only frontier projection for Work-bound Hosted cycles.

The lineage remains the inventory of materialized begins. This module interprets
strongly-bound cycle outcomes into terminal history versus the active frontier.
It never selects by wall-clock recency and never authorizes mutation.
"""
from __future__ import annotations

import copy
from typing import Any

from tools import hosted_agent_cycle
from tools.canonical import stable_hash

SCHEMA = "HostedCycleFrontier 0.1"
STATES = {"NONE", "SINGLE", "CONCURRENT", "SUCCESSION_UNPROVEN"}
TERMINAL_STATES = {"PASS"}
FIELDS = {
    "schemaVersion",
    "terminalCycleIds",
    "activeCycleIds",
    "state",
    "successionEvidence",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "frontierHash",
}
EVIDENCE_FIELDS = {
    "terminalCycleInstanceId",
    "terminalResultCommentId",
    "activeCycleInstanceId",
    "activeBeginCommentId",
    "ordered",
}


class HostedCycleFrontierError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _cycle_id(value: Any) -> str:
    if not isinstance(value, str) or hosted_agent_cycle.CYCLE_INSTANCE_RE.fullmatch(value) is None:
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_CYCLE_ID_INVALID")
    return value


def _comment_id(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_COMMENT_ID_INVALID")
    return value


def _outcome_map(outcomes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_OUTCOME_INVALID")
        cycle_id = _cycle_id(outcome.get("cycleInstanceId"))
        if cycle_id in mapped:
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_OUTCOME_DUPLICATE")
        if not isinstance(outcome.get("state"), str):
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_OUTCOME_INVALID")
        mapped[cycle_id] = outcome
    return mapped


def _candidate_map(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_CANDIDATE_INVALID")
        cycle_id = _cycle_id(candidate.get("cycleInstanceId"))
        begin_id = _comment_id(candidate.get("requestCommentId"))
        if cycle_id in mapped:
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_CANDIDATE_DUPLICATE")
        mapped[cycle_id] = {**candidate, "requestCommentId": begin_id}
    return mapped


def build_frontier(
    candidates: list[dict[str, Any]], outcomes: list[dict[str, Any]]
) -> dict[str, Any]:
    candidate_by_id = _candidate_map(candidates)
    outcome_by_id = _outcome_map(outcomes)
    if set(candidate_by_id) != set(outcome_by_id):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_BINDING_MISMATCH")

    terminal_ids = sorted(
        cycle_id
        for cycle_id, outcome in outcome_by_id.items()
        if outcome["state"] in TERMINAL_STATES
    )
    active_ids = sorted(set(outcome_by_id) - set(terminal_ids))

    evidence: list[dict[str, Any]] = []
    succession_proven = True
    if len(active_ids) == 1 and terminal_ids:
        active_id = active_ids[0]
        active_begin = candidate_by_id[active_id]["requestCommentId"]
        for terminal_id in terminal_ids:
            result_ids = outcome_by_id[terminal_id].get("resultCommentIds")
            if not isinstance(result_ids, list) or not result_ids:
                raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_TERMINAL_EVIDENCE_INVALID")
            terminal_result = max(_comment_id(item) for item in result_ids)
            ordered = terminal_result < active_begin
            evidence.append(
                {
                    "terminalCycleInstanceId": terminal_id,
                    "terminalResultCommentId": terminal_result,
                    "activeCycleInstanceId": active_id,
                    "activeBeginCommentId": active_begin,
                    "ordered": ordered,
                }
            )
            succession_proven = succession_proven and ordered

    if len(active_ids) > 1:
        state = "CONCURRENT"
    elif len(active_ids) == 1 and terminal_ids and not succession_proven:
        state = "SUCCESSION_UNPROVEN"
    elif len(active_ids) == 1:
        state = "SINGLE"
    else:
        state = "NONE"

    core = {
        "schemaVersion": SCHEMA,
        "terminalCycleIds": terminal_ids,
        "activeCycleIds": active_ids,
        "state": state,
        "successionEvidence": evidence,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return validate_frontier({**core, "frontierHash": stable_hash(core)})


def validate_frontier(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != SCHEMA
        or value.get("state") not in STATES
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_BOUNDARY_INVALID")

    terminal = value.get("terminalCycleIds")
    active = value.get("activeCycleIds")
    if not isinstance(terminal, list) or not isinstance(active, list):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_IDS_INVALID")
    for items in (terminal, active):
        if items != sorted(set(items)):
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_IDS_INVALID")
        for item in items:
            _cycle_id(item)
    if set(terminal) & set(active):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_IDS_OVERLAP")

    evidence = value.get("successionEvidence")
    if not isinstance(evidence, list):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_INVALID")
    normalized_evidence: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_INVALID")
        terminal_id = _cycle_id(item.get("terminalCycleInstanceId"))
        active_id = _cycle_id(item.get("activeCycleInstanceId"))
        terminal_result = _comment_id(item.get("terminalResultCommentId"))
        active_begin = _comment_id(item.get("activeBeginCommentId"))
        ordered = item.get("ordered")
        if not isinstance(ordered, bool) or ordered != (terminal_result < active_begin):
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_ORDER_INVALID")
        if terminal_id not in terminal or active_id not in active:
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_BINDING_INVALID")
        normalized_evidence.append(copy.deepcopy(item))
    if evidence != sorted(
        normalized_evidence,
        key=lambda item: (item["terminalCycleInstanceId"], item["activeCycleInstanceId"]),
    ):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_ORDER_INVALID")

    if len(active) > 1:
        expected_state = "CONCURRENT"
    elif len(active) == 1 and terminal and any(not item["ordered"] for item in evidence):
        expected_state = "SUCCESSION_UNPROVEN"
    elif len(active) == 1:
        expected_state = "SINGLE"
    else:
        expected_state = "NONE"
    if value["state"] != expected_state:
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_STATE_INVALID")
    if len(active) == 1 and terminal:
        pairs = {(item["terminalCycleInstanceId"], item["activeCycleInstanceId"]) for item in evidence}
        expected_pairs = {(terminal_id, active[0]) for terminal_id in terminal}
        if pairs != expected_pairs:
            raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_INCOMPLETE")
    elif evidence:
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_EVIDENCE_NOT_APPLICABLE")

    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "frontierHash"}
    if value.get("frontierHash") != stable_hash(core):
        raise HostedCycleFrontierError("HOSTED_CYCLE_FRONTIER_HASH_MISMATCH")
    return value

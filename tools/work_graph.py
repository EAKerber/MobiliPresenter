from __future__ import annotations

from collections import defaultdict
from typing import Any

from tools.semantics.work import WorkStatus

SCHEMA_VERSION = "WorkGraph 0.1"


def _id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("WORK_GRAPH_ID_INVALID")
    return value


def _active(item: dict[str, Any]) -> bool:
    return WorkStatus.parse(str(item.get("status") or "")).terminal is False


def validate_items(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    active_branches: dict[str, str] = {}
    active_prs: dict[int, str] = {}
    for raw in items:
        if not isinstance(raw, dict):
            raise RuntimeError("WORK_GRAPH_ITEM_INVALID")
        work_id = _id(raw.get("id"))
        if work_id in by_id:
            raise RuntimeError("WORK_GRAPH_DUPLICATE_ID")
        depends_on = raw.get("dependsOn")
        if not isinstance(depends_on, list) or any(not isinstance(dep, str) or not dep for dep in depends_on):
            raise RuntimeError("WORK_GRAPH_DEPENDENCIES_INVALID")
        if len(depends_on) != len(set(depends_on)):
            raise RuntimeError("WORK_GRAPH_DEPENDENCY_DUPLICATE")
        if work_id in depends_on:
            raise RuntimeError("WORK_GRAPH_SELF_DEPENDENCY")
        WorkStatus.parse(str(raw.get("status") or ""))
        branch = raw.get("branch")
        pr = raw.get("prNumber")
        if _active(raw):
            if isinstance(branch, str) and branch:
                if branch in active_branches:
                    raise RuntimeError("WORK_GRAPH_ACTIVE_BRANCH_CONFLICT")
                active_branches[branch] = work_id
            if isinstance(pr, int) and not isinstance(pr, bool):
                if pr in active_prs:
                    raise RuntimeError("WORK_GRAPH_ACTIVE_PR_CONFLICT")
                active_prs[pr] = work_id
        by_id[work_id] = raw
    for work_id, item in by_id.items():
        for dependency in item["dependsOn"]:
            if dependency not in by_id:
                raise RuntimeError(f"WORK_GRAPH_DEPENDENCY_MISSING:{work_id}:{dependency}")
    return by_id


def _ensure_acyclic(by_id: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(work_id: str) -> None:
        if work_id in visited:
            return
        if work_id in visiting:
            raise RuntimeError("WORK_GRAPH_CYCLE")
        visiting.add(work_id)
        for dependency in by_id[work_id]["dependsOn"]:
            visit(dependency)
        visiting.remove(work_id)
        visited.add(work_id)

    for work_id in sorted(by_id):
        visit(work_id)


def active_execution_bindings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive execution identity only from non-terminal WorkItems."""
    by_id = validate_items(items)
    _ensure_acyclic(by_id)
    bindings: list[dict[str, Any]] = []
    for work_id in sorted(by_id):
        item = by_id[work_id]
        status = WorkStatus.parse(str(item.get("status") or ""))
        if status.terminal:
            continue
        branch = item.get("branch")
        pr_number = item.get("prNumber")
        bindings.append({
            "workId": work_id,
            "workerId": item.get("workerId"),
            "status": status.value,
            "branch": branch if isinstance(branch, str) and branch else None,
            "prNumber": pr_number if isinstance(pr_number, int) and not isinstance(pr_number, bool) else None,
        })
    return bindings


def build(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = validate_items(items)
    _ensure_acyclic(by_id)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    runnable: list[str] = []
    handoff_required: list[str] = []
    dependency_blocked: list[str] = []
    terminal: list[str] = []
    for work_id in sorted(by_id):
        item = by_id[work_id]
        status = WorkStatus.parse(item["status"])
        dependencies = list(item["dependsOn"])
        deps_done = all(WorkStatus.parse(by_id[dep]["status"]).terminal for dep in dependencies)
        is_terminal = status.terminal
        is_handoff = status is WorkStatus.HANDOFF
        is_dependency_blocked = status in {WorkStatus.READY, WorkStatus.IN_PROGRESS} and not deps_done
        is_runnable = status in {WorkStatus.READY, WorkStatus.IN_PROGRESS} and deps_done
        if is_terminal:
            terminal.append(work_id)
        if is_handoff:
            handoff_required.append(work_id)
        if is_dependency_blocked:
            dependency_blocked.append(work_id)
        if is_runnable:
            runnable.append(work_id)
        nodes.append({
            "id": work_id,
            "status": status.value,
            "terminal": is_terminal,
            "dependencyBlocked": is_dependency_blocked,
            "runnable": is_runnable,
            "handoffRequired": is_handoff,
        })
        edges.extend({"from": work_id, "to": dep, "kind": "dependsOn"} for dep in sorted(dependencies))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "runnable": runnable,
        "handoffRequired": handoff_required,
        "dependencyBlocked": dependency_blocked,
        "terminal": terminal,
    }


def validate(graph: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, dict) or graph.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("WORK_GRAPH_SCHEMA_UNSUPPORTED")
    expected = {"schemaVersion", "nodes", "edges", "runnable", "handoffRequired", "dependencyBlocked", "terminal"}
    if set(graph) != expected:
        raise RuntimeError("WORK_GRAPH_FIELDS_INVALID")
    if not all(isinstance(graph.get(name), list) for name in expected - {"schemaVersion"}):
        raise RuntimeError("WORK_GRAPH_COLLECTION_INVALID")
    return graph


def require_dependencies_done(item: dict[str, Any], inventory: list[dict[str, Any]] | None) -> None:
    dependencies = item.get("dependsOn") or []
    if not dependencies:
        return
    if inventory is None:
        raise RuntimeError("WORK_GRAPH_INVENTORY_REQUIRED")
    by_id = validate_items(inventory)
    _ensure_acyclic(by_id)
    work_id = _id(item.get("id"))
    current = by_id.get(work_id)
    if current is None:
        raise RuntimeError("WORK_GRAPH_ITEM_MISSING")
    if any(not WorkStatus.parse(by_id[dep]["status"]).terminal for dep in current["dependsOn"]):
        raise RuntimeError("WORK_GRAPH_DEPENDENCY_NOT_DONE")

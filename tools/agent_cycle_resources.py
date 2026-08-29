from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from tools.canonical import stable_hash

SCHEMA_VERSION = "AgentCycleTouchedResourceSet 0.2"
REPOSITORY = "EAKerber/MobiliPresenter"
CYCLE_RE = re.compile(r"^cycle-instance-[0-9a-f]{24}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
RESOURCE_KINDS = {
    "git-branch",
    "git-path",
    "domain-subject",
    "lease-scope",
    "coordination-lease",
}
ORIGIN_FIELDS = {"sourceKind", "sourceHash", "operation"}
RESOURCE_FIELDS = {"kind", "locator", "origins", "resourceHash"}
COVERAGE_FIELDS = {"status", "scope", "reasonCode"}
SET_FIELDS = {
    "schemaVersion",
    "repository",
    "cycleInstanceId",
    "resources",
    "coverage",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "resourceSetHash",
}
COVERAGE_STATUS = "UNKNOWN"
COVERAGE_SCOPE = "strong-hosted-records"
COVERAGE_REASON = "AGENT_CYCLE_PROVIDER_COVERAGE_INCOMPLETE"


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise RuntimeError(code)
    return value


def _exact_locator(kind: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_RESOURCE_LOCATOR_INVALID")
    expected: dict[str, set[str]] = {
        "git-branch": {"repository", "branch"},
        "git-path": {"repository", "branch", "path"},
        "domain-subject": {"domain", "subjectKind", "subjectId"},
        "lease-scope": {"repository", "branch", "role", "sessionId"},
        "coordination-lease": {"leaseId"},
    }
    fields = expected.get(kind)
    if fields is None or set(value) != fields:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_LOCATOR_INVALID")
    out = copy.deepcopy(value)
    if kind in {"git-branch", "git-path", "lease-scope"}:
        if _text(out.get("repository"), "AGENT_CYCLE_RESOURCE_REPOSITORY_INVALID") != REPOSITORY:
            raise RuntimeError("AGENT_CYCLE_RESOURCE_REPOSITORY_INVALID")
    if kind == "git-branch":
        _text(out.get("branch"), "AGENT_CYCLE_RESOURCE_BRANCH_INVALID")
    elif kind == "git-path":
        _text(out.get("branch"), "AGENT_CYCLE_RESOURCE_BRANCH_INVALID")
        path = _text(out.get("path"), "AGENT_CYCLE_RESOURCE_PATH_INVALID")
        if path.startswith("/") or path.endswith("/") or any(
            part in {"", ".", ".."} for part in path.split("/")
        ):
            raise RuntimeError("AGENT_CYCLE_RESOURCE_PATH_INVALID")
    elif kind == "domain-subject":
        _text(out.get("domain"), "AGENT_CYCLE_RESOURCE_DOMAIN_INVALID")
        _text(out.get("subjectKind"), "AGENT_CYCLE_RESOURCE_SUBJECT_INVALID")
        _text(out.get("subjectId"), "AGENT_CYCLE_RESOURCE_SUBJECT_INVALID")
    elif kind == "lease-scope":
        _text(out.get("branch"), "AGENT_CYCLE_RESOURCE_LEASE_SCOPE_INVALID")
        _text(out.get("role"), "AGENT_CYCLE_RESOURCE_LEASE_SCOPE_INVALID")
        _text(out.get("sessionId"), "AGENT_CYCLE_RESOURCE_LEASE_SCOPE_INVALID")
    else:
        _text(out.get("leaseId"), "AGENT_CYCLE_RESOURCE_LEASE_INVALID")
    return out


def coverage() -> dict[str, str]:
    return {
        "status": COVERAGE_STATUS,
        "scope": COVERAGE_SCOPE,
        "reasonCode": COVERAGE_REASON,
    }


def validate_coverage(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != COVERAGE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_COVERAGE_INVALID")
    expected = coverage()
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_COVERAGE_INVALID")
    return value


def origin(
    source_kind: str, source_hash: str, operation: str | None = None
) -> dict[str, Any]:
    return {
        "sourceKind": _text(source_kind, "AGENT_CYCLE_RESOURCE_ORIGIN_INVALID"),
        "sourceHash": _hash(source_hash, "AGENT_CYCLE_RESOURCE_ORIGIN_INVALID"),
        "operation": None
        if operation is None
        else _text(operation, "AGENT_CYCLE_RESOURCE_ORIGIN_INVALID"),
    }


def validate_origin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ORIGIN_FIELDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_ORIGIN_INVALID")
    expected = origin(
        value.get("sourceKind"), value.get("sourceHash"), value.get("operation")
    )
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_ORIGIN_INVALID")
    return value


def resource(
    kind: str, locator: dict[str, Any], *origins: dict[str, Any]
) -> dict[str, Any]:
    if kind not in RESOURCE_KINDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_KIND_INVALID")
    canonical_locator = _exact_locator(kind, locator)
    canonical_origins = [copy.deepcopy(validate_origin(item)) for item in origins]
    canonical_origins.sort(
        key=lambda item: (
            item["sourceKind"],
            item["sourceHash"],
            item["operation"] or "",
        )
    )
    if not canonical_origins or len(canonical_origins) != len(
        {stable_hash(item) for item in canonical_origins}
    ):
        raise RuntimeError("AGENT_CYCLE_RESOURCE_ORIGINS_INVALID")
    identity = {"kind": kind, "locator": canonical_locator}
    return {
        **identity,
        "origins": canonical_origins,
        "resourceHash": stable_hash(identity),
    }


def validate_resource(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESOURCE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_FIELDS_INVALID")
    kind = value.get("kind")
    if kind not in RESOURCE_KINDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_KIND_INVALID")
    expected = resource(kind, value.get("locator"), *(value.get("origins") or []))
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_NOT_CANONICAL")
    return value


def _merge_resources(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in items:
        item = validate_resource(raw)
        key = (item["kind"], item["resourceHash"])
        current = by_identity.get(key)
        if current is None:
            by_identity[key] = copy.deepcopy(item)
            continue
        merged = current["origins"] + item["origins"]
        unique = {stable_hash(entry): entry for entry in merged}
        current["origins"] = sorted(
            (copy.deepcopy(entry) for entry in unique.values()),
            key=lambda entry: (
                entry["sourceKind"],
                entry["sourceHash"],
                entry["operation"] or "",
            ),
        )
    return [by_identity[key] for key in sorted(by_identity)]


def build_resource_set(
    *, repository: str, cycle_instance_id: str, resources: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    if repository != REPOSITORY:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_SET_REPOSITORY_INVALID")
    if not isinstance(cycle_instance_id, str) or CYCLE_RE.fullmatch(cycle_instance_id) is None:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_SET_CYCLE_INVALID")
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": repository,
        "cycleInstanceId": cycle_instance_id,
        "resources": _merge_resources(resources),
        "coverage": coverage(),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "resourceSetHash": stable_hash(body)}


def validate_resource_set(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SET_FIELDS:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_SET_FIELDS_INVALID")
    resources = value.get("resources")
    if not isinstance(resources, list):
        raise RuntimeError("AGENT_CYCLE_RESOURCE_SET_RESOURCES_INVALID")
    validate_coverage(value.get("coverage"))
    expected = build_resource_set(
        repository=value.get("repository"),
        cycle_instance_id=value.get("cycleInstanceId"),
        resources=resources,
    )
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_SET_MISMATCH")
    return value


def _git_branch(branch: str, source: dict[str, Any]) -> dict[str, Any]:
    return resource(
        "git-branch", {"repository": REPOSITORY, "branch": branch}, source
    )


def _git_path(branch: str, path: str, source: dict[str, Any]) -> dict[str, Any]:
    return resource(
        "git-path",
        {"repository": REPOSITORY, "branch": branch, "path": path},
        source,
    )


def resources_from_remote_command(command: dict[str, Any]) -> list[dict[str, Any]]:
    from tools import remote_canonical_execution as remote

    remote.validate_command(command)
    source_hash = remote.command_hash(command)
    target = command["target"]
    if command["kind"] == "domain":
        op = f"{target['domain']}.{target['action']}"
        src = origin("remote-canonical-command", source_hash, op)
        subject = target["subject"]
        return [
            resource(
                "domain-subject",
                {
                    "domain": target["domain"],
                    "subjectKind": subject["kind"],
                    "subjectId": subject["id"],
                },
                src,
            )
        ]

    operation = target["operation"]
    src = origin("remote-canonical-command", source_hash, operation)
    branch = target["branch"]
    found = [_git_branch(branch, src)]
    if "path" in target:
        found.append(_git_path(branch, target["path"], src))
    elif operation == "mutate-files":
        payload = command["payload"]
        for change in payload.get("changes", []):
            found.append(_git_path(branch, change["path"], src))
    return found


def resources_from_git_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    from tools import git_mutation_plan

    git_mutation_plan.validate(plan)
    operation = plan["operation"]
    if operation in {"create-pr", "merge-pr"}:
        raise RuntimeError("AGENT_CYCLE_RESOURCE_GIT_OPERATION_UNSUPPORTED")
    src = origin("git-mutation-plan", plan["planHash"], operation)
    target = plan["target"]
    branch = target["branch"]
    found = [_git_branch(branch, src)]
    if operation in {"create-file", "update-file", "delete-file"}:
        found.append(_git_path(branch, target["path"], src))
    elif operation == "mutate-files":
        for entry in plan["mutation"]["entries"]:
            found.append(_git_path(branch, entry["path"], src))
    return found


def resources_from_transition_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    from tools import transition_protocol

    transition_protocol.validate_plan(plan)
    src = origin(
        "transition-plan", plan["planHash"], f"{plan['domain']}.{plan['action']}"
    )
    subject = plan["subject"]
    return [
        resource(
            "domain-subject",
            {
                "domain": plan["domain"],
                "subjectKind": subject["kind"],
                "subjectId": subject["id"],
            },
            src,
        )
    ]


def resources_from_agent_tool_dispatch(
    dispatch: dict[str, Any],
) -> list[dict[str, Any]]:
    from tools.agent_tools import mutation_dispatch

    mutation_dispatch.validate_dispatch(dispatch)
    src = origin(
        "agent-tool-mutation-dispatch",
        dispatch["dispatchHash"],
        dispatch["command"]["target"].get("operation")
        or dispatch["command"]["target"].get("action"),
    )
    nested = resources_from_remote_command(dispatch["command"])
    return [resource(item["kind"], item["locator"], src) for item in nested]


def resources_from_write_lease_request(
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    from tools import agent_write_lifecycle

    agent_write_lifecycle.validate_request(request)
    src = origin(
        "agent-write-lease-request",
        agent_write_lifecycle.request_hash(request),
        request["action"],
    )
    actor = request["actor"]
    return [
        resource(
            "lease-scope",
            {
                "repository": REPOSITORY,
                "branch": request["branch"],
                "role": actor["role"],
                "sessionId": actor["sessionId"],
            },
            src,
        )
    ]


def resources_from_write_lease_result(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    from tools import agent_write_lifecycle

    agent_write_lifecycle.validate_result(result)
    src = origin("agent-write-lease-result", result["resultHash"], result["action"])
    actor = result["actor"]
    return [
        resource(
            "lease-scope",
            {
                "repository": REPOSITORY,
                "branch": result["branch"],
                "role": actor["role"],
                "sessionId": actor["sessionId"],
            },
            src,
        ),
        resource(
            "coordination-lease",
            {"leaseId": result["binding"]["leaseId"]},
            src,
        ),
    ]

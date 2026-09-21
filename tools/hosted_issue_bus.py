from __future__ import annotations

import json
from typing import Any


class HostedIssueBusError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedIssueBusError(code)
    return value


def _request_json(
    transport: Any,
    method: str,
    endpoint: str,
    *,
    payload: dict[str, Any] | None = None,
    invalid_code: str,
) -> Any:
    if transport is None:
        raise HostedIssueBusError("BLOCKED_EXECUTION_SURFACE")
    try:
        response = transport.request(method, endpoint, payload=payload) if payload is not None else transport.request(method, endpoint)
        return json.loads(response.body)
    except HostedIssueBusError:
        raise
    except (AttributeError, json.JSONDecodeError) as exc:
        raise HostedIssueBusError(invalid_code) from exc
    except Exception as exc:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_TRANSPORT_UNAVAILABLE") from exc


def validate_event_envelope(value: Any, *, repository: str, bus_title: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_EVENT_INVALID")
    issue, comment, observed = value.get("issue"), value.get("comment"), value.get("repository")
    if not all(isinstance(item, dict) for item in (issue, comment, observed)):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_EVENT_INVALID")
    if issue.get("pull_request") is not None:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_PR_COMMENT_FORBIDDEN")
    if issue.get("title") != bus_title:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_ACTOR_FORBIDDEN")
    if observed.get("full_name") != repository:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_REPOSITORY_MISMATCH")
    body = comment.get("body")
    if not isinstance(body, str):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_BODY_INVALID")
    return {"issue": issue, "comment": comment, "repository": observed, "body": body}


def event_identity(envelope: dict[str, Any]) -> dict[str, int]:
    try:
        issue, comment = envelope["issue"], envelope["comment"]
    except (KeyError, TypeError) as exc:
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_IDENTITY_INVALID") from exc
    return {
        "issueNumber": _positive(issue.get("number"), "HOSTED_ISSUE_BUS_IDENTITY_INVALID"),
        "commentId": _positive(comment.get("id"), "HOSTED_ISSUE_BUS_IDENTITY_INVALID"),
    }


def get_comment(transport: Any, *, repository: str, comment_id: int) -> dict[str, Any]:
    comment_id = _positive(comment_id, "HOSTED_ISSUE_BUS_COMMENT_ID_INVALID")
    value = _request_json(
        transport, "GET", f"repos/{repository}/issues/comments/{comment_id}",
        invalid_code="HOSTED_ISSUE_BUS_COMMENT_INVALID",
    )
    if not isinstance(value, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENT_INVALID")
    return value


def list_comments(transport: Any, *, repository: str, issue_number: int) -> list[dict[str, Any]]:
    issue_number = _positive(issue_number, "HOSTED_ISSUE_BUS_ISSUE_ID_INVALID")
    comments: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _request_json(
            transport, "GET",
            f"repos/{repository}/issues/{issue_number}/comments?per_page=100&page={page}",
            invalid_code="HOSTED_ISSUE_BUS_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENTS_INVALID")
        comments.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return comments
    raise HostedIssueBusError("HOSTED_ISSUE_BUS_COMMENTS_UNBOUNDED")


def find_open_issue(transport: Any, *, repository: str, title: str) -> int:
    matches: list[int] = []
    for page in range(1, 101):
        value = _request_json(
            transport, "GET",
            f"repos/{repository}/issues?state=open&per_page=100&page={page}",
            invalid_code="HOSTED_ISSUE_BUS_ISSUES_INVALID",
        )
        if not isinstance(value, list):
            raise HostedIssueBusError("HOSTED_ISSUE_BUS_ISSUES_INVALID")
        for issue in value:
            if isinstance(issue, dict) and issue.get("title") == title and issue.get("pull_request") is None:
                number = issue.get("number")
                if isinstance(number, int) and not isinstance(number, bool) and number > 0:
                    matches.append(number)
        if len(value) < 100:
            break
    if len(matches) != 1:
        raise HostedIssueBusError(
            "HOSTED_ISSUE_BUS_MISSING" if not matches else "HOSTED_ISSUE_BUS_AMBIGUOUS"
        )
    return matches[0]


def post_comment(transport: Any, *, repository: str, issue_number: int, body: str) -> int:
    issue_number = _positive(issue_number, "HOSTED_ISSUE_BUS_ISSUE_ID_INVALID")
    if not isinstance(body, str):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_BODY_INVALID")
    value = _request_json(
        transport, "POST", f"repos/{repository}/issues/{issue_number}/comments",
        payload={"body": body}, invalid_code="HOSTED_ISSUE_BUS_SUBMIT_INVALID",
    )
    if not isinstance(value, dict):
        raise HostedIssueBusError("HOSTED_ISSUE_BUS_SUBMIT_INVALID")
    return _positive(value.get("id"), "HOSTED_ISSUE_BUS_SUBMIT_INVALID")
